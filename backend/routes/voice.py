"""Хоолойн чанарын шалгалт, TTS тохиргоо, хүний бичлэг болон лавлах хоолой."""
import json
import os
import re
import sqlite3
import subprocess
import threading
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from audio_files import duration, phone_quality, recording_for, recording_path, save_recording, text_hash
from config import DATA_DIR
from deps import current_tenant, current_user
import knowledge_jobs
from tenant import Tenant, load_faq

router = APIRouter(prefix="/api/voice", tags=["voice"])

HOLDS = ["Түр хүлээгээрэй.", "Одоохон хэлье.", "Мэдээллийг нь шалгаж байна.",
         "Бага зэрэг хүлээгээрэй.", "Одоохон олчихлоо.", "Түр хором хүлээгээрэй."]
SYSTEM = {"алдаа": "Энэ мэдээллийг баталгаатай олж чадсангүй. Манай ажилтан тан руу эргэж холбогдох уу?",
          "дахин асуух": "Уучлаарай, сайн ойлгосонгүй. Та дахин хэлж өгнө үү?",
          "тодруулах": "Та юуны талаар мэдэхийг хүсэж байна вэ? Асуултаа арай тодорхой хэлж өгнө үү?"}
LEAD = ["Таны нэрийг хэлж өгнө үү?", "Тантай холбогдох утасны дугаараа хэлж өгнө үү.",
        "Таны дугаар", "Зөв үү?", "Таны мэдээллийг амжилттай бүртгэлээ."]
DIGITS = ["тэг", "нэг", "хоёр", "гурав", "дөрөв", "тав", "зургаа", "долоо", "найм", "ес"]
QUESTION_SCRIPT = "Та манай хөтөлбөрийн талаар өөр асуух зүйл байна уу?"


def load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError):
        return default


def all_texts(t: Tenant) -> list[tuple[str, str]]:
    src = load_faq(t)
    rows: list[tuple[str, str]] = []
    if src.get("greeting"):
        rows.append(("Мэндчилгээ", src["greeting"]))
    rows += [("Хүлээлгэх", text) for text in src.get("fillers", [])]
    rows += [("hold", text) for text in HOLDS]
    rows += list(SYSTEM.items())
    rows += [("bridge", row.get("bridge", "")) for row in src.get("topics", {}).values()]
    rows += [("бүртгэл", text) for text in LEAD]
    rows += [("цифр", text) for text in DIGITS]
    rows += [("FAQ", row.get("answer", "")) for row in src.get("faq", [])
             if row.get("answer") and "TODO" not in row.get("answer", "")]
    facts = load_json(os.path.join(t.kb_index_dir, "facts.json"), {}).get("facts", [])
    rows += [("Мэдээлэл", row.get("text", "")) for row in facts]
    seen, result = set(), []
    for kind, text in rows:
        text = " ".join(text.split())
        if text and text not in seen:
            seen.add(text)
            result.append((kind, text))
    return result


def play_counts(t: Tenant, days: int = 90) -> dict[str, int]:
    if not os.path.isfile(t.db_path):
        return {}
    try:
        with sqlite3.connect(t.db_path) as con:
            rows = con.execute("SELECT text, COUNT(*) FROM messages WHERE role='assistant' AND ts>? GROUP BY text",
                               (time.time() - days * 86400,)).fetchall()
        return {text: count for text, count in rows if text}
    except sqlite3.Error:
        return {}


def question_files(t: Tenant) -> tuple[str, str]:
    return t.path("voice", "question.wav"), t.path("voice", "question.txt")


def voice_items(t: Tenant) -> list[dict]:
    qa = load_json(os.path.join(t.kb_index_dir, "audio_qa.json"), {})
    checks = qa.get("clips", {})
    seeds = load_json(t.path("data", "tts_seeds.json"), {})
    said = play_counts(t)
    result = []
    for kind, text in all_texts(t):
        key, check = text_hash(text), checks.get(text_hash(text), {})
        word = re.compile(rf"(?<!\w){re.escape(text)}(?!\w)")
        result.append({"kind": kind, "text": text, "hash": key,
                       "recorded": bool(recording_for(t.recordings_dir, text)),
                       "flags": check.get("flags", []), "cer": check.get("cer"), "hyp": check.get("hyp"),
                       "seed": seeds.get(key, 0),
                       "plays": sum(count for spoken, count in said.items() if text in spoken and word.search(spoken))})
    return result


@router.get("")
def get_voice(t: Tenant = Depends(current_tenant)):
    cfg = t.config()
    qa = load_json(os.path.join(t.kb_index_dir, "audio_qa.json"), {})
    wav, txt = question_files(t)
    question_text = None
    if os.path.isfile(txt):
        with open(txt, encoding="utf-8") as file:
            question_text = file.read().strip()
    return {"items": voice_items(t), "qa_at": qa.get("checked_at"),
            "settings": {"lexicon": cfg.get("lexicon", []), "speed": cfg.get("tts_speed", 0.85),
                         "pause_ms": cfg.get("pause_ms", 300)},
            "question": {"exists": os.path.isfile(wav), "text": question_text, "script": QUESTION_SCRIPT}}


class LexiconItem(BaseModel):
    word: str
    say: str


class VoiceSettings(BaseModel):
    lexicon: list[LexiconItem] = []
    speed: float = 0.85
    pause_ms: int = 300


@router.put("/settings")
def put_settings(body: VoiceSettings, t: Tenant = Depends(current_tenant)):
    if not 0.7 <= body.speed <= 1.15:
        raise HTTPException(400, "Хурд 0.7-1.15 байх ёстой")
    if not 100 <= body.pause_ms <= 1000:
        raise HTTPException(400, "Завсар 100-1000 мс байх ёстой")
    lexicon = []
    for row in body.lexicon[:200]:
        word, say = " ".join(row.word.split())[:40], " ".join(row.say.split())[:80]
        if word and say and word != say:
            lexicon.append({"word": word, "say": say})
    cfg = t.config()
    cfg.update(lexicon=lexicon, tts_speed=round(body.speed, 2), pause_ms=body.pause_ms)
    t.save_config(cfg)
    return {"ok": True, "lexicon": lexicon}


@router.post("/regenerate/{item_hash}")
def regenerate(item_hash: str, t: Tenant = Depends(current_tenant)):
    item = next((row for row in voice_items(t) if row["hash"] == item_hash), None)
    if not item:
        raise HTTPException(404, "Өгүүлбэр олдсонгүй")
    if item["recorded"]:
        raise HTTPException(400, "Энэ өгүүлбэр таны бичлэгээр тоглогддог")
    job = knowledge_jobs.status(t)
    if job["state"] == "running":
        raise HTTPException(409, "Аудио бэлдэж байна. Дууссаны дараа дахин дарна уу")
    path = t.path("data", "tts_seeds.json")
    seeds = load_json(path, {})
    seeds[item_hash] = seeds.get(item_hash, 0) + 1
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as file:
        json.dump(seeds, file, indent=1)
    os.replace(path + ".tmp", path)
    if job["state"] == "queued":
        return knowledge_jobs.status(t)
    try:
        return knowledge_jobs.enqueue(t, "regen")
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/question")
async def save_question(file: UploadFile = File(...), text: str = Form(QUESTION_SCRIPT),
                        t: Tenant = Depends(current_tenant)):
    text = " ".join(text.split())
    if len(text) < 8 or not text.endswith("?"):
        raise HTTPException(400, "Яг уншсан асуултаа бичнэ үү (? тэмдгээр төгсөнө)")
    wav, txt = question_files(t)
    try:
        seconds = save_recording(await file.read(), wav)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not 1.5 <= seconds <= 10:
        os.remove(wav)
        raise HTTPException(400, f"Бичлэг {seconds:.1f}с байна. 2-8 секунд байх ёстой")
    with open(txt, "w", encoding="utf-8") as out:
        out.write(text)
    return {"ok": True, "seconds": round(seconds, 1)}


@router.get("/question/audio")
def question_audio(t: Tenant = Depends(current_tenant)):
    wav, _ = question_files(t)
    if not os.path.isfile(wav):
        raise HTTPException(404, "Асуултын бичлэг алга")
    return FileResponse(wav, media_type="audio/wav")


@router.delete("/question")
def delete_question(t: Tenant = Depends(current_tenant)):
    for path in question_files(t):
        if os.path.isfile(path):
            os.remove(path)
    return {"ok": True}


@router.post("/recording/{item_hash}")
async def save_voice(item_hash: str, file: UploadFile = File(...), t: Tenant = Depends(current_tenant)):
    item = next((row for row in voice_items(t) if row["hash"] == item_hash), None)
    if not item:
        raise HTTPException(404, "Өгүүлбэр олдсонгүй")
    try:
        seconds = save_recording(await file.read(), recording_path(t.recordings_dir, item["text"]))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "seconds": round(seconds, 1)}


@router.delete("/recording/{item_hash}")
def delete_voice(item_hash: str, t: Tenant = Depends(current_tenant)):
    item = next((row for row in voice_items(t) if row["hash"] == item_hash), None)
    path = recording_path(t.recordings_dir, item["text"]) if item else ""
    if not path or not os.path.isfile(path):
        raise HTTPException(404, "Бичлэг олдсонгүй")
    os.remove(path)
    return {"ok": True}


def audio_index(t: Tenant) -> dict[str, str]:
    out: dict[str, str] = {}
    faq = load_json(os.path.join(t.faq_index_dir, "faq_index.json"), {})
    clips = [faq.get(key) for key in ("greeting", "error", "repeat", "clarify")]
    clips += faq.get("fillers", []) + faq.get("holds", []) + faq.get("digits", [])
    clips += list(faq.get("topics", {}).values()) + list(faq.get("lead", {}).values())
    clips += [{"text": row.get("answer"), "audio": row.get("audio")} for row in faq.get("faq", [])]
    facts = load_json(os.path.join(t.kb_index_dir, "facts.json"), {})
    clips += [{"text": row.get("text"), "audio": row.get("audio")} for row in facts.get("facts", [])]
    for clip in clips:
        if clip and clip.get("text") and clip.get("audio"):
            out[text_hash(clip["text"])] = clip["audio"]
    return out


@router.get("/audio/{item_hash}")
def voice_audio(item_hash: str, phone: int = 0, t: Tenant = Depends(current_tenant)):
    if not re.fullmatch(r"[0-9a-f]{12}", item_hash):
        raise HTTPException(400, "Буруу hash")
    item = next((row for row in voice_items(t) if row["hash"] == item_hash), None)
    recorded = recording_path(t.recordings_dir, item["text"]) if item else ""
    path = recorded if recorded and os.path.isfile(recorded) else audio_index(t).get(item_hash)
    if not path or not os.path.isfile(path):
        raise HTTPException(404, "Аудио алга. Аудио бэлдэх дарна уу")
    if phone:
        return Response(phone_quality(path), media_type="audio/wav")
    return FileResponse(path, media_type="audio/wav")


# Лавлах хоолой нь бүх байгууллагад нийтлэг учраас зөвхөн platform admin засна.
REF_DIR = os.path.join(DATA_DIR, "voices")
REF_WAV, REF_TXT = os.path.join(REF_DIR, "custom.wav"), os.path.join(REF_DIR, "custom.txt")
REF_SCRIPT = ("Сайн байна уу. Манай сургалтын талаар асуух зүйл байвал надад хэлээрэй. "
              "Би танд баяртайгаар тусалж, хэрэгтэй мэдээллийг тань өгье.")
PREVIEW_DIR = os.path.join(DATA_DIR, "preview")
PREVIEW = {"running": False, "code": None}


def require_admin(user: dict = Depends(current_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "Зөвхөн платформын admin")
    return user


@router.get("/reference")
def reference_status(_: dict = Depends(require_admin)):
    text = None
    if os.path.isfile(REF_TXT):
        with open(REF_TXT, encoding="utf-8") as file:
            text = file.read().strip()
    files = sorted(name for name in os.listdir(PREVIEW_DIR) if name.endswith(".wav")) if os.path.isdir(PREVIEW_DIR) else []
    return {"exists": os.path.isfile(REF_WAV), "script": REF_SCRIPT, "text": text,
            "seconds": round(duration(REF_WAV), 1) if os.path.isfile(REF_WAV) else None,
            "preview": {**PREVIEW, "files": files}}


@router.post("/reference")
async def save_reference(file: UploadFile = File(...), text: str = Form(REF_SCRIPT),
                         _: dict = Depends(require_admin)):
    text = " ".join(text.split())
    if len(text) < 20:
        raise HTTPException(400, "Бичлэгт яг юу хэлснийг бичнэ үү")
    try:
        seconds = save_recording(await file.read(), REF_WAV)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not 4 <= seconds <= 16:
        os.remove(REF_WAV)
        raise HTTPException(400, f"Бичлэг {seconds:.1f}с байна. 5-15 секунд байх ёстой")
    with open(REF_TXT, "w", encoding="utf-8") as out:
        out.write(text)
    return {"ok": True, "seconds": round(seconds, 1)}


@router.delete("/reference")
def delete_reference(_: dict = Depends(require_admin)):
    for path in (REF_WAV, REF_TXT):
        if os.path.isfile(path):
            os.remove(path)
    return {"ok": True}


@router.get("/reference/audio")
def reference_audio(_: dict = Depends(require_admin)):
    if not os.path.isfile(REF_WAV):
        raise HTTPException(404, "Лавлах хоолой алга")
    return FileResponse(REF_WAV, media_type="audio/wav")


def _run_preview(slug: str):
    source, runtime = knowledge_jobs.sim_root(), knowledge_jobs.runtime_root()
    python = os.path.join(source, ".venv", "bin", "python")
    log_path = os.path.join(DATA_DIR, "preview.log")
    code = -1
    if os.path.isfile(python):
        with open(log_path, "w", encoding="utf-8") as log:
            code = subprocess.call([python, "-W", "ignore", "scripts/voice_preview.py"], cwd=runtime,
                                   env={**os.environ, "TENANT": slug, "HF_HUB_OFFLINE": "1",
                                        "TTS_CANDIDATES": "1"}, stdout=log, stderr=subprocess.STDOUT)
    PREVIEW.update(running=False, code=code)


@router.post("/reference/preview")
def start_preview(t: Tenant = Depends(current_tenant), _: dict = Depends(require_admin)):
    if PREVIEW["running"]:
        raise HTTPException(409, "Жишээ үүсгэж байна")
    PREVIEW.update(running=True, code=None)
    threading.Thread(target=_run_preview, args=(t.slug,), daemon=True).start()
    return PREVIEW


@router.get("/reference/preview/{name}")
def preview_audio(name: str, _: dict = Depends(require_admin)):
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+\.wav", name):
        raise HTTPException(400, "Файлын нэр буруу")
    path = os.path.join(PREVIEW_DIR, name)
    if not os.path.isfile(path):
        raise HTTPException(404, "Жишээ алга")
    return FileResponse(path, media_type="audio/wav")
