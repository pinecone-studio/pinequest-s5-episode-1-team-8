"""
Байгууллагын бүх RAG нэг өгөгдлийн санд: tenants/<slug>/data/receptionist.db (SQLite).
SIM-TRUNK ба вэб (pinequest) хоёуланд ЯГ ижил файл.

  knowledge_docs  байгууллагын RAG: мэдээллийн өгүүлбэр (fact) + аудио, том хэсэг (chunk), FAQ асуулт — bge-m3 вектортой
  person_docs     хувийн RAG: хүн бүрийн баримт (people.py)
  calls, messages, leads, lead_codes, lead_changes   дуудлага, бүртгэл, өөрчлөлт

"Аудио бэлдэх" бүрийн төгсгөлд sync() индексийг (knowledge_index/, faq_audio/) энд бичнэ.
Утасны AI асахдаа бүгдийг санах ойд ачаалж хайна (1мс-ээс бага) — дуудлагын үеэр DB руу хүлээлтгүй.
Аудио (wav) дискэнд, DB зөвхөн замыг нь хадгална.
"""
import json
import os
import sqlite3
import time

import numpy as np

SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_docs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT,      -- fact | chunk | faq_question
    text        TEXT,
    source      TEXT,      -- мэдээллийн файл эсвэл FAQ id
    section     TEXT,
    audio       TEXT,      -- бэлэн аудионы зам (fact, FAQ хариулт)
    emb         BLOB,      -- float32 вектор
    embed_model TEXT,
    built_at    REAL
);
CREATE INDEX IF NOT EXISTS idx_knowledge_kind ON knowledge_docs(kind);
"""


def db_path(tdir: str) -> str:
    return os.path.join(tdir, "data", "receptionist.db")


def _connect(tdir: str):
    path = db_path(tdir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path, timeout=5)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def _load(path_json: str, path_npz: str, key: str, npz_key: str = "emb"):
    try:
        with open(path_json, encoding="utf-8") as f:
            meta = json.load(f)
        emb = np.load(path_npz)[npz_key]
    except (OSError, ValueError, KeyError):
        return None, None
    return meta, emb


def collect(tdir: str) -> list[tuple]:
    """Бэлдсэн индексийн файлуудаас мөрүүд: (kind, text, source, section, audio, emb, embed_model)."""
    rows = []
    kb = os.path.join(tdir, "knowledge_index")
    meta, emb = _load(os.path.join(kb, "facts.json"), os.path.join(kb, "facts.npz"), "facts")
    if meta and len(emb) == len(meta["facts"]):
        rows += [("fact", x["text"], x.get("source"), x.get("section"), x.get("audio"), v, meta["embed_model"])
                 for x, v in zip(meta["facts"], emb)]
    meta, emb = _load(os.path.join(kb, "chunks.json"), os.path.join(kb, "index.npz"), "chunks")
    if meta and len(emb) == len(meta["chunks"]):
        rows += [("chunk", x["text"], x.get("source"), None, None, v, meta["embed_model"])
                 for x, v in zip(meta["chunks"], emb)]
    fa = os.path.join(tdir, "faq_audio")
    meta, emb = _load(os.path.join(fa, "faq_index.json"), os.path.join(fa, "faq_index.npz"), "faq")
    if meta and len(emb) == len(meta.get("questions", [])):
        topics = meta.get("row_topic") or [None] * len(emb)
        for q, row, topic, v in zip(meta["questions"], meta["row_to_faq"], topics, emb):
            faq = meta["faq"][row] if row >= 0 else {}
            rows.append(("faq_question", q, faq.get("id"), topic, faq.get("audio"), v, meta["embed_model"]))
    return rows


def sync(tdir: str) -> dict:
    """Индексийг knowledge_docs руу бүтнээр нь солино (нэг transaction — AI/вэб хагас өгөгдөл харахгүй)."""
    rows = collect(tdir)
    now = time.time()
    con = _connect(tdir)
    try:
        with con:
            con.execute("DELETE FROM knowledge_docs")
            con.executemany("INSERT INTO knowledge_docs (kind, text, source, section, audio, emb, embed_model, built_at) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            [(k, t, s, sec, a, np.asarray(v, np.float32).tobytes(), m, now)
                             for k, t, s, sec, a, v, m in rows])
    finally:
        con.close()
    return stats(tdir)


def stats(tdir: str) -> dict:
    """Нэг DB-д юу байгаа вэ (вэб, танилцуулгад)."""
    con = _connect(tdir)
    try:
        kinds = {r["kind"]: r["n"] for r in con.execute("SELECT kind, COUNT(*) n FROM knowledge_docs GROUP BY kind")}
        row = con.execute("SELECT embed_model, LENGTH(emb) b, built_at FROM knowledge_docs LIMIT 1").fetchone()
        tables = {r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}

        def count(table: str) -> int:
            return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] if table in tables else 0
        out = {"facts": kinds.get("fact", 0), "chunks": kinds.get("chunk", 0), "faq_questions": kinds.get("faq_question", 0),
               "person_docs": count("person_docs"), "people": count("lead_codes"), "calls": count("calls"),
               "messages": count("messages"), "leads": count("leads"), "changes": count("lead_changes"),
               "embed_model": row["embed_model"] if row else None, "dim": (row["b"] // 4) if row else 0,
               "built_at": row["built_at"] if row else None}
    finally:
        con.close()
    out["db_bytes"] = os.path.getsize(db_path(tdir)) if os.path.exists(db_path(tdir)) else 0
    return out


def search(tdir: str, vec: np.ndarray, kind: str = "fact", k: int = 3) -> list[tuple[str, float]]:
    """DB-ээс шууд хайх (шалгалт, вэб): [(текст, оноо)]. Утасны AI санах ойн хуулбараас хайдаг."""
    con = _connect(tdir)
    try:
        rows = con.execute("SELECT text, emb FROM knowledge_docs WHERE kind=?", (kind,)).fetchall()
    finally:
        con.close()
    if not rows:
        return []
    m = np.stack([np.frombuffer(r["emb"], np.float32) for r in rows])
    s = m @ np.asarray(vec, np.float32)
    top = np.argsort(-s)[:k]
    return [(rows[i]["text"], float(s[i])) for i in top]
