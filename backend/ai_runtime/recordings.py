"""
Хүний бичсэн аудио (scripts/record.py-ээр бичнэ).

Өгүүлбэрийн бичлэг tenants/<slug>/recordings/<hash>.wav байвал build_faq_audio.py, scripts/ingest.py
TTS-ийн оронд түүнийг ашиглана. Hash нь текстээс гардаг тул текст өөрчлөгдвөл
тухайн өгүүлбэрийг дахин бичих шаардлагатай (хуучин бичлэг автоматаар ашиглагдахгүй).
"""
import hashlib
import os

def rec_dir(d: str | None = None) -> str:
    """Байгууллага бүрийн бичлэг: tenants/<slug>/recordings (d=None -> TENANT)."""
    if d or os.getenv("RECORDINGS_DIR"):
        return os.path.abspath(d or os.getenv("RECORDINGS_DIR"))
    import tenant
    return tenant.current().recordings_dir


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def recording_path(text: str, d: str | None = None) -> str:
    return os.path.join(rec_dir(d), f"{text_hash(text)}.wav")


def recording_for(text: str, d: str | None = None) -> str | None:
    path = recording_path(text, d)
    return path if os.path.exists(path) else None
