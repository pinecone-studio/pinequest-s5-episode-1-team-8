"""
Лавлах хоолойгоор (voices/custom.wav) жишээ өгүүлбэр үүсгэж сонсох. Вэбийн "Туршиж сонсох" товч.

  .venv/bin/python scripts/voice_preview.py     # -> data/preview/0.wav, 1.wav, 2.wav

Хурдан байлгахын тулд best-of-N хийхгүй (seed 0).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["TTS_CANDIDATES"] = "1"

import soundfile as sf  # noqa: E402

from stream_voice import OronTTS  # noqa: E402

SAMPLES = [
    "Сайн байна уу. Pinecone Academy байна. Танд юугаар туслах вэ?",
    "Төлбөрийг хоёроос гурав хувааж төлж болох бөгөөд хөтөлбөр эхлэхээс өмнө эхний төлбөрөө төлнө.",
    "Түр хүлээгээрэй, шалгаад хэлье.",
]
OUT = os.path.join(ROOT, "data", "preview")

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        os.remove(os.path.join(OUT, f))
    tts = OronTTS()
    print("Лавлах хоолой:", tts.ref_file)
    for i, text in enumerate(SAMPLES):
        wav, sr = tts.synth(text)
        sf.write(os.path.join(OUT, f"{i}.wav"), wav, sr)
        print(f"[{i + 1}/{len(SAMPLES)}] {text}", flush=True)
    print("Дууслаа")
