"""Хариулж чадаагүй асуултыг дахин шалгах, зөв хариулт заах, шинэ FAQ болгох —
SIM-TRUNK web/app.py ("хариулж чадаагүй: шалгах, хариулт бэлдэх")-тэй ЯГ ижил.
AI сервер (phone_server REVIEW_PORT) асуулт бүрийг ОДОО ямар хариулт авахыг шалгаж, ойр хариултуудыг санал болгоно."""
import itertools
import json
import os
import re
import threading
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from audio_files import text_hash
import db
from deps import current_tenant
import knowledge_jobs
from routes import training
from tenant import Tenant

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
    hidden = set(load_json(hidden_path(t), []))
    seen, items = set(), []
    for r in rows(t, 500):
        q = (r["question"] or "").strip()
        if q and q not in seen and q not in hidden:
            seen.add(q)
            items.append({"q": q, "ts": r["ts"], "call_uuid": r["call_uuid"], "route": r["route"]})
    live = False
    try:
        res = httpx.post(REVIEW_URL, json={"tenant": t.slug, "questions": [i["q"] for i in items]}, timeout=180)
        if res.status_code == 200:
            for i, rv in zip(items, res.json()):
                i["now"] = rv
            live = True
    except httpx.HTTPError:
        pass
    idx = {f["text"]: n for n, f in enumerate(load_json(os.path.join(t.kb_index_dir, "facts.json"), {}).get("facts", []))}
    for i in items:
        for s in (i.get("now") or {}).get("suggest", []):
            s["value"] = f"faq:{s['id']}" if s["kind"] == "faq" else (f"fact:{idx[s['text']]}" if s["text"] in idx else "")
    return {"items": items, "live": live, "pending": load_json(pending_path(t), [])}


class QuestionBody(BaseModel):
    q: str


@router.post("/hide")
def hide(body: QuestionBody, t: Tenant = Depends(current_tenant)):
    """Жагсаалтаас нуух (чимээ, шийдэгдсэн). Дуудлагын лог хэвээр."""
    hidden = load_json(hidden_path(t), [])
    if body.q not in hidden:
        hidden.append(body.q)
        os.makedirs(os.path.dirname(hidden_path(t)), exist_ok=True)
        with open(hidden_path(t), "w", encoding="utf-8") as f:
            json.dump(hidden, f, ensure_ascii=False, indent=1)
    return {"ok": True}


def add_pending(t: Tenant, note: str):
    pending = load_json(pending_path(t), [])
    pending.append(note)
    os.makedirs(os.path.dirname(pending_path(t)), exist_ok=True)
    with open(pending_path(t), "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=1)


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
    questions: list[str] = []        # нэмэлт хувилбарууд (заавал биш)


@router.post("/answer")
def add_answer(body: NewAnswerBody, t: Tenant = Depends(current_tenant)):
    """Шинэ хариулт -> шинэ FAQ (асуулт + хариулт). "Хэрэгжүүлэх"-д ElevenLabs аудио үүсгэж AI-г сургана.
    Хариултыг байгууллага өөрөө бичнэ — AI зохиохгүй."""
    answer = " ".join(body.answer.split())
    if not 5 <= len(answer) <= 400:
        raise HTTPException(400, "Хариулт 5-400 тэмдэгт байна")
    q = clean_question(t, body.q)                    # stt.clean + байгууллагын stt_fixes (FAQRouter.fix_stt)
    questions = [x for x in dict.fromkeys([q] + [" ".join(x.split()) for x in body.questions]) if x][:20]
    with LOCK:
        data = load_json(t.faq_path, {"faq": []})
        fid = "web_" + text_hash(answer)[:8]
        item = next((x for x in data["faq"] if x["id"] == fid), None)
        if item:
            item["questions"] = list(dict.fromkeys(item["questions"] + questions))
        else:
            data["faq"].append({"id": fid, "questions": questions, "answer": answer, "source": "web",
                                "created_at": int(time.time())})
        tmp = t.faq_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, t.faq_path)
    add_pending(t, f"шинэ хариулт: {answer[:60]}")
    hide(QuestionBody(q=body.q), t)
    return {"ok": True, "id": fid}


class TeachBody(BaseModel):
    q: str
    answer: str          # faq:<id> | fact:<index> | label:other | label:clarify


@router.post("/teach")
def teach(body: TeachBody, t: Tenant = Depends(current_tenant)):
    """Байгаа хариултыг заах (AI сургалтын жишээ) + жагсаалтаас нуух."""
    training.save_example(t, body.q, body.answer)
    add_pending(t, f"заасан: {body.q[:60]}")
    hide(QuestionBody(q=body.q), t)
    return {"ok": True}


@router.post("/apply")
def apply_answers(t: Tenant = Depends(current_tenant)):
    """Бичсэн хариултын аудио (ElevenLabs) + сургалт. AI зогсохгүй."""
    try:
        status = knowledge_jobs.enqueue(t, "answers")
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    with open(pending_path(t), "w", encoding="utf-8") as f:
        json.dump([], f)
    return status
