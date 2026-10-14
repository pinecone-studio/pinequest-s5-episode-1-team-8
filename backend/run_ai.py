"""Repository доторх утасны AI үйлчилгээг ажиллуулах жижиг launcher.

  .venv/bin/python backend/run_ai.py phone
  .venv/bin/python backend/run_ai.py sip
"""
import os
import sys

import knowledge_jobs
from config import DATA_DIR, TENANTS_DIR

COMMANDS = {"phone": "phone_server.py", "sip": "sip_bridge.py"}
ENV_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


def load_env(path: str = ENV_FILE) -> None:
    """Repo-ийн .env (SMS_API_KEY, SMS_API_TOKEN гэх мэт). ./dev.sh уншдаг ч launchd-ийн
    үйлчилгээ (install_services.sh) уншдаггүй байсан -> бүртгэлийн код SMS-ээр явдаггүй байв.
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


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    script = COMMANDS.get(name)
    if not script:
        options = " | ".join(COMMANDS)
        raise SystemExit(f"Ашиглах: .venv/bin/python backend/run_ai.py [{options}]")

    load_env()
    root = knowledge_jobs.runtime_root()
    python = knowledge_jobs.python_executable()
    env = {
        **os.environ,
        "DATA_DIR": DATA_DIR,
        "HF_HUB_OFFLINE": os.getenv("HF_HUB_OFFLINE", "1"),
        "PYTHONUNBUFFERED": "1",
    }
    args = [python, "-W", "ignore", knowledge_jobs.RUNNER, root, TENANTS_DIR, script]
    os.execve(python, args, env)


if __name__ == "__main__":
    main()
