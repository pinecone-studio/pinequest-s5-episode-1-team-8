"""
ElevenLabs хоолой сонгох (вэб -> Хоолой -> Хоолой сонгох). Зөвхөн платформын admin: түлхүүр бүх байгууллагад нийтлэг.

  GET  /api/admin/eleven                     -> түлхүүртэй эсэх, хоолойнууд, өгүүлбэр бүрт аль хоолойгоор жишээ үүссэн
  POST /api/admin/eleven/key {"key"}         -> шалгаад хадгална (буцааж харуулахгүй)
  POST /api/admin/eleven/generate {"voice", "scope": "sample"|"all"} -> үүсгээгүйг цаана нь үүсгэнэ
  PUT  /api/admin/eleven/choice {"voice"}    -> энэ байгууллагын хоолой ("Аудиог шинэчлэх"-ээр хэрэгжинэ)
  GET  /api/admin/eleven/audio/{voice}/{h}   -> жишээ аудио (?phone=1 утасны чанар)
"""
import os
import re

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

import eleven
from audio_files import phone_quality
from deps import current_tenant
from routes.admin import require_admin
from routes.voice import voice_items
from tenant import Tenant

router = APIRouter(prefix="/api/admin/eleven", tags=["eleven"], dependencies=[Depends(require_admin)])


def check_voice(voice: str):
    if not eleven.VOICE_ID.fullmatch(voice):
        raise HTTPException(400, "Буруу хоолой")


@router.get("")
def status(t: Tenant = Depends(current_tenant)):
    eng = eleven.engine(t)
    base = {"has_key": bool(eleven.key()), "model": eng["model"], "voice": eng["voice"], "job": eleven.JOB,
            "voices": [], "items": [], "error": None}
    if not base["has_key"]:
        return base
    try:
        voices = eleven.voices()
    except RuntimeError as exc:
        return {**base, "error": str(exc)}
    items = voice_items(t)
    sample = {i["hash"] for i in eleven.sample_items(items)}
    made = {}
    for v in voices:
        d = eleven.samples_dir(t, v["id"])
        if os.path.isdir(d):
            made[v["id"]] = {name[:-4] for name in os.listdir(d) if name.endswith(".wav")}
    rows = [{"kind": i["kind"], "text": i["text"], "hash": i["hash"], "recorded": i["recorded"],
             "sample": i["hash"] in sample, "eleven": [vid for vid, hashes in made.items() if i["hash"] in hashes]}
            for i in items]
    return {**base, "voices": voices, "items": rows}


class KeyBody(BaseModel):
    key: str


@router.post("/key")
def save_key(body: KeyBody):
    try:
        eleven.save_key(body.key)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True}


class GenerateBody(BaseModel):
    voice: str
    scope: str = "sample"            # sample (8 төлөөлөх) | all (бичлэггүй бүх өгүүлбэр)


@router.post("/generate")
def generate(body: GenerateBody, t: Tenant = Depends(current_tenant)):
    check_voice(body.voice)
    if eleven.JOB["running"]:
        raise HTTPException(409, "Үүсгэж байна, түр хүлээнэ үү")
    if not eleven.key():
        raise HTTPException(400, "ElevenLabs түлхүүр оруулаагүй")
    items = voice_items(t)
    items = eleven.sample_items(items) if body.scope == "sample" else [i for i in items if not i["recorded"]]
    out = eleven.samples_dir(t, body.voice)
    todo = [{"hash": i["hash"], "text": i["text"]} for i in items
            if not os.path.isfile(os.path.join(out, f"{i['hash']}.wav"))]
    return eleven.generate(t, body.voice, todo)


class ChoiceBody(BaseModel):
    voice: str


@router.put("/choice")
def choice(body: ChoiceBody, t: Tenant = Depends(current_tenant)):
    """Бүх өгүүлбэр (өөрийн бичлэгээс бусад) энэ хоолойгоор. Үүсгэсэн жишээг бэлдэх үед шууд ашиглана."""
    check_voice(body.voice)
    cfg = t.config()
    cfg.update(tts_engine="eleven", eleven_voice=body.voice, eleven_voice_name=eleven.voice_name(body.voice))
    cfg.pop("clip_engine", None)              # Oron-той өгүүлбэр бүрийн сонголт хэрэггүй
    t.save_config(cfg)
    return {"ok": True, "name": cfg["eleven_voice_name"]}


@router.get("/audio/{voice}/{h}")
def audio(voice: str, h: str, phone: int = 0, t: Tenant = Depends(current_tenant)):
    check_voice(voice)
    if not re.fullmatch(r"[0-9a-f]{12}", h):
        raise HTTPException(400, "Буруу hash")
    path = os.path.join(eleven.samples_dir(t, voice), f"{h}.wav")
    if not os.path.isfile(path):
        raise HTTPException(404, "Жишээ үүсгээгүй")
    if phone:
        return Response(phone_quality(path), media_type="audio/wav")
    return FileResponse(path, media_type="audio/wav")
