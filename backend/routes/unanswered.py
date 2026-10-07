"""Хариулж чадаагүй асуултыг дахин шалгах, зөв хариулт заах, шинэ FAQ болгох."""
import itertools
import json
import os
import re
import threading
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from audio_files import text_hash
import db
from deps import current_tenant
import knowledge_jobs
from routes import training
from tenant import Tenant, load_faq, write_json

router = APIRouter(prefix="/api/unanswered", tags=["unanswered"])
REVIEW_URL = os.getenv("REVIEW_URL", f"http://127.0.0.1:{os.getenv('REVIEW_PORT', '9093')}/review")
LOCK = threading.RLock()
SPECIAL = re.compile(r"<\|[^|>]*\|>")
NUMBER_WORDS = {"тэг", "нэг", "хоёр", "гурав", "гурван", "дөрөв", "дөрвөн", "тав", "таван", "зургаа",
                "зургаан", "долоо", "долоон", "найм", "найман", "ес", "есөн", "арав", "арван", "хорь",
                "хорин", "гуч", "гучин", "дөч", "дөчин", "тавь", "тавин", "жар", "жаран", "дал", "далан",
                "ная", "наян", "ер", "ерэн", "зуу", "зуун", "мянга", "мянган"}


def load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError):
        return default


def hidden_path(t: Tenant) -> str:
    return t.path("data", "unanswered_hidden.json")


def pending_path(t: Tenant) -> str:
    return t.path("data", "answers_pending.json")


def rows(t: Tenant, limit: int) -> list[dict]:
    """Tenant-ийн raw unanswered мөрүүд. Бусад endpoint нэг SQL-ийг давтаж бичихгүй."""
    placeholders = ",".join("?" * len(db.UNANSWERED_ROUTES))
    with db.connect(t.db_path) as con:
        result = con.execute(f"""
            SELECT u.id, u.call_uuid, u.ts, u.text AS question, a.route, a.score
            FROM messages a JOIN messages u ON u.id = (
                SELECT MAX(id) FROM messages WHERE call_uuid=a.call_uuid AND role='user' AND id < a.id)
            WHERE a.role='assistant' AND a.route IN ({placeholders})
            ORDER BY a.ts DESC LIMIT ?""", (*db.UNANSWERED_ROUTES, limit)).fetchall()
    return [dict(row) for row in result]


@router.get("")
def unanswered(limit: int = Query(200, ge=1, le=1000), t: Tenant = Depends(current_tenant)):
    return rows(t, limit)


@router.get("/review")
def review(t: Tenant = Depends(current_tenant)):
    """Асуулт бүрийг ажиллаж буй SIM-TRUNK AI-аар одоо дахин шалгуулна.

    AI унтарсан үед raw жагсаалт хэвээр ирнэ (live=false), тиймээс хэрэглэгч хариулт
    заах/шинээр бичих ажлаа үргэлжлүүлж чадна.
    """
    hidden = set(load_json(hidden_path(t), []))
    seen: set[str] = set()
    items = []
    for row in rows(t, 500):
        question = (row.get("question") or "").strip()
        if question and question not in seen and question not in hidden:
            seen.add(question)
            items.append({"q": question, "ts": row["ts"], "call_uuid": row["call_uuid"], "route": row["route"]})

    live = False
    if items:
        try:
            response = httpx.post(REVIEW_URL, json={"tenant": t.slug, "questions": [item["q"] for item in items]},
                                  timeout=180)
            if response.status_code == 200 and isinstance(response.json(), list):
                for item, current in zip(items, response.json()):
                    item["now"] = current
                live = True
        except (httpx.HTTPError, ValueError):
            pass

    choices = training.answers(t)
    faq_values = {row["value"] for row in choices["faq"]}
    fact_values = {row.get("text"): row["value"] for row in choices["facts"]}
    for item in items:
        for suggestion in (item.get("now") or {}).get("suggest", []):
            if suggestion.get("kind") == "faq":
                value = f"faq:{suggestion.get('id', '')}"
                suggestion["value"] = value if value in faq_values else ""
            else:
                suggestion["value"] = fact_values.get(suggestion.get("text"), "")
    return {"items": items, "live": live, "pending": load_json(pending_path(t), [])}


class QuestionBody(BaseModel):
    q: str


@router.post("/hide")
def hide(body: QuestionBody, t: Tenant = Depends(current_tenant)):
    question = " ".join(body.q.split())[:500]
    if not question:
        raise HTTPException(400, "Асуулт хоосон байна")
    with LOCK:
        hidden = load_json(hidden_path(t), [])
        if question not in hidden:
            hidden.append(question)
            write_json(hidden_path(t), hidden)
    return {"ok": True}


def add_pending(t: Tenant, note: str):
    with LOCK:
        pending = load_json(pending_path(t), [])
        if note not in pending:
            pending.append(note)
            write_json(pending_path(t), pending)


def clean_question(t: Tenant, text: str) -> str:
    """SIM-TRUNK-ийн STT cleanup + байгууллагын stt_fixes-ийг хөнгөн dependency-гүй хэрэглэнэ."""
    text = SPECIAL.sub(" ", text)
    text = re.sub(r"([^\W\d])\1{3,}", r"\1", text)
    words = []
    for word, group in itertools.groupby(text.split()):
        count = len(list(group))
        words += [word] * (count if word.lower() in NUMBER_WORDS or word.isdigit() or count < 3 else 1)
    text = " ".join(words).strip()
    for item in t.config().get("stt_fixes", []):
        try:
            text = re.sub(r"(?<![а-яөүёa-z])(?:" + item["heard"] + ")", item["fix"], text, flags=re.I)
        except (re.error, KeyError, TypeError):
            continue
    return text


class NewAnswerBody(BaseModel):
    q: str
    answer: str
    questions: list[str] = Field(default_factory=list)


@router.post("/answer")
def add_answer(body: NewAnswerBody, t: Tenant = Depends(current_tenant)):
    """Байгууллагын бичсэн шинэ хариултыг FAQ болгоно. Ижил хариултыг давхар үүсгэхгүй."""
    answer = " ".join(body.answer.split())
    if not 5 <= len(answer) <= 400:
        raise HTTPException(400, "Хариулт 5-400 тэмдэгт байна")
    questions = [clean_question(t, body.q)] + [" ".join(question.split()) for question in body.questions]
    questions = [question[:300] for question in dict.fromkeys(questions) if question][:20]
    if not questions:
        raise HTTPException(400, "Асуулт хоосон байна")

    with LOCK:
        data = load_faq(t) or {"greeting": "", "fillers": [], "topics": {}, "faq": []}
        item = next((row for row in data.get("faq", []) if " ".join(row.get("answer", "").split()) == answer), None)
        if item:
            item["questions"] = list(dict.fromkeys(item.get("questions", []) + questions))[:40]
            item.pop("auto", None)
        else:
            item = {"id": f"web_{text_hash(answer)}", "questions": questions, "answer": answer,
                    "source": "web", "created_at": int(time.time())}
            data.setdefault("faq", []).append(item)
        write_json(t.faq_path, data)
    add_pending(t, f"шинэ хариулт: {answer[:60]}")
    hide(QuestionBody(q=body.q), t)
    return {"ok": True, "id": item["id"]}


class TeachBody(BaseModel):
    q: str
    answer: str


@router.post("/teach")
def teach(body: TeachBody, t: Tenant = Depends(current_tenant)):
    result = training.save_example(t, clean_question(t, body.q), body.answer)
    add_pending(t, f"заасан: {body.q[:60]}")
    hide(QuestionBody(q=body.q), t)
    return result


@router.post("/apply")
def apply_answers(t: Tenant = Depends(current_tenant)):
    try:
        result = knowledge_jobs.enqueue(t, "answers")
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    write_json(pending_path(t), [])
    return result
