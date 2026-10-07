"""
Англи хэл (хоёр хэлтэй горим) — SIM-TRUNK web/app.py-ийн "англи хэл" хэсэгтэй ЯГ ижил (english_core = SIM-TRUNK english.py).

  GET  /api/english               -> орчуулах хариултууд, хэллэг, хуучирсан орчуулга, аудио бэлдсэн эсэх
  PUT  /api/english               -> орчуулга хадгалах (AI зохиохгүй: байгууллага өөрөө бичнэ)
  POST /api/english/build         -> англи аудио бэлдэх
  GET  /api/english/audio/{hash}  -> англи хариултын аудио (?phone=1 утасны чанар)
"""
import json
import os
import re

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

import english_core as english
import knowledge_jobs
from audio_files import phone_quality
from deps import current_tenant
from tenant import Tenant

router = APIRouter(prefix="/api/english", tags=["english"])


def load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


@router.get("")
def get_english(t: Tenant = Depends(current_tenant)):
    meta = load_json(os.path.join(t.kb_index_dir, "english.json"), {})
    built = {x["hash"]: x["clip"]["text"] for x in meta.get("items", []) if x.get("clip")}
    qa = load_json(os.path.join(t.kb_index_dir, "audio_qa.json"), {}).get("english", {})
    items = english.items(t)
    for x in items:
        x["built"] = built.get(x["hash"]) == x["en"] if x["en"] else False
        check = qa.get(x["hash"], {}) if x["built"] and qa.get(x["hash"], {}).get("text") == x["en"] else {}
        x["flags"], x["hyp"] = check.get("flags", []), check.get("hyp")
    over = english.load(t)["phrases"]
    return {"enabled": english.enabled(t), "items": items, "stale": english.stale(t),
            "phrases": english.phrases(t), "custom_phrases": sorted(over), "built": bool(meta),
            "built_at": os.path.getmtime(os.path.join(t.kb_index_dir, "english.json")) if meta else None}


class EnglishBody(BaseModel):
    enabled: bool
    answers: dict[str, str] = {}             # монгол бичвэрийн hash -> англи
    questions: dict[str, list[str]] = {}     # faq id -> англи асуултууд
    phrases: dict = {}                       # DEFAULT_PHRASES_EN-ийг дарах (өөрчилсөн нь л)


@router.put("")
def put_english(body: EnglishBody, t: Tenant = Depends(current_tenant)):
    """Орчуулга хадгалах. Англи текстийг AI зохиохгүй: байгууллага өөрөө бичнэ (эсвэл орчуулагч)."""
    by_hash = {x["hash"]: x for x in english.items(t)}
    data = english.load(t)
    answers = {h: v for h, v in data["answers"].items() if h not in by_hash}   # хуучирсныг хадгална (сэргээхэд)
    for h, en in body.answers.items():
        en = " ".join(en.split())[:600]
        if h not in by_hash or not en:
            continue
        # загвар FAQ-ийн англи хувилбарыг өөрчлөөгүй бол хадгалахгүй (нэр, утас солигдвол дагаж шинэчлэгдэнэ)
        default = by_hash[h]["en"] if by_hash[h]["standard"] and h not in data["answers"] else None
        if en != default:
            answers[h] = {"mn": by_hash[h]["mn"], "en": en}
    ids = {x["id"] for x in by_hash.values() if x["id"]}
    questions = {k: [" ".join(q.split())[:200] for q in v if q.strip()][:20]
                 for k, v in body.questions.items() if k in ids}
    phrases = {}
    defaults = english.phrases(t, custom=False)        # бөглөсөн загвар: өөрчлөөгүй бол хадгалахгүй
    for k, v in body.phrases.items():
        if k == "lead" and isinstance(v, dict):
            lead = {lk: " ".join(str(lv).split())[:300] for lk, lv in v.items()
                    if lk in defaults["lead"] and str(lv).strip() and lv != defaults["lead"][lk]}
            if lead:
                phrases["lead"] = lead
        elif k == "holds" and isinstance(v, list):
            holds = [" ".join(str(x).split())[:120] for x in v if str(x).strip()][:6]
            if holds and holds != defaults["holds"]:
                phrases["holds"] = holds
        elif k in defaults and isinstance(v, str) and v.strip() and v != defaults[k]:
            phrases[k] = " ".join(v.split())[:300]
    english.save(t, {"phrases": phrases, "answers": answers, "questions": questions})
    cfg = t.config()
    langs = [x for x in cfg.get("languages", ["mn"]) if x != "en"] + (["en"] if body.enabled else [])
    cfg["languages"] = langs
    t.save_config(cfg)
    return {"ok": True}


@router.post("/build")
def build_english(t: Tenant = Depends(current_tenant)):
    try:
        return knowledge_jobs.enqueue(t, "english")
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/audio/{h}")
def audio_en(h: str, phone: int = 0, t: Tenant = Depends(current_tenant)):
    """Англи хариултын бэлдсэн аудио (монгол бичвэрийн hash-аар)."""
    if not re.fullmatch(r"[0-9a-f]{12}", h):
        raise HTTPException(400, "Буруу hash")
    meta = load_json(os.path.join(t.kb_index_dir, "english.json"), {})
    path = next((x["clip"]["audio"] for x in meta.get("items", []) if x["hash"] == h and x.get("clip")), None)
    if not path or not os.path.exists(path):
        raise HTTPException(404, "Англи аудио алга (\"Англи аудио бэлдэх\" дарна уу)")
    if phone:
        return Response(phone_quality(path), media_type="audio/wav")
    return FileResponse(path, media_type="audio/wav")
