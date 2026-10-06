"""Монгол хариултын англи орчуулга болон хоёр хэлтэй горимын тохиргоо."""
import hashlib
import json
import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import current_tenant
from tenant import Tenant, load_faq, write_json

router = APIRouter(prefix="/api/english", tags=["english"])
DEFAULT_PHRASES = {"greeting_suffix": "For English, please speak English.",
                   "repeat": "Sorry, could you please repeat that?",
                   "missing": "I do not have that information yet. Our staff can call you back."}


def digest(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:12]


def path(t: Tenant) -> str:
    return t.path("english.json")


def load(t: Tenant) -> dict:
    try:
        with open(path(t), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"answers": {}, "questions": {}, "phrases": {}}


def source_items(t: Tenant) -> list[dict]:
    rows = []
    for faq in load_faq(t).get("faq", []):
        if faq.get("answer"):
            rows.append({"id": faq["id"], "kind": "faq", "mn": faq["answer"], "questions": faq.get("questions", [])})
    if os.path.isdir(t.knowledge_dir):
        for name in sorted(os.listdir(t.knowledge_dir)):
            if name.lower().endswith((".md", ".txt")):
                with open(os.path.join(t.knowledge_dir, name), encoding="utf-8") as f:
                    rows += [{"id": None, "kind": "knowledge", "mn": line.strip(), "questions": []}
                             for line in f if line.strip() and not line.lstrip().startswith("#")]
    return rows[:1000]


@router.get("")
def get_english(t: Tenant = Depends(current_tenant)):
    data, cfg = load(t), t.config()
    items = []
    for row in source_items(t):
        key = digest(row["mn"])
        items.append({**row, "hash": key, "en": data["answers"].get(key, {}).get("en", ""),
                      "questions_en": data["questions"].get(row["id"], []) if row["id"] else []})
    return {"enabled": "en" in cfg.get("languages", ["mn"]), "items": items,
            "phrases": {**DEFAULT_PHRASES, **data.get("phrases", {})}}


class EnglishBody(BaseModel):
    enabled: bool
    answers: dict[str, str] = {}
    questions: dict[str, list[str]] = {}
    phrases: dict[str, str] = {}


@router.put("")
def put_english(body: EnglishBody, t: Tenant = Depends(current_tenant)):
    valid = {digest(x["mn"]): x["mn"] for x in source_items(t)}
    answers = {key: {"mn": valid[key], "en": " ".join(value.split())[:1200]}
               for key, value in body.answers.items() if key in valid and value.strip()}
    faq_ids = {x.get("id") for x in source_items(t) if x.get("id")}
    questions = {key: [" ".join(q.split())[:300] for q in value if q.strip()][:30]
                 for key, value in body.questions.items() if key in faq_ids}
    phrases = {key: " ".join(value.split())[:400] for key, value in body.phrases.items()
               if key in DEFAULT_PHRASES and value.strip()}
    write_json(path(t), {"answers": answers, "questions": questions, "phrases": phrases})
    cfg = t.config()
    cfg["languages"] = [x for x in cfg.get("languages", ["mn"]) if x != "en"] + (["en"] if body.enabled else [])
    t.save_config(cfg)
    return {"ok": True}
