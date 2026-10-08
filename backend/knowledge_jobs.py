"""Дотоод AI runtime-ийн knowledge/audio pipeline-ийг tenant бүрээр дараалалд ажиллуулна.

Скрипт бүр sim_runner.py-ээр дамжиж backend/data/tenants/<slug> дээр ажиллана.
AI engine backend/ai_runtime-д хамт хадгалагддаг тул гаднын repository шаардахгүй."""
import os
import queue
import re
import subprocess
import sys
import threading
import time

from config import AI_RUNTIME_DIR, DATA_DIR, LIVE, TENANTS_DIR
from tenant import Tenant

JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
PROCS: dict[str, subprocess.Popen] = {}     # ажиллаж буй алхмын процесс (зогсооход)
CANCELED = -2                                # «Зогсоох» дарсан ажлын код
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
    # Хариулж чадаагүй асуултаас нэмсэн FAQ: шинэ хариултын аудио + selector сургалт.
    # ElevenLabs/build-time TTS ашигладаг тул ажиллаж буй AI серверийг зогсоох шаардлагагүй.
    "answers": [["build_faq_audio.py"], ["scripts/train_selector.py"], ["scripts/audio_qa.py"]],
}
OPTIONAL = {"scripts/audio_qa.py"}
RUNNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sim_runner.py")
# 8GB: AI сервер ажиллаж байхад TTS/загварууд swap-д орно -> бэлдэх хугацаанд түр зогсооно (бүх дуудлага тасарна!).
# SIM-TRUNK web/app.py-тэй ижил. Том серверт BUILD_STOP_AI=0.
AI_LABEL = "mn.pinecone.ai"
AI_PLIST = os.path.expanduser(f"~/Library/LaunchAgents/{AI_LABEL}.plist")
STOP_AI_TASKS = {"build", "regen", "english"}


def sim_root() -> str:
    """AI runtime-ийн эх код. Env override нь хуучин integration test-д үлдсэн."""
    configured = os.getenv("SIM_TRUNK_DIR")
    if configured:
        return os.path.abspath(configured)
    return AI_RUNTIME_DIR


def python_executable(source: str | None = None) -> str:
    """Энэ төслийн Python-ийг ашиглана; fake/legacy runtime өөрийн venv-тэй бол түүнийг хүндэтгэнэ."""
    configured = os.getenv("AI_PYTHON")
    if configured:
        return os.path.abspath(configured)
    bundled = os.path.join(source or sim_root(), ".venv", "bin", "python")
    return bundled if os.path.isfile(bundled) else sys.executable


def ai_libs_ready(python: str) -> bool:
    """«Аудио бэлдэх» -д хэрэгтэй хүнд сангууд (requirements-ai.txt) суусан эсэх. Тест/legacy runtime-д AI_LIBS_CHECK=0."""
    if os.getenv("AI_LIBS_CHECK", "1") == "0":
        return True
    r = subprocess.run([python, "-c", "import torch, sentence_transformers"], capture_output=True)
    return r.returncode == 0


def tts_cache() -> str:
    """Бүх байгууллагын нийтлэг TTS кэш."""
    return os.path.join(sim_root(), "data", "tts_cache") if LIVE else os.path.join(DATA_DIR, "tts_cache")


def log_path(t: Tenant) -> str:
    return t.path("data", "job.log")


def stop_ai(task: str) -> bool:
    return LIVE and task in STOP_AI_TASKS and os.path.exists(AI_PLIST) and os.getenv("BUILD_STOP_AI", "1") == "1"


def launchctl(args: list[str], log) -> int:
    return subprocess.call(["launchctl", *args], stdout=log, stderr=subprocess.STDOUT)


def _symlink(target: str, link: str):
    """Утасны AI, SIP хоёр зэрэг асахад нэг холбоосыг давхар үүсгэж болно -> аль нэг нь үүсгэсэн бол хангалттай."""
    try:
        os.symlink(target, link, target_is_directory=os.path.isdir(target))
    except FileExistsError:
        pass


def runtime_root() -> str:
    """Дотоод AI кодыг DATA_DIR-тэй холбоод тусгаарлагдсан runtime үүсгэнэ.

    AI tenant.py нь ROOT/tenants зам ашигладаг тул кодыг дотоод runtime хавтсанд
    symlink-ээр харуулж, tenants/data-г backend/data руу холбоно.
    """
    source = sim_root()
    if LIVE:
        return source
    runtime = os.path.join(DATA_DIR, ".ai-runtime")
    os.makedirs(runtime, exist_ok=True)
    for name in os.listdir(source):
        if name in {"tenants", "data", "logs", "voices", ".git", "__pycache__"}:
            continue
        target, link = os.path.join(source, name), os.path.join(runtime, name)
        if os.path.islink(link) and os.readlink(link) != target:   # SIM_TRUNK_DIR солигдсон -> шинэ рүү заана
            os.unlink(link)
        if not os.path.lexists(link):
            _symlink(target, link)
    for name, target in (("tenants", os.path.join(DATA_DIR, "tenants")), ("data", DATA_DIR)):
        link = os.path.join(runtime, name)
        os.makedirs(target, exist_ok=True)
        if not os.path.lexists(link):
            _symlink(target, link)
    voices = os.path.join(runtime, "voices")       # Oron-ийн лавлах хоолой (custom.*) ашиглахгүй
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
                _symlink(os.path.join(source_voices, name), link)
    os.makedirs(os.path.join(runtime, "logs"), exist_ok=True)
    return runtime


def _run(slug: str):
    source, tenant = sim_root(), Tenant(slug)
    python = python_executable(source)
    job = JOBS[slug]
    job.update(state="running", started=time.time())
    os.makedirs(os.path.dirname(log_path(tenant)), exist_ok=True)
    code = 0
    with open(log_path(tenant), "w", encoding="utf-8") as log:
        if not os.path.isfile(python):
            log.write(f"AI Python орчин олдсонгүй: {python}\n")
            code = -1
        elif source == AI_RUNTIME_DIR and not ai_libs_ready(python):
            log.write("AI сангууд суугаагүй байна (torch, sentence-transformers, mlx-whisper).\n"
                      "Терминалд нэг удаа: ./dev.sh --ai   (~3GB, 5-15 минут), дараа нь дахин «Бэлдэх» дарна уу.\n")
            code = -1
        else:
            root = runtime_root()
            env = {**os.environ, "DATA_DIR": DATA_DIR, "TENANT": slug, "HF_HUB_OFFLINE": "1",
                   "PYTHONUNBUFFERED": "1", "TTS_CANDIDATES": os.getenv("TTS_CANDIDATES", "1")}
            task = job.get("task", "build")
            stopped = stop_ai(task)
            if stopped:
                launchctl(["bootout", f"gui/{os.getuid()}/{AI_LABEL}"], log)
                log.write("AI сервер түр зогслоо (санах ой чөлөөлөх)\n")
                log.flush()
            try:
                # BUILD_STEPS нь хуучин integration test болон гаднын тохиргоонд
                # солигдож болдог нийцтэй нэр тул build үед шууд ашиглана.
                for step in BUILD_STEPS if task == "build" else TASK_STEPS[task]:
                    if job.get("cancel"):
                        break
                    log.write(f"\n=== {' '.join(step)} ===\n")
                    log.flush()
                    proc = subprocess.Popen([python, "-W", "ignore", RUNNER, root, TENANTS_DIR, *step], cwd=root, env=env,
                                            stdout=log, stderr=subprocess.STDOUT)
                    PROCS[slug] = proc
                    code = proc.wait()
                    PROCS.pop(slug, None)
                    if job.get("cancel"):
                        break
                    if code and step[0] in OPTIONAL:
                        log.write(f"({step[0]} алдаатай дууслаа, алгаслаа)\n")
                        code = 0
                    if code:
                        break
            finally:
                if stopped:
                    launchctl(["bootstrap", f"gui/{os.getuid()}", AI_PLIST], log)
                    log.write("AI сервер дахин асав\n")
        if job.get("cancel"):
            code = CANCELED
            log.write("\n⏹ Зогсоосон. Өмнө бэлдсэн аудио, мэдээлэл хэвээр ажиллана.\n")
    if code == CANCELED:
        job.update(state="canceled", finished=time.time(), code=code)
        return
    if code == 0:
        sync_rag(tenant)
    job.update(state="done" if code == 0 else "error", finished=time.time(), code=code)
    notify_done(tenant, job.get("task", "build"), code)


def cancel(t: Tenant) -> dict:
    """Дараалалд эсвэл ажиллаж буй ажлыг зогсооно. Ажиллаж буй алхмын процессыг унтрааж, AI серверийг буцааж асаана."""
    with JOBS_LOCK:
        job = JOBS.get(t.slug)
        if not job or job["state"] not in ("queued", "running"):
            raise RuntimeError("Зогсоох ажил алга")
        job["cancel"] = True
        _rebuild.discard(t.slug)
        if job["state"] == "queued":                 # ажиллаж эхлээгүй -> шууд
            job.update(state="canceled", finished=time.time(), code=CANCELED)
        proc = PROCS.get(t.slug)
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    return status(t)


def sync_rag(t: Tenant):
    """Байгууллагын RAG-ийг нэг өгөгдлийн санд (receptionist.db · knowledge_docs). SIM-TRUNK-ийн скрипт өөрөө
    бичдэг ч хуучин хувилбартай SIM-TRUNK дээр ажиллаж байсан ч заавал шинэчлэгдэнэ."""
    import rag_store
    try:
        rag_store.sync(t.dir)
    except Exception as exc:
        print(f"  [RAG өгөгдлийн сан] {t.slug}: {exc}")


# ---------------- нэмэлт (SIM-TRUNK-д алга): бэлэн болмогц мэдэгдэл, автомат бэлдэлт ----------------

DONE_TEXT = {"build": "AI ресепшн бэлэн боллоо ✅", "regen": "Аудио шинэчлэгдлээ ✅", "english": "Англи аудио бэлэн боллоо ✅",
             "answers": "Шинэ хариултууд хэрэгжлээ ✅", "train": "AI сургалт дууслаа ✅"}


def notify_done(t: Tenant, task: str, code: int):
    """Ажил дуусахад байгууллагын Telegram групп руу (тохируулсан бол). Алдаа нь ажилд нөлөөлөхгүй."""
    import notify
    try:
        name, ext = t.config().get("name", t.slug), t.config().get("extension")
        if code == 0:
            text = f"{name}: {DONE_TEXT.get(task, 'Ажил дууслаа ✅')}"
            if task == "build" and ext:
                text += f"\nТуршиж залгах: {ext}"
        else:
            text = f"{name}: ⚠️ ажил алдаатай дууслаа (код {code}). Вэбийн «Тохируулах» хэсгийн логийг шалгана уу."
        notify.send(t, text)
    except Exception as exc:                 # мэдэгдэл бэлдэлтийг хэзээ ч унагахгүй
        print(f"  [мэдэгдэл] {t.slug}: {exc}")


AUTO_DELAY = float(os.getenv("AUTO_BUILD_DELAY", "30"))   # сүүлийн өөрчлөлтөөс хойш хүлээх (олон файлыг нэг бэлдэлтэд)
_timers: dict[str, threading.Timer] = {}
_rebuild: set[str] = set()                                 # бэлдэж байх үед өөрчлөгдсөн -> дууссаны дараа дахин


def auto_build_enabled(t: Tenant) -> bool:
    import notify
    return bool(notify.load_settings(t).get("auto_build"))


def schedule_build(t: Tenant):
    """Мэдээлэл/FAQ өөрчлөгдөхөд (автомат бэлдэлт асаалттай бол) AUTO_DELAY секундын дараа "Бэлдэх"."""
    if not auto_build_enabled(t):
        return
    with JOBS_LOCK:
        old = _timers.pop(t.slug, None)
        if old:
            old.cancel()
        timer = threading.Timer(AUTO_DELAY, _auto_fire, args=(t.slug,))
        timer.daemon = True
        _timers[t.slug] = timer
        timer.start()


def _auto_fire(slug: str):
    _timers.pop(slug, None)
    try:
        enqueue(Tenant(slug), "build")
    except RuntimeError:                 # ажил явж байна -> дууссаны дараа дахин бэлдэнэ
        _rebuild.add(slug)


def _worker():
    while True:
        slug = JOB_QUEUE.get()
        if JOBS.get(slug, {}).get("state") == "canceled":   # дараалалд байхдаа зогсоосон
            JOB_QUEUE.task_done()
            continue
        try:
            _run(slug)
        except Exception as exc:
            JOBS[slug].update(state="error", finished=time.time(), code=-1, error=str(exc))
        finally:
            JOB_QUEUE.task_done()
        if slug in _rebuild:
            _rebuild.discard(slug)
            try:
                enqueue(Tenant(slug), "build")
            except RuntimeError:
                pass


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
