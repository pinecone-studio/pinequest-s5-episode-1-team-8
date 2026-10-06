"""SIM-TRUNK-ийн бодит knowledge/audio pipeline-ийг tenant бүрээр дараалалд ажиллуулна."""
import os
import queue
import re
import subprocess
import threading
import time

from config import DATA_DIR
from tenant import Tenant

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
JOB_QUEUE: "queue.Queue[str]" = queue.Queue()
LOG_SKIP = re.compile(r"it/s\]|s/it\]|ref_text|gen_text|Converting|Using |Generating|vocab|token :|model :|Batches|Loading weights")
BUILD_STEPS = [["scripts/ingest.py", "--no-audio"], ["scripts/autogen.py"], ["scripts/prebuild_en.py"],
               ["build_faq_audio.py"], ["scripts/ingest.py"], ["scripts/build_en.py"],
               ["scripts/train_selector.py"], ["scripts/audio_qa.py"]]
OPTIONAL = {"scripts/audio_qa.py"}


def sim_root() -> str:
    configured = os.getenv("SIM_TRUNK_DIR")
    if configured:
        return os.path.abspath(configured)
    project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(os.path.dirname(project), "SIM-TRUNK")


def log_path(t: Tenant) -> str:
    return t.path("data", "job.log")


def _run(slug: str):
    root, tenant = sim_root(), Tenant(slug)
    python = os.path.join(root, ".venv", "bin", "python")
    job = JOBS[slug]
    job.update(state="running", started=time.time())
    os.makedirs(os.path.dirname(log_path(tenant)), exist_ok=True)
    code = 0
    with open(log_path(tenant), "w", encoding="utf-8") as log:
        if not os.path.isfile(python):
            log.write(f"SIM-TRUNK Python орчин олдсонгүй: {python}\n")
            code = -1
        else:
            env = {**os.environ, "DATA_DIR": DATA_DIR, "TENANT": slug, "HF_HUB_OFFLINE": "1",
                   "PYTHONUNBUFFERED": "1", "TTS_CANDIDATES": os.getenv("TTS_CANDIDATES", "1")}
            for step in BUILD_STEPS:
                log.write(f"\n=== {' '.join(step)} ===\n")
                log.flush()
                code = subprocess.call([python, "-W", "ignore", *step], cwd=root, env=env,
                                       stdout=log, stderr=subprocess.STDOUT)
                if code and step[0] in OPTIONAL:
                    log.write(f"({step[0]} алдаатай дууслаа, алгаслаа)\n")
                    code = 0
                if code:
                    break
    job.update(state="done" if code == 0 else "error", finished=time.time(), code=code)


def _worker():
    while True:
        slug = JOB_QUEUE.get()
        try:
            _run(slug)
        except Exception as exc:
            JOBS[slug].update(state="error", finished=time.time(), code=-1, error=str(exc))
        finally:
            JOB_QUEUE.task_done()


threading.Thread(target=_worker, daemon=True).start()


def enqueue(t: Tenant) -> dict:
    with JOBS_LOCK:
        current = JOBS.get(t.slug)
        if current and current["state"] in ("queued", "running"):
            raise RuntimeError("Энэ байгууллагын ажил дараалалд байна")
        JOBS[t.slug] = {"state": "queued", "queued_at": time.time(), "started": None,
                        "finished": None, "code": None}
        JOB_QUEUE.put(t.slug)
    return status(t)


def status(t: Tenant) -> dict:
    job = JOBS.get(t.slug) or {"state": "idle", "code": None, "finished": None}
    queued_at = job.get("queued_at", 0)
    ahead = sum(1 for slug, item in JOBS.items() if slug != t.slug and item["state"] == "running")
    ahead += sum(1 for slug, item in JOBS.items() if slug != t.slug and item["state"] == "queued"
                 and item.get("queued_at", 0) < queued_at)
    lines = []
    if os.path.isfile(log_path(t)):
        with open(log_path(t), encoding="utf-8", errors="replace") as file:
            lines = [line.rstrip() for line in file if line.strip() and not LOG_SKIP.search(line)]
    return {**job, "running": job["state"] in ("queued", "running"),
            "ahead": ahead if job["state"] == "queued" else 0, "log": lines[-25:]}
