"""Нийтлэг тохиргоо.

Бүх байгууллагын өгөгдөл DATA_DIR-д (git-д орохгүй), AI engine-ийн эх код
backend/ai_runtime-д байна. Төсөл ажиллахдаа гаднын SIM-TRUNK хавтас шаардахгүй.

SIM_TRUNK_DIR / SIM_TRUNK_LIVE нь зөвхөн хуучин integration test болон шилжилтийн
үеийн нийцтэй байдлыг хадгалсан тохиргоо; ердийн ажиллуулалтад ашиглахгүй.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

ENV_FILE = os.path.join(os.path.dirname(HERE), ".env")


def load_env(path: str = ENV_FILE) -> None:
    """Repo-ийн .env (SMS_API_KEY, SMS_API_TOKEN гэх мэт). ./dev.sh уншдаг ч launchd-ийн
    үйлчилгээ (install_services.sh) уншдаггүй байсан -> SMS (бүртгэлийн код, сануулга) явдаггүй байв.
    Орчинд аль хэдийн байгаа утгыг дарахгүй."""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_env()
DATA_DIR = os.getenv("DATA_DIR", os.path.join(HERE, "data"))
AI_RUNTIME_DIR = os.path.join(HERE, "ai_runtime")
LIVE = os.getenv("SIM_TRUNK_LIVE") == "1"
SIM_TRUNK_DIR = os.path.abspath(os.getenv("SIM_TRUNK_DIR") or AI_RUNTIME_DIR)
TENANTS_DIR = os.path.join(SIM_TRUNK_DIR, "tenants") if LIVE else os.path.join(DATA_DIR, "tenants")
