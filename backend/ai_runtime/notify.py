"""
Ажилтанд мэдэгдэл (Telegram). Шинэ бүртгэл / ажилтан эргэж залгах хүсэлт ирэхэд групп руу мессеж.

Тохиргоо: вэб -> Тохиргоо (tenants/<slug>/data/settings.json, 0600).
Telegram байхгүй/алдаатай бол дуудлагад нөлөөлөхгүй (зөвхөн лог).
"""
import json
import os

import httpx

API = "https://api.telegram.org/bot{token}/{method}"


def settings_path(path: str | None = None) -> str:
    """Байгууллага бүрийн тохиргоо: tenants/<slug>/data/settings.json (path=None -> TENANT)."""
    if path:
        return path
    import tenant
    return tenant.current().settings_path


def load_settings(path: str | None = None) -> dict:
    try:
        with open(settings_path(path), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(data: dict, path: str | None = None):
    path = settings_path(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def telegram(method: str, token: str | None = None, **params) -> dict:
    token = token or load_settings().get("telegram_token")
    if not token:
        raise RuntimeError("Telegram токен тохируулаагүй")
    r = httpx.post(API.format(token=token, method=method), json=params, timeout=10)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("description", f"HTTP {r.status_code}"))
    return data["result"]


def send(text: str, path: str | None = None) -> bool:
    """Тохируулсан групп руу мессеж. Амжилтгүй бол False (алдааг хэвлэнэ)."""
    s = load_settings(path)
    if not (s.get("telegram_token") and s.get("telegram_chat_id")):
        return False
    try:
        telegram("sendMessage", s["telegram_token"], chat_id=s["telegram_chat_id"], text=text)
        return True
    except Exception as e:
        print(f"  [Telegram алдаа] {e}")
        return False


def lead_message(name, phone, phone_raw, reason, question=None) -> str:
    kind = "📞 Ажилтан эргэж залгах хүсэлт" if reason == "handoff" else "🆕 Шинэ бүртгэл"
    lines = [kind, f"Нэр: {name or '—'}", f"Утас: {phone or '— (баталгаажаагүй)'}"]
    if not phone and phone_raw:
        lines.append(f"STT сонссон: {phone_raw}")
    if question:
        lines.append(f"Асуулт: {question}")
    lines.append("Дэлгэрэнгүй: вэб -> Бүртгэл")
    return "\n".join(lines)
