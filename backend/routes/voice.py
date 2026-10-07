"""
Хоолой: залгагчид тоглогдох бүх өгүүлбэр, чанарын шалгалт, дуудлагын толь, өөрийн бичлэг.
TTS нь ElevenLabs (анхдагч Уянга; хоолой сонгох -> routes/eleven.py). Oron TTS ашиглахгүй.

  GET  /api/voice                       -> өгүүлбэрүүд (бичлэгтэй эсэх, шалгалт, тоглогдсон тоо), хоолой, толь
  PUT  /api/voice/settings              -> дуудлагын толь ("CV" -> "си ви")
  POST /api/voice/regenerate/{hash}     -> нэг өгүүлбэрийг ElevenLabs-аар өөр хувилбараар
  POST /api/voice/rebuild               -> хоолой, толь, бичлэгийн дагуу аудиог шинэчлэх (сургалтгүй)
  GET  /api/voice/export                -> одоо тоглогдох бүх аудио + manifest -> ZIP
"""
import csv
import io
import json
import os
import re
import sqlite3
import tempfile
import time
import zipfile

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

import eleven
import knowledge_jobs
from audio_files import phone_quality, recording_for, recording_path, save_recording, text_hash
from deps import current_tenant
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


def load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError):
        return default


def all_texts(t: Tenant) -> list[tuple[str, str]]:
    """Залгагчид тоглогдох бүх өгүүлбэр (SIM-TRUNK scripts/record.py · all_texts).
    Хэллэгүүдийг (хүлээлгэх, алдаа, бүртгэл, цифр) "Аудио бэлдэх"-ийн бичсэн faq_index.json-оос авна —
    SIM-TRUNK байгууллагын нэр, утсыг оруулж бэлддэг тул яг тоглогдох бичвэр. Бэлдээгүй бол доорх загвар."""
    src = load_faq(t)
    built = load_json(os.path.join(t.faq_index_dir, "faq_index.json"), {})
    one = lambda key: (built.get(key) or {}).get("text")                                    # noqa: E731
    many = lambda key: [c.get("text", "") for c in (built.get(key) or [])]                   # noqa: E731
    system_keys = {"алдаа": "error", "дахин асуух": "repeat", "тодруулах": "clarify"}
    rows: list[tuple[str, str]] = []
    greeting = src.get("greeting") or one("greeting")
    if greeting:
        rows.append(("Мэндчилгээ", greeting))
    rows += [("Хүлээлгэх", text) for text in (src.get("fillers") or many("fillers"))]
    rows += [("hold", text) for text in (many("holds") or HOLDS)]
    rows += [(kind, one(system_keys[kind]) or text) for kind, text in SYSTEM.items()]
    rows += [("bridge", row.get("bridge", "")) for row in src.get("topics", {}).values()]
    rows += [("бүртгэл", text) for text in ([c.get("text", "") for c in (built.get("lead") or {}).values()] or LEAD)]
    rows += [("цифр", text) for text in (many("digits") or DIGITS)]
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


def seed_key(item_hash: str) -> str:
    """SIM-TRUNK stream_voice.clip_seed: ElevenLabs-ийн "дахин үүсгэх" seed "eleven:<hash>" түлхүүртэй."""
    return f"eleven:{item_hash}"


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
                       "seed": seeds.get(seed_key(key), 0),
                       "plays": sum(count for spoken, count in said.items() if text in spoken and word.search(spoken))})
    return result


@router.get("")
def get_voice(t: Tenant = Depends(current_tenant)):
    cfg = t.config()
    qa = load_json(os.path.join(t.kb_index_dir, "audio_qa.json"), {})
    eng = eleven.engine(t)
    return {"items": voice_items(t), "qa_at": qa.get("checked_at"),
            "voice": {"name": eng["name"], "id": eng["voice"], "model": eng["model"], "has_key": bool(eleven.key())},
            "settings": {"lexicon": cfg.get("lexicon", []), "speed": cfg.get("tts_speed", 0.85),
                         "pause_ms": cfg.get("pause_ms", 300)}}


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
    seeds[seed_key(item_hash)] = seeds.get(seed_key(item_hash), 0) + 1
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


@router.post("/rebuild")
def rebuild(t: Tenant = Depends(current_tenant)):
    """Хоолойн сонголт, толь, бичлэг, seed-ийн дагуу аудиог шинэчилнэ (кэштэйг алгасна, сургалтгүй)."""
    try:
        return knowledge_jobs.enqueue(t, "regen")
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/export")
def export(t: Tenant = Depends(current_tenant)):
    """Одоо тоглогдох бүх аудио + бичвэр (manifest.json, manifest.csv) -> ZIP. Өөр сервер, gateway руу зөөхөд."""
    index, rows = audio_index(t), []
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for item in voice_items(t):
            recorded = recording_for(t.recordings_dir, item["text"])
            path = recorded or index.get(item["hash"])
            if not path or not os.path.isfile(path):
                continue
            name = f"audio/{item['hash']}.wav"
            z.write(path, name)
            rows.append({"file": name, "hash": item["hash"], "kind": item["kind"], "text": item["text"],
                         "source": "бичлэг" if recorded else "ElevenLabs"})
        z.writestr("manifest.json", json.dumps({"tenant": t.slug, "exported_at": time.time(), "clips": rows},
                                               ensure_ascii=False, indent=1))
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["file", "hash", "kind", "text", "source"])
        writer.writeheader()
        writer.writerows(rows)
        z.writestr("manifest.csv", "\ufeff" + buf.getvalue())     # Excel-д кирилл зөв харагдана
    tmp.close()
    return FileResponse(tmp.name, media_type="application/zip", filename=f"{t.slug}-audio-{time.strftime('%Y%m%d')}.zip",
                        background=BackgroundTask(os.remove, tmp.name))
