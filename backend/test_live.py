"""
Бодит горим (SIM_TRUNK_LIVE=1, ./dev.sh --sim): SIM-TRUNK-ийн байгууллагууд дээр шууд ажиллах.

  .venv/bin/python backend/test_live.py

Хуурамч SIM-TRUNK (түр хавтас) дээр: байгууллага, дуудлагыг SIM-TRUNK/tenants-аас уншина, бэлдэлт тэнд бичнэ,
бэлдэх үед AI серверийг түр зогсооно (launchctl-ийг дуурайна), хэрэглэгчид DATA_DIR-д үлдэнэ.
"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SIM = tempfile.mkdtemp(prefix="fake_sim_live_")
os.environ.update(DATA_DIR=tempfile.mkdtemp(prefix="pc_live_"), SIM_TRUNK_LIVE="1", SIM_TRUNK_DIR=SIM, BUILD_STOP_AI="1")

FAKE_TENANT = """
import os
ROOT = os.path.dirname(os.path.abspath(__file__))
TENANTS_DIR = os.path.join(ROOT, "tenants")
class Tenant:
    def __init__(self, slug):
        self.slug, self.dir = slug, os.path.join(TENANTS_DIR, slug)
    def path(self, *parts):
        return os.path.join(self.dir, *parts)
def current():
    return Tenant(os.environ["TENANT"])
"""
FAKE_INGEST = """
import json, os
import tenant
t = tenant.current()
lines = [l.strip() for n in sorted(os.listdir(t.path("knowledge"))) for l in open(t.path("knowledge", n), encoding="utf-8") if l.strip()]
os.makedirs(t.path("knowledge_index"), exist_ok=True)
json.dump({"facts": [{"text": x} for x in lines], "indexed_at": "live"}, open(t.path("knowledge_index", "facts.json"), "w"))
"""
os.makedirs(os.path.join(SIM, "scripts"))
os.makedirs(os.path.join(SIM, ".venv", "bin"))
os.symlink(sys.executable, os.path.join(SIM, ".venv", "bin", "python"))
open(os.path.join(SIM, "tenant.py"), "w").write(FAKE_TENANT)
open(os.path.join(SIM, "scripts", "fake_ingest.py"), "w").write(FAKE_INGEST)
LIVE_TENANT = os.path.join(SIM, "tenants", "pinecone")
os.makedirs(os.path.join(LIVE_TENANT, "knowledge"))
json.dump({"name": "Pinecone Academy (SIM)", "extension": "1000", "plan": "active"},
          open(os.path.join(LIVE_TENANT, "config.json"), "w"), ensure_ascii=False)
open(os.path.join(LIVE_TENANT, "knowledge", "info.md"), "w", encoding="utf-8").write("Сургалт 6 сар.\n")

import accounts  # noqa: E402
import app as server  # noqa: E402
import config  # noqa: E402
import db  # noqa: E402
import eleven  # noqa: E402
import knowledge_jobs  # noqa: E402
import tenant  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

failures: list[str] = []


def check(name: str, ok: bool, detail: object = ""):
    print(f"  {'✓' if ok else '✗'} {name}" + (f"  ({detail})" if not ok and detail != "" else ""))
    if not ok:
        failures.append(name)


def main():
    print("\n[live] SIM-TRUNK-ийн бодит өгөгдөл дээр")
    check("байгууллагууд SIM-TRUNK/tenants-д", config.LIVE and tenant.TENANTS_DIR == os.path.join(SIM, "tenants"))
    accounts.create_user("live-admin", "live-pass-123", role="admin")
    check("хэрэглэгчид манай DATA_DIR-д (SIM-TRUNK-д биш)", accounts.DB.startswith(os.environ["DATA_DIR"])
          and not os.path.exists(os.path.join(SIM, "accounts.db")))
    a = TestClient(server.app)
    a.post("/api/login", json={"email": "live-admin", "password": "live-pass-123"})
    check("SIM-TRUNK-ийн байгууллагын тохиргоо", a.get("/api/org").json().get("name") == "Pinecone Academy (SIM)")

    t = tenant.Tenant("pinecone")
    db.start_call(t.db_path, "live-call-1", "99112233")          # утасны систем бичдэг газар
    calls = a.get("/api/calls").json()
    check("утасны системийн дуудлага шууд харагдана", any(c["uuid"] == "live-call-1" for c in calls), calls[:1])

    # #108-аас хойш AI runtime энэ repo-д: түлхүүр үргэлж DATA_DIR-д (SIM-TRUNK хавтас шаардахгүй)
    check("ElevenLabs түлхүүр DATA_DIR-аас", eleven.KEY_FILE == os.path.join(config.DATA_DIR, "elevenlabs_key"))
    os.makedirs(os.path.join(SIM, "data"), exist_ok=True)
    open(eleven.KEY_FILE, "w").write("sk_" + "x" * 40)
    check("түлхүүртэй гэж харагдана (анхдагч Уянга)", a.get("/api/voice").json()["voice"] == {
        "name": "ElevenLabs", "id": eleven.DEFAULT_VOICE, "model": eleven.MODEL, "has_key": True})

    calls_made: list[list[str]] = []
    plist = os.path.join(SIM, "ai.plist")
    open(plist, "w").write("")
    old = knowledge_jobs.BUILD_STEPS, knowledge_jobs.AI_PLIST, knowledge_jobs.launchctl
    knowledge_jobs.BUILD_STEPS, knowledge_jobs.AI_PLIST = [["scripts/fake_ingest.py"]], plist
    knowledge_jobs.launchctl = lambda args, log: calls_made.append(args) or 0
    try:
        a.post("/api/knowledge/build")
        st = {}
        for _ in range(100):
            st = a.get("/api/knowledge/build").json()
            if not st["running"]:
                break
            time.sleep(0.05)
        facts = json.load(open(os.path.join(LIVE_TENANT, "knowledge_index", "facts.json")))
        check("бэлдэлт SIM-TRUNK-ийн байгууллагын хавтсанд", st.get("state") == "done" and facts["indexed_at"] == "live", st)
        check("манай хавтсанд хуулбар үүсгэхгүй (.sim-runtime, tenants алга)",
              not os.path.exists(os.path.join(os.environ["DATA_DIR"], ".sim-runtime"))
              and not os.path.exists(os.path.join(os.environ["DATA_DIR"], "tenants")))
        check("бэлдэх үед AI түр зогсоод дахин асна", [c[0] for c in calls_made] == ["bootout", "bootstrap"], calls_made)
        calls_made.clear()
        a.post("/api/train")
        for _ in range(100):
            if not a.get("/api/knowledge/build").json()["running"]:
                break
            time.sleep(0.05)
        check("сургалт (train) AI-г зогсоохгүй", calls_made == [], calls_made)
    finally:
        knowledge_jobs.BUILD_STEPS, knowledge_jobs.AI_PLIST, knowledge_jobs.launchctl = old

    print(f"\n{'ТЭНЦЛЭЭ ✓' if not failures else f'ТЭНЦЭЭГҮЙ: {len(failures)} шалгалт'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
