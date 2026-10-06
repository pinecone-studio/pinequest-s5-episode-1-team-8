"""
Дуудлагын лог (SQLite): дуудлага бүрийн яриа, AI ямар замаар хариулсан, бүртгэл (lead).
Байгууллага бүр өөрийн файлтай: tenants/<slug>/data/receptionist.db (Tenant.db_path).
Утасны AI бичнэ, вэб уншиж үйлчилгээний чанарыг хянана.

  calls:    uuid, caller, started_at, ended_at, duration
  messages: call_uuid, ts, role (user|assistant), text, route, score, stt_sec, latency
  leads:    бүртгүүлэх / ажилтан эргэж залгах хүсэлт
"""
import os
import sqlite3
import time
from contextlib import contextmanager

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

# AI хариулж чадаагүйг илтгэх route-ууд -> вэбэд "хариулж чадаагүй асуулт" болж харагдана
UNANSWERED_ROUTES = ("repeat", "handoff", "clarify", "en_repeat", "en_handoff")


@contextmanager
def connect(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path, timeout=5)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()


def start_call(path: str, uuid: str, caller: str | None = None, ts: float | None = None):
    with connect(path) as con:
        con.execute("INSERT OR IGNORE INTO calls (uuid, caller, started_at) VALUES (?, ?, ?)",
                    (uuid, caller, ts or time.time()))


def end_call(path: str, uuid: str, ts: float | None = None):
    now = ts or time.time()
    with connect(path) as con:
        con.execute("UPDATE calls SET ended_at = ?, duration = ? - started_at WHERE uuid = ?", (now, now, uuid))


def add_message(path: str, uuid: str, role: str, text: str, route: str | None = None, score: float | None = None,
                stt_sec: float | None = None, latency: float | None = None, ts: float | None = None):
    with connect(path) as con:
        con.execute("INSERT INTO messages (call_uuid, ts, role, text, route, score, stt_sec, latency) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (uuid, ts or time.time(), role, text, route, score, stt_sec, latency))


def add_lead(path: str, call_uuid: str, name: str | None, phone: str | None, phone_raw: str | None = None,
             caller: str | None = None, reason: str = "lead", question: str | None = None, ts: float | None = None):
    with connect(path) as con:
        con.execute("INSERT INTO leads (call_uuid, created_at, name, phone, phone_raw, caller, reason, question) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (call_uuid, ts or time.time(), name, phone, phone_raw, caller, reason, question))
