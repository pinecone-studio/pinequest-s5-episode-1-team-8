"""
Нэг өгөгдлийн сан (rag_store.py): байгууллагын RAG + хувийн RAG + дуудлага, бүртгэл — receptionist.db.

  GET /api/rag   -> {"facts", "faq_questions", "chunks", "person_docs", "people", "calls", "messages", "leads",
                     "changes", "embed_model", "dim", "built_at", "db_bytes"}
"""
import os

from fastapi import APIRouter, Depends

import rag_store
from deps import current_tenant
from tenant import Tenant

router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.get("")
def rag_stats(t: Tenant = Depends(current_tenant)):
    st = rag_store.stats(t.dir)
    built = [os.path.join(t.dir, "knowledge_index", "facts.json"), os.path.join(t.dir, "faq_audio", "faq_index.json")]
    newest = max((os.path.getmtime(p) for p in built if os.path.exists(p)), default=0)
    if newest and newest > (st["built_at"] or 0):       # индекс DB-ээс шинэ (өмнө нь бэлдсэн) -> нэг удаа бичнэ
        st = rag_store.sync(t.dir)
    return st
