"""
Ажилтанд мэдэгдэл (Telegram). Шинэ бүртгэл / ажилтан эргэж залгах хүсэлт ирэхэд групп руу мессеж.

Тохиргоо: вэб -> Тохиргоо (tenants/<slug>/data/settings.json, 0600).
Telegram байхгүй/алдаатай бол дуудлагад нөлөөлөхгүй (зөвхөн лог).
"""
import json
import os
import re

import httpx

API = "https://api.telegram.org/bot{token}/{method}"
SENDSMS_API = "https://smsapi.buural.mn/api/user/send"


def send_registration_code(phone: str | None, code: str, company: str = "") -> bool:
    """Баталгаажсан Монгол дугаар руу SendSMS.mn эсвэл SMS gateway-аар илгээнэ."""
    if not re.fullmatch(r"\d{4}", code):
        print("  [SMS] илгээгээгүй: 4 оронтой код алга")
        return False
    label = f"{company.strip()[:20]}: " if company and company.strip() else ""
    return send_sms(phone, f"{label}Бүртгэлийн код: {code}. Бусдад бүү хэл.")


def event_sms_text(company: str, event: str, at: str, code: str | None) -> str:
    """Эвентэд бүртгүүлэхэд шууд очих сануулга: "Pinecone Academy: AI Hackathon 10/18 10:00 цагт. Код: 4052"."""
    from datetime import datetime
    try:
        when = datetime.strptime(at[:16], "%Y-%m-%dT%H:%M").strftime("%m/%d %H:%M")
    except (TypeError, ValueError):
        when = ""
    label = f"{company.strip()[:20]}: " if company and company.strip() else ""
    text = f"{label}Сануулга - {event[:40]} {when} цагт. Таныг бүртгэлээ."
    return text + (f" Код: {code}" if code and re.fullmatch(r"\d{4}", code) else "")


def send_event_sms(phone: str | None, company: str, event: str, at: str, code: str | None) -> bool:
    return send_sms(phone, event_sms_text(company, event, at, code))


def send_sms(phone: str | None, message: str) -> bool:
    """SMS (бүртгэлийн код, уулзалт/эвентийн сануулга). SMS_API_KEY+SMS_API_TOKEN (SendSMS.mn) эсвэл
    SMS_API_URL+SMS_API_TOKEN (Bearer gateway). SMS_DRY_RUN=1 бол илгээхгүй (туршилт)."""
    url = os.getenv("SMS_API_URL", "").strip()
    api_key = os.getenv("SMS_API_KEY", "").strip()
    token = os.getenv("SMS_API_TOKEN", "").strip()
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 11 and digits.startswith("976"):
        digits = digits[3:]
    if not re.fullmatch(r"\d{8}", digits):
        print("  [SMS] илгээгээгүй: баталгаажсан 8 оронтой дугаар алга")
        return False
    if api_key and token:
        url = SENDSMS_API
        payload = {"apiKey": api_key, "apiToken": token, "phone": digits, "message": message}
        headers = {}
    elif url.startswith("https://") and token:
        payload = {"to": f"+976{digits}", "message": message}
        headers = {"Authorization": f"Bearer {token}"}
    else:
        print("  [SMS] илгээгээгүй: SMS_API_KEY/SMS_API_TOKEN тохируулаагүй")
        return False
    if os.getenv("SMS_DRY_RUN") == "1":
        print(f"  [SMS dry-run] {digits[:2]}****{digits[-2:]}: {message}")
        return True
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        try:
            result = response.json()
        except ValueError:
            result = None
        if isinstance(result, dict) and (
            result.get("success") is False
            or result.get("status") in ("error", "failed", "failure")
            or result.get("error")
        ):
            print("  [SMS алдаа] үйлчилгээ хүсэлтийг татгалзлаа")
            return False
        print(f"  [SMS] үйлчилгээ хүсэлтийг хүлээн авлаа (HTTP {response.status_code})")
        return True
    except httpx.HTTPStatusError as exc:
        print(f"  [SMS алдаа] HTTP {exc.response.status_code}")
        return False
    except httpx.HTTPError as exc:
        print(f"  [SMS алдаа] {type(exc).__name__}")
        return False


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
