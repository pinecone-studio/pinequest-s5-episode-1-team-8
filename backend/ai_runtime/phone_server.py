"""
AI Receptionist - AudioSocket утасны сервер (олон байгууллага)

  Утас -> Asterisk -> AudioSocket(TCP) -> энэ сервер
     8kHz аудио -> Silero VAD -> Whisper STT -> stream_voice.respond()
     -> Oron TTS (24kHz) -> 8kHz -> 20ms frame -> Asterisk -> Утас

Залгагч AI-г тасалж яривал (barge-in) хариуг зогсоож шинэ асуултыг сонсоно.

Олон байгууллага: sip_bridge.py UUID-ээс өмнө TENANT (0x02, slug) мессеж илгээнэ (залгасан дотуур
дугаараас). Asterisk илгээдэггүй -> DEFAULT_TENANT. STT, embedding, VAD-ийг бүгд хуваалцана;
байгууллага бүрийн индекс (хэдхэн MB) анх залгахад ачаалагдана.

  .venv/bin/python phone_server.py
"""
import asyncio
import copy
import faulthandler
import json
import os
import re
import signal
import struct
import time
from concurrent.futures import ThreadPoolExecutor
from math import gcd

import numpy as np
from scipy.signal import resample_poly

from stream_voice import (HOLD_AFTER, LLM_GENERATE, OLLAMA_MODEL, OLLAMA_URL, SELECT_LLM,
                          SELECT_MODEL, FAQRouter, OronTTS, respond)
import account as acct
import db
import english
import notify
import people
import tenant as tenants
from lead import START_FAQ, LeadFlow
from stt import BilingualSTT, WhisperSTT

AI_PORT = int(os.getenv("AI_PORT", "9092"))

HANGUP, UUID, TENANT, DTMF, AUDIO, ERROR = 0x00, 0x01, 0x02, 0x03, 0x10, 0xFF
SR = 8000
FRAME_BYTES = 320            # 20ms, 16-bit mono 8kHz
FRAME_SEC = 0.02

VAD_CHUNK = 256              # Silero 8kHz үед 256 sample (32ms) шаарддаг
VAD_THRESHOLD = float(os.getenv("VAD_THRESHOLD", "0.5"))
END_SILENCE = float(os.getenv("END_SILENCE", "0.5"))     # ийм чимээгүй -> өгүүлбэр дууссан
MIN_SPEECH = float(os.getenv("MIN_SPEECH", "0.25"))      # үүнээс богино -> чимээ гэж үзнэ
# BARGE_IN=0 (default): half-duplex. AI ярьж байхад утаснаас ирэх дууг үл тооно.
# Утасны чанга яригч/echo-оос AI өөрийнхөө дууг "залгагч ярьж байна" гэж ойлгож
# өөрийгөө тасалдаг гогцооноос хамгаална. >0 бол ийм урт яриагаар AI-г тасална.
BARGE_IN = float(os.getenv("BARGE_IN", "0"))
ECHO_TAIL = float(os.getenv("ECHO_TAIL", "0.8"))        # AI-ийн дуу дууссаны дараах echo-гийн хугацаа
MIN_TEXT_CHARS = 3                                       # "а", "мн" гэх мэт STT үр дүнг чимээ гэж үзнэ
ACK_AFTER = float(os.getenv("ACK_AFTER", "1.0"))        # STT ийм удаан бол hold тоглуулж эхэлнэ
PRE_ROLL = 0.5   # яриа эхлэхээс өмнөх аудио. AI дуусмагц шууд ярьвал эхний үе ("хич-ээл") таслагдахгүй
# 8GB машинд дуудлагагүй үед macOS загваруудыг swap руу гаргаж, дараагийн дуудлагын эхний хариулт 10с+ болсон
# (10-06 демо шалгалт: залгагч хариу сонсохгүй таслав). Үе үе жижиг STT + embedding -> санах ойд барина. 0 = унтраах
KEEPALIVE = float(os.getenv("KEEPALIVE", "90"))
REVIEW_PORT = int(os.getenv("REVIEW_PORT", "9093"))   # вэбийн "Хариулж чадаагүй" хуудсанд (зөвхөн 127.0.0.1)
WARM_TEXTS = ["сайн байна уу", "сургалтын төлбөр хэд вэ", "хөтөлбөр хэдэн сар үргэлжилдэг вэ тэгээд төлбөрөө хувааж төлж болох уу"]


def to_pcm8k(wav: np.ndarray, sr: int) -> bytes:
    """float32 (ямар ч sr) -> 8kHz 16-bit signed little-endian PCM."""
    if sr != SR:
        g = gcd(SR, sr)
        wav = resample_poly(wav, SR // g, sr // g)
    return (np.clip(wav, -1.0, 1.0) * 32767).astype("<i2").tobytes()


class Models:
    """Бүх дуудлагад хуваалцах моделиуд (нэг удаа ачаална)."""

    def __init__(self):
        from silero_vad import load_silero_vad

        t = time.perf_counter()
        # Хариултууд урьдчилсан аудио тул TTS зөвхөн LLM_GENERATE=1 үед хэрэгтэй (~1.5GB RAM хэмнэнэ)
        self.tts = None
        if LLM_GENERATE:
            self.tts = OronTTS()
            self.tts.warmup()
        default = tenants.Tenant(tenants.DEFAULT_TENANT)
        router = FAQRouter(default.faq_index_dir, default.kb_index_dir)
        self.embedder = router.embedder             # бүх байгууллага нэг embedding загвар
        self.account_search = acct.Search(self.embedder.query)   # хувийн RAG (бүртгэлээ шалгах/өөрчлөх)
        self.routers = {default.slug: router}
        self.stt = WhisperSTT()
        self.stt.warmup()
        self.bilingual: BilingualSTT | None = None      # англи горимтой байгууллага байвал л (~0.5GB)
        self.en_routers: dict[str, english.EnglishRouter] = {}
        if any(english.enabled(t) for t in tenants.all_tenants()):
            self.bilingual_stt()
        self.vad = load_silero_vad()
        self.warm_llm()
        self.tts_pool = ThreadPoolExecutor(max_workers=1)
        self.stt_pool = ThreadPoolExecutor(max_workers=1)
        print(f"Моделиуд бэлэн: {time.perf_counter() - t:.1f}s "
              f"(TTS {'асаалттай' if self.tts else 'унтраалттай'}; {default.slug}: аудиотой өгүүлбэр "
              f"{len(router.facts)}, сургасан сонгогч {selector_state(router)})")

    def router_for(self, t: "tenants.Tenant") -> FAQRouter:
        """Байгууллагын индекс: анх залгахад ачаална, дараа нь өөрчлөгдсөн бол л дахин."""
        router = self.routers.get(t.slug)
        if router is None:
            router = self.routers[t.slug] = FAQRouter(t.faq_index_dir, t.kb_index_dir, self.embedder)
            print(f"[{t.slug}] ачааллаа: өгүүлбэр {len(router.facts)}, сонгогч {selector_state(router)}")
        else:
            try:
                if router.reload_if_changed():
                    print(f"[{t.slug}] мэдээлэл шинэчлэгдсэн -> дахин ачааллаа (өгүүлбэр {len(router.facts)}, "
                          f"FAQ {len(router.meta['faq'])}, сонгогч {selector_state(router)})")
            except Exception as e:
                print(f"[{t.slug}] дахин ачаалж чадсангүй, хуучнаар нь үргэлжлүүлнэ: {e}")
        return router

    def bilingual_stt(self) -> BilingualSTT:
        if self.bilingual is None:
            self.bilingual = BilingualSTT(self.stt)
            self.bilingual.warmup()
        return self.bilingual

    def en_router_for(self, t: "tenants.Tenant") -> "english.EnglishRouter | None":
        """Англи горим идэвхтэй бөгөөд бэлдсэн (scripts/build_en.py) бол англи хариулагч, үгүй бол None."""
        path = os.path.join(t.kb_index_dir, "english.json")
        if not english.enabled(t) or not os.path.exists(path):
            self.en_routers.pop(t.slug, None)
            return None
        router = self.en_routers.get(t.slug)
        if router is None or router.stamp != os.path.getmtime(path):
            try:
                router = self.en_routers[t.slug] = english.EnglishRouter(t, self.embedder)
                self.bilingual_stt()
                print(f"[{t.slug}] англи горим: {sum(1 for x in router.meta['items'] if x.get('clip'))}"
                      f"/{len(router.meta['items'])} хариулт орчуулгатай")
            except Exception as e:
                print(f"[{t.slug}] англи индекс ачаалж чадсангүй: {e}")
        return router

    @staticmethod
    def warm_llm():
        """Ollama моделийг санах ойд урьдчилан ачаална -> эхний дуудлага удаашрахгүй."""
        import httpx
        models = ([SELECT_MODEL] if SELECT_LLM else []) + ([OLLAMA_MODEL] if LLM_GENERATE else [])
        for model in models:
            try:
                httpx.post(f"{OLLAMA_URL}/api/generate",
                           json={"model": model, "keep_alive": -1}, timeout=120)
            except httpx.HTTPError as e:
                print(f"Ollama ({model}) ачаалж чадсангүй: {e}")


class Call:
    def __init__(self, reader, writer, models: Models):
        self.reader, self.writer, self.m = reader, writer, models
        self.out = bytearray()          # Утас руу илгээх PCM
        self.out_done = asyncio.Event()  # out хоосорсон
        self.out_done.set()
        self.history: list = []
        self.turn: asyncio.Task | None = None
        self.closed = False
        self.last_out = 0.0              # сүүлийн аудио frame илгээсэн хугацаа
        self.uuid = None                 # AudioSocket UUID -> дуудлагын лог
        self.tenant = tenants.Tenant(tenants.DEFAULT_TENANT)   # TENANT мессежээр солигдоно
        self.router: FAQRouter | None = None
        self.lead: LeadFlow | None = None   # бүртгэл/ажилтанд шилжүүлэх яриа явагдаж байвал
        self.lead_question = None        # handoff үед хариулж чадаагүй асуулт
        self.account: acct.AccountFlow | None = None   # залгагч өөрийн бүртгэлийг шалгаж/өөрчилж байвал
        self.dtmf = ""                   # товчлуураар бичиж буй дугаар
        self.en: english.EnglishRouter | None = None   # байгууллага англи горимтой бол
        self.lang = "mn"                 # залгагчийн сүүлд ярьсан хэл
        self.en_misses = 0               # англиар дараалан олдоогүй асуулт
        self.last_reply: list = []       # сүүлийн хариултын аудио ("Дахиад хэлээч" -> repeat_last)
        self.last_reply_text = ""
        # VAD дотооддоо төлөвтэй -> дуудлага бүрт өөрийн хуулбар (2 хүн зэрэг залгахад будилахгүй)
        self.vad = copy.deepcopy(models.vad)

    # ---------- Гаралт ----------

    def send(self, kind: int, payload: bytes = b""):
        self.writer.write(bytes([kind]) + struct.pack(">H", len(payload)) + payload)

    async def sender(self):
        """20ms тутамд 320 byte жигд илгээнэ (Asterisk-ийн jitter-ээс сэргийлнэ)."""
        next_t = time.monotonic()
        while not self.closed:
            if self.out:  # сүүлийн дутуу frame-ийг 0-ээр дүүргэнэ
                frame = bytes(self.out[:FRAME_BYTES]).ljust(FRAME_BYTES, b"\x00")
                del self.out[:FRAME_BYTES]
                self.send(AUDIO, frame)
                self.last_out = time.monotonic()
                try:
                    await self.writer.drain()
                except ConnectionError:
                    return
                if not self.out:
                    self.out_done.set()
            next_t += FRAME_SEC
            delay = next_t - time.monotonic()
            if delay < -0.2:                # удаан хоцорвол дахин тааруулна
                next_t = time.monotonic()
                delay = 0
            await asyncio.sleep(max(delay, 0))

    async def play(self, wav, sr):
        """respond()-ийн play_fn: аудиог дараалалд нэмээд дуустал хүлээнэ."""
        pcm = to_pcm8k(np.asarray(wav, dtype=np.float32), sr)
        self.out_done.clear()
        self.out += pcm
        await self.out_done.wait()

    async def play_all(self, clips):
        for wav, sr in clips:
            await self.play(wav, sr)

    def flush(self):
        self.out.clear()
        self.out_done.set()

    @property
    def ai_audible(self) -> bool:
        """AI-ийн дуу тоглож байна эсвэл саяхан дууссан (echo буцаж ирж болзошгүй)."""
        return bool(self.out) or time.monotonic() - self.last_out < ECHO_TAIL

    @property
    def busy(self) -> bool:
        return self.ai_audible or (self.turn is not None and not self.turn.done())

    # ---------- Ээлж ----------

    async def hold_while(self, fut):
        """fut удаан бол (санах ой дүүрч STT удаашрах гэх мэт) hold хэллэг тоглуулж,
        залгагчид урт чимээгүй байдал мэдрүүлэхгүй."""
        router, en = self.router, (self.en if self.lang == "en" else None)
        try:
            await asyncio.wait_for(asyncio.shield(fut), ACK_AFTER)
            return
        except asyncio.TimeoutError:
            pass
        while not fut.done():
            await self.play(*(en.clip(en.hold()) if en else router.clip(router.hold())))
            try:
                await asyncio.wait_for(asyncio.shield(fut), HOLD_AFTER)
            except asyncio.TimeoutError:
                pass

    async def handle_utterance(self, audio: np.ndarray):
        loop = asyncio.get_running_loop()
        if not self.lead and not self.account:
            self.dtmf = ""
        t0 = time.perf_counter()
        stt = loop.run_in_executor(self.m.stt_pool, self.transcribe, audio)
        holder = asyncio.create_task(self.hold_while(stt))
        try:
            text, lang = await stt
        finally:
            holder.cancel()     # тоглож байгаа hold дуусаад хариу араас нь тоглоно
        stt_sec = time.perf_counter() - t0
        print(f"  [STT {time.perf_counter() - t0:.2f}s]{' [' + lang + ']' if self.en else ''} {text!r}")
        self.lang = lang
        # Бүртгэлийн үед "за" (2 үсэг) хүчинтэй хариулт
        if len(re.sub(r"\W", "", text)) < (2 if self.lead or self.account else MIN_TEXT_CHARS):
            print("  [алгасав] хэт богино (чимээ/echo)")
            return
        self.log("user", text, stt_sec=stt_sec)
        t1 = time.perf_counter()
        if self.lead and await self.lead_turn(text):
            return
        if self.account and lang != "en" and await self.account_turn(text=text):
            return
        if lang == "en":
            return await self.en_turn(text, t1)
        meta: dict = {}
        played = []

        async def play_capture(wav, sr):
            played.append((wav, sr))
            await self.play(wav, sr)

        reply = await respond(text, self.history, self.router, self.m.tts,
                              self.m.tts_pool, play_fn=play_capture, meta=meta)
        if meta.get("faq_id") == "repeat_last":          # "Дахиад хэлээч" -> өмнөх хариултаа дахин
            for wav, sr in self.last_reply:
                await self.play(wav, sr)
            reply = f"{reply} {self.last_reply_text}".strip()
        elif meta.get("route") not in ("repeat", "clarify"):
            fillers = {id(self.router.clip(c)[0]) for c in self.router.meta["fillers"] + self.router.meta["holds"]}
            answer = [(w, s) for w, s in played if id(w) not in fillers]
            if answer:
                self.last_reply, self.last_reply_text = answer, reply
        print(f"  AI: {reply}")
        self.log("assistant", reply, route=meta.get("route"), score=meta.get("score"),
                 latency=time.perf_counter() - t1)
        self.history += [{"role": "user", "content": text},
                         {"role": "assistant", "content": reply}]
        self.history = self.history[-8:]
        self.maybe_start_lead(meta, text)
        self.maybe_start_account(meta, text)

    def transcribe(self, audio: np.ndarray) -> tuple[str, str]:
        """-> (бичвэр, хэл). Англи горимгүй байгууллагад хэл танихгүй (хурд, санах ой)."""
        if not self.en:
            return self.m.stt.transcribe(audio, SR), "mn"
        if self.lead and self.lead.state in ("name", "phone", "confirm"):
            # нэр, дугаар, тийм/үгүй богино -> хэл буруу танигдана: бүртгэлийн хэлээр шууд
            return self.m.bilingual.transcribe_as(audio, SR, self.lead.lang), self.lead.lang
        return self.m.bilingual.transcribe(audio, SR, self.lang)

    async def en_turn(self, text: str, t1: float):
        """Англи асуулт: орчуулгатай хариулт, эсвэл ажилтан эргэж залгах санал."""
        r = await asyncio.to_thread(self.en.respond, text, self.en_misses)
        self.en_misses = self.en_misses + 1 if r["route"] == "repeat" else 0
        await self.play(*self.en.clip(r["clip"]))
        print(f"  AI [en:{r['route']} {r['score']:.2f}]: {r['text']}")
        self.log("assistant", r["text"], route=f"en_{r['route']}", score=r["score"],
                 latency=time.perf_counter() - t1)
        self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": r["text"]}]
        self.history = self.history[-8:]
        caller = db.caller_of(self.uuid, path=self.tenant.db_path) if self.uuid else None
        if r["route"] == "handoff":
            self.lead = LeadFlow("handoff", "offer", caller, lang="en")
            self.lead_question = r.get("missing") or self.last_question(text)
        elif r.get("faq_id") in START_FAQ:
            self.lead, self.lead_question = LeadFlow(START_FAQ[r["faq_id"]], "name", caller, lang="en"), None

    # ---------- Бүртгэл / ажилтанд шилжүүлэх ----------

    def maybe_start_lead(self, meta: dict, text: str):
        if "lead" not in self.router.meta:      # хуучин аудио (lead асуултгүй) -> алгасна
            return
        caller = db.caller_of(self.uuid, path=self.tenant.db_path) if self.uuid else None
        if meta.get("route") == "handoff":       # "ажилтан эргэж холбогдох уу?" гэж асуусан
            self.lead, self.lead_question = LeadFlow("handoff", "offer", caller), self.last_question(text)
        elif meta.get("faq_id") in START_FAQ:    # хариулт нь өөрөө нэр асуусан
            self.lead = LeadFlow(START_FAQ[meta["faq_id"]], "name", caller)
            self.lead_question = None

    def last_question(self, fallback: str) -> str:
        """Ажилтанд шилжүүлэх үеийн жинхэнэ асуулт ("дахин хэлнэ үү"-гийн өмнөх)."""
        users = [m["content"] for m in self.history if m["role"] == "user"]
        return " / ".join(users[-2:]) if users else fallback

    async def lead_turn(self, text: str) -> bool:
        """Бүртгэлийн нэг алхам. False = энэ нь хариулт биш шинэ асуулт -> энгийн горим."""
        router, flow = self.router, self.lead
        keys = flow.handle(text)
        if not keys:
            self.lead = None
            return False
        spoken = []
        en = self.en if flow.lang == "en" and self.en else None
        code_keys = []
        if flow.finished and flow.result != "declined":
            code = self.save_lead(flow)
            if code and not en and "account" in router.meta:
                code_keys = ["your_code", f"digits:{code}", "code_remember"]
        if code_keys and keys:
            keys = keys[:-1] + code_keys + keys[-1:]
        for key in keys:
            if key in code_keys and not key.startswith("digits:"):
                clip = router.meta["account"][key]
                await self.play(*router.clip(clip))
                spoken.append(clip["text"])
            elif key.startswith("digits:"):
                digits = key.split(":", 1)[1]
                await self.play(*self.digits_audio(digits, en))
                spoken.append(" ".join(digits[i:i + 2] for i in range(0, len(digits), 2)))
            else:
                clip = en.lead(key) if en else router.meta["lead"][key]
                await self.play(*(en.clip(clip) if en else router.clip(clip)))
                spoken.append(clip["text"])
        reply = " ".join(spoken)
        print(f"  AI [бүртгэл:{flow.state}]: {reply}")
        self.log("assistant", reply, route=f"lead_{flow.result or flow.state}")
        if flow.finished:
            self.lead = None
        self.history += [{"role": "user", "content": text},
                         {"role": "assistant", "content": reply}]
        self.history = self.history[-8:]
        return True

    def save_lead(self, flow: LeadFlow) -> str | None:
        """Бүртгэлийг хадгалж, хувийн RAG-д холбоно (код + баримтууд) -> бүртгэлийн код."""
        try:
            lead_id = db.add_lead(self.uuid, flow.name, flow.phone, " | ".join(flow.phone_raw) or None,
                                  flow.caller, flow.reason, self.lead_question,
                                  course=self.tenant.config().get("lead_label"), path=self.tenant.db_path)
            print(f"  [LEAD] {flow.name} {flow.phone or '(дугааргүй)'} ({flow.reason})")
            msg = notify.lead_message(flow.name, flow.phone, " | ".join(flow.phone_raw),
                                      flow.reason, self.lead_question)
            # дуудлагыг саатуулахгүй
            asyncio.get_running_loop().run_in_executor(None, notify.send, msg, self.tenant.settings_path)
        except Exception as e:
            print(f"  [лог алдаа] {e}")
            return None
        try:
            code = people.ensure_code(self.tenant.dir, lead_id)
            people.docs(self.tenant.dir, lead_id)
            return code
        except Exception as e:
            print(f"  [хувийн RAG алдаа] {e}")
            return None

    # ---------- Бүртгэлээ шалгах / өөрчлөх (хувийн RAG) ----------

    def maybe_start_account(self, meta: dict, text: str):
        faq = meta.get("faq_id")
        if faq not in ("my_account", "staff_mode") or "account" not in self.router.meta or self.lead:
            return
        if faq == "staff_mode":                   # ажилтан бусдын бүртгэлийг өөрчилнө
            self.account = acct.AccountFlow(self.tenant.dir, self.m.account_search, None, self.uuid, staff=True)
            print("  [ажилтны горим]")
        else:
            intent = acct.detect_intent(self.m.account_search, text)
            self.account = acct.AccountFlow(self.tenant.dir, self.m.account_search, intent, self.uuid)
            print(f"  [бүртгэлээ шалгах] хүсэлт: {intent or '-'}")
        if len(self.dtmf) >= self.account.dtmf_len():   # хэллэг дуусахаас өмнө кодоо бичсэн
            asyncio.get_running_loop().call_soon(self.on_account_dtmf, "#")

    async def account_turn(self, text: str | None = None, digits: str | None = None) -> bool:
        """Нэг алхам. False = энэ нь урсгалын хариулт биш (шинэ асуулт) -> энгийн горим."""
        flow = self.account
        keys = await asyncio.to_thread(flow.handle_dtmf if digits is not None else flow.handle,
                                       digits if digits is not None else text)
        if keys is None:
            self.account = None
            return False
        spoken = []
        for key in keys:
            if key.startswith("digits:"):
                number = key.split(":", 1)[1]
                await self.play(*self.digits_audio(number))
                spoken.append(" ".join(number[i:i + 2] for i in range(0, len(number), 2)))
            elif key.startswith("date:"):
                parts = people.slot_parts(people.parse_local(key.split(":", 1)[1]))
                for part in parts:
                    clip = self.router.meta.get("dates", {}).get(part)
                    if clip:
                        await self.play(*self.router.clip(clip))
                spoken.append(" ".join(parts))
            else:
                clip = self.router.meta["account"].get(key)
                if not clip:                        # «Аудио бэлдэх»-ээс өмнөх индекст шинэ хэллэг алга
                    print(f"  [анхаар] '{key}' хэллэгийн аудио алга — «Аудио бэлдэх» дарна уу")
                    continue
                await self.play(*self.router.clip(clip))
                spoken.append(clip["text"])
        reply = " ".join(spoken)
        print(f"  AI [бүртгэлээ шалгах:{flow.state}]: {reply}")
        self.log("assistant", reply, route=f"account_{flow.state}")
        for ev in flow.events:
            self.notify_change(ev["lead"], ev)
        flow.events.clear()
        if flow.finished:
            self.account = None
        self.history += [{"role": "user", "content": text or f"[товчлуур] {digits}"},
                         {"role": "assistant", "content": reply}]
        self.history = self.history[-8:]
        return True

    def notify_change(self, lead: dict, ev: dict):
        """AI-ийн хийсэн өөрчлөлтийг ажилтанд (Telegram). Ажилтан гараар юу ч хийх шаардлагагүй."""
        what = {"phone": "утасны дугаар", "status": "бүртгэл", "attendance": "ирэх эсэх"}.get(ev["field"], "уулзалтын цаг")
        new = ev["new"] or "цуцалсан"
        who = "ажилтан утсаар өөрчиллөө" if ev.get("staff") else "залгагч өөрөө утсаар өөрчиллөө"
        msg = (f"{self.tenant.config().get('name', self.tenant.slug)}: {lead.get('name') or 'Бүртгэл'} — "
               f"{what} {ev['old'] or '—'} → {new} ({who})")
        print(f"  [өөрчлөлт] {msg}")
        asyncio.get_running_loop().run_in_executor(None, notify.send, msg, self.tenant.settings_path)

    def on_dtmf(self, key: str):
        """Утасны товчлуур: бүртгэлийн дугаар асуух үед 8 цифр (эсвэл # хүртэл) цуглуулна.
        Яриагаар хэлсэн дугаарыг STT ихэвчлэн алддаг ("наян" -> "ноён"), товчлуур 100% зөв."""
        if self.account and not self.lead:
            return self.on_account_dtmf(key)
        if not self.lead:                # "кодоо бичнэ үү" тоглож байхад дарсан цифрийг хадгална
            self.dtmf = "" if key in "*#" else (self.dtmf + key)[-12:]
            return
        if not (self.lead and self.lead.state in ("phone", "confirm")):
            return
        if self.turn and not self.turn.done():
            return                       # өмнөх алхам дуусаагүй
        if key == "*":                    # алдсан бол * дараад дахин эхэлнэ
            self.dtmf = ""
            return
        if key != "#":
            self.dtmf += key
        digits = self.dtmf
        local = digits[3:] if digits.startswith("976") else digits
        if key == "#" or len(local) >= 8:  # 8 цифр болмогц автоматаар (эсвэл # дарахад)
            self.dtmf = ""
            print(f"  [товчлуур] {digits}")
            self.turn = asyncio.create_task(self.dtmf_turn(digits))

    def on_account_dtmf(self, key: str):
        """Бүртгэлийн код (4), шинэ дугаар (8), цэс/баталгаажуулалт (1 товчлуур).
        AI ярьж байхад дарсан бол хэллэгийг тасалж шууд хариулна (хүлээлгэхгүй)."""
        if key == "*":
            self.dtmf = ""
            return
        if key != "#":
            self.dtmf += key
        need = self.account.dtmf_len()
        local = self.dtmf[3:] if need == 8 and self.dtmf.startswith("976") else self.dtmf
        if not self.dtmf or (key != "#" and len(local) < need):
            return
        digits, self.dtmf = self.dtmf, ""
        secret = self.account.state in ("code", "staff_code")
        print(f"  [товчлуур] {'*' * len(digits) if secret else digits}")
        self.log("user", "[товчлуур] код" if secret else f"[товчлуур] {digits}")
        prev = self.turn
        self.flush()

        async def run():
            if prev and not prev.done():
                try:
                    await prev
                except asyncio.CancelledError:
                    pass
            if self.account:
                await self.account_turn(digits=digits)
        self.turn = asyncio.create_task(run())

    async def dtmf_turn(self, digits: str):
        self.log("user", f"[товчлуур] {digits}")
        if self.lead.state == "confirm":     # баталгаажуулах үед дахин дугаар бичвэл шинэ дугаар
            self.lead.state = "phone"
        await self.lead_turn(digits)

    def digits_audio(self, digits: str, en: "english.EnglishRouter | None" = None):
        """Дугаарыг цифр бүрийн бэлэн аудиогоор уншина: хос бүрийн дараа урт завсар."""
        src = en or self.router
        clips = en.digits() if en else self.router.meta["digits"]
        parts, sr = [], 24000
        for i, d in enumerate(digits):
            wav, sr = src.clip(clips[int(d)])
            parts += [wav, np.zeros(int(sr * (0.3 if i % 2 else 0.08)), np.float32)]
        return np.concatenate(parts), sr

    def log(self, role, text, **kw):
        """Дуудлагын лог (вебэд харагдана). Алдаа гарсан ч дуудлагад нөлөөлөхгүй."""
        if not self.uuid:
            return
        try:
            db.add_message(self.uuid, role, text, path=self.tenant.db_path, **kw)
        except Exception as e:
            print(f"  [лог алдаа] {e}")

    def start_turn(self, audio: np.ndarray):
        if self.turn and not self.turn.done():
            self.turn.cancel()
        self.turn = asyncio.create_task(self.handle_utterance(audio))

    def barge_in(self):
        print("  [barge-in] залгагч тасаллаа")
        if self.turn and not self.turn.done():
            self.turn.cancel()
        self.flush()

    # ---------- Оролт ----------

    async def run(self):
        import torch

        sender = asyncio.create_task(self.sender())

        self.vad.reset_states()
        pcm_buf = np.zeros(0, dtype=np.float32)
        speech: list[np.ndarray] = []
        pre: list[np.ndarray] = []
        in_speech = False
        speech_sec = silence_sec = 0.0
        barged = False
        muted = False
        chunk_sec = VAD_CHUNK / SR

        try:
            while True:
                header = await self.reader.readexactly(3)
                kind, length = header[0], struct.unpack(">H", header[1:])[0]
                payload = await self.reader.readexactly(length) if length else b""

                if kind == TENANT:              # sip_bridge: залгасан дугаарын байгууллага
                    try:
                        t = tenants.Tenant(payload.decode())
                        if t.exists():
                            self.tenant = t
                    except ValueError:
                        print(f"  [анхаар] буруу TENANT {payload!r} -> {self.tenant.slug}")
                    continue
                if kind == UUID:
                    self.uuid = payload.hex()
                    self.router = await asyncio.to_thread(self.m.router_for, self.tenant)
                    self.en = await asyncio.to_thread(self.m.en_router_for, self.tenant)
                    print(f"\nДуудлага холбогдлоо {self.uuid[:8]} [{self.tenant.slug}]{' +en' if self.en else ''}")
                    greeting = self.router.meta["greeting"]
                    clips = [self.router.clip(greeting)]
                    text = greeting["text"]
                    self.last_reply, self.last_reply_text = list(clips), text
                    if self.en:              # "For English, please go ahead and speak English."
                        suffix = self.en.phrase("greeting_suffix")
                        clips.append(self.en.clip(suffix))
                        text += " " + suffix["text"]
                    self.turn = asyncio.create_task(self.play_all(clips))
                    try:
                        db.start_call(self.uuid, path=self.tenant.db_path)
                        db.add_message(self.uuid, "assistant", text, route="greeting",
                                       path=self.tenant.db_path)
                    except Exception as e:
                        print(f"  [лог алдаа] {e}")
                    continue
                if kind == DTMF:
                    self.on_dtmf(payload.decode(errors="ignore"))
                    continue
                if kind in (HANGUP, ERROR):
                    print("  Утсаа тасаллаа" if kind == HANGUP else f"  Алдаа {payload!r}")
                    break
                if kind != AUDIO or self.router is None:   # UUID-ээс өмнөх аудиог алгасна
                    continue

                samples = np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768
                pcm_buf = np.concatenate([pcm_buf, samples])
                while len(pcm_buf) >= VAD_CHUNK:
                    chunk, pcm_buf = pcm_buf[:VAD_CHUNK], pcm_buf[VAD_CHUNK:]
                    if BARGE_IN <= 0 and self.ai_audible:
                        # Half-duplex: AI ярьж байхад ирсэн дуу нь ихэвчлэн AI-ийн өөрийнх нь echo
                        in_speech, speech, muted = False, [], True
                        pre = (pre + [chunk])[-int(PRE_ROLL / chunk_sec):]  # дуу хаагдсан ч хадгална
                        continue
                    if muted:
                        self.vad.reset_states()
                        muted = False
                    prob = self.vad(torch.from_numpy(chunk), SR).item()

                    if prob >= VAD_THRESHOLD:
                        if not in_speech:
                            in_speech, speech, speech_sec, barged = True, list(pre), 0.0, False
                        speech.append(chunk)
                        speech_sec += chunk_sec
                        silence_sec = 0.0
                        # AI ярьж байхад залгагч хангалттай урт ярьвал -> зогсооно
                        if BARGE_IN > 0 and not barged and speech_sec >= BARGE_IN and self.ai_audible:
                            self.barge_in()
                            barged = True
                    elif in_speech:
                        speech.append(chunk)
                        silence_sec += chunk_sec
                        if silence_sec >= END_SILENCE:
                            in_speech = False
                            if speech_sec >= MIN_SPEECH:
                                if self.busy and not barged:
                                    print("  [алгасав] AI хариу бэлдэж байх үеийн яриа")
                                else:
                                    self.start_turn(np.concatenate(speech))
                            speech = []
                    pre = (pre + [chunk])[-int(PRE_ROLL / chunk_sec):]
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            self.closed = True
            if self.uuid:
                try:
                    db.end_call(self.uuid, path=self.tenant.db_path)
                except Exception as e:
                    print(f"  [лог алдаа] {e}")
            if self.turn and not self.turn.done():
                self.turn.cancel()
            sender.cancel()
            self.writer.close()


def selector_state(router) -> str:
    sel = router.selector
    if not sel:
        return "алга"
    return f"{'идэвхтэй' if sel.enabled else 'идэвхгүй'}, {len(router.sel_answers)} хариулт"


GENERIC_FAQ = ("smalltalk_", "phone_", "repeat_last", "register", "human_request", "contact_phone")


def suggest(router: FAQRouter, text: str, k: int = 3) -> list[dict]:
    """Асуултад хамгийн ойр агуулгатай хариулт (FAQ, мэдээллийн өгүүлбэр) -> зөв хариултыг сонгоход санал.
    Мэндчилгээ, бүртгэл, утасны хэллэг зэрэг ерөнхий FAQ-г санал болгохгүй (бараг бүх асуултад ойр гардаг)."""
    v = router.embedder.query([text])[0]
    cands = []
    if len(router.emb):
        best: dict[int, float] = {}
        for row, s in enumerate(router.emb @ v):
            i = router.meta["row_to_faq"][row]
            if i >= 0 and not router.meta["faq"][i]["id"].startswith(GENERIC_FAQ):
                best[i] = max(best.get(i, -1.0), float(s))
        cands += [{"kind": "faq", "id": router.meta["faq"][i]["id"], "text": router.meta["faq"][i]["answer"], "score": s}
                  for i, s in best.items()]
    if len(router.fact_emb):
        cands += [{"kind": "fact", "text": f["text"], "score": float(s)} for f, s in zip(router.facts, router.fact_emb @ v)]
    return [{**c, "score": round(c["score"], 3)} for c in sorted(cands, key=lambda c: -c["score"])[:k]]


async def review_one(router: FAQRouter, question: str) -> dict:
    """Хариулж чадаагүй асуултыг ОДОО ямар хариулт авахыг дуудлагагүйгээр шалгана (STT засвар, сонгогч хэрэглэнэ)."""
    from stt import clean
    text = clean(question or "")
    words = text.lower().split()
    letters = re.sub(r"[^а-яөүёa-z]", "", text.lower())
    stuck = re.search(r"(?:^|\s)(\w{3,})(?:\s+\1){3,}", (question or "").lower())   # "үлдээд үлдээд үлдээд үлдээд"
    if len(letters) < 3 or (len(words) > 3 and len(set(words)) == 1) or stuck:
        return {"q": question, "text": text, "noise": True}
    meta: dict = {}

    async def silent(wav, sr):
        pass

    reply = await respond(text, [], router, None, None, play_fn=silent, meta=meta)
    sug = await asyncio.to_thread(suggest, router, meta.get("stt_fixed") or text)
    return {"q": question, "text": text, "fixed": meta.get("stt_fixed"), "route": meta.get("route"), "reply": reply,
            "faq_id": meta.get("faq_id"), "suggest": sug}


async def review_http(models: Models, reader, writer):
    """POST /review {"tenant": slug, "questions": [...]} -> [review_one...]. Вэб (127.0.0.1) л дуудна."""
    code, data = "200 OK", b"[]"
    try:
        head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 10)
        length = int(re.search(rb"content-length: *(\d+)", head, re.I).group(1))
        body = json.loads(await reader.readexactly(length))
        t = tenants.Tenant(body["tenant"])
        router = await asyncio.to_thread(models.router_for, t)
        out = [await review_one(router, q) for q in body.get("questions", [])[:60]]
        data = json.dumps(out, ensure_ascii=False).encode()
    except Exception as e:
        code, data = "400 Bad Request", json.dumps({"error": str(e)}, ensure_ascii=False).encode()
    writer.write(f"HTTP/1.1 {code}\r\nContent-Type: application/json\r\nContent-Length: {len(data)}\r\n"
                 f"Connection: close\r\n\r\n".encode() + data)
    try:
        await writer.drain()
    finally:
        writer.close()


async def keepalive(models: Models, active: list):
    """Дуудлагагүй үед KEEPALIVE сек тутам STT (1с чимээгүй) + embedding (3 урттай асуулт, MPS-ийн хэлбэр бүр)
    ажиллуулна. Удаан бол (swap) лог руу анхааруулна."""
    loop = asyncio.get_running_loop()
    silence = np.zeros(SR, np.float32)
    while True:
        await asyncio.sleep(KEEPALIVE)
        if active[0]:
            continue
        t = time.perf_counter()
        try:
            await loop.run_in_executor(models.stt_pool, models.stt.transcribe, silence, SR)
            await asyncio.to_thread(models.embedder.query, WARM_TEXTS)
        except Exception as e:
            print(f"[keepalive] алдаа: {e}")
            continue
        if time.perf_counter() - t > 3:
            print(f"[keepalive] {time.perf_counter() - t:.1f}s удаан (санах ой дутуу, swap) -> загваруудыг ачааллаа")


async def main():
    # kill -USR1 <pid> -> бүх thread-ийн Python стек svc_ai.log руу (гацвал шалтгааныг олоход)
    faulthandler.register(signal.SIGUSR1, all_threads=True)
    print("Моделиуд ачаалж байна...")
    models = await asyncio.to_thread(Models)
    await asyncio.to_thread(models.embedder.query, WARM_TEXTS)     # эхний дуудлагын route удаан байсан (MPS)
    active = [0]                                                    # одоо явж буй дуудлага
    if KEEPALIVE > 0:
        asyncio.create_task(keepalive(models, active))

    async def handle(reader, writer):
        t = time.perf_counter()
        call = Call(reader, writer, models)
        active[0] += 1
        try:
            await call.run()
        finally:
            active[0] -= 1
        if call.uuid:   # UUID-гүй холболт = вэбийн төлөв шалгалт гэх мэт
            print(f"Дуудлага дууслаа ({time.perf_counter() - t:.0f}s)\n")

    await asyncio.start_server(lambda r, w: review_http(models, r, w), "127.0.0.1", REVIEW_PORT)
    server = await asyncio.start_server(handle, "0.0.0.0", AI_PORT)
    print(f"AudioSocket сервер {AI_PORT} порт дээр хүлээж байна...")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
