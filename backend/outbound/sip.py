"""SIP-ээр гарах дуудлага: GSM gateway (GoIP, Dinstar ...), SIP trunk эсвэл softphone руу шууд.

  INVITE sip:<дугаар>@<gateway>  ->  100/180/183  ->  200 OK (утсаа авлаа)  ->  ACK  ->  RTP  ->  BYE
  401/407 -> digest нэвтрэлт; 486/603 -> завгүй/татгалзсан; 408/480/487, хугацаа дуусвал -> утсаа аваагүй

Дуу: PCMU/PCMA 8kHz, 20мс. Товчлуур: RFC 4733 (telephone-event), SIP INFO, дуун дахь DTMF — аль нь ч.
NAT: нөгөө талаас RTP өөр хаягаас ирвэл тэр хаяг руу илгээнэ (symmetric RTP).
"""
import hashlib
import random
import re
import socket
import struct
import threading
import time
import uuid
import warnings
from dataclasses import dataclass

import numpy as np

from outbound.call import SR, CallIO

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import audioop

CODECS = {0: ("PCMU", audioop.lin2ulaw, audioop.ulaw2lin), 8: ("PCMA", audioop.lin2alaw, audioop.alaw2lin)}
DTMF_PT = 101
EVENTS = "0123456789*#ABCD"
FRAME = 160                       # 20мс @ 8kHz


@dataclass
class SipConfig:
    host: str                     # gateway IP / домэйн
    port: int = 5060
    user: str = "ai"              # From / digest нэвтрэх нэр
    password: str = ""
    local_ip: str = ""            # хоосон бол автоматаар
    local_port: int = 0           # 0 бол дурын (5060 нь SIM-TRUNK-ийн sip_bridge)
    prefix: str = ""              # дугаарын өмнө (gateway шаардвал, жишээ нь "0")
    ring_timeout: float = 40


class SipError(Exception):
    def __init__(self, outcome: str, detail: str):
        super().__init__(detail)
        self.outcome = outcome        # busy | no_answer | failed


def _local_ip(host: str, port: int) -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((host, port))
        return s.getsockname()[0]


def _header(msg: str, name: str) -> str | None:
    m = re.search(rf"^{name}\s*:\s*(.+)$", msg, re.I | re.M)
    return m.group(1).strip() if m else None


def _digest(challenge: str, method: str, uri: str, user: str, password: str) -> str:
    p = dict(re.findall(r'(\w+)="?([^",]+)"?', challenge))
    ha1 = hashlib.md5(f"{user}:{p.get('realm', '')}:{password}".encode()).hexdigest()
    ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
    parts = [f'username="{user}"', f'realm="{p.get("realm", "")}"', f'nonce="{p.get("nonce", "")}"', f'uri="{uri}"']
    if "auth" in p.get("qop", "").split(","):
        cnonce, nc = uuid.uuid4().hex[:16], "00000001"
        resp = hashlib.md5(f"{ha1}:{p['nonce']}:{nc}:{cnonce}:auth:{ha2}".encode()).hexdigest()
        parts += ["qop=auth", f"nc={nc}", f'cnonce="{cnonce}"']
    else:
        resp = hashlib.md5(f"{ha1}:{p.get('nonce', '')}:{ha2}".encode()).hexdigest()
    parts.append(f'response="{resp}"')
    if p.get("opaque"):
        parts.append(f'opaque="{p["opaque"]}"')
    return "Digest " + ", ".join(parts) + ", algorithm=MD5"


class SipCall(CallIO):
    """Нэг гарах дуудлага. dial() -> (утсаа авбал) CallIO; эс бөгөөс SipError."""

    def __init__(self, cfg: SipConfig, number: str):
        super().__init__()
        self.cfg = cfg
        self.number = cfg.prefix + re.sub(r"\D", "", number)
        self.sip = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sip.bind(("0.0.0.0", cfg.local_port))
        self.rtp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rtp.bind(("0.0.0.0", 0))
        self.ip = cfg.local_ip or _local_ip(cfg.host, cfg.port)
        self.gw = (socket.gethostbyname(cfg.host), cfg.port)
        self.call_id = f"{uuid.uuid4().hex}@{self.ip}"
        self.tag = uuid.uuid4().hex[:10]
        self.uri = f"sip:{self.number}@{cfg.host}:{cfg.port}"
        self.cseq = 0
        self.branch = ""
        self.to_hdr = f"<{self.uri}>"
        self.remote_target = self.uri
        self.remote_rtp: tuple[str, int] | None = None
        self.pt = 0
        self.dtmf_pt = DTMF_PT
        self.state = "init"               # init -> ringing -> up -> ended
        self.outcome: str | None = None
        self.detail = ""
        self.answered = threading.Event()
        self.final = threading.Event()
        self._invite_auth: str | None = None
        self._queue: list[bytes] = []     # илгээх 20мс-ийн хэсгүүд
        self._qlock = threading.Condition()
        self._seen_events: set[int] = set()

    # ---------------- SIP мессеж ----------------
    def _via(self) -> str:
        return f"SIP/2.0/UDP {self.ip}:{self.sip.getsockname()[1]};branch={self.branch};rport"

    def _request(self, method: str, uri: str, cseq: int, extra: list[str] | None = None, body: str = "",
                 new_branch: bool = True) -> str:
        if new_branch:
            self.branch = "z9hG4bK" + uuid.uuid4().hex[:16]
        lines = [f"{method} {uri} SIP/2.0", f"Via: {self._via()}", "Max-Forwards: 70",
                 f"From: <sip:{self.cfg.user}@{self.cfg.host}>;tag={self.tag}", f"To: {self.to_hdr}",
                 f"Call-ID: {self.call_id}", f"CSeq: {cseq} {method}",
                 f"Contact: <sip:{self.cfg.user}@{self.ip}:{self.sip.getsockname()[1]}>", "User-Agent: AI-Reception"]
        lines += extra or []
        if body:
            lines += ["Content-Type: application/sdp"]
        lines += [f"Content-Length: {len(body.encode())}", "", body]
        return "\r\n".join(lines)

    def _send(self, text: str, addr=None):
        self.sip.sendto(text.encode(), addr or self.gw)

    def _sdp(self) -> str:
        port = self.rtp.getsockname()[1]
        return "\r\n".join([
            "v=0", f"o=ai {int(time.time())} 1 IN IP4 {self.ip}", "s=ai", f"c=IN IP4 {self.ip}", "t=0 0",
            f"m=audio {port} RTP/AVP 0 8 {DTMF_PT}", "a=rtpmap:0 PCMU/8000", "a=rtpmap:8 PCMA/8000",
            f"a=rtpmap:{DTMF_PT} telephone-event/8000", f"a=fmtp:{DTMF_PT} 0-16", "a=ptime:20", "a=sendrecv", ""])

    def _invite(self):
        self.cseq += 1
        extra = ["Allow: INVITE, ACK, BYE, CANCEL, OPTIONS, INFO"]
        if self._invite_auth:
            extra.append(self._invite_auth)
        self._invite_cseq = self.cseq
        self._send(self._request("INVITE", self.uri, self.cseq, extra, self._sdp()))
        self._invite_branch = self.branch

    def _ack(self, cseq: int, uri: str, new_branch: bool):
        self._send(self._request("ACK", uri, cseq, new_branch=new_branch))

    def _reply(self, msg: str, addr, code: int = 200, reason: str = "OK"):
        hdrs = [f"{n}: {_header(msg, n)}" for n in ("Via", "From", "To", "Call-ID", "CSeq") if _header(msg, n)]
        self._send("\r\n".join([f"SIP/2.0 {code} {reason}", *hdrs, "Content-Length: 0", "", ""]), addr)

    def _parse_sdp(self, msg: str):
        body = msg.split("\r\n\r\n", 1)[-1]
        ip = re.search(r"^c=IN IP4 (\S+)", body, re.M)
        m = re.search(r"^m=audio (\d+) RTP/AVP ([\d ]+)", body, re.M)
        if ip and m:
            self.remote_rtp = (ip.group(1), int(m.group(1)))
            offered = [int(x) for x in m.group(2).split()]
            self.pt = next((p for p in offered if p in CODECS), 0)
        te = re.search(r"^a=rtpmap:(\d+) telephone-event", body, re.M)
        if te:
            self.dtmf_pt = int(te.group(1))

    def _on_response(self, msg: str):
        code = int(msg.split()[1])
        method = (_header(msg, "CSeq") or "").split()[-1]
        cseq = int((_header(msg, "CSeq") or "0").split()[0])
        if method != "INVITE":
            return
        if 100 <= code < 200:
            if code >= 180:
                self.state = "ringing"
            return
        to = _header(msg, "To")
        if code >= 300:                              # алдаатай эцсийн хариу -> ACK (ижил branch)
            if to:
                self.to_hdr = to
            self._ack(cseq, self.uri, new_branch=False)
            self.to_hdr = f"<{self.uri}>"
        if code in (401, 407) and not self._invite_auth and self.cfg.password:
            challenge = _header(msg, "WWW-Authenticate" if code == 401 else "Proxy-Authenticate") or ""
            name = "Authorization" if code == 401 else "Proxy-Authorization"
            self._invite_auth = f"{name}: {_digest(challenge, 'INVITE', self.uri, self.cfg.user, self.cfg.password)}"
            self._invite()
            return
        if 200 <= code < 300:
            if to:
                self.to_hdr = to
            contact = _header(msg, "Contact")
            if contact:
                m = re.search(r"<([^>]+)>", contact)
                self.remote_target = m.group(1) if m else contact
            self._parse_sdp(msg)
            self._ack(cseq, self.remote_target, new_branch=True)
            if self.state != "up":
                self.state = "up"
                self.answered.set()
                threading.Thread(target=self._sender, daemon=True).start()
            self.final.set()
            return
        self.outcome = ("busy" if code in (486, 600, 603) else "no_answer" if code in (408, 480, 487)
                        else "failed")
        self.detail = msg.split("\r\n", 1)[0]
        self.state = "ended"
        self.final.set()
        self.ended.set()

    def _on_request(self, msg: str, addr):
        method = msg.split()[0]
        if method == "BYE":
            self._reply(msg, addr)
            self.state = "ended"
            self.ended.set()
        elif method == "INFO":                       # SIP INFO DTMF (Signal=1)
            self._reply(msg, addr)
            m = re.search(r"Signal\s*=\s*([0-9*#A-D])", msg)
            if m:
                self._event(m.group(1))
        elif method in ("OPTIONS", "UPDATE"):
            self._reply(msg, addr)
        elif method != "ACK":
            self._reply(msg, addr, 405, "Method Not Allowed")

    def _sip_loop(self):
        self.sip.settimeout(0.2)
        while self.state != "closed":
            try:
                data, addr = self.sip.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                return
            msg = data.decode(errors="replace")
            if _header(msg, "Call-ID") != self.call_id:
                continue
            if msg.startswith("SIP/2.0"):
                self._on_response(msg)
            else:
                self._on_request(msg, addr)

    # ---------------- RTP ----------------
    def _rtp_loop(self):
        self.rtp.settimeout(0.2)
        while self.state != "closed":
            try:
                data, addr = self.rtp.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                return
            if len(data) < 12:
                continue
            if self.remote_rtp and addr != self.remote_rtp and self.state == "up":
                self.remote_rtp = addr                  # symmetric RTP (NAT)
            b0, b1 = data[0], data[1]
            pt = b1 & 0x7F
            off = 12 + 4 * (b0 & 0x0F)
            if b0 & 0x10:                              # extension header
                off += 4 + 4 * struct.unpack("!H", data[off + 2:off + 4])[0]
            payload = data[off:]
            if pt == self.dtmf_pt and len(payload) >= 4:
                ts = struct.unpack("!I", data[4:8])[0]
                if ts not in self._seen_events and payload[0] < len(EVENTS):
                    self._seen_events.add(ts)
                    self._event(EVENTS[payload[0]])
            elif pt in CODECS and payload:
                pcm = CODECS[pt][2](payload, 2)
                self._feed(np.frombuffer(pcm, "<i2").astype(np.float32) / 32768)

    def _sender(self):
        """20мс тутам: дараалалд дуу байвал түүнийг, үгүй бол чимээгүй (gateway RTP хүлээгээд таслахгүйн тулд)."""
        seq, ts, ssrc = random.randint(0, 65535), random.randint(0, 2 ** 31), random.randint(0, 2 ** 31)
        silence = CODECS[self.pt][1](b"\x00\x00" * FRAME, 2)
        nxt = time.monotonic()
        marker = True
        while self.state == "up":
            with self._qlock:
                frame = self._queue.pop(0) if self._queue else None
                self._qlock.notify_all()
            payload = CODECS[self.pt][1](frame, 2) if frame else silence
            header = struct.pack("!BBHII", 0x80, (0x80 if marker else 0) | self.pt, seq & 0xFFFF, ts & 0xFFFFFFFF, ssrc)
            if self.remote_rtp:
                try:
                    self.rtp.sendto(header + payload, self.remote_rtp)
                except OSError:
                    pass
            marker = False
            seq, ts = seq + 1, ts + FRAME
            nxt += 0.02
            time.sleep(max(0.0, nxt - time.monotonic()))

    def _send_audio(self, audio8k: np.ndarray):
        pcm = (np.clip(audio8k, -1, 1) * 32767).astype("<i2").tobytes()
        frames = [pcm[i:i + FRAME * 2].ljust(FRAME * 2, b"\x00") for i in range(0, len(pcm), FRAME * 2)]
        with self._qlock:
            self._queue.extend(frames)
            while self._queue and self.state == "up":
                self._qlock.wait(0.1)

    # ---------------- дуудлага ----------------
    def dial(self) -> "SipCall":
        threading.Thread(target=self._sip_loop, daemon=True).start()
        threading.Thread(target=self._rtp_loop, daemon=True).start()
        self._invite()
        self.final.wait(self.cfg.ring_timeout)
        if not self.answered.is_set():
            if not self.final.is_set():               # утсаа аваагүй -> CANCEL (INVITE-ийн branch, CSeq)
                self.branch = self._invite_branch
                self._send(self._request("CANCEL", self.uri, self._invite_cseq, new_branch=False))
                self.outcome, self.detail = "no_answer", "утсаа аваагүй (хугацаа дууслаа)"
            self.close()
            raise SipError(self.outcome or "failed", self.detail or "дуудлага холбогдсонгүй")
        return self

    def _hangup(self):
        if self.state == "up":
            self.cseq += 1
            self._send(self._request("BYE", self.remote_target, self.cseq), self.gw)
            time.sleep(0.2)
        self.close()

    def close(self):
        self.state = "closed"
        self.ended.set()
        for s in (self.sip, self.rtp):
            try:
                s.close()
            except OSError:
                pass


def ping(cfg: SipConfig, timeout: float = 2) -> tuple[bool, str]:
    """Gateway SIP OPTIONS-д хариулж байгаа эсэх (бэлэн эсэхийг шалгах)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout)
            ip = cfg.local_ip or _local_ip(cfg.host, cfg.port)
            branch, call_id = "z9hG4bK" + uuid.uuid4().hex[:12], uuid.uuid4().hex
            s.bind(("0.0.0.0", 0))
            msg = "\r\n".join([f"OPTIONS sip:{cfg.host}:{cfg.port} SIP/2.0",
                               f"Via: SIP/2.0/UDP {ip}:{s.getsockname()[1]};branch={branch};rport",
                               "Max-Forwards: 70", f"From: <sip:{cfg.user}@{cfg.host}>;tag={uuid.uuid4().hex[:8]}",
                               f"To: <sip:{cfg.host}:{cfg.port}>", f"Call-ID: {call_id}", "CSeq: 1 OPTIONS",
                               "Content-Length: 0", "", ""])
            s.sendto(msg.encode(), (socket.gethostbyname(cfg.host), cfg.port))
            data, _ = s.recvfrom(65535)
            first = data.decode(errors="replace").split("\r\n", 1)[0]
            return first.startswith("SIP/2.0"), first
    except OSError as exc:
        return False, f"хариу ирсэнгүй ({exc})"

