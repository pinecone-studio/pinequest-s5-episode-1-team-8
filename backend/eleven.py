"""
ElevenLabs: залгагчид тоглогдох аудиог зөвхөн БЭЛДЭХЭД үүсгэнэ (дуудлагын үед бэлэн аудио тоглогдоно).
Oron TTS ашиглахгүй. Байгууллага хоолой сонгоогүй бол Уянга (монгол, халх аялга).

Түлхүүр: DATA_DIR/elevenlabs_key (600, git-д орохгүй; бодит горимд SIM-TRUNK/data/). SIM-TRUNK-ийн бэлдэх скриптүүд
(.sim-runtime/data -> DATA_DIR) яг энэ файлыг уншина.
Жишээ аудио: tenants/<slug>/data/eleven_samples/<tag>/<hash>.wav — "Аудио бэлдэх" эндээс шууд хуулна,
ElevenLabs-ийг дахин дуудахгүй (SIM-TRUNK stream_voice.eleven_sample_path).
"""
import json
import os
import re
import subprocess
import threading

import httpx

import knowledge_jobs
from config import DATA_DIR, LIVE, SIM_TRUNK_DIR, TENANTS_DIR
from tenant import Tenant

# бэлдэх скриптүүдийн уншдаг газар: .sim-runtime/data -> DATA_DIR, бодит горимд SIM-TRUNK/data
KEY_FILE = os.path.join(SIM_TRUNK_DIR, "data", "elevenlabs_key") if LIVE else os.path.join(DATA_DIR, "elevenlabs_key")
URL = "https://api.elevenlabs.io/v1"
MODEL = "eleven_v4"                      # монгол хэл дэмждэг (v3, multilingual v2 дэмждэггүй)
DEFAULT_VOICE = os.getenv("ELEVEN_VOICE", "2cecqSnkajrth9sJSoEH")   # Уянга (ElevenLabs-ийн нийтийн сан)
DEFAULT_NAME = "Уянга"
VOICE_ID = re.compile(r"[A-Za-z0-9]{10,40}")
SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eleven_samples.py")
SAMPLES = 8

_voices: dict[str, dict] = {}            # хоолойн жагсаалтын кэш (түлхүүр солигдвол цэвэрлэнэ)
JOB = {"running": False, "done": 0, "total": 0, "chars": 0, "error": None}


def key() -> str | None:
    try:
        with open(KEY_FILE, encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return os.getenv("ELEVENLABS_API_KEY")


def save_key(value: str):
    """Түлхүүрийг ElevenLabs-аар шалгаад хадгална. Буруу бол ValueError (монгол мессеж)."""
    value = value.strip()
    if not value.startswith("sk_"):
        raise ValueError('Түлхүүр "sk_"-ээр эхэлдэг. Жагсаалтад харагдах нь түлхүүрийн ID — '
                         "түлхүүр зөвхөн үүсгэх (эсвэл Rotate) үед нэг удаа харагдана.")
    if not re.fullmatch(r"sk_[A-Za-z0-9_\-]{20,200}", value):
        raise ValueError("Түлхүүрийн хэлбэр буруу")
    r = httpx.get(f"{URL}/voices", headers={"xi-api-key": value}, timeout=30)
    if r.status_code != 200:
        raise ValueError(f"ElevenLabs түлхүүрийг хүлээж авсангүй ({r.status_code}). Voices (Read) эрх хэрэгтэй.")
    os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)
    fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(value)
    _voices.clear()


def engine(t: Tenant) -> dict:
    """Байгууллагын ElevenLabs тохиргоо (SIM-TRUNK stream_voice.tts_engine, Oron-гүй)."""
    cfg = t.config()
    voice = cfg.get("eleven_voice") or (DEFAULT_VOICE if key() else None)
    # SIM-TRUNK: "Uyanga - Kind Khalkha Friend" -> "Uyanga" (хоолойн сангийн тайлбаргүй)
    name = (cfg.get("eleven_voice_name") or "").split(" - ")[0] or (DEFAULT_NAME if voice == DEFAULT_VOICE else None)
    speed = min(max(float(cfg.get("eleven_speed", 1.0)), 0.7), 1.2)
    return {"voice": voice, "name": name, "model": cfg.get("eleven_model", MODEL), "speed": speed}


def samples_dir(t: Tenant, voice: str) -> str:
    eng = engine(t)
    return t.path("data", "eleven_samples", f"eleven-{voice}-{eng['model']}-s{round(eng['speed'] * 100)}")


def voices() -> list[dict]:
    """Монгол хүний хоолой (нийтийн сан) эхэнд, дараа нь дансны хоолойнууд. RuntimeError: API алдаа."""
    if not _voices:
        headers = {"xi-api-key": key() or ""}
        try:
            # Нийтийн сангийн хоолойг API-аар ашиглахад төлбөртэй багц хэрэгтэй
            r = httpx.get(f"{URL}/shared-voices", params={"language": "mn", "page_size": 30}, headers=headers, timeout=30)
            if r.status_code == 200:
                for v in r.json().get("voices", []):
                    _voices[v["voice_id"]] = {"id": v["voice_id"], "name": v.get("name", ""), "library": True,
                                              "info": " · ".join(x for x in ("монгол", v.get("gender"), "сангийн хоолой") if x)}
            r = httpx.get(f"{URL}/voices", headers=headers, timeout=30)
            r.raise_for_status()
        except httpx.HTTPError as exc:
            _voices.clear()
            raise RuntimeError(f"Хоолойн жагсаалт авч чадсангүй: {exc}") from exc
        for v in r.json().get("voices", []):
            if v["voice_id"] not in _voices:       # дансанд нэмсэн сангийн хоолой -> "монгол" тэмдэглэгээ хэвээр
                labels = v.get("labels") or {}
                _voices[v["voice_id"]] = {"id": v["voice_id"], "name": v.get("name", ""), "library": False,
                                          "info": " · ".join(x for x in (labels.get("gender"), labels.get("accent"),
                                                                         labels.get("age")) if x)}
    return list(_voices.values())


def voice_name(voice: str) -> str:
    if voice == DEFAULT_VOICE:
        return DEFAULT_NAME
    if voice not in _voices and key():
        try:
            voices()
        except RuntimeError:
            pass
    return _voices.get(voice, {}).get("name", "").split(" - ")[0] or "ElevenLabs"


def sample_items(items: list[dict]) -> list[dict]:
    """Хоолойг харьцуулах төлөөлөх өгүүлбэрүүд: мэндчилгээ, тодруулах, FAQ (тоотой), бүртгэлийн асуулт,
    англи үгтэй, тоотой мэдээлэл."""
    items = [i for i in items if not i["recorded"]]
    latin = lambda i: len(re.findall(r"[A-Za-z]{2,}", i["text"]))           # noqa: E731
    number = lambda i: bool(re.search(r"\d|хувь|төгрөг|мянга", i["text"]))    # noqa: E731
    kind = lambda *names: [i for i in items if i["kind"] in names]          # noqa: E731
    facts = kind("Мэдээлэл")
    groups = [kind("Мэндчилгээ")[:1], kind("тодруулах")[:1],
              sorted(kind("FAQ"), key=lambda i: (not number(i), -len(i["text"])))[:2],
              sorted([i for i in kind("бүртгэл") if i["text"].endswith("?")], key=lambda i: -len(i["text"]))[:1],
              sorted(facts, key=latin, reverse=True)[:1], [i for i in facts if number(i) and not latin(i)][:1]]
    picked = []
    for group in groups:
        for i in group:
            if i["hash"] not in {p["hash"] for p in picked}:
                picked.append(i)
    return picked[:SAMPLES]


def _run(t: Tenant, voice: str, todo: list[dict]):
    """SIM-TRUNK-ийн орчинд eleven_samples.py: бэлдэлттэй яг адил (тоог үгээр, дуудлагын толь, дууны түвшин)."""
    source = knowledge_jobs.sim_root()
    python = os.path.join(source, ".venv", "bin", "python")
    try:
        if not os.path.isfile(python):
            raise RuntimeError(f"SIM-TRUNK Python орчин олдсонгүй: {python}")
        root = knowledge_jobs.runtime_root()
        env = {**os.environ, "DATA_DIR": DATA_DIR, "TENANT": t.slug, "HF_HUB_OFFLINE": "1", "PYTHONUNBUFFERED": "1"}
        proc = subprocess.Popen([python, "-W", "ignore", knowledge_jobs.RUNNER, root, TENANTS_DIR, SCRIPT],
                                cwd=root, env=env, text=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        proc.stdin.write(json.dumps({"voice": voice, "items": todo}, ensure_ascii=False))
        proc.stdin.close()
        chars = {i["hash"]: len(i["text"]) for i in todo}
        last = ""
        for line in proc.stdout:
            kind, _, rest = line.strip().partition(" ")
            if kind == "ok":
                JOB["done"] += 1
                JOB["chars"] += chars.get(rest, 0)
            elif kind == "error":
                JOB["error"] = rest
            elif line.strip():
                last = line.strip()
        if proc.wait() and not JOB["error"]:
            JOB["error"] = last[:300] or f"алдаа (код {proc.returncode})"
    except Exception as exc:
        JOB["error"] = str(exc)[:300]
    finally:
        if JOB["error"] and "paid_plan_required" in JOB["error"]:
            JOB["error"] = ("Монгол (сангийн) хоолойг API-аар ашиглахад ElevenLabs-ийн төлбөртэй багц (Starter) хэрэгтэй. "
                            "Үнэгүй багцад зөвхөн анхдагч хоолойнууд.")
        JOB["running"] = False


def generate(t: Tenant, voice: str, todo: list[dict]) -> dict:
    """Үүсгээгүй өгүүлбэрүүдийг цаана нь үүсгэнэ (бүгд ~80 x 3с = 4 мин; вэб хүсэлтийн хугацаанд багтахгүй)."""
    JOB.update(running=bool(todo), done=0, total=len(todo), chars=0, error=None)
    if todo:
        threading.Thread(target=_run, args=(t, voice, todo), daemon=True).start()
    return JOB
