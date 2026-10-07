"""
Долоо хоногийн тайлан: тоо, их асуусан сэдэв, хариулж чадаагүй (чимээ шүүнэ), Даваа 09:00 хуваарь, API.

  .venv/bin/python backend/test_report.py
"""
import os
import sys
import tempfile
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.update(DATA_DIR=tempfile.mkdtemp(prefix="pc_rep_"), REPORT_SCHEDULER="0", OUTBOUND_SCHEDULER="0")

import accounts  # noqa: E402
import app as server  # noqa: E402
import db  # noqa: E402
import notify  # noqa: E402
import report  # noqa: E402
import tenant  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

failures: list[str] = []


def check(name: str, ok: bool, detail: object = ""):
    print(f"  {'✓' if ok else '✗'} {name}" + (f"  ({detail})" if not ok and detail != "" else ""))
    if not ok:
        failures.append(name)


def main():
    print("\n[тайлан] Долоо хоногийн тайлан")
    sent: list[str] = []
    notify.send = lambda t, text: sent.append(text) or True
    c = TestClient(server.app)
    c.post("/api/signup", json={"company": "Тайлан тест", "phone": "7011 2233", "email": "rep@example.mn", "password": "rep-pass-123"})
    t = tenant.Tenant(c.get("/api/me").json()["tenant"])
    faq = tenant.load_faq(t)
    price = next(x for x in faq["faq"] if x["id"] == "smalltalk_capabilities")
    tenant.write_json(t.path("knowledge_index", "facts.json"),
                      {"facts": [{"text": "Төлбөр сард нэг сая төгрөг.", "section": "Төлбөр"}]})
    now = time.time()
    with db.connect(t.db_path) as con:
        rows = [("c1", "Юу асууж болох вэ", price["answer"], "faq"), ("c1", "Төлбөр хэд вэ", "Төлбөр сард нэг сая төгрөг.", "model"),
                ("c2", "Үнэ хэд вэ", "Төлбөр сард нэг сая төгрөг.", "fact"), ("c2", "Машины зогсоол бий юу", "Уучлаарай", "repeat"),
                ("c3", "машины  зогсоол бий юу?", "Уучлаарай", "handoff"), ("c3", "а а а", "Уучлаарай", "repeat")]
        for i, (call, q, a, route) in enumerate(rows):
            con.execute("INSERT OR IGNORE INTO calls (uuid, caller, started_at) VALUES (?, '991', ?)", (call, now - 3600 - i))
            con.execute("INSERT INTO messages (call_uuid, ts, role, text) VALUES (?, ?, 'user', ?)", (call, now - 3000 + 2 * i, q))
            con.execute("INSERT INTO messages (call_uuid, ts, role, text, route) VALUES (?, ?, 'assistant', ?, ?)",
                        (call, now - 3000 + 2 * i + 1, a, route))
        con.execute("INSERT INTO calls (uuid, started_at) VALUES ('old', ?)", (now - 30 * 86400,))
    r = c.get("/api/report").json()
    check("тоо: 3 дуудлага (хуучин нь орохгүй), 3/6 хариулсан", r["calls"] == 3 and r["answered"] == 3
          and r["unanswered"] == 3 and r["rate"] == 50, {k: r[k] for k in ("calls", "answered", "unanswered", "rate")})
    check("их асуусан: мэдээллийн гарчиг, FAQ-ийн асуулт", r["topics"] == [["Төлбөр", 2], [price["questions"][0], 1]], r["topics"])
    check("хариулж чадаагүй: давтагдсаныг нэгтгэж, чимээг хасна",
          r["unanswered_top"] == [{"q": "Машины зогсоол бий юу", "count": 2}], r["unanswered_top"])
    check("Telegram-ийн бичвэр", "Тайлан тест" in r["text"] and "зогсоол" in r["text"] and "×2" in r["text"], r["text"])
    check("Telegram тохируулаагүй бол илгээхгүй", c.post("/api/report/send").status_code == 400)
    st = notify.load_settings(t)
    st.update(telegram_token="1:x", telegram_chat_id=5)
    notify.save_settings(t, st)
    monday = datetime(2026, 10, 12, 9, 5, tzinfo=report.TZ).timestamp()
    check("даваа 09:00-аас хойш нэг удаа", report.send_due(monday) == [t.slug] and report.send_due(monday + 3600) == []
          and len(sent) == 1, sent)
    next_monday_8 = datetime(2026, 10, 19, 8, 0, tzinfo=report.TZ).timestamp()
    check("дараагийн даваа 08:00-д хараахан биш, 09:00-д илгээнэ", report.send_due(next_monday_8) == []
          and report.send_due(next_monday_8 + 3600) == [t.slug] and len(sent) == 2, len(sent))
    c.put("/api/report/settings", json={"enabled": False})
    check("унтраавал автоматаар илгээхгүй", report.send_due(monday + 14 * 86400) == [])
    check("одоо илгээх (гараар)", c.post("/api/report/send").status_code == 200 and len(sent) == 3, len(sent))
    print(f"\n{'ТЭНЦЛЭЭ ✓' if not failures else f'ТЭНЦЭЭГҮЙ: {len(failures)} шалгалт'}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
