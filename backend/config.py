"""Нийтлэг тохиргоо.

Бүх байгууллагын өгөгдөл DATA_DIR-д (git-д орохгүй), AI engine-ийн эх код
backend/ai_runtime-д байна. Төсөл ажиллахдаа гаднын SIM-TRUNK хавтас шаардахгүй.

SIM_TRUNK_DIR / SIM_TRUNK_LIVE нь зөвхөн хуучин integration test болон шилжилтийн
үеийн нийцтэй байдлыг хадгалсан тохиргоо; ердийн ажиллуулалтад ашиглахгүй.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_DIR", os.path.join(HERE, "data"))
AI_RUNTIME_DIR = os.path.join(HERE, "ai_runtime")
LIVE = os.getenv("SIM_TRUNK_LIVE") == "1"
SIM_TRUNK_DIR = os.path.abspath(os.getenv("SIM_TRUNK_DIR") or AI_RUNTIME_DIR)
TENANTS_DIR = os.path.join(SIM_TRUNK_DIR, "tenants") if LIVE else os.path.join(DATA_DIR, "tenants")
