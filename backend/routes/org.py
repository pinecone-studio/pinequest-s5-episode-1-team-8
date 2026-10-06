"""
Байгууллагын мэдээлэл (вэб -> Тохируулах).

  GET /api/org   -> нэр, утас, и-мэйл, хаяг, цагийн хуваарь, дотуур дугаар, эрх, хэрэглэгчид, файлын тоо
  PUT /api/org   -> хадгална; мэндчилгээ, утас/хаяг/цагийн загвар FAQ дахин үүснэ (гараар зассан FAQ хэвээр)
"""
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import accounts
import tenant as tenants
from deps import current_tenant
from tenant import Tenant

router = APIRouter(prefix="/api/org", tags=["org"])
FIELDS = ("name", "phone", "email", "address", "hours")
DOC_EXT = (".md", ".txt", ".pdf", ".docx")


def org_info(t: Tenant) -> dict:
    cfg = t.config()
    docs = [n for n in os.listdir(t.knowledge_dir) if n.lower().endswith(DOC_EXT)] \
        if os.path.isdir(t.knowledge_dir) else []
    return {**{k: cfg.get(k, "") for k in FIELDS}, "slug": t.slug, "extension": cfg.get("extension"),
            "plan": cfg.get("plan", "trial"), "documents": len(docs), "users": accounts.users_of(t.slug)}


@router.get("")
def get_org(t: Tenant = Depends(current_tenant)):
    return org_info(t)


class OrgBody(BaseModel):
    name: str
    phone: str = ""
    email: str = ""
    address: str = ""
    hours: str = ""


@router.put("")
def put_org(body: OrgBody, t: Tenant = Depends(current_tenant)):
    name = " ".join(body.name.split())
    if not 2 <= len(name) <= 80:
        raise HTTPException(400, "Байгууллагын нэр 2-80 тэмдэгт")
    phone = tenants.clean_phone(body.phone)
    if phone and not 6 <= len(phone.lstrip("+")) <= 12:
        raise HTTPException(400, "Утасны дугаар буруу")
    email = body.email.strip()
    if email and not accounts.EMAIL.fullmatch(email):
        raise HTTPException(400, "И-мэйл хаяг буруу")
    cfg = t.config()
    cfg.update(name=name, phone=phone, email=email[:120], address=body.address.strip()[:300],
               hours=body.hours.strip()[:200])
    t.save_config({k: v for k, v in cfg.items() if v != ""})
    tenants.refresh_faq(t)
    return org_info(t)
