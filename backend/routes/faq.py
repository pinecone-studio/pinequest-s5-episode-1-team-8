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
def put_faq(body: FaqBody, t: Tenant = Depends(current_tenant)):
    old_data = load_faq(t)
    old = {row.get("id"): row for row in old_data.get("faq", [])}
    seen: set[str] = set()
    rows = []
    for item in body.faq:
        key = item.id.strip()[:80]
        answer = item.answer.strip()[:1200]
        questions = list(dict.fromkeys(" ".join(q.split())[:300] for q in item.questions if q.strip()))[:40]
        if not key or key in seen or not answer or not questions:
            raise HTTPException(400, "FAQ бүр давхцаагүй id, асуулт, хариулттай байна")
        seen.add(key)
        row = {"id": key, "questions": questions, "answer": answer}
        if item.topic:
            row["topic"] = item.topic
        if item.source:
            row["source"] = item.source
        if item.created_at:
            row["created_at"] = item.created_at
        # Загвараас үүссэн FAQ-г өөрчлөөгүй бол auto тэмдгийг хадгална. Зассан бол
        # дараагийн build байгууллагын загвараар дарж бичихгүй.
        previous = old.get(key, {})
        comparable = {k: v for k, v in previous.items() if k != "auto"}
        if item.auto and row == comparable:
            row["auto"] = True
        rows.append(row)
    greeting = " ".join(body.greeting.split())[:600]
    if not greeting:
        raise HTTPException(400, "Мэндчилгээ хоосон байна")
    data = {**{k: v for k, v in old_data.items() if k.startswith("_")},   # "_note" гэх мэт тайлбар (SIM-TRUNK хадгалдаг)
            "greeting": greeting,
            "greeting_custom": old_data.get("greeting_custom", False) or greeting != old_data.get("greeting"),
            "fillers": [" ".join(x.split())[:300] for x in body.fillers if x.strip()][:10],
            "topics": body.topics, "faq": rows}
    write_json(t.faq_path, data)
    return data


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
