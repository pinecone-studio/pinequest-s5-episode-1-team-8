"""
Хувийн RAG: бүртгэлтэй хүн бүрийн мэдээлэл. AI туслах (assistant.py) кодоор баталгаажуулаад уншиж, өөрчилнө;
сануулгын дуудлага (reminders.py) эвентэд ирэх эсэхийг асууж энд тэмдэглэнэ. Байгууллагын хавтсаар (tenants/<slug>/).

Хадгалалт — байгууллагын data/receptionist.db (SQLite, дуудлагын логтой нэг файл):
  lead_codes   (lead_id, code)                    4 оронтой бүртгэлийн код -> залгагчийг таних
  person_docs  (lead_id, field, text, emb)        хүний баримтууд + bge-m3 вектор (утасны AI тооцоолж хадгална)
  lead_changes (lead_id, ts, field, old, new, source, call_uuid)   өөрчлөлтийн түүх
Уулзалтын цаг: data/reminders.json (сануулгын дуудлагатай нэг эх сурвалж).
Сул цаг: data/settings.json "booking" — байхгүй бол Даваа-Баасан 10-17 цаг, цагт 1 хүн, 14 хоног.
Эвентүүд: data/settings.json "events" [{"name", "at"}] — тэр эвентэд бүртгүүлсэн хүн бүрт өмнөх өдрийн 11:00-д
"Та ирэх хэвээрээ юу?" дуудлага автоматаар товлогдоно (sync_event_reminders); хариу нь хувийн RAG-д (attendance).

Ажилтан (багш) утсаар: ажилтны кодоор нэвтэрч, БҮХ хүний баримтаас нэрээр хайж бусдын бүртгэлийг өөрчилнө
("Болдын цагийг Баасан гараг руу шилжүүл") — өгөгдлийн сан руу гараар орох шаардлагагүй.

AI SQL бичихгүй: зөвхөн эдгээр функцийг дуудна, залгагч/ажилтан кодоороо баталгаажсаны дараа л.
Ажилтан гараар юу ч өөрчлөх шаардлагагүй: код бүртгэл үүсэхэд автоматаар, сул цаг ажлын цагаас.
"""
import difflib
import hmac
import json
import os
import random
import re
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Ulaanbaatar")
CODE_LEN = 4
STAFF_PIN_LEN = 6        # ажилтны код: утсаар бусдын бүртгэлийг өөрчлөх эрх (settings.json "staff_pin")
NAME_MATCH = 0.75        # нэрээр хайх доод оноо (STT "Балд" ~ "Болд")
SCHEMA = """
CREATE TABLE IF NOT EXISTS lead_codes (
    lead_id    INTEGER PRIMARY KEY,
    code       TEXT UNIQUE NOT NULL,
    created_at REAL
);
CREATE TABLE IF NOT EXISTS person_docs (
    lead_id    INTEGER,
    field      TEXT,      -- name | phone | appointment | status | course
    text       TEXT,
    emb        BLOB,      -- float32 bge-m3 (NULL = дахин тооцоолно)
    updated_at REAL,
    PRIMARY KEY (lead_id, field)
);
CREATE TABLE IF NOT EXISTS lead_changes (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id   INTEGER,
    ts        REAL,
    field     TEXT,       -- phone | appointment | status | attendance
    old       TEXT,
    new       TEXT,
    source    TEXT,       -- ai | web
    call_uuid TEXT
);
CREATE INDEX IF NOT EXISTS idx_changes_lead ON lead_changes(lead_id);
"""
BOOKING = {"days": [0, 1, 2, 3, 4], "start": 10, "end": 17, "capacity": 1, "horizon": 14}
CANCELED = ("declined", "canceled")          # эдгээр төлөвтэй сануулга цаг эзлэхгүй
STATUS_WORDS = {"new": "шинэ, ажилтан удахгүй холбогдоно", "contacted": "ажилтан холбогдсон", "done": "дууссан",
                "canceled": "цуцлагдсан"}

WEEKDAYS = ["Даваа", "Мягмар", "Лхагва", "Пүрэв", "Баасан", "Бямба", "Ням"]
MONTHS = ["нэгдүгээр", "хоёрдугаар", "гуравдугаар", "дөрөвдүгээр", "тавдугаар", "зургаадугаар", "долоодугаар",
          "наймдугаар", "есдүгээр", "аравдугаар", "арван нэгдүгээр", "арван хоёрдугаар"]
UNIT_GEN = ["", "нэгний", "хоёрны", "гурвын", "дөрвөний", "тавны", "зургааны", "долооны", "наймны", "есний"]
TENS = {1: ("арван", "аравны"), 2: ("хорин", "хорины"), 3: ("гучин", "гучны")}
HOUR_WORDS = {7: "долоон", 8: "найман", 9: "есөн", 10: "арван", 11: "арван нэгэн", 12: "арван хоёр",
              13: "арван гурван", 14: "арван дөрвөн", 15: "арван таван", 16: "арван зургаан", 17: "арван долоон",
              18: "арван найман", 19: "арван есөн", 20: "хорин", 21: "хорин нэгэн"}


# ---------------- огноо -> үг (утсаар уншихад; аудио нь бэлэн клипүүдээс) ----------------

def day_words(day: int) -> str:
    """15 -> "арван тавны"."""
    tens, unit = divmod(day, 10)
    return UNIT_GEN[unit] if not tens else (TENS[tens][1] if not unit else f"{TENS[tens][0]} {UNIT_GEN[unit]}")


def date_words(d: datetime) -> str:
    """2026-10-15 -> "аравдугаар сарын арван тавны"."""
    return f"{MONTHS[d.month - 1]} сарын {day_words(d.day)}"


def slot_parts(d: datetime) -> list[str]:
    """Уулзалтын цагийг уншиж буй клипүүд: гараг, сар, өдөр, цаг."""
    return [f"{WEEKDAYS[d.weekday()]} гараг", f"{MONTHS[d.month - 1]} сарын", day_words(d.day),
            f"{HOUR_WORDS.get(d.hour, str(d.hour))} цагт"]


def slot_text(d: datetime) -> str:
    return " ".join(slot_parts(d))


def all_date_texts(booking: dict | None = None) -> list[str]:
    """Аудио бэлдэхэд: гараг, сар, өдөр бүр, ажлын цаг бүрийн клип (нэг удаа, ~70 богино өгүүлбэр)."""
    b = {**BOOKING, **(booking or {})}
    hours = sorted(set(range(int(b["start"]), int(b["end"]))) | {9, 10, 11, 12, 13, 14, 15, 16, 17, 18})
    return ([f"{w} гараг" for w in WEEKDAYS] + [f"{m} сарын" for m in MONTHS] +
            [day_words(d) for d in range(1, 32)] + [f"{HOUR_WORDS[h]} цагт" for h in hours if h in HOUR_WORDS])


def parse_local(value: str) -> datetime:
    """"2026-10-15T10:00" (Улаанбаатарын цаг) -> datetime."""
    return datetime.strptime(value[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=TZ)


def fmt(d: datetime) -> str:
    return d.strftime("%Y-%m-%dT%H:%M")


# ---------------- хадгалалт ----------------

def db_path(tdir: str) -> str:
    return os.path.join(tdir, "data", "receptionist.db")


@contextmanager
def connect(tdir: str):
    path = db_path(tdir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path, timeout=5)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()


def _read_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write_json(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def reminders_path(tdir: str) -> str:
    return os.path.join(tdir, "data", "reminders.json")


def booking(tdir: str) -> dict:
    st = _read_json(os.path.join(tdir, "data", "settings.json"))
    return {**BOOKING, **(st.get("booking") or {})}


def lead(tdir: str, lead_id: int) -> dict | None:
    with connect(tdir) as con:
        try:
            row = con.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
        except sqlite3.OperationalError:          # дуудлагын лог хараахан үүсээгүй
            return None
    return dict(row) if row else None


def log_change(con, lead_id: int, field: str, old, new, source: str, call_uuid: str | None):
    con.execute("INSERT INTO lead_changes (lead_id, ts, field, old, new, source, call_uuid) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (lead_id, time.time(), field, old, new, source, call_uuid))


# ---------------- бүртгэлийн код ----------------

def ensure_code(tdir: str, lead_id: int) -> str:
    """Бүртгэлийн кодыг буцаана (байхгүй бол давхцахгүй 4 оронтой код үүсгэнэ)."""
    with connect(tdir) as con:
        row = con.execute("SELECT code FROM lead_codes WHERE lead_id=?", (lead_id,)).fetchone()
        if row:
            return row["code"]
        used = {r["code"] for r in con.execute("SELECT code FROM lead_codes")}
        rng = random.SystemRandom()
        while True:
            code = f"{rng.randrange(10 ** CODE_LEN):0{CODE_LEN}d}"
            # 1111, 1234 гэх мэт таахад амархан кодыг алгасна
            if code not in used and len(set(code)) > 1 and code not in "0123456789" and code not in "9876543210":
                break
        con.execute("INSERT INTO lead_codes (lead_id, code, created_at) VALUES (?, ?, ?)", (lead_id, code, time.time()))
    return code


def ensure_all_codes(tdir: str) -> dict[int, str]:
    """Бүх бүртгэлд код (вэб, хуучин бүртгэлүүд) -> {lead_id: code}."""
    with connect(tdir) as con:
        try:
            ids = [r["id"] for r in con.execute("SELECT id FROM leads")]
        except sqlite3.OperationalError:
            ids = []
        have = {r["lead_id"]: r["code"] for r in con.execute("SELECT lead_id, code FROM lead_codes")}
    for i in ids:
        if i not in have:
            have[i] = ensure_code(tdir, i)
    return {i: have[i] for i in ids}


def find(tdir: str, code: str) -> dict | None:
    """Код -> бүртгэл (таарахгүй бол None)."""
    code = re.sub(r"\D", "", code or "")
    if len(code) != CODE_LEN:
        return None
    with connect(tdir) as con:
        row = con.execute("SELECT lead_id FROM lead_codes WHERE code=?", (code,)).fetchone()
    return lead(tdir, row["lead_id"]) if row else None


# ---------------- ажилтны код, нэрээр хайх ----------------

def settings_path(tdir: str) -> str:
    return os.path.join(tdir, "data", "settings.json")


def staff_pin(tdir: str, create: bool = True) -> str | None:
    """Ажилтны 6 оронтой код (байхгүй бол үүсгэнэ — вэбийн Бүртгэл хуудсанд харагдана)."""
    st = _read_json(settings_path(tdir))
    if st.get("staff_pin") or not create:
        return st.get("staff_pin")
    return new_staff_pin(tdir)


def new_staff_pin(tdir: str) -> str:
    rng = random.SystemRandom()
    while True:
        pin = f"{rng.randrange(10 ** STAFF_PIN_LEN):0{STAFF_PIN_LEN}d}"
        if len(set(pin)) > 2:
            break
    st = _read_json(settings_path(tdir))
    st["staff_pin"] = pin
    _write_json(settings_path(tdir), st)
    return pin


def check_staff_pin(tdir: str, pin: str) -> bool:
    real = staff_pin(tdir, create=False)
    return bool(real) and hmac.compare_digest(real, re.sub(r"\D", "", pin or ""))


def _words(text: str) -> list[str]:
    return re.findall(r"[а-яөүёa-z]+", (text or "").lower())


def name_score(text: str, name: str) -> float:
    """Ярианд хүний нэр байгаа эсэх: "Болдын цагийг" ~ "Болд" (нөхцөл, STT-ийн 1 үсгийн алдааг тэвчинэ)."""
    best = 0.0
    for n in _words(name):
        if len(n) < 3:
            continue
        for w in _words(text):
            best = max(best, difflib.SequenceMatcher(None, w[:len(n)], n).ratio() if len(w) >= len(n) - 1 else 0.0)
    return best


def find_by_name(tdir: str, text: str) -> list[dict]:
    """Ажилтны хайлт: БҮХ хүний нэрийн баримтаас (person_docs) -> таарсан бүртгэлүүд, шинэ нь эхэндээ."""
    ensure_all_codes(tdir)
    with connect(tdir) as con:
        try:
            rows = [dict(r) for r in con.execute("SELECT * FROM leads ORDER BY created_at DESC, id DESC")]
        except sqlite3.OperationalError:
            return []
    scored = [(name_score(text, r.get("name") or ""), r) for r in rows]
    hits = [(sc, r) for sc, r in scored if sc >= NAME_MATCH]
    hits.sort(key=lambda x: -x[0])          # sort тогтвортой -> ижил оноотойд шинэ нь эхэндээ
    for _, r in hits:
        docs(tdir, r["id"])
    return [r for _, r in hits]


def strip_name(text: str, name: str) -> str:
    """Командаас нэрийг хасна: "Болдын цагийг солих" -> "цагийг солих" (хүсэлт таних, өдөр хайхад)."""
    names = [n for n in _words(name) if len(n) >= 3]
    keep = [w for w in (text or "").split()
            if not any(difflib.SequenceMatcher(None, w.lower()[:len(n)], n).ratio() >= NAME_MATCH for n in names)]
    return " ".join(keep)


# ---------------- уулзалтын цаг (reminders.json) ----------------

def appointment(tdir: str, lead_id: int) -> datetime | None:
    """Товлосон уулзалт (эвентийн "ирэх үү" дуудлага биш — тэр нь хөтөлбөр/эвентийн баримтад)."""
    item = _read_json(reminders_path(tdir)).get("items", {}).get(str(lead_id))
    if not item or item.get("status") in CANCELED or not item.get("appointment") or item.get("event"):
        return None
    return parse_local(item["appointment"])


def taken(tdir: str, exclude_lead: int | None = None) -> dict[str, int]:
    """Цаг бүрт хэдэн хүн товлогдсон (цуцлагдсаныг тооцохгүй)."""
    out: dict[str, int] = {}
    for k, v in _read_json(reminders_path(tdir)).get("items", {}).items():
        if v.get("status") in CANCELED or not v.get("appointment") or str(exclude_lead) == k or v.get("event"):
            continue                          # эвентийн дуудлага уулзалтын сул цаг эзлэхгүй
        out[v["appointment"][:16]] = out.get(v["appointment"][:16], 0) + 1
    return out


def free_slots(tdir: str, now: datetime | None = None, exclude_lead: int | None = None) -> list[datetime]:
    """Ажлын цагаас үүссэн сул цагууд (дор хаяж 2 цагийн дараах), ойроос нь эхэлж."""
    b = booking(tdir)
    now = now or datetime.now(TZ)
    used = taken(tdir, exclude_lead)
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    for i in range(int(b["horizon"]) + 1):
        day = day0 + timedelta(days=i)
        if day.weekday() not in b["days"]:
            continue
        for h in range(int(b["start"]), int(b["end"])):
            at = day.replace(hour=h)
            if at >= now + timedelta(hours=2) and used.get(fmt(at), 0) < int(b["capacity"]):
                out.append(at)
    return out


def relative_words(d: datetime, now: datetime | None = None) -> str:
    """Хайлтад: "өнөөдөр", "маргааш", "нөгөөдөр" (залгагч ингэж хэлдэг)."""
    now = now or datetime.now(TZ)
    return {0: "өнөөдөр", 1: "маргааш", 2: "нөгөөдөр"}.get((d.date() - now.date()).days, "")


def _set_reminder(tdir: str, lead_id: int, when: datetime | None, now: datetime):
    path = reminders_path(tdir)
    data = _read_json(path)
    data.setdefault("items", {})
    old = data["items"].get(str(lead_id), {})
    if when is None:
        if old:
            old.update(status="canceled", last_outcome="canceled")
    else:
        # Өмнөх өдрийн 11:00-д сануулна; уулзалт хэт ойрхон бол залгагч яг одоо утсаар баталсан тул дахин залгахгүй
        remind = (when - timedelta(days=1)).replace(hour=11, minute=0)
        status = "scheduled" if remind > now + timedelta(hours=1) else "confirmed"
        data["items"][str(lead_id)] = {"lead_id": lead_id, "appointment": fmt(when), "call_at": remind.timestamp(),
                                       "status": status, "attempts": 0, "text": None,   # вэб загвараар дахин бичнэ
                                       "history": old.get("history", []), "created_at": int(time.time()),
                                       "changed_by": "ai"}
    _write_json(path, data)


# ---------------- AI-ийн өөрчлөлтүүд ----------------

def same_person(tdir: str, lead_id: int) -> list[int]:
    """Тэр хүний бүх бүртгэл (Bootcamp, эвент ...): ижил баталгаажсан дугаартай бүртгэлүүд."""
    with connect(tdir) as con:
        row = con.execute("SELECT phone FROM leads WHERE id=?", (lead_id,)).fetchone()
        if not row:
            raise KeyError(lead_id)
        if not row["phone"]:
            return [lead_id]
        ids = [r["id"] for r in con.execute("SELECT id FROM leads WHERE phone=? ORDER BY id", (row["phone"],))]
    return ids or [lead_id]


def set_phone(tdir: str, lead_id: int, phone: str, source: str = "ai", call_uuid: str | None = None) -> str | None:
    """Дугаар солих -> холбогдох БҮХ газарт: тэр хүний бүх бүртгэл (ижил хуучин дугаартай), хувийн баримтууд;
    сануулгын дуудлага шинэ дугаар руу залгана (дуудлагын үед бүртгэлээс уншдаг). -> хуучин дугаар."""
    ids = same_person(tdir, lead_id)
    with connect(tdir) as con:
        old = con.execute("SELECT phone FROM leads WHERE id=?", (lead_id,)).fetchone()["phone"]
        for i in ids:
            con.execute("UPDATE leads SET phone=? WHERE id=?", (phone, i))
            log_change(con, i, "phone", old, phone, source, call_uuid)
    for i in ids:
        docs(tdir, i)
    return old


def set_appointment(tdir: str, lead_id: int, when: datetime, source: str = "ai", call_uuid: str | None = None,
                    now: datetime | None = None) -> datetime | None:
    """Сул цаг бол товлоно -> хуучин цаг. Сул биш бол ValueError."""
    now = now or datetime.now(TZ)
    if when not in free_slots(tdir, now, exclude_lead=lead_id):
        raise ValueError("энэ цаг сул биш")
    old = appointment(tdir, lead_id)
    _set_reminder(tdir, lead_id, when, now)
    with connect(tdir) as con:
        log_change(con, lead_id, "appointment", fmt(old) if old else None, fmt(when), source, call_uuid)
    docs(tdir, lead_id)
    return old


def cancel_appointment(tdir: str, lead_id: int, source: str = "ai", call_uuid: str | None = None) -> datetime | None:
    old = appointment(tdir, lead_id)
    if old is None:
        return None
    _set_reminder(tdir, lead_id, None, datetime.now(TZ))
    with connect(tdir) as con:
        log_change(con, lead_id, "appointment", fmt(old), None, source, call_uuid)
    docs(tdir, lead_id)
    return old


def cancel_registration(tdir: str, lead_id: int, source: str = "ai", call_uuid: str | None = None) -> str | None:
    """Хөтөлбөр/эвентийн бүртгэлийг цуцална ("Эвентэд очиж чадахгүй боллоо"): төлөв canceled + товлосон цаг
    суллагдана -> хуучин төлөв."""
    with connect(tdir) as con:
        row = con.execute("SELECT status FROM leads WHERE id=?", (lead_id,)).fetchone()
        if not row:
            raise KeyError(lead_id)
        con.execute("UPDATE leads SET status='canceled' WHERE id=?", (lead_id,))
        log_change(con, lead_id, "status", row["status"], "canceled", source, call_uuid)
    cancel_appointment(tdir, lead_id, source, call_uuid)
    path = reminders_path(tdir)                       # эвентийн "ирэх үү" дуудлага хэрэггүй болсон
    data = _read_json(path)
    item = data.get("items", {}).get(str(lead_id))
    if item and item.get("event") and item.get("status") not in CANCELED:
        item.update(status="canceled", last_outcome="canceled")
        _write_json(path, data)
    docs(tdir, lead_id)
    return row["status"]


def events(tdir: str) -> list[dict]:
    """Байгууллагын эвентүүд: [{"name": "AI Hackathon эвент", "at": "2026-10-18T10:00"}]."""
    return [e for e in _read_json(settings_path(tdir)).get("events", []) if e.get("name") and e.get("at")]


def set_events(tdir: str, items: list[dict]):
    st = _read_json(settings_path(tdir))
    st["events"] = [{"name": " ".join(e["name"].split())[:120], "at": fmt(parse_local(e["at"]))} for e in items]
    _write_json(settings_path(tdir), st)


def event_of(tdir: str, course: str | None) -> dict | None:
    """Бүртгэлийн хөтөлбөр/эвентийн нэр -> эвент (нэр нь агуулагдсан бол)."""
    c = (course or "").lower()
    return next((e for e in events(tdir) if e["name"].lower() in c or (c and c in e["name"].lower())), None)


def sync_event_reminders(tdir: str, now: datetime | None = None) -> int:
    """Эвентэд бүртгүүлсэн хүн бүрт өмнөх өдрийн 11:00-д "ирэх үү" дуудлага товлоно (хэн ч гараар оруулахгүй).
    Аль хэдийн сануулгатай, цуцалсан, эвент өнгөрсөн бол алгасна. -> шинээр товлосон тоо."""
    now = now or datetime.now(TZ)
    if not events(tdir):
        return 0
    with connect(tdir) as con:
        try:
            rows = [dict(r) for r in con.execute("SELECT * FROM leads WHERE course IS NOT NULL AND status != 'canceled'")]
        except sqlite3.OperationalError:
            return 0
    path = reminders_path(tdir)
    data = _read_json(path)
    data.setdefault("items", {})
    added = 0
    for row in rows:
        ev = event_of(tdir, row["course"])
        if not ev or str(row["id"]) in data["items"] or not (row.get("phone") or row.get("caller")):
            continue
        at = parse_local(ev["at"])
        if at <= now:
            continue
        call_at = max((at - timedelta(days=1)).replace(hour=11, minute=0), now)
        data["items"][str(row["id"])] = {"lead_id": row["id"], "appointment": fmt(at), "call_at": call_at.timestamp(),
                                         "status": "scheduled", "attempts": 0, "text": None, "history": [],
                                         "created_at": int(time.time()), "event": ev["name"], "changed_by": "auto"}
        added += 1
    if added:
        _write_json(path, data)
    return added


def attendance(tdir: str, lead_id: int) -> bool | None:
    item = _read_json(reminders_path(tdir)).get("items", {}).get(str(lead_id)) or {}
    return item.get("attendance")


def mark_attendance(tdir: str, lead_id: int, coming: bool, source: str = "call", call_uuid: str | None = None):
    """Сануулгын дуудлагын хариу -> хувийн RAG: "ирнэ" / "ирэхгүй" (ирэхгүй бол бүртгэл цуцлагдана).
    reminders.json-ийн item["attendance"]-ийг дуудагч (reminders.apply_outcome) бичнэ."""
    with connect(tdir) as con:
        row = con.execute("SELECT status FROM leads WHERE id=?", (lead_id,)).fetchone()
        if not row:
            return
        log_change(con, lead_id, "attendance", None, "ирнэ" if coming else "ирэхгүй", source, call_uuid)
        if not coming and row["status"] != "canceled":
            con.execute("UPDATE leads SET status='canceled' WHERE id=?", (lead_id,))
            log_change(con, lead_id, "status", row["status"], "canceled", source, call_uuid)
    docs(tdir, lead_id)


def changes(tdir: str, lead_id: int | None = None, limit: int = 200) -> list[dict]:
    with connect(tdir) as con:
        if lead_id is None:
            rows = con.execute("SELECT * FROM lead_changes ORDER BY ts DESC LIMIT ?", (limit,))
        else:
            rows = con.execute("SELECT * FROM lead_changes WHERE lead_id=? ORDER BY ts DESC LIMIT ?", (lead_id, limit))
        return [dict(r) for r in rows]


# ---------------- хувийн баримтууд (RAG) ----------------

def doc_texts(tdir: str, lead_id: int) -> dict[str, str]:
    """Хүний бүртгэлээс баримтууд (утасны AI эдгээрээс хайж хариулна)."""
    row = lead(tdir, lead_id)
    if not row:
        return {}
    out = {}
    if row.get("name"):
        out["name"] = f"Таны бүртгэлтэй нэр {row['name']}"
    if row.get("phone"):
        out["phone"] = f"Таны бүртгэлтэй утасны дугаар {row['phone']}"
    when = appointment(tdir, lead_id)
    out["appointment"] = (f"Таны уулзалтын цаг {slot_text(when)}" if when
                          else "Танд товлосон уулзалтын цаг алга")
    out["status"] = f"Таны бүртгэлийн төлөв {STATUS_WORDS.get(row.get('status') or 'new', row.get('status'))}"
    coming = attendance(tdir, lead_id)
    if coming is not None:
        out["attendance"] = f"Эвентэд ирэх эсэх: {'ирнэ' if coming else 'ирэхгүй'} (өмнөх өдөр утсаар асуусан)"
    if row.get("course"):
        ev = event_of(tdir, row["course"])
        when = f" ({slot_text(parse_local(ev['at']))})" if ev else ""
        out["course"] = f"Таны бүртгүүлсэн хөтөлбөр, эвент: {row['course']}{when}"
    return out


def docs(tdir: str, lead_id: int) -> list[dict]:
    """Баримтуудыг person_docs-д шинэчилж буцаана: [{"field", "text", "emb": bytes | None}].
    Текст өөрчлөгдсөн баримтын векторыг арилгана (AI дараагийн хайлтад дахин тооцоолно)."""
    texts = doc_texts(tdir, lead_id)
    now = time.time()
    with connect(tdir) as con:
        old = {r["field"]: dict(r) for r in con.execute("SELECT * FROM person_docs WHERE lead_id=?", (lead_id,))}
        for field, text in texts.items():
            if field not in old or old[field]["text"] != text:
                con.execute("INSERT OR REPLACE INTO person_docs (lead_id, field, text, emb, updated_at) "
                            "VALUES (?, ?, ?, NULL, ?)", (lead_id, field, text, now))
        for field in set(old) - set(texts):
            con.execute("DELETE FROM person_docs WHERE lead_id=? AND field=?", (lead_id, field))
        rows = con.execute("SELECT field, text, emb FROM person_docs WHERE lead_id=?", (lead_id,)).fetchall()
    return [dict(r) for r in rows]


def save_emb(tdir: str, lead_id: int, field: str, text: str, emb: bytes):
    with connect(tdir) as con:
        con.execute("UPDATE person_docs SET emb=? WHERE lead_id=? AND field=? AND text=?", (emb, lead_id, field, text))
