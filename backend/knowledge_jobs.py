"""SIM-TRUNK-ийн бодит knowledge/audio pipeline-ийг tenant бүрээр дараалалд ажиллуулна.

Скрипт бүр sim_runner.py-ээр дамжиж МАНАЙ байгууллагын хавтас (backend/data/tenants/<slug>) дээр ажиллана."""
import os
import queue
import re
import subprocess
import threading
import time

from config import DATA_DIR, TENANTS_DIR
from tenant import Tenant

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
JOB_QUEUE: "queue.Queue[str]" = queue.Queue()
LOG_SKIP = re.compile(r"it/s\]|s/it\]|ref_text|gen_text|Converting|Using |Generating|vocab|token :|model :|Batches|Loading weights")
BUILD_STEPS = [["scripts/ingest.py", "--no-audio"], ["scripts/autogen.py"], ["scripts/prebuild_en.py"],
               ["build_faq_audio.py"], ["scripts/ingest.py"], ["scripts/build_en.py"],
               ["scripts/train_selector.py"], ["scripts/audio_qa.py"]]
TASK_STEPS = {
    "build": BUILD_STEPS,
    "train": [["scripts/train_selector.py"]],
    "english": [["scripts/prebuild_en.py"], ["scripts/build_en.py"], ["scripts/audio_qa.py"]],
    "regen": [["build_faq_audio.py"], ["scripts/ingest.py"], ["scripts/audio_qa.py"]],
}
OPTIONAL = {"scripts/audio_qa.py"}
RUNNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sim_runner.py")


def sim_root() -> str:
    configured = os.getenv("SIM_TRUNK_DIR")
    if configured:
        return os.path.abspath(configured)
    project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(os.path.dirname(project), "SIM-TRUNK")


def tts_cache() -> str:
    """SIM-TRUNK-ийн нийтлэг TTS кэш (ingest аудиог энд бичнэ)"""
    return os.path.join(sim_root(), "data", "tts_cache")


def log_path(t: Tenant) -> str:
    return t.path("data", "job.log")


def runtime_root() -> str:
    """SIM-TRUNK кодыг ашиглахдаа өгөгдлийг энэ төслийн DATA_DIR руу холбоно.

    SIM-TRUNK-ийн tenant.py нь өөрийн ROOT/tenants замыг ашигладаг тул эх кодыг
    symlink-ээр runtime хавтсанд харуулж, tenants/data-г манай backend/data руу
    холбоно. Ингэснээр эх SIM-TRUNK-ийн өгөгдлийг өөрчлөхгүй.
    """
    source = sim_root()
    runtime = os.path.join(DATA_DIR, ".sim-runtime")
    os.makedirs(runtime, exist_ok=True)
    for name in os.listdir(source):
        if name in {"tenants", "data", "logs", "voices", ".git", "__pycache__"}:
            continue
        target, link = os.path.join(source, name), os.path.join(runtime, name)
        if not os.path.lexists(link):
            os.symlink(target, link, target_is_directory=os.path.isdir(target))
    for name, target in (("tenants", os.path.join(DATA_DIR, "tenants")), ("data", DATA_DIR)):
        link = os.path.join(runtime, name)
        os.makedirs(target, exist_ok=True)
        if not os.path.lexists(link):
            os.symlink(target, link, target_is_directory=True)
    voices = os.path.join(runtime, "voices")
    if os.path.islink(voices):
        os.unlink(voices)
    os.makedirs(voices, exist_ok=True)
    source_voices = os.path.join(source, "voices")
    if os.path.isdir(source_voices):
        for name in os.listdir(source_voices):
            if name in {"custom.wav", "custom.txt"}:
                continue
            link = os.path.join(voices, name)
            if not os.path.lexists(link):
                os.symlink(os.path.join(source_voices, name), link)
    custom_dir = os.path.join(DATA_DIR, "voices")
    os.makedirs(custom_dir, exist_ok=True)
    for name in ("custom.wav", "custom.txt"):
        link = os.path.join(voices, name)
        if not os.path.lexists(link):
            os.symlink(os.path.join(custom_dir, name), link)
    os.makedirs(os.path.join(runtime, "logs"), exist_ok=True)
    return runtime


def _run(slug: str):
    source, tenant = sim_root(), Tenant(slug)
    python = os.path.join(source, ".venv", "bin", "python")
    job = JOBS[slug]
    job.update(state="running", started=time.time())
    os.makedirs(os.path.dirname(log_path(tenant)), exist_ok=True)
    code = 0
    with open(log_path(tenant), "w", encoding="utf-8") as log:
        if not os.path.isfile(python):
            log.write(f"SIM-TRUNK Python орчин олдсонгүй: {python}\n")
            code = -1
        else:
            root = runtime_root()
            env = {**os.environ, "DATA_DIR": DATA_DIR, "TENANT": slug, "HF_HUB_OFFLINE": "1",
                   "PYTHONUNBUFFERED": "1", "TTS_CANDIDATES": os.getenv("TTS_CANDIDATES", "1")}
            task = job.get("task", "build")
            # BUILD_STEPS нь хуучин integration test болон гаднын тохиргоонд
            # солигдож болдог нийцтэй нэр тул build үед шууд ашиглана.
            for step in BUILD_STEPS if task == "build" else TASK_STEPS[task]:
                log.write(f"\n=== {' '.join(step)} ===\n")
                log.flush()
                code = subprocess.call([python, "-W", "ignore", RUNNER, root, TENANTS_DIR, *step], cwd=root, env=env,
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


def enqueue(t: Tenant, task: str = "build") -> dict:
    if task not in TASK_STEPS:
        raise ValueError(f"Тодорхойгүй ажил: {task}")
    with JOBS_LOCK:
        current = JOBS.get(t.slug)
        if current and current["state"] in ("queued", "running"):
            raise RuntimeError("Энэ байгууллагын ажил дараалалд байна")
        JOBS[t.slug] = {"state": "queued", "task": task, "queued_at": time.time(), "started": None,
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
