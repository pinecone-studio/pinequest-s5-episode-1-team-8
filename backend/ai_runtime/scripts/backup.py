"""
Өдөр бүрийн нөөц: бүх байгууллагын мэдээлэл, FAQ, сургалтын жишээ, хүний бичлэг, дуудлагын лог,
бүртгэл (tenants/), хэрэглэгчид (data/accounts.db), платформын хоолой (voices/).
Дахин үүсгэж болох аудио/индекс (data/tts_cache, tenants/*/faq_audio, knowledge_index)-ийг оруулахгүй.

  .venv/bin/python scripts/backup.py   # ~/PineconeBackups/pinecone-YYYY-MM-DD.tgz, сүүлийн 14

Python-оор бичсэн шалтгаан: LaunchAgent-аас /bin/bash Desktop хавтсанд хандах эрх авч чадаагүй
("Operation not permitted"), харин Python-д аль хэдийн зөвшөөрөл өгсөн.
Анхаар: энэ компьютер эвдэрвэл нөөц ч алга -> үе үе гадаад диск/Drive руу хуулна уу.
"""
import glob
import os
import sqlite3
import tarfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.getenv("BACKUP_DIR", os.path.expanduser("~/PineconeBackups"))
ITEMS = ["tenants", "data", "voices"]
SKIP_DIRS = {"faq_audio", "knowledge_index", "tts_cache", "en_cache", "preview"}
SKIP_FILES = {"selector_cache.npz", "receptionist.db", "accounts.db", "job.log"}   # db-г snapshot-оор
KEEP = 14


def keep(info: tarfile.TarInfo):
    parts = info.name.split("/")
    if set(parts) & SKIP_DIRS or parts[-1] in SKIP_FILES:
        return None
    return info


def main():
    os.chdir(ROOT)
    os.makedirs(DEST, exist_ok=True)
    # Ажиллаж байх үед SQLite-ийг аюулгүй хуулна (backup API) -> *.snapshot.db
    snapshots = []
    for path in glob.glob("tenants/*/data/receptionist.db") + ["data/accounts.db"]:
        if os.path.exists(path):
            snap = path.replace(".db", ".snapshot.db")
            src, dst = sqlite3.connect(path), sqlite3.connect(snap)
            src.backup(dst)
            dst.close()
            src.close()
            snapshots.append(snap)
    out = os.path.join(DEST, f"pinecone-{time.strftime('%Y-%m-%d')}.tgz")
    try:
        with tarfile.open(out, "w:gz") as tar:
            for item in ITEMS:
                if os.path.exists(item):
                    tar.add(item, filter=keep)
        os.chmod(out, 0o600)
    finally:
        for snap in snapshots:
            os.remove(snap)
    for old in sorted(glob.glob(os.path.join(DEST, "pinecone-*.tgz")))[:-KEEP]:
        os.remove(old)
    print(f"{time.strftime('%F %T')} нөөц: {out} ({os.path.getsize(out) // 1024} KB, {len(snapshots)} өгөгдлийн сан)")


if __name__ == "__main__":
    main()
