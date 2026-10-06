"""
Хариулж чадаагүй асуултууд: AI дахин асуусан, тодруулсан эсвэл ажилтанд шилжүүлсэн.

  GET /api/unanswered?limit=200 -> залгагчийн асуулт + AI-ийн хариултын зам (шинэ нь эхэндээ)
"""
from fastapi import APIRouter, Depends, Query

import db
from deps import current_tenant
from tenant import Tenant

router = APIRouter(prefix="/api/unanswered", tags=["unanswered"])


@router.get("")
def unanswered(limit: int = Query(200, ge=1, le=1000), t: Tenant = Depends(current_tenant)):
    placeholders = ",".join("?" * len(db.UNANSWERED_ROUTES))
    with db.connect(t.db_path) as con:
        rows = con.execute(f"""
            SELECT u.id, u.call_uuid, u.ts, u.text AS question, a.route, a.score
            FROM messages a JOIN messages u ON u.id = (
                SELECT MAX(id) FROM messages WHERE call_uuid=a.call_uuid AND role='user' AND id < a.id)
            WHERE a.role='assistant' AND a.route IN ({placeholders})
            ORDER BY a.ts DESC LIMIT ?""", (*db.UNANSWERED_ROUTES, limit)).fetchall()
    return [dict(r) for r in rows]
