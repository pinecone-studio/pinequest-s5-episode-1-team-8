"""Сануулгын дуудлагын аудио (ElevenLabs, байгууллагын хоолой) — SIM-TRUNK-ийн орчинд sim_runner.py-ээр.
SIM-TRUNK-ийн ElevenTTS: тоо, цагийг үгээр болгож, дуудлагын толийг хэрэглэнэ ("Аудио бэлдэх"-тэй ижил дуу).

  stdin:  {"items": [{"hash": "...", "text": "..."}], "out": "<хавтас>"}
  stdout: мөр бүрт "ok <hash>", алдаа гарвал "error <мессеж>"
"""
import json
import os
import sys

import soundfile as sf

from stream_voice import ElevenTTS

job = json.load(sys.stdin)
os.makedirs(job["out"], exist_ok=True)
try:
    tts = ElevenTTS()
    for item in job["items"]:
        wav, sr = tts.synth(item["text"])
        sf.write(os.path.join(job["out"], f"{item['hash']}.wav"), wav, sr)
        print("ok", item["hash"], flush=True)
except Exception as exc:
    print("error", " ".join(str(exc).split())[:300], flush=True)
    sys.exit(1)
