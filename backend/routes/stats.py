"""
Самбарын статистик.

  GET /api/stats -> дуудлага, асуулт, хариулсан / хариулж чадаагүй, хариултын зам, дундаж хугацаа,
                    шинэ бүртгэл, сүүлийн 5 өдрийн дуудлага (Улаанбаатарын цагаар)
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends

import db
from deps import current_tenant
from tenant import Tenant

router = APIRouter(prefix="/api/stats", tags=["stats"])
TZ = ZoneInfo("Asia/Ulaanbaatar")
DAYS = 5


def local_date(ts: float) -> str:
    return datetime.fromtimestamp(ts, TZ).date().isoformat()


@router.get("")
def stats(t: Tenant = Depends(current_tenant)):
    today = datetime.now(TZ).date()
    since = datetime.combine(today - timedelta(days=DAYS - 1), datetime.min.time(), TZ).timestamp()
    with db.connect(t.db_path) as con:
        calls = con.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
        asked = con.execute("SELECT COUNT(*) FROM messages WHERE role='user'").fetchone()[0]
        routes = dict(con.execute(
            "SELECT COALESCE(route,'?'), COUNT(*) FROM messages "
            "WHERE role='assistant' AND COALESCE(route,'') != 'greeting' GROUP BY route").fetchall())
        lat = con.execute("SELECT AVG(latency), AVG(stt_sec) FROM messages").fetchone()
        new_leads = con.execute("SELECT COUNT(*) FROM leads WHERE status='new'").fetchone()[0]
        recent = [r[0] for r in con.execute("SELECT started_at FROM calls WHERE started_at >= ?", (since,))]
    routes = {r: n for r, n in routes.items() if not r.startswith("lead_")}   # бүртгэлийн алхам асуулт биш
    unanswered = sum(routes.get(r, 0) for r in db.UNANSWERED_ROUTES)
    per_day = {(today - timedelta(days=i)).isoformat(): 0 for i in range(DAYS - 1, -1, -1)}
    for ts in recent:
        day = local_date(ts)
        if day in per_day:
            per_day[day] += 1
    return {"calls": calls, "questions": asked, "answered": sum(routes.values()) - unanswered,
            "unanswered": unanswered, "routes": routes, "avg_latency": lat[0], "avg_stt": lat[1],
            "new_leads": new_leads, "days": [{"date": d, "calls": n} for d, n in per_day.items()]}
