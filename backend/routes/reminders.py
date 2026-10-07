"""
Нэмэлт (SIM-TRUNK-д алга): AI-аас гарах сануулгын дуудлага (reminders.py).

  GET    /api/reminders                     -> сануулгууд (бүртгэлээр), мессежийн загвар, залгагч бэлэн эсэх
  PUT    /api/reminders/{lead_id}           {"appointment": "2026-10-15T10:00", "call": "now" | "day_before" | "2026-10-14T11:00"}
  POST   /api/reminders/{lead_id}/call      -> одоо залгах (дараалалд)
  DELETE /api/reminders/{lead_id}           -> цуцлах
  PUT    /api/reminders/template            {"template"} -> {name} {org} {date} {time}
  GET    /api/admin/outbound                -> залгах тохиргоо (admin; нууц үг харуулахгүй)
  PUT    /api/admin/outbound                {"mode": "off" | "sip" | "mac", "host", "port", "user", "password", "prefix"}
  POST   /api/admin/outbound/check          -> gateway/SIP trunk хариулж байгаа эсэх
"""
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import notify
import reminders
from deps import current_tenant
from outbound import dialer
from routes.admin import require_admin
from tenant import Tenant

router = APIRouter(prefix="/api/reminders", tags=["reminders"])
admin_router = APIRouter(prefix="/api/admin/outbound", tags=["outbound"], dependencies=[Depends(require_admin)])


@router.get("")
def list_reminders(t: Tenant = Depends(current_tenant)):
    cfg = dialer.load()
    items = reminders.load(t)["items"]
    for key, item in items.items():          # утасны AI сольсон цаг (people.py) -> текстийг загвараар
        if not item.get("text") and item.get("appointment"):
            item["text"] = reminders.item_text(t, reminders.lead_of(t, int(key)) or {}, item)
    return {"items": items, "template": reminders.template(t),
            "default_template": reminders.DEFAULT_TEMPLATE, "dialer": {"mode": cfg["mode"]},
            "hours": list(reminders.HOURS)}


class TemplateBody(BaseModel):
    template: str


@router.put("/template")
def put_template(body: TemplateBody, t: Tenant = Depends(current_tenant)):
    tpl = " ".join(body.template.split())[:600]
    try:
        preview = reminders.render(t, {"name": "Болд"}, "2026-10-15T10:00", tpl or None)
    except (KeyError, IndexError, ValueError):
        raise HTTPException(400, "Зөвхөн {name} {org} {date} {time} ашиглана") from None
    st = notify.load_settings(t)
    st["reminder_template"] = tpl if tpl and tpl != reminders.DEFAULT_TEMPLATE else None
    notify.save_settings(t, st)
    return {"ok": True, "template": reminders.template(t), "preview": preview}


class ReminderBody(BaseModel):
    appointment: str
    call: str = "day_before"


def call_time(appointment: datetime, call: str) -> float:
    now = datetime.now(reminders.TZ)
    if call == "now":
        return time.time()
    if call == "day_before":           # өмнөх өдрийн 11:00, өнгөрсөн бол одоо
        at = (appointment - timedelta(days=1)).replace(hour=11, minute=0)
        return max(at, now).timestamp()
    return reminders.parse_local(call).timestamp()


@router.put("/{lead_id}")
def schedule(lead_id: int, body: ReminderBody, t: Tenant = Depends(current_tenant)):
    lead = reminders.lead_of(t, lead_id)
    if not lead:
        raise HTTPException(404, "Бүртгэл олдсонгүй")
    if not reminders.number_of(lead):
        raise HTTPException(400, "Энэ бүртгэлд утасны дугаар алга")
    try:
        when = reminders.parse_local(body.appointment)
        call_at = call_time(when, body.call)
    except ValueError:
        raise HTTPException(400, "Огноо буруу (жишээ: 2026-10-15T10:00)") from None
    if when < datetime.now(reminders.TZ):
        raise HTTPException(400, "Уулзалтын цаг өнгөрсөн байна")
    text = reminders.render(t, lead, body.appointment)
    with reminders.data_lock:
        data = reminders.load(t)
        old = data["items"].get(str(lead_id), {})
        if old.get("status") == "calling":
            raise HTTPException(409, "Яг одоо залгаж байна")
        data["items"][str(lead_id)] = {"lead_id": lead_id, "appointment": body.appointment[:16], "call_at": call_at,
                                       "status": "scheduled", "attempts": 0, "text": text, "history": old.get("history", []),
                                       "created_at": int(time.time())}
        reminders.save(t, data)
    if body.call == "now":
        reminders.wake()
    return {**data["items"][str(lead_id)], "new_chars": reminders.new_chars(t, text)}


@router.post("/{lead_id}/call")
def call_now(lead_id: int, t: Tenant = Depends(current_tenant)):
    with reminders.data_lock:
        data = reminders.load(t)
        item = data["items"].get(str(lead_id))
        if not item:
            raise HTTPException(404, "Сануулга олдсонгүй")
        if item.get("status") == "calling":
            raise HTTPException(409, "Яг одоо залгаж байна")
        item.update(status="scheduled", call_at=time.time(), attempts=0)
        reminders.save(t, data)
    reminders.wake()
    return item


@router.delete("/{lead_id}")
def cancel(lead_id: int, t: Tenant = Depends(current_tenant)):
    with reminders.data_lock:
        data = reminders.load(t)
        item = data["items"].get(str(lead_id))
        if not item:
            raise HTTPException(404, "Сануулга олдсонгүй")
        if item.get("status") == "calling":
            raise HTTPException(409, "Яг одоо залгаж байна")
        del data["items"][str(lead_id)]
        reminders.save(t, data)
    return {"ok": True}


# ---------------- admin: залгах тохиргоо ----------------

@admin_router.get("")
def get_outbound():
    cfg = dialer.load()
    return {**{k: v for k, v in cfg.items() if k != "password"}, "password_set": bool(cfg.get("password"))}


class OutboundBody(BaseModel):
    mode: str
    host: str = ""
    port: int = 5060
    user: str = "ai"
    password: str | None = None         # None/хоосон бол хуучнаараа
    prefix: str = ""
    local_ip: str = ""
    ring_timeout: float = 40


@admin_router.put("")
def put_outbound(body: OutboundBody):
    if body.mode not in dialer.MODES:
        raise HTTPException(400, "mode: off | sip | mac")
    if body.mode == "sip" and not body.host.strip():
        raise HTTPException(400, "GSM gateway / SIP trunk-ийн хаяг оруулна уу")
    old = dialer.load()
    cfg = {**body.model_dump(exclude={"password"}), "host": body.host.strip(), "prefix": body.prefix.strip(),
           "password": body.password if body.password else old.get("password", "")}
    dialer.save(cfg)
    return get_outbound()


@admin_router.post("/check")
def check_outbound():
    ok, detail = dialer.ready()
    return {"ready": ok, "detail": detail}
