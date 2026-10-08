"""
Өгөгдлийн сан (вэбээс харах): байгууллагын receptionist.db (SQLite) — хүснэгт бүр, мөр бүр. Зөвхөн УНШИНА:
өөрчлөлтийг AI туслах, сануулгын дуудлага хийнэ (people.py), хэн ч гараар засахгүй.

  GET /api/database                    -> {"file", "bytes", "tables": [{"name", "rows", "columns", "about"}]}
  GET /api/database/{table}?q=&offset= -> {"columns", "rows", "total"} — вектор (BLOB) -> {"dims", "preview"}

Ил тод байдал (компани өөрийн өгөгдөл хаана, юу, хэрхэн хадгалагдаж байгааг мэдэх):
  GET    /api/database/info                 -> юу хадгалагддаг, гадагш юу явдаг, хэн хардаг, нөөцлөлт
  GET    /api/database/export?format=csv|db -> бүх өгөгдлийг татах (CSV zip — Excel-д нээгдэнэ, эсвэл SQLite файл)
  DELETE /api/database/person/{lead_id}     -> тэр хүний бүх мэдээллийг устгах ("мартагдах эрх")
"""
import csv
import io
import json
import os
import sqlite3
import tempfile
import time
import zipfile

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

import backup
import db
import people
import rag_store
import reminders
from deps import current_tenant
from tenant import Tenant

router = APIRouter(prefix="/api/database", tags=["database"])
PAGE = 50
ABOUT = {
    "leads": "Бүртгэл: нэр, утас, хөтөлбөр/эвент, төлөв",
    "person_docs": "Хувийн RAG: хүн бүрийн баримт + вектор",
    "lead_codes": "Бүртгэлийн код (хүнийг таних)",
    "lead_changes": "AI, ажилтан, дуудлагын хийсэн өөрчлөлт",
    "knowledge_docs": "Байгууллагын RAG: мэдээллийн өгүүлбэр, FAQ асуулт + вектор",
    "calls": "Дуудлага",
    "messages": "Ярианы мөр бүр (залгагч, AI)",
}
ORDER = list(ABOUT)


def _connect(t: Tenant) -> sqlite3.Connection:
    # Бүх хүснэгтийг үүсгэсэн байхаар (шинэ байгууллагад ч хоосон хүснэгтүүд харагдана)
    with db.connect(t.db_path):
        pass
    with people.connect(t.dir):
        pass
    rag_store._connect(t.dir).close()
    con = sqlite3.connect(f"file:{people.db_path(t.dir)}?mode=ro", uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    return con


def _tables(con) -> list[str]:
    names = [r["name"] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    return sorted(names, key=lambda n: (ORDER.index(n) if n in ORDER else len(ORDER), n))


def _cell(value):
    if isinstance(value, bytes):              # вектор: float32
        n = len(value) // 4
        vec = np.frombuffer(value[:n * 4], np.float32)
        return {"dims": n, "preview": [round(float(x), 3) for x in vec[:6]]}
    return value


@router.get("")
def overview(t: Tenant = Depends(current_tenant)):
    con = _connect(t)
    try:
        tables = []
        for name in _tables(con):
            cols = [r["name"] for r in con.execute(f'PRAGMA table_info("{name}")')]
            rows = con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            tables.append({"name": name, "rows": rows, "columns": cols, "about": ABOUT.get(name, "")})
    finally:
        con.close()
    path = people.db_path(t.dir)
    return {"file": os.path.join("tenants", t.slug, "data", "receptionist.db"), "bytes": os.path.getsize(path), "tables": tables}


SECRET_KEYS = {"telegram_token", "staff_pin", "password"}


def _count(con, table: str) -> int:
    try:
        return con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    except sqlite3.OperationalError:
        return 0


@router.get("/info")
def info(t: Tenant = Depends(current_tenant)):
    """Компанид ойлгомжтой: юу, хаана, хэн, гадагш юу явдаг, хэр удаан."""
    con = _connect(t)
    try:
        n = {name: _count(con, name) for name in _tables(con)}
    finally:
        con.close()
    st = reminders.settings(t)
    rec_dir = t.recordings_dir
    recordings = len([f for f in os.listdir(rec_dir) if f.endswith(".wav")]) if os.path.isdir(rec_dir) else 0
    knowledge = len(os.listdir(t.knowledge_dir)) if os.path.isdir(t.knowledge_dir) else 0
    stored = [
        {"what": "Дуудлага", "detail": "залгасан дугаар (Caller ID), хэзээ, хэр удаан", "count": n.get("calls", 0)},
        {"what": "Ярианы бичвэр", "detail": "залгагч болон AI-ийн хэлсэн өгүүлбэр бүр (текстээр)", "count": n.get("messages", 0)},
        {"what": "Бүртгэл", "detail": "нэр, утас, хөтөлбөр/эвент, төлөв, тэмдэглэл", "count": n.get("leads", 0)},
        {"what": "Хувийн RAG", "detail": "хүн бүрийн баримт ба вектор, бүртгэлийн код", "count": n.get("person_docs", 0)},
        {"what": "Өөрчлөлтийн түүх", "detail": "AI, ажилтан, дуудлагаар хийсэн өөрчлөлт бүр", "count": n.get("lead_changes", 0)},
        {"what": "Байгууллагын мэдээлэл", "detail": "таны оруулсан файлууд, FAQ, тэдгээрийн вектор", "count": n.get("knowledge_docs", 0) + knowledge},
        {"what": "Ажилтны хоолойн бичлэг", "detail": "хэллэгийг өөрийн хоолойгоор бичсэн бол", "count": recordings},
    ]
    external = [
        {"to": "ElevenLabs (дуу үүсгэх)", "what": "зөвхөн AI-ийн хэлэх хариултын текст (мэдээлэл, FAQ, сануулгын мессеж — "
                                                   "сануулганд хүний нэр, огноо орно); «Аудио бэлдэх» үед нэг удаа",
         "active": True},
        {"to": "Telegram", "what": "шинэ бүртгэл, өөрчлөлтийн мэдэгдэл (нэр, утас) — таны группт",
         "active": bool(st.get("telegram_token") and st.get("telegram_chat_id"))},
        {"to": "GSM gateway / SIP", "what": "сануулгын дуудлага хийх утасны дугаар", "active": True},
    ]
    local = ["Яриа таних (монгол Whisper)", "RAG хайлт, хариулт сонгох", "Хувийн мэдээллийг өөрчлөх"]
    path = people.db_path(t.dir)
    return {"location": {"server": "PineQuest AI Ресепшн сервер", "file": os.path.join("tenants", t.slug, "data", "receptionist.db"),
                         "bytes": os.path.getsize(path) if os.path.exists(path) else 0, "separate": True},
            "stored": stored, "not_stored": ["Залгагчийн дуу бичлэг — зөвхөн бичвэр хадгалагдана"],
            "external": external, "local": local,
            "access": ["Танай байгууллагын нэвтэрсэн хэрэглэгчид", "Платформын админ (засвар, тусламжид)"],
            "retention": "Та устгах хүртэл хадгалагдана. Хүн бүрийн мэдээллийг «Бүртгэл» хуудаснаас бүрэн устгаж болно.",
            "backup": backup.status(t)}


def _csv(rows, cols) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        w.writerow([f"[вектор {len(v) // 4}]" if isinstance(v, bytes) else v for v in r])
    return ("\ufeff" + buf.getvalue()).encode("utf-8")      # BOM: Excel кирилл зөв уншина


@router.get("/export")
def export(format: str = "csv", t: Tenant = Depends(current_tenant)):
    stamp = time.strftime("%Y%m%d-%H%M")
    if format == "db":
        tmp = tempfile.mktemp(suffix=".db")
        s, d = sqlite3.connect(people.db_path(t.dir)), sqlite3.connect(tmp)
        try:
            _connect(t).close()
            s.backup(d)
        finally:
            d.close()
            s.close()
        data = open(tmp, "rb").read()
        os.remove(tmp)
        return Response(data, media_type="application/x-sqlite3",
                        headers={"Content-Disposition": f'attachment; filename="{t.slug}-{stamp}.db"'})
    if format != "csv":
        raise HTTPException(400, "format: csv | db")
    con = _connect(t)
    out = io.BytesIO()
    try:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for name in _tables(con):
                cur = con.execute(f'SELECT * FROM "{name}"')
                z.writestr(f"{name}.csv", _csv(cur.fetchall(), [c[0] for c in cur.description]))
            z.writestr("reminders.json", json.dumps(reminders.load(t), ensure_ascii=False, indent=2))
            st = {k: ("***" if k in SECRET_KEYS and v else v) for k, v in reminders.settings(t).items()}
            z.writestr("settings.json", json.dumps(st, ensure_ascii=False, indent=2))
            z.writestr("README.txt", "Таны AI ресепшний бүх өгөгдөл. CSV файлуудыг Excel-ээр нээнэ.\n"
                                     "Нууц түлхүүрүүд (Telegram token, ажилтны код) *** гэж нуугдсан.\n")
    finally:
        con.close()
    return Response(out.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{t.slug}-{stamp}.zip"'})


@router.delete("/person/{lead_id}")
def forget_person(lead_id: int, t: Tenant = Depends(current_tenant)):
    """Тэр хүний бүх мэдээлэл: бүртгэлүүд (ижил дугаартай), код, хувийн баримт, өөрчлөлт, сануулга, дуудлага, яриа."""
    lead = people.lead(t.dir, lead_id)
    if not lead:
        raise HTTPException(404, "Бүртгэл олдсонгүй")
    ids = people.same_person(t.dir, lead_id)
    phones = {p for p in [lead.get("phone"), lead.get("caller")] if p}
    removed = {}
    with db.connect(t.db_path) as con:
        q = ",".join("?" * len(ids))
        uuids = {r["call_uuid"] for r in con.execute(f"SELECT call_uuid FROM leads WHERE id IN ({q})", ids) if r["call_uuid"]}
        if phones:
            p = ",".join("?" * len(phones))
            uuids |= {r["uuid"] for r in con.execute(f"SELECT uuid FROM calls WHERE caller IN ({p})", list(phones))}
        u = ",".join("?" * len(uuids)) or "''"
        removed["messages"] = con.execute(f"DELETE FROM messages WHERE call_uuid IN ({u})", list(uuids)).rowcount
        removed["calls"] = con.execute(f"DELETE FROM calls WHERE uuid IN ({u})", list(uuids)).rowcount
        removed["leads"] = con.execute(f"DELETE FROM leads WHERE id IN ({q})", ids).rowcount
    with people.connect(t.dir) as con:
        for table in ("lead_codes", "person_docs", "lead_changes"):
            removed[table] = con.execute(f"DELETE FROM {table} WHERE lead_id IN ({q})", ids).rowcount
    with reminders.data_lock:
        data = reminders.load(t)
        removed["reminders"] = sum(1 for i in ids if data["items"].pop(str(i), None) is not None)
        reminders.save(t, data)
    return {"ok": True, "removed": removed}


@router.get("/{table}")
def table_rows(table: str, q: str = "", offset: int = 0, t: Tenant = Depends(current_tenant)):
    con = _connect(t)
    try:
        if table not in _tables(con):            # зөвхөн байгаа хүснэгтийн нэр (SQL injection-гүй)
            raise HTTPException(404, "Ийм хүснэгт алга")
        cols = [r["name"] for r in con.execute(f'PRAGMA table_info("{table}")')]
        types = {r["name"]: (r["type"] or "").upper() for r in con.execute(f'PRAGMA table_info("{table}")')}
        text_cols = [c for c in cols if types[c] in ("TEXT", "")]
        where, args = "", []
        q = q.strip()[:100]
        if q and text_cols:
            where = "WHERE " + " OR ".join(f'"{c}" LIKE ?' for c in text_cols)
            args = [f"%{q}%"] * len(text_cols)
        total = con.execute(f'SELECT COUNT(*) FROM "{table}" {where}', args).fetchone()[0]
        offset = max(0, offset)
        rows = con.execute(f'SELECT * FROM "{table}" {where} ORDER BY rowid DESC LIMIT ? OFFSET ?',
                           [*args, PAGE, offset]).fetchall()
    finally:
        con.close()
    return {"table": table, "columns": cols, "rows": [[_cell(r[c]) for c in cols] for r in rows], "total": total,
            "offset": offset, "page": PAGE, "about": ABOUT.get(table, "")}
