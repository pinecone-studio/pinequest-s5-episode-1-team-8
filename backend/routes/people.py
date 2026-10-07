"""
Хувийн RAG (people.py): бүртгэлийн код, утасны AI-ийн хийсэн өөрчлөлтүүд. Ажилтан өгөгдлийн сан руу гараар орохгүй —
код бүртгэл үүсэхэд автоматаар, сул цаг ажлын цагаас (settings.json "booking"), өөрчлөлтийг утсаар:
залгагч өөрийн кодоор, ажилтан (багш) ажилтны кодоор бусдын бүртгэлийг ("Болдын цагийг Баасан руу шилжүүл").

  GET  /api/people            -> {"codes": {lead_id: "2809"}, "changes": [...], "booking": {...}, "staff_pin": "482913"}
  POST /api/people/staff-pin  -> шинэ ажилтны код (хуучин нь хүчингүй)
"""
from fastapi import APIRouter, Depends

import people
from deps import current_tenant
from tenant import Tenant

router = APIRouter(prefix="/api/people", tags=["people"])


@router.get("")
def overview(t: Tenant = Depends(current_tenant)):
    codes = people.ensure_all_codes(t.dir)      # хуучин/вэбээр үүссэн бүртгэлд ч код
    return {"codes": {str(k): v for k, v in codes.items()}, "changes": people.changes(t.dir),
            "booking": people.booking(t.dir), "staff_pin": people.staff_pin(t.dir)}


@router.post("/staff-pin")
def regenerate_staff_pin(t: Tenant = Depends(current_tenant)):
    return {"staff_pin": people.new_staff_pin(t.dir)}
