"""Байгууллагын мэндчилгээ болон түгээмэл асуултын засвар."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

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
    """Бодит дуудлагын асуултыг FAQ-ийн асуултын шинэ хувилбар болгоно."""
    data = load_faq(t)
    question = " ".join(body.question.split())[:300]
    for row in data.get("faq", []):
        if row.get("id") == body.faq_id:
            if question and question not in row.get("questions", []):
                row.setdefault("questions", []).append(question)
                row.pop("auto", None)
                write_json(t.faq_path, data)
            return {"ok": True}
    raise HTTPException(404, "FAQ олдсонгүй")
