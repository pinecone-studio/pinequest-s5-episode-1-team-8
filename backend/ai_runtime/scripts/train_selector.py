"""
Хариулт сонгогчийг сургана (бүхэлдээ локал, API-гүй, ~1-3 мин).

  TENANT=pinecone .venv/bin/python scripts/train_selector.py

Өгөгдөл:
  1. faq.json-ийн асуултууд (TODO хариулттайг алгасна)
  2. knowledge өгүүлбэр бүр өөрөө
  3. tenants/<slug>/training/examples.json: гараар бичсэн + вэбээр "заасан" бодит дуудлагын асуултууд,
     training/auto.json: мэдээллээс автоматаар үүсгэсэн асуултууд (scripts/autogen.py)
  + STT-ийн алдааг дуурайсан хувилбарууд (үсэг солих/алгасах, "за", "тэгээд" угтвар)

Үр дүн: tenants/<slug>/knowledge_index/selector.npz + selector.json. AI сервер дараагийн дуудлага дээр өөрөө ачаална.
Шалгалтын асуултуудад (tests/eval_questions.json эсвэл автоматаар үүсгэсэн tests/auto_eval.json)
сургахгүй: төгсгөлд нь дүрэм ганцаараа vs сонгогчтой нарийвчлалыг хэмжиж,
сонгогч муу гарвал идэвхгүй болгоно (enabled=false) -> чанар хэзээ ч буурахгүй.
"""
import asyncio
import difflib
import json
import os
import random
import sys
import time
import warnings

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("HF_HUB_OFFLINE", "1")
warnings.filterwarnings("ignore")

import tenant as tenants  # noqa: E402
from selector import (FILES, char_matrix, compute_idf, fact_label, multi_label,  # noqa: E402
                      normalize, text_key)
from stream_voice import lex_stems  # noqa: E402

T = tenants.current()
OUT_DIR = T.kb_index_dir
STAGE = os.path.join(OUT_DIR, ".selector_new")
EXAMPLE_FILES = [T.training_path, T.auto_training_path]
CACHE = os.path.join("data", "selector_cache.npz")
AUGMENT = 3                      # жишээ бүрт STT-маягийн хэдэн хувилбар
# (C, үсгийн n-gram-ын жин). Туршилтаар: C өндөр (64+), үсгийн жин бага (0.2) хамгийн сайн;
# kNN болон LR+kNN холимог муу гарсан.
GRID = [(c, w) for c in (64.0, 256.0) for w in (0.2, 0.4)]
FOLDS = 4

CONFUSE = {"ө": "о", "о": "ө", "ү": "у", "у": "ү", "э": "и", "и": "э", "а": "э", "й": "", "ь": "", "ы": "и"}
PREFIX = ["за ", "тэгээд ", "би ", "асуух гэсэн юм ", "нөгөө ", "аан ", "энэ "]
SUFFIX = ["", "", " юм", " вэ", " тэ"]
END_WORDS = {"вэ", "бэ", "уу", "үү", "юу", "юм"}


def log(msg: str):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def noisy(text: str, rng: random.Random) -> str:
    """STT-ийн түгээмэл алдааг дуурайна: эгшиг солих, үсэг алгасах, угтвар/сүүл үг."""
    words = normalize(text).split()
    for _ in range(rng.randint(1, 2)):
        op = rng.random()
        long = [i for i, w in enumerate(words) if len(w) >= 5]
        if op < 0.35 and long:                       # үсэг солих ("хөтөлбөр" -> "хөтолбөр")
            i = rng.choice(long)
            w = words[i]
            pos = [j for j, ch in enumerate(w) if ch in CONFUSE]
            if pos:
                j = rng.choice(pos)
                words[i] = w[:j] + CONFUSE[w[j]] + w[j + 1:]
        elif op < 0.6 and long:                      # үе алгасах ("хөтөлбөр" -> "хөлбөр")
            i = rng.choice(long)
            w = words[i]
            j = rng.randint(1, len(w) - 3)
            words[i] = w[:j] + w[j + rng.randint(1, 2):]
        elif op < 0.8:
            words.insert(0, rng.choice(PREFIX).strip())
        elif len(words) > 2 and words[-1] in END_WORDS:
            words.pop()
        else:
            words.append(rng.choice(SUFFIX).strip())
    return " ".join(w for w in words if w)


def load_data():
    """-> (rows [(text, label, group)], answers {label: spec}, warnings)"""
    faq = json.load(open(T.faq_path, encoding="utf-8"))
    facts = [f["text"] for f in json.load(open(os.path.join(OUT_DIR, "facts.json"), encoding="utf-8"))["facts"]
             if f.get("audio")]
    by_norm = {normalize(t): t for t in facts}
    answered = {f["id"] for f in faq["faq"] if "TODO" not in f["answer"]}
    answers: dict[str, dict] = {"other": {"kind": "other"}, "clarify": {"kind": "clarify"}}
    rows: list[tuple[str, str, int]] = []
    warns: list[str] = []

    def resolve(text: str) -> str | None:
        if normalize(text) in by_norm:
            return by_norm[normalize(text)]
        close = difflib.get_close_matches(normalize(text), list(by_norm), n=1, cutoff=0.85)
        return by_norm[close[0]] if close else None

    def add(q: str, label: str):
        rows.append((q, label, len(rows)))

    for f in faq["faq"]:
        if f["id"] in answered:
            answers[f"faq:{f['id']}"] = {"kind": "faq", "id": f["id"]}
            for q in f["questions"]:
                add(q, f"faq:{f['id']}")
    for t in facts:
        answers[fact_label(t)] = {"kind": "facts", "texts": [t]}
        add(t, fact_label(t))

    examples = []
    for path in EXAMPLE_FILES:
        if os.path.exists(path):
            examples += json.load(open(path, encoding="utf-8"))["examples"]
    for ex in examples:
        q = ex.get("q", "").strip()
        if not q:
            continue
        if "faq" in ex:
            if ex["faq"] not in answered:
                warns.append(f"FAQ '{ex['faq']}' алга/TODO: {q}")
                continue
            add(q, f"faq:{ex['faq']}")
        elif "fact" in ex or "facts" in ex:
            texts = [ex["fact"]] if "fact" in ex else ex["facts"]
            found = [resolve(t) for t in texts]
            if None in found:
                warns.append(f"өгүүлбэр олдсонгүй (мэдээлэл өөрчлөгдсөн?): {q}")
                continue
            label = fact_label(found[0]) if len(found) == 1 else multi_label(found)
            answers.setdefault(label, {"kind": "facts", "texts": found})
            add(q, label)
        elif ex.get("label") in ("other", "clarify"):
            add(q, ex["label"])
    return rows, answers, warns


def embed_all(embedder, texts: list[str]) -> np.ndarray:
    """bge-m3 embedding, кэштэй (дахин сургахад зөвхөн шинэ текстийг тооцно)."""
    cache: dict[str, np.ndarray] = {}
    if os.path.exists(CACHE):
        z = np.load(CACHE)
        if str(z["model"]) == embedder.model_name:
            cache = dict(zip(z["keys"].tolist(), z["emb"]))
    keys = [text_key(t) for t in texts]
    todo = sorted({k: t for k, t in zip(keys, texts) if k not in cache}.items())
    if todo:
        log(f"embedding: {len(todo)} шинэ текст (кэшэнд {len(cache)})")
        vecs = embedder.query([t for _, t in todo])
        cache.update({k: v for (k, _), v in zip(todo, vecs)})
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        np.savez(CACHE, model=embedder.model_name, keys=np.array(list(cache)),
                 emb=np.stack(list(cache.values())))
    return np.stack([cache[k] for k in keys]).astype(np.float32)


def features(E, texts, idf, char_w):
    from scipy.sparse import csr_matrix, hstack
    return hstack([csr_matrix(E), char_matrix(texts, idf) * char_w]).tocsr()


def fit(X, y, C):
    from sklearn.linear_model import LogisticRegression
    return LogisticRegression(C=C, max_iter=3000).fit(X, y)


def eval_file() -> str | None:
    """Гараар бичсэн шалгалт байвал түүнийг, үгүй бол мэдээллээс автоматаар үүсгэснийг."""
    for path in (T.eval_path, T.auto_eval_path):
        if os.path.exists(path):
            return path
    return None


async def evaluate(router) -> tuple[int, int]:
    import eval_runner
    ok, total, _ = await eval_runner.run_eval(router, quiet=True, eval_file=eval_file())
    return ok, total


def main():
    from sklearn.model_selection import GroupKFold

    from embed import Embedder

    t0 = time.time()
    rows, answers, warns = load_data()
    for w in warns:
        log(f"анхаар: {w}")
    rng = random.Random(7)
    texts, labels, groups = [], [], []
    for q, label, g in rows:
        variants = [normalize(q)] + [noisy(q, rng) for _ in range(AUGMENT)]
        for v in dict.fromkeys(variants):       # давхардлыг хасна, дарааллыг хадгална
            texts.append(v)
            labels.append(label)
            groups.append(g)
    classes = sorted(set(labels))
    log(f"{len(rows)} жишээ ({len(texts)} хувилбартай), {len(classes)} хариулт")

    faq_meta = json.load(open(os.path.join(T.faq_index_dir, "faq_index.json"), encoding="utf-8"))
    embedder = Embedder(faq_meta["embed_model"])
    E = embed_all(embedder, texts)
    idf = compute_idf(texts)
    y = np.array(labels)

    # Хамгийн сайн тохиргоог cross-validation-аар (нэг жишээний хувилбарууд нэг fold-д)
    best = None
    for C, char_w in GRID:
        X = features(E, texts, idf, char_w)
        correct = 0
        for tr, te in GroupKFold(FOLDS).split(X, y, groups):
            correct += int((fit(X[tr], y[tr], C).predict(X[te]) == y[te]).sum())
        acc = correct / len(y)
        log(f"  C={C:<5} үсгийн жин={char_w}: CV нарийвчлал {acc:.1%}")
        if best is None or acc > best[0]:
            best = (acc, C, char_w)
    cv_acc, C, char_w = best

    model = fit(features(E, texts, idf, char_w), y, C)
    W = model.coef_.astype(np.float32)
    meta = {
        "labels": model.classes_.tolist(), "answers": {k: answers[k] for k in model.classes_},
        "emb_w": 1.0, "char_w": char_w, "C": C, "embed_model": embedder.model_name,
        "examples": len(rows), "rows": len(texts), "cv_acc": round(cv_acc, 4),
        "trained_at": time.time(), "warnings": warns, "enabled": True,
        "per_label": {k: int((y == k).sum()) for k in model.classes_},
        # Хамгаалалтад: хариулт бүрийн сургалтын асуултуудын үгс (ижил утгатай, мэдээлэлд байхгүй үг)
        "label_stems": {k: sorted(set().union(*[lex_stems(q) for q, lab, _ in rows if lab == k]))
                        for k in model.classes_},
    }
    # Түр хавтсанд хадгалж шалгана -> AI сервер дутуу файл уншихгүй
    os.makedirs(STAGE, exist_ok=True)
    np.savez(os.path.join(STAGE, FILES[0]), W=W, b=model.intercept_.astype(np.float32), idf=idf)
    with open(os.path.join(STAGE, FILES[1]), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)

    # Шалгалт: дүрэм ганцаараа vs сонгогчтой (eval асуултууд сургалтад ороогүй)
    from selector import Selector
    from stream_voice import FAQRouter
    router = FAQRouter(T.faq_index_dir, OUT_DIR, embedder)
    router.selector = None
    if eval_file():
        base = asyncio.run(evaluate(router))
        router.attach_selector(Selector(STAGE))
        with_sel = asyncio.run(evaluate(router))
        meta["eval"] = {"rules": base, "selector": with_sel, "file": os.path.basename(eval_file())}
        meta["enabled"] = with_sel[0] >= base[0]
    else:                                 # шалгалтын асуулт алга -> харьцуулах боломжгүй
        base = with_sel = (0, 0)
        meta["eval"] = None
    with open(os.path.join(STAGE, FILES[1]), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    for name in FILES:                    # npz эхлээд, json сүүлд (AI сервер json-ийн өөрчлөлтөөр ачаална)
        os.replace(os.path.join(STAGE, name), os.path.join(OUT_DIR, name))
    os.rmdir(STAGE)

    if meta["eval"]:
        log(f"шалгалт ({meta['eval']['file']}): дүрэм {base[0]}/{base[1]}, сонгогчтой {with_sel[0]}/{with_sel[1]}")
    else:
        log("шалгалтын асуулт алга -> харьцуулалтгүйгээр идэвхжүүлэв")
    log(("Дууслаа: сонгогч ИДЭВХТЭЙ" if meta["enabled"] else
         "Дууслаа: сонгогч дүрмээс муу тул ИДЭВХГҮЙ (жишээ нэмээд дахин сургана уу)")
        + f" · CV {cv_acc:.1%} · {time.time() - t0:.0f}с")


if __name__ == "__main__":
    main()
