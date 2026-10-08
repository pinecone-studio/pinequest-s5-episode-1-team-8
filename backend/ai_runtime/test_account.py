"""
Бүртгэлээ утсаар шалгах/өөрчлөх (account.py + people.py) тест — утасгүй, түр байгууллагын хавтсанд.

  .venv/bin/python test_account.py          # хурдан (үсгийн n-gram embedding)
  .venv/bin/python test_account.py --real   # бодит bge-m3 (хүсэлт таних босгыг шалгана, ~1.2GB RAM)
"""
import json
import os
import sqlite3
import sys
import tempfile
import zlib
from datetime import datetime

import numpy as np

import account as acct
import db
import people

failures: list[str] = []


def check(name: str, ok: bool, detail: str = ""):
    print(f"  {'✓' if ok else '✗'} {name}{f' — {detail}' if detail else ''}")
    if not ok:
        failures.append(name)


def fake_embed(texts):
    """Үсгийн 3-gram -> 512 хэмжээст normalized вектор (bge-m3-ийн оронд, хурдан)."""
    out = np.zeros((len(texts), 512), np.float32)
    for i, t in enumerate(texts):
        t = f" {t.lower()} "
        for j in range(len(t) - 2):
            out[i, zlib.crc32(t[j:j + 3].encode()) % 512] += 1
    return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-6)


def make_tenant() -> str:
    tdir = tempfile.mkdtemp()
    os.makedirs(os.path.join(tdir, "data"))
    with open(os.path.join(tdir, "data", "settings.json"), "w") as f:
        json.dump({"booking": {"days": [0, 1, 2, 3, 4], "start": 10, "end": 13, "capacity": 1, "horizon": 7}}, f)
    return tdir


def main(embed):
    now = datetime(2026, 10, 12, 9, 0, tzinfo=people.TZ)        # Даваа 09:00
    tdir = make_tenant()
    path = people.db_path(tdir)
    bold = db.add_lead("c1", "Болд", "99112233", None, None, "lead", path=path)
    saraa = db.add_lead("c2", "Сараа", "88776655", None, None, "lead", path=path)
    search = acct.Search(embed)

    print("\n[1] Код ба хувийн баримтууд (RAG)")
    code = people.ensure_code(tdir, bold)
    check("4 оронтой код", len(code) == 4 and code.isdigit(), code)
    check("код давтагдахгүй, дахин дуудахад ижил", people.ensure_code(tdir, bold) == code)
    codes = people.ensure_all_codes(tdir)
    check("бүх бүртгэлд код", set(codes) == {bold, saraa} and codes[bold] != codes[saraa])
    check("кодоор олно", (people.find(tdir, code) or {}).get("name") == "Болд")
    check("буруу код -> None", people.find(tdir, "12") is None and people.find(tdir, "abcd") is None)
    docs = {d["field"]: d["text"] for d in people.docs(tdir, bold)}
    check("баримтууд: нэр, утас, цаг, төлөв", {"name", "phone", "appointment", "status"} <= set(docs), str(sorted(docs)))
    with sqlite3.connect(path) as con:
        n = con.execute("SELECT COUNT(*) FROM person_docs WHERE lead_id=?", (bold,)).fetchone()[0]
    check("person_docs хүснэгтэд хадгалагдсан", n >= 4)

    print("\n[2] Сул цагууд")
    slots = people.free_slots(tdir, now)
    check("ажлын цагаас (10-12 цаг, 2 цагийн дараахаас)", slots[0] == now.replace(hour=11) and
          all(10 <= s.hour < 13 and s.weekday() < 5 for s in slots), people.fmt(slots[0]))
    people.set_appointment(tdir, saraa, now.replace(hour=11), now=now)
    check("Сараагийн авсан цаг бусдад сул биш", now.replace(hour=11) not in people.free_slots(tdir, now))
    try:
        people.set_appointment(tdir, bold, now.replace(hour=11), now=now)
        check("эзэлсэн цагийг авахгүй", False)
    except ValueError:
        check("эзэлсэн цагийг авахгүй", True)
    check("огноо үгээр", people.slot_text(datetime(2026, 10, 15, 10, tzinfo=people.TZ)) ==
          "Пүрэв гараг аравдугаар сарын арван тавны арван цагт", people.slot_text(datetime(2026, 10, 15, 10, tzinfo=people.TZ)))
    texts = people.all_date_texts()
    check("огнооны клип бүгд байна", all(p in texts for s in slots for p in people.slot_parts(s)), f"{len(texts)} клип")

    print("\n[3] Код буруу -> 3 оролдлого")
    flow = acct.AccountFlow(tdir, search, None, "call-x", now=now)
    r = [flow.handle_dtmf("0000"), flow.handle_dtmf("1111"), flow.handle_dtmf("2222")]
    check("code_wrong, code_wrong, code_fail", r == [["code_wrong"], ["code_wrong"], ["code_fail"]] and flow.finished, str(r))
    flow = acct.AccountFlow(tdir, search, None, "call-x", now=now)
    check("кодгүй асуулт -> урсгалаас гарна (энгийн горим)", flow.handle("сургалтын төлбөр хэд вэ") is None)

    print("\n[4] Цаг солих: код -> сул цаг -> сонгох -> батлах")
    flow = acct.AccountFlow(tdir, search, "change_time", "call-1", now=now)
    keys = flow.handle_dtmf(code)
    check("баталгаажаад шууд сул цаг санал болгоно", keys[:2] == ["verified", "slots_intro"] and "press_1" in keys, str(keys))
    check("Сараагийн цаг санал болгохгүй", "date:2026-10-12T11:00" not in keys)
    second = flow.offered[1]
    keys = flow.handle_dtmf("2")
    check("2 -> сонгосон цагийг уншаад асууна", keys == ["you_chose", f"date:{people.fmt(second)}", "confirm"], str(keys))
    check("батлахаас өмнө бичээгүй", people.appointment(tdir, bold) is None)
    keys = flow.handle_dtmf("1")
    check("1 -> товлолоо", keys[0] == "appt_done" and people.appointment(tdir, bold) == second, str(keys))
    item = json.load(open(people.reminders_path(tdir)))["items"][str(bold)]
    check("reminders.json: сануулга өмнөх өдөр 11:00, AI өөрчилсөн", item["status"] in ("scheduled", "confirmed")
          and item["changed_by"] == "ai" and item["text"] is None, item["status"])
    ch = people.changes(tdir, bold)
    check("өөрчлөлтийн түүх (lead_changes)", ch and ch[0]["field"] == "appointment" and ch[0]["source"] == "ai"
          and ch[0]["call_uuid"] == "call-1")
    check("ажилтанд мэдэгдэх үйл явдал", flow.events and flow.events[0]["new"] == people.fmt(second))
    docs = {d["field"]: d["text"] for d in people.docs(tdir, bold)}
    check("хувийн баримт шинэчлэгдсэн", people.slot_text(second) in docs["appointment"])

    print("\n[5] Дугаар солих (яриагаар)")
    flow = acct.AccountFlow(tdir, search, None, "call-2", now=now)
    keys = flow.handle(" ".join(code))
    check("код яриагаар -> цэс + одоогийн цаг", keys[0] == "verified" and "appt_is" in keys and keys[-1] == "menu", str(keys))
    keys = flow.handle_dtmf("1")
    check("1 -> шинэ дугаар асууна", keys == ["ask_new_phone"])
    check("буруу урттай -> дахин", flow.handle_dtmf("1234") == ["phone_retry"])
    keys = flow.handle_dtmf("95551234")
    check("дугаарыг уншаад асууна", keys == ["new_phone_is", "digits:95551234", "confirm"])
    check("'үгүй' -> дахин асууна", flow.handle("үгүй") == ["ask_new_phone"])
    flow.handle_dtmf("95551234")
    check("'тийм' -> солилоо", flow.handle("тийм зөв") == ["phone_done", "anything_else"]
          and people.lead(tdir, bold)["phone"] == "95551234")
    check("Сараагийн дугаар хэвээр", people.lead(tdir, saraa)["phone"] == "88776655")

    print("\n[6] Хувийн RAG-аас хайх (зөвхөн өөрийн баримт)")
    flow = acct.AccountFlow(tdir, search, None, "call-3", now=now)
    flow.handle_dtmf(code)
    keys = flow.handle("миний цаг хэзээ билээ")
    check("'миний цаг хэзээ' -> өөрийн цаг", keys[:2] == ["appt_is", f"date:{people.fmt(second)}"], str(keys))
    keys = flow.handle("ямар дугаар бүртгэлтэй вэ")
    check("'ямар дугаар' -> шинэ дугаар", keys[:2] == ["phone_is", "digits:95551234"], str(keys))
    with sqlite3.connect(path) as con:
        n = con.execute("SELECT COUNT(*) FROM person_docs WHERE lead_id=? AND emb IS NOT NULL", (bold,)).fetchone()[0]
    check("баримтын вектор DB-д хадгалагдсан", n >= 2, str(n))

    print("\n[7] Сул цагийг өдрөөр хайх, цуцлах")
    flow = acct.AccountFlow(tdir, search, None, "call-4", now=now)
    flow.handle_dtmf(code)
    flow.handle_dtmf("2")
    keys = flow.handle("баасан гарагт болох уу")
    check("'баасан' -> зөвхөн Баасан гарагийн цагууд", flow.offered and all(s.weekday() == 4 for s in flow.offered),
          ", ".join(people.fmt(s) for s in flow.offered))
    keys = flow.handle("эхнийх нь")
    check("'эхнийх' -> 1-р цаг", keys[0] == "you_chose" and flow.chosen == flow.offered[0])
    flow.handle_dtmf("1")
    friday = flow.chosen
    check("Баасан руу шилжлээ, хуучин цаг суллагдсан", people.appointment(tdir, bold) == friday
          and second in people.free_slots(tdir, now))
    keys = flow.handle_dtmf("3")
    check("3 -> цагаа уншаад цуцлах эсэхийг асууна", keys[-1] == "ask_cancel" and "appt_is" in keys)
    check("2 -> өөрчлөхгүй", flow.handle_dtmf("2") == ["unchanged", "anything_else"] and people.appointment(tdir, bold))
    flow.handle_dtmf("3")
    check("1 -> цуцаллаа", flow.handle_dtmf("1") == ["cancel_done", "anything_else"] and not people.appointment(tdir, bold))
    check("цуцалсан цаг сул болсон", friday in people.free_slots(tdir, now))
    check("бүх өөрчлөлт түүхэнд", len(people.changes(tdir, bold)) == 4, str(len(people.changes(tdir, bold))))

    print("\n[8] Код асуухаас өмнө хүсэлт таних")
    for text, want in [("цагаа солимоор байна", "change_time"), ("дугаараа солимоор байна", "change_phone"),
                       ("уулзалтаа цуцалмаар байна", "cancel")]:
        got = acct.detect_intent(search, text)
        check(f"'{text}' -> {want}", got == want, str(got))

    print("\n[9] Ажилтан утсаар бусдын бүртгэлийг өөрчилнө")
    check("ажилтны код тохируулаагүй бол нэвтрэхгүй", not people.check_staff_pin(tdir, "123456"))
    pin = people.staff_pin(tdir)
    check("6 оронтой ажилтны код (settings.json)", len(pin) == 6 and people.staff_pin(tdir) == pin)
    staff = acct.AccountFlow(tdir, search, None, "call-s", now=now, staff=True)
    check("ажилтны код 6 цифр хүлээнэ", staff.dtmf_len() == 6)
    check("залгагчийн код ажилтны эрх өгөхгүй", staff.handle_dtmf(code) == ["code_wrong"])
    keys = staff.handle_dtmf(pin)
    check("зөв код -> хэнийг өөрчлөх вэ", keys == ["staff_verified"] and staff.state == "target")
    bold2 = db.add_lead("c3", "Болд", "99001122", None, None, "lead", path=path)    # ижил нэртэй шинэ хүн
    keys = staff.handle("Болдын цагийг баасан гараг руу шилжүүл")
    check("нэрээр БҮХ хүнээс хайж, шинэ Болдын кодыг уншина", keys[:2] == ["target_is", f"digits:{people.ensure_code(tdir, bold2)}"]
          and keys[-1] == "confirm_target", str(keys))
    keys = staff.handle_dtmf("2")
    check("биш -> дараагийн Болд (код, утас)", keys == ["target_is", f"digits:{code}", "target_phone", "digits:95551234",
                                                      "confirm_target"], str(keys))
    keys = staff.handle_dtmf("1")
    check("мөн -> командыг гүйцэтгэнэ: Баасан гарагийн сул цагууд", keys[0] == "slots_intro"
          and staff.offered and all(x.weekday() == 4 for x in staff.offered), str(keys[:3]))
    staff.handle_dtmf("1")
    keys = staff.handle_dtmf("1")
    check("товлоод дараагийн хүн рүү", keys[0] == "appt_done" and keys[-1] == "staff_next" and staff.state == "target"
          and people.appointment(tdir, bold) == staff.chosen, str(keys))
    last = people.changes(tdir, bold)[0]
    check("түүхэнд ажилтан өөрчилсөн (source=staff)", last["source"] == "staff" and last["call_uuid"] == "call-s")
    check("мэдэгдэлд хэний бүртгэл", staff.events[-1]["lead"]["id"] == bold and staff.events[-1]["staff"])
    keys = staff.handle_dtmf(codes[saraa])
    check("кодоор хүн сонгох (Сараа)", keys[:2] == ["target_is", f"digits:{codes[saraa]}"])
    staff.handle_dtmf("1")
    check("цэс -> 1 дугаар солих", staff.handle_dtmf("1") == ["ask_new_phone"])
    staff.handle_dtmf("80001111")
    check("Сараагийн дугаар солигдлоо", staff.handle_dtmf("1") == ["phone_done", "staff_next"]
          and people.lead(tdir, saraa)["phone"] == "80001111")
    check("STT 'Балдын' -> Болд олдоно", [r["id"] for r in people.find_by_name(tdir, "балдын цаг хэзээ вэ")][:2] == [bold2, bold])
    check("нэргүй ярианаас хүн олдохгүй", staff.handle("сайн байна уу") == ["target_not_found"])
    check("command-аас нэр хасагдана", people.strip_name("Болдын цагийг баасан руу шилжүүл", "Болд") == "цагийг баасан руу шилжүүл")
    wrong = acct.AccountFlow(tdir, search, None, "call-w", now=now, staff=True)
    r = [wrong.handle_dtmf("000000") for _ in range(3)]
    check("ажилтны код 3 удаа буруу -> дуусна", r[-1] == ["code_fail"] and wrong.finished)
    for text, want in [("Болдын цагийг баасан руу шилжүүл", "change_time"), ("Сараагийн дугаарыг солих", "change_phone"),
                       ("Болдын уулзалтыг цуцал", "cancel")]:
        lead_name = "Болд" if "Болд" in text else "Сараа"
        got = acct.detect_staff_intent(search, people.strip_name(text, lead_name))
        check(f"ажилтны команд '{text}' -> {want}", got == want, str(got))



def web_parity(embed):
    """#108-ийн дараа: утасны AI вэбтэй НЭГ people.py ашиглаж, нэг нэгнийхээ бичсэнийг эвдэхгүй."""
    import json as _json
    from datetime import timedelta
    print("\n[10] Утас ба вэб нэг логик (backend/people.py)")
    check("people = backend/people.py (хуулбар биш)", people.__file__.endswith(os.path.join("backend", "people.py"))
          and hasattr(people, "cancel_registration") and people.EMBED_ON_WRITE is False, people.__file__)
    now = datetime(2026, 10, 12, 9, 0, tzinfo=people.TZ)
    tdir = make_tenant()
    path = people.db_path(tdir)
    ev_at = now + timedelta(days=3)
    st = _json.load(open(os.path.join(tdir, "data", "settings.json")))
    st["events"] = [{"name": "AI Hackathon эвент", "at": people.fmt(ev_at.replace(hour=10, minute=0))}]
    _json.dump(st, open(os.path.join(tdir, "data", "settings.json"), "w"))
    a = db.add_lead("c1", "Номин", "88990011", None, None, "lead", path=path, course="AI Hackathon эвент")
    b = db.add_lead("c2", "Номин", "88990011", None, None, "lead", path=path, course="Bootcamp хөтөлбөр")
    people.sync_event_reminders(tdir, now)
    items = _json.load(open(people.reminders_path(tdir)))["items"]
    items[str(a)]["attendance"] = True
    _json.dump({"items": items}, open(people.reminders_path(tdir), "w"))
    docs = {d["field"] for d in people.docs(tdir, a)}
    check("утасны AI баримт шинэчлэхэд «ирэх эсэх» устахгүй", "attendance" in docs, sorted(docs))
    check("эвентийг уулзалт гэж андуурахгүй", people.appointment(tdir, a) is None)
    check("эвентийн цаг уулзалтын сул цагийг эзлэхгүй", not people.taken(tdir))
    search = acct.Search(embed)
    code = people.ensure_code(tdir, a)
    flow = acct.AccountFlow(tdir, search, None, "call-p", now=now)
    flow.handle_dtmf(code)
    keys = flow.handle("Ирнэ гэж бүртгэгдсэн үү")
    check("«Ирнэ гэж бүртгэгдсэн үү» -> attendance_yes", keys[0] == "attendance_yes", keys)
    keys = flow.handle_dtmf("4")
    check("цэс 4 -> бүртгэл цуцлах уу", keys == ["ask_cancel_reg"] and flow.state == "reg_cancel_confirm", keys)
    keys = flow.handle_dtmf("1")
    check("утсаар бүртгэл цуцлагдлаа", keys[0] == "reg_cancel_done" and people.lead(tdir, a)["status"] == "canceled"
          and flow.events[-1]["field"] == "status", keys)
    check("эвентийн сануулга цуцлагдсан, Bootcamp бүртгэл хэвээр",
          _json.load(open(people.reminders_path(tdir)))["items"][str(a)]["status"] == "canceled"
          and people.lead(tdir, b)["status"] == "new")
    flow = acct.AccountFlow(tdir, search, None, "call-q", now=now)
    flow.handle_dtmf(people.ensure_code(tdir, b))
    flow.handle("Эвентэд очиж чадахгүй боллоо")
    check("«очиж чадахгүй боллоо» -> бүртгэл цуцлах", flow.state == "reg_cancel_confirm")
    flow.handle_dtmf("2")
    flow.handle_dtmf("1")
    flow.handle_dtmf("80405060")
    flow.handle_dtmf("1")
    check("утсаар дугаар солиход тэр хүний бүх бүртгэл шинэчлэгдэнэ (вэбтэй ижил)",
          people.lead(tdir, a)["phone"] == "80405060" and people.lead(tdir, b)["phone"] == "80405060")


if __name__ == "__main__":
    if "--real" in sys.argv:
        from embed import Embedder
        emb = Embedder()
        main(emb.query)
        web_parity(emb.query)
    else:
        main(fake_embed)
        web_parity(fake_embed)
    print(f"\n{'ТЭНЦЛЭЭ ✓' if not failures else f'ТЭНЦЭЭГҮЙ: {len(failures)} шалгалт'}")
    sys.exit(1 if failures else 0)
