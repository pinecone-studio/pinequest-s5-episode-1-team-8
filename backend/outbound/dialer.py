"""Аль замаар залгах вэ (платформын admin тохируулна): DATA_DIR/outbound.json (600).

  {"mode": "sip", "host": "192.168.1.50", "port": 5060, "user": "ai", "password": "...", "prefix": ""}
     -> GSM gateway (GoIP, Dinstar ...) / SIP trunk руу SIP INVITE (outbound/sip.py)
  {"mode": "mac"}  -> iMac iPhone-ээр (Continuity) залгаж, дууг BlackHole-оор дамжуулна (outbound/mac.py)
  {"mode": "off"}  -> залгахгүй (сануулга хуваарьтаа хүлээнэ)
Орчны хувьсагч OUTBOUND_MODE, OUTBOUND_SIP_HOST ... файлыг дарна (сервер дээр тохируулахад).
"""
import json
import os

from config import DATA_DIR

PATH = os.path.join(DATA_DIR, "outbound.json")
FIELDS = ("mode", "host", "port", "user", "password", "prefix", "local_ip", "local_port", "ring_timeout")
MODES = ("off", "sip", "mac")


def load() -> dict:
    try:
        with open(PATH, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        cfg = {}
    cfg.setdefault("mode", "off")
    for k in FIELDS:
        env = os.getenv(f"OUTBOUND_{'SIP_' if k not in ('mode',) else ''}{k.upper()}")
        if env:
            cfg[k] = int(env) if k in ("port", "local_port") else float(env) if k == "ring_timeout" else env
    return cfg


def save(cfg: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    fd = os.open(PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in cfg.items() if k in FIELDS}, f, ensure_ascii=False, indent=1)


def sip_config(cfg: dict):
    from outbound.sip import SipConfig
    return SipConfig(host=cfg["host"], port=int(cfg.get("port") or 5060), user=cfg.get("user") or "ai",
                     password=cfg.get("password") or "", local_ip=cfg.get("local_ip") or "",
                     local_port=int(cfg.get("local_port") or 0), prefix=cfg.get("prefix") or "",
                     ring_timeout=float(cfg.get("ring_timeout") or 40))


def ready(cfg: dict | None = None) -> tuple[bool, str]:
    """Одоо залгаж болох эсэх + тайлбар (вэбэд харуулна)."""
    cfg = cfg or load()
    if cfg["mode"] == "sip":
        if not cfg.get("host"):
            return False, "GSM gateway-ийн хаяг (IP) оруулаагүй"
        from outbound.sip import ping
        ok, detail = ping(sip_config(cfg))
        return ok, f"GSM gateway хариулж байна ({detail})" if ok else f"GSM gateway хариу өгөхгүй байна: {detail}"
    if cfg["mode"] == "mac":
        from outbound import mac
        return mac.ready()
    return False, "Гарах дуудлага унтраалттай (admin → залгах тохиргоо)"


def dial(number: str, cfg: dict | None = None):
    """Залгана -> утсаа авбал CallIO. Утсаа аваагүй/завгүй/алдаа бол outbound.sip.SipError."""
    cfg = cfg or load()
    if cfg["mode"] == "sip":
        from outbound.sip import SipCall
        return SipCall(sip_config(cfg), number).dial()
    if cfg["mode"] == "mac":
        from outbound import mac
        return mac.MacCall(number).dial()
    from outbound.sip import SipError
    raise SipError("failed", "гарах дуудлага унтраалттай")
