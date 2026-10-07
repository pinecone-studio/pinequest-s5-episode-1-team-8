"""Утасны товчлуур (DTMF) таних — Goertzel. Дуудлагын дуунд (in-band) ирсэн дохиог олно.

Товч бүр бага (697-941Гц) + өндөр (1209-1633Гц) хоёр давтамжийн нийлбэр. Хүний яриа, чимээ хоёр
давтамжийг ингэж цэвэр гаргадаггүй тул найдвартай (сүлжээний шахалтыг ч давдаг).
"""
import numpy as np

LOW = (697, 770, 852, 941)
HIGH = (1209, 1336, 1477, 1633)
KEYS = ("123A", "456B", "789C", "*0#D")
FRAME_MS = 40          # нэг хэмжилт
MIN_FRAMES = 2         # дор хаяж 80мс тогтвортой (ITU: >= 40мс)


def _power(frame: np.ndarray, sr: int, freq: float) -> float:
    k = 2 * np.cos(2 * np.pi * freq / sr)
    s1 = s2 = 0.0
    for x in frame:
        s1, s2 = x + k * s1 - s2, s1
    return s1 * s1 + s2 * s2 - k * s1 * s2


def frame_digit(frame: np.ndarray, sr: int) -> str | None:
    energy = float(np.dot(frame, frame)) * len(frame) / 2
    if energy < 1e-3:
        return None
    low = [_power(frame, sr, f) for f in LOW]
    high = [_power(frame, sr, f) for f in HIGH]
    li, hi = int(np.argmax(low)), int(np.argmax(high))
    lo_p, hi_p = low[li], high[hi]
    # хоёр давтамж хоёулаа давамгай (нийт энергийн дийлэнх), бусад давтамжаас 4 дахин их, twist < 8 (9дБ)
    if (lo_p + hi_p) < 0.5 * energy or min(lo_p, hi_p) * 8 < max(lo_p, hi_p):
        return None
    if any(p * 4 > lo_p for i, p in enumerate(low) if i != li) or any(p * 4 > hi_p for i, p in enumerate(high) if i != hi):
        return None
    return KEYS[li][hi]


def detect_at(audio: np.ndarray, sr: int) -> list[tuple[str, int]]:
    """(товч, эхэлсэн дээж) — нэг дарах = нэг тэмдэгт."""
    n = int(sr * FRAME_MS / 1000)
    out, current, run, start = [], None, 0, 0
    for i in range(0, len(audio) - n + 1, n):
        d = frame_digit(np.asarray(audio[i:i + n], dtype=np.float64), sr)
        if d == current:
            run += 1
        else:
            current, run, start = d, 1, i
        if d and run == MIN_FRAMES:
            out.append((d, start))
    return out


def detect(audio: np.ndarray, sr: int) -> list[str]:
    """Аудио дахь дарсан товчлуурууд дарааллаар."""
    return [d for d, _ in detect_at(audio, sr)]


def tone(digit: str, sr: int, seconds: float = 0.15, level: float = 0.3) -> np.ndarray:
    """Тест, демо: товчлуурын дохио үүсгэнэ."""
    row = next(i for i, keys in enumerate(KEYS) if digit in keys)
    t = np.arange(int(sr * seconds)) / sr
    return (level * (np.sin(2 * np.pi * LOW[row] * t) + np.sin(2 * np.pi * HIGH[KEYS[row].index(digit)] * t)) / 2).astype(np.float32)
