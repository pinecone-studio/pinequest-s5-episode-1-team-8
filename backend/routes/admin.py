"""
Платформын admin: бүх байгууллага (вэб -> Байгууллагууд). Зөвхөн role=admin, бусдад 403.

  GET  /api/admin/tenants               -> бүх байгууллага: нэр, дугаар, эрх, хэрэглэгчид, дуудлагын тоо, бэлэн эсэх
  POST /api/admin/tenants {...}         -> шинэ байгууллага + эзэмшигч (төлбөр төлсөн хүн) хэрэглэгч
  POST /api/admin/switch {"slug"}       -> тэр байгууллагыг харах (cookie; app.viewed_tenant)
  DELETE /api/admin/switch              -> өөрийн байгууллага руу буцах
  POST /api/admin/plan {"slug", "plan"} -> trial -> active (төлбөр төлсөн) -> suspended. Төлбөрийн систем алга: гараар.
"""
import os
import shutil

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import accounts
import auth
import db
import knowledge_jobs
import tenant as tenants
from deps import current_user


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(403, "Зөвхөн платформын admin")
    return user


router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def find(slug: str) -> tenants.Tenant:
    try:
        t = tenants.Tenant(slug)
    except ValueError:
        t = None
    if not t or not t.exists():
        raise HTTPException(404, "Байгууллага олдсонгүй")
    return t


@router.get("/tenants")
def list_tenants():
    out = []
    for t in tenants.all_tenants():
        cfg = t.config()
        calls = 0
        if os.path.exists(t.db_path):
            with db.connect(t.db_path) as con:
                calls = con.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
        ready = os.path.exists(os.path.join(t.faq_index_dir, "faq_index.json"))   # SIM-TRUNK admin_tenants-тэй ижил
        out.append({"slug": t.slug, "name": cfg.get("name"), "address": cfg.get("address"),
                    "email": cfg.get("email"),
                    "extension": cfg.get("extension"),
                    "plan": cfg.get("plan", "trial"), "created_at": cfg.get("created_at"), "calls": calls,
                    "ready": ready, "users": [u["email"] for u in accounts.users_of(t.slug)],
                    "job": (knowledge_jobs.JOBS.get(t.slug) or {}).get("state", "idle")})
    return out          # SIM-TRUNK шиг хавтасны нэрийн дарааллаар (tenant.all_tenants)


class NewTenantBody(BaseModel):
    name: str = ""
    phone: str = ""
    email: str = ""        # байгууллагын албан и-мэйл
    address: str = ""
    hours: str = ""
    owner_email: str = ""  # нэвтрэх хэрэглэгч
    password: str = ""


@router.post("/tenants")
def create_tenant(body: NewTenantBody):
    owner = accounts.normalize_email(body.owner_email)
    if not accounts.EMAIL.fullmatch(owner):
        raise HTTPException(400, "Эзэмшигчийн и-мэйл буруу")
    if len(body.password) < 8:
        raise HTTPException(400, "Нууц үг 8-аас дээш тэмдэгт байх ёстой")
    email = body.email.strip()
    if email and not accounts.EMAIL.fullmatch(email):
        raise HTTPException(400, "Байгууллагын и-мэйл буруу")
    phone = tenants.clean_phone(body.phone)
    if phone and not 6 <= len(phone.lstrip("+")) <= 12:
        raise HTTPException(400, "Утасны дугаар буруу")
    try:
        with tenants.LOCK:
            t = tenants.create(body.name, phone=phone, email=email, address=body.address[:300], hours=body.hours[:200])
            try:
                accounts.create_user(owner, body.password, t.slug)
            except ValueError:
                shutil.rmtree(t.dir, ignore_errors=True)
                raise
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return {"ok": True, "slug": t.slug}


class SwitchBody(BaseModel):
    slug: str


@router.post("/switch")
def switch(request: Request, body: SwitchBody):
    t = find(body.slug)
    response = JSONResponse({"ok": True, "slug": t.slug, "name": t.config().get("name", t.slug)})
    secure = request.headers.get("x-forwarded-proto") == "https" or request.url.scheme == "https"
    response.set_cookie(auth.TENANT_COOKIE, t.slug, max_age=accounts.SESSION_DAYS * 86400,
                        httponly=True, samesite="lax", secure=secure)
    return response


@router.delete("/switch")
def switch_back():
    response = JSONResponse({"ok": True})
    response.delete_cookie(auth.TENANT_COOKIE)
    return response


class PlanBody(BaseModel):
    slug: str
    plan: str


@router.post("/plan")
def set_plan(body: PlanBody):
    if body.plan not in tenants.PLANS:
        raise HTTPException(400, "plan: trial | active | suspended")
    t = find(body.slug)
    cfg = t.config()
    cfg["plan"] = body.plan
    t.save_config(cfg)
    return {"ok": True}
