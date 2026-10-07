"""Нэмэлт (SIM-TRUNK-д алга): "Бэлдэх"-ийн өмнө ElevenLabs-аар ШИНЭЭР үүсэх өгүүлбэрийг тоолно — API дуудахгүй.
SIM-TRUNK-ийн орчинд sim_runner.py-ээр ажиллана (backend/routes/knowledge.py · build_estimate дуудна).
Бэлдэхтэй ижил дүрэм: хүний бичлэг -> TTS кэш (clip_key) -> харьцуулалтын жишээ -> үгүй бол ElevenLabs.
stdout-ын сүүлийн мөр: {"total", "recorded", "cached", "new", "chars", "texts": [...]}
"""
import json
import os

import record
import tenant as tenants
from recordings import recording_for
from stream_voice import clip_key, clip_seed, eleven_sample_path, engine_for, tts_seeds, voice_tag

t, seeds = tenants.current(), tts_seeds()
out = {"total": 0, "recorded": 0, "cached": 0, "new": 0, "chars": 0, "texts": []}
for _, text in record.all_texts():
    out["total"] += 1
    if recording_for(text, t.recordings_dir):
        out["recorded"] += 1
        continue
    engine = engine_for(text)
    seed = clip_seed(text, engine, seeds)
    path = os.path.join(tenants.TTS_CACHE, f"{clip_key(text, seed, voice_tag(engine))}.wav")
    if os.path.exists(path) or (engine == "eleven" and not seed and os.path.exists(eleven_sample_path(text))):
        out["cached"] += 1
    else:
        out["new"] += 1
        out["chars"] += len(text)
        out["texts"].append(text)
out["texts"] = out["texts"][:20]
print(json.dumps(out, ensure_ascii=False))
