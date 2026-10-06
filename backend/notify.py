"""
Ажилтанд мэдэгдэл (Telegram). Шинэ бүртгэл / ажилтан эргэж залгах хүсэлт ирэхэд групп руу мессеж.

Тохиргоо: вэб -> Тохиргоо. Байгууллага бүрийн tenants/<slug>/data/settings.json (0600) — токен git-д орохгүй.
Telegram байхгүй/алдаатай бол дуудлагад нөлөөлөхгүй (send() False буцаана).
"""
import json
import os
import re

import httpx

from tenant import Tenant

API = "https://api.telegram.org/bot{token}/{method}"
TOKEN = re.compile(r"\d{5,12}:[A-Za-z0-9_-]{30,50}")    # @BotFather-ийн токен (URL-д орох тул заавал шалгана)


def load_settings(t: Tenant) -> dict:
    try:
        with open(t.settings_path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(t: Tenant, data: dict):
    os.makedirs(os.path.dirname(t.settings_path), exist_ok=True)
    fd = os.open(t.settings_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def telegram(method: str, token: str, **params):
    """Telegram Bot API. Алдаа бол RuntimeError (Telegram-ийн тайлбартай)."""
    if not TOKEN.fullmatch(token or ""):
        raise RuntimeError("Токены хэлбэр буруу (жишээ: 123456789:ABC-DEF...)")
    try:
        r = httpx.post(API.format(token=token, method=method), json=params, timeout=10)
        data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        raise RuntimeError(f"Telegram-тай холбогдож чадсангүй: {e}") from None
    if not data.get("ok"):
        raise RuntimeError(data.get("description", f"HTTP {r.status_code}"))
    return data["result"]


def send(t: Tenant, text: str) -> bool:
    """Тохируулсан групп руу мессеж. Амжилтгүй бол False (алдааг хэвлэнэ)."""
    s = load_settings(t)
    if not (s.get("telegram_token") and s.get("telegram_chat_id")):
        return False
    try:
        telegram("sendMessage", s["telegram_token"], chat_id=s["telegram_chat_id"], text=text)
        return True
    except RuntimeError as e:
        print(f"  [Telegram алдаа] {t.slug}: {e}")
        return False
