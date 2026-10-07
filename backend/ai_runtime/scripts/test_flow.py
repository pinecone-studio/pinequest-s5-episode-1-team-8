"""
Чанга яригчгүйгээр respond() урсгалыг туршина: юу, хэзээ тоглосныг цагтай нь хэвлэж,
хамгийн урт ЧИМЭЭГҮЙ завсрыг хэмжинэ.

  .venv/bin/python scripts/test_flow.py "асуулт 1" "асуулт 2" ...

TENANT=<slug> (default pinecone) байгууллагын индексийг ашиглана.
"""
import asyncio
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stream_voice import LLM_GENERATE, FAQRouter, OronTTS, respond  # noqa: E402


async def run(questions):
    engine = None
    if LLM_GENERATE:
        engine = OronTTS()
        engine.warmup()
    router = FAQRouter()
    executor = ThreadPoolExecutor(max_workers=1)
    history = []

    for q in questions:
        print(f"\n=== Та: {q}")
        t0 = time.perf_counter()
        last_end = t0
        gaps = []

        async def fake_play(wav, sr):
            nonlocal last_end
            start = time.perf_counter()
            gaps.append(start - last_end)
            dur = len(wav) / sr
            print(f"    ♪ {start - t0:5.1f}s  тоглов {dur:4.1f}s  (өмнөх чимээгүй {start - last_end:.1f}s)")
            await asyncio.sleep(dur)          # бодит тоглуулалтын хугацааг дуурайна
            last_end = time.perf_counter()

        reply = await respond(q, history, router, engine, executor, play_fn=fake_play)
        total = time.perf_counter() - t0
        print(f"  AI: {reply}")
        print(f"  Нийт {total:.1f}s | эхний дуу {gaps[0]:.2f}s | "
              f"хамгийн урт чимээгүй {max(gaps):.2f}s")
        history += [{"role": "user", "content": q}, {"role": "assistant", "content": reply}]
        if os.getenv("FRESH") == "1":   # асуулт бүрийг бие даасан дуудлага мэт
            history = []


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1:]))
