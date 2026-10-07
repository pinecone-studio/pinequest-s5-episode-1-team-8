"""
Нэмэлт (SIM-TRUNK-д алга): AI-аас гарах сануулгын дуудлага.

  Ажилтан бүртгэлд уулзалтын огноо/цаг оноох -> товлосон цагт AI залгана (GSM gateway / SIP trunk / iMac)
  -> "Сайн байна уу, Болд. ... аравдугаар сарын арван тавны 10:00 цагт ирээрэй. Баталгаажуулах бол 1, цуцлах бол 2"
  -> confirmed | declined | unconfirmed | no_answer | busy | failed  -> Telegram мэдэгдэл

tenants/<slug>/data/reminders.json   {"items": {"<lead_id>": {...}}}
tenants/<slug>/data/reminder_audio/<хоолой>/<hash>.wav   ElevenLabs аудио (нэг удаа, кэштэй)
Залгах цаг: 09-20 (Улаанбаатар). Утсаа аваагүй/завгүй бол 30 минутын дараа, нийт 3 оролдлого.
"""
import json
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import db
import knowledge_jobs
from audio_files import text_hash
from config import DATA_DIR, TENANTS_DIR
from tenant import Tenant, all_tenants, write_json

TZ = ZoneInfo("Asia/Ulaanbaatar")
HOURS = tuple(int(x) for x in os.getenv("OUTBOUND_HOURS", "9-20").split("-"))
MAX_ATTEMPTS, RETRY_MIN, POLL = 3, 30, float(os.getenv("OUTBOUND_POLL", "15"))
FINAL = {"confirmed", "declined", "unconfirmed", "canceled"}
RETRY = {"no_answer", "busy", "hung_up", "failed"}

DEFAULT_TEMPLATE = ("Сайн байна уу, {name}. Энэ бол {org}. Таны бүртгэл баталгаажлаа. {date} {time} цагт ирээрэй. "
                    "Баталгаажуулах бол нэг, цуцлах бол хоёрыг дарна уу.")
PHRASES = {
    "repeat": "Баталгаажуулах бол нэг, цуцлах бол хоёрыг дарна уу.",
    "confirmed": "Баярлалаа, баталгаажууллаа. Таныг хүлээж байна.",
    "declined": "Ойлголоо, цуцаллаа. Манай ажилтан тантай холбогдоно. Баярлалаа.",
    "no_input": "Хариу ирсэнгүй. Манай ажилтан тантай холбогдоно. Баярлалаа.",
}
MONTHS = ["нэгдүгээр", "хоёрдугаар", "гуравдугаар", "дөрөвдүгээр", "тавдугаар", "зургаадугаар", "долоодугаар",
          "наймдугаар", "есдүгээр", "аравдугаар", "арван нэгдүгээр", "арван хоёрдугаар"]
UNIT_GEN = ["", "нэгний", "хоёрны", "гурвын", "дөрвөний", "тавны", "зургааны", "долооны", "наймны", "есний"]
TENS = {1: ("арван", "аравны"), 2: ("хорин", "хорины"), 3: ("гучин", "гучны")}

_lock = threading.Lock()          # нэг удаад нэг дуудлага (gateway 1 суваг)
data_lock = threading.RLock()     # reminders.json уншиж-бичих (вэб ба залгагч зэрэг)
_wake = threading.Event()


def date_words(d: datetime) -> str:
    """2026-10-15 -> "аравдугаар сарын арван тавны" (утсаар уншихад)."""
    tens, unit = divmod(d.day, 10)
    day = UNIT_GEN[unit] if not tens else (TENS[tens][1] if not unit else f"{TENS[tens][0]} {UNIT_GEN[unit]}")
    return f"{MONTHS[d.month - 1]} сарын {day}"


def parse_local(value: str) -> datetime:
    """"2026-10-15T10:00" (Улаанбаатарын цаг) -> datetime."""
    return datetime.strptime(value[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=TZ)


def settings(t: Tenant) -> dict:
    import notify
    return notify.load_settings(t)


def template(t: Tenant) -> str:
    return settings(t).get("reminder_template") or DEFAULT_TEMPLATE


def render(t: Tenant, lead: dict, appointment: str, tpl: str | None = None) -> str:
    when = parse_local(appointment)
    text = (tpl or template(t)).format(name=(lead.get("name") or "").strip(), org=t.config().get("name", t.slug),
                                       date=date_words(when), time=when.strftime("%H:%M"))
    return re.sub(r",\s*\.", ".", re.sub(r"\s+", " ", text)).strip()     # нэргүй бол "Сайн байна уу, ." -> "."


def path(t: Tenant) -> str:
    return t.path("data", "reminders.json")


def load(t: Tenant) -> dict:
    try:
        with open(path(t), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    data.setdefault("items", {})
    return data


def save(t: Tenant, data: dict):
    write_json(path(t), data)


def lead_of(t: Tenant, lead_id: int) -> dict | None:
    with db.connect(t.db_path) as con:
        row = con.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    return dict(row) if row else None


def number_of(lead: dict) -> str | None:
    """Баталгаажсан дугаар, эс бөгөөс Caller ID (8+ цифр)."""
    for value in (lead.get("phone"), lead.get("caller")):
        digits = re.sub(r"[^\d+]", "", value or "")
        if len(digits.lstrip("+")) >= 8:
            return digits
    return None


# ---------------- аудио (ElevenLabs, нэг удаа) ----------------

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reminder_audio.py")


def audio_dir(t: Tenant) -> str:
    import eleven
    return t.path("data", "reminder_audio", eleven.engine(t)["voice"] or "default")


def _synth_sim(t: Tenant, todo: list[dict], out_dir: str):
    """SIM-TRUNK-ийн ElevenTTS-ээр (тоо, цаг үгээр; байгууллагын хоолой)."""
    source = knowledge_jobs.sim_root()
    python = os.path.join(source, ".venv", "bin", "python")
    root = knowledge_jobs.runtime_root()
    env = {**os.environ, "DATA_DIR": DATA_DIR, "TENANT": t.slug, "HF_HUB_OFFLINE": "1"}
    r = subprocess.run([python, "-W", "ignore", knowledge_jobs.RUNNER, root, TENANTS_DIR, SCRIPT], cwd=root, env=env,
                       input=json.dumps({"items": todo, "out": out_dir}, ensure_ascii=False),
                       capture_output=True, text=True, timeout=300)
    errors = [ln[6:] for ln in r.stdout.splitlines() if ln.startswith("error ")]
    if r.returncode or errors:
        raise RuntimeError(errors[0] if errors else (r.stdout + r.stderr).strip()[-300:])


synth = _synth_sim          # тест солино


def clips(t: Tenant, message: str) -> dict:
    """message + тогтмол хэллэгүүдийн аудио (байхгүйг нь л үүсгэнэ) -> {нэр: (wav, sr)}."""
    import soundfile as sf
    texts = {"message": message, **PHRASES}
    out = audio_dir(t)
    todo = [{"hash": text_hash(x), "text": x} for x in texts.values()
            if not os.path.exists(os.path.join(out, f"{text_hash(x)}.wav"))]
    if todo:
        os.makedirs(out, exist_ok=True)
        synth(t, todo, out)
    return {k: sf.read(os.path.join(out, f"{text_hash(x)}.wav"), dtype="float32") for k, x in texts.items()}


def new_chars(t: Tenant, message: str) -> int:
    """Энэ сануулгад ElevenLabs-аар шинээр үүсэх тэмдэгт (токен)."""
    out = audio_dir(t)
    return sum(len(x) for x in [message, *PHRASES.values()] if not os.path.exists(os.path.join(out, f"{text_hash(x)}.wav")))


# ---------------- дуудлага ----------------

def call(t: Tenant, lead_id: int) -> str:
    """Нэг сануулгын дуудлага (blocking). Үр дүнг reminders.json-д, Telegram руу."""
    from outbound import dialer, session
    from outbound.sip import SipError
    with data_lock:
        data = load(t)
        item = data["items"].get(str(lead_id))
        lead = lead_of(t, lead_id)
        if not item or not lead or item.get("status") != "scheduled":
            return "skipped"
        item.update(status="calling", attempts=item.get("attempts", 0) + 1, last_call=time.time())
        save(t, data)
    outcome, pressed, detail = "failed", [], ""
    try:
        number = number_of(lead)
        if not number:
            raise SipError("failed", "утасны дугаар алга")
        # Утасны AI цагийг сольсон бол текст хоосон -> загвараар дахин бичнэ
        audio = clips(t, item.get("text") or render(t, lead, item["appointment"]))
        io = dialer.dial(number)
        try:
            outcome, pressed = session.run(io, audio)
        finally:
            io.hangup()
    except SipError as exc:
        outcome, detail = exc.outcome, str(exc)
    except Exception as exc:                       # ElevenLabs, аудио төхөөрөмж ...
        outcome, detail = "failed", str(exc)[:200]
    with data_lock:
        data = load(t)
        item = data["items"].get(str(lead_id))
        if not item:                               # дуудлагын үеэр цуцалсан
            return outcome
        item.setdefault("history", []).append({"ts": int(time.time()), "outcome": outcome, "pressed": pressed,
                                               "detail": detail})
        if outcome in RETRY and item["attempts"] < MAX_ATTEMPTS:
            item.update(status="scheduled", call_at=time.time() + RETRY_MIN * 60, last_outcome=outcome)
        else:
            item.update(status=outcome if outcome in FINAL or outcome == "failed" else "no_answer", last_outcome=outcome)
        save(t, data)
    if outcome == "confirmed":
        with db.connect(t.db_path) as con:
            con.execute("UPDATE leads SET status='contacted' WHERE id=? AND status='new'", (lead_id,))
    _notify(t, lead, item, outcome)
    return outcome


TEXT = {"confirmed": "✅ баталгаажууллаа", "declined": "❌ цуцаллаа", "unconfirmed": "📞 сонссон ч хариу өгсөнгүй",
        "no_answer": "📵 утсаа аваагүй", "busy": "📵 завгүй", "hung_up": "📵 тасалсан", "failed": "⚠️ залгаж чадсангүй"}


def _notify(t: Tenant, lead: dict, item: dict, outcome: str):
    import notify
    when = parse_local(item["appointment"]).strftime("%m/%d %H:%M")
    retry = " (дахин залгана)" if item["status"] == "scheduled" else ""
    try:
        notify.send(t, f"{t.config().get('name', t.slug)}: {lead.get('name') or lead.get('phone') or 'Бүртгэл'} — "
                       f"{when} уулзалт {TEXT.get(outcome, outcome)}{retry}")
    except Exception as exc:
        print(f"  [мэдэгдэл] {exc}")


def in_hours(now: datetime | None = None) -> bool:
    now = now or datetime.now(TZ)
    return HOURS[0] <= now.hour < HOURS[1]


def run_due(now: float | None = None, check_ready: bool = True) -> list[tuple[str, int, str]]:
    """Хугацаа нь болсон сануулгуудыг нэг нэгээр залгана (scheduler, тест)."""
    from outbound import dialer
    now = now or time.time()
    due = [(t, int(k)) for t in all_tenants() for k, v in load(t)["items"].items()
           if v.get("status") == "scheduled" and v.get("call_at", 0) <= now]
    if not due or not in_hours(datetime.fromtimestamp(now, TZ)) or (check_ready and not dialer.ready()[0]):
        return []
    done = []
    with _lock:
        for t, lead_id in due:
            done.append((t.slug, lead_id, call(t, lead_id)))
    return done


def _loop():
    while True:
        _wake.wait(POLL)
        _wake.clear()
        try:
            run_due()
        except Exception as exc:
            print(f"  [сануулга] {exc}")


def wake():
    _wake.set()


if os.getenv("OUTBOUND_SCHEDULER", "1") == "1":
    threading.Thread(target=_loop, daemon=True).start()
