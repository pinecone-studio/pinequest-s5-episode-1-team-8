"""
AI туслах (вэбийн "AI туршилт"): утасгүйгээр, бичиж/товчлуур дарж AI ресепшнтэй ярина (assistant.py).

  POST /api/assistant  {"session"?, "text"? | "dtmf"?, "mode"?: "caller" | "staff"}
    -> {"session", "replies": [...], "state", "trace": [RAG-ийн олсон баримтууд + оноо],
        "person": хувийн RAG-ийн баримтууд (баталгаажсан хүн) | null, "changes": [өгөгдлийн санд бичсэн]}

  Хувийн хүсэлт ("Эвентэд очиж чадахгүй боллоо") -> код -> хувийн RAG (person_docs) -> өөрчлөлт
  "Ажилтны горим" / mode=staff -> ажилтны код -> бусдын бүртгэл
  Бусад асуулт -> байгууллагын RAG (мэдээллийн өгүүлбэр + FAQ)
"""
import threading
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import assistant
import notify
import people
import rag_store
from deps import current_tenant
from ingest_text import read_file, split_facts
from tenant import Tenant, load_faq

router = APIRouter(prefix="/api/assistant", tags=["assistant"])
SESSIONS: dict[str, dict] = {}
TTL, MAX_SESSIONS = 1800, 200
# Байгууллагын мэдээллээс хариулах: тод таарсан (ORG_MATCH) эсвэл дунд оноотой ч бусдаасаа тод ялгарсан
ORG_MATCH, ORG_MIN, ORG_MARGIN = (0.85, 0.75, 0.05) if assistant.embedder.MODEL == "bge-m3" else (0.55, 0.28, 0.10)
FLOW_FAQ = {"my_account", "staff_mode", "register", "human_request"}
_search = assistant.Search()          # хүсэлтүүдийн вектор кэш бүх ярианд нийтлэг


class Body(BaseModel):
    session: str | None = None
    text: str | None = None
    dtmf: str | None = None
    mode: str = "caller"


def _session(t: Tenant, sid: str | None) -> tuple[str, dict]:
    now = time.time()
    for k in [k for k, v in SESSIONS.items() if now - v["ts"] > TTL]:
        SESSIONS.pop(k, None)
    if sid and sid in SESSIONS and SESSIONS[sid]["slug"] == t.slug:
        SESSIONS[sid]["ts"] = now
        return sid, SESSIONS[sid]
    if len(SESSIONS) >= MAX_SESSIONS:
        SESSIONS.pop(min(SESSIONS, key=lambda k: SESSIONS[k]["ts"]))
    sid = uuid.uuid4().hex
    SESSIONS[sid] = {"slug": t.slug, "flow": None, "ts": now}
    return sid, SESSIONS[sid]


def org_docs(t: Tenant) -> list[tuple[str, str]]:
    """Байгууллагын RAG: мэдээллийн өгүүлбэрүүд (receptionist.db · knowledge_docs эсвэл файлууд) + FAQ асуулт -> хариулт."""
    docs: list[tuple[str, str]] = []
    try:
        con = rag_store._connect(t.dir)
        docs = [(r["text"], r["text"]) for r in con.execute("SELECT text FROM knowledge_docs WHERE kind='fact'")]
        con.close()
    except Exception:
        docs = []
    if not docs:
        import os
        for dp, _, fs in os.walk(t.knowledge_dir):
            for name in sorted(fs):
                if name.lower().endswith((".txt", ".md", ".pdf", ".docx")) and name.lower() != "readme.md":
                    docs += [(x, x) for x, _ in split_facts(read_file(os.path.join(dp, name)))]
    for f in load_faq(t).get("faq", []):
        if f.get("id") in FLOW_FAQ or "TODO" in f.get("answer", ""):
            continue
        docs += [(f["answer"], q) for q in f.get("questions", [])]
    return docs


def org_answer(t: Tenant, text: str) -> tuple[str, list[dict]]:
    ranked = _search.rank(text, org_docs(t), "байгууллагын RAG")
    trace = _search.last
    top = ranked[0][1] if ranked else 0.0
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    if top >= ORG_MATCH or (top >= ORG_MIN and top - second >= ORG_MARGIN):
        return ranked[0][0], trace
    return t.phrases()["error"], trace


def person_view(t: Tenant, lead: dict | None) -> dict | None:
    if not lead:
        return None
    row = people.lead(t.dir, lead["id"]) or lead
    when = people.appointment(t.dir, lead["id"])
    return {"id": row["id"], "name": row.get("name"), "phone": row.get("phone"), "course": row.get("course"),
            "status": row.get("status"), "code": people.ensure_code(t.dir, row["id"]),
            "appointment": people.fmt(when) if when else None,
            "docs": [{"field": d["field"], "text": d["text"], "vector": d["emb"] is not None}
                     for d in people.docs(t.dir, row["id"])]}


def _notify(t: Tenant, ev: dict):
    what = {"phone": "утасны дугаар", "appointment": "уулзалтын цаг", "status": "бүртгэл"}[ev["field"]]
    new = "цуцалсан" if ev["new"] in (None, "canceled") else ev["new"]
    who = "ажилтан өөрчиллөө" if ev.get("staff") else "өөрөө өөрчиллөө"
    msg = (f"{t.config().get('name', t.slug)}: {ev['lead'].get('name') or 'Бүртгэл'} — {what} "
           f"{ev['old'] or '—'} → {new} (AI туслахаар, {who})")
    threading.Thread(target=notify.send, args=(t, msg), daemon=True).start()


SAMPLES = [("Болд", "99112233", "Software Engineer Bootcamp хөтөлбөр"), ("Номин", "88990011", "AI Hackathon эвент"),
           ("Сараа", "95551234", "AI Hackathon эвент")]


@router.post("/samples")
def add_samples(t: Tenant = Depends(current_tenant)):
    """Туршилтад: хөтөлбөр, эвентэд бүртгүүлсэн жишээ хүмүүс (код, хувийн баримт, сул цагтай)."""
    import db
    out = []
    now = datetime.now(people.TZ)
    for i, (name, phone, course) in enumerate(SAMPLES):
        lead_id = db.add_lead(t.db_path, f"sample-{uuid.uuid4().hex[:8]}", name, phone, None, phone, "lead", course=course)
        if i == 0:                        # Болд — товлосон уулзалттай
            slots = people.free_slots(t.dir, now)
            if slots:
                people.set_appointment(t.dir, lead_id, slots[0], "web", None, now=now)
        out.append(person_view(t, {"id": lead_id}))
    return {"people": out, "staff_pin": people.staff_pin(t.dir)}


@router.post("")
def talk(body: Body, t: Tenant = Depends(current_tenant)):
    if body.mode not in ("caller", "staff"):
        raise HTTPException(400, "mode: caller | staff")
    text = " ".join((body.text or "").split())[:500]
    dtmf = "".join(c for c in (body.dtmf or "") if c in "0123456789*#")[:16]
    if not text and not dtmf and not (body.mode == "staff" and not body.session):
        raise HTTPException(400, "Юу ч бичээгүй байна")
    sid, s = _session(t, body.session)
    ph = t.phrases()["account"]
    call_id = f"web-{sid[:8]}"
    trace: list[dict] = []
    replies: list[str] = []

    if s["flow"] is None and body.mode == "staff":
        s["flow"] = assistant.AccountFlow(t.dir, _search, None, call_id, staff=True)
        if not text and not dtmf:
            return {"session": sid, "replies": [ph["staff_ask_pin"]], "state": "staff_code", "trace": [],
                    "person": None, "changes": []}

    for _ in range(2):                       # урсгалын хариулт биш бол энгийн горимоор дахин нэг удаа
        flow = s["flow"]
        if flow is None:
            if dtmf:
                replies = ["Эхлээд хүсэлтээ бичнэ үү. Жишээ нь: «Эвентэд очиж чадахгүй боллоо»."]
                break
            stems = assistant.stems(text)
            if any(x.startswith("ажил") for x in stems) and any(x.startswith(("горим", "нэвт")) for x in stems) \
                    or any(x.startswith("багш") for x in stems):
                s["flow"] = assistant.AccountFlow(t.dir, _search, None, call_id, staff=True)
                replies, trace = [ph["staff_ask_pin"]], []
                break
            intent = assistant.detect_intent(_search, text)
            trace = _search.last
            if intent:
                s["flow"] = assistant.AccountFlow(t.dir, _search, intent, call_id)
                replies = [ph["ask_code"]]
                trace = [{**trace[0], "kind": f"хүсэлт: {assistant.INTENT_LABELS[intent]}"}] + trace[1:] if trace else []
            else:
                answer, trace = org_answer(t, text)
                replies = [answer]
            break
        keys = flow.handle_dtmf(dtmf) if dtmf else flow.handle(text)
        if keys is None:
            s["flow"] = None
            continue
        trace = flow.search.last if flow.search.last else []
        flow.search.last = []
        replies = assistant.render(ph, people.lead(t.dir, flow.lead["id"]) if flow.lead else None, keys)
        for ev in flow.events:
            _notify(t, ev)
        break

    flow = s["flow"]
    changes = []
    if flow and flow.lead:
        s["last_lead"] = flow.lead
    if flow and flow.events:
        s["last_lead"] = flow.events[-1]["lead"]
        lead_ids = {ev["lead"]["id"] for ev in flow.events}
        changes = [c for lid in lead_ids for c in people.changes(t.dir, lid)[:len(flow.events) + 1]
                   if c["call_uuid"] == call_id][:len(flow.events)]
        flow.events.clear()
    person = person_view(t, flow.lead if flow and flow.lead else s.get("last_lead") if flow else None)
    state = flow.state if flow else "idle"
    if flow and flow.finished:
        s["flow"] = None
    return {"session": sid, "replies": replies, "state": state, "trace": trace, "person": person, "changes": changes,
            "dtmf_len": flow.dtmf_len() if flow else 0, "staff": bool(flow and flow.staff)}
