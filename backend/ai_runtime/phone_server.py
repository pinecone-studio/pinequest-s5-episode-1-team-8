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
import base64
import copy
import faulthandler
import json
import os
import re
import signal
import struct
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
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
from lead import START_FAQ, LeadFlow, wants_event, wants_register
import names
from stt import NAME_DECODES, BilingualSTT, WhisperSTT, create_mn_stt

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
# Орчны дуу (өрөөнд ярьж буй бусад хүн): Silero үүнийг ч яриа гэж үздэг тул өгүүлбэр хэзээ ч дуусахгүй,
# залгагчийн "байхгүй" танигдахгүй байсан (бодит дуудлага 10-14, 33с). Утсанд ойр ярьж буй хүний дуу
# орчноос чанга -> сүүлийн NOISE_WINDOW секундын доод түвшнөөс SPEECH_SNR дахин чанга дууг л яриа гэнэ.
SPEECH_SNR = float(os.getenv("SPEECH_SNR", "2.5"))       # ~8dB
MIN_RMS = float(os.getenv("MIN_RMS", "0.004"))           # ~-48dBFS: чимээгүй өрөөнд ч үүнээс сул бол яриа биш
NOISE_WINDOW = 3.0
MAX_UTTERANCE = float(os.getenv("MAX_UTTERANCE", "8"))   # үүнээс урт бол таслаад таниулна (гацахгүй)
# Утсанд хамгийн ойр (хамгийн чанга) нь залгагч. Өгүүлбэрийн оргилоос REL_SPEECH-ээс сул хэсэг = чимээгүй
# (залгагч дуусмагц ард яриа байсан ч өгүүлбэр дуусна), залгагчийн түвшнөөс FAR_RATIO-оос сул өгүүлбэр = алсын хүн.
VAD_DEBUG = os.getenv("VAD_DEBUG") == "1"              # өгүүлбэр бүрийн VAD шийдвэрийг лог руу
REL_SPEECH = float(os.getenv("REL_SPEECH", "0.25"))    # ~-12dB
FAR_RATIO = float(os.getenv("FAR_RATIO", "0.25"))      # ~-12dB
PRE_ROLL = 0.5   # яриа эхлэхээс өмнөх аудио. AI дуусмагц шууд ярьвал эхний үе ("хич-ээл") таслагдахгүй
# 8GB машинд дуудлагагүй үед macOS загваруудыг swap руу гаргаж, дараагийн дуудлагын эхний хариулт 10с+ болсон
# (10-06 демо шалгалт: залгагч хариу сонсохгүй таслав). Үе үе жижиг STT + embedding -> санах ойд барина. 0 = унтраах
KEEPALIVE = float(os.getenv("KEEPALIVE", "90"))
BYE_WORDS = re.compile(r"баяртай|баярлалаа|байхгүй|үгүй|болоо|алга|дараа ярья")
REPROMPT_AFTER = float(os.getenv("REPROMPT_AFTER", "6"))   # бүртгэлийн асуултын дараах чимээгүй (сек)
# Нэг товчлуураар хариулдаг алхмууд: баталгаажуулах 1/2, эвент сонгох 1-3, эвентэд бүртгүүлэх эсэх 1/2
ONE_KEY = {"confirm": "12", "event_pick": "123", "event_offer": "12", "book_offer": "12"}
DTMF_GAP = 5.0      # сек: товчлуур хооронд үүнээс удаан завсарлавал дугаарыг шинээр эхлүүлнэ
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
        self.stt = create_mn_stt()
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

    def warm(self):
        """STT + embedding-ийг нэг удаа ажиллуулж санах ойд ачаална (swap-аас буцаана)."""
        t = time.perf_counter()
        try:
            self.stt.transcribe(np.zeros(SR, np.float32), SR)
            self.embedder.query(WARM_TEXTS)
        except Exception as e:
            print(f"  [warm алдаа] {e}")
        if time.perf_counter() - t > 3:
            print(f"  [warm] {time.perf_counter() - t:.1f}s (swap-аас ачааллаа)")

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
        self.dtmf_at = 0.0               # сүүлд товчлуур дарсан цаг (DTMF_GAP)
        self.caller_level = 0.0          # залгагчийн ярианы түвшин (хүлээж авсан өгүүлбэрүүдийн оргил)
        self.reprompt: asyncio.Task | None = None   # бүртгэлийн асуултыг давтах таймер
        self.hearing = False             # залгагч яг одоо ярьж байна (VAD)
        self.name_audio = None           # нэрийн бичлэг -> дуудлагын дараа нэрийг засна (fix_names)
        self.name_jobs: list = []        # [(lead_id, нэр, бичлэг)]
        self.last_lead_id: int | None = None   # энэ дуудлагад хадгалсан бүртгэл (цаг товлоход)
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

    async def hangup(self):
        """AI утсаа салгана (sip_bridge -> утас руу BYE). Хариулт play()-д бүрэн илгээгдсэн."""
        await asyncio.sleep(0.8)          # утасны jitter buffer-т үлдсэн сүүлийн үг
        print("  AI утсаа салгалаа")
        self.send(HANGUP)
        await self.writer.drain()

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
        except RuntimeError as exc:
            print(f"  [STT алдаа] {exc}")
            holder.cancel()
            await self.play(*self.router.clip(self.router.meta["error"]))
            return
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
        name_flow = self.lead if self.lead and self.lead.state == "name" else None
        if self.lead and await self.lead_turn(text):
            if name_flow and name_flow.state != "name":    # нэрээ хэлсэн бичлэг
                self.name_audio = audio
            return
        if self.account and lang != "en" and await self.account_turn(text=text):
            return
        if (lang != "en" and not self.lead and not self.account and "lead" in self.router.meta
                and (wants_event(text, self.upcoming_events())
                     or wants_event(self.router.fix_stt(text), self.upcoming_events()))):
            caller = db.caller_of(self.uuid, path=self.tenant.db_path) if self.uuid else None
            self.lead = LeadFlow("event", "event_start", caller, events=self.upcoming_events())
            print("  [эвент] бүртгүүлэх хүсэлт")
            if await self.lead_turn(text):
                return
        elif (lang != "en" and not self.lead and not self.account and "which_ask" in self.router.meta.get("lead", {})
                and self.upcoming_events() and wants_register(self.router.fix_stt(text))):
            # "Бүртгүүлмээр байна" (юунд гэдгийг хэлээгүй, эвент байгаа) -> хөтөлбөр үү, эвент үү гэж асууна
            caller = db.caller_of(self.uuid, path=self.tenant.db_path) if self.uuid else None
            book = "account" in self.router.meta and bool(people.free_slots(self.tenant.dir))
            self.lead = LeadFlow("lead", "which_start", caller, events=self.upcoming_events(), book=book)
            print("  [бүртгэл] хөтөлбөр үү, эвент үү?")
            self.lead_question = None
            if await self.lead_turn(text):
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
        # "Өөр асуух зүйл байна уу?" -> "Байхгүй" -> баяртай гээд AI өөрөө утсаа салгана.
        # Сонгогч "одоо", "хайр"-ыг ч баяртай гэж үзсэн удаатай -> ийм үг байвал л салгана.
        if meta.get("faq_id") == "smalltalk_bye" and BYE_WORDS.search(text.lower()):
            await self.hangup()

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
            reason = START_FAQ[meta["faq_id"]]
            book = reason == "lead" and "account" in self.router.meta and bool(people.free_slots(self.tenant.dir))
            self.lead = LeadFlow(reason, "name", caller, book=book)
            self.lead_question = None

    def upcoming_events(self) -> list[dict]:
        """Удахгүй болох эвентүүд (Тохиргоо -> Эвент), ойроос нь. "Эвентэд бүртгүүлмээр байна" -> эдгээрээс."""
        now = datetime.now(people.TZ)
        evs = [e for e in people.events(self.tenant.dir) if people.parse_local(e["at"]) > now]
        return sorted(evs, key=lambda e: e["at"])[:3]

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
        replay = []                       # залгагч чимээгүй бол асуултыг давтах (arm_reprompt)

        async def say(wav, sr):
            replay.append((wav, sr))
            await self.play(wav, sr)
        en = self.en if flow.lang == "en" and self.en else None
        code_keys = []
        if (flow.save_pending or (flow.finished and flow.result not in ("declined", "book"))) and not flow.saved:
            flow.saved, flow.save_pending = True, False
            code = self.save_lead(flow)
            if flow.duplicate:
                flow.saved, flow.result, flow.state = False, "duplicate", "duplicate"
                keys = ["already_registered"]
            if code and not en and "account" in router.meta:
                code_keys = ["your_code", f"digits:{code}", "code_remember"]
        if code_keys and keys:
            keys = keys[:-1] + code_keys + keys[-1:]
        if keys == ["@book"]:                         # "Уулзалтын цаг товлох уу?" -> тийм
            self.lead = None
            return await self.start_booking(text)
        for key in keys:
            if key in code_keys and not key.startswith("digits:"):
                clip = router.meta["account"][key]
                await say(*router.clip(clip))
                spoken.append(clip["text"])
            elif key.startswith("digits:"):
                digits = key.split(":", 1)[1]
                await say(*self.digits_audio(digits, en))
                spoken.append(" ".join(digits[i:i + 2] for i in range(0, len(digits), 2)))
            elif key.startswith("date:"):             # эвентийн гараг, сар, өдөр, цаг
                parts = people.slot_parts(people.parse_local(key.split(":", 1)[1]))
                for part in parts:
                    clip = router.meta.get("dates", {}).get(part)
                    if clip:
                        await say(*router.clip(clip))
                spoken.append(" ".join(parts))
            elif key.startswith("ev:"):               # эвентийн нэр («Аудио бэлдэх»-ээр бэлдсэн)
                clip = router.meta.get("events", {}).get(key[3:])
                if clip:
                    await say(*router.clip(clip))
                else:
                    print(f"  [анхаар] '{key[3:]}' эвентийн аудио алга — «Аудио бэлдэх» дарна уу")
                spoken.append(key[3:])
            else:
                clip = en.lead(key) if en else router.meta["lead"].get(key)
                if not clip:                          # шинэ хэллэг, аудио бэлдээгүй
                    print(f"  [анхаар] '{key}' хэллэгийн аудио алга — «Аудио бэлдэх» дарна уу")
                    continue
                await say(*(en.clip(clip) if en else router.clip(clip)))
                spoken.append(clip["text"])
        reply = " ".join(spoken)
        print(f"  AI [бүртгэл:{flow.state}]: {reply}")
        self.log("assistant", reply, route=f"lead_{flow.result or flow.state}")
        if flow.finished:
            self.lead = None
            if flow.event and flow.saved:          # "бүртгэж авлаа ... баяртай" -> яриаг дуусгана
                await self.hangup()
        else:
            self.arm_reprompt(replay)
        if not flow.finished and flow.state == "phone" and self.dtmf:   # нэрийн алхмын үед бичсэн цифрүүд
            self.dtmf_at = time.monotonic()          # хэллэг тоглох хугацааг завсар гэж тооцохгүй
            local = self.dtmf[3:] if self.dtmf.startswith("976") else self.dtmf
            if len(local) >= 8:
                asyncio.get_running_loop().call_soon(self.on_dtmf, "#")
        self.history += [{"role": "user", "content": text},
                         {"role": "assistant", "content": reply}]
        self.history = self.history[-8:]
        return True

    def save_lead(self, flow: LeadFlow) -> str | None:
        """Бүртгэлийг хадгалж, хувийн RAG-д холбоно (код + баримтууд) -> бүртгэлийн код."""
        try:
            course = flow.event["name"] if flow.event else self.tenant.config().get("lead_label")
            existing = (db.active_lead(flow.phone, path=self.tenant.db_path)
                        if flow.reason in ("lead", "event") and flow.phone else None)
            if existing:
                flow.duplicate, self.last_lead_id = True, existing
                print(f"  [LEAD] өмнө бүртгэлтэй хэрэглэгч (#{existing})")
                return None
            lead_id = db.add_lead(self.uuid, flow.name, flow.phone, " | ".join(flow.phone_raw) or None,
                                  flow.caller, flow.reason, self.lead_question, course=course,
                                  path=self.tenant.db_path)
            self.last_lead_id = lead_id
            print(f"  [LEAD] {flow.name} {flow.phone or '(дугааргүй)'} ({flow.reason})")
            if flow.lang == "mn" and flow.name:
                self.name_jobs.append((lead_id, flow.name, self.name_audio))
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
        except Exception as e:
            print(f"  [хувийн RAG алдаа] {e}")
            return None
        if flow.phone:
            try:
                asyncio.get_running_loop().run_in_executor(
                    None, notify.send_registration_code, flow.phone, code,
                    self.tenant.config().get("name") or "")
            except Exception as e:
                print(f"  [SMS эхлүүлэх алдаа] {type(e).__name__}")
        return code

    def fix_names(self, jobs):
        """Дуудлагын дараа: нэрийн бичлэгийг нэрсийн санууллагатай дахин таниулж, монгол нэрсийн
        жагсаалтаас хамгийн ойрыг сонгоно ("бэлэг сайхан" -> "Билэгсайхан"). Дуудлагын явцад
        нэр муу танигддаг тул энд засна."""
        lex = names.lexicon(os.path.join(self.tenant.dir, "names.txt"))
        for lead_id, name, audio in jobs:
            try:
                texts = [name]
                if audio is not None and isinstance(self.m.stt, WhisperSTT):
                    texts += [self.m.stt.transcribe(audio, SR, **d) for d in NAME_DECODES]
                fixed = names.fix(names.best_text(texts, lex), lex)
                if fixed and fixed != name:
                    db.set_lead_name(lead_id, fixed, path=self.tenant.db_path)
                    people.docs(self.tenant.dir, lead_id)
                    # дуудлагын явцад ажилтанд таниагүй нэр ("Нөмнө") очсон -> засварыг мэдэгдэнэ
                    org = self.tenant.config().get("name", self.tenant.slug)
                    notify.send(f"{org}: бүртгэл #{lead_id}-ийн нэр засагдлаа — {name} → {fixed}",
                                self.tenant.settings_path)
                print(f"  [нэр] #{lead_id} {texts!r} -> {fixed}")
            except Exception as e:
                print(f"  [нэр засах алдаа] {type(e).__name__}: {e}")

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
        await self.play_account(flow, keys, text or f"[товчлуур] {digits}")
        return True

    async def start_booking(self, text: str) -> bool:
        """Шинэ бүртгэлийн дараа шууд цаг товлох: кодоор нэвтэрсэн мэт account.py-ийн цаг санал болгох урсгал."""
        lead = people.lead(self.tenant.dir, self.last_lead_id) if self.last_lead_id else None
        if not lead:
            return False
        flow = acct.AccountFlow(self.tenant.dir, self.m.account_search, None, self.uuid)
        flow.lead, flow.state = lead, "menu"
        self.account = flow
        keys = await asyncio.to_thread(flow._do, "change_time")
        await self.play_account(flow, keys, text)
        return True

    async def play_account(self, flow, keys: list[str], said: str):
        spoken = []
        for key in keys:
            if key.startswith("ev:"):                 # бүртгэлийн нэр (эвент/хөтөлбөр) — цуцлахын өмнө
                clip = self.router.meta.get("events", {}).get(key[3:])
                if clip:
                    await self.play(*self.router.clip(clip))
                spoken.append(key[3:])
            elif key.startswith("digits:"):
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
        self.history += [{"role": "user", "content": said}, {"role": "assistant", "content": reply}]
        self.history = self.history[-8:]

    def notify_change(self, lead: dict, ev: dict):
        """AI-ийн хийсэн өөрчлөлтийг ажилтанд (Telegram). Ажилтан гараар юу ч хийх шаардлагагүй."""
        what = {"phone": "утасны дугаар", "status": "бүртгэл", "attendance": "ирэх эсэх"}.get(ev["field"], "уулзалтын цаг")
        new = ev["new"] or "цуцалсан"
        who = "ажилтан утсаар өөрчиллөө" if ev.get("staff") else "залгагч өөрөө утсаар өөрчиллөө"
        msg = (f"{self.tenant.config().get('name', self.tenant.slug)}: {lead.get('name') or 'Бүртгэл'} — "
               f"{what} {ev['old'] or '—'} → {new} ({who})")
        print(f"  [өөрчлөлт] {msg}")
        asyncio.get_running_loop().run_in_executor(None, notify.send, msg, self.tenant.settings_path)
        phone = lead.get("phone") or lead.get("caller")
        if ev["field"] == "appointment" and ev["new"] and phone and not ev.get("staff"):
            try:
                if notify.load_settings(self.tenant.settings_path).get("sms_on_register"):
                    text = notify.event_sms_text(self.tenant.config().get("name") or "", "уулзалт", ev["new"], None)
                    asyncio.get_running_loop().run_in_executor(None, notify.send_sms, phone, text)
            except Exception as e:
                print(f"  [SMS эхлүүлэх алдаа] {type(e).__name__}")

    def on_dtmf(self, key: str):
        """Утасны товчлуур: бүртгэлийн дугаар асуух үед 8 цифр (эсвэл # хүртэл) цуглуулна.
        Яриагаар хэлсэн дугаарыг STT ихэвчлэн алддаг ("наян" -> "ноён"), товчлуур 100% зөв."""
        self.cancel_reprompt()
        if self.account and not self.lead:
            return self.on_account_dtmf(key)
        if not self.lead:                # "кодоо бичнэ үү" тоглож байхад дарсан цифрийг хадгална
            self.dtmf = "" if key in "*#" else (self.dtmf + key)[-12:]
            return
        if not (self.lead and self.lead.state in ("name", "phone", "confirm", *ONE_KEY)):
            return
        if key == "*":                    # алдсан бол * дараад дахин эхэлнэ
            self.dtmf = ""
            return
        # Хагас бичээд зогсож, дахин эхнээс нь бичвэл хуучин цифрүүд урд нь наалдаж
        # "88008432" -> "00843288" болж байсан (бодит дуудлага) -> удаан завсарласан бол шинээр эхэлнэ
        now = time.monotonic()
        if key != "#" and self.dtmf and now - self.dtmf_at > DTMF_GAP:
            self.dtmf = ""
        self.dtmf_at = now
        if self.lead.state == "name":     # нэрийг таниулж байх зуур дугаараа бичиж эхэлсэн -> хадгална
            if key != "#":
                self.dtmf += key
            return
        # Баталгаажуулах үед 1=зөв, 2=буруу. # хүлээлгүй шууд боловсруулна.
        if key in ONE_KEY.get(self.lead.state, "") and not self.dtmf:
            digits = key
        else:
            if key != "#":
                self.dtmf += key
            digits = self.dtmf
        local = digits[3:] if digits.startswith("976") else digits
        complete = len(digits) == 1 and digits in ONE_KEY.get(self.lead.state, "")
        if complete or key == "#" or len(local) >= 8:  # 8 цифр болмогц автоматаар (эсвэл # дарахад)
            self.dtmf = ""
            print(f"  [товчлуур] {digits}")
            prev = self.turn
            self.flush()

            async def run():
                await self.interrupt(prev)
                if self.lead:
                    await self.dtmf_turn(digits)
            self.turn = asyncio.create_task(run())

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
            await self.interrupt(prev)
            if self.account:
                await self.account_turn(digits=digits)
        self.turn = asyncio.create_task(run())

    @staticmethod
    async def interrupt(prev):
        """Товчлуур дарахад AI-ийн одоо ярьж буй хэллэгийг (жишээ нь эвентийн огноо) тасална:
        өмнө нь дуусахыг хүлээгээд дараа нь хариулдаг байсан. flush() тоглож буй дууг цэвэрлэсэн."""
        if prev and not prev.done():
            prev.cancel()
            try:
                await prev
            except asyncio.CancelledError:
                pass

    async def dtmf_turn(self, digits: str):
        self.log("user", f"[товчлуур] {digits}")
        if self.lead.state == "confirm":
            if digits not in ("1", "2"):  # дахин дугаар бичвэл шинэ дугаар
                self.lead.state = "phone"
            elif self.lead.lang == "en":
                digits = "yes" if digits == "1" else "no"
        await self.lead_turn(digits)

    def digits_audio(self, digits: str, en: "english.EnglishRouter | None" = None):
        """Дугаарыг хоёр хоёр оронгоор уншина ("85 22" -> "наян тав, хорин хоёр"). Хосын аудио
        бэлдээгүй (хуучин индекс) эсвэл англи бол цифр бүрээр: хос бүрийн дараа урт завсар."""
        src = en or self.router
        pairs = None if en else self.router.meta.get("pairs")
        parts, sr = [], 24000
        if pairs:
            for i in range(0, len(digits), 2):
                chunk = digits[i:i + 2]
                clip = pairs.get(chunk) if len(chunk) == 2 else self.router.meta["digits"][int(chunk)]
                wav, sr = src.clip(clip)
                parts += [wav, np.zeros(int(sr * 0.25), np.float32)]
            return np.concatenate(parts), sr
        clips = en.digits() if en else self.router.meta["digits"]
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

    def arm_reprompt(self, clips):
        """Бүртгэлийн асуултын дараа залгагч REPROMPT_AFTER сек чимээгүй бол асуултаа нэг удаа давтана.
        AI "Зөв үү? ... дарна уу" гэж ярьж байхад "зөв" гэвэл half-duplex-д алга болж, хоёр тал
        бие биенээ хүлээгээд гацдаг байсан (туршилт)."""
        self.cancel_reprompt()
        if clips:
            self.reprompt = asyncio.create_task(self._reprompt(list(clips)))

    def cancel_reprompt(self):
        if self.reprompt and not self.reprompt.done() and self.reprompt is not asyncio.current_task():
            self.reprompt.cancel()
        self.reprompt = None

    async def _reprompt(self, clips):
        await asyncio.sleep(REPROMPT_AFTER)
        while self.hearing and not self.closed:     # ярьж эхэлсэн -> өгүүлбэр дуусахыг хүлээнэ
            await asyncio.sleep(0.3)
        if self.closed or not self.lead or self.busy or self.reprompt is not asyncio.current_task():
            return
        print("  [дахин асуув] залгагч чимээгүй")
        for wav, sr in clips:
            await self.play(wav, sr)

    def start_turn(self, audio: np.ndarray):
        self.cancel_reprompt()
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
        levels: list[float] = []         # сүүлийн NOISE_WINDOW секундын түвшин (орчны дуу)
        utt_rms: list[float] = []        # өгүүлбэрийн chunk бүрийн түвшин
        utt_peak = 0.0

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
                    # Мэндчилгээ тоглох зуур загваруудыг swap-аас санах ойд буцаана: 8GB дээр
                    # дуудлагын эхний STT 6–20с болж байсан. stt_pool (1 thread) -> эхний яриа араас нь
                    asyncio.get_running_loop().run_in_executor(self.m.stt_pool, self.m.warm)
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
                        if VAD_DEBUG and in_speech:
                            print("  [vad] AI ярьж эхэлсэн -> залгагчийн өгүүлбэр хаагдлаа")
                        # Half-duplex: AI ярьж байхад ирсэн дуу нь ихэвчлэн AI-ийн өөрийнх нь echo
                        in_speech, speech, muted = False, [], True
                        pre = (pre + [chunk])[-int(PRE_ROLL / chunk_sec):]  # дуу хаагдсан ч хадгална
                        continue
                    if muted:
                        self.vad.reset_states()
                        muted = False
                    prob = self.vad(torch.from_numpy(chunk), SR).item()
                    rms = float(np.sqrt(np.mean(chunk * chunk)))
                    levels = (levels + [rms])[-int(NOISE_WINDOW / chunk_sec):]
                    noise = float(np.percentile(levels, 20)) if len(levels) > 10 else 0.0
                    near = rms >= max(MIN_RMS, noise * SPEECH_SNR)

                    voiced = prob >= VAD_THRESHOLD and near
                    if voiced and (not in_speech or rms >= utt_peak * REL_SPEECH):
                        if not in_speech:
                            in_speech, speech, speech_sec, barged = True, list(pre), 0.0, False
                            utt_rms = [float(np.sqrt(np.mean(c * c))) for c in pre]
                            utt_peak = 0.0
                        speech.append(chunk)
                        utt_rms.append(rms)
                        utt_peak = max(utt_peak, rms)
                        speech_sec += chunk_sec
                        silence_sec = 0.0
                        # AI ярьж байхад залгагч хангалттай урт ярьвал -> зогсооно
                        if BARGE_IN > 0 and not barged and speech_sec >= BARGE_IN and self.ai_audible:
                            self.barge_in()
                            barged = True
                    elif in_speech:
                        speech.append(chunk)
                        utt_rms.append(rms)
                        silence_sec += chunk_sec      # оргилоос сул яриа (үгийн сүүл эсвэл ард яриа) -> төгсгөлд чимээгүй
                        if voiced:
                            speech_sec += chunk_sec   # ...гэхдээ MIN_SPEECH-д тоолно ("зөв" 0.19с болж алгасагдсан)
                    if in_speech and (silence_sec >= END_SILENCE or len(speech) * chunk_sec >= MAX_UTTERANCE):
                        if silence_sec < END_SILENCE:
                            print(f"  [VAD] {MAX_UTTERANCE:.0f}с-ээс урт (орчны дуу {noise:.3f}) -> таниулна")
                        in_speech = False
                        if VAD_DEBUG:
                            print(f"  [vad] {speech_sec:.2f}s оргил {utt_peak:.3f} залгагч {self.caller_level:.3f} "
                                  f"busy={self.busy} орчин {noise:.3f}")
                        if speech_sec >= MIN_SPEECH:
                            if self.caller_level and utt_peak < self.caller_level * FAR_RATIO:
                                print(f"  [алгасав] алсын яриа (орчны хүн) {utt_peak:.3f} < {self.caller_level:.3f}")
                            elif self.busy and not barged:
                                print("  [алгасав] AI хариу бэлдэж байх үеийн яриа")
                            else:
                                self.caller_level = (utt_peak if not self.caller_level
                                                     else 0.7 * self.caller_level + 0.3 * utt_peak)
                                self.start_turn(near_speech(speech, utt_rms, utt_peak, chunk_sec))
                        speech = []
                    pre = (pre + [chunk])[-int(PRE_ROLL / chunk_sec):]
                    self.hearing = in_speech
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            self.closed = True
            if self.name_jobs:   # утас тасарсны дараа -> дуудлагыг саатуулахгүй
                asyncio.get_running_loop().run_in_executor(self.m.stt_pool, self.fix_names, list(self.name_jobs))
            if self.uuid:
                try:
                    db.end_call(self.uuid, path=self.tenant.db_path)
                except Exception as e:
                    print(f"  [лог алдаа] {e}")
            if self.turn and not self.turn.done():
                self.turn.cancel()
            sender.cancel()
            self.writer.close()


def near_speech(chunks: list, levels: list, peak: float, chunk_sec: float, pad: float = 0.3) -> np.ndarray:
    """Өгүүлбэрээс залгагчийн (ойрын, чанга) яриаг л үлдээнэ: эхний/сүүлийн чанга хэсгийн гадна талын
    сул яриа (ард ярьж буй хүн) хасагдана, дотор нь сул хэсэг 0.25 болно. Шуугиантай туршилтад
    ард яриа "юм уу мөнх" нь "зөв"-ийг дарж байсан."""
    loud = [i for i, r in enumerate(levels) if r >= peak * REL_SPEECH]
    if not loud:
        return np.concatenate(chunks)
    n = int(pad / chunk_sec)
    lo, hi = max(0, loud[0] - n), min(len(chunks), loud[-1] + 1 + n)
    return np.concatenate([c if levels[i] >= peak * REL_SPEECH or not (loud[0] <= i <= loud[-1]) else c * 0.25
                           for i, c in enumerate(chunks[lo:hi], lo)])


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
        if head.startswith(b"POST /stt"):      # вэбийн сануулгын дуудлага (outbound/session.py): яриа -> бичвэр
            pcm = np.frombuffer(base64.b64decode(body["audio"]), "<i2").astype(np.float32) / 32768
            text = await asyncio.get_running_loop().run_in_executor(
                models.stt_pool, models.stt.transcribe, pcm, int(body.get("sr", SR)))
            data = json.dumps({"text": text}, ensure_ascii=False).encode()
            raise StopAsyncIteration
        t = tenants.Tenant(body["tenant"])
        router = await asyncio.to_thread(models.router_for, t)
        out = [await review_one(router, q) for q in body.get("questions", [])[:60]]
        data = json.dumps(out, ensure_ascii=False).encode()
    except StopAsyncIteration:
        pass
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
