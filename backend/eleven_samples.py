"""
ElevenLabs-аар жишээ аудио үүсгэнэ. Дотоод AI runtime-д sim_runner.py-ээр ажиллана (backend/eleven.py дуудна):
AI runtime-ийн ElevenTTS тоо, цагийг үгээр болгож, дуудлагын толийг хэрэглээд дууны түвшинг тэнцүүлдэг —
"Аудио бэлдэх"-тэй яг адил аудио гарч, бэлдэх үед ElevenLabs-ийг дахин дуудахгүй.

  stdin:  {"voice": "<voice_id>", "items": [{"hash": "...", "text": "..."}]}
  stdout: мөр бүрт "ok <hash>", алдаа гарвал "error <мессеж>"
  аудио:  tenants/<slug>/data/eleven_samples/<eleven_tag>/<hash>.wav
"""
import json
import os
import sys

import soundfile as sf

import tenant
from stream_voice import ElevenTTS, eleven_tag, tts_engine

job = json.load(sys.stdin)
out_dir = tenant.current().path("data", "eleven_samples", eleven_tag({**tts_engine(), "voice": job["voice"]}))
os.makedirs(out_dir, exist_ok=True)
try:
    tts = ElevenTTS(voice=job["voice"])
    for item in job["items"]:
        wav, sr = tts.synth(item["text"])
        sf.write(os.path.join(out_dir, f"{item['hash']}.wav"), wav, sr)
        print("ok", item["hash"], flush=True)
except Exception as exc:
    print("error", " ".join(str(exc).split())[:300], flush=True)
    sys.exit(1)
