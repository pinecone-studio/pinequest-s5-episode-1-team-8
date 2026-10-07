"""
Нэмэлт (SIM-TRUNK-д алга): долоо хоногийн тайлан (report.py).

  GET  /api/report?days=7          -> тайлан (тоо, их асуусан сэдэв, хариулж чадаагүй ...) + Telegram-ийн бичвэр
  POST /api/report/send            -> одоо Telegram руу илгээх
  PUT  /api/report/settings        {"enabled"} -> Даваа бүр 09:00-д автоматаар (анхдагч: асаалттай)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

import notify
import report
from deps import current_tenant
from tenant import Tenant

router = APIRouter(prefix="/api/report", tags=["report"])


@router.get("")
def get_report(days: int = Query(7, ge=1, le=90), t: Tenant = Depends(current_tenant)):
    r = report.build(t, days)
    st = notify.load_settings(t)
    return {**r, "text": report.text(t, r), "enabled": report.enabled(t),
            "telegram": bool(st.get("telegram_token") and st.get("telegram_chat_id")),
            "last_sent": st.get("weekly_report_sent")}


@router.post("/send")
def send_now(t: Tenant = Depends(current_tenant)):
    st = notify.load_settings(t)
    if not (st.get("telegram_token") and st.get("telegram_chat_id")):
        raise HTTPException(400, "Эхлээд Telegram мэдэгдлийг тохируулна уу")
    if not report.send(t):
        raise HTTPException(502, "Telegram руу илгээж чадсангүй")
    return {"ok": True}


class ReportSettings(BaseModel):
    enabled: bool


@router.put("/settings")
def put_settings(body: ReportSettings, t: Tenant = Depends(current_tenant)):
    st = notify.load_settings(t)
    st["weekly_report"] = body.enabled
    notify.save_settings(t, st)
    return {"ok": True, "enabled": body.enabled}
