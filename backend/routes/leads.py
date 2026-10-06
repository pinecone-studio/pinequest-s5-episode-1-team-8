"""
Бүртгэл: залгагч бүртгүүлэх эсвэл ажилтантай ярих хүсэлт өгсөн (утасны AI бичнэ).

  GET   /api/leads        -> бүх бүртгэл (шинэ нь эхэндээ)
  PATCH /api/leads/{id}   {"status"?, "notes"?} -> төлөв (new | contacted | done), тэмдэглэл
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import db
from deps import current_tenant
from tenant import Tenant

router = APIRouter(prefix="/api/leads", tags=["leads"])
STATUSES = ("new", "contacted", "done")


@router.get("")
def leads(t: Tenant = Depends(current_tenant)):
    with db.connect(t.db_path) as con:
        rows = con.execute("SELECT * FROM leads ORDER BY created_at DESC, id DESC").fetchall()
    return [dict(r) for r in rows]


class LeadUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None


@router.patch("/{lead_id}")
def update_lead(lead_id: int, body: LeadUpdate, t: Tenant = Depends(current_tenant)):
    if body.status is not None and body.status not in STATUSES:
        raise HTTPException(400, "Төлөв: new | contacted | done")
    if body.notes is not None and len(body.notes) > 1000:
        raise HTTPException(400, "Тэмдэглэл 1000 тэмдэгтээс хэтрэхгүй")
    with db.connect(t.db_path) as con:
        if not con.execute("SELECT 1 FROM leads WHERE id=?", (lead_id,)).fetchone():
            raise HTTPException(404, "Бүртгэл олдсонгүй")
        if body.status is not None:
            con.execute("UPDATE leads SET status=? WHERE id=?", (body.status, lead_id))
        if body.notes is not None:
            con.execute("UPDATE leads SET notes=? WHERE id=?", (body.notes.strip(), lead_id))
        row = con.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    return dict(row)
