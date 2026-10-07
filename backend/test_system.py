"""
Backend-ийн тест. Кодыг өөрчилсний дараа, PR-ийн өмнө ажиллуулна.

  .venv/bin/python backend/test_system.py

1-2. Нэвтрэлт: нэвтрэх, буруу нууц үг, хамгаалалттай API, гарах, хуурамч cookie,
     нууц үг солиход хуучин session хүчингүй, буруу оролдлогын хязгаар (IP + и-мэйл)
3. Байгууллага бүртгүүлэх: шинэ байгууллага, загвар FAQ, давхардал, хязгаар
4. Байгууллагын мэдээлэл (Тохируулах): засах, загвар FAQ дахин үүсэх, байгууллага хооронд тусгаарлалт
5. Нууц үг солих: одоогийн нууц үг шалгах, энэ төхөөрөмж нэвтэрсэн хэвээр, бусад нь гарна
6. Telegram мэдэгдэл: токен, групп сонгох, тест мессеж (Telegram API-г дуурайна — интернэт хэрэггүй)
7. Яриа: дуудлагын жагсаалт, нэг дуудлагын яриа, байгууллага хооронд тусгаарлалт
8. Самбарын статистик: хариулсан / хариулж чадаагүй, зам, сүүлийн 5 өдөр, шинэ бүртгэл
9. Бүртгэл (lead): жагсаалт, төлөв, тэмдэглэл, байгууллага хооронд тусгаарлалт
10. Хариулж чадаагүй асуултууд
11. Мэдээлэл бэлдэх: SIM-TRUNK скрипт манай байгууллагын хавтсаар ажиллана (хуурамч SIM-TRUNK — AI загваргүй)
12. Төлөв (/api/status): AI сервер, SIP, бэлэн эсэх, sidebar-ын тоо
13. AI сургалт: сургасан загварын мэдээлэл (SIM-TRUNK-ийн бичдэг газраас)
14. Байгууллагууд (admin): жагсаалт, эрх солих, өөр байгууллага руу сольж харах, owner-т хаалттай
15. Өөрийн хоолойгоор бичих: бичлэг хадгалах, сонсох, устгах, WAV шалгалт, байгууллага хооронд тусгаарлалт
16. ElevenLabs хоолой (admin): түлхүүр, хоолойнууд, жишээ үүсгэх, сонгох (ElevenLabs, SIM-TRUNK-ийг дуурайна)
17. Хоолой (Oron-гүй): одоогийн хоолой, ElevenLabs-ийн дахин үүсгэх, аудиог шинэчлэх, ZIP татах
18. Хоолойн жагсаалт: бэлдсэний дараа яг тоглогдох хэллэгүүд (SIM-TRUNK-ийн faq_index.json)
19. Байгууллагын загвар SIM-TRUNK-тэй ижил: хэллэг (config phrases), утасны ярианы FAQ, мэндчилгээ

Түр хавтсанд (DATA_DIR) ажиллана — backend/data/-ийн жинхэнэ хэрэглэгчдэд хүрэхгүй.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="pc_test_")

import accounts  # noqa: E402
import app as server  # noqa: E402
import auth  # noqa: E402
import tenant  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

app = server.app

failures: list[str] = []


def check(name: str, ok: bool, detail: object = ""):
    print(f"  {'✓' if ok else '✗'} {name}" + (f"  ({detail})" if not ok and detail != "" else ""))
    if not ok:
        failures.append(name)


def login(client: TestClient, email: str, password: str, **kw):
    return client.post("/api/login", json={"email": email, "password": password}, **kw)


def signup(client: TestClient, **kw):
    body = {"company": "Гэрэл шүдний эмнэлэг", "phone": "7270 0800", "email": "gerel@example.mn",
            "password": "gerel-pass-1", **kw}
    return client.post("/api/signup", json=body)


def owner_client(company: str, email: str) -> TestClient:
    """Шинэ байгууллага бүртгүүлж нэвтэрсэн client (бусад тестэд)"""
    server.SIGNUPS.clear()
    c = TestClient(app)
    r = signup(c, company=company, email=email, phone="")
    assert r.status_code == 200, r.text
    return c


def test_login():
    print("\n[1] Нэвтрэлт")
    auth.FAIL_DELAY = 0
    pw = accounts.ensure_admin()
    check("анх асахад admin үүснэ, дахин үүсэхгүй", bool(pw) and accounts.ensure_admin() is None)
    accounts.create_user("owner@example.mn", "secret-pass-1", "gerel")

    c = TestClient(app)
    r = c.get("/api/me")
    check("нэвтрээгүй -> 401", r.status_code == 401, r.status_code)
    check("/docs хаалттай", c.get("/docs").status_code in (401, 404))

    r = login(c, "owner@example.mn", "wrong-pass")
    check("буруу нууц үг -> 401", r.status_code == 401 and "буруу" in r.json()["detail"], r.status_code)
    r = login(c, "nobody@example.mn", "secret-pass-1")
    check("байхгүй хэрэглэгч -> 401 (ижил мессеж)", r.status_code == 401 and "буруу" in r.json()["detail"])
    r = login(c, "", "")
    check("хоосон -> 400", r.status_code == 400, r.status_code)

    r = login(c, " Owner@Example.mn ", "secret-pass-1")
    cookie = r.headers.get("set-cookie", "").lower()
    check("зөв нууц үг -> 200 + cookie (том/жижиг үсэг, зай хамаарахгүй)",
          r.status_code == 200 and r.json()["email"] == "owner@example.mn" and auth.COOKIE in cookie, r.status_code)
    check("cookie httponly, samesite=lax", "httponly" in cookie and "samesite=lax" in cookie, cookie)
    me = c.get("/api/me")
    check("/api/me -> хэрэглэгч", me.status_code == 200 and me.json()["role"] == "owner"
          and me.json()["tenant"] == "gerel" and "hash" not in me.json(), me.text)

    token = c.cookies.get(auth.COOKIE)
    fake = token[:-1] + ("0" if token[-1] != "0" else "1")
    r = TestClient(app).get("/api/me", headers={"cookie": f"{auth.COOKIE}={fake}"})
    check("хуурамч cookie -> 401", r.status_code == 401)

    accounts.set_password("owner@example.mn", "new-secret-2")
    check("нууц үг солиход хуучин session хүчингүй", c.get("/api/me").status_code == 401)

    login(c, "owner@example.mn", "new-secret-2")
    check("шинэ нууц үгээр нэвтэрнэ", c.get("/api/me").status_code == 200)
    r = c.post("/api/logout")
    check("гарах -> cookie устна", r.status_code == 200 and c.get("/api/me").status_code == 401)

    print("\n[2] Буруу оролдлогын хязгаар")
    auth._fails.clear()
    codes = [login(c, "owner@example.mn", "bad").status_code for _ in range(6)]
    check("нэг и-мэйл рүү 5 буруу оролдлогын дараа 429", codes == [401] * 5 + [429], codes)
    r = login(c, "owner@example.mn", "new-secret-2")
    check("хаагдсан үед зөв нууц үг ч 429", r.status_code == 429, r.status_code)

    auth._fails.clear()
    proxy = TestClient(app, client=("127.0.0.1", 50000))     # Next.js-ээр дамжсан хүсэлт мэт
    for i in range(5):
        login(proxy, "owner@example.mn", "bad", headers={"x-forwarded-for": f"10.0.0.{i}"})
    r = login(proxy, "owner@example.mn", "bad", headers={"x-forwarded-for": "10.0.0.99"})
    check("IP толгой сольсон ч нэг и-мэйл рүү 5 удаа буруу -> 429", r.status_code == 429, r.status_code)
    r = login(proxy, "admin", "bad", headers={"x-forwarded-for": "10.0.0.99"})
    check("өөр и-мэйл, өөр IP -> хаагдаагүй (401)", r.status_code == 401, r.status_code)

    auth._fails.clear()
    for i in range(5):     # гаднаас шууд ирсэн хүсэлт x-forwarded-for хуурч IP-ийн хязгаараас зугтахгүй
        login(c, f"user{i}@example.mn", "bad", headers={"x-forwarded-for": f"10.0.0.{i}"})
    r = login(c, "owner@example.mn", "new-secret-2", headers={"x-forwarded-for": "10.0.0.50"})
    check("гаднын хүсэлтийн IP толгойд итгэхгүй (нэг IP-ээс 5 удаа -> 429)", r.status_code == 429, r.status_code)


def test_signup():
    print("\n[3] Байгууллага бүртгүүлэх")
    import speech
    check("утасны дугаарыг үгээр", speech.number_words("72700800", phone=True) == "далан хоёр, долоон зуу, найман зуу"
          and speech.number_words("99112233", phone=True) == "ерэн ес, арван нэг, хорин хоёр, гучин гурав",
          speech.number_words("99112233", phone=True))
    check("slug: кирилл -> латин", tenant.make_slug("Гэрэл шүдний эмнэлэг") == "gerel-shudnii-emneleg",
          tenant.make_slug("Гэрэл шүдний эмнэлэг"))

    server.SIGNUPS.clear()
    c = TestClient(app)
    r = signup(c)
    me = c.get("/api/me").json()
    check("бүртгүүлмэгц нэвтэрнэ (owner, өөрийн байгууллага)", r.status_code == 200 and me["email"] == "gerel@example.mn"
          and me["role"] == "owner" and me["tenant_name"] == "Гэрэл шүдний эмнэлэг" and me["plan"] == "trial", r.text)
    t = tenant.Tenant(me["tenant"])
    cfg, faq = t.config(), tenant.load_faq(t)
    ids = {x["id"] for x in faq.get("faq", [])}
    check("утсыг цэвэрлэж хадгална, дотуур дугаар олгоно", cfg.get("phone") == "72700800" and me["extension"].isdigit(), cfg)
    check("загвар FAQ (утастай -> contact_phone, хаяггүй -> location алга)",
          "contact_phone" in ids and "location" not in ids and "Гэрэл шүдний эмнэлэг" in faq["greeting"], ids)
    by_id = {x["id"]: x["answer"] for x in faq["faq"]}
    check("SIM-TRUNK-ийн шинэ нэр асуух, үдэх хэллэг",
          "Та нэрээ" in by_id["register"] and "Та нэрээ" in by_id["human_request"]
          and by_id["smalltalk_bye"] == "Манайхаар үйлчлүүлсэнд баярлалаа. Өдрийг сайхан өнгөрүүлээрэй.")
    check("мэдээллийн хавтас үүснэ", os.path.isdir(t.knowledge_dir))

    bad = [signup(TestClient(app), email="bad-email").status_code,
           signup(TestClient(app), email="x@example.mn", password="short").status_code,
           signup(TestClient(app), email="x@example.mn", company="A").status_code,
           signup(TestClient(app), email="x@example.mn", phone="123").status_code]
    check("буруу и-мэйл / богино нууц үг / нэр / утас -> 400", bad == [400] * 4, bad)
    r = signup(TestClient(app), company="Өөр байгууллага")
    check("бүртгэлтэй и-мэйл -> 400, хавтас үлдэхгүй", r.status_code == 400
          and not tenant.Tenant(tenant.make_slug("Өөр байгууллага")).exists(), r.text)

    server.SIGNUPS.clear()
    codes = [signup(TestClient(app), company=f"Байгууллага {i}", email=f"org{i}@example.mn").status_code for i in range(4)]
    check("нэг IP-ээс цагт 3-аас олон бүртгэл -> 429", codes == [200, 200, 200, 429], codes)
    exts = sorted(x.config()["extension"] for x in tenant.all_tenants())
    check("дотуур дугаар давхцахгүй", len(exts) == len(set(exts)), exts)


def test_org():
    print("\n[4] Байгууллагын мэдээлэл (Тохируулах)")
    a = owner_client("Нар кофе", "nar@example.mn")
    b = owner_client("Сар фитнес", "sar@example.mn")
    org = a.get("/api/org").json()
    check("GET /api/org -> өөрийн байгууллага", org["name"] == "Нар кофе" and org["users"][0]["email"] == "nar@example.mn"
          and org["documents"] == 0 and "hash" not in org["users"][0], org)
    r = a.put("/api/org", json={"name": "  Нар   кофе шоп ", "phone": "9911-2233", "email": "info@nar.mn",
                                "address": "СБД, 1-р хороо.", "hours": "Өдөр бүр 08:00-22:00"})
    t = tenant.Tenant(org["slug"])
    faq = tenant.load_faq(t)
    ids = {x["id"] for x in faq["faq"]}
    check("PUT /api/org -> хадгална (зай, утсыг цэвэрлэнэ)", r.status_code == 200 and r.json()["name"] == "Нар кофе шоп"
          and r.json()["phone"] == "99112233", r.text)
    check("загвар FAQ дахин үүснэ: утас, хаяг, цаг, шинэ нэр мэндчилгээнд",
          {"contact_phone", "location", "hours"} <= ids and "Нар кофе шоп" in faq["greeting"]
          and any("ерэн ес, арван нэг" in x["answer"] for x in faq["faq"]), ids)
    a.put("/api/org", json={"name": "Нар кофе шоп"})
    ids = {x["id"] for x in tenant.load_faq(t)["faq"]}
    check("хаяг, цагийг хассан -> тэдгээр FAQ хасагдана", not {"contact_phone", "location", "hours"} & ids, ids)
    bad = [a.put("/api/org", json=body).status_code for body in
           ({"name": "A"}, {"name": "Нар", "phone": "12"}, {"name": "Нар", "email": "буруу"})]
    check("буруу нэр / утас / и-мэйл -> 400", bad == [400, 400, 400], bad)
    check("өөр байгууллага зөвхөн өөрийнхийгөө харна", b.get("/api/org").json()["name"] == "Сар фитнес")
    check("нэвтрээгүй -> 401", TestClient(app).get("/api/org").status_code == 401)


def test_password():
    print("\n[5] Нууц үг солих")
    auth._fails.clear()
    a = owner_client("Цэцэг дэлгүүр", "tsetseg@example.mn")
    other = TestClient(app)
    login(other, "tsetseg@example.mn", "gerel-pass-1")        # өөр төхөөрөмж
    change = lambda c, cur, new: c.post("/api/account/password", json={"current": cur, "new": new})
    check("одоогийн нууц үг буруу -> 400", change(a, "wrong-pass", "new-pass-123").status_code == 400)
    check("богино шинэ нууц үг -> 400", change(a, "gerel-pass-1", "short").status_code == 400)
    check("хуучинтайгаа ижил -> 400", change(a, "gerel-pass-1", "gerel-pass-1").status_code == 400)
    r = change(a, "gerel-pass-1", "new-pass-123")
    check("солигдоно, энэ төхөөрөмж нэвтэрсэн хэвээр", r.status_code == 200 and a.get("/api/me").status_code == 200, r.text)
    check("бусад төхөөрөмж гарна", other.get("/api/me").status_code == 401)
    check("шинэ нууц үгээр нэвтэрнэ, хуучнаар үгүй", login(TestClient(app), "tsetseg@example.mn", "new-pass-123").status_code == 200
          and login(TestClient(app), "tsetseg@example.mn", "gerel-pass-1").status_code == 401)
    auth._fails.clear()
    codes = [change(a, "bad-pass-000", "x-pass-1234").status_code for _ in range(6)]
    check("5 удаа буруу -> 429", codes[-1] == 429, codes)
    auth._fails.clear()


class FakeTelegram:
    """notify.httpx.post-ийн оронд: Telegram руу хандахгүй, дуудлагыг тэмдэглэнэ."""
    TOKEN = "123456789:" + "A" * 35

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, url, json=None, timeout=None):
        token, method = url.split("/bot", 1)[1].split("/", 1)
        self.calls.append((method, json or {}))
        if token != self.TOKEN:
            result = {"ok": False, "description": "Unauthorized"}
        elif method == "getMe":
            result = {"ok": True, "result": {"username": "gerel_bot"}}
        elif method == "getUpdates":
            result = {"ok": True, "result": [{"message": {"chat": {"id": -100123, "title": "Ажилтнууд"}}}]}
        else:
            result = {"ok": True, "result": {}}
        return type("R", (), {"status_code": 200, "json": lambda self: result})()


def test_telegram():
    print("\n[6] Telegram мэдэгдэл")
    import notify
    fake = FakeTelegram()
    real_post, notify.httpx.post = notify.httpx.post, fake
    try:
        a = owner_client("Мөнх эмнэлэг", "munkh@example.mn")
        st = a.get("/api/settings").json()
        check("анх тохируулаагүй", st["telegram_token_set"] is False and st["telegram_chat_id"] is None, st)
        r = a.put("/api/settings/telegram", json={"token": "буруу/../токен"})
        check("хэлбэр буруу токен -> 400, Telegram руу хандахгүй", r.status_code == 400 and not fake.calls, r.text)
        r = a.put("/api/settings/telegram", json={"token": "123456789:" + "B" * 35})
        check("Telegram татгалзсан токен -> 400", r.status_code == 400 and "Unauthorized" in r.text, r.text)
        check("токенгүй үед групп сонгох -> 400", a.put("/api/settings/telegram", json={"chat_id": 1}).status_code == 400)
        r = a.put("/api/settings/telegram", json={"token": FakeTelegram.TOKEN})
        st = r.json()
        check("зөв токен -> хадгална, токеныг буцаахгүй (сүүлийн 4 үсэг л)", r.status_code == 200 and st["telegram_token_set"]
              and st["telegram_bot"] == "gerel_bot" and FakeTelegram.TOKEN not in r.text and st["telegram_token_hint"] == "…AAAA", r.text)
        chats = a.get("/api/settings/telegram/chats").json()
        check("групп хайх", chats == [{"id": -100123, "title": "Ажилтнууд"}], chats)
        check("групп сонгоогүй үед тест -> 400", a.post("/api/settings/telegram/test").status_code == 400)
        a.put("/api/settings/telegram", json={"chat_id": -100123, "chat_title": "Ажилтнууд"})
        r = a.post("/api/settings/telegram/test")
        check("тест мессеж сонгосон групп руу", r.status_code == 200 and fake.calls[-1][0] == "sendMessage"
              and fake.calls[-1][1]["chat_id"] == -100123 and "Мөнх эмнэлэг" in fake.calls[-1][1]["text"], r.text)
        t = tenant.Tenant(a.get("/api/me").json()["tenant"])
        check("тохиргооны файл 0600", oct(os.stat(t.settings_path).st_mode & 0o777) == "0o600")
        b = owner_client("Өөр байгууллага", "other@example.mn")
        check("өөр байгууллага хуваалцахгүй", b.get("/api/settings").json()["telegram_token_set"] is False)
    finally:
        notify.httpx.post = real_post


def test_calls():
    print("\n[7] Яриа (дуудлагын түүх)")
    import demo_data
    a = owner_client("Дуудлага тест", "calls@example.mn")
    b = owner_client("Хоосон байгууллага", "empty@example.mn")
    check("анх дуудлага алга", a.get("/api/calls").json() == [])
    t = tenant.Tenant(a.get("/api/me").json()["tenant"])
    n = demo_data.seed(t)
    calls = a.get("/api/calls").json()
    check("жишээ дуудлагууд, шинэ нь эхэндээ", len(calls) == n and calls[0]["started_at"] >= calls[-1]["started_at"], len(calls))
    first = calls[0]
    check("асуултын тоо, хугацаа", first["questions"] == 3 and first["unanswered"] == 0 and first["duration"] > 0, first)
    check("хариулж чадаагүй тоолно", sum(c["unanswered"] for c in calls) == 3, [c["unanswered"] for c in calls])
    check("limit", len(a.get("/api/calls?limit=2").json()) == 2 and a.get("/api/calls?limit=0").status_code == 422)
    find = lambda query: [c["caller"] for c in a.get(f"/api/calls?{query}").json()]  # noqa: E731
    check("шүүлтүүр: залгагчийн дугаараар", find("q=9555") == ["95554433"], find("q=9555"))
    check("шүүлтүүр: ярианы үгээр, том/жижиг үсэг хамаарахгүй", find("q=зогсоол") == ["88001122"]
          and find("q=ЗОГСООЛ") == ["88001122"], find("q=ЗОГСООЛ"))
    check("шүүлтүүр: зөвхөн хариулж чадаагүй", sorted(find("unanswered=true")) == ["80112233", "88001122", "99887766"],
          find("unanswered=true"))
    check("шүүлтүүр: хослуулах, хугацаа", find("q=зогсоол&unanswered=true&days=1") == ["88001122"]
          and len(find("days=1")) == 2 and len(find("days=365")) == 6, find("days=1"))
    check("шүүлтүүр: % _ тэмдэгт жинхэнэ утгаараа", find("q=%25") == [] and find("q=_") == [], find("q=%25"))
    d = a.get(f"/api/calls/{first['uuid']}").json()
    check("нэг дуудлагын яриа дарааллаараа", [m["role"] for m in d["messages"]] == ["user", "assistant"] * 3
          and d["messages"][1]["route"] == "faq", d)
    check("байхгүй дуудлага -> 404", a.get("/api/calls/nope").status_code == 404)
    check("өөр байгууллага харахгүй", b.get("/api/calls").json() == [] and b.get(f"/api/calls/{first['uuid']}").status_code == 404)


def test_stats():
    print("\n[8] Самбарын статистик")
    import demo_data
    from routes.stats import local_date
    a = owner_client("Статистик тест", "stats@example.mn")
    st = a.get("/api/stats").json()
    check("хоосон үед 0, 5 өдөр", st["calls"] == 0 and st["answered"] == 0 and len(st["days"]) == 5
          and all(d["calls"] == 0 for d in st["days"]), st)
    demo_data.seed(tenant.Tenant(a.get("/api/me").json()["tenant"]))
    st = a.get("/api/stats").json()
    check("дуудлага, асуулт", st["calls"] == 6 and st["questions"] == 14, st)
    check("хариулсан 8, хариулж чадаагүй 3 (бүртгэлийн алхам тоолохгүй)", st["answered"] == 8 and st["unanswered"] == 3
          and not any(r.startswith("lead_") for r in st["routes"]), st["routes"])
    check("шинэ бүртгэл", st["new_leads"] == 2)
    expected = {}
    for c in a.get("/api/calls").json():
        expected[local_date(c["started_at"])] = expected.get(local_date(c["started_at"]), 0) + 1
    check("өдөр бүрийн дуудлага (Улаанбаатарын цагаар)", all(d["calls"] == expected.get(d["date"], 0) for d in st["days"])
          and st["days"][-1]["date"] > st["days"][0]["date"], st["days"])
    check("өөр байгууллагад 0", owner_client("Статистик 2", "stats2@example.mn").get("/api/stats").json()["calls"] == 0)


def test_leads():
    print("\n[9] Бүртгэл (lead)")
    import demo_data
    a = owner_client("Бүртгэл тест", "leads@example.mn")
    b = owner_client("Бүртгэл 2", "leads2@example.mn")
    check("анх хоосон", a.get("/api/leads").json() == [])
    demo_data.seed(tenant.Tenant(a.get("/api/me").json()["tenant"]))
    leads = a.get("/api/leads").json()
    check("2 бүртгэл, шинэ нь эхэндээ, төлөв new", len(leads) == 2 and leads[0]["created_at"] >= leads[1]["created_at"]
          and {x["status"] for x in leads} == {"new"}, leads)
    lead = next(x for x in leads if x["reason"] == "lead")
    check("баталгаажсан дугаар, STT бичвэр", lead["phone"] == "95554433" and lead["phone_raw"], lead)
    handoff = next(x for x in leads if x["reason"] == "handoff")
    check("ажилтан руу шилжүүлсэн: дугааргүй, асуулттай", handoff["phone"] is None and handoff["question"], handoff)
    r = a.patch(f"/api/leads/{lead['id']}", json={"status": "contacted", "notes": "  Маргааш залгана  "})
    check("төлөв, тэмдэглэл хадгална", r.status_code == 200 and r.json()["status"] == "contacted"
          and r.json()["notes"] == "Маргааш залгана", r.text)
    check("зөвхөн тэмдэглэл -> төлөв хэвээр", a.patch(f"/api/leads/{lead['id']}", json={"notes": "ok"}).json()["status"] == "contacted")
    check("шинэ бүртгэлийн тоо буурна", a.get("/api/stats").json()["new_leads"] == 1)
    check("буруу төлөв -> 400", a.patch(f"/api/leads/{lead['id']}", json={"status": "bad"}).status_code == 400)
    check("байхгүй -> 404", a.patch("/api/leads/99999", json={"status": "done"}).status_code == 404)
    check("өөр байгууллага харахгүй, засахгүй", b.get("/api/leads").json() == []
          and b.patch(f"/api/leads/{lead['id']}", json={"status": "done"}).status_code == 404)


def test_unanswered():
    print("\n[10] Хариулж чадаагүй асуултууд")
    import demo_data
    a = owner_client("Асуулт тест", "unans@example.mn")
    check("анх хоосон", a.get("/api/unanswered").json() == [])
    demo_data.seed(tenant.Tenant(a.get("/api/me").json()["tenant"]))
    items = a.get("/api/unanswered").json()
    pairs = {(x["question"], x["route"]) for x in items}
    check("3 асуулт, тус бүр өмнөх асуулттайгаа", pairs == {
        ("Машины зогсоол бий юу", "repeat"), ("Хүүхдэд зориулсан сургалт байгаа юу", "handoff"),
        ("Мэдээлэл авъя", "clarify")}, pairs)
    check("шинэ нь эхэндээ, дуудлага руу холбоостой", items[0]["ts"] >= items[-1]["ts"]
          and a.get(f"/api/calls/{items[0]['call_uuid']}").status_code == 200)
    check("тоо нь самбартай таарна", len(items) == a.get("/api/stats").json()["unanswered"])
    check("limit", len(a.get("/api/unanswered?limit=1").json()) == 1)
    check("өөр байгууллага харахгүй", owner_client("Асуулт 2", "unans2@example.mn").get("/api/unanswered").json() == [])

    import routes.unanswered as unanswered_api
    import knowledge_jobs

    class FakeReviewResponse:
        status_code = 200

        def __init__(self, questions):
            self.questions = questions

        def json(self):
            result = []
            for question in self.questions:
                if "зогсоол" in question:
                    result.append({"q": question, "text": question, "route": "repeat", "reply": "Дахин хэлнэ үү",
                                   "suggest": [{"kind": "faq", "id": "smalltalk_hello",
                                                "text": "Сайн байна уу", "score": 0.81}]})
                elif "Хүүхдэд" in question:
                    result.append({"q": question, "text": question, "noise": True})
                else:
                    result.append({"q": question, "text": question, "route": "faq",
                                   "reply": "Одоо хариулдаг болсон", "suggest": []})
            return result

    old_post, old_enqueue = unanswered_api.httpx.post, knowledge_jobs.enqueue
    unanswered_api.httpx.post = lambda _url, json, timeout: FakeReviewResponse(json["questions"])
    try:
        reviewed = a.get("/api/unanswered/review").json()
        suggestion = next(x for x in reviewed["items"] if "зогсоол" in x["q"])["now"]["suggest"][0]
        check("live review: одоогийн route, noise, санал болгосон answer value",
              reviewed["live"] and len(reviewed["items"]) == 3 and suggestion["value"] == "faq:smalltalk_hello"
              and sum(bool(x.get("now", {}).get("noise")) for x in reviewed["items"]) == 1, reviewed)

        r = a.post("/api/unanswered/hide", json={"q": "Хүүхдэд зориулсан сургалт байгаа юу"})
        check("чимээ/шийдсэн асуултыг нуух", r.status_code == 200
              and len(a.get("/api/unanswered/review").json()["items"]) == 2, r.text)

        answer = "Манай хүүхдийн сургалтын мэдээллийг ажилтан утсаар дэлгэрэнгүй өгнө."
        body = {"q": "Мэдээлэл авъя", "answer": answer, "questions": ["Хүүхдийн сургалт бий юу"]}
        first = a.post("/api/unanswered/answer", json=body)
        second = a.post("/api/unanswered/answer", json={**body, "questions": ["Хүүхдийн анги байдаг уу"]})
        faq_rows = [x for x in tenant.load_faq(tenant.Tenant(a.get("/api/me").json()["tenant"]))["faq"]
                    if x["answer"] == answer]
        check("шинэ хариулт нэг FAQ болж, асуултын хувилбар давхардахгүй",
              first.status_code == second.status_code == 200 and len(faq_rows) == 1
              and {"Хүүхдийн сургалт бий юу", "Хүүхдийн анги байдаг уу"} <= set(faq_rows[0]["questions"]), faq_rows)

        taught = a.post("/api/unanswered/teach", json={"q": "Машины зогсоол бий юу", "answer": "faq:smalltalk_hello"})
        pending = a.get("/api/unanswered/review").json()
        check("байгаа хариултыг зааж, pending-д тэмдэглэнэ (SIM-TRUNK шиг үйлдэл бүрт)",
              taught.status_code == 200 and len(pending["pending"]) == 3 and pending["items"] == [], pending)

        knowledge_jobs.enqueue = lambda t, task="build": {"state": "queued", "task": task, "running": True,
                                                            "ahead": 0, "log": []}
        applied = a.post("/api/unanswered/apply")
        check("Хэрэгжүүлэх -> answers audio+training job, амжилттай бол pending цэвэрлэнэ",
              applied.status_code == 200 and applied.json()["task"] == "answers"
              and a.get("/api/unanswered/review").json()["pending"] == [], applied.text)
    finally:
        unanswered_api.httpx.post = old_post
        knowledge_jobs.enqueue = old_enqueue


FAKE_SIM_TENANT = """
import os
ROOT = os.path.dirname(os.path.abspath(__file__))
TENANTS_DIR = os.path.join(ROOT, "tenants")
TTS_CACHE = os.path.join(ROOT, "data", "tts_cache")
class Tenant:
    def __init__(self, slug):
        self.slug, self.dir = slug, os.path.join(TENANTS_DIR, slug)
    knowledge_dir = property(lambda self: os.path.join(self.dir, "knowledge"))
    kb_index_dir = property(lambda self: os.path.join(self.dir, "knowledge_index"))
def current():
    return Tenant(os.environ["TENANT"])
"""
FAKE_SIM_INGEST = """
import hashlib, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tenant as tenants
T = tenants.current()
facts = []
for name in sorted(os.listdir(T.knowledge_dir)):
    for line in open(os.path.join(T.knowledge_dir, name), encoding="utf-8"):
        if line.strip():
            os.makedirs(tenants.TTS_CACHE, exist_ok=True)
            wav = os.path.join(tenants.TTS_CACHE, hashlib.sha1(line.strip().encode()).hexdigest() + ".wav")
            open(wav, "wb").write(b"RIFF")
            facts.append({"text": line.strip(), "source": name, "audio": wav})
os.makedirs(T.kb_index_dir, exist_ok=True)
json.dump({"facts": facts, "indexed_at": "test"}, open(os.path.join(T.kb_index_dir, "facts.json"), "w"))
"""


def test_knowledge_build():
    print("\n[11] Мэдээлэл бэлдэх (SIM-TRUNK холболт)")
    import time
    import knowledge_jobs
    sim = tempfile.mkdtemp(prefix="fake_sim_")
    os.makedirs(os.path.join(sim, "scripts"))
    os.makedirs(os.path.join(sim, ".venv", "bin"))
    os.symlink(sys.executable, os.path.join(sim, ".venv", "bin", "python"))
    open(os.path.join(sim, "tenant.py"), "w").write(FAKE_SIM_TENANT)
    open(os.path.join(sim, "scripts", "fake_ingest.py"), "w").write(FAKE_SIM_INGEST)
    old_env, old_steps = os.environ.get("SIM_TRUNK_DIR"), knowledge_jobs.BUILD_STEPS
    os.environ["SIM_TRUNK_DIR"], knowledge_jobs.BUILD_STEPS = sim, [["scripts/fake_ingest.py"]]
    try:
        a = owner_client("Бэлдэх тест", "build@example.mn")
        a.put("/api/knowledge/file/info.md", json={"content": "Сургалт 6 сар үргэлжилнэ.\nТөлбөр сард 1,500,000 төгрөг."})
        r = a.post("/api/knowledge/build")
        st = {}
        for _ in range(100):
            st = a.get("/api/knowledge/build").json()
            if not st["running"]:
                break
            time.sleep(0.1)
        check("бэлдэлт амжилттай дуусна", st.get("state") == "done", st)
        k = a.get("/api/knowledge").json()
        check("манай мэдээллийг уншиж, үр дүн манай хавтсанд", [f["text"] for f in k["facts"]] ==
              ["Сургалт 6 сар үргэлжилнэ.", "Төлбөр сард 1,500,000 төгрөг."] and k["indexed_at"] == "test", k)
        check("SIM-TRUNK-ийн tenants хавтсанд юу ч бичихгүй", not os.path.exists(os.path.join(sim, "tenants")))
        fact = k["facts"][0]
        r = a.get(f"/api/knowledge/audio/{fact['hash']}")
        check("TTS кэш дэх аудио тоглогдоно", fact["has_audio"] and r.status_code == 200, r.status_code)
        other = owner_client("Бэлдэх 2", "build2@example.mn")
        check("өөр байгууллага бусдын аудиог авахгүй", other.get(f"/api/knowledge/audio/{fact['hash']}").status_code == 404)
    finally:
        knowledge_jobs.BUILD_STEPS = old_steps
        if old_env is None:
            os.environ.pop("SIM_TRUNK_DIR", None)
        else:
            os.environ["SIM_TRUNK_DIR"] = old_env


def test_status():
    print("\n[12] Төлөв (/api/status)")
    import json
    import socket
    import demo_data
    a = owner_client("Төлөв тест", "status@example.mn")
    t = tenant.Tenant(a.get("/api/me").json()["tenant"])
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen()
    os.environ["AI_PORT"] = str(srv.getsockname()[1])
    try:
        st = a.get("/api/status").json()
        check("AI сервер асаалттай бол ai_server=true", st["ai_server"] is True, st)
        check("шинэ байгууллага: бэлэн биш, тоо 0", st["ready"] is False and st["facts"] == st["faq"] == st["documents"] == 0
              and st["new_leads"] == st["unanswered"] == 0 and st["build_running"] is False and st["selector"] is None, st)
    finally:
        srv.close()
    check("AI сервер унтарсан бол ai_server=false", a.get("/api/status").json()["ai_server"] is False)
    os.environ.pop("AI_PORT")
    demo_data.seed(t)
    a.put("/api/knowledge/file/info.md", json={"content": "Мэдээлэл"})
    st = a.get("/api/status").json()
    check("sidebar-ын тоо самбартай таарна", st["new_leads"] == 2 and st["unanswered"] == 3
          and st["unanswered"] == a.get("/api/stats").json()["unanswered"] and st["documents"] == 1, st)
    tenant.write_json(t.path("knowledge_index", "facts.json"), {"facts": [{"text": "a"}, {"text": "b"}]})
    check("зөвхөн мэдээлэл бэлдсэн -> бэлэн биш (FAQ аудио алга)", a.get("/api/status").json()["ready"] is False)
    tenant.write_json(t.path("faq_audio", "faq_index.json"), {"faq": [{"id": "x"}]})
    tenant.write_json(t.path("knowledge_index", "selector.json"), {"enabled": True, "eval": {"selector": [41, 42]}})
    st = a.get("/api/status").json()
    check("бэлдсэн -> бэлэн, шалгалтын үр дүн", st["ready"] is True and st["facts"] == 2 and st["faq"] == 1
          and st["selector"] == {"enabled": True, "eval": {"selector": [41, 42]}}, st)
    check("өөр байгууллагад нөлөөлөхгүй", owner_client("Төлөв 2", "status2@example.mn").get("/api/status").json()["ready"] is False)
    st = a.get("/api/status").json()
    check("өөрийн хоолойгоор бичсэн: recorded / voice_total", st["recorded"] == 0 and st["voice_total"] > 20, st)
    b = owner_client("Төлөв 3", "status3@example.mn")
    tb = tenant.Tenant(b.get("/api/me").json()["tenant"])
    tenant.write_json(tb.path("knowledge_index", "facts.json"), {"facts": [], "indexed_at": "x"})
    tenant.write_json(tb.path("faq_audio", "faq_index.json"), {"faq": [{"id": "x"}]})
    check("мэдээллийн өгүүлбэргүй ч хоёр индекс бэлдсэн бол бэлэн (SIM-TRUNK шиг)", b.get("/api/status").json()["ready"] is True)
    faq = tenant.load_faq(tb)
    tenant.write_json(tb.faq_path, {"_note": "тайлбар", **faq})
    b.put("/api/faq", json=b.get("/api/faq").json())
    check("FAQ хадгалахад _note тайлбар хэвээр", tenant.load_faq(tb).get("_note") == "тайлбар")
    cfg = tb.config()
    cfg["eleven_voice_name"] = "Uyanga - Kind Khalkha Friend"
    tb.save_config(cfg)
    check("хоолойн нэр сангийн тайлбаргүй (SIM-TRUNK шиг)", b.get("/api/voice").json()["voice"]["name"] == "Uyanga")


def test_training_model():
    print("\n[13] AI сургалт: сургасан загвар")
    a = owner_client("Сургалт тест", "train@example.mn")
    t = tenant.Tenant(a.get("/api/me").json()["tenant"])
    check("сургаагүй үед model алга", a.get("/api/train").json()["model"] is None)
    meta = {"enabled": True, "examples": 120, "eval": {"selector": [41, 42], "rules": [40, 42]},
            "labels": ["faq:price", "fact:0a1b2c3d4e5f", "clarify"], "answers": {"faq:price": {"kind": "faq", "id": "price"}},
            "label_stems": {"faq:price": ["үнэ"]}, "per_label": {"faq:price": 1.0}}       # бодит selector.json шиг
    tenant.write_json(t.path("knowledge_index", "selector.json"), meta)   # train_selector.py-ийн бичдэг газар
    model = a.get("/api/train").json()["model"]
    check("train_selector.py-ийн үр дүн харагдана", model["enabled"] is True and model["examples"] == 120
          and model["eval"] == meta["eval"], model)
    check("хариултын тоо (dict биш), том талбарууд илгээхгүй", model["answers"] == 3
          and "label_stems" not in model and "per_label" not in model, model)


def test_admin():
    print("\n[14] Байгууллагууд (admin)")
    import demo_data
    tenant.ensure_default()
    accounts.create_user("root", "root-pass-123", role="admin")
    adm = TestClient(app)
    login(adm, "root", "root-pass-123")
    owner = owner_client("Admin тест", "admintest@example.mn")
    slug = owner.get("/api/me").json()["tenant"]
    demo_data.seed(tenant.Tenant(slug))
    blocked = [owner.get("/api/admin/tenants").status_code, owner.post("/api/admin/switch", json={"slug": slug}).status_code,
               owner.post("/api/admin/plan", json={"slug": slug, "plan": "active"}).status_code]
    check("owner-т хаалттай (403)", blocked == [403, 403, 403], blocked)
    rows = {x["slug"]: x for x in adm.get("/api/admin/tenants").json()}
    row = rows.get(slug, {})
    check("бүх байгууллага: хэрэглэгч, дуудлагын тоо, эрх", "pinecone" in rows and row.get("users") == ["admintest@example.mn"]
          and row.get("calls") == 6 and row.get("plan") == "trial" and row.get("ready") is False, row)
    r = adm.post("/api/admin/plan", json={"slug": slug, "plan": "active"})
    check("эрх идэвхжүүлнэ", r.status_code == 200 and owner.get("/api/me").json()["plan"] == "active", r.text)
    check("буруу эрх / байхгүй байгууллага", adm.post("/api/admin/plan", json={"slug": slug, "plan": "vip"}).status_code == 400
          and adm.post("/api/admin/plan", json={"slug": "baikhgui", "plan": "active"}).status_code == 404
          and adm.post("/api/admin/switch", json={"slug": "../etc"}).status_code == 404)
    r = adm.post("/api/admin/switch", json={"slug": slug})
    me = adm.get("/api/me").json()
    check("сольсны дараа тэр байгууллагыг харна", r.status_code == 200 and me["tenant"] == slug and me["own_tenant"] is False
          and adm.get("/api/org").json()["name"] == "Admin тест" and len(adm.get("/api/calls").json()) == 6, me)
    adm.post("/api/admin/switch", json={"slug": "pinecone"})
    check("өөрийнхөө руу буцна", adm.get("/api/me").json()["own_tenant"] is True)
    forged = owner.get("/api/me", headers={"cookie": f"{auth.COOKIE}={owner.cookies.get(auth.COOKIE)}; {auth.TENANT_COOKIE}=pinecone"}).json()
    check("owner cookie хуурсан ч өөрийнхөө байгууллагыг л харна", forged["tenant"] == slug, forged)
    adm.post("/api/admin/switch", json={"slug": slug})
    r = adm.delete("/api/admin/switch")
    check("«Өөрийнхөө руу буцах» (DELETE /api/admin/switch)", r.status_code == 200 and adm.get("/api/me").json()["tenant"] == "pinecone")
    check("owner буцах товч ашиглах -> 403", owner.delete("/api/admin/switch").status_code == 403)
    adm.post("/api/admin/switch", json={"slug": slug})
    adm.post("/api/logout")
    login(adm, "root", "root-pass-123")
    check("дахин нэвтрэхэд өөрийн байгууллага", adm.get("/api/me").json()["tenant"] == "pinecone")

    new = {"name": "Нэмсэн сургууль", "phone": "7011 2233", "email": "info@nemsen.mn", "address": "Сүхбаатар дүүрэг",
           "hours": "", "owner_email": "ezen@example.mn", "password": "ezen-pass-123"}
    check("owner байгууллага нэмэх -> 403", owner.post("/api/admin/tenants", json=new).status_code == 403)
    r = adm.post("/api/admin/tenants", json=new)
    new_slug = r.json().get("slug")
    row = {x["slug"]: x for x in adm.get("/api/admin/tenants").json()}.get(new_slug, {})
    check("admin байгууллага + эзэмшигч нэмнэ", r.status_code == 200 and row.get("users") == ["ezen@example.mn"]
          and row.get("address") == "Сүхбаатар дүүрэг" and row.get("email") == "info@nemsen.mn", (r.text, row))
    check("admin нэвтэрсэн хэвээр", adm.get("/api/me").json()["email"] == "root")
    ezen = TestClient(app)
    check("эзэмшигч нэвтэрч өөрийн байгууллагыг харна", login(ezen, "ezen@example.mn", "ezen-pass-123").status_code == 200
          and ezen.get("/api/me").json()["tenant"] == new_slug and ezen.get("/api/org").json()["phone"] == "70112233")
    before = len(tenant.all_tenants())
    dup = adm.post("/api/admin/tenants", json={**new, "name": "Давхар"})
    check("давхардсан эзэмшигчийн и-мэйл -> 400, байгууллага үлдэхгүй",
          dup.status_code == 400 and len(tenant.all_tenants()) == before, dup.text)
    bad = [adm.post("/api/admin/tenants", json={**new, "owner_email": "x@example.mn", "password": "short"}).status_code,
           adm.post("/api/admin/tenants", json={**new, "owner_email": "buruu"}).status_code,
           adm.post("/api/admin/tenants", json={**new, "owner_email": "y@example.mn", "email": "buruu"}).status_code]
    check("буруу нууц үг / и-мэйл -> 400", bad == [400, 400, 400], bad)


def wav_bytes(seconds: float = 1.0, rate: int = 24000, channels: int = 1) -> bytes:
    import io
    import math
    import struct
    import wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        n = int(seconds * rate)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i / 20))) * channels for i in range(n)))
    return buf.getvalue()


def test_recordings():
    print("\n[15] Өөрийн хоолойгоор бичих")
    a = owner_client("Хоолой тест", "voice@example.mn")
    t = tenant.Tenant(a.get("/api/me").json()["tenant"])
    items = a.get("/api/voice").json()["items"]
    greet = next(x for x in items if x["kind"] == "мэндчилгээ")
    check("өгүүлбэр бүр бичлэггүй (ElevenLabs) эхэлнэ", items and not any(x["recorded"] for x in items), items[:2])
    up = lambda h, data: a.post(f"/api/voice/recording/{h}", files={"file": ("rec.wav", data, "audio/wav")})  # noqa: E731
    r = up(greet["hash"], wav_bytes(1.2))
    check("бичлэг хадгална", r.status_code == 200 and abs(r.json()["seconds"] - 1.2) < 0.05, r.text)
    check("SIM-TRUNK-тэй ижил газар (recordings/<hash>.wav) — Бэлдэхэд TTS-ийн оронд",
          os.path.exists(t.path("recordings", f"{greet['hash']}.wav")))
    check("жагсаалтад бичлэгтэй гэж харагдана", next(x for x in a.get("/api/voice").json()["items"]
                                                    if x["hash"] == greet["hash"])["recorded"] is True)
    r = a.get(f"/api/voice/audio/{greet['hash']}")
    check("сонсох -> WAV", r.status_code == 200 and r.content[:4] == b"RIFF", r.status_code)
    bad = [up(greet["hash"], b"not a wav").status_code, up(greet["hash"], wav_bytes(0.1)).status_code]
    check("WAV биш / хэт богино -> 400", bad == [400, 400], bad)
    import wave
    r = up(greet["hash"], wav_bytes(1, rate=44100, channels=2))
    with wave.open(t.path("recordings", f"{greet['hash']}.wav"), "rb") as w:
        fmt = (w.getframerate(), w.getnchannels())
    check("44.1kHz stereo -> 24kHz mono болгоно", r.status_code == 200 and fmt == (24000, 1), (r.status_code, fmt))
    check("байхгүй өгүүлбэр -> 404, буруу hash -> 400", up("0" * 12, wav_bytes()).status_code == 404
          and a.get("/api/voice/audio/..%2F..%2Fx").status_code in (400, 404))
    other = owner_client("Хоолой 2", "voice2@example.mn")
    check("өөр байгууллага сонсох / устгах боломжгүй", other.get(f"/api/voice/audio/{greet['hash']}").status_code == 404
          and other.delete(f"/api/voice/recording/{greet['hash']}").status_code == 404)
    r = a.delete(f"/api/voice/recording/{greet['hash']}")
    check("устгахад ElevenLabs руу буцна", r.status_code == 200 and not os.path.exists(t.path("recordings", f"{greet['hash']}.wav"))
          and a.get(f"/api/voice/audio/{greet['hash']}").status_code == 404)
    a.put("/api/knowledge/file/info.md", json={"content": "## Хугацаа\nСургалт 6 сар үргэлжилнэ. Богино.\n"})
    check("мэдээллийн файлын өгүүлбэр жагсаалтад (SIM-TRUNK ingest.split_facts)",
          [(x["kind"], x["text"]) for x in a.get("/api/voice").json()["items"] if x["kind"].startswith("мэдээлэл")]
          == [("мэдээлэл info.md", "Сургалт 6 сар үргэлжилнэ.")])


FAKE_ELEVEN_SIM = {
    "tenant.py": """
import os
TENANTS_DIR = ""
class Tenant:
    def __init__(self, slug):
        self.slug, self.dir = slug, os.path.join(TENANTS_DIR, slug)
    def path(self, *parts):
        return os.path.join(self.dir, *parts)
def current():
    return Tenant(os.environ["TENANT"])
""",
    "soundfile.py": """
import struct, wave
def write(path, data, sr):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(b"".join(struct.pack("<h", int(x * 32767)) for x in data))
""",
    "stream_voice.py": """
def tts_engine():
    return {"voice": None, "model": "eleven_v4", "speed": 1.0}
def eleven_tag(eng):
    return f"eleven-{eng['voice']}-{eng['model']}-s{round(eng['speed'] * 100)}"
class ElevenTTS:
    def __init__(self, voice=None):
        self.voice = voice
    def synth(self, text):
        return [0.1, -0.1] * 2400, 24000
""",
}


class FakeResponse:
    def __init__(self, status: int, data: dict):
        self.status_code, self.data = status, data

    def json(self):
        return self.data

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPError(f"HTTP {self.status_code}")


def test_eleven():
    print("\n[16] ElevenLabs хоолой (admin)")
    import time
    import eleven
    import knowledge_jobs
    sim = tempfile.mkdtemp(prefix="fake_eleven_")
    os.makedirs(os.path.join(sim, ".venv", "bin"))
    os.symlink(sys.executable, os.path.join(sim, ".venv", "bin", "python"))
    for name, code in FAKE_ELEVEN_SIM.items():
        open(os.path.join(sim, name), "w", encoding="utf-8").write(code)
    good_key = "sk_" + "a" * 40

    def fake_get(url, headers=None, params=None, timeout=None):
        if headers.get("xi-api-key") != good_key:
            return FakeResponse(401, {})
        if url.endswith("/shared-voices"):
            return FakeResponse(200, {"voices": [{"voice_id": eleven.DEFAULT_VOICE, "name": "Uyanga", "gender": "female"}]})
        return FakeResponse(200, {"voices": [{"voice_id": "LauraVoice0001", "name": "Laura - Enthusiastic",
                                              "labels": {"gender": "female", "accent": "american"}}]})

    old_env, old_get = os.environ.get("SIM_TRUNK_DIR"), eleven.httpx.get
    os.environ["SIM_TRUNK_DIR"], eleven.httpx.get = sim, fake_get
    try:
        accounts.create_user("eleven-admin", "eleven-pass-123", role="admin")
        adm = TestClient(app)
        login(adm, "eleven-admin", "eleven-pass-123")
        owner = owner_client("Eleven тест", "eleven@example.mn")
        blocked = [owner.get("/api/admin/eleven").status_code,
                   owner.post("/api/admin/eleven/key", json={"key": good_key}).status_code]
        check("owner-т хаалттай (403)", blocked == [403, 403], blocked)
        st = adm.get("/api/admin/eleven").json()
        check("түлхүүргүй үед хоолой алга", st["has_key"] is False and st["voices"] == [] and st["voice"] is None, st)
        check("түлхүүргүй үед үүсгэхгүй",
              adm.post("/api/admin/eleven/generate", json={"voice": eleven.DEFAULT_VOICE}).status_code == 400)
        bad = [adm.post("/api/admin/eleven/key", json={"key": k}).status_code for k in ("abc", "sk_" + "b" * 40)]
        check("буруу түлхүүр хадгалагдахгүй (хэлбэр, ElevenLabs 401)", bad == [400, 400] and not os.path.exists(eleven.KEY_FILE), bad)
        r = adm.post("/api/admin/eleven/key", json={"key": good_key})
        mode = oct(os.stat(eleven.KEY_FILE).st_mode & 0o777) if os.path.exists(eleven.KEY_FILE) else None
        check("зөв түлхүүр хадгалагдана (600), буцааж харуулахгүй", r.status_code == 200 and mode == "0o600"
              and good_key not in adm.get("/api/admin/eleven").text, (r.status_code, mode))
        st = adm.get("/api/admin/eleven").json()
        names = [v["name"] for v in st["voices"]]
        check("анхдагч хоолой Уянга, монгол хоолой эхэнд", st["voice"] == eleven.DEFAULT_VOICE and names[0] == "🇲🇳 Uyanga"
              and st["voices"][0]["library"] and len(names) == 2, st["voices"])
        samples = [i for i in st["items"] if i["sample"]]
        check("төлөөлөх жишээ өгүүлбэрүүд (≤8)", 0 < len(samples) <= eleven.SAMPLES, len(samples))
        r = adm.post("/api/admin/eleven/generate", json={"voice": eleven.DEFAULT_VOICE, "scope": "sample"})
        for _ in range(100):
            job = adm.get("/api/admin/eleven").json()["job"]
            if not job["running"]:
                break
            time.sleep(0.1)
        check("жишээ үүснэ (SIM-TRUNK-ийн ElevenTTS)", r.status_code == 200 and job["done"] == len(samples)
              and not job["error"], job)
        st = adm.get("/api/admin/eleven").json()
        made = [i for i in st["items"] if eleven.DEFAULT_VOICE in i["eleven"]]
        check("үүсгэсэн өгүүлбэр жагсаалтад тэмдэглэгдэнэ", {i["hash"] for i in made} == {i["hash"] for i in samples}, made)
        h = samples[0]["hash"]
        a = adm.get(f"/api/admin/eleven/audio/{eleven.DEFAULT_VOICE}/{h}")
        p = adm.get(f"/api/admin/eleven/audio/{eleven.DEFAULT_VOICE}/{h}?phone=1")
        check("жишээг сонсох, утасны чанараар (8kHz)", a.status_code == 200 and p.status_code == 200
              and int.from_bytes(p.content[24:28], "little") == 8000, (a.status_code, p.status_code))
        r = adm.post("/api/admin/eleven/generate", json={"voice": eleven.DEFAULT_VOICE, "scope": "sample"}).json()
        check("үүсгэснийг дахин үүсгэхгүй (төлбөр хэмнэнэ)", r["total"] == 0 and not r["running"], r)
        wrong = [adm.get(f"/api/admin/eleven/audio/{eleven.DEFAULT_VOICE}/zz").status_code,
                 adm.get("/api/admin/eleven/audio/bad!/0123456789ab").status_code,
                 adm.get(f"/api/admin/eleven/audio/LauraVoice0001/{h}").status_code]
        check("буруу hash, хоолой / үүсгээгүй жишээ", wrong == [400, 400, 404], wrong)
        r = adm.put("/api/admin/eleven/choice", json={"voice": "LauraVoice0001", "clips": {h: "eleven", "000000000000": "eleven"}})
        cfg = tenant.Tenant(adm.get("/api/me").json()["tenant"]).config()
        check("хоолой сонгоход байгууллагын тохиргоонд (SIM-TRUNK шиг)", r.json() == {"ok": True, "eleven": 1}
              and cfg.get("eleven_voice") == "LauraVoice0001" and cfg.get("eleven_voice_name") == "Laura - Enthusiastic"
              and cfg.get("clip_engine") == {h: "eleven"}, (r.json(), cfg))
    finally:
        eleven.httpx.get = old_get
        if os.path.exists(eleven.KEY_FILE):
            os.remove(eleven.KEY_FILE)
        if old_env is None:
            os.environ.pop("SIM_TRUNK_DIR", None)
        else:
            os.environ["SIM_TRUNK_DIR"] = old_env


def test_voice_eleven_only():
    print("\n[17] Хоолой (Oron-гүй)")
    import io
    import json
    import time
    import zipfile
    import knowledge_jobs
    old_env = os.environ.get("SIM_TRUNK_DIR")
    os.environ["SIM_TRUNK_DIR"] = tempfile.mkdtemp(prefix="no_sim_")    # Python орчингүй -> ажил шууд дуусна
    try:
        a = owner_client("Хоолой Eleven", "voice-eleven@example.mn")
        t = tenant.Tenant(a.get("/api/me").json()["tenant"])
        v = a.get("/api/voice").json()
        check("түлхүүргүй үед хоолой алга, Oron-ийн асуултын аялга алга",
              v["voice"]["has_key"] is False and v["voice"]["name"] == "ElevenLabs" and "question" not in v, v.get("voice"))
        cfg = t.config()
        cfg.update(eleven_voice="LauraVoice0001", eleven_voice_name="Laura")
        t.save_config(cfg)
        check("сонгосон хоолой харагдана", a.get("/api/voice").json()["voice"]["name"] == "Laura")
        removed = [a.get("/api/voice/reference").status_code, a.get("/api/voice/question/audio").status_code]
        check("Oron-ийн лавлах хоолой, асуултын аялга хасагдсан", all(code >= 400 for code in removed), removed)

        def wait():
            for _ in range(100):
                if not knowledge_jobs.status(t)["running"]:
                    return
                time.sleep(0.05)

        item = next(x for x in v["items"] if x["kind"] == "мэндчилгээ")
        r = a.post(f"/api/voice/regenerate/{item['hash']}")
        wait()
        seeds = json.load(open(t.path("data", "tts_seeds.json"), encoding="utf-8"))
        again = next(x for x in a.get("/api/voice").json()["items"] if x["hash"] == item["hash"])
        check("↻ ElevenLabs-ийн seed (eleven:<hash>) нэмэгдэнэ", r.status_code == 200 and seeds == {f"eleven:{item['hash']}": 1}
              and again["seed"] == 1, seeds)
        r = a.post("/api/voice/rebuild")
        check("аудиог шинэчлэх ажил эхэлнэ", r.status_code == 200 and r.json()["task"] == "regen", r.text)
        wait()
        a.post(f"/api/voice/recording/{item['hash']}", files={"file": ("rec.wav", wav_bytes(1.0), "audio/wav")})
        r = a.get("/api/voice/export")
        z = zipfile.ZipFile(io.BytesIO(r.content))
        manifest = json.loads(z.read("manifest.json"))
        check("ZIP: бичлэг + manifest (json, csv)", r.status_code == 200 and f"audio/{item['hash']}.wav" in z.namelist()
              and "manifest.csv" in z.namelist() and manifest["clips"][0]["source"] == "бичлэг", z.namelist())
    finally:
        if old_env is None:
            os.environ.pop("SIM_TRUNK_DIR", None)
        else:
            os.environ["SIM_TRUNK_DIR"] = old_env


def test_voice_texts():
    print("\n[18] Хоолойн жагсаалт = SIM-TRUNK record.all_texts")
    a = owner_client("Хэллэг тест", "phrases@example.mn")
    t = tenant.Tenant(a.get("/api/me").json()["tenant"])
    items = a.get("/api/voice").json()["items"]
    kinds = list(dict.fromkeys(x["kind"] for x in items))
    check("төрлүүд SIM-TRUNK-ийн дарааллаар", kinds[:9] == ["мэндчилгээ", "filler", "hold", "алдаа", "дахин асуух",
                                                         "тодруулах", "бүртгэл", "цифр", "FAQ smalltalk_hello"], kinds)
    lead = [x["text"] for x in items if x["kind"] == "бүртгэл"]
    check("бүртгэлийн хэллэг байгууллагын хэллэгээс (нэр орсон)", lead == list(t.phrases()["lead"].values())
          and "Таны мэдээллийг амжилттай бүртгэлээ. Манай ажилтан тантай удахгүй холбогдоно. Өөр асуух зүйл байна уу?" in lead, lead)
    cfg = t.config()
    cfg["phrases"] = {"error": "Уучлаарай, {name}-ийн ажилтан эргэж залгана."}
    t.save_config(cfg)
    items = a.get("/api/voice").json()["items"]
    check("config phrases өөрчлөхөд жагсаалт шууд дагана", [x["text"] for x in items if x["kind"] == "алдаа"]
          == ["Уучлаарай, Хэллэг тест-ийн ажилтан эргэж залгана."])
    v = a.get("/api/voice").json()
    check("SIM-TRUNK-ийн талбарууд (engine, eleven_voice, oron)", all(x["engine"] == "eleven" for x in v["items"])
          and v["eleven_voice"] == "ElevenLabs" and v["oron"] is False, {k: v[k] for k in ("eleven_voice", "oron")})


def test_tenant_sim_parity():
    print("\n[19] Байгууллагын загвар = SIM-TRUNK")
    t = tenant.create("Загвар тест", phone="7011 2233")
    faq = tenant.load_faq(t)
    ids = {x["id"] for x in faq["faq"]}
    check("утасны ярианы FAQ (сонсогдож байна уу, дахин хэлэх, буруу дугаар ...)",
          {"phone_hear_check", "phone_bad_line", "repeat_last", "phone_wait", "phone_which_org",
           "phone_call_later", "phone_wrong_number", "contact_phone"} <= ids, sorted(ids))
    ph = t.phrases()
    check("хэллэгт нэр, утас орно", "Загвар тест" in ph["greeting"] and "дал, арван нэг, хорин хоёр, гучин гурав" in ph["lead"]["done_no_phone"], ph["lead"])
    cfg = t.config()
    cfg["phrases"] = {"greeting": "Сайн байна уу, {name}. Юугаар туслах вэ?"}
    t.save_config(cfg)
    faq["faq"].append({"id": "custom_1", "questions": ["Үнэ"], "answer": "Гараар бичсэн хариулт."})
    tenant.write_json(t.faq_path, faq)
    tenant.refresh_faq(t)
    after = tenant.load_faq(t)
    check("мэндчилгээ config phrases-аас, гараар нэмсэн FAQ хэвээр",
          after["greeting"] == "Сайн байна уу, Загвар тест. Юугаар туслах вэ?"
          and any(x["id"] == "custom_1" for x in after["faq"]), after["greeting"])


if __name__ == "__main__":
    test_login()
    test_signup()
    test_org()
    test_password()
    test_telegram()
    test_calls()
    test_stats()
    test_leads()
    test_unanswered()
    test_knowledge_build()
    test_status()
    test_training_model()
    test_admin()
    test_recordings()
    test_eleven()
    test_voice_eleven_only()
    test_voice_texts()
    test_tenant_sim_parity()
    print(f"\n{'ТЭНЦЛЭЭ ✓' if not failures else f'ТЭНЦЭЭГҮЙ: {len(failures)} шалгалт'}")
    sys.exit(1 if failures else 0)
