"""iMac + iPhone (Continuity) -ээр гарах дуудлага. GSM gateway-гүй үед.

  tel:// -> FaceTime iPhone-оор залгана
  FaceTime: Гаралт (Output) = "BlackHole 2ch"  -> энд уншина (залгагчийн дуу)
            Микрофон (Input) = "BlackHole 16ch" -> энд бичнэ (AI-ийн дуу)
Нөхцөл: BlackHole 2ch + 16ch суусан, iPhone ба iMac нэг Apple ID, "iPhone-ийн дуудлага" асаалттай,
Terminal-д Accessibility эрх (FaceTime-ийн "Залгах"/"Таслах" товчийг дарахад).
"""
import subprocess
import sys
import threading
import time

import numpy as np

from outbound.call import SR, CallIO, to_rate

IN_DEVICE, OUT_DEVICE = "BlackHole 2ch", "BlackHole 16ch"
DEV_SR = 48000
RING_HZ = 425          # Монгол/Европын ringback (дуудлага холбогдохоос өмнөх "дуут дохио")


def _devices() -> list[str]:
    import sounddevice as sd
    return [d["name"] for d in sd.query_devices()]


def ready() -> tuple[bool, str]:
    if sys.platform != "darwin":
        return False, "Зөвхөн macOS дээр"
    try:
        names = _devices()
    except Exception as exc:                 # sounddevice/PortAudio алга
        return False, f"Аудио төхөөрөмж уншиж чадсангүй: {exc}"
    missing = [d for d in (IN_DEVICE, OUT_DEVICE) if not any(d in n for n in names)]
    if missing:
        return False, f"{', '.join(missing)} суугаагүй (https://existential.audio/blackhole/, админ эрх)"
    return True, "iMac + iPhone (BlackHole) бэлэн"


def _osascript(script: str) -> bool:
    return subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10).returncode == 0


CLICK_CALL = '''tell application "System Events" to tell process "FaceTime"
  repeat with b in (buttons of every window)
    if name of b is in {"Call", "Залгах"} then click b
  end repeat
end tell'''


def _ringback(frame: np.ndarray) -> bool:
    """425Гц давамгай (ringback) эсэх."""
    spec = np.abs(np.fft.rfft(frame * np.hanning(len(frame))))
    freqs = np.fft.rfftfreq(len(frame), 1 / SR)
    band = spec[(freqs > RING_HZ - 25) & (freqs < RING_HZ + 25)].sum()
    return band > 0.5 * spec[(freqs > 200) & (freqs < 3400)].sum()


class MacCall(CallIO):
    def __init__(self, number: str):
        super().__init__()
        self.number = "".join(ch for ch in number if ch.isdigit() or ch == "+")
        self._recent: list[np.ndarray] = []
        self._stream_in = self._stream_out = None

    def _on_input(self, indata, frames, t, status):
        mono = indata.mean(axis=1).astype(np.float32)
        audio8k = to_rate(mono, DEV_SR)
        self._feed(audio8k)
        self._recent.append(audio8k)
        self._recent = self._recent[-25:]

    def dial(self, ring_timeout: float = 45) -> "MacCall":
        import sounddevice as sd
        from outbound.sip import SipError
        self._stream_in = sd.InputStream(device=IN_DEVICE, samplerate=DEV_SR, channels=2, callback=self._on_input)
        self._stream_in.start()
        subprocess.run(["open", f"tel://{self.number}"], check=False)
        time.sleep(1.5)
        _osascript(CLICK_CALL)
        # утсаа авсныг таних: ringback сонсогдсоны дараа ringback бус дуу (хүний "Байна уу") эсвэл 2.5с чимээгүй
        start, heard_ring, quiet_since = time.monotonic(), False, None
        while time.monotonic() - start < ring_timeout:
            time.sleep(0.25)
            if not self._recent:
                continue
            frame = np.concatenate(self._recent[-10:])
            rms = float(np.sqrt(np.mean(frame ** 2)))
            if rms > 0.01 and _ringback(frame):
                heard_ring, quiet_since = True, None
            elif rms > 0.02:
                break                                   # хүн ярьж байна -> утсаа авсан
            elif heard_ring:
                quiet_since = quiet_since or time.monotonic()
                if time.monotonic() - quiet_since > 2.5:
                    break
        else:
            self._hangup()
            raise SipError("no_answer", "утсаа аваагүй")
        self._stream_out = sd.OutputStream(device=OUT_DEVICE, samplerate=DEV_SR, channels=2)
        self._stream_out.start()
        return self

    def _send_audio(self, audio8k: np.ndarray):
        audio = to_rate(audio8k, SR, DEV_SR)
        stereo = np.repeat(audio[:, None], 2, axis=1)
        done = threading.Event()

        def write():
            self._stream_out.write(stereo)
            done.set()
        threading.Thread(target=write, daemon=True).start()
        done.wait(len(audio) / DEV_SR + 2)

    def _hangup(self):
        _osascript('tell application "FaceTime" to quit')
        for s in (self._stream_in, self._stream_out):
            if s:
                s.stop()
                s.close()
        self.ended.set()
