"""Pinecone AI-ийн хариултын чанарыг тогтмол 30 асуултаар хэмжинэ.

Хурдан бүтэц шалгах:
  .venv/bin/python backend/test_ai_evaluation.py --validate-only

Бүрэн evaluation (дотоод backend/ai_runtime + backend/data ашиглана):
  .venv/bin/python backend/test_ai_evaluation.py

TTS болон ElevenLabs ашиглахгүй. Embedding model зөвхөн локал cache-аас ачаална.
"""
from __future__ import annotations

import asyncio
from collections import Counter
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = PROJECT_ROOT / "backend" / "tests" / "fixtures" / "pinecone_eval_questions.json"
MIN_ACCURACY = float(os.getenv("AI_EVAL_PASS", "0.85"))
ALLOWED_SPECIAL = {"REPEAT", "CLARIFY", "HANDOFF"}


def load_cases() -> list[dict]:
    with FIXTURE.open(encoding="utf-8") as file:
        data = json.load(file)
    cases = data.get("questions")
    if not isinstance(cases, list) or len(cases) != 30:
        raise ValueError("Evaluation fixture яг 30 асуулттай байна")

    seen: set[str] = set()
    for index, case in enumerate(cases, 1):
        question, expected, category = case.get("q"), case.get("expect"), case.get("category")
        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"#{index}: q хоосон байна")
        if question in seen:
            raise ValueError(f"#{index}: давхардсан асуулт: {question}")
        if not isinstance(expected, (str, list)) or not expected:
            raise ValueError(f"#{index}: expect буруу байна")
        if isinstance(expected, list) and not all(isinstance(item, str) and item for item in expected):
            raise ValueError(f"#{index}: expect жагсаалт зөвхөн текст байна")
        if not isinstance(category, str) or not category:
            raise ValueError(f"#{index}: category хоосон байна")
        seen.add(question)
    return cases


def validate_only(cases: list[dict]) -> int:
    categories = Counter(case["category"] for case in cases)
    special = sum(
        any(item in ALLOWED_SPECIAL for item in ([case["expect"]] if isinstance(case["expect"], str) else case["expect"]))
        for case in cases
    )
    print(f"AI evaluation fixture: {len(cases)} асуулт ✓")
    for category, total in sorted(categories.items()):
        print(f"  {category}: {total}")
    print(f"  тусгай хариулт (REPEAT/CLARIFY/HANDOFF): {special}")
    return 0


def run_inside_runtime() -> int:
    """Project Python-оор дотоод runtime/data дээр тусгаарласан process ажиллуулна."""
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))
    import knowledge_jobs
    from config import TENANTS_DIR

    runtime = Path(knowledge_jobs.runtime_root())
    python = Path(knowledge_jobs.python_executable())
    index = Path(TENANTS_DIR) / "pinecone" / "knowledge_index"
    required = [index / name for name in ("chunks.json", "index.npz", "facts.json", "facts.npz")]
    missing = [path.relative_to(PROJECT_ROOT) for path in required if not path.is_file()]
    if missing:
        print("AI evaluation ажиллуулах knowledge index бэлэн биш байна:", file=sys.stderr)
        for path in missing:
            print(f"  - {path}", file=sys.stderr)
        print("\nВэбийн «Мэдээлэл → Аудио бэлдэх» товчийг дараад дахин ажиллуулна уу.", file=sys.stderr)
        return 2
    env = {
        **os.environ,
        "TENANT": "pinecone",
        "HF_HUB_OFFLINE": "1",
        "AI_RUNTIME_ROOT": str(runtime),
        "_PINECONE_AI_EVAL_INSIDE": "1",
    }
    return subprocess.run([str(python), str(Path(__file__).resolve())], cwd=runtime, env=env, check=False).returncode


def text_only_router():
    """Production өгөгдлөөр түр индекс үүсгэнэ; TTS болон жинхэнэ аудиод хүрэхгүй."""
    import numpy as np
    import soundfile as sf

    import tenant as tenants
    from embed import Embedder
    from lead import DIGITS
    from stream_voice import FAQRouter, lex_stems

    tenant = tenants.current()
    temp = tempfile.TemporaryDirectory(prefix="pinecone_ai_eval_")
    root = Path(temp.name)
    faq_dir, kb_dir = root / "faq_audio", root / "knowledge_index"
    faq_dir.mkdir()
    kb_dir.mkdir()
    shutil.copy2(Path(tenant.config_path), root / "config.json")

    silent = root / "silent.wav"
    sf.write(silent, np.zeros(2400, dtype=np.float32), 24000)
    for name in ("chunks.json", "index.npz", "facts.npz"):
        shutil.copy2(Path(tenant.kb_index_dir) / name, kb_dir / name)
    with (Path(tenant.kb_index_dir) / "facts.json").open(encoding="utf-8") as file:
        facts = json.load(file)
    for fact in facts.get("facts", []):
        fact["audio"] = str(silent)
    with (kb_dir / "facts.json").open("w", encoding="utf-8") as file:
        json.dump(facts, file, ensure_ascii=False)
    for name in ("selector.json", "selector.npz"):
        source = Path(tenant.kb_index_dir) / name
        if source.is_file():
            shutil.copy2(source, kb_dir / name)

    with Path(tenant.faq_path).open(encoding="utf-8") as file:
        source = json.load(file)
    phrases = tenant.phrases()
    clip = lambda text: {"text": text, "audio": str(silent)}  # noqa: E731
    faq, questions, row_to_faq, row_topic = [], [], [], []
    for item in source.get("faq", []):
        if "TODO" in item.get("answer", ""):
            continue
        faq.append({"id": item["id"], "topic": item.get("topic"),
                    "answer": item["answer"], "audio": str(silent)})
        for question in item.get("questions", []):
            questions.append(question)
            row_to_faq.append(len(faq) - 1)
            row_topic.append(None)
    for item in source.get("faq", []):
        if "TODO" in item.get("answer", "") and item.get("topic"):
            for question in item.get("questions", []):
                questions.append(question)
                row_to_faq.append(-1)
                row_topic.append(item["topic"])

    embedder = Embedder()
    embeddings = embedder.query(questions) if questions else np.zeros(
        (0, embedder.model.get_sentence_embedding_dimension()), dtype=np.float32)
    np.savez(faq_dir / "faq_index.npz", emb=embeddings)
    clarify_options = [
        {"keys": item.get("keys") or sorted(lex_stems(item["label"])),
         "question": item.get("question") or item["label"]}
        for item in tenant.config().get("clarify_topics", [])
    ]
    meta = {
        "tenant": tenant.slug,
        "embed_model": embedder.model_name,
        "greeting": clip(source.get("greeting") or phrases["greeting"]),
        "fillers": [clip(text) for text in (source.get("fillers") or phrases["fillers"])],
        "holds": [clip(text) for text in phrases["holds"]],
        "error": clip(phrases["error"]),
        "repeat": clip(phrases["repeat"]),
        "clarify": clip(phrases["clarify"]),
        "clarify_options": clarify_options,
        "generic_stems": sorted(tenant.generic_stems()),
        "lead": {key: clip(text) for key, text in phrases["lead"].items()},
        "digits": [clip(text) for text in DIGITS],
        "topics": {key: clip(value["bridge"]) for key, value in source.get("topics", {}).items()},
        "faq": faq,
        "questions": questions,
        "row_to_faq": row_to_faq,
        "row_topic": row_topic,
        "all_audio": [str(silent)],
    }
    with (faq_dir / "faq_index.json").open("w", encoding="utf-8") as file:
        json.dump(meta, file, ensure_ascii=False)
    return temp, FAQRouter(str(faq_dir), str(kb_dir), embedder)


async def evaluate(cases: list[dict]) -> int:
    runtime = os.environ.get("AI_RUNTIME_ROOT")
    if not runtime:
        raise RuntimeError("AI_RUNTIME_ROOT тохируулаагүй")
    sys.path.insert(0, runtime)
    from stream_voice import respond

    temp, router = text_only_router()
    failures = []

    async def silent(_wav, _sr):
        return None

    special = {"REPEAT": router.repeat()["text"], "CLARIFY": router.clarify()["text"],
               "HANDOFF": router.error()["text"]}
    correct = 0
    try:
        for case in cases:
            meta: dict = {}
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                reply = await respond(case["q"], [], router, None, None, play_fn=silent, meta=meta)
            expected = case["expect"] if isinstance(case["expect"], list) else [case["expect"]]
            if any(special.get(item, item) in reply for item in expected):
                correct += 1
            else:
                failures.append((case, reply, meta))
    finally:
        temp.cleanup()

    failed_questions = {case["q"] for case, _, _ in failures}
    by_category: dict[str, list[int]] = {}
    for case in cases:
        result = by_category.setdefault(case["category"], [0, 0])
        result[1] += 1
        result[0] += case["q"] not in failed_questions

    print("\nAI evaluation")
    for category, (ok, count) in sorted(by_category.items()):
        print(f"  {category}: {ok}/{count} ({ok / count:.0%})")
    accuracy = correct / len(cases)
    print(f"  НИЙТ: {correct}/{len(cases)} ({accuracy:.0%}), босго {MIN_ACCURACY:.0%}")
    for case, reply, meta in failures:
        note = f" — {case['note']}" if case.get("note") else ""
        print(f"  ✗ {case['q']}{note}")
        print(f"    хүлээсэн: {case['expect']}")
        score = meta.get("score")
        route = meta.get("route")
        route_info = f"{route} {score:.2f}" if isinstance(score, (int, float)) else str(route)
        print(f"    гарсан: [{route_info}] {reply[:120]}")
    return 0 if accuracy >= MIN_ACCURACY else 1


def main() -> int:
    try:
        cases = load_cases()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Evaluation fixture буруу: {exc}", file=sys.stderr)
        return 2
    if "--validate-only" in sys.argv:
        return validate_only(cases)
    if os.getenv("_PINECONE_AI_EVAL_INSIDE") != "1":
        return run_inside_runtime()
    return asyncio.run(evaluate(cases))


if __name__ == "__main__":
    raise SystemExit(main())
