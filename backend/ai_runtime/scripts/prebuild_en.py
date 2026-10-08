"""
Аудио бэлдэхийн өмнөх шат: бүх англи хэсгийг ("Pinecone Academy", "A I", "CV"...) ЗӨВХӨН англи
моделиор үүсгэж data/en_cache/-д хадгална. Дараа нь build_faq_audio, ingest монгол моделиор
ганцаараа ажиллаж англи хэсгийг кэшээс авна (8GB санах ойд хоёр модель зэрэг багтахгүй).

  .venv/bin/python scripts/prebuild_en.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import record  # noqa: E402  (тоглогдох бүх өгүүлбэрийн жагсаалт)
from stream_voice import OronTTS, engine_for, split_language, spoken  # noqa: E402

if __name__ == "__main__":
    # дуудлагын толийг хэрэглэсний дараах англи хэсгүүд ("QPay" -> "Q Pay")
    # ElevenLabs-аар бэлдэх өгүүлбэрүүд англи үгээ өөрөө уншина -> зөвхөн Oron-ых
    segs = sorted({seg for _, text in record.all_texts() if engine_for(text) == "oron"
                   for seg, en in split_language(spoken(text)) if en})
    if not segs:                 # Oron-гүй (устгасан) эсвэл бүгд ElevenLabs -> Oron ачаалахгүй
        print("Oron-оор бэлдэх англи хэсэг алга -> алгаслаа")
        sys.exit(0)
    tts = OronTTS()          # монгол моделийг ачаалахгүй (lazy)
    if not tts.en_ckpt:
        sys.exit("Англи модель (F5TTS_v1_Base) алга -> англи хэсгийг Oron уншина")
    todo = [s for s in segs if not os.path.exists(tts.en_cache_path(s))]
    print(f"Англи хэсэг: {len(segs)}, кэшээс {len(segs) - len(todo)}, шинээр {len(todo)}")
    for i, seg in enumerate(todo, 1):
        tts._synth_en(seg)
        print(f"  [{i}/{len(todo)}] {seg}", flush=True)
    print("Дууслаа")
