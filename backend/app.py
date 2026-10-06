"""
AI Receptionist — backend API (FastAPI). Вэб интерфейс нь frontend/ (Next.js) — /api/* хүсэлтүүдийг энд дамжуулна.

Одоогоор: нэвтрэх, гарах, нэвтэрсэн хэрэглэгчийн мэдээлэл.

  POST /api/login   {"email", "password"} -> хэрэглэгч + httpOnly session cookie
  POST /api/logout  -> cookie устгана
  GET  /api/me      -> нэвтэрсэн хэрэглэгч (нэвтрээгүй бол 401)

  .venv/bin/python backend/app.py          # http://127.0.0.1:8100

Анх асахад хэрэглэгч байхгүй бол "admin" санамсаргүй нууц үгтэй үүсч, терминалд НЭГ удаа хэвлэгдэнэ.
Анхдагчаар зөвхөн энэ компьютерээс (127.0.0.1:8100; SIM-TRUNK-ийн вэб 8000-д) нээгдэнэ — гаднаас зөвхөн Next.js-ээр дамжина.
"""
import os
import sys
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import accounts  # noqa: E402
import auth  # noqa: E402  (буруу оролдлогын хязгаар, cookie нэр)

LOCAL = {"127.0.0.1", "::1"}

# /docs, /openapi.json-ийг хаана: гадагш нээхэд API-ийн бүтцийг ил гаргахгүй
app = FastAPI(title="AI Receptionist", docs_url=None, redoc_url=None, openapi_url=None)
PUBLIC = {"/api/login", "/api/logout"}


def client_ip(request: Request) -> str:
    # Next.js (эсвэл cloudflared)-ээр дамжсан хүсэлт 127.0.0.1-ээс ирдэг -> жинхэнэ IP нь толгойд.
    # Толгойг хуурч болох тул хязгаарыг и-мэйлээр бас тоолно (auth.py).
    host = request.client.host if request.client else "?"
    if host not in LOCAL:
        return host
    forwarded = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or host


def public_user(user: dict) -> dict:
    return {"email": user["email"], "role": user["role"], "tenant": user["tenant"],
            "expires": user.get("expires")}


@app.middleware("http")
async def require_login(request: Request, call_next):
    path = request.url.path
    if path in PUBLIC:
        response = await call_next(request)
    else:
        user = accounts.session_user(request.cookies.get(auth.COOKIE))
        if user is None:
            response = JSONResponse({"detail": "Нэвтрэх шаардлагатай"}, status_code=401)
        else:
            request.state.user = user
            response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


class LoginBody(BaseModel):
    email: str = ""
    password: str = ""


def error(detail: str, status: int) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status)


@app.post("/api/login")
def login(request: Request, body: LoginBody):
    email = accounts.normalize_email(body.email)
    keys = [f"ip:{client_ip(request)}", f"email:{email}"]
    if auth.too_many_fails(keys):
        return error("Олон удаа буруу оролдлоо. 10 минутын дараа дахин оролдоно уу.", 429)
    if not email or not body.password:
        return error("И-мэйл, нууц үгээ оруулна уу", 400)
    user = accounts.authenticate(email, body.password)
    if not user:
        auth.record_fail(keys)
        time.sleep(auth.FAIL_DELAY)   # таахыг удаашруулна
        return error("И-мэйл эсвэл нууц үг буруу", 401)
    token = accounts.make_session(user)
    response = JSONResponse(public_user(accounts.session_user(token)))
    secure = request.headers.get("x-forwarded-proto") == "https" or request.url.scheme == "https"
    response.set_cookie(auth.COOKIE, token, max_age=accounts.SESSION_DAYS * 86400,
                        httponly=True, samesite="lax", secure=secure)
    return response


@app.post("/api/logout")
def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(auth.COOKIE)
    return response


@app.get("/api/me")
def me(request: Request):
    return public_user(request.state.user)


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8100"))
    password = accounts.ensure_admin()
    if password:
        print(f"Анхны хэрэглэгч үүслээ -> нэвтрэх нэр: admin, нууц үг: {password}")
        print("  (дахин хэвлэгдэхгүй. Солих: .venv/bin/python backend/accounts.py admin admin)")
    print(f"API: http://{host}:{port}  (вэб: frontend/ -> bun dev -> http://localhost:3000)")
    uvicorn.run(app, host=host, port=port, log_level="warning")
