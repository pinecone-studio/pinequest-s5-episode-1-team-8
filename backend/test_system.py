"""
Backend-ийн тест. Кодыг өөрчилсний дараа, PR-ийн өмнө ажиллуулна.

  .venv/bin/python backend/test_system.py

1. Нэвтрэлт: нэвтрэх, буруу нууц үг, хамгаалалттай API, гарах, хуурамч cookie,
   нууц үг солиход хуучин session хүчингүй, буруу оролдлогын хязгаар (IP + и-мэйл)

Түр хавтсанд (DATA_DIR) ажиллана — backend/data/-ийн жинхэнэ хэрэглэгчдэд хүрэхгүй.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="pc_test_")

import accounts  # noqa: E402
import auth  # noqa: E402
from app import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

failures: list[str] = []


def check(name: str, ok: bool, detail: object = ""):
    print(f"  {'✓' if ok else '✗'} {name}" + (f"  ({detail})" if not ok and detail != "" else ""))
    if not ok:
        failures.append(name)


def login(client: TestClient, email: str, password: str, **kw):
    return client.post("/api/login", json={"email": email, "password": password}, **kw)


def test_login():
    print("\n[1] Нэвтрэлт")
    auth.FAIL_DELAY = 0
    pw = accounts.ensure_admin()
    check("анх асахад admin үүснэ, дахин үүсэхгүй", bool(pw) and accounts.ensure_admin() is None)
    accounts.create_user("owner@example.mn", "secret-pass-1", "gerel")

    c = TestClient(app)
    r = c.get("/api/me")
    check("нэвтрээгүй -> 401", r.status_code == 401, r.status_code)
    check("/docs хаалттай", c.get("/docs").status_code in (401, 404))

    r = login(c, "owner@example.mn", "wrong-pass")
    check("буруу нууц үг -> 401", r.status_code == 401 and "буруу" in r.json()["detail"], r.status_code)
    r = login(c, "nobody@example.mn", "secret-pass-1")
    check("байхгүй хэрэглэгч -> 401 (ижил мессеж)", r.status_code == 401 and "буруу" in r.json()["detail"])
    r = login(c, "", "")
    check("хоосон -> 400", r.status_code == 400, r.status_code)

    r = login(c, " Owner@Example.mn ", "secret-pass-1")
    cookie = r.headers.get("set-cookie", "").lower()
    check("зөв нууц үг -> 200 + cookie (том/жижиг үсэг, зай хамаарахгүй)",
          r.status_code == 200 and r.json()["email"] == "owner@example.mn" and auth.COOKIE in cookie, r.status_code)
    check("cookie httponly, samesite=lax", "httponly" in cookie and "samesite=lax" in cookie, cookie)
    me = c.get("/api/me")
    check("/api/me -> хэрэглэгч", me.status_code == 200 and me.json()["role"] == "owner"
          and me.json()["tenant"] == "gerel" and "hash" not in me.json(), me.text)

    token = c.cookies.get(auth.COOKIE)
    fake = token[:-1] + ("0" if token[-1] != "0" else "1")
    r = TestClient(app).get("/api/me", headers={"cookie": f"{auth.COOKIE}={fake}"})
    check("хуурамч cookie -> 401", r.status_code == 401)

    accounts.set_password("owner@example.mn", "new-secret-2")
    check("нууц үг солиход хуучин session хүчингүй", c.get("/api/me").status_code == 401)

    login(c, "owner@example.mn", "new-secret-2")
    check("шинэ нууц үгээр нэвтэрнэ", c.get("/api/me").status_code == 200)
    r = c.post("/api/logout")
    check("гарах -> cookie устна", r.status_code == 200 and c.get("/api/me").status_code == 401)

    print("\n[2] Буруу оролдлогын хязгаар")
    auth._fails.clear()
    codes = [login(c, "owner@example.mn", "bad").status_code for _ in range(6)]
    check("нэг и-мэйл рүү 5 буруу оролдлогын дараа 429", codes == [401] * 5 + [429], codes)
    r = login(c, "owner@example.mn", "new-secret-2")
    check("хаагдсан үед зөв нууц үг ч 429", r.status_code == 429, r.status_code)

    auth._fails.clear()
    proxy = TestClient(app, client=("127.0.0.1", 50000))     # Next.js-ээр дамжсан хүсэлт мэт
    for i in range(5):
        login(proxy, "owner@example.mn", "bad", headers={"x-forwarded-for": f"10.0.0.{i}"})
    r = login(proxy, "owner@example.mn", "bad", headers={"x-forwarded-for": "10.0.0.99"})
    check("IP толгой сольсон ч нэг и-мэйл рүү 5 удаа буруу -> 429", r.status_code == 429, r.status_code)
    r = login(proxy, "admin", "bad", headers={"x-forwarded-for": "10.0.0.99"})
    check("өөр и-мэйл, өөр IP -> хаагдаагүй (401)", r.status_code == 401, r.status_code)

    auth._fails.clear()
    for i in range(5):     # гаднаас шууд ирсэн хүсэлт x-forwarded-for хуурч IP-ийн хязгаараас зугтахгүй
        login(c, f"user{i}@example.mn", "bad", headers={"x-forwarded-for": f"10.0.0.{i}"})
    r = login(c, "owner@example.mn", "new-secret-2", headers={"x-forwarded-for": "10.0.0.50"})
    check("гаднын хүсэлтийн IP толгойд итгэхгүй (нэг IP-ээс 5 удаа -> 429)", r.status_code == 429, r.status_code)


if __name__ == "__main__":
    test_login()
    print(f"\n{'ТЭНЦЛЭЭ ✓' if not failures else f'ТЭНЦЭЭГҮЙ: {len(failures)} шалгалт'}")
    sys.exit(1 if failures else 0)
