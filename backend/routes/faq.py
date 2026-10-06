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


class FaqBody(BaseModel):
    greeting: str
    fillers: list[str] = []
    topics: dict = {}
    faq: list[FaqItem]


@router.put("")
def put_faq(body: FaqBody, t: Tenant = Depends(current_tenant)):
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
        rows.append(row)
    greeting = " ".join(body.greeting.split())[:600]
    if not greeting:
        raise HTTPException(400, "Мэндчилгээ хоосон байна")
    data = {"greeting": greeting, "greeting_custom": True,
            "fillers": [" ".join(x.split())[:300] for x in body.fillers if x.strip()][:10],
            "topics": body.topics, "faq": rows}
    write_json(t.faq_path, data)
    return data
