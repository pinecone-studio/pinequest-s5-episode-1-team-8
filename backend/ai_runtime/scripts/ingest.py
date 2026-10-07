"""
Байгууллагын knowledge/ хавтасны баримтуудыг RAG индекс + УРЬДЧИЛСАН АУДИО болгоно.

  TENANT=pinecone .venv/bin/python scripts/ingest.py             # индекс + өгүүлбэр бүрийн аудио
  TENANT=pinecone .venv/bin/python scripts/ingest.py --no-audio  # зөвхөн индекс (хурдан шалгахад)

Дэмжих төрөл: .txt .md .pdf .docx
Гаралт (tenants/<slug>/knowledge_index/):
  index.npz, chunks.json  - LLM-д context болгох хэсгүүд
  facts.npz, facts.json   - өгүүлбэр бүр + харьяалах гарчиг (## ...) + аудио файлын зам
  аудио: data/tts_cache/<hash>.wav (текст өөрчлөгдөөгүй бол дахин үүсгэхгүй, байгууллагууд хуваалцана)

Утасны дуудлагын үеэр TTS ажиллахгүй: асуултад таарсан өгүүлбэрийн аудиог шууд тоглуулна.
Баримт нэмэх/засах бүрт дахин ажиллуулна.
"""
import json
import os
import re
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import tenant as tenants  # noqa: E402
from embed import EMBED_MODEL, Embedder  # noqa: E402
from recordings import recording_for, text_hash  # noqa: E402

TENANT = tenants.current()
KNOWLEDGE_DIR = os.path.abspath(os.getenv("KNOWLEDGE_DIR", TENANT.knowledge_dir))
OUT_DIR = os.path.abspath(os.getenv("KNOWLEDGE_INDEX", TENANT.kb_index_dir))
CHUNK_CHARS = 500      # утсаар ярихад тохирох богино хэсэг
OVERLAP_CHARS = 80
FACT_MIN_CHARS = 15    # үүнээс богино мөрийг (гарчиг гэх мэт) өгүүлбэр гэж үзэхгүй


def read_file(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".txt", ".md"):
        with open(path, encoding="utf-8") as f:
            return f.read()
    if ext == ".pdf":
        from pypdf import PdfReader
        return "\n\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
    if ext == ".docx":
        from docx import Document
        return "\n\n".join(p.text for p in Document(path).paragraphs)
    return ""


def split_chunks(text: str) -> list[str]:
    """Догол мөрөөр хуваагаад CHUNK_CHARS хүртэл нийлүүлнэ. Урт догол мөрийг өгүүлбэрээр хуваана."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    pieces = []
    for p in paras:
        if len(p) <= CHUNK_CHARS:
            pieces.append(p)
        else:
            pieces += [s.strip() for s in re.split(r"(?<=[.!?])\s+", p) if s.strip()]

    chunks, buf = [], ""
    for piece in pieces:
        if buf and len(buf) + len(piece) + 1 > CHUNK_CHARS:
            chunks.append(buf)
            buf = buf[-OVERLAP_CHARS:] + " " + piece
        else:
            buf = f"{buf}\n{piece}" if buf else piece
    if buf:
        chunks.append(buf)
    return chunks


def split_facts(text: str) -> list[tuple[str, str | None]]:
    """Утсаар чангаар уншихад тохирох өгүүлбэрүүд + харьяалах гарчиг (## Төлбөр). Гарчиг нь
    тодруулах сэдэв, асуулт автоматаар үүсгэхэд хэрэглэгдэнэ. Жагсаалтын тэмдэг, богино мөрийг хасна."""
    facts, section = [], None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            if line.startswith("##") and title:
                section = title
            continue
        if not line:
            continue
        line = re.sub(r"^([-*•]|\d+[.)])\s+", "", line)
        line = re.sub(r"[*_`]", "", line)
        for sent in re.split(r"(?<=[.!?])\s+", line):
            sent = sent.strip()
            if len(sent) >= FACT_MIN_CHARS:
                facts.append((sent, section))
    return facts


def synth_facts(facts: list[dict]):
    """Өгүүлбэр бүрийг аудио болгоно. Хүний бичлэг (recordings/) байвал түүнийг, үгүй бол TTS.
    Кэштэй тул зөвхөн шинэ/өөрчлөгдсөн өгүүлбэрт TTS ажиллана."""
    import soundfile as sf

    import shutil
    from stream_voice import clip_key, clip_seed, eleven_sample_path, engine_for, tts_seeds, voice_tag
    seeds = tts_seeds()
    audio_dir = tenants.TTS_CACHE           # бүх байгууллагад нийтлэг кэш
    os.makedirs(audio_dir, exist_ok=True)
    todo, recorded = [], 0
    for f in facts:
        rec = recording_for(f["text"], TENANT.recordings_dir)
        if rec:
            f["audio"] = rec
            recorded += 1
            continue
        f["engine"] = engine_for(f["text"])          # "oron" | "eleven" (Хоолой хуудасны сонголт)
        f["seed"] = clip_seed(f["text"], f["engine"], seeds)
        f["audio"] = os.path.join(audio_dir, f"{clip_key(f['text'], f['seed'], voice_tag(f['engine']))}.wav")
        if (not os.path.exists(f["audio"]) and f["engine"] == "eleven" and not f["seed"]
                and os.path.exists(eleven_sample_path(f["text"]))):
            shutil.copyfile(eleven_sample_path(f["text"]), f["audio"])   # харьцуулалтад үүсгэснийг ашиглана
        if not os.path.exists(f["audio"]):
            todo.append(f)
    print(f"Аудио: {recorded} хүний бичлэг, {len(facts) - recorded - len(todo)} кэшээс, "
          f"{len(todo)} TTS-ээр шинээр үүсгэнэ")
    if not todo:
        return

    from stream_voice import ElevenTTS, OronTTS
    from stt import HF_MN, WhisperSTT
    engines = {"eleven": ElevenTTS()} if any(f["engine"] == "eleven" for f in todo) else {}
    tts = engines["oron"] = OronTTS() if any(f["engine"] == "oron" for f in todo) else None
    from stream_voice import TTS_CANDIDATES
    if tts and TTS_CANDIDATES > 1:   # 1 бол STT ачаалахгүй (8GB машинд санах ой хэмнэнэ)
        # MLX (Metal) + TTS-ийн torch MPS нэг процесст -> Metal assertion-оор унасан -> CPU
        tts.scorer = WhisperSTT(HF_MN, device="cpu")
    t0 = time.perf_counter()
    for i, f in enumerate(todo, 1):
        wav, sr = engines[f["engine"]].synth(f["text"], f["seed"])
        sf.write(f["audio"], wav, sr)
        left = (time.perf_counter() - t0) / i * (len(todo) - i)
        print(f"  [{i}/{len(todo)}] {len(wav) / sr:4.1f}s  ~{left / 60:.0f} мин үлдсэн  {f['text'][:60]}")


def main():
    no_audio = "--no-audio" in sys.argv
    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    files = sorted(
        os.path.join(dp, f) for dp, _, fs in os.walk(KNOWLEDGE_DIR) for f in fs
        if f.lower().endswith((".txt", ".md", ".pdf", ".docx")) and f.lower() != "readme.md"
    )
    if not files:
        print(f"{KNOWLEDGE_DIR} хоосон байна. Мэдээллээ (вэб -> Мэдээлэл) оруулаад дахин ажиллуулна уу.")
        return

    chunks, sources, facts, docs = [], [], [], []
    for path in files:
        rel = os.path.relpath(path, KNOWLEDGE_DIR)
        text = read_file(path)
        parts = split_chunks(text)
        doc_facts = split_facts(text)
        chunks += parts
        sources += [rel] * len(parts)
        facts += [{"text": t, "source": rel, "section": sec} for t, sec in doc_facts]
        docs.append({"file": rel, "chunks": len(parts), "facts": len(doc_facts)})
        print(f"  {rel}: {len(parts)} хэсэг, {len(doc_facts)} өгүүлбэр")

    # Ижил өгүүлбэр олон баримтад давтагдвал нэг удаа л хадгална
    seen, unique = set(), []
    for f in facts:
        if f["text"] not in seen:
            seen.add(f["text"])
            unique.append(f)
    facts = unique

    embedder = Embedder()
    print(f"Embedding ({embedder.model_name}): {len(chunks)} хэсэг, {len(facts)} өгүүлбэр...")
    chunk_emb = embedder.passage(chunks)
    fact_emb = embedder.passage([f["text"] for f in facts])
    del embedder  # TTS-д санах ой чөлөөлнө
    import gc
    import torch
    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()   # үгүй бол bge-m3 GPU-д түгжигдэж TTS swap-д орсон (өгүүлбэр бүр 10+ мин)

    os.makedirs(OUT_DIR, exist_ok=True)
    np.savez(os.path.join(OUT_DIR, "index.npz"), emb=chunk_emb)
    np.savez(os.path.join(OUT_DIR, "facts.npz"), emb=fact_emb)
    meta = {"embed_model": EMBED_MODEL,
            "indexed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "documents": docs}
    with open(os.path.join(OUT_DIR, "chunks.json"), "w", encoding="utf-8") as f:
        json.dump({**meta, "chunks": [{"text": c, "source": s} for c, s in zip(chunks, sources)]},
                  f, ensure_ascii=False, indent=2)

    if no_audio:
        for fact in facts:
            fact["audio"] = None
    else:
        synth_facts(facts)
    with open(os.path.join(OUT_DIR, "facts.json"), "w", encoding="utf-8") as f:
        json.dump({**meta, "facts": facts}, f, ensure_ascii=False, indent=2)

    print(f"Дууслаа: {len(files)} баримт, {len(chunks)} хэсэг, {len(facts)} өгүүлбэр -> {OUT_DIR}/")


if __name__ == "__main__":
    main()
