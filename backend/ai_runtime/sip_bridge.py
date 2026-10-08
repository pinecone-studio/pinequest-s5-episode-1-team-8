"""
Жижиг SIP сервер: Asterisk-гүйгээр Zoiper-оос шууд залгаж турших.

  Zoiper ─SIP/RTP (PCMU/PCMA 8kHz)─► sip_bridge.py ─AudioSocket TCP─► phone_server.py

Asterisk-тай ижил AudioSocket протоколоор phone_server руу холбогддог тул
дараа нь жинхэнэ Asterisk / SIP trunk руу шилжихэд phone_server өөрчлөгдөхгүй.

  .venv/bin/python phone_server.py      # 1-р терминал
  .venv/bin/python sip_bridge.py        # 2-р терминал

Zoiper: username=phone1, password=дурын, domain=<энэ компьютерийн IP>, UDP.
Байгууллага бүр дотуур дугаартай (tenants/<slug>/config.json "extension"): 1000 -> Pinecone гэх мэт.
Бүртгэлгүй дугаар руу залгахад 404. Байгууллагыг phone_server руу TENANT (0x02) мессежээр дамжуулна.
Анхаар: зөвхөн локал сүлжээнд демо хийхэд зориулсан. Нэвтрэлт шалгадаггүй.
"""
import asyncio
import os
import random
import re
import socket
import struct
import time
import uuid
import warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import audioop  # Python 3.12 хүртэл стандарт санд байдаг

import db
import tenant as tenants

SIP_PORT = int(os.getenv("SIP_PORT", "5060"))
AI_HOST = os.getenv("AI_HOST", "127.0.0.1")
AI_PORT = int(os.getenv("AI_PORT", "9092"))
RTP_PORTS = range(10000, 10100, 2)

HANGUP, UUID_KIND, TENANT_KIND, DTMF, AUDIO = 0x00, 0x01, 0x02, 0x03, 0x10   # AudioSocket (+ TENANT)
DTMF_KEYS = "0123456789*#"   # RFC 4733 event 0-11
CODECS = {0: ("PCMU", audioop.ulaw2lin, audioop.lin2ulaw),
          8: ("PCMA", audioop.alaw2lin, audioop.lin2alaw)}


def local_ip(target: str = "8.8.8.8") -> str:
    """target хүрэх замаар гарах интерфейсийн IP (LAN, hotspot, Tailscale аль нь ч)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((target, 80))
        return s.getsockname()[0]
    finally:
        s.close()


def my_ip(target: str = "8.8.8.8") -> str:
    """WiFi/hotspot солигдож болох тул дуудлага бүрт шинээр тодорхойлно."""
    return os.getenv("HOST_IP") or local_ip(target)


# ---------------- SIP мессеж ----------------

def parse(data: bytes):
    text = data.decode("utf-8", errors="replace")
    head, _, body = text.partition("\r\n\r\n")
    lines = head.split("\r\n")
    headers = []
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers.append((k.strip(), v.strip()))
    return lines[0], headers, body


def hget(headers, *names):
    names = {n.lower() for n in names}
    return next((v for k, v in headers if k.lower() in names), "")


def hall(headers, *names):
    names = {n.lower() for n in names}
    return [v for k, v in headers if k.lower() in names]


def response(code, reason, req_headers, extra=(), body="", to_tag=None):
    lines = [f"SIP/2.0 {code} {reason}"]
    for v in hall(req_headers, "Via", "v"):
        lines.append(f"Via: {v}")
    to = hget(req_headers, "To", "t")
    if to_tag and ";tag=" not in to:
        to += f";tag={to_tag}"
    lines += [f"From: {hget(req_headers, 'From', 'f')}", f"To: {to}",
              f"Call-ID: {hget(req_headers, 'Call-ID', 'i')}",
              f"CSeq: {hget(req_headers, 'CSeq')}",
              "Server: pinecone-sip-bridge"]
    lines += list(extra)
    if body:
        lines.append("Content-Type: application/sdp")
    lines.append(f"Content-Length: {len(body.encode())}")
    return ("\r\n".join(lines) + "\r\n\r\n" + body).encode()


def parse_sdp(body: str):
    ip = re.search(r"^c=IN IP4 (\S+)", body, re.M)
    m = re.search(r"^m=audio (\d+) \S+ ([\d ]+)", body, re.M)
    if not (ip and m):
        return None
    pts = [int(p) for p in m.group(2).split()]
    pt = next((p for p in pts if p in CODECS), None)
    te = re.search(r"^a=rtpmap:(\d+) telephone-event", body, re.M)   # товчлуурын (DTMF) payload
    return ip.group(1), int(m.group(1)), pt, int(te.group(1)) if te else 101


def make_sdp(rtp_port: int, pt: int, ip: str, dtmf_pt: int = 101) -> str:
    name = CODECS[pt][0]
    return ("v=0\r\n"
            f"o=- {random.randint(1, 10**9)} 1 IN IP4 {ip}\r\n"
            "s=pinecone\r\n"
            f"c=IN IP4 {ip}\r\n"
            "t=0 0\r\n"
            f"m=audio {rtp_port} RTP/AVP {pt} {dtmf_pt}\r\n"
            f"a=rtpmap:{pt} {name}/8000\r\n"
            f"a=rtpmap:{dtmf_pt} telephone-event/8000\r\n"
            f"a=fmtp:{dtmf_pt} 0-16\r\n"
            "a=ptime:20\r\n"
            "a=sendrecv\r\n")


# ---------------- Нэг дуудлага: RTP <-> AudioSocket ----------------

class RTPProtocol(asyncio.DatagramProtocol):
    def __init__(self, call):
        self.call = call

    def datagram_received(self, data, addr):
        self.call.on_rtp(data, addr)


class Call:
    def __init__(self, call_id, remote, pt, caller=None, dtmf_pt=101, tenant=None):
        self.call_id = call_id
        self.tenant = tenant
        self.dtmf_pt = dtmf_pt
        self.last_dtmf_ts = None      # нэг товчлуурын төгсгөлийн пакет 3 удаа давтагддаг
        self.caller = caller
        self.remote = remote          # (ip, port) SDP-ээс; эхний RTP ирэхэд шинэчилнэ
        self.pt = pt
        _, self.decode, self.encode = CODECS[pt]
        self.seq = random.randint(0, 65535)
        self.ts = random.randint(0, 2**31)
        self.ssrc = random.randint(0, 2**31)
        self.transport = None
        self.writer = None
        self.port = None
        self.task = None
        self.starting = False
        self.retry_at = 0.0              # AI сервер бэлэн биш бол дахин оролдох хугацаа
        self.failed = False

    async def open_rtp(self):
        loop = asyncio.get_running_loop()
        for port in random.sample(list(RTP_PORTS), len(RTP_PORTS)):
            try:
                self.transport, _ = await loop.create_datagram_endpoint(
                    lambda: RTPProtocol(self), local_addr=("0.0.0.0", port))
                self.port = port
                return port
            except OSError:
                continue
        raise RuntimeError("Сул RTP порт олдсонгүй")

    async def start_ai(self):
        try:
            reader, writer = await asyncio.open_connection(AI_HOST, AI_PORT)
        except OSError as e:
            if not self.failed:
                print(f"[SIP] AI сервер рүү холбогдож чадсангүй ({AI_HOST}:{AI_PORT}): {e}. "
                      "2с тутам дахин оролдоно...")
            self.failed = True
            self.retry_at = time.monotonic() + 2.0
            self.starting = False
            return
        if self.failed:
            print("[SIP] AI сервер бэлэн боллоо -> холбогдлоо")
        self.writer = writer
        call_uuid = uuid.uuid4()
        try:
            db.start_call(call_uuid.hex, self.caller, path=self.tenant.db_path)
        except Exception as e:
            print(f"[SIP] лог алдаа: {e}")
        slug = self.tenant.slug.encode()
        self.writer.write(bytes([TENANT_KIND]) + struct.pack(">H", len(slug)) + slug)
        self.writer.write(bytes([UUID_KIND]) + struct.pack(">H", 16) + call_uuid.bytes)
        self.task = asyncio.create_task(self.from_ai(reader))

    def on_rtp(self, data, addr):
        if len(data) < 12:
            return
        self.remote = addr                      # symmetric RTP (NAT, Tailscale userspace-д тэсвэртэй)
        if self.writer is None:
            # Утаснаас анхны RTP ирсний дараа AI-г эхлүүлнэ -> мэндчилгээ тасрахгүй,
            # мөн буцах хаяг (remote) баталгаатай болсон байна.
            if not self.starting and time.monotonic() >= self.retry_at:
                self.starting = True
                if not self.failed:
                    print(f"[SIP] Анхны RTP {addr[0]}:{addr[1]} -> AI эхэллээ")
                asyncio.ensure_future(self.start_ai())
            return
        cc = data[0] & 0x0F
        has_ext = data[0] & 0x10
        pt = data[1] & 0x7F
        if pt == self.dtmf_pt:                   # утасны товчлуур (RFC 4733) -> AudioSocket DTMF
            self.on_dtmf(data)
            return
        if pt != self.pt:
            return
        off = 12 + cc * 4
        if has_ext and len(data) >= off + 4:
            off += 4 + struct.unpack(">H", data[off + 2:off + 4])[0] * 4
        pcm = self.decode(data[off:], 2)
        self.writer.write(bytes([AUDIO]) + struct.pack(">H", len(pcm)) + pcm)

    def on_dtmf(self, data: bytes):
        if len(data) < 16:
            return
        event, flags = data[12], data[13]
        ts = struct.unpack(">I", data[4:8])[0]
        if not flags & 0x80 or ts == self.last_dtmf_ts or event >= len(DTMF_KEYS):
            return                                  # зөвхөн товч суллагдах (end) үед нэг удаа
        self.last_dtmf_ts = ts
        key = DTMF_KEYS[event]
        print(f"[SIP] Товчлуур: {key}")
        self.writer.write(bytes([DTMF]) + struct.pack(">H", 1) + key.encode())

    async def from_ai(self, reader):
        """phone_server аль хэдийн 20ms тутамд жигд илгээдэг -> шууд RTP болгоно."""
        try:
            while True:
                header = await reader.readexactly(3)
                kind, length = header[0], struct.unpack(">H", header[1:])[0]
                payload = await reader.readexactly(length) if length else b""
                if kind != AUDIO or not self.transport:
                    continue
                for i in range(0, len(payload), 320):
                    frame = payload[i:i + 320]
                    rtp = struct.pack(">BBHII", 0x80, self.pt, self.seq, self.ts, self.ssrc)
                    self.transport.sendto(rtp + self.encode(frame, 2), self.remote)
                    self.seq = (self.seq + 1) & 0xFFFF
                    self.ts = (self.ts + len(frame) // 2) & 0xFFFFFFFF
        except (asyncio.IncompleteReadError, ConnectionError):
            pass

    def close(self):
        if self.writer:
            try:
                self.writer.write(bytes([HANGUP]) + b"\x00\x00")
                self.writer.close()
            except Exception:
                pass
        if self.task:
            self.task.cancel()
        if self.transport:
            self.transport.close()


# ---------------- SIP сервер ----------------

class SIPServer(asyncio.DatagramProtocol):
    def __init__(self):
        self.calls: dict[str, Call] = {}
        self.answers: dict[str, bytes] = {}    # INVITE давтагдвал ижил 200 OK буцаана

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        if data.strip() == b"":                # keep-alive
            return
        first, headers, body = parse(data)
        if first.startswith("SIP/2.0"):
            return                             # бидний илгээсэн хүсэлтийн хариу
        method = first.split(" ", 1)[0]
        call_id = hget(headers, "Call-ID", "i")
        send = lambda msg: self.transport.sendto(msg, addr)  # noqa: E731

        if method == "REGISTER":
            contact = hget(headers, "Contact", "m")
            send(response(200, "OK", headers, [f"Contact: {contact};expires=3600",
                                               "Expires: 3600"], to_tag="reg"))
            print(f"[SIP] Бүртгэгдлээ: {hget(headers, 'From', 'f')} {addr[0]}")
        elif method == "OPTIONS":
            send(response(200, "OK", headers, ["Allow: INVITE, ACK, BYE, CANCEL, OPTIONS"]))
        elif method == "INVITE":
            asyncio.create_task(self.invite(headers, body, call_id, send, addr[0], first))
        elif method == "ACK":
            pass
        elif method == "BYE":
            send(response(200, "OK", headers))
            call = self.calls.pop(call_id, None)
            self.answers.pop(call_id, None)
            if call:
                call.close()
                print(f"[SIP] Дуудлага дууслаа {call_id[:8]}")
        elif method == "CANCEL":
            send(response(200, "OK", headers))
        else:
            send(response(405, "Method Not Allowed", headers))

    async def invite(self, headers, body, call_id, send, peer_ip, request_line=""):
        if call_id in self.answers:            # давтагдсан INVITE / re-INVITE
            send(self.answers[call_id])
            return
        # Залгасан дугаар: "INVITE sip:1000@host SIP/2.0" -> 1000 -> байгууллага
        m = re.search(r"sip:([^@>;\s]+)@", request_line) or re.search(r"sip:([^@>;]+)@", hget(headers, "To", "t"))
        ext = m.group(1) if m else ""
        t = tenants.by_extension(ext)
        if t is None:
            send(response(404, "Not Found", headers, to_tag="x"))
            print(f"[SIP] {ext!r} дугаартай байгууллага алга (tenants/*/config.json extension)")
            return
        if t.config().get("plan") == "suspended":      # эрх нь түдгэлзсэн (төлбөр гэх мэт)
            send(response(403, "Forbidden", headers, to_tag="x"))
            print(f"[SIP] {t.slug}: эрх түдгэлзсэн -> дуудлага хүлээж авсангүй")
            return
        send(response(100, "Trying", headers))
        offer = parse_sdp(body)
        if not offer or offer[2] is None:
            send(response(488, "Not Acceptable Here", headers, to_tag="x"))
            print("[SIP] Codec таарсангүй (PCMU/PCMA хэрэгтэй)")
            return
        ip, port, pt, dtmf_pt = offer
        me = my_ip(peer_ip)
        m = re.search(r"sip:([^@>;]+)", hget(headers, "From", "f"))
        call = Call(call_id, (ip, port), pt, caller=m.group(1) if m else None, dtmf_pt=dtmf_pt, tenant=t)
        try:
            rtp_port = await call.open_rtp()
        except (OSError, RuntimeError) as e:
            call.close()
            send(response(503, "Service Unavailable", headers, to_tag="x"))
            print(f"[SIP] RTP порт нээж чадсангүй: {e}")
            return
        self.calls[call_id] = call
        ok = response(200, "OK", headers,
                      [f"Contact: <sip:ai@{me}:{SIP_PORT}>",
                       "Allow: INVITE, ACK, BYE, CANCEL, OPTIONS"],
                      body=make_sdp(rtp_port, pt, me, dtmf_pt), to_tag=uuid.uuid4().hex[:8])
        self.answers[call_id] = ok
        send(ok)
        print(f"[SIP] Дуудлага холбогдлоо [{t.slug} {ext}] {hget(headers, 'From', 'f')} "
              f"codec={CODECS[pt][0]} rtp {me}:{rtp_port} <-> {ip}:{port}")


async def main():
    loop = asyncio.get_running_loop()
    await loop.create_datagram_endpoint(SIPServer, local_addr=("0.0.0.0", SIP_PORT))
    print(f"SIP сервер: {my_ip()}:{SIP_PORT} (UDP)  ->  AI {AI_HOST}:{AI_PORT}")
    print(f"Zoiper: username=phone1  password=дурын  domain={my_ip()}  transport=UDP")
    for t in tenants.all_tenants():
        print(f"  {t.config().get('extension', '—'):>6} -> {t.slug} ({t.config().get('name', '')})")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
