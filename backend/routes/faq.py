"""Байгууллагын мэндчилгээ болон түгээмэл асуулт — SIM-TRUNK web/app.py (FAQ)-тай ЯГ ижил.

  GET  /api/faq                         -> faq.json
  PUT  /api/faq                         -> бүтнээр нь хадгална (зассан загвар FAQ "auto" тэмдгээ алдана)
  POST /api/faq/question {faq_id, question} -> хариулж чадаагүй асуултыг FAQ-ийн асуултын хувилбар болгоно
"""
import json
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import current_tenant
from tenant import Tenant

router = APIRouter(prefix="/api/faq", tags=["faq"])


def load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


@router.get("")
def get_faq(t: Tenant = Depends(current_tenant)):
    return load_json(t.faq_path, {})


@router.put("")
def put_faq(data: dict, t: Tenant = Depends(current_tenant)):
    for key in ("greeting", "fillers", "topics", "faq"):
        if key not in data:
            raise HTTPException(400, f"faq.json-д '{key}' байх ёстой")
    for item in data["faq"]:
        if not item.get("id") or not item.get("answer") or not isinstance(item.get("questions"), list):
            raise HTTPException(400, "FAQ бүр id, questions (жагсаалт), answer-тэй байх ёстой")
    old = {x["id"]: x for x in load_json(t.faq_path, {}).get("faq", [])}
    for item in data["faq"]:        # хэрэглэгч зассан загвар FAQ -> "auto" тэмдгийг авна (дахин үүсгэхэд дарагдахгүй)
        if item.get("auto") and {k: v for k, v in item.items() if k != "auto"} != \
                {k: v for k, v in old.get(item["id"], {}).items() if k != "auto"}:
            item.pop("auto")
    if data.get("greeting") != load_json(t.faq_path, {}).get("greeting"):
        data["greeting_custom"] = True
    with open(t.faq_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {"ok": True}


class AddQuestion(BaseModel):
    faq_id: str
    question: str


@router.post("/question")
def add_question(body: AddQuestion, t: Tenant = Depends(current_tenant)):
    """Хариулж чадаагүй асуултыг тухайн FAQ-ийн асуултын хувилбар болгон нэмнэ."""
    data = load_json(t.faq_path, {})
    for item in data.get("faq", []):
        if item["id"] == body.faq_id:
            q = body.question.strip()
            if q and q not in item["questions"]:
                item["questions"].append(q)
            with open(t.faq_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return {"ok": True}
    raise HTTPException(404, "FAQ олдсонгүй")
