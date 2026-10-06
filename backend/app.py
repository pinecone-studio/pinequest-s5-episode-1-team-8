"""
AI Receptionist — backend API (FastAPI). Вэб интерфейс нь frontend/ (Next.js) — /api/* хүсэлтүүдийг энд дамжуулна.

  POST /api/signup  {"company", "phone", "email", "password"} -> шинэ байгууллага + эзэмшигч, нэвтэрнэ
  POST /api/login   {"email", "password"} -> хэрэглэгч + httpOnly session cookie
  POST /api/logout  -> cookie устгана
  GET  /api/me      -> нэвтэрсэн хэрэглэгч, байгууллага (нэвтрээгүй бол 401)

Бусад API нь routes/ хавтсанд хэсэг бүрээрээ (org, account, settings, calls, stats, leads, unanswered).

Нэвтэрмэгц зөвхөн өөрийн байгууллагын өгөгдлийг харна: middleware хүсэлт бүрт хэрэглэгчийн
байгууллагыг request.state.tenant-д тавина (routes -> deps.current_tenant).

  .venv/bin/python backend/app.py          # http://127.0.0.1:8100

Анх асахад "admin" хэрэглэгч санамсаргүй нууц үгтэй үүсч, терминалд НЭГ удаа хэвлэгдэнэ.
Анхдагчаар зөвхөн энэ компьютерээс (127.0.0.1:8100; SIM-TRUNK-ийн вэб 8000-д) нээгдэнэ — гаднаас зөвхөн Next.js-ээр дамжина.
"""
import os
import shutil
import sys
import threading
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import accounts  # noqa: E402
import auth  # noqa: E402  (буруу оролдлогын хязгаар, cookie)
import tenant as tenants  # noqa: E402
from routes import account, admin, calls, english, faq, knowledge, leads, org, settings, stats, status, training, unanswered, voice  # noqa: E402

LOCAL = {"127.0.0.1", "::1"}

# /docs, /openapi.json-ийг хаана: гадагш нээхэд API-ийн бүтцийг ил гаргахгүй
app = FastAPI(title="AI Receptionist", docs_url=None, redoc_url=None, openapi_url=None)
PUBLIC = {"/api/login", "/api/logout", "/api/signup"}


def client_ip(request: Request) -> str:
    # Next.js (эсвэл cloudflared)-ээр дамжсан хүсэлт 127.0.0.1-ээс ирдэг -> жинхэнэ IP нь толгойд.
    # Толгойг хуурч болох тул хязгаарыг и-мэйлээр бас тоолно (auth.py).
    host = request.client.host if request.client else "?"
    if host not in LOCAL:
        return host
    forwarded = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or host


def public_user(user: dict, t: "tenants.Tenant | None" = None) -> dict:
    """t — харж буй байгууллага (admin өөр байгууллага руу сольсон бол тэр), эс бөгөөс хэрэглэгчийнх"""
    t = t or tenants.Tenant(user["tenant"])
    cfg = t.config()
    return {"email": user["email"], "role": user["role"], "tenant": t.slug,
            "tenant_name": cfg.get("name", t.slug), "extension": cfg.get("extension"),
            "plan": cfg.get("plan", "trial"), "expires": user.get("expires"),
            "own_tenant": t.slug == user["tenant"]}


def viewed_tenant(request: Request, user: dict) -> "tenants.Tenant":
    """Хэрэглэгчийн байгууллага. Admin "Байгууллагууд"-аас өөр байгууллага руу сольсон бол тэр (cookie)."""
    slug = request.cookies.get(auth.TENANT_COOKIE)
    if user["role"] == "admin" and slug:
        try:
            t = tenants.Tenant(slug)
            if t.exists():
                return t
        except ValueError:
            pass
    return tenants.Tenant(user["tenant"])


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
            request.state.tenant = viewed_tenant(request, user)
            response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


def error(detail: str, status: int) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status)


def logged_in(request: Request, user: dict) -> JSONResponse:
    """Хэрэглэгчийн мэдээлэл + session cookie"""
    response = JSONResponse(public_user(user))
    auth.set_session(response, request, user)
    return response


# ---------------- нэвтрэх ----------------

class LoginBody(BaseModel):
    email: str = ""
    password: str = ""


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
    return logged_in(request, user)


@app.post("/api/logout")
def logout():
    response = JSONResponse({"ok": True})
    response.delete_cookie(auth.COOKIE)
    response.delete_cookie(auth.TENANT_COOKIE)
    return response


@app.get("/api/me")
def me(request: Request):
    return public_user(request.state.user, request.state.tenant)


# ---------------- бүртгүүлэх ----------------

class SignupBody(BaseModel):
    company: str = ""
    phone: str = ""
    email: str = ""
    password: str = ""


SIGNUPS: dict[str, list[float]] = {}
SIGNUPS_PER_HOUR = 3
tenants_lock = threading.Lock()


@app.post("/api/signup")
def signup(request: Request, body: SignupBody):
    """Шинэ байгууллага + эзэмшигч хэрэглэгч. Туршилтын эрхтэй (plan=trial) эхэлнэ."""
    ip = client_ip(request)
    now = time.time()
    SIGNUPS[ip] = [t for t in SIGNUPS.get(ip, []) if now - t < 3600]
    if len(SIGNUPS[ip]) >= SIGNUPS_PER_HOUR:
        return error("Нэг цагт 3-аас олон бүртгэл үүсгэх боломжгүй", 429)
    email = accounts.normalize_email(body.email)
    if not accounts.EMAIL.fullmatch(email):
        return error("И-мэйл хаяг буруу", 400)
    if len(body.password) < 8:
        return error("Нууц үг 8-аас дээш тэмдэгт байх ёстой", 400)
    phone = tenants.clean_phone(body.phone)
    if phone and not 6 <= len(phone.lstrip("+")) <= 12:
        return error("Утасны дугаар буруу", 400)
    try:
        with tenants_lock:
            t = tenants.create(body.company, phone=phone, email=email)
            try:
                uid = accounts.create_user(email, body.password, t.slug)
            except ValueError:
                shutil.rmtree(t.dir, ignore_errors=True)
                raise
    except ValueError as e:
        return error(str(e), 400)
    SIGNUPS[ip].append(now)
    print(f"Шинэ байгууллага: {t.slug} ({t.config()['name']}) {email}")
    return logged_in(request, accounts.get(uid))


# ---------------- хэсгүүд ----------------

app.include_router(org.router)
app.include_router(account.router)
app.include_router(settings.router)
app.include_router(calls.router)
app.include_router(stats.router)
app.include_router(leads.router)
app.include_router(unanswered.router)
app.include_router(knowledge.router)
app.include_router(faq.router)
app.include_router(voice.router)
app.include_router(training.router)
app.include_router(english.router)
app.include_router(status.router)
app.include_router(admin.router)


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8100"))
    tenants.ensure_default()
    password = accounts.ensure_admin()
    if password:
        print(f"Анхны хэрэглэгч үүслээ -> нэвтрэх нэр: admin, нууц үг: {password}")
        print("  (дахин хэвлэгдэхгүй. Солих: .venv/bin/python backend/accounts.py admin admin)")
    print(f"API: http://{host}:{port}  (вэб: frontend/ -> bun dev -> http://localhost:3000)")
    uvicorn.run(app, host=host, port=port, log_level="warning")
