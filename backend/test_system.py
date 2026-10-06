"""
Backend-ийн тест. Кодыг өөрчилсний дараа, PR-ийн өмнө ажиллуулна.

  .venv/bin/python backend/test_system.py

1-2. Нэвтрэлт: нэвтрэх, буруу нууц үг, хамгаалалттай API, гарах, хуурамч cookie,
     нууц үг солиход хуучин session хүчингүй, буруу оролдлогын хязгаар (IP + и-мэйл)
3. Байгууллага бүртгүүлэх: шинэ байгууллага, загвар FAQ, давхардал, хязгаар
4. Байгууллагын мэдээлэл (Тохируулах): засах, загвар FAQ дахин үүсэх, байгууллага хооронд тусгаарлалт
5. Нууц үг солих: одоогийн нууц үг шалгах, энэ төхөөрөмж нэвтэрсэн хэвээр, бусад нь гарна

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


if __name__ == "__main__":
    test_login()
    test_signup()
    test_org()
    test_password()
    print(f"\n{'ТЭНЦЛЭЭ ✓' if not failures else f'ТЭНЦЭЭГҮЙ: {len(failures)} шалгалт'}")
    sys.exit(1 if failures else 0)
