"""
Бүртгэл: залгагч бүртгүүлэх эсвэл ажилтантай ярих хүсэлт өгсөн (утасны AI бичнэ).

  GET   /api/leads        -> бүх бүртгэл (шинэ нь эхэндээ)
  PATCH /api/leads/{id}   {"status"?, "notes"?, "name"?} -> төлөв (new | contacted | done), тэмдэглэл, нэр
                          (нэрийг засвал байгууллагын нэрсийн толинд нэмж, AI дараагийн удаа зөв таньна)
"""
import os
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import db
from deps import current_tenant
from tenant import Tenant

router = APIRouter(prefix="/api/leads", tags=["leads"])
STATUSES = ("new", "contacted", "done", "canceled")


@router.get("")
def leads(t: Tenant = Depends(current_tenant)):
    with db.connect(t.db_path) as con:
        rows = con.execute("SELECT * FROM leads ORDER BY created_at DESC, id DESC").fetchall()
    return [dict(r) for r in rows]


class LeadUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None
    name: str | None = None


def learn_name(t: Tenant, name: str):
    """Засварласан нэрийг tenants/<slug>/names.txt-д нэмнэ -> утасны AI (names.py) дуудлагын дараа
    STT-ийн бичсэн нэрийг энэ жагсаалтаас хамгийн ойрыг нь сонгож засна."""
    path = os.path.join(t.dir, "names.txt")
    existing = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            existing = {line.strip().lower() for line in f}
    new = [w for w in re.findall(r"[А-ЯӨҮЁа-яөүё-]{2,}", name) if w.lower() not in existing]
    if new:
        with open(path, "a", encoding="utf-8") as f:
            f.write("".join(f"{w}\n" for w in new))


@router.patch("/{lead_id}")
def update_lead(lead_id: int, body: LeadUpdate, t: Tenant = Depends(current_tenant)):
    if body.status is not None and body.status not in STATUSES:
        raise HTTPException(400, "Төлөв: new | contacted | done | canceled")
    if body.notes is not None and len(body.notes) > 1000:
        raise HTTPException(400, "Тэмдэглэл 1000 тэмдэгтээс хэтрэхгүй")
    name = " ".join((body.name or "").split())
    if body.name is not None and not 1 <= len(name) <= 80:
        raise HTTPException(400, "Нэр 1-80 тэмдэгт байна")
    with db.connect(t.db_path) as con:
        if not con.execute("SELECT 1 FROM leads WHERE id=?", (lead_id,)).fetchone():
            raise HTTPException(404, "Бүртгэл олдсонгүй")
        if body.status is not None:
            con.execute("UPDATE leads SET status=? WHERE id=?", (body.status, lead_id))
        if body.notes is not None:
            con.execute("UPDATE leads SET notes=? WHERE id=?", (body.notes.strip(), lead_id))
        if body.name is not None:
            con.execute("UPDATE leads SET name=? WHERE id=?", (name, lead_id))
        row = con.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    if body.name is not None:
        learn_name(t, name)
    return dict(row)
