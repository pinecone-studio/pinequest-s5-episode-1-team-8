"""
Яриа (дуудлагын түүх).

  GET /api/calls?limit=100   -> сүүлийн дуудлагууд (асуултын тоо, хариулж чадаагүй тоотой)
  GET /api/calls/{uuid}      -> нэг дуудлагын бүх яриа
"""
from fastapi import APIRouter, Depends, HTTPException, Query

import db
from deps import current_tenant
from tenant import Tenant

router = APIRouter(prefix="/api/calls", tags=["calls"])


@router.get("")
def calls(limit: int = Query(100, ge=1, le=1000), t: Tenant = Depends(current_tenant)):
    placeholders = ",".join("?" * len(db.UNANSWERED_ROUTES))
    with db.connect(t.db_path) as con:
        rows = con.execute(f"""
            SELECT c.*,
              (SELECT COUNT(*) FROM messages m WHERE m.call_uuid=c.uuid AND m.role='user') AS questions,
              (SELECT COUNT(*) FROM messages m WHERE m.call_uuid=c.uuid AND m.role='assistant'
                 AND m.route IN ({placeholders})) AS unanswered
            FROM calls c ORDER BY c.started_at DESC LIMIT ?""", (*db.UNANSWERED_ROUTES, limit)).fetchall()
    return [dict(r) for r in rows]


@router.get("/{uuid}")
def call_detail(uuid: str, t: Tenant = Depends(current_tenant)):
    with db.connect(t.db_path) as con:
        call = con.execute("SELECT * FROM calls WHERE uuid=?", (uuid,)).fetchone()
        msgs = con.execute("SELECT * FROM messages WHERE call_uuid=? ORDER BY ts, id", (uuid,)).fetchall()
    if not call:
        raise HTTPException(404, "Дуудлага олдсонгүй")
    return {"call": dict(call), "messages": [dict(m) for m in msgs]}
