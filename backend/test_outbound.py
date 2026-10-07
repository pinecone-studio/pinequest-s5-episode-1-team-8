"""
AI-аас гарах дуудлага (сануулга): товчлуур таних, SIP залгагч (хуурамч GSM gateway-тэй), дуудлагын яриа.

  .venv/bin/python backend/test_outbound.py

Хуурамч gateway нь бодит GoIP/Dinstar шиг: digest нэвтрэлт, 180 -> 200 OK (SDP), RTP хүлээн авна,
товчлуурыг RFC 4733 / SIP INFO / дуун дотор илгээнэ, завгүй (486), утсаа авахгүй (CANCEL хүлээнэ).
"""
import hashlib
import os
import re
import socket
import struct
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="pc_out_")
os.environ["OUTBOUND_SCHEDULER"] = "0"          # тест өөрөө run_due() дуудна

import numpy as np  # noqa: E402

from outbound import dtmf, session  # noqa: E402
from outbound.call import SR  # noqa: E402
from outbound.sip import SipCall, SipConfig, SipError, ping  # noqa: E402

failures: list[str] = []


def check(name: str, ok: bool, detail: object = ""):
    print(f"  {'✓' if ok else '✗'} {name}" + (f"  ({detail})" if not ok and detail != "" else ""))
    if not ok:
        failures.append(name)


def hdr(msg: str, name: str) -> str:
    m = re.search(rf"^{name}\s*:\s*(.+)$", msg, re.I | re.M)
    return m.group(1).strip() if m else ""


class FakeGateway(threading.Thread):
    """Нэг дуудлага хүлээн авах GSM gateway-ийн дуурайгч."""

    def __init__(self, mode="answer", dtmf_mode="rfc4733", digit="1", password="", after_packets=60):
        super().__init__(daemon=True)
        self.mode, self.dtmf_mode, self.digit, self.password = mode, dtmf_mode, digit, password
        self.after = after_packets
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.rtp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rtp.bind(("127.0.0.1", 0))
        self.log: list[str] = []
        self.rtp_in = 0
        self.auth_ok = None
        self.invite_uri = ""
        self.stop = False
        self.peer_rtp = None
        self.client = None

    def reply(self, req: str, code: int, reason: str, extra=(), body=""):
        lines = [f"SIP/2.0 {code} {reason}"] + [f"{n}: {hdr(req, n)}" for n in ("Via", "From", "Call-ID", "CSeq")]
        to = hdr(req, "To") + (";tag=gw1" if code > 100 and "tag=" not in hdr(req, "To") else "")
        lines += [f"To: {to}", *extra]
        if body:
            lines.append("Content-Type: application/sdp")
        lines += [f"Content-Length: {len(body)}", "", body]
        self.sock.sendto("\r\n".join(lines).encode(), self.client)

    def run(self):
        self.sock.settimeout(0.2)
        threading.Thread(target=self.rtp_loop, daemon=True).start()
        while not self.stop:
            try:
                data, addr = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                return
            msg = data.decode()
            method = msg.split()[0]
            self.log.append(method)
            self.client = addr
            if method == "OPTIONS":
                self.reply(msg, 200, "OK")
            elif method == "INVITE":
                self.invite_uri, self.invite = msg.split()[1], msg
                auth = hdr(msg, "Authorization")
                if self.password and not auth:
                    self.reply(msg, 401, "Unauthorized", ['WWW-Authenticate: Digest realm="goip", nonce="abc123"'])
                    continue
                if self.password:
                    p = dict(re.findall(r'(\w+)="?([^",]+)"?', auth))
                    ha1 = hashlib.md5(f"{p['username']}:goip:{self.password}".encode()).hexdigest()
                    ha2 = hashlib.md5(f"INVITE:{p['uri']}".encode()).hexdigest()
                    self.auth_ok = p["response"] == hashlib.md5(f"{ha1}:abc123:{ha2}".encode()).hexdigest()
                self.reply(msg, 100, "Trying")
                if self.mode == "busy":
                    self.reply(msg, 486, "Busy Here")
                    continue
                self.reply(msg, 180, "Ringing")
                if self.mode == "silent":
                    continue
                body = msg.split("\r\n\r\n", 1)[1]
                port = int(re.search(r"m=audio (\d+)", body).group(1))
                self.peer_rtp = ("127.0.0.1", port)
                time.sleep(0.3)
                sdp = ("v=0\r\no=gw 1 1 IN IP4 127.0.0.1\r\ns=gw\r\nc=IN IP4 127.0.0.1\r\nt=0 0\r\n"
                       f"m=audio {self.rtp.getsockname()[1]} RTP/AVP 0 101\r\na=rtpmap:0 PCMU/8000\r\n"
                       "a=rtpmap:101 telephone-event/8000\r\n")
                self.reply(msg, 200, "OK", [f"Contact: <sip:gw@127.0.0.1:{self.port}>"], sdp)
            elif method in ("BYE", "CANCEL"):
                self.reply(msg, 200, "OK")
                if method == "CANCEL":
                    self.reply(self.invite, 487, "Request Terminated")

    def rtp_loop(self):
        import audioop
        self.rtp.settimeout(0.2)
        sent_digit = False
        seq, ts = 1, 1000
        while not self.stop:
            try:
                data, _ = self.rtp.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                return
            self.rtp_in += 1
            if self.rtp_in >= self.after and not sent_digit and self.peer_rtp:
                sent_digit = True
                if self.dtmf_mode == "rfc4733":
                    for i in range(3):        # end bit-тэй 3 пакет (дахин илгээлт)
                        payload = bytes(["0123456789*#".index(self.digit), 0x8A, 0, 160])
                        self.rtp.sendto(struct.pack("!BBHII", 0x80, 101, seq + i, ts, 77) + payload, self.peer_rtp)
                elif self.dtmf_mode == "inband":
                    tone = (dtmf.tone(self.digit, SR, 0.2) * 32767).astype("<i2").tobytes()
                    for i in range(0, len(tone), 320):
                        self.rtp.sendto(struct.pack("!BBHII", 0x80, 0, seq, ts, 77) + audioop.lin2ulaw(tone[i:i + 320], 2),
                                        self.peer_rtp)
                        seq, ts = seq + 1, ts + 160
                        time.sleep(0.02)
                elif self.dtmf_mode == "info":
                    info = "\r\n".join([f"INFO sip:ai@127.0.0.1 SIP/2.0", f"Via: SIP/2.0/UDP 127.0.0.1:{self.port};branch=z9hG4bKi1",
                                        f"From: {hdr(self.invite, 'To')};tag=gw1", f"To: {hdr(self.invite, 'From')}",
                                        f"Call-ID: {hdr(self.invite, 'Call-ID')}", "CSeq: 1 INFO",
                                        "Content-Type: application/dtmf-relay", "Content-Length: 22", "",
                                        f"Signal={self.digit}\r\nDuration=160"])
                    self.sock.sendto(info.encode(), self.client)

    def close(self):
        self.stop = True
        time.sleep(0.3)
        self.sock.close()
        self.rtp.close()


def clips(seconds: float = 0.6) -> dict:
    t = np.arange(int(24000 * seconds)) / 24000
    wav = (0.2 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
    return {k: (wav, 24000) for k in ("message", "repeat", "confirmed", "declined", "no_input")}


def call(gw: FakeGateway, password="", number="99112233", ring=3):
    cfg = SipConfig(host="127.0.0.1", port=gw.port, user="ai", password=password, local_ip="127.0.0.1", ring_timeout=ring)
    return SipCall(cfg, number)


def test_dtmf():
    print("\n[1] Товчлуур таних (Goertzel)")
    rng = np.random.default_rng(1)
    noise = (0.2 * rng.standard_normal(SR)).astype(np.float32)
    sig = np.concatenate([noise, dtmf.tone("1", SR), np.zeros(800, np.float32), dtmf.tone("2", SR), noise])
    check("1, 2 (чимээний дунд)", dtmf.detect(sig, SR) == ["1", "2"], dtmf.detect(sig, SR))
    check("зөвхөн чимээ -> товч алга", dtmf.detect(noise, SR) == [])
    check("бүх 16 товч", all(dtmf.detect(dtmf.tone(k, SR, 0.12), SR) == [k] for row in dtmf.KEYS for k in row))


def test_sip():
    print("\n[2] SIP залгагч ↔ хуурамч GSM gateway")
    gw = FakeGateway(password="secret", dtmf_mode="rfc4733", digit="1")
    gw.start()
    ok, first = ping(SipConfig(host="127.0.0.1", port=gw.port, local_ip="127.0.0.1"))
    check("gateway шалгах (OPTIONS)", ok and "200" in first, first)
    c = call(gw, password="secret").dial()
    check("digest нэвтрэлт, утсаа авлаа (200 OK -> ACK)", gw.auth_ok is True and c.state == "up"
          and gw.invite_uri.startswith("sip:99112233@"), (gw.auth_ok, c.state, gw.invite_uri))
    outcome, pressed = session.run(c, clips())
    c.hangup()
    time.sleep(0.3)
    check("мессеж RTP-ээр явж, 1 дарахад баталгаажсан", outcome == "confirmed" and gw.rtp_in >= 60, (outcome, pressed, gw.rtp_in))
    check("дуусахад BYE", "BYE" in gw.log, gw.log)
    gw.close()

    for mode, digit, want in (("inband", "2", "declined"), ("info", "1", "confirmed")):
        gw = FakeGateway(dtmf_mode=mode, digit=digit)
        gw.start()
        c = call(gw).dial()
        outcome, _ = session.run(c, clips())
        c.hangup()
        check(f"товчлуур {mode}: {digit} -> {want}", outcome == want, outcome)
        gw.close()

    gw = FakeGateway(dtmf_mode="none")
    gw.start()
    c = call(gw).dial()
    session.WAIT_FIRST, session.WAIT_REPEAT = 0.5, 0.5
    outcome, _ = session.run(c, clips(0.2))
    c.hangup()
    check("товч дараагүй -> дахин асуугаад unconfirmed", outcome == "unconfirmed", outcome)
    gw.close()

    gw = FakeGateway(mode="busy")
    gw.start()
    try:
        call(gw).dial()
        check("завгүй -> busy", False)
    except SipError as e:
        check("завгүй (486) -> busy", e.outcome == "busy", e)
    gw.close()

    gw = FakeGateway(mode="silent")
    gw.start()
    try:
        call(gw, ring=1).dial()
        check("утсаа аваагүй -> no_answer", False)
    except SipError as e:
        time.sleep(0.3)
        check("утсаа аваагүй -> CANCEL, no_answer", e.outcome == "no_answer" and "CANCEL" in gw.log, (e.outcome, gw.log))
    gw.close()


def test_reminders():
    print("\n[3] Сануулга: товлох -> хуваарьт залгагч -> gateway -> үр дүн")
    import soundfile as sf
    from fastapi.testclient import TestClient
    import accounts
    import app as server
    import db
    import notify
    import reminders
    import tenant

    def fake_synth(t, todo, out):      # ElevenLabs-ийн оронд (токен зарцуулахгүй)
        for item in todo:
            sf.write(os.path.join(out, f"{item['hash']}.wav"), clips(0.3)["message"][0], 24000)
    reminders.synth = fake_synth
    reminders.in_hours = lambda now=None: True
    session.WAIT_FIRST, session.WAIT_REPEAT = 4, 4
    sent: list[str] = []
    notify.send = lambda t, text: sent.append(text) or True

    tenant.ensure_default()
    accounts.create_user("rem-admin", "rem-pass-123", role="admin")
    adm = TestClient(server.app)
    adm.post("/api/login", json={"email": "rem-admin", "password": "rem-pass-123"})
    owner = TestClient(server.app)
    owner.post("/api/signup", json={"company": "Сануулга тест", "phone": "7011 2233", "email": "rem@example.mn",
                                    "password": "rem-pass-123"})
    t = tenant.Tenant(owner.get("/api/me").json()["tenant"])
    with db.connect(t.db_path) as con:
        con.execute("INSERT INTO leads (call_uuid, created_at, name, phone, reason, status) VALUES "
                    "('c1', 1, 'Болд', '99112233', 'lead', 'new'), ('c2', 1, 'Сараа', NULL, 'lead', 'new')")
        bold, saraa = [r[0] for r in con.execute("SELECT id FROM leads ORDER BY id").fetchall()]

    blocked = owner.put("/api/admin/outbound", json={"mode": "sip", "host": "1.2.3.4"}).status_code
    check("залгах тохиргоо зөвхөн admin", blocked == 403, blocked)
    gw = FakeGateway(password="gwpass", dtmf_mode="rfc4733", digit="1", after_packets=40)
    gw.start()
    r = adm.put("/api/admin/outbound", json={"mode": "sip", "host": "127.0.0.1", "port": gw.port, "user": "ai",
                                              "password": "gwpass", "local_ip": "127.0.0.1", "ring_timeout": 3})
    check("тохиргоо хадгална, нууц үг буцааж харуулахгүй", r.status_code == 200 and r.json()["password_set"] is True
          and "password" not in r.json(), r.text)
    check("gateway бэлэн (OPTIONS)", adm.post("/api/admin/outbound/check").json()["ready"] is True)

    future = (reminders.datetime.now(reminders.TZ) + reminders.timedelta(days=3)).strftime("%Y-%m-%dT10:00")
    bad = [owner.put(f"/api/reminders/{saraa}", json={"appointment": future, "call": "now"}).status_code,
           owner.put(f"/api/reminders/{bold}", json={"appointment": "2020-01-01T10:00", "call": "now"}).status_code,
           owner.put("/api/reminders/999", json={"appointment": future, "call": "now"}).status_code]
    check("дугааргүй / өнгөрсөн цаг / байхгүй бүртгэл", bad == [400, 400, 404], bad)
    r = owner.put(f"/api/reminders/{bold}", json={"appointment": future, "call": "day_before"})
    item = r.json()
    check("өмнөх өдрийн 11:00-д товлоно, мессеж нэр/өдөр/цагтай", r.status_code == 200 and item["status"] == "scheduled"
          and "Болд" in item["text"] and "сарын" in item["text"] and "10:00 цагт" in item["text"]
          and item["call_at"] > time.time() + 3600 and item["new_chars"] > 100, item)
    check("хугацаа болоогүй бол залгахгүй", reminders.run_due() == [])
    owner.post(f"/api/reminders/{bold}/call")
    done = reminders.run_due()
    item = owner.get("/api/reminders").json()["items"][str(bold)]
    check("залгаад 1 дарахад баталгаажсан", done == [(t.slug, bold, "confirmed")] and item["status"] == "confirmed"
          and item["history"][-1]["pressed"][:1] == ["1"] and gw.auth_ok, (done, item.get("history")))
    with db.connect(t.db_path) as con:
        status = con.execute("SELECT status FROM leads WHERE id=?", (bold,)).fetchone()[0]
    check("бүртгэл 'Холбогдсон', Telegram мэдэгдэл", status == "contacted" and len(sent) == 1
          and "Болд" in sent[0] and "баталгаажууллаа" in sent[0], (status, sent))
    gw.close()

    gw = FakeGateway(mode="busy")
    gw.start()
    adm.put("/api/admin/outbound", json={"mode": "sip", "host": "127.0.0.1", "port": gw.port, "local_ip": "127.0.0.1",
                                         "ring_timeout": 2})
    owner.put(f"/api/reminders/{bold}", json={"appointment": future, "call": "now"})
    reminders.run_due()
    item = owner.get("/api/reminders").json()["items"][str(bold)]
    check("завгүй -> 30 минутын дараа дахин (1/3)", item["status"] == "scheduled" and item["attempts"] == 1
          and item["call_at"] > time.time() + 25 * 60 and item["last_outcome"] == "busy", item)
    gw.close()

    r = owner.put("/api/reminders/template", json={"template": "Сайн байна уу {name}. {org}. {date} {time} цагт. {bad}"})
    check("загварт буруу хувьсагч -> 400", r.status_code == 400, r.text)
    r = owner.put("/api/reminders/template", json={"template": "{name}, {org}-д {date} {time} цагт уулзъя. Нэг эсвэл хоёрыг дарна уу."})
    check("загвар хадгалж жишээ харуулна", r.status_code == 200 and "Болд" in r.json()["preview"], r.text)
    check("цуцлах", owner.delete(f"/api/reminders/{bold}").status_code == 200
          and str(bold) not in owner.get("/api/reminders").json()["items"])


if __name__ == "__main__":
    test_dtmf()
    test_sip()
    test_reminders()
    print(f"\n{'ТЭНЦЛЭЭ ✓' if not failures else f'ТЭНЦЭЭГҮЙ: {len(failures)} шалгалт'}")
    sys.exit(1 if failures else 0)
