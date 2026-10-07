"""
AI туслах (хувийн RAG) тест: хүн өөрийн бүртгэлийг, ажилтан бусдын бүртгэлийг AI-аар өөрчилнө.

  .venv/bin/python backend/test_assistant.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="pc_asst_")
os.environ["OUTBOUND_SCHEDULER"] = "0"

import app as server  # noqa: E402
import assistant  # noqa: E402
import people  # noqa: E402
import tenant  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

failures: list[str] = []


def check(name: str, ok: bool, detail: object = ""):
    print(f"  {'✓' if ok else '✗'} {name}{f'  ({detail})' if not ok and detail != '' else ''}")
    if not ok:
        failures.append(name)


def client(company: str = "Pinecone Academy", email: str = "asst@example.mn") -> tuple[TestClient, tenant.Tenant]:
    server.SIGNUPS.clear()
    c = TestClient(server.app)
    r = c.post("/api/signup", json={"company": company, "email": email, "password": "secret-pass-1"})
    assert r.status_code == 200, r.text
    t = tenant.Tenant(r.json()["tenant"])
    os.makedirs(t.knowledge_dir, exist_ok=True)
    with open(os.path.join(t.knowledge_dir, "info.md"), "w", encoding="utf-8") as f:
        f.write("# Сургалт\nSoftware Engineer хөтөлбөр 6 сар үргэлжилнэ.\nСургалтын төлбөр сард 1,500,000 төгрөг.\n"
                "Хичээл өдөр бүр 9 цагаас эхэлнэ.\n# Эвент\nAI Hackathon эвент 10 сарын 18-нд болно.\n")
    return c, t


def say(c: TestClient, sid: str | None, text: str | None = None, dtmf: str | None = None, mode: str = "caller") -> dict:
    r = c.post("/api/assistant", json={"session": sid, "text": text, "dtmf": dtmf, "mode": mode})
    assert r.status_code == 200, r.text
    return r.json()


def main():
    c, t = client()
    print("\n[1] Жишээ бүртгэлүүд (хөтөлбөр, эвент)")
    r = c.post("/api/assistant/samples").json()
    ppl = {p["name"]: p for p in r["people"][:3]}
    check("Болд — Bootcamp, Номин, Сараа — эвент", ppl["Болд"]["course"].startswith("Software Engineer")
          and ppl["Номин"]["course"] == "AI Hackathon эвент", list(ppl))
    check("хүн бүр код, хувийн баримттай (RAG)", all(len(p["code"]) == 4 and len(p["docs"]) >= 4 for p in ppl.values()))
    check("Болд товлосон цагтай", ppl["Болд"]["appointment"] is not None)

    print("\n[2] Эвентэд очиж чадахгүй боллоо -> бүртгэл цуцлах")
    r = say(c, None, "Эвентэд очиж чадахгүй боллоо")
    sid = r["session"]
    check("хүсэлтийг таньж код асууна", r["replies"] == [t.phrases()["account"]["ask_code"]] and r["state"] == "code", r)
    check("RAG trace: хүсэлт", r["trace"] and r["trace"][0]["kind"].startswith("хүсэлт"), r["trace"][:1])
    r = say(c, sid, dtmf=ppl["Номин"]["code"])
    check("баталгаажаад эвентийг уншиж асууна", r["replies"][0] == "Баталгаажлаа." and "AI Hackathon эвент" in r["replies"][1]
          and r["state"] == "reg_cancel_confirm" and r["person"]["name"] == "Номин", r["replies"])
    check("батлахаас өмнө өөрчлөөгүй", people.lead(t.dir, ppl["Номин"]["id"])["status"] == "new")
    r = say(c, sid, "тийм")
    check("цуцаллаа", r["replies"][0] == t.phrases()["account"]["reg_cancel_done"], r["replies"])
    check("өгөгдлийн сан: төлөв canceled", people.lead(t.dir, ppl["Номин"]["id"])["status"] == "canceled")
    check("хувийн RAG-ийн баримт шинэчлэгдсэн", any(d["field"] == "status" and "цуцлагдсан" in d["text"]
                                                    for d in r["person"]["docs"]), r["person"]["docs"])
    check("өөрчлөлт хариунд (status new -> canceled)", r["changes"] and r["changes"][0]["field"] == "status"
          and r["changes"][0]["new"] == "canceled" and r["changes"][0]["source"] == "ai", r["changes"])
    r = say(c, sid, "Миний бүртгэл ямар байгаа вэ")
    check("дахин асуухад 'цуцлагдсан'", "цуцлагдсан" in " ".join(r["replies"]), r["replies"])

    print("\n[3] Bootcamp: цаг солих, дараа нь бүртгэлээ цуцлах")
    r = say(c, None, "Цагаа солимоор байна")
    sid = r["session"]
    r = say(c, sid, dtmf=ppl["Болд"]["code"])
    check("сул цагуудыг санал болгоно", r["state"] == "slot" and any(x.startswith("Нэгийг дарвал") for x in r["replies"]), r["replies"])
    say(c, sid, dtmf="2")
    r = say(c, sid, dtmf="1")
    new_time = people.appointment(t.dir, ppl["Болд"]["id"])
    check("цаг солигдлоо", r["replies"][0].startswith("Таны цагийг солилоо") and people.fmt(new_time) != ppl["Болд"]["appointment"]
          and r["person"]["appointment"] == people.fmt(new_time), r["replies"])
    r = say(c, sid, "Bootcamp хөтөлбөрт суухаа больсон")
    check("ижил ярианд бүртгэлээ цуцлах -> асууна", r["state"] == "reg_cancel_confirm", r)
    say(c, sid, dtmf="1")
    check("бүртгэл цуцлагдаж, цаг нь суллагдсан", people.lead(t.dir, ppl["Болд"]["id"])["status"] == "canceled"
          and people.appointment(t.dir, ppl["Болд"]["id"]) is None and new_time in people.free_slots(t.dir))

    print("\n[4] Асуух, буруу код")
    r = say(c, None, "Би юунд бүртгүүлсэн бэ")
    r = say(c, r["session"], " ".join(ppl["Сараа"]["code"]))
    check("кодыг яриагаар хэлэхэд ч болно", r["state"] == "menu" and r["replies"][0] == "Баталгаажлаа.", r)
    r = say(c, r["session"], "Би юунд бүртгүүлсэн бэ")
    check("'юунд бүртгүүлсэн' -> эвент", "AI Hackathon эвент" in r["replies"][0], r["replies"])
    r = say(c, None, "Бүртгэлээ цуцлах")
    sid = r["session"]
    rs = [say(c, sid, dtmf="0000")["replies"][0] for _ in range(3)]
    check("3 удаа буруу код -> дуусна", rs[-1] == t.phrases()["account"]["code_fail"]
          and say(c, sid, dtmf="1")["state"] == "idle", rs)

    print("\n[5] Ажилтан: бусдын бүртгэлийг AI-аар")
    pin = people.staff_pin(t.dir)
    r = say(c, None, mode="staff")
    sid = r["session"]
    check("ажилтны код асууна (6 цифр)", r["replies"] == [t.phrases()["account"]["staff_ask_pin"]] and r["state"] == "staff_code"
          and r["dtmf_len"] == 6 and r["staff"])
    check("код оруулалгүй команд бичвэл дахин код асууна", say(c, sid, "Номины бүртгэлийг цуцал", mode="staff")["replies"]
          == [t.phrases()["account"]["staff_ask_pin"]])
    check("залгагчийн код ажилтны эрх өгөхгүй", say(c, sid, dtmf=ppl["Сараа"]["code"] + "00", mode="staff")["replies"][0]
          == t.phrases()["account"]["code_wrong"])
    r = say(c, sid, dtmf=pin, mode="staff")
    check("нэвтэрлээ", r["state"] == "target")
    r = say(c, sid, "Сараагийн бүртгэлийг цуцал", mode="staff")
    check("бүх хүнээс нэрээр олж кодоор батлуулна", r["state"] == "target_confirm" and ppl["Сараа"]["code"][:2] in r["replies"][0]
          and r["trace"] and r["trace"][0]["kind"] == "хүн", r)
    r = say(c, sid, dtmf="1", mode="staff")
    check("командыг гүйцэтгэх гэж асууна", r["state"] == "reg_cancel_confirm" and "AI Hackathon эвент" in " ".join(r["replies"]), r["replies"])
    r = say(c, sid, dtmf="1", mode="staff")
    check("Сараагийн бүртгэл цуцлагдсан (source=staff)", people.lead(t.dir, ppl["Сараа"]["id"])["status"] == "canceled"
          and r["changes"][0]["source"] == "staff" and r["state"] == "target", r["changes"])
    check("өөрчилсөн хүн самбарт үлдэнэ", r["person"] and r["person"]["name"] == "Сараа")
    check("вэбийн түүхэнд харагдана", any(x["source"] == "staff" for x in c.get("/api/people").json()["changes"]))

    print("\n[6] Байгууллагын RAG (хувийн биш асуулт)")
    for q, want in [("Төлбөр хэд вэ", "1,500,000"), ("Хичээл хэдэн цагаас эхэлдэг вэ", "9 цагаас"),
                    ("Хөтөлбөр хэдэн сар үргэлжилдэг вэ", "6 сар")]:
        r = say(c, None, q)
        check(f"'{q}' -> мэдээллээс", want in r["replies"][0] and r["state"] == "idle"
              and r["trace"][0]["kind"] == "байгууллагын RAG", r["replies"])
    r = say(c, None, "Танайд усан сан бий юу")
    check("мэдээлэлд байхгүй -> зохиохгүй", r["replies"][0] == t.phrases()["error"], r["replies"])

    print("\n[7] Хүсэлт таних (RAG_EMBED=%s)" % assistant.embedder.name())
    s = assistant.Search()
    for text, want in [("Эвентэд очиж чадахгүй боллоо", "cancel_registration"), ("Бүртгэлээ цуцалмаар байна", "cancel_registration"),
                       ("Хакатонд оролцож чадахгүй нь", "cancel_registration"), ("Цагаа өөр өдөр болгож болох уу", "change_time"),
                       ("Утасны дугаар маань солигдсон", "change_phone"), ("Миний цаг хэзээ билээ", "ask_time"),
                       ("Уулзалтаа цуцалмаар байна", "cancel"),
                       ("Сургалтын төлбөр хэд вэ", None), ("Хаана байрладаг вэ", None), ("Сайн байна уу", None),
                       ("Хичээл хэдэн цагаас эхэлдэг вэ", None), ("Баярлалаа", None),
                       ("Би дугаараа сольсон", "change_phone")]:
        got = assistant.detect_intent(s, text)
        check(f"'{text}' -> {want}", got == want, got)



def events_and_phone():
    print("\n[8] Эвент: өмнөх өдөр 'ирэх үү' дуудлага автоматаар -> хувийн RAG")
    import json
    import reminders
    c, t = client("Pinecone Events", "events@example.mn")
    r = c.post("/api/assistant/samples").json()
    bold_bc, nomin, saraa, bold_ev = [p["id"] for p in r["people"]]
    ev = c.get("/api/people").json()["events"]
    check("жишээ эвент (2 хоногийн дараа)", ev and ev[0]["name"] == "AI Hackathon эвент", ev)
    items = reminders.load(t)["items"]
    at = people.parse_local(ev[0]["at"])
    check("эвентэд бүртгүүлсэн 3 хүнд дуудлага товлогдсон (гараар оруулаагүй)",
          all(items[str(i)]["event"] == "AI Hackathon эвент" and items[str(i)]["status"] == "scheduled" for i in (nomin, saraa, bold_ev))
          and str(bold_bc) in items and not items[str(bold_bc)].get("event"), sorted(items))
    call_at = people.datetime.fromtimestamp(items[str(nomin)]["call_at"], people.TZ)
    check("өмнөх өдрийн 11:00-д", call_at.date() == (at - people.timedelta(days=1)).date() and call_at.hour == 11, call_at)
    r = c.post("/api/assistant/reminder-call", json={"lead_id": nomin}).json()
    check("AI: 'эвентэд ирэх хэвээрээ юу'", "ирэх хэвээрээ юу" in r["replies"][0] and "AI Hackathon эвент" in r["replies"][0]
          and "Номин" in r["replies"][0], r["replies"])
    r = c.post("/api/assistant/reminder-call", json={"lead_id": nomin, "key": "2"}).json()
    docs = {d["field"]: d["text"] for d in r["person"]["docs"]}
    check("2 -> хувийн RAG: ирэхгүй", "ирэхгүй" in docs.get("attendance", ""), docs)
    check("бүртгэл цуцлагдсан, сануулга declined", people.lead(t.dir, nomin)["status"] == "canceled"
          and reminders.load(t)["items"][str(nomin)]["status"] == "declined")
    check("өөрчлөлт: attendance + status", {c_["field"] for c_ in r["changes"]} == {"attendance", "status"}, r["changes"])
    r = c.post("/api/assistant/reminder-call", json={"lead_id": saraa, "key": "1"}).json()
    docs = {d["field"]: d["text"] for d in r["person"]["docs"]}
    check("1 -> хувийн RAG: ирнэ, төлөв contacted", "ирнэ" in docs.get("attendance", "")
          and people.lead(t.dir, saraa)["status"] == "contacted", docs)
    r = say(c, None, "Эвентэд ирэх эсэх маань бүртгэгдсэн үү")
    r = say(c, r["session"], dtmf=people.ensure_code(t.dir, saraa))
    check("дараа нь AI-аас асуухад хувийн RAG-аас: ирнэ", r["person"] and r["person"]["name"] == "Сараа"
          and r["replies"][-2] == t.phrases()["account"]["attendance_yes"], r["replies"])
    c.put("/api/people/events", json={"events": [{"name": "AI Hackathon эвент", "at": ev[0]["at"]},
                                                 {"name": "Demo Day", "at": "2099-01-05T15:00"}]})
    check("эвент нэмэх/засах", [e["name"] for e in c.get("/api/people").json()["events"]] == ["AI Hackathon эвент", "Demo Day"])
    check("буруу огноо -> 400", c.put("/api/people/events", json={"events": [{"name": "X эвент", "at": "маргааш"}]}).status_code == 400)

    print("\n[9] Дугаараа сольсон -> тэр хүний БҮХ бүртгэл, баримт, дуудлага")
    r = say(c, None, "Би дугаараа сольсон")
    check("хүсэлт: дугаар солих", r["state"] == "code", r)
    r = say(c, r["session"], dtmf=people.ensure_code(t.dir, bold_bc))
    check("шинэ дугаар асууна", r["state"] == "new_phone", r["replies"])
    sid = r["session"]
    say(c, sid, dtmf="80405060")
    r = say(c, sid, dtmf="1")
    check("Bootcamp ба эвентийн бүртгэл хоёулаа шинэ дугаартай", people.lead(t.dir, bold_bc)["phone"] == "80405060"
          and people.lead(t.dir, bold_ev)["phone"] == "80405060")
    check("хоёр бүртгэлийн хувийн баримт шинэчлэгдсэн", all(any("80405060" in d["text"] for d in people.docs(t.dir, i))
                                                       for i in (bold_bc, bold_ev)))
    check("эвентийн дуудлага шинэ дугаар руу залгана", reminders.number_of(reminders.lead_of(t, bold_ev)) == "80405060")
    check("өөрчлөлтийн түүх хоёр бүртгэлд", all(people.changes(t.dir, i)[0]["field"] == "phone" for i in (bold_bc, bold_ev)))
    check("бусдын дугаар хэвээр", people.lead(t.dir, saraa)["phone"] == "95551234")
    raw = json.load(open(reminders.path(t), encoding="utf-8"))
    check("reminders.json эвдрээгүй", str(bold_ev) in raw["items"])


if __name__ == "__main__":
    main()
    events_and_phone()
    print(f"\n{'ТЭНЦЛЭЭ ✓' if not failures else f'ТЭНЦЭЭГҮЙ: {len(failures)} шалгалт'}")
    sys.exit(1 if failures else 0)
