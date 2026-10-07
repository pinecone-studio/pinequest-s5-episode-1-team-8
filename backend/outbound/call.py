"""Залгагчаас үл хамаарах дуудлагын суурь: ирж буй дууг хадгалж товчлуур (DTMF) таних, тоглуулах.

Залгагч бүр (SIP/GSM gateway, Mac) энэ классаас удамшиж _send_audio, _hangup-ийг хэрэгжүүлнэ.
Ирсэн дууг _feed() (8kHz float), сигналаар ирсэн товчлуурыг _event() (RFC 4733, SIP INFO)-ээр өгнө.
"""
import threading
import time
from math import gcd

import numpy as np
from scipy.signal import resample_poly

from outbound import dtmf

SR = 8000          # утасны дуу (PCMU/PCMA)


def to_rate(audio: np.ndarray, sr: int, target: int = SR) -> np.ndarray:
    if sr == target:
        return audio.astype(np.float32)
    g = gcd(target, sr)
    return resample_poly(audio, target // g, sr // g).astype(np.float32)


class CallIO:
    """Session (outbound/session.py)-д харагдах интерфейс."""

    def __init__(self):
        self._lock = threading.Lock()
        self._inbound: list[np.ndarray] = []
        self._base = 0               # self._inbound[0]-ийн үнэмлэхүй байрлал (дээж)
        self._scan_from = 0          # товчлуур хайсан байрлал (буферт)
        self._samples = 0
        self._last_tone = -SR        # сүүлд таньсан товчлуурын үнэмлэхүй байрлал (давхар тоолохгүй)
        self._digits: list[str] = []
        self.ended = threading.Event()       # нөгөө тал тасалсан

    # ---- залгагч дуудна ----
    def _feed(self, audio8k: np.ndarray):
        with self._lock:
            self._inbound.append(audio8k)
            self._samples += len(audio8k)

    def _event(self, digit: str):
        with self._lock:
            self._digits.append(digit)

    # ---- session дуудна ----
    def _scan(self):
        """Шинэ ирсэн дуунаас товчлуур (давхцалтай: дохио хоёр хэсэгт хуваагдаж болно)."""
        with self._lock:
            if not self._inbound:
                return
            audio = np.concatenate(self._inbound)
            start = max(0, self._scan_from - int(SR * 0.12))
            found = dtmf.detect_at(audio[start:], SR) if len(audio) - start >= SR * 0.08 else []
            for d, pos in found:
                at = self._base + start + pos
                if at - self._last_tone > SR * 0.2:          # ижил дохиог давхцалтай хэсэгт дахин тоолохгүй
                    self._digits.append(d)
                    self._last_tone = at
            self._scan_from = len(audio)
            keep = int(SR * 0.5)                     # санах ойд сүүлийн хэсэг л
            if len(audio) > keep:
                self._base += len(audio) - keep
                self._inbound, self._scan_from = [audio[-keep:]], keep
            else:
                self._inbound = [audio]

    def digits(self) -> list[str]:
        """Өмнөх дуудлагаас хойш дарсан товчлуурууд (сигнал + дуун дахь)."""
        self._scan()
        with self._lock:
            out, self._digits = self._digits, []
        return out

    def collect(self, seconds: float) -> list[str]:
        """Товчлуур хүлээнэ (дармагц буцна). Нөгөө тал тасалбал хоосон."""
        end = time.monotonic() + seconds
        while time.monotonic() < end and not self.ended.is_set():
            found = self.digits()
            if found:
                return found
            time.sleep(0.05)
        return self.digits()

    def play(self, audio: np.ndarray, sr: int):
        """Дуу тоглуулна (дуустал хүлээнэ). Энэ хугацаанд дарсан товчлуур хадгалагдана."""
        if not self.ended.is_set():
            self._send_audio(to_rate(audio, sr))

    def hangup(self):
        self._hangup()

    # ---- залгагч хэрэгжүүлнэ ----
    def _send_audio(self, audio8k: np.ndarray):
        raise NotImplementedError

    def _hangup(self):
        raise NotImplementedError
