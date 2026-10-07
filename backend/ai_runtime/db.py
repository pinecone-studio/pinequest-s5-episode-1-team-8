"""
Дуудлагын лог (SQLite): дуудлага бүрийн яриа, AI ямар замаар хариулсан.
Веб (web/app.py) эндээс уншиж үйлчилгээний чанарыг хянана.
Байгууллага бүр өөрийн файлтай: tenants/<slug>/data/receptionist.db (path=None -> TENANT орчны хувьсагч).

  calls:    uuid, caller, started_at, ended_at, duration
  messages: call_uuid, ts, role (user|assistant), text, route, score, stt_sec, latency
"""
import os
import sqlite3
import time
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH")     # тест: тогтмол зам. Үгүй бол байгууллагын


def db_path(path: str | None = None) -> str:
    if path or DB_PATH:
        return os.path.abspath(path or DB_PATH)
    import tenant
    return tenant.current().db_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    uuid       TEXT PRIMARY KEY,
    caller     TEXT,
    started_at REAL,
    ended_at   REAL,
    duration   REAL
);
CREATE TABLE IF NOT EXISTS messages (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    call_uuid TEXT,
    ts        REAL,
    role      TEXT,
    text      TEXT,
    route     TEXT,
    score     REAL,
    stt_sec   REAL,
    latency   REAL
);
CREATE INDEX IF NOT EXISTS idx_messages_call ON messages(call_uuid);
CREATE TABLE IF NOT EXISTS leads (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    call_uuid  TEXT,
    created_at REAL,
    name       TEXT,
    phone      TEXT,      -- баталгаажсан 8 оронтой дугаар (таахгүй: эс бөгөөс NULL)
    phone_raw  TEXT,      -- STT-ийн түүхий бичвэр (ажилтан шалгахад)
    caller     TEXT,      -- SIP Caller ID
    course     TEXT,
    reason     TEXT,      -- lead | handoff
    question   TEXT,      -- handoff үед хариулж чадаагүй асуулт
    status     TEXT DEFAULT 'new',   -- new | contacted | done
    notes      TEXT
);
"""

# AI хариулж чадаагүйг илтгэх route-ууд -> вебэд "хариулж чадаагүй асуулт" болж харагдана
UNANSWERED_ROUTES = ("repeat", "handoff", "clarify", "en_repeat", "en_handoff")


@contextmanager
def connect(path: str | None = None):
    path = db_path(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path, timeout=5)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()


def start_call(uuid: str, caller: str | None = None, path: str | None = None):
    with connect(path) as con:
        con.execute("INSERT OR IGNORE INTO calls (uuid, started_at) VALUES (?, ?)", (uuid, time.time()))
        if caller:
            con.execute("UPDATE calls SET caller = ? WHERE uuid = ?", (caller, uuid))


def end_call(uuid: str, path: str | None = None):
    now = time.time()
    with connect(path) as con:
        con.execute("UPDATE calls SET ended_at = ?, duration = ? - started_at WHERE uuid = ?",
                    (now, now, uuid))


def add_message(uuid: str, role: str, text: str, route: str | None = None,
                score: float | None = None, stt_sec: float | None = None,
                latency: float | None = None, path: str | None = None):
    with connect(path) as con:
        con.execute(
            "INSERT INTO messages (call_uuid, ts, role, text, route, score, stt_sec, latency) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (uuid, time.time(), role, text, route, score, stt_sec, latency))


def add_lead(call_uuid, name, phone, phone_raw, caller, reason, question=None,
             course=None, path: str | None = None):
    """-> шинэ бүртгэлийн id (people.ensure_code-д)."""
    with connect(path) as con:
        cur = con.execute(
            "INSERT INTO leads (call_uuid, created_at, name, phone, phone_raw, caller, course, reason, question) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (call_uuid, time.time(), name, phone, phone_raw, caller, course, reason, question))
        return cur.lastrowid


def caller_of(call_uuid: str, path: str | None = None) -> str | None:
    with connect(path) as con:
        row = con.execute("SELECT caller FROM calls WHERE uuid = ?", (call_uuid,)).fetchone()
    return row["caller"] if row else None
