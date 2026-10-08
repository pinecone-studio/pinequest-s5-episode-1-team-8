"""
Вэбийн хэрэглэгчид (backend/data/accounts.db): байгууллага бүр өөрийн бүртгэлтэй.

  users: email (нэвтрэх нэр), нууц үгийн хэш (PBKDF2-SHA256 200k), tenant (байгууллага), role
    role = owner  -> зөвхөн өөрийн байгууллага
    role = admin  -> платформын эзэн: бүх байгууллагыг харна

Session: гарын үсэгтэй cookie (user id + нууц үгийн хувилбар + хугацаа), backend/data/web_secret (0600).
Нууц үг солиход тухайн хэрэглэгчийн хуучин session хүчингүй болно (pw_version).

Анх асахад хэрэглэгч байхгүй бол "admin" санамсаргүй нууц үгтэй үүснэ (ensure_admin).

  .venv/bin/python backend/accounts.py admin <нэр>     # admin нууц үг солих / үүсгэх
"""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager

from config import DATA_DIR

DB = os.path.join(DATA_DIR, "accounts.db")
SECRET_FILE = os.path.join(DATA_DIR, "web_secret")
SESSION_DAYS = 7
DEFAULT_TENANT = "pinecone"
EMAIL = re.compile(r"[^@\s]{1,64}@[^@\s]{1,190}\.[a-z]{2,}", re.I)
WORDS = ["pine", "cone", "nest", "code", "bolt", "mars", "luna", "nova", "tiger", "eagle", "river", "stone"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    email      TEXT UNIQUE NOT NULL,
    salt       TEXT NOT NULL,
    hash       TEXT NOT NULL,
    tenant     TEXT NOT NULL,
    role       TEXT NOT NULL DEFAULT 'owner',
    pw_version INTEGER NOT NULL DEFAULT 1,
    created_at REAL
);
"""


@contextmanager
def connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(DB, timeout=5)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()
    os.chmod(DB, 0o600)


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000).hex()


def _secret() -> bytes:
    if not os.path.exists(SECRET_FILE):
        os.makedirs(DATA_DIR, exist_ok=True)
        fd = os.open(SECRET_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_hex(32))
    with open(SECRET_FILE) as f:
        return bytes.fromhex(f.read().strip())


def normalize_email(email: str) -> str:
    return email.strip().lower()


def create_user(email: str, password: str, tenant: str = DEFAULT_TENANT, role: str = "owner") -> int:
    email = normalize_email(email)
    if role == "owner" and not EMAIL.fullmatch(email):
        raise ValueError("И-мэйл хаяг буруу")
    if len(password) < 8:
        raise ValueError("Нууц үг 8-аас дээш тэмдэгт байх ёстой")
    salt = secrets.token_hex(16)
    try:
        with connect() as con:
            cur = con.execute("INSERT INTO users (email, salt, hash, tenant, role, created_at) VALUES (?,?,?,?,?,?)",
                              (email, salt, _hash(password, salt), tenant, role, time.time()))
            return cur.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("Энэ и-мэйлээр бүртгэл үүссэн байна") from None


def set_password(email: str, password: str):
    if len(password) < 8:
        raise ValueError("Нууц үг 8-аас дээш тэмдэгт байх ёстой")
    salt = secrets.token_hex(16)
    with connect() as con:
        n = con.execute("UPDATE users SET salt=?, hash=?, pw_version=pw_version+1 WHERE email=?",
                        (salt, _hash(password, salt), normalize_email(email))).rowcount
    if not n:
        raise ValueError("Хэрэглэгч олдсонгүй")


def authenticate(email: str, password: str) -> dict | None:
    with connect() as con:
        row = con.execute("SELECT * FROM users WHERE email=?", (normalize_email(email),)).fetchone()
    if row is None:
        _hash(password, "00" * 16)          # байхгүй хэрэглэгчийн хариу ч ижил удаан (timing)
        return None
    return dict(row) if hmac.compare_digest(_hash(password, row["salt"]), row["hash"]) else None


def get(user_id: int) -> dict | None:
    with connect() as con:
        row = con.execute("SELECT id, email, tenant, role, pw_version, created_at FROM users WHERE id=?",
                          (user_id,)).fetchone()
    return dict(row) if row else None


DEMO_EMAIL = "demo"


def demo_user() -> dict:
    """«Демо» товчны хэрэглэгч: admin эрхээр бүгдийг харна (засах эрхийг app.py хаана). Байхгүй бол үүсгэнэ."""
    with connect() as con:
        row = con.execute("SELECT id FROM users WHERE email=?", (DEMO_EMAIL,)).fetchone()
    if row is None:
        create_user(DEMO_EMAIL, secrets.token_urlsafe(24), role="admin")    # нууц үгээр нэвтрэх боломжгүй
        return demo_user()
    return get(row["id"])


def users_of(tenant: str) -> list[dict]:
    with connect() as con:
        return [dict(r) for r in con.execute(
            "SELECT id, email, role, created_at FROM users WHERE tenant=? ORDER BY id", (tenant,))]


def make_session(user: dict) -> str:
    payload = f"{user['id']}.{user['pw_version']}.{int(time.time()) + SESSION_DAYS * 86400}"
    sig = hmac.new(_secret(), payload.encode(), "sha256").hexdigest()
    return f"{payload}.{sig}"


def session_user(token: str | None) -> dict | None:
    """Cookie зөв, хугацаа нь дуусаагүй, нууц үг солигдоогүй бол хэрэглэгч (+ expires), үгүй бол None."""
    if not token or token.count(".") != 3:
        return None
    uid, ver, exp, sig = token.split(".")
    good = hmac.new(_secret(), f"{uid}.{ver}.{exp}".encode(), "sha256").hexdigest()
    if not (hmac.compare_digest(sig, good) and uid.isdigit() and exp.isdigit() and int(exp) > time.time()):
        return None
    user = get(int(uid))
    if not user or str(user["pw_version"]) != ver:
        return None
    return {**user, "expires": int(exp)}


def ensure_admin() -> str | None:
    """Хэрэглэгч огт байхгүй бол "admin"-ийг санамсаргүй нууц үгтэй үүсгээд нууц үгийг буцаана
    (терминалд НЭГ удаа хэвлэхэд). Хэрэглэгч байвал None."""
    with connect() as con:
        if con.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            return None
    password = "-".join(secrets.choice(WORDS) for _ in range(3)) + f"-{secrets.randbelow(900) + 100}"
    create_user("admin", password, role="admin")
    return password


if __name__ == "__main__":
    import getpass
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "admin":
        name = sys.argv[2]
        pw = getpass.getpass("Шинэ нууц үг (8+ тэмдэгт): ")
        if pw != getpass.getpass("Дахин: "):
            raise SystemExit("Тохирохгүй")
        try:
            set_password(name, pw)
        except ValueError:
            create_user(name, pw, role="admin")
        print("Болсон. Энэ хэрэглэгчийн хуучин нэвтрэлтүүд хүчингүй болов.")
    else:
        print(__doc__)
