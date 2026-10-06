"""TTS дуудлагын толь, хурд, завсар болон уншигдах өгүүлбэрийн жагсаалт."""
import hashlib
import json
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import current_tenant
from tenant import Tenant, load_faq

router = APIRouter(prefix="/api/voice", tags=["voice"])


def item(kind: str, text: str) -> dict:
    return {"kind": kind, "text": text, "hash": hashlib.sha1(text.encode()).hexdigest()[:12]}


def voice_items(t: Tenant) -> list[dict]:
    data = load_faq(t)
    rows = [item("Мэндчилгээ", data.get("greeting", ""))] if data.get("greeting") else []
    rows += [item("Хүлээлгэх", text) for text in data.get("fillers", []) if text]
    rows += [item("FAQ", row["answer"]) for row in data.get("faq", []) if row.get("answer")]
    try:   # мэдээллийн өгүүлбэрүүд ("Бэлдэх"-ийн дараа knowledge_index/facts.json-д)
        with open(t.path("knowledge_index", "facts.json"), encoding="utf-8") as f:
            rows += [item("Мэдээлэл", x["text"]) for x in json.load(f).get("facts", []) if x.get("text")]
    except (OSError, ValueError):
        pass
    seen = set()   # ижил өгүүлбэр нэг удаа
    return [r for r in rows if not (r["hash"] in seen or seen.add(r["hash"]))]


@router.get("")
def get_voice(t: Tenant = Depends(current_tenant)):
    cfg = t.config()
    items = [{**x, "recorded": os.path.exists(t.path("recordings", f"{x['hash']}.wav"))} for x in voice_items(t)]
    return {"items": items, "settings": {"lexicon": cfg.get("lexicon", []),
            "speed": cfg.get("tts_speed", 0.85), "pause_ms": cfg.get("pause_ms", 300)}}


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
