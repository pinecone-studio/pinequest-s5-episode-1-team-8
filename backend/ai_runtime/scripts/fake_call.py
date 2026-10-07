"""
Утасгүйгээр AI сервер рүү (AudioSocket 9092) хуурамч дуудлага хийнэ: WAV файлуудыг
залгагчийн яриа болгон илгээж, AI-ийн хариуг хүлээнэ. Лог, вэбийг шалгахад.

  .venv/bin/python scripts/fake_call.py [--tenant slug] асуулт1.wav асуулт2.wav ...
"""
import asyncio
import struct
import sys
import time
import uuid

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

AUDIO, HANGUP = 0x10, 0x00


def pcm8k(path: str) -> bytes:
    wav, sr = sf.read(path, dtype="float32", always_2d=True)
    wav = resample_poly(wav.mean(axis=1), 8000, sr)
    return (np.clip(wav, -1, 1) * 32767).astype("<i2").tobytes()


async def main(paths, tenant=None):
    reader, writer = await asyncio.open_connection("127.0.0.1", 9092)
    if tenant:                     # sip_bridge-ийн адил: аль байгууллага руу залгаж байгаа вэ
        writer.write(b"\x02" + struct.pack(">H", len(tenant)) + tenant.encode())
    writer.write(b"\x01" + struct.pack(">H", 16) + uuid.uuid4().bytes)
    last_rx = [time.monotonic()]
    received = [0]

    async def rx():
        try:
            while True:
                head = await reader.readexactly(3)
                n = struct.unpack(">H", head[1:])[0]
                await reader.readexactly(n)
                if head[0] == AUDIO:
                    last_rx[0] = time.monotonic()
                    received[0] += 1
        except asyncio.IncompleteReadError:
            pass

    async def send(pcm: bytes):
        for i in range(0, len(pcm), 320):
            writer.write(bytes([AUDIO]) + struct.pack(">H", 320) + pcm[i:i + 320].ljust(320, b"\0"))
            await writer.drain()
            await asyncio.sleep(0.02)

    async def wait_ai(limit=60):
        t = time.monotonic()
        await asyncio.sleep(1.0)
        while time.monotonic() - last_rx[0] < 1.5 and time.monotonic() - t < limit:
            await asyncio.sleep(0.2)
        await asyncio.sleep(1.0)   # echo tail

    asyncio.create_task(rx())
    await wait_ai()
    print(f"мэндчилгээ: {received[0]} frame")
    for p in paths:
        before = received[0]
        await send(pcm8k(p) + bytes(320 * 40))
        await wait_ai()
        print(f"{p}: AI {received[0] - before} frame хариулсан")
    writer.write(bytes([HANGUP, 0, 0]))
    await writer.drain()
    writer.close()


args = sys.argv[1:]
slug = None
if args[:1] == ["--tenant"]:
    slug, args = args[1], args[2:]
asyncio.run(main(args, slug))
