"""
Өөрийн хоолойгоор бичих (вэб -> Хоолой). Өгүүлбэр бүрийг хүн өөрөө бичиж эсвэл аудио файлаар оруулна.

  POST   /api/voice/{hash}         file=<WAV>  -> бичлэг хадгална
  DELETE /api/voice/{hash}                     -> бичлэгийг устгана (TTS руу буцна)
  GET    /api/voice/{hash}/audio               -> одоо тоглогдох аудио: бичлэг байвал түүнийг, үгүй бол TTS

Бичлэг: tenants/<slug>/recordings/<hash>.wav — SIM-TRUNK-ийн recordings.py-тай ижил нэр, тул "Бэлдэх" үед
тэр өгүүлбэрт TTS хийхгүй, бичлэгийг ашиглана. Hash = sha1(текст)[:12] — текст өөрчлөгдвөл дахин бичнэ.
Хөтөч дуу бичих, файл хөрвүүлэх, чимээгүй тайрах, түвшин тэнцүүлэхийг хийгээд 24kHz mono 16-bit WAV илгээнэ.
"""
import io
import os
import re
import wave

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

import knowledge_jobs
from config import DATA_DIR
from deps import current_tenant
from routes.status import load_json
from routes.voice import voice_items
from tenant import Tenant

router = APIRouter(prefix="/api/voice", tags=["voice"])
SAMPLE_RATE = 24000                    # SIM-TRUNK TTS / record.py-тай ижил
MIN_SEC, MAX_SEC = 0.3, 60
MAX_BYTES = 5 * 1024 * 1024


def recording_path(t: Tenant, h: str) -> str:
    return t.path("recordings", f"{h}.wav")


def find_item(t: Tenant, h: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{12}", h):
        raise HTTPException(400, "Буруу hash")
    item = next((x for x in voice_items(t) if x["hash"] == h), None)
    if not item:
        raise HTTPException(404, "Өгүүлбэр олдсонгүй (текст өөрчлөгдсөн байж магадгүй)")
    return item


def check_wav(data: bytes) -> float:
    """24kHz mono 16-bit PCM WAV эсэх, урт. Буруу бол 400."""
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Файл хэт том (5MB хүртэл)")
    try:
        with wave.open(io.BytesIO(data)) as w:
            channels, width, rate, frames = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    except (wave.Error, EOFError):
        raise HTTPException(400, "WAV файл биш") from None
    if (channels, width, rate) != (1, 2, SAMPLE_RATE):
        raise HTTPException(400, f"{SAMPLE_RATE // 1000}kHz mono 16-bit WAV байх ёстой")
    seconds = frames / rate
    if not MIN_SEC <= seconds <= MAX_SEC:
        raise HTTPException(400, f"Бичлэг {MIN_SEC}-{MAX_SEC} секунд байх ёстой")
    return seconds


@router.post("/{h}")
async def save_recording(h: str, file: UploadFile = File(...), t: Tenant = Depends(current_tenant)):
    find_item(t, h)
    data = await file.read(MAX_BYTES + 1)
    seconds = check_wav(data)
    path = recording_path(t, h)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "wb") as f:
        f.write(data)
    os.replace(path + ".tmp", path)
    return {"ok": True, "seconds": round(seconds, 1)}


@router.delete("/{h}")
def delete_recording(h: str, t: Tenant = Depends(current_tenant)):
    find_item(t, h)
    path = recording_path(t, h)
    if not os.path.exists(path):
        raise HTTPException(404, "Бичлэг олдсонгүй")
    os.remove(path)
    return {"ok": True}


def built_audio(t: Tenant) -> dict[str, str]:
    """hash -> бэлдсэн (TTS) аудио: faq_audio/faq_index.json, knowledge_index/facts.json"""
    import hashlib
    faq = load_json(t.path("faq_audio", "faq_index.json"))
    clips = [faq.get("greeting")] + list(faq.get("fillers", []))
    clips += [{"text": x.get("answer", ""), "audio": x.get("audio")} for x in faq.get("faq", [])]
    clips += load_json(t.path("knowledge_index", "facts.json")).get("facts", [])
    return {hashlib.sha1(c["text"].encode()).hexdigest()[:12]: c["audio"]
            for c in clips if isinstance(c, dict) and c.get("text") and c.get("audio")}


@router.get("/{h}/audio")
def play(h: str, t: Tenant = Depends(current_tenant)):
    find_item(t, h)
    path = recording_path(t, h)
    if not os.path.exists(path):
        path = built_audio(t).get(h, "")
    # Манай өгөгдөл эсвэл SIM-TRUNK-ийн нийтлэг TTS кэш доторх файл л
    roots = [os.path.realpath(DATA_DIR), os.path.realpath(knowledge_jobs.tts_cache())]
    real = os.path.realpath(path) if path else ""
    if not path or not os.path.isfile(path) or not any(real.startswith(r + os.sep) for r in roots):
        raise HTTPException(404, "Аудио алга (бичээгүй, бэлдээгүй)")
    return FileResponse(path, media_type="audio/wav", headers={"Cache-Control": "no-store"})
