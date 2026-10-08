"""
Интернэтгүй горим: Hugging Face загваруудыг зөвхөн локал кэшээс ачаална, telemetry илгээхгүй.
Загвар ачаалдаг модуль бүр (embed, stt, stream_voice) хамгийн эхэнд нь import хийнэ —
LaunchAgent-аас гадуур гараар ажиллуулсан ч гадагш хандахгүй.

Анх суулгахад (загвар татах) л:  HF_HUB_OFFLINE=0 .venv/bin/python scripts/ingest.py
"""
import os

_off = os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", _off)
os.environ.setdefault("HF_DATASETS_OFFLINE", _off)
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ.setdefault("DO_NOT_TRACK", "1")
