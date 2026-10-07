"""Repository доторх утасны AI үйлчилгээг ажиллуулах жижиг launcher.

  .venv/bin/python backend/run_ai.py phone
  .venv/bin/python backend/run_ai.py sip
"""
import os
import sys

import knowledge_jobs
from config import DATA_DIR, TENANTS_DIR

COMMANDS = {"phone": "phone_server.py", "sip": "sip_bridge.py"}


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    script = COMMANDS.get(name)
    if not script:
        options = " | ".join(COMMANDS)
        raise SystemExit(f"Ашиглах: .venv/bin/python backend/run_ai.py [{options}]")

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
