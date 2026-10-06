"""Байгууллагын RAG мэдээллийн файлууд: жагсаах, унших, засах, оруулах, устгах."""
import os
import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from deps import current_tenant
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
    return {"files": files}


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
