"""
Өгөгдлийн сан (вэбээс харах): байгууллагын receptionist.db (SQLite) — хүснэгт бүр, мөр бүр. Зөвхөн УНШИНА:
өөрчлөлтийг AI туслах, сануулгын дуудлага хийнэ (people.py), хэн ч гараар засахгүй.

  GET /api/database                    -> {"file", "bytes", "tables": [{"name", "rows", "columns", "about"}]}
  GET /api/database/{table}?q=&offset= -> {"columns", "rows", "total"} — вектор (BLOB) -> {"dims", "preview"}
"""
import os
import sqlite3

import numpy as np
from fastapi import APIRouter, Depends, HTTPException

import db
import people
import rag_store
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
