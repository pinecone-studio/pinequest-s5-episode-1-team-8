"""Бичлэг хадгалах, утасны чанараар тоглуулах — SIM-TRUNK-тэй ЯГ ижил алгоритм:
scripts/record.py · clean() (чимээгүй тайрах, 24kHz, түвшин тэнцүүлэх) ба web/app.py · phone_quality() (8kHz μ-law).
"""
import hashlib
import io
import os
import warnings
from math import gcd

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import audioop

MIC_SR = 48000
OUT_SR = 24000          # TTS-тэй ижил -> phone_server 8kHz болгож хөрвүүлнэ
TARGET_RMS = 0.08       # ~ -22 dBFS
PAD_START, PAD_END = 0.15, 0.25


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def recording_path(directory: str, text: str) -> str:
    return os.path.join(directory, f"{text_hash(text)}.wav")


def recording_for(directory: str, text: str) -> str | None:
    path = recording_path(directory, text)
    return path if os.path.isfile(path) else None


def clean(audio: np.ndarray, sr: int = MIC_SR) -> np.ndarray | None:
    """Чимээгүйг тайрч, 24kHz болгож, дууны түвшинг тэнцүүлнэ (вэб бичлэгт ч ашиглана)."""
    if len(audio) < sr * 0.3:
        return None
    frame = int(sr * 0.02)
    n = len(audio) // frame
    rms = np.sqrt((audio[:n * frame].reshape(n, frame) ** 2).mean(axis=1))
    thresh = max(0.01, 0.1 * np.percentile(rms, 95))
    voiced = np.where(rms > thresh)[0]
    if len(voiced) == 0:
        return None
    start = max(0, voiced[0] * frame - int(PAD_START * sr))
    end = min(len(audio), (voiced[-1] + 1) * frame + int(PAD_END * sr))
    g = gcd(OUT_SR, sr)
    audio = resample_poly(audio[start:end], OUT_SR // g, sr // g).astype(np.float32)

    speech = audio[np.abs(audio) > 0.02]
    level = np.sqrt((speech ** 2).mean()) if len(speech) else np.sqrt((audio ** 2).mean())
    audio = audio * (TARGET_RMS / max(level, 1e-4))
    peak = np.abs(audio).max()
    if peak > 0.95:
        audio *= 0.95 / peak
    fade = int(OUT_SR * 0.01)
    audio[:fade] *= np.linspace(0, 1, fade)
    audio[-fade:] *= np.linspace(1, 0, fade)
    return audio


def save_recording(data: bytes, path: str) -> float:
    """Хөтчөөс ирсэн аудио -> clean() -> 24kHz WAV (SIM-TRUNK web/app.py · save_voice). Секунд буцаана."""
    try:
        wav, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    except (sf.LibsndfileError, RuntimeError, TypeError) as exc:
        raise ValueError("Аудио файл уншигдсангүй (WAV оруулна уу)") from exc
    audio = clean(wav.mean(axis=1), sr)
    if audio is None:
        raise ValueError("Дуу сонсогдсонгүй. Микрофоноо шалгана уу.")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(path, audio, OUT_SR)
    return len(audio) / OUT_SR


def phone_quality(path: str) -> bytes:
    """Утсаар сонсогдох шиг: 8kHz руу буулгаж, PCMU (μ-law) кодлоод буцааж задална (sip_bridge-тэй адил)."""
    wav, sr = sf.read(path, dtype="float32", always_2d=True)
    g = gcd(8000, sr)
    pcm = (np.clip(resample_poly(wav.mean(axis=1), 8000 // g, sr // g), -1, 1) * 32767).astype("<i2").tobytes()
    pcm = audioop.ulaw2lin(audioop.lin2ulaw(pcm, 2), 2)
    buf = io.BytesIO()
    sf.write(buf, np.frombuffer(pcm, "<i2"), 8000, format="WAV", subtype="PCM_16")
    return buf.getvalue()
