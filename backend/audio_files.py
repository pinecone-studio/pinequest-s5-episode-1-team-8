"""Хөтчөөс ирсэн PCM WAV бичлэгийг хадгалах, тоглуулахад бэлдэх жижиг хэрэгслүүд.

Хүнд numpy/scipy сан backend-д шаардахгүй. AI/TTS pipeline өөрийн SIM-TRUNK
орчноор ажилладаг; энд зөвхөн browser-ийн 16-bit WAV-г mono 24 kHz болгоно.
"""
import audioop
import hashlib
import io
import os
import wave

OUT_RATE = 24_000
TARGET_RMS = int(0.08 * 32767)


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def recording_path(directory: str, text: str) -> str:
    return os.path.join(directory, f"{text_hash(text)}.wav")


def recording_for(directory: str, text: str) -> str | None:
    path = recording_path(directory, text)
    return path if os.path.isfile(path) else None


def _pcm(data: bytes) -> tuple[bytes, int]:
    try:
        with wave.open(io.BytesIO(data), "rb") as src:
            channels, width, rate = src.getnchannels(), src.getsampwidth(), src.getframerate()
            if src.getcomptype() != "NONE" or channels not in (1, 2) or width not in (1, 2, 3, 4):
                raise ValueError
            frames = src.readframes(src.getnframes())
    except (wave.Error, EOFError, ValueError) as exc:
        raise ValueError("Зөв PCM WAV бичлэг оруулна уу") from exc
    if width != 2:
        frames = audioop.lin2lin(frames, width, 2)
    if channels == 2:
        frames = audioop.tomono(frames, 2, 0.5, 0.5)
    return frames, rate


def _clean(frames: bytes, rate: int) -> bytes:
    if len(frames) < int(rate * 0.3) * 2:
        raise ValueError("Бичлэг хэт богино байна")
    frame_bytes = max(1, int(rate * 0.02)) * 2
    levels = [audioop.rms(frames[i:i + frame_bytes], 2)
              for i in range(0, len(frames) - frame_bytes + 1, frame_bytes)]
    if not levels:
        raise ValueError("Дуу сонсогдсонгүй")
    threshold = max(int(0.01 * 32767), int(max(levels) * 0.1))
    voiced = [i for i, level in enumerate(levels) if level > threshold]
    if not voiced:
        raise ValueError("Дуу сонсогдсонгүй")
    start = max(0, voiced[0] * frame_bytes - int(rate * 0.15) * 2)
    end = min(len(frames), (voiced[-1] + 1) * frame_bytes + int(rate * 0.25) * 2)
    frames = frames[start:end]
    if rate != OUT_RATE:
        frames, _ = audioop.ratecv(frames, 2, 1, rate, OUT_RATE, None)
    level = audioop.rms(frames, 2)
    if not level:
        raise ValueError("Дуу сонсогдсонгүй")
    return audioop.mul(frames, 2, min(8.0, TARGET_RMS / level))


def wav_bytes(frames: bytes, rate: int) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as dst:
        dst.setnchannels(1)
        dst.setsampwidth(2)
        dst.setframerate(rate)
        dst.writeframes(frames)
    return out.getvalue()


def save_recording(data: bytes, path: str) -> float:
    frames, rate = _pcm(data)
    frames = _clean(frames, rate)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as file:
        file.write(wav_bytes(frames, OUT_RATE))
    os.replace(tmp, path)
    return len(frames) / 2 / OUT_RATE


def duration(path: str) -> float:
    try:
        with wave.open(path, "rb") as src:
            return src.getnframes() / src.getframerate()
    except (OSError, wave.Error):
        return 0.0


def phone_quality(path: str) -> bytes:
    with open(path, "rb") as file:
        frames, rate = _pcm(file.read())
    if rate != 8000:
        frames, _ = audioop.ratecv(frames, 2, 1, rate, 8000, None)
    frames = audioop.ulaw2lin(audioop.lin2ulaw(frames, 2), 2)
    return wav_bytes(frames, 8000)
