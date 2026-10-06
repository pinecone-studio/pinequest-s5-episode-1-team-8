"""
Яриа (дуудлагын түүх).

  GET /api/calls?limit=100   -> сүүлийн дуудлагууд (асуултын тоо, хариулж чадаагүй тоотой)
      &q=99112233|зогсоол  -> залгагчийн дугаар эсвэл ярианы үгээр хайна
      &unanswered=true     -> зөвхөн хариулж чадаагүй асуулттай
      &days=7              -> сүүлийн N хоног (1 = өнөөдрөөс хойш 24 цаг)
  GET /api/calls/{uuid}      -> нэг дуудлагын бүх яриа
"""
import time

from fastapi import APIRouter, Depends, HTTPException, Query

import db
from deps import current_tenant
from tenant import Tenant

router = APIRouter(prefix="/api/calls", tags=["calls"])


def like(text: str) -> str:
    """LIKE хайлтын тусгай тэмдэгтийг (% _) жинхэнэ утгаар нь"""
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


@router.get("")
def calls(limit: int = Query(100, ge=1, le=1000), q: str = Query("", max_length=100),
          unanswered: bool = False, days: int | None = Query(None, ge=1, le=365),
          t: Tenant = Depends(current_tenant)):
    placeholders = ",".join("?" * len(db.UNANSWERED_ROUTES))
    where, params = [], []
    if q.strip():
        # SQLite-ийн LIKE кирилл үсгийн том/жижгийг ялгадаг -> Python-ийн lower() (ulower)
        where.append("(c.caller LIKE ? ESCAPE '\\' OR EXISTS (SELECT 1 FROM messages m "
                     "WHERE m.call_uuid=c.uuid AND ulower(m.text) LIKE ? ESCAPE '\\'))")
        params += [like(q.strip().lower())] * 2
    if days:
        where.append("c.started_at >= ?")
        params.append(time.time() - days * 86400)
    sql = f"""
        SELECT * FROM (
          SELECT c.*,
            (SELECT COUNT(*) FROM messages m WHERE m.call_uuid=c.uuid AND m.role='user') AS questions,
            (SELECT COUNT(*) FROM messages m WHERE m.call_uuid=c.uuid AND m.role='assistant'
               AND m.route IN ({placeholders})) AS unanswered
          FROM calls c {"WHERE " + " AND ".join(where) if where else ""})
        {"WHERE unanswered > 0" if unanswered else ""}
        ORDER BY started_at DESC LIMIT ?"""
    with db.connect(t.db_path) as con:
        con.create_function("ulower", 1, lambda s: s.lower() if isinstance(s, str) else s, deterministic=True)
        rows = con.execute(sql, (*db.UNANSWERED_ROUTES, *params, limit)).fetchall()
    return [dict(r) for r in rows]


@router.get("/{uuid}")
def call_detail(uuid: str, t: Tenant = Depends(current_tenant)):
    with db.connect(t.db_path) as con:
        call = con.execute("SELECT * FROM calls WHERE uuid=?", (uuid,)).fetchone()
        msgs = con.execute("SELECT * FROM messages WHERE call_uuid=? ORDER BY ts, id", (uuid,)).fetchall()
    if not call:
        raise HTTPException(404, "Дуудлага олдсонгүй")
    return {"call": dict(call), "messages": [dict(m) for m in msgs]}
