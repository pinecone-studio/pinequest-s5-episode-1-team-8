"""
Хувийн RAG (people.py): бүртгэлийн код, утасны AI-ийн хийсэн өөрчлөлтүүд. Ажилтан өгөгдлийн сан руу гараар орохгүй —
код бүртгэл үүсэхэд автоматаар, сул цаг ажлын цагаас (settings.json "booking"), өөрчлөлтийг утсаар:
залгагч өөрийн кодоор, ажилтан (багш) ажилтны кодоор бусдын бүртгэлийг ("Болдын цагийг Баасан руу шилжүүл").

  GET  /api/people            -> {"codes": {lead_id: "2809"}, "changes": [...], "booking": {...}, "staff_pin": "482913"}
  POST /api/people/staff-pin  -> шинэ ажилтны код (хуучин нь хүчингүй)
  PUT  /api/people/events     {"events": [{"name", "at": "2026-10-18T10:00"}]} -> бүртгүүлсэн хүн бүрт өмнөх өдрийн
                              "ирэх үү" дуудлага автоматаар товлогдоно
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import people
import reminders
from deps import current_tenant
from tenant import Tenant

router = APIRouter(prefix="/api/people", tags=["people"])


@router.get("")
def overview(t: Tenant = Depends(current_tenant)):
    codes = people.ensure_all_codes(t.dir)      # хуучин/вэбээр үүссэн бүртгэлд ч код
    with reminders.data_lock:
        people.sync_event_reminders(t.dir)
    return {"codes": {str(k): v for k, v in codes.items()}, "changes": people.changes(t.dir),
            "booking": people.booking(t.dir), "staff_pin": people.staff_pin(t.dir), "events": people.events(t.dir)}


class EventsBody(BaseModel):
    events: list[dict]


@router.put("/events")
def put_events(body: EventsBody, t: Tenant = Depends(current_tenant)):
    if len(body.events) > 50:
        raise HTTPException(400, "Хамгийн ихдээ 50 эвент")
    try:
        items = [{"name": str(e.get("name", "")).strip(), "at": str(e.get("at", ""))} for e in body.events]
        if any(len(e["name"]) < 2 for e in items):
            raise ValueError
        people.set_events(t.dir, items)
    except (ValueError, KeyError):
        raise HTTPException(400, "Эвент бүр нэр, огноо цагтай (жишээ: 2026-10-18T10:00)") from None
    with reminders.data_lock:
        added = people.sync_event_reminders(t.dir)
    return {"events": people.events(t.dir), "scheduled": added}


@router.post("/staff-pin")
def regenerate_staff_pin(t: Tenant = Depends(current_tenant)):
    return {"staff_pin": people.new_staff_pin(t.dir)}
