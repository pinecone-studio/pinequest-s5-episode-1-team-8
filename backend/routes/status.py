"""
AI ресепшний төлөв (sidebar, самбар, Тохируулах). Вэб 10 секунд тутам асууна.

  GET /api/status -> AI сервер / SIP асаалттай эсэх, мэдээлэл бэлдсэн эсэх, бэлдэлт явагдаж байгаа эсэх,
                     sidebar-ын тоо (шинэ бүртгэл, хариулж чадаагүй), автомат шалгалтын үр дүн

AI сервер (AudioSocket) AI_PORT=9092, SIP SIP_PORT=5060 (UDP) — SIM-TRUNK-тэй ижил.
"""
import json
import os
import socket

from fastapi import APIRouter, Depends

import db
import knowledge_jobs
from deps import current_tenant
from tenant import Tenant

router = APIRouter(prefix="/api/status", tags=["status"])
DOC_EXT = (".md", ".txt", ".pdf", ".docx")


def port_open(port: int, udp: bool = False) -> bool:
    if udp:  # UDP-д "холбогдох" боломжгүй -> bind хийж үзнэ (амжилтгүй = өөр процесс эзэлсэн)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind(("0.0.0.0", port))
            return False
        except OSError:
            return True
        finally:
            s.close()
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def load_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


@router.get("")
def status(t: Tenant = Depends(current_tenant)):
    # Бэлдэлтийн үр дүн (SIM-TRUNK-ийн ingest, build_faq_audio, train_selector бичнэ)
    facts = load_json(t.path("knowledge_index", "facts.json")).get("facts", [])
    faq = load_json(t.path("faq_audio", "faq_index.json")).get("faq", [])
    selector = load_json(t.path("knowledge_index", "selector.json"))
    docs = [n for n in os.listdir(t.knowledge_dir) if n.lower().endswith(DOC_EXT)] \
        if os.path.isdir(t.knowledge_dir) else []
    placeholders = ",".join("?" * len(db.UNANSWERED_ROUTES))
    with db.connect(t.db_path) as con:
        new_leads = con.execute("SELECT COUNT(*) FROM leads WHERE status='new'").fetchone()[0]
        unanswered = con.execute(f"SELECT COUNT(*) FROM messages WHERE role='assistant' AND route IN ({placeholders})",
                                 db.UNANSWERED_ROUTES).fetchone()[0]
    return {
        "ai_server": port_open(int(os.getenv("AI_PORT", "9092"))),
        "sip": port_open(int(os.getenv("SIP_PORT", "5060")), udp=True),
        "documents": len(docs), "facts": len(facts), "faq": len(faq), "ready": bool(facts) and bool(faq),
        "build_running": knowledge_jobs.status(t)["running"],
        "selector": {"enabled": selector.get("enabled"), "eval": selector.get("eval")} if selector else None,
        "new_leads": new_leads, "unanswered": unanswered,
    }
