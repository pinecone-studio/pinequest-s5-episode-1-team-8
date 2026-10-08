"""
Өдөр бүрийн автомат нөөцлөлт: байгууллага бүрийн receptionist.db -> data/backups/receptionist-YYYY-MM-DD.db.
SQLite-ийн backup API (ажиллаж байх үед ч бүтэн, зөрчилгүй хуулбар). Сүүлийн KEEP хоногийг үлдээнэ.
"""
import glob
import os
import sqlite3
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from tenant import Tenant, all_tenants

TZ = ZoneInfo("Asia/Ulaanbaatar")
KEEP = int(os.getenv("BACKUP_KEEP", "7"))
CHECK = float(os.getenv("BACKUP_CHECK", "3600"))     # цаг тутам шалгаж, өнөөдрийнх алга бол хийнэ


def backup_dir(t: Tenant) -> str:
    return t.path("data", "backups")


def backups(t: Tenant) -> list[str]:
    return sorted(glob.glob(os.path.join(backup_dir(t), "receptionist-*.db")))


def run(t: Tenant, day: str | None = None) -> str | None:
    """Өнөөдрийн нөөцлөлт (байвал дахин хийхгүй) -> файлын зам."""
    src = t.db_path
    if not os.path.exists(src):
        return None
    day = day or datetime.now(TZ).strftime("%Y-%m-%d")
    out = os.path.join(backup_dir(t), f"receptionist-{day}.db")
    if os.path.exists(out):
        return out
    os.makedirs(backup_dir(t), exist_ok=True)
    tmp = out + ".tmp"
    s, d = sqlite3.connect(src, timeout=10), sqlite3.connect(tmp)
    try:
        s.backup(d)
    finally:
        d.close()
        s.close()
    os.replace(tmp, out)
    for old in backups(t)[:-KEEP]:
        os.remove(old)
    return out


def status(t: Tenant) -> dict:
    files = backups(t)
    last = files[-1] if files else None
    return {"count": len(files), "keep_days": KEEP,
            "last": os.path.getmtime(last) if last else None,
            "last_bytes": os.path.getsize(last) if last else 0}


def _loop():
    while True:
        for t in all_tenants():
            try:
                run(t)
            except Exception as exc:
                print(f"  [нөөцлөлт] {t.slug}: {exc}")
        time.sleep(CHECK)


if os.getenv("BACKUP_SCHEDULER", "1") == "1":
    threading.Thread(target=_loop, daemon=True).start()
