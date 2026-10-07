"""
Хувийн RAG (people.py): бүртгэлийн код, утасны AI-ийн хийсэн өөрчлөлтүүд. Ажилтан гараар юу ч өөрчлөхгүй —
код бүртгэл үүсэхэд автоматаар, сул цаг ажлын цагаас (settings.json "booking"), өөрчлөлтийг залгагч өөрөө утсаар.

  GET /api/people   -> {"codes": {lead_id: "2809"}, "changes": [...], "booking": {...}}
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
            "booking": people.booking(t.dir)}
