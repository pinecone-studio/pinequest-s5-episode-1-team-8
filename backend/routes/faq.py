"""Байгууллагын мэндчилгээ болон түгээмэл асуулт — SIM-TRUNK web/app.py (FAQ)-тай ЯГ ижил.

  GET  /api/faq                         -> faq.json
  PUT  /api/faq                         -> бүтнээр нь хадгална (зассан загвар FAQ "auto" тэмдгээ алдана)
  POST /api/faq/question {faq_id, question} -> хариулж чадаагүй асуултыг FAQ-ийн асуултын хувилбар болгоно
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import knowledge_jobs
from deps import current_tenant
from tenant import Tenant, load_faq, write_json

router = APIRouter(prefix="/api/faq", tags=["faq"])


@router.get("")
def get_faq(t: Tenant = Depends(current_tenant)):
    return load_faq(t)


class FaqItem(BaseModel):
    id: str
    questions: list[str]
    answer: str
    topic: str | None = None
    auto: bool | None = None
    source: str | None = None
    created_at: int | None = None


class FaqBody(BaseModel):
    greeting: str
    fillers: list[str] = []
    topics: dict = {}
    faq: list[FaqItem]


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
        previous = old.get(key, {})
        comparable = {k: v for k, v in previous.items() if k != "auto"}
        if item.auto and row == comparable:
            row["auto"] = True
        rows.append(row)
    greeting = " ".join(body.greeting.split())[:600]
    if not greeting:
        raise HTTPException(400, "Мэндчилгээ хоосон байна")
    data = {**{k: v for k, v in old_data.items() if k.startswith("_")},
            "greeting": greeting,
            "greeting_custom": old_data.get("greeting_custom", False) or greeting != old_data.get("greeting"),
            "fillers": [" ".join(x.split())[:300] for x in body.fillers if x.strip()][:10],
            "topics": body.topics, "faq": rows}
    write_json(t.faq_path, data)
    knowledge_jobs.schedule_build(t)
    return data


class AddQuestion(BaseModel):
    faq_id: str
    question: str


@router.post("/question")
def add_question(body: AddQuestion, t: Tenant = Depends(current_tenant)):
    """Хариулж чадаагүй асуултыг тухайн FAQ-ийн асуултын хувилбар болгон нэмнэ."""
    data = load_faq(t)
    question = " ".join(body.question.split())[:300]
    for item in data.get("faq", []):
        if item.get("id") == body.faq_id:
            if question and question not in item.get("questions", []):
                item.setdefault("questions", []).append(question)
                item.pop("auto", None)
                write_json(t.faq_path, data)
                knowledge_jobs.schedule_build(t)
            return {"ok": True}
    raise HTTPException(404, "FAQ олдсонгүй")
