"""Байгууллагын RAG мэдээлэл, бэлдсэн өгүүлбэр/аудио болон SIM-TRUNK build job."""
import json
import hashlib
import os
import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from deps import current_tenant
import knowledge_jobs
from config import DATA_DIR, TENANTS_DIR
from tenant import Tenant

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
DOC_EXT = (".md", ".txt", ".pdf", ".docx")
TEXT_EXT = (".md", ".txt")
MAX_FILE = 20 * 1024 * 1024


def safe_name(name: str) -> str:
    name = os.path.basename(name.strip())
    if not name or not re.fullmatch(r"[^/\\\0]{1,160}", name) or not name.lower().endswith(DOC_EXT):
        raise HTTPException(400, "Файлын нэр эсвэл төрөл буруу (.md, .txt, .pdf, .docx)")
    return name


@router.get("")
def list_files(t: Tenant = Depends(current_tenant)):
    os.makedirs(t.knowledge_dir, exist_ok=True)
    files = []
    for name in sorted(os.listdir(t.knowledge_dir)):
        path = os.path.join(t.knowledge_dir, name)
        if os.path.isfile(path) and name.lower().endswith(DOC_EXT):
            st = os.stat(path)
            files.append({"name": name, "size": st.st_size, "mtime": st.st_mtime,
                          "editable": name.lower().endswith(TEXT_EXT)})
    facts_path = t.path("knowledge_index", "facts.json")
    try:
        with open(facts_path, encoding="utf-8") as f:
            indexed = json.load(f)
    except (OSError, ValueError):
        indexed = {}
    facts = []
    recordings = os.path.realpath(t.path("recordings"))
    for fact in indexed.get("facts", []):
        text = fact.get("text", "")
        audio = fact.get("audio")
        facts.append({"text": text, "source": fact.get("source"),
                      "hash": hashlib.sha1(text.encode()).hexdigest()[:12],
                      "has_audio": bool(audio and os.path.isfile(audio)),
                      "recorded": bool(audio and os.path.realpath(audio).startswith(recordings + os.sep))})
    return {"files": files, "facts": facts, "indexed_at": indexed.get("indexed_at")}


@router.get("/file/{name}")
def read_file(name: str, t: Tenant = Depends(current_tenant)):
    name = safe_name(name)
    if not name.lower().endswith(TEXT_EXT):
        raise HTTPException(400, "PDF/DOCX файлыг веб дээр засах боломжгүй")
    path = os.path.join(t.knowledge_dir, name)
    if not os.path.isfile(path):
        raise HTTPException(404, "Файл олдсонгүй")
    with open(path, encoding="utf-8") as f:
        return {"name": name, "content": f.read()}


class DocumentBody(BaseModel):
    content: str = ""


@router.put("/file/{name}")
def write_file(name: str, body: DocumentBody, t: Tenant = Depends(current_tenant)):
    name = safe_name(name)
    if not name.lower().endswith(TEXT_EXT):
        raise HTTPException(400, "Зөвхөн .md, .txt файл засна")
    data = body.content.encode("utf-8")
    if len(data) > MAX_FILE:
        raise HTTPException(413, "20MB-аас том файл")
    os.makedirs(t.knowledge_dir, exist_ok=True)
    path = os.path.join(t.knowledge_dir, name)
    with open(path + ".tmp", "wb") as f:
        f.write(data)
    os.replace(path + ".tmp", path)
    return {"ok": True, "name": name}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), t: Tenant = Depends(current_tenant)):
    name = safe_name(file.filename or "")
    data = await file.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise HTTPException(413, "20MB-аас том файл")
    os.makedirs(t.knowledge_dir, exist_ok=True)
    with open(os.path.join(t.knowledge_dir, name), "wb") as f:
        f.write(data)
    return {"ok": True, "name": name}


@router.delete("/file/{name}")
def delete_file(name: str, t: Tenant = Depends(current_tenant)):
    path = os.path.join(t.knowledge_dir, safe_name(name))
    if not os.path.isfile(path):
        raise HTTPException(404, "Файл олдсонгүй")
    os.remove(path)
    return {"ok": True}


@router.post("/build")
def start_build(t: Tenant = Depends(current_tenant)):
    try:
        return knowledge_jobs.enqueue(t)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/build")
def build_status(t: Tenant = Depends(current_tenant)):
    return knowledge_jobs.status(t)


@router.get("/audio/{fact_hash}")
def fact_audio(fact_hash: str, t: Tenant = Depends(current_tenant)):
    if not re.fullmatch(r"[0-9a-f]{12}", fact_hash):
        raise HTTPException(400, "Буруу hash")
    path = t.path("knowledge_index", "facts.json")
    try:
        with open(path, encoding="utf-8") as f:
            facts = json.load(f).get("facts", [])
    except (OSError, ValueError):
        facts = []
    audio = next((row.get("audio") for row in facts
                  if hashlib.sha1(row.get("text", "").encode()).hexdigest()[:12] == fact_hash), None)
    # Манай өгөгдөл (хүний бичлэг) эсвэл SIM-TRUNK-ийн нийтлэг TTS кэш доторх файл л
    allowed = [os.path.realpath(DATA_DIR), os.path.realpath(TENANTS_DIR), os.path.realpath(knowledge_jobs.tts_cache())]
    real = os.path.realpath(audio) if audio else ""
    if not audio or not os.path.isfile(audio) or not any(real.startswith(root + os.sep) for root in allowed):
        raise HTTPException(404, "Аудио олдсонгүй")
    return FileResponse(audio, media_type="audio/wav")
