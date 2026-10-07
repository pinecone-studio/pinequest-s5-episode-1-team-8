"""
Утасгүйгээр SIP-ийн бүх замыг турших: Zoiper шиг sip_bridge.py руу INVITE илгээж, WAV-ийг PCMU RTP-ээр
"ярьж", AI-ийн хариу RTP-г тоолно. Дотуур дугаар -> байгууллага чиглүүлэлтийг шалгахад.

  .venv/bin/python scripts/sip_test.py 1001 асуулт.wav [асуулт2.wav ...]
"""
import asyncio
import random
import re
import socket
import struct
import sys
import time
import uuid
import warnings

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import audioop

SIP = ("127.0.0.1", 5060)


def invite(ext: str, rtp_port: int, call_id: str, tag: str) -> bytes:
    sdp = (f"v=0\r\no=- 1 1 IN IP4 127.0.0.1\r\ns=test\r\nc=IN IP4 127.0.0.1\r\nt=0 0\r\n"
           f"m=audio {rtp_port} RTP/AVP 0 101\r\na=rtpmap:0 PCMU/8000\r\na=rtpmap:101 telephone-event/8000\r\n")
    return (f"INVITE sip:{ext}@127.0.0.1 SIP/2.0\r\nVia: SIP/2.0/UDP 127.0.0.1:5099;branch=z9hG4bK{tag}\r\n"
            f"From: <sip:sip-test@127.0.0.1>;tag={tag}\r\nTo: <sip:{ext}@127.0.0.1>\r\nCall-ID: {call_id}\r\n"
            f"CSeq: 1 INVITE\r\nContact: <sip:sip-test@127.0.0.1:5099>\r\nContent-Type: application/sdp\r\n"
            f"Content-Length: {len(sdp)}\r\n\r\n{sdp}").encode()


def simple(method: str, ext: str, call_id: str, tag: str, to_tag: str, cseq: int) -> bytes:
    return (f"{method} sip:{ext}@127.0.0.1 SIP/2.0\r\nVia: SIP/2.0/UDP 127.0.0.1:5099;branch=z9hG4bK{uuid.uuid4().hex[:8]}\r\n"
            f"From: <sip:sip-test@127.0.0.1>;tag={tag}\r\nTo: <sip:{ext}@127.0.0.1>;tag={to_tag}\r\n"
            f"Call-ID: {call_id}\r\nCSeq: {cseq} {method}\r\nContent-Length: 0\r\n\r\n").encode()


def ulaw_frames(path: str) -> list[bytes]:
    wav, sr = sf.read(path, dtype="float32", always_2d=True)
    pcm = (np.clip(resample_poly(wav.mean(axis=1), 8000, sr), -1, 1) * 32767).astype("<i2").tobytes()
    pcm += bytes(320 * 40)                          # 0.8с чимээгүй -> өгүүлбэр дууссан
    return [audioop.lin2ulaw(pcm[i:i + 320].ljust(320, b"\0"), 2) for i in range(0, len(pcm), 320)]


async def main(ext: str, wavs: list[str]):
    sip = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sip.bind(("127.0.0.1", 5099))
    sip.settimeout(5)
    rtp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rtp.bind(("127.0.0.1", 0))
    rtp.setblocking(False)
    call_id, tag = uuid.uuid4().hex, uuid.uuid4().hex[:8]
    sip.sendto(invite(ext, rtp.getsockname()[1], call_id, tag), SIP)
    while True:
        data = sip.recv(4096).decode(errors="replace")
        code = int(data.split(" ", 2)[1])
        if code >= 200:
            break
    if code != 200:
        print(f"SIP {code}: {data.splitlines()[0]}")
        return code
    to_tag = re.search(r"^To:.*;tag=([^;\r\n]+)", data, re.M | re.I).group(1)
    port = int(re.search(r"^m=audio (\d+)", data, re.M).group(1))
    sip.sendto(simple("ACK", ext, call_id, tag, to_tag, 1), SIP)
    print(f"SIP 200 OK -> RTP 127.0.0.1:{port}")

    received = [0]
    seq, ts, ssrc = random.randint(0, 9999), 0, random.randint(0, 2**31)

    async def rx(seconds: float):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                while True:
                    rtp.recvfrom(2048)
                    received[0] += 1
            except BlockingIOError:
                pass
            await asyncio.sleep(0.02)

    async def send(frames):
        nonlocal seq, ts
        for f in frames:
            rtp.sendto(struct.pack(">BBHII", 0x80, 0, seq & 0xFFFF, ts & 0xFFFFFFFF, ssrc) + f, ("127.0.0.1", port))
            seq, ts = seq + 1, ts + 160
            try:
                while True:
                    rtp.recvfrom(2048)
                    received[0] += 1
            except BlockingIOError:
                pass
            await asyncio.sleep(0.02)

    silence = [audioop.lin2ulaw(bytes(320), 2)] * 50
    await send(silence * 4)                         # AI холбогдож мэндчилгээ тоглуулна
    await rx(9)
    print(f"мэндчилгээ: {received[0]} RTP пакет")
    for w in wavs:
        before = received[0]
        await send(ulaw_frames(w))
        await rx(12)
        print(f"{w.split('/')[-1]}: AI {received[0] - before} пакет ({(received[0] - before) * 0.02:.1f}с) хариулсан")
    sip.sendto(simple("BYE", ext, call_id, tag, to_tag, 2), SIP)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1], sys.argv[2:])) or 0)
