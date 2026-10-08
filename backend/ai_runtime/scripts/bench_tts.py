"""
Oron TTS-ийн хурдыг хэмжинэ.

  .venv/bin/python scripts/bench_tts.py            # nfe_step=16
  TTS_NFE_STEP=8 .venv/bin/python scripts/bench_tts.py

RTF (real-time factor) = синтез хийсэн хугацаа / аудионы урт.
RTF < 1 бол ярианаас хурдан -> streaming тоглуулалт тасралтгүй явна.
Гаралтын WAV-ууд bench_out/ хавтаст хадгалагдана (чанарыг чихээр шалгана).
"""
import os
import sys
import time

import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stream_voice import OronTTS, TTS_NFE_STEP  # noqa: E402

SENTENCES = [
    "Сайн байна уу. Pinecone Academy байна.",
    "Түр хүлээгээрэй, шалгаад хэлье.",
    "Software Engineer хөтөлбөр нь зургаан сарын хугацаатай.",
    "Та бүртгүүлэх сонирхолтой байна уу? Таны нэрийг асууж болох уу?",
]


def main():
    os.makedirs("bench_out", exist_ok=True)
    t = time.perf_counter()
    engine = OronTTS()
    print(f"Модель ачаалсан: {time.perf_counter() - t:.1f}s")

    t = time.perf_counter()
    engine.warmup()
    print(f"Warmup: {time.perf_counter() - t:.1f}s  (nfe_step={TTS_NFE_STEP})\n")

    total_synth = total_audio = 0.0
    for i, text in enumerate(SENTENCES):
        t = time.perf_counter()
        wav, sr = engine.synth(text)
        dt = time.perf_counter() - t
        dur = len(wav) / sr
        total_synth += dt
        total_audio += dur
        sf.write(f"bench_out/{TTS_NFE_STEP}_{i}.wav", wav, sr)
        print(f"{dt:5.2f}s синтез / {dur:5.2f}s аудио  RTF={dt / dur:.2f}  {text}")

    print(f"\nДундаж RTF = {total_synth / total_audio:.2f}  (sr={sr})")


if __name__ == "__main__":
    main()
