"""Баталгаатай англи орчуулга, хэллэг болон урьдчилан бэлдсэн англи аудио."""
import hashlib
import json
import os
import re

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from audio_files import phone_quality
from deps import current_tenant
import knowledge_jobs
from tenant import Tenant, load_faq, write_json

router = APIRouter(prefix="/api/english", tags=["english"])

DEFAULT_PHRASES = {
    "greeting_suffix": "For English, please go ahead and speak English.",
    "repeat": "Sorry, I didn't catch that. Could you say it again?",
    "error": "Sorry, I couldn't find that information. Would you like a staff member to call you back?",
    "mongolian_only": ("Sorry, I have that information only in Mongolian. "
                       "Would you like a staff member to call you back?"),
    "holds": ["One moment, please.", "Let me check that for you."],
    "lead": {
        "ask_name_again": "Sure. May I have your name, please?",
        "ask_phone": "Thank you. What phone number can we reach you at? You can also type it on your keypad.",
        "readback": "Your number is",
        "confirm": "Is that correct?",
        "phone_retry": "Sorry, I didn't get that. Please type your eight digit phone number on your keypad.",
        "done": "Thank you, you're all set. A staff member will contact you soon. Is there anything else I can help you with?",
        "done_no_phone": ("I've noted your name, but I couldn't get your number. Please call us at {phone_en}. "
                          "Is there anything else I can help you with?"),
        "declined": "Alright. Is there anything else I can help you with?",
    },
}

STANDARD_EN = {
    "smalltalk_hello": {
        "answer": "Hello, this is {name}. How can I help you?",
        "questions": ["Hello", "Hi", "Good morning", "Hello, is anyone there?"],
    },
    "smalltalk_thanks": {
        "answer": "You're welcome. Is there anything else I can help you with?",
        "questions": ["Thank you", "Thanks a lot", "Okay, thanks", "I see, thank you"],
    },
    "smalltalk_bye": {
        "answer": "Thank you for calling {name}. Have a nice day!",
        "questions": ["Goodbye", "Bye", "That's all", "Nothing else, thanks", "No, that's it"],
    },
    "smalltalk_capabilities": {
        "answer": ("I'm the AI assistant of {name}. You can ask me about our services, "
                   "or ask to register or to talk to a staff member."),
        "questions": ["What can I ask you?", "Who are you?", "Are you a robot?", "What do you know?"],
    },
    "human_request": {
        "answer": "Sure, a staff member will call you back. May I have your name, please?",
        "questions": ["I want to talk to a person", "Can I speak to someone?",
                      "Connect me to an operator", "Please call me back", "I need a human"],
    },
    "register": {
        "answer": "I can help you register. May I have your name, please?",
        "questions": ["I want to register", "I'd like to sign up", "How do I enroll?",
                      "I want to book an appointment", "Can I make a reservation?"],
    },
    "contact_phone": {
        "answer": "Our phone number is {phone_en}.",
        "questions": ["What is your phone number?", "What number should I call?", "How can I contact you?"],
    },
}
EN_DIGITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]


def digest(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:12]


def english_path(t: Tenant) -> str:
    return t.path("english.json")


def load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError):
        return default


def load(t: Tenant) -> dict:
    data = load_json(english_path(t), {})
    return {"answers": data.get("answers", {}), "questions": data.get("questions", {}),
            "phrases": data.get("phrases", {})}


def phone_en(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    words = [EN_DIGITS[int(char)] for char in digits]
    return ", ".join(" ".join(words[index:index + 4]) for index in range(0, len(words), 4))


def values(t: Tenant) -> dict:
    cfg = t.config()
    return {"name": cfg.get("name", t.slug), "phone_en": phone_en(cfg.get("phone", ""))}


def phrases(t: Tenant, custom: bool = True) -> dict:
    over, vals = (load(t)["phrases"] if custom else {}), values(t)

    def fill(value):
        if isinstance(value, str):
            return value.format(**vals)
        return [fill(item) for item in value]

    out = {key: fill(over.get(key, value)) for key, value in DEFAULT_PHRASES.items() if key != "lead"}
    lead = {**DEFAULT_PHRASES["lead"], **over.get("lead", {})}
    if not t.config().get("phone"):
        lead["done_no_phone"] = ("I've noted your name, but I couldn't get your number. Please call us again. "
                                 "Is there anything else I can help you with?")
    out["lead"] = {key: fill(value) for key, value in lead.items()}
    return out


def fact_rows(t: Tenant) -> list[dict]:
    return load_json(os.path.join(t.kb_index_dir, "facts.json"), {}).get("facts", [])


def source_items(t: Tenant) -> list[dict]:
    saved, cfg, rows, seen = load(t), t.config(), [], set()
    vals = values(t)
    for faq in load_faq(t).get("faq", []):
        text = faq.get("answer", "")
        if not text or "TODO" in text:
            continue
        key = digest(text)
        standard = STANDARD_EN.get(faq.get("id")) if faq.get("auto") else None
        default_en = standard["answer"].format(**vals) if standard else ""
        if faq.get("id") == "contact_phone" and not cfg.get("phone"):
            default_en = ""
        default_questions = standard["questions"] if standard else []
        rows.append({"id": faq.get("id"), "kind": "faq", "mn": text, "hash": key,
                     "en": saved["answers"].get(key, {}).get("en", default_en),
                     "questions": faq.get("questions", []),
                     "questions_en": saved["questions"].get(faq.get("id"), default_questions),
                     "standard": bool(standard)})
        seen.add(key)
    for fact in fact_rows(t):
        text, key = fact.get("text", ""), digest(fact.get("text", ""))
        if not text or key in seen:
            continue
        seen.add(key)
        rows.append({"id": None, "kind": "knowledge", "mn": text, "hash": key,
                     "en": saved["answers"].get(key, {}).get("en", ""), "questions": [],
                     "questions_en": [], "standard": False, "section": fact.get("section")})
    return rows[:1000]


@router.get("")
def get_english(t: Tenant = Depends(current_tenant)):
    data, cfg = load(t), t.config()
    meta_path = os.path.join(t.kb_index_dir, "english.json")
    meta = load_json(meta_path, {})
    built = {row.get("hash"): row.get("clip", {}).get("text") for row in meta.get("items", []) if row.get("clip")}
    qa = load_json(os.path.join(t.kb_index_dir, "audio_qa.json"), {}).get("english", {})
    items = source_items(t)
    for row in items:
        row["built"] = bool(row["en"] and built.get(row["hash"]) == row["en"])
        check = qa.get(row["hash"], {}) if row["built"] else {}
        if check.get("text") != row["en"]:
            check = {}
        row["flags"], row["hyp"] = check.get("flags", []), check.get("hyp")
    current = {row["hash"] for row in items}
    stale = [{"hash": key, **value} for key, value in data["answers"].items() if key not in current]
    return {"enabled": "en" in cfg.get("languages", ["mn"]), "items": items,
            "phrases": phrases(t), "stale": stale, "built": bool(meta),
            "built_at": os.path.getmtime(meta_path) if os.path.isfile(meta_path) else None}


class EnglishBody(BaseModel):
    enabled: bool
    answers: dict[str, str] = {}
    questions: dict[str, list[str]] = {}
    phrases: dict = {}


@router.put("")
def put_english(body: EnglishBody, t: Tenant = Depends(current_tenant)):
    current = {row["hash"]: row for row in source_items(t)}
    old = load(t)
    answers = {key: value for key, value in old["answers"].items() if key not in current}
    for key, value in body.answers.items():
        text = " ".join(value.split())[:600]
        if key in current and text:
            default = current[key]["en"] if current[key].get("standard") and key not in old["answers"] else None
            if text != default:
                answers[key] = {"mn": current[key]["mn"], "en": text}
    ids = {row["id"] for row in current.values() if row.get("id")}
    questions = {key: [" ".join(q.split())[:200] for q in value if q.strip()][:20]
                 for key, value in body.questions.items() if key in ids}
    clean_phrases = {}
    defaults = phrases(t, custom=False)
    for key, value in body.phrases.items():
        if key == "holds" and isinstance(value, list):
            holds = [" ".join(str(x).split())[:120] for x in value if str(x).strip()][:6]
            if holds and holds != defaults["holds"]:
                clean_phrases[key] = holds
        elif key == "lead" and isinstance(value, dict):
            lead = {k: " ".join(str(v).split())[:300] for k, v in value.items()
                    if k in defaults["lead"] and str(v).strip() and v != defaults["lead"][k]}
            if lead:
                clean_phrases[key] = lead
        elif (key in defaults and isinstance(value, str) and value.strip()
              and value != defaults[key]):
            clean_phrases[key] = " ".join(value.split())[:300]
    write_json(english_path(t), {"answers": answers, "questions": questions, "phrases": clean_phrases})
    cfg = t.config()
    cfg["languages"] = [x for x in cfg.get("languages", ["mn"]) if x != "en"] + (["en"] if body.enabled else [])
    t.save_config(cfg)
    return {"ok": True}


@router.post("/build")
def build_english(t: Tenant = Depends(current_tenant)):
    try:
        return knowledge_jobs.enqueue(t, "english")
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/audio/{item_hash}")
def english_audio(item_hash: str, phone: int = 0, t: Tenant = Depends(current_tenant)):
    if not re.fullmatch(r"[0-9a-f]{12}", item_hash):
        raise HTTPException(400, "Буруу hash")
    meta = load_json(os.path.join(t.kb_index_dir, "english.json"), {})
    path = next((row.get("clip", {}).get("audio") for row in meta.get("items", [])
                 if row.get("hash") == item_hash and row.get("clip")), None)
    if not path or not os.path.isfile(path):
        raise HTTPException(404, "Англи аудио алга")
    if phone:
        return Response(phone_quality(path), media_type="audio/wav")
    return FileResponse(path, media_type="audio/wav")
