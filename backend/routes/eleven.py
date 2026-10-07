"""
ElevenLabs хоолой сонгох (вэб -> Хоолой -> Хоолой сонгох). Зөвхөн платформын admin: түлхүүр бүх байгууллагад нийтлэг.

  GET  /api/admin/eleven                     -> түлхүүртэй эсэх, хоолойнууд, өгүүлбэр бүрт аль хоолойгоор жишээ үүссэн
  POST /api/admin/eleven/key {"key"}         -> шалгаад хадгална (буцааж харуулахгүй)
  POST /api/admin/eleven/generate {"voice", "scope": "sample"|"all"} -> үүсгээгүйг цаана нь үүсгэнэ
  PUT  /api/admin/eleven/choice {"voice", "clips"} -> энэ байгууллагын хоолой ("Аудиог шинэчлэх"-ээр хэрэгжинэ)
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
    """SIM-TRUNK web/app.py · eleven_status-тэй ижил."""
    eng = eleven.engine(t)
    voices = []
    if eleven.key():
        try:
            voices = eleven.voices()
        except RuntimeError as exc:
            return {"has_key": True, "error": str(exc), "voices": [], "items": [], "model": eleven.MODEL, "job": eleven.JOB}
    items = [{k: i[k] for k in ("kind", "text", "hash", "recorded")} for i in voice_items(t)]
    sample = {i["hash"] for i in eleven.sample_items(items)}
    made = {}
    for v in voices:
        d = eleven.samples_dir(t, v["id"])
        if os.path.isdir(d):
            made[v["id"]] = {name[:-4] for name in os.listdir(d)}
    clips = t.config().get("clip_engine") or {}
    for it in items:
        it["sample"] = it["hash"] in sample
        it["eleven"] = [vid for vid, hashes in made.items() if it["hash"] in hashes]
        it["choice"] = clips.get(it["hash"], "eleven")
    return {"has_key": bool(eleven.key()), "voices": voices, "items": items, "model": eleven.MODEL,
            "voice": eng["voice"], "job": eleven.JOB, "oron": False}


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
    clips: dict[str, str] = {}           # text_hash -> "eleven" (SIM-TRUNK: "oron" | "eleven")


@router.put("/choice")
def choice(body: ChoiceBody, t: Tenant = Depends(current_tenant)):
    """Өгүүлбэр бүрийн сонголт -> config (eleven_voice, clip_engine). "Аудиог шинэчлэх"-ээр хэрэгжинэ."""
    check_voice(body.voice)
    known = {i["hash"] for i in voice_items(t)}
    clips = {h: e for h, e in body.clips.items() if h in known and e in ("oron", "eleven")}
    cfg = t.config()
    cfg.update(eleven_voice=body.voice, clip_engine={h: e for h, e in clips.items() if e == "eleven"},
               eleven_voice_name=eleven.voice_name(body.voice))
    t.save_config(cfg)
    return {"ok": True, "eleven": sum(e == "eleven" for e in clips.values())}


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
