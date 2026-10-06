"""
Нэвтрэлтийн хамгаалалт: session cookie-ийн нэр, буруу оролдлогын хязгаар.

Буруу нууц үг: нэг IP эсвэл нэг и-мэйл рүү 10 минутад 5 удаа -> түр хаана (429). IP-ийн толгойг хуурсан ч
и-мэйлийн хязгаар хэвээр. Буруу оролдлого бүр FAIL_DELAY секунд удаашрна (таахыг удаашруулна).
Хэрэглэгч, нууц үг, session -> accounts.py
"""
import time

COOKIE = "pc_session"
MAX_FAILS, FAIL_WINDOW = 5, 600
FAIL_DELAY = 1.0

_fails: dict[str, list[float]] = {}


def too_many_fails(keys: list[str]) -> bool:
    now = time.time()
    for key in keys:
        _fails[key] = [t for t in _fails.get(key, []) if now - t < FAIL_WINDOW]
    return any(len(_fails[key]) >= MAX_FAILS for key in keys)


def record_fail(keys: list[str]):
    for key in keys:
        _fails.setdefault(key, []).append(time.time())
