"""
Pinecone AI Receptionist - хурдан хариулдаг voice pipeline

Асуулт ирэхэд (бүх хариулт урьдчилан бэлдсэн аудио, дуудлагын үеэр TTS ажиллахгүй):
  0. Сургасан сонгогч (selector.py) итгэлтэй бол -> түүний сонгосон аудио / "мэдээлэлд алга"
  1. FAQ-тай маш төстэй бол     -> FAQ-ийн бэлэн аудиог ШУУД тоглуулна
  2. knowledge/ доторх өгүүлбэрүүдээс (scripts/ingest.py урьдчилан аудио болгосон):
     - маш төстэй өгүүлбэр      -> тэр өгүүлбэрийн аудиог шууд тоглуулна
     - эргэлзээтэй              -> filler/hold тоглуулж байх зуур LLM аль өгүүлбэр нь
                                   хариулт болохыг ДУГААРААР сонгоно (~1с, текст зохиохгүй)
  3. Юу ч таарахгүй бол         -> "ажилтантай холбож өгье" бэлэн аудио
     (LLM_GENERATE=1 үед: LLM шинэ хариулт бичиж TTS хийнэ. 8GB RAM дээр маш удаан)
  Хүлээлгийн үед HOLD_AFTER секунд чимээгүй болмогц hold хэллэг/аялгууг ээлжлэн тоглуулна.

Бэлтгэл:
  python scripts/ingest.py       # knowledge/ -> knowledge_index/
  python build_faq_audio.py      # faq.json   -> faq_audio/

Ажиллуулах (текстээр тест):
  python stream_voice.py
"""

import offline  # noqa: F401  (хамгийн эхэнд: HF загварыг зөвхөн локалаас)
import asyncio
import json
import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import numpy as np
import sounddevice as sd
import soundfile as sf

from selector import Selector, normalize

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")    # LLM_GENERATE=1 үед монголоор хариулт бичих
# Өгүүлбэр сонгох (зөвхөн дугаар буцаана) - жижиг модель хангалттай, RAM хэмнэнэ (2.5GB vs 4.3GB)
SELECT_MODEL = os.getenv("SELECT_MODEL", "qwen3:4b-instruct-2507-q4_K_M")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "80"))
# auto: voices/custom.wav (вэбээр бичсэн хүний хоолой, voice clone) байвал түүнийг, үгүй бол Oron "female"
TTS_VOICE = os.getenv("TTS_VOICE", "auto")
VOICES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voices")
CUSTOM_REF = os.path.join(VOICES_DIR, "custom.wav")
TTS_NFE_STEP = int(os.getenv("TTS_NFE_STEP", "16"))
# F5 хугацааг байтын уртаар тооцдог тул монгол (кирилл=2 байт) хэт хурдан гарсан: хүний лавлах хоолой
# 13.7 үсэг/с, TTS дунджаар 15.9, зарим нь 17-21 (хэрэглэгч "хэт хурдан" гэсэн) -> 0.85
TTS_SPEED = float(os.getenv("TTS_SPEED", "0.85"))
# Урьдчилан бэлддэг тул чанарт анхаарна: монгол хэсгийг хэд хэдэн seed-ээр үүсгэж, STT хамгийн
# зөв таньсныг сонгоно (scorer өгсөн үед, ж.нь build_faq_audio, ingest). 1 = зөвхөн seed 0.
TTS_CANDIDATES = int(os.getenv("TTS_CANDIDATES", "4"))
TTS_LEAD_SILENCE = 0.15   # утасны дуудлагын эхэнд эхний авиа алдагдахгүй
TTS_TARGET_RMS = 0.07     # бүх клипийн дууны түвшинг тэнцүүлнэ

FAQ_MATCH = float(os.getenv("FAQ_MATCH", "0.80"))      # үүнээс дээш = бэлэн хариу (0.75 үед "хэдэн цагт" -> "хэр удаан" гэж андуурсан)
TOPIC_MATCH = float(os.getenv("TOPIC_MATCH", "0.58"))  # үүнээс дээш = сэдвийн bridge
RAG_MATCH = float(os.getenv("RAG_MATCH", "0.45"))      # үүнээс доош = мэдээлэл олдсонгүй
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))

# RAG мэдээллийн урьдчилсан аудиотой өгүүлбэрүүд (scripts/ingest.py) -> дуудлагын үеэр TTS ажиллахгүй
FACT_DIRECT = float(os.getenv("FACT_DIRECT", "0.68"))  # үүнээс дээш = LLM-гүйгээр шууд тоглуулна
FACT_MIN = float(os.getenv("FACT_MIN", "0.40"))        # үүнээс доош = нэр дэвшигч болохгүй
FACT_CANDIDATES = 4
# Утгын (embedding) оноонд үгийн язгуурын давхцлыг нэмнэ: "хуваан"~"хувааж", "зээлээр"~"зээлийн".
# 38 өгүүлбэртэй үед embedding дангаараа "дадлага хийдэг үү"-г "ярилцлага хийдэг"-тэй андуурсан.
LEX_WEIGHT = float(os.getenv("LEX_WEIGHT", "0.15"))
LEX_STOP = {"вэ", "уу", "үү", "юу", "бэ", "нь", "болох", "болно", "байна", "байдаг", "байгаа",
            "хийдэг", "хийх", "юм", "гэж", "гэсэн", "болон", "та", "би", "танай", "энэ", "тэр", "хэд",
            "хэдэн", "ямар", "яаж", "хаана", "мөн", "өгдөг", "авах", "талаар", "тухай", "мэдээлэл",
            "ийн", "ний", "ын", "тай", "тэй"}  # англи үгийн араас залгасан нөхцөл ("bootcamp-ийн")
# Эдгээр язгуураас өөр үггүй асуулт ("сургалтын талаар мэдээлэл") = хэт ерөнхий -> тодруулж асууна.
# Байгууллага бүрийнх faq_index.json-д (tenant.Tenant.generic_stems); энэ нь хуучин индексийн fallback.
GENERIC_STEMS = {"сург", "хөтө", "мэдэ", "тала", "тухa", "бүүт", "bootcamp", "pinecone", "акад", "academy",
                 "авъя", "авмаа", "хүсэ", "сонс"}


# "мэдээлэл авъя", "талаар асуух" — ерөнхий хүсэлтийн үгс (LEX_STOP-д байдаг тул тусад нь)
INFO_STEMS = {"мэдэ", "тала", "туха", "асуу"}


def lex_stems(text: str) -> set[str]:
    """Үгсийн эхний 4 үсэг (монгол нөхцлийг ойролцоогоор нэгтгэнэ). 3 үсэг "сургалт"-"сурагч"-ийг
    андуурсан тул 4."""
    words = re.findall(r"[а-яөүёa-z]+", text.lower())
    # Англи үг монгол шиг нөхцөл авдаггүй тул бүтнээр нь ("pinequest" != "pinecone")
    return {w if w.isascii() else w[:4] for w in words if len(w) >= 3 and w not in LEX_STOP}
FAQ_CANDIDATE = float(os.getenv("FAQ_CANDIDATE", "0.60"))  # FAQ_MATCH-аас доош ч LLM сонголтод оруулна
# LLM-гүй шийдвэр (default). 8GB RAM дээр LLM 3.5GB GPU санах ой түгжиж бүхнийг удаашруулсан,
# мөн сонголт нь найдваргүй байсан (зөв өгүүлбэр 1-рт байхад "0" гэсэн).
SELECT_LLM = os.getenv("SELECT_LLM", "0") == "1"
FACT_MARGIN = 0.05       # FACT_DIRECT-ээс дээш үед 2-р өгүүлбэрээс ийм зөрүүтэй байх
FAQ_NEAR = float(os.getenv("FAQ_NEAR", "0.70"))  # STT бага алдсан ("хэдэн сард сардаг") FAQ
FACT_OK = 0.50           # ...эсвэл ийм оноотой бөгөөд
FACT_OK_MARGIN = 0.08    # 2-р өгүүлбэрээс тод ялгарч байвал тоглуулна
TOP2_GAP = 0.03          # 2 өгүүлбэр тоглуулахад 3-р өгүүлбэрээс ийм зөрүүтэй байх
TOP2_STRONG = 0.75       # ...эсвэл 1-р нь ийм өндөр бол ("хэдэн компанитай хамтардаг" -> 3 нь бүгд хамаатай)
# Сургасан сонгогч: магадлал ийм өндөр бол дүрмийн өмнө шууд шийднэ
SELECTOR = os.getenv("SELECTOR", "1") == "1"
SEL_MIN = float(os.getenv("SEL_MIN", "0.5"))      # FAQ/өгүүлбэр тоглуулах
OTHER_MIN = float(os.getenv("OTHER_MIN", "0.6"))  # "мэдээлэлд алга" -> дүрмийг алгасаж дахин асууна
# Сонгогчийн өгүүлбэр-хариултыг асуулттай нийтлэг үг (>=1) эсвэл утгын төстэй байдал (>= энэ) баталгаажуулна.
# Хэмжилт (эмнэлэг + Pinecone): буруу 3 сонголт нийтлэг үггүй, sim<=0.53 ("мэс засал" -> "хүүхдийн эмч хийдэг");
# зөв 33 нь үгтэй эсвэл sim>=0.66.
SEL_FACT_SIM = float(os.getenv("SEL_FACT_SIM", "0.60"))
FLAT_SPREAD = 0.06      # 1-4-р өгүүлбэрийн зөрүү үүнээс бага = асуулт хэт ерөнхий -> тодруулна
FACT_MAX = 2
# Өгүүлбэр ч таарахгүй үед LLM-ээр шинэ хариулт бичүүлж TTS хийх эсэх.
# 8GB RAM дээр 1 минутаас удаан тул default унтраалттай -> "ажилтантай холбож өгье" аудио.
LLM_GENERATE = os.getenv("LLM_GENERATE", "0") == "1"

HOLD_AFTER = float(os.getenv("HOLD_AFTER", "0.8"))  # ийм удаан чимээгүй болвол hold тоглуулна
MAX_HOLDS = int(os.getenv("MAX_HOLDS", "30"))
STREAM_ANSWER = os.getenv("STREAM_ANSWER", "0") == "1"

FIRST_CHUNK_MIN = 15
CHUNK_MIN = 40
CHUNK_MAX = 160

HARD_END = re.compile(r"[.!?…](\s|$)")
SOFT_END = re.compile(r"[,;:](\s|$)")
FOLLOWUP_WORDS = {"нь", "тэр", "түүний", "үүний", "энэ", "тэгвэл", "тэгээд"}
LONG_WORDS, TAIL_WORDS = 7, 5   # үүнээс урт өгүүлбэрийн сүүлийн хэдэн үгийг тусад нь хайна
# "хэдэн цагт/хэдээс" нь үргэлжлэх хугацаа биш, цагийн хуваарь асууж байна. Embedding нь
# "хэдэн цагт эхэлдэг"-ийг "хэдэн сар үргэлжилдэг"-тэй хэт ойртуулдаг тул зөвхөн цагийн
# тухай асуулт/хариулттай FAQ-г зөвшөөрнө.
CLOCK_TIME = re.compile(r"(?:\bхэдэн\s+)?\bцагт\b|\bцагаас\b|\bхэдээс\b|\bцагийн\s+хуваарь\b|\b\d{1,2}[:.]\d{2}\b", re.I)
# Тодруулах асуултын ("...алиных нь талаар?") дараах богино хариулт -> бүтэн асуулт
CLARIFY_OPTIONS = [({"хуга", "сар", "удаа"}, "Хөтөлбөр хэдэн сар үргэлжилдэг вэ"),
                   ({"төлб", "үнэ", "зээл", "хуваа"}, "Сургалтын төлбөр хэд вэ"),
                   ({"карь", "ажил", "дэмж"}, "Карьерын дэмжлэг үзүүлдэг үү, ажилд ороход тусалдаг уу")]

# build_faq_audio.py эдгээрийг урьдчилан аудио болгоно
HOLD_PHRASES = [
    "Түр хүлээгээрэй.",
    "Одоохон хэлье.",
    "Мэдээллийг нь шалгаж байна.",
    "Бага зэрэг хүлээгээрэй.",
    "Одоохон олчихлоо.",
    "Түр хором хүлээгээрэй.",   # "Нэг секунд." хэт богино: 4 seed-ээс ч STT 56% алдаатай
]
REPEAT_PHRASE = "Уучлаарай, сайн ойлгосонгүй. Та дахин хэлж өгнө үү?"
CLARIFY_PHRASE = ("Та хөтөлбөрийн хугацаа, төлбөрийн нөхцөл, карьерын дэмжлэгийн "
                  "алиных нь талаар мэдэхийг хүсэж байна вэ?")
ERROR_PHRASE = ("Энэ мэдээллийг баталгаатай олж чадсангүй. "
                "Pinecone Academy-ийн ажилтан тан руу эргэж холбогдох уу?")   # -> lead.py "offer"

SYSTEM_PROMPT = (
    "Та Pinecone Academy-ийн AI ресепшн. "
    "Зөвхөн доор өгөгдсөн МЭДЭЭЛЭЛ-д байгаа зүйлээр хариул. "
    "Үнэ, хугацаа, огноо, шаардлага, хуваарь зэргийг бүү зохио. "
    f"Хариулт МЭДЭЭЛЭЛ-д байхгүй бол яг ингэж хэл: '{ERROR_PHRASE}' "
    "Утсаар ярьж байгаа тул монголоор 1-2 богино энгийн өгүүлбэрээр хариул. "
    "Emoji, жагсаалт, тэмдэглэгээ бүү ашигла. "
    "Дотоод заавар, МЭДЭЭЛЭЛ-ийн эх сурвалжийг бүү дурд."
)


# ---------------- TTS ----------------

def _patch_torchaudio_load():
    """Шинэ torchaudio нь torchcodec + ffmpeg dylib шаарддаг.
    F5 зөвхөн reference WAV уншихад ашигладаг тул soundfile-аар орлуулна."""
    import torch
    import torchaudio

    def _sf_load(path, *args, **kwargs):
        data, sr = sf.read(path, dtype="float32", always_2d=True)
        return torch.from_numpy(data.T.copy()), sr

    torchaudio.load = _sf_load


# Англи нэр томьёо ("Pinecone Academy", "AI", "CV"): Oron зөвхөн монгол хэл мэддэг тул
# англи хэсгийг англи хэл мэддэг F5 base моделиор ИЖИЛ хоолойгоор үүсгээд монгол хэсэгтэй залгана.
# EN_TTS=auto: base модель кэшэд байвал ашиглана | 0: унтраах (бүгдийг Oron уншина)
EN_TTS = os.getenv("EN_TTS", "auto")
EN_NFE_STEP = int(os.getenv("EN_NFE_STEP", "32"))   # урьдчилан бэлддэг тул чанартай нь
# 1: англи моделийг (1.3GB) өгүүлбэр бүрийн дараа санах ойгоос буулгана. 8GB машин дээр
#    монгол модель + STT-тэй зэрэг байхад swap-д орж аудио бэлдэлт 20 дахин удааширсан.
EN_UNLOAD = os.getenv("EN_UNLOAD", "1") == "1"
# Англи хэсгийн кэш: scripts/prebuild_en.py зөвхөн англи моделиор урьдчилан үүсгэнэ -> дараа нь
# монгол модель ганцаараа ажиллана (8GB-д хоёр модель зэрэг багтахгүй, өгүүлбэр бүр 15+ мин болж байсан)
EN_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "en_cache")

LATIN_RUN = re.compile(r"[A-Za-z][A-Za-z0-9.'’@/+]*(?:(?:\s*[&,]\s*|\s+|-)[A-Za-z0-9][A-Za-z0-9.'’@/+]*)*")
_CYR2LAT = dict(zip("абвгдеёжзийклмноөпрстуүфхцчшщъыьэюя",
                    ["a", "b", "v", "g", "d", "ye", "yo", "j", "z", "i", "i", "k", "l", "m", "n", "o",
                     "u", "p", "r", "s", "t", "u", "u", "f", "kh", "ts", "ch", "sh", "sh", "", "ii", "",
                     "e", "yu", "ya"]))


def romanize(text: str) -> str:
    out = []
    for ch in text:
        lat = _CYR2LAT.get(ch.lower())
        out.append(ch if lat is None else (lat.capitalize() if ch.isupper() else lat))
    return "".join(out)


def split_language(text: str) -> list[tuple[str, bool]]:
    """Текстийг [(хэсэг, англи_эсэх)] болгоно. "Pinecone Academy-ийн утас" ->
    [("Pinecone Academy", True), ("ийн утас", False)]"""
    segs, pos = [], 0
    for m in LATIN_RUN.finditer(text):
        run = m.group(0).rstrip(".,'’")
        if m.start() > pos:
            segs.append((text[pos:m.start()], False))
        segs.append((run, True))
        pos = m.start() + len(run)
    if pos < len(text):
        segs.append((text[pos:], False))

    out: list[tuple[str, bool]] = []
    for seg, en in segs:
        if not en:
            # "portfolio-г", "Club-т" гэх мэт 1-2 үсэгтэй нөхцөлийг англи үгэнд нь залгана
            # (дангаар нь уншвал утгагүй). "-ийн" мэт урт нөхцөл монгол хэсэгт үлдэнэ.
            m = re.match(r"^-(\w{1,2})\b", seg)
            if m and out and out[-1][1]:
                out[-1] = (f"{out[-1][0]}-{romanize(m.group(1))}", True)
                seg = seg[m.end():]
            seg = re.sub(r"^[-\s]+", "", seg.strip())
            if not re.search(r"\w", seg):
                continue                      # зөвхөн цэг, таслал
        out.append((seg, en))
    return out


EN_ACRONYM = re.compile(r"\b[A-Z]{2,4}\b")
EN_WORDS = {"RAG"}                     # үсэглэхгүй, үг шиг уншина


def en_prepare(text: str) -> tuple[str, float]:
    """Англи моделд зориулж бичвэрийг засаж, ярих хугацааг (сек) тооцоолно.
    "AI" -> "A I" (үсэглэнэ), "Pinecone" -> "Pine cone". Хоёулаа туршилтаар (STT) хамгийн тод гарсан."""
    text = re.sub(r"\bPinecone\b", "Pine cone", text)
    letters = 0

    def spell(m):
        nonlocal letters
        word = m.group(0)
        if word in EN_WORDS:
            return word.lower()
        letters += len(word)
        return " ".join(word)

    text = EN_ACRONYM.sub(spell, text)
    other = len(text) - 2 * letters
    return text, 0.35 + 0.088 * max(other, 0) + 0.45 * letters   # (0.075/0.4 үед хэт хурдан байсан)


TTS_MAX_CHARS = int(os.getenv("TTS_MAX_CHARS", "160"))


def split_long(text: str, limit: int = TTS_MAX_CHARS) -> list[str]:
    """Өгүүлбэрийн хил дээр limit хүртэл бүлэглэнэ. Нэг өгүүлбэр limit-ээс урт бол таслалаар."""
    if len(text) <= limit:
        return [text]
    sents = [x for x in re.split(r"(?<=[.!?])\s+", text.strip()) if x]
    out, buf = [], ""
    for sent in sents:
        pieces = [sent] if len(sent) <= limit else [x for x in re.split(r"(?<=,)\s+", sent) if x]
        for piece in pieces:
            if buf and len(buf) + 1 + len(piece) > limit:
                out.append(buf)
                buf = piece
            else:
                buf = f"{buf} {piece}".strip()
    if buf:
        out.append(buf)
    return out


def trim_silence(wav: np.ndarray, sr: int, pad: float = 0.08, start: bool = True, end: bool = True) -> np.ndarray:
    frame = int(sr * 0.01)
    n = len(wav) // frame
    if n == 0:
        return wav
    rms = np.sqrt((wav[:n * frame].reshape(n, frame) ** 2).mean(axis=1))
    # 0.02 босго "Сайн", "Хичээл"-ийн эхний сул гийгүүлэгчийг (с, х) тасалж байсан -> 0.008
    voiced = np.where(rms > 0.008 * rms.max())[0]
    # Гэвч F5 заримдаа 1с+ сул шуугиангаар эхэлдэг (0.008-аас их) -> англи үгийн араас 1.3с чимээгүй.
    # Тод ярианаас (5%) өмнө 0.25с, хойно 0.3с-ээс илүү сул хэсгийг авахгүй (гийгүүлэгч, сунжралтад хангалттай).
    strong = np.where(rms > 0.05 * rms.max())[0]
    if len(voiced) == 0:
        return wav
    first, last = voiced[0], voiced[-1]
    if len(strong):
        first, last = max(first, strong[0] - 25), min(last, strong[-1] + 30)
    a = max(0, first * frame - int(pad * sr)) if start else 0
    b = min(len(wav), (last + 1) * frame + int(pad * sr)) if end else len(wav)
    return wav[a:b]


# Англи үгэнд залгасан монгол нөхцөл ("Academy-ийн", "QPay-ээр"): завсаргүй шахам залгана
SUFFIX_START = re.compile(r"^(ийн|ын|ний|н|ийг|ыг|ид|д|т|аас|ээс|оос|өөс|аар|ээр|оор|өөр|тай|тэй|той|руу|рүү|луу|лүү)(?!\w)")


def speech_rms(wav: np.ndarray) -> float:
    speech = wav[np.abs(wav) > 0.01]
    return float(np.sqrt((speech ** 2).mean())) if len(speech) else 0.0


def join_segments(parts: list, segs: list, sr: int) -> np.ndarray:
    """Монгол/англи хэсгүүдийг залгах: хэсэг бүрийн чанга сулыг тэнцүүлж (англи загвар өөр түвшинд
    гаргадаг), залгаас дээр 12мс зөөлөн орж/гарах (товшилтгүй), нөхцлийн өмнө 15мс, бусад 80мс завсар."""
    fade = int(sr * 0.012)
    out = []
    for i, part in enumerate(parts):
        part = part.astype(np.float32).copy()
        level = speech_rms(part)
        if level > 1e-4:
            part *= TTS_TARGET_RMS / level
        if len(part) > 2 * fade:
            if i > 0:
                part[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
            if i < len(parts) - 1:
                part[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
        out.append(part)
        if i < len(parts) - 1:
            nxt, nxt_en = segs[i + 1]
            gap = 0.015 if (not nxt_en and SUFFIX_START.match(nxt.strip())) else 0.08
            out.append(np.zeros(int(sr * gap), np.float32))
    return np.concatenate(out)


def finish_clip(wav: np.ndarray, sr: int) -> np.ndarray:
    """Дууны түвшинг тэнцүүлж, эхэнд чимээгүй нэмнэ."""
    speech = wav[np.abs(wav) > 0.01]
    level = float(np.sqrt((speech ** 2).mean())) if len(speech) else 0.0
    if level > 1e-4:
        wav = wav * (TTS_TARGET_RMS / level)
    peak = float(np.abs(wav).max()) if len(wav) else 0.0
    if peak > 0.95:
        wav = wav * (0.95 / peak)
    lead = np.zeros(int(sr * TTS_LEAD_SILENCE), np.float32)
    return np.concatenate([lead, wav.astype(np.float32)])


def _en_checkpoint() -> str | None:
    """F5 base (англи) checkpoint кэшэд байвал замыг нь буцаана. Татахгүй."""
    if EN_TTS == "0":
        return None
    from huggingface_hub import try_to_load_from_cache
    path = try_to_load_from_cache("SWivid/F5-TTS", "F5TTS_v1_Base/model_1250000.safetensors")
    return path if isinstance(path, str) else None


def reference_voice(voice: str = TTS_VOICE) -> tuple[str, str]:
    """(лавлах WAV, түүний бичвэр). F5 энэ хүний хоолой, хэмнэлийг дуурайна."""
    if voice in ("auto", "custom") and os.path.exists(CUSTOM_REF):
        with open(CUSTOM_REF[:-4] + ".txt", encoding="utf-8") as f:
            return CUSTOM_REF, f.read().strip()
    from huggingface_hub import hf_hub_download
    name = "female" if voice in ("auto", "custom") else voice
    ref_file = hf_hub_download("btsee/oron-tts", f"voices/{name}.wav")
    with open(hf_hub_download("btsee/oron-tts", f"voices/{name}.txt"), encoding="utf-8") as f:
        return ref_file, f.read().strip()


def tts_settings() -> dict:
    """Байгууллагын (TENANT) ярианы тохиргоо: дуудлагын толь, хурд, өгүүлбэр хоорондын завсар."""
    import tenant
    cfg = tenant.current().config()
    speed = float(cfg.get("tts_speed") or TTS_SPEED)
    return {"lexicon": cfg.get("lexicon") or [], "speed": min(max(speed, 0.7), 1.15),
            "pause": min(max(int(cfg.get("pause_ms") or 300), 100), 1000) / 1000}


def spoken(text: str) -> str:
    """TTS-д өгөх бичвэр: байгууллагын дуудлагын толийг хэрэглэсэн."""
    from speech import apply_lexicon
    return apply_lexicon(text, tts_settings()["lexicon"])


def question_reference() -> tuple[str, str] | None:
    """Асуултын аялгатай лавлах бичлэг ("...уу?" өсөх өнгө): байгууллагын, эсвэл нийтлэг. Байхгүй бол None."""
    import tenant
    for d in (tenant.current().path("voice"), VOICES_DIR):
        wav, txt = os.path.join(d, "question.wav"), os.path.join(d, "question.txt")
        if os.path.exists(wav) and os.path.exists(txt):
            with open(txt, encoding="utf-8") as f:
                return wav, f.read().strip()
    return None


def voice_tag(engine: str | None = None) -> str:
    """Аудио кэшийн түлхүүрт нэмнэ: хоолой эсвэл чанарын тохиргоо солигдвол бүгд шинээр үүснэ.
    engine: "oron" | "eleven" (өгөөгүй бол байгууллагын анхдагч)."""
    import hashlib
    eng = tts_engine()
    if (engine or eng["engine"]) == "eleven":
        return eleven_tag(eng)
    ref_file, ref_text = reference_voice()
    with open(ref_file, "rb") as f:
        h = hashlib.sha1(f.read() + ref_text.encode()).hexdigest()[:8]
    speed = tts_settings()["speed"]
    return f"{h}-n{TTS_NFE_STEP}-s{round(speed * 100)}-v2"   # seed-ийн тоо зөвхөн сонголтод нөлөөлөх тул тэмдэгт оруулахгүй


def clip_key(text: str, seed: int = 0, tag: str | None = None) -> str:
    """Кэшийн файлын нэр. Уншигдах бичвэр (толь хэрэглэсэн) + хоолой. Англи үгтэй клипт залгаасны
    хувилбар (mix2), асуултын бичлэгтэй бол түүний hash, дахин үүсгэсэн бол seed нэмэгдэнэ —
    эдгээр байхгүй үед хуучин түлхүүртэй ижил (одоогийн кэш хүчинтэй)."""
    import hashlib
    from recordings import text_hash
    sp = spoken(text)
    extra = "|mix2" if re.search(r"[A-Za-z]", sp) else ""
    q = question_reference() if "?" in sp else None
    if q:
        with open(q[0], "rb") as f:
            extra += "|q" + hashlib.sha1(f.read() + q[1].encode()).hexdigest()[:8]
    if seed:
        extra += f"|seed{seed}"
    return text_hash(sp + (tag or voice_tag()) + extra)


def tts_seeds() -> dict:
    """"Дахин үүсгэх" дарсан клипүүдийн seed: tenants/<slug>/data/tts_seeds.json {text_hash: seed}."""
    import tenant
    try:
        with open(tenant.current().path("data", "tts_seeds.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


# ---------------- ElevenLabs: зөвхөн аудио БЭЛДЭХЭД ----------------
# Дуудлагын үед ашиглахгүй — залгагчид бэлдсэн аудио кэшээс тоглогдоно (хурд, интернэтгүй ажиллагаа хэвээр).
# config.json "tts_engine": "eleven" + "eleven_voice" үед "Аудио бэлдэх" кэшэд байхгүй (шинэ/өөрчлөгдсөн)
# өгүүлбэрийг ElevenLabs-аар үүсгэж хадгална. Түлхүүр: data/elevenlabs_key (git-д орохгүй, 600).
ELEVEN_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "elevenlabs_key")
ELEVEN_MODEL = "eleven_v4"          # монгол (mon) дэмждэг загвар (v3, multilingual v2 дэмждэггүй)
# Байгууллага хоолой сонгоогүй үед: Уянга (монгол, халх аялга; ElevenLabs-ийн нийтийн сан, төлбөртэй багц)
ELEVEN_DEFAULT_VOICE = os.getenv("ELEVEN_VOICE", "2cecqSnkajrth9sJSoEH")
ELEVEN_URL = "https://api.elevenlabs.io/v1"


def eleven_key() -> str | None:
    try:
        with open(ELEVEN_KEY_FILE, encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return os.getenv("ELEVENLABS_API_KEY")


def oron_available() -> bool:
    """Oron TTS (монгол F5 загвар) энэ машинд байгаа эсэх. Устгасан бол бүх аудиог ElevenLabs бэлдэнэ."""
    from huggingface_hub import try_to_load_from_cache
    return isinstance(try_to_load_from_cache("btsee/oron-tts", "model.safetensors"), str)


def tts_engine() -> dict:
    """Байгууллагын TTS: "eleven" (ElevenLabs, бэлдэх үед л) эсвэл "oron" (локал, загвар нь байвал).
    clips: өгүүлбэр бүрээр сонгосон ("Хоолой" хуудасны харьцуулалт) {text_hash: "oron" | "eleven"}."""
    import tenant
    cfg = tenant.current().config()
    oron = oron_available()
    voice = cfg.get("eleven_voice") or (ELEVEN_DEFAULT_VOICE if eleven_key() else None)
    engine = cfg.get("tts_engine") or ("oron" if oron else "eleven")
    if engine == "oron" and not oron:
        engine = "eleven"
    if engine == "eleven" and not voice and oron:
        engine = "oron"
    clips = {h: e for h, e in (cfg.get("clip_engine") or {}).items() if (e == "oron" and oron) or (e == "eleven" and voice)}
    return {"engine": engine, "voice": voice, "model": cfg.get("eleven_model", ELEVEN_MODEL),
            "speed": min(max(float(cfg.get("eleven_speed", 1.0)), 0.7), 1.2), "clips": clips, "oron": oron}


def eleven_tag(eng: dict | None = None) -> str:
    eng = eng or tts_engine()
    return f"eleven-{eng['voice']}-{eng['model']}-s{round(eng['speed'] * 100)}"


def engine_for(text: str) -> str:
    """Энэ өгүүлбэрийг аль TTS-ээр бэлдэх вэ: өгүүлбэрийн сонголт, эс бөгөөс байгууллагын анхдагч."""
    from recordings import text_hash
    eng = tts_engine()
    return eng["clips"].get(text_hash(text), eng["engine"])


def clip_seed(text: str, engine: str, seeds: dict | None = None) -> int:
    """"Дахин үүсгэх"-ийн seed TTS тус бүрт тусдаа: Oron-ийн засвар (чимээгүй "долоо") ElevenLabs-т хамаарахгүй.
    tts_seeds.json: {"<hash>": n} (Oron), {"eleven:<hash>": n} (ElevenLabs)."""
    from recordings import text_hash
    seeds = tts_seeds() if seeds is None else seeds
    h = text_hash(text)
    return seeds.get(h if engine == "oron" else f"{engine}:{h}", 0)


def eleven_sample_path(text: str, eng: dict | None = None) -> str:
    """Харьцуулахаар үүсгэсэн ElevenLabs аудио (seed 0) — сонгосон бол бэлдэхэд API-г дахин дуудахгүй."""
    import tenant
    from recordings import text_hash
    eng = eng or tts_engine()
    return tenant.current().path("data", "eleven_samples", eleven_tag(eng), f"{text_hash(text)}.wav")


class ElevenTTS:
    """OronTTS-тэй ижил synth(text, seed) -> (wav, sr). Монгол + англи холимог бичвэрийг нэг дор уншина."""
    scorer = None                   # best-of-N STT шалгалт Oron-д л

    def __init__(self, voice: str | None = None, model: str | None = None, speed: float | None = None):
        eng = tts_engine()
        self.key = eleven_key()
        if not self.key:
            raise RuntimeError(f"ElevenLabs түлхүүр алга: {ELEVEN_KEY_FILE}")
        self.voice = voice or eng["voice"]
        self.model = model or eng["model"]
        self.speed = speed if speed is not None else eng["speed"]
        if not self.voice:
            raise RuntimeError("ElevenLabs хоолой сонгоогүй (config.json eleven_voice)")

    def request(self, text: str, seed: int = 0, language: str | None = "mn") -> bytes:
        body = {"text": text, "model_id": self.model, "seed": seed}
        if language:
            body["language_code"] = language       # үгүй бол кирилл бичвэрийг орос аялгаар уншиж болзошгүй
        if self.speed != 1.0:
            body["voice_settings"] = {"speed": self.speed}
        for attempt in range(4):
            r = httpx.post(f"{ELEVEN_URL}/text-to-speech/{self.voice}", params={"output_format": "pcm_24000"},
                           headers={"xi-api-key": self.key}, json=body, timeout=180)
            if r.status_code == 200:
                return r.content
            if r.status_code in (429, 500, 502, 503) and attempt < 3:
                time.sleep(3 * 2 ** attempt)
                continue
            raise RuntimeError(f"ElevenLabs {r.status_code}: {r.text[:300]}")
        raise RuntimeError("ElevenLabs: хариу ирсэнгүй")

    def synth(self, text: str, seed: int = 0):
        from speech import speak
        gen = speak(spoken(text))        # утас, цаг, тоог монгол үгээр (утасны дугаарыг хосоор)
        wav = np.frombuffer(self.request(gen, seed), "<i2").astype(np.float32) / 32768
        return finish_clip(wav, 24000), 24000


def make_tts():
    """Бэлдэх скриптүүдэд: байгууллагын тохиргооны дагуу ElevenLabs эсвэл локал Oron."""
    return ElevenTTS() if tts_engine()["engine"] == "eleven" else OronTTS()


class OronTTS:
    def __init__(self, voice: str = TTS_VOICE):
        _patch_torchaudio_load()
        from f5_tts.api import F5TTS
        from huggingface_hub import hf_hub_download
        from oron_tts.text import MongolianNormalizer

        repo = "btsee/oron-tts"
        ckpt = hf_hub_download(repo, "model.safetensors")
        vocab = hf_hub_download(repo, "vocab.txt")
        self.ref_file, self.ref_text = reference_voice(voice)
        self._mn_args = dict(model="F5TTS_v1_Base", ckpt_file=ckpt, vocab_file=vocab, use_ema=False)
        self._mn_tts = None         # монгол модель: анх хэрэгтэй үед ачаална (англи pre-pass-д хэрэггүй)
        self.normalizer = MongolianNormalizer()
        self.en_ckpt = _en_checkpoint()
        self.en_tts = None          # анхны англи хэсэг гарахад ачаална
        self.scorer = None          # WhisperSTT өгвөл монгол хэсгийг best-of-N seed-ээр сонгоно
        st = tts_settings()
        self.speed, self.pause = st["speed"], st["pause"]
        self.qref = question_reference()   # "?"-ээр төгссөн хэсэгт асуултын аялгатай лавлах бичлэг

    @property
    def tts(self):
        if self._mn_tts is None:
            from f5_tts.api import F5TTS
            self._mn_tts = F5TTS(**self._mn_args)
        return self._mn_tts

    def en_cache_path(self, text: str) -> str:
        import hashlib
        with open(self.ref_file, "rb") as f:
            voice = hashlib.sha1(f.read()).hexdigest()[:8]
        key = hashlib.sha1(f"{text}|{voice}|{EN_NFE_STEP}|en2".encode()).hexdigest()[:16]   # en2: удаашруулсан
        return os.path.join(EN_CACHE_DIR, f"{key}.wav")

    def _normalize(self, text: str) -> str:
        from speech import fallback, speak
        text = speak(text)               # утасны дугаар, цаг (Oron буруу уншдаг)
        for strict in (True, False):
            try:
                return self.normalizer.normalize(text, strict=strict)
            except Exception:
                continue
        print(f"  [анхаар] тоог үгээр бичнэ үү (нөхцөлтэй тоо): {text}")
        return self.normalizer.normalize(fallback(text), strict=False)

    def _synth_mn_seed(self, text: str, seed: int):
        ref_file, ref_text = self.ref_file, self.ref_text
        if self.qref and text.rstrip().endswith("?"):
            ref_file, ref_text = self.qref          # асуултын өсөх аялгыг дуурайна
        wav, sr, _ = self.tts.infer(
            ref_file=ref_file,
            ref_text=ref_text,
            gen_text=self._normalize(text),
            nfe_step=TTS_NFE_STEP,
            cfg_strength=2.0,
            sway_sampling_coef=-1.0,
            speed=self.speed,
            seed=seed,
        )
        return np.asarray(wav, dtype=np.float32), sr

    def _synth_mn(self, text: str, seed: int = 0):
        """Урт текстийг өгүүлбэрээр хувааж тус бүрийг үүсгээд завсартай нийлүүлнэ: F5 урт текстийг өөрөө
        2+ batch болгоход MPS дээр "MTLCommandBufferStatusCommitted" assertion-оор унасан (~400 тэмдэгт).
        Асуулт ("?") тусдаа хэсэг болно -> асуултын аялга зөвхөн тэр өгүүлбэрт."""
        parts = split_long(text)
        if len(parts) == 1 and self.qref and "?" in text and not text.rstrip().endswith("?"):
            parts = [x for x in re.split(r"(?<=\?)\s+", text) if x]
        elif self.qref:
            parts = [y for x in parts for y in re.split(r"(?<=\?)\s+", x) if y]
        if len(parts) > 1:
            pieces, sr = [], 24000
            for k, part in enumerate(parts):
                wav, sr = self._synth_mn_one(part, seed)
                wav = trim_silence(wav, sr, start=k > 0, end=k < len(parts) - 1)
                pieces += [wav] + ([np.zeros(int(sr * self.pause), np.float32)] if k < len(parts) - 1 else [])
            return np.concatenate(pieces), sr
        return self._synth_mn_one(text, seed)

    def _synth_mn_one(self, text: str, seed: int = 0):
        """scorer байвал TTS_CANDIDATES seed-ээр үүсгэж, STT-ийн тэмдэгтийн алдаа хамгийн бага нь."""
        if not self.scorer or TTS_CANDIDATES <= 1:
            return self._synth_mn_seed(text, seed)
        from stt import cer
        best = None
        for seed in range(seed, seed + TTS_CANDIDATES):
            wav, sr = self._synth_mn_seed(text, seed)
            err = cer(text, self.scorer.transcribe(wav, sr))
            if best is None or err < best[0]:
                best = (err, wav, sr, seed)
            if err == 0:
                break
        print(f"    [best-of-{TTS_CANDIDATES}] seed {best[3]}, алдаа {best[0]:.0%}: {text[:40]}")
        return best[1], best[2]

    def _synth_en(self, text: str):
        cached = self.en_cache_path(text)
        if os.path.exists(cached):
            wav, sr = sf.read(cached, dtype="float32")
            return wav, sr
        if self.en_tts is None:
            from f5_tts.api import F5TTS
            self.en_tts = F5TTS(model="F5TTS_v1_Base", ckpt_file=self.en_ckpt)
            from f5_tts.infer.utils_infer import preprocess_ref_audio_text
            ref, _ = preprocess_ref_audio_text(self.ref_file, romanize(self.ref_text), show_info=lambda *a: None)
            self.en_ref_sec = sf.info(ref).duration
        # Ижил reference хоолой, текстийг нь латинаар -> хоолой ижил, байтын харьцаа зөв.
        # Богино товчлолд F5 хэт бага хугацаа олгодог тул хугацааг өөрсдөө тогтооно.
        gen, seconds = en_prepare(text)
        wav, sr, _ = self.en_tts.infer(
            ref_file=self.ref_file,
            ref_text=romanize(self.ref_text),
            gen_text=gen,
            fix_duration=self.en_ref_sec + seconds,
            nfe_step=EN_NFE_STEP,
            cfg_strength=2.0,
            sway_sampling_coef=-1.0,
            seed=0,
        )
        wav = np.asarray(wav, dtype=np.float32)
        os.makedirs(EN_CACHE_DIR, exist_ok=True)
        sf.write(cached, wav, sr)
        return wav, sr

    def synth(self, text: str, seed: int = 0):
        """text: эх бичвэр (дуудлагын толийг энд хэрэглэнэ). seed: "Дахин үүсгэх" дарахад нэмэгдэнэ.
        F5 цэг таслалгүй ганц үгийг ("долоо") чимээгүй үүсгэсэн -> богино бичвэрт цэг нэмнэ. Чимээгүй
        гарвал (оргил < 0.05) дараагийн seed-ээр дахин (утасны дугаар уншихад цифр алга болохоос сэргийлнэ)."""
        gen = spoken(text)
        if len(gen.split()) <= 2 and not re.search(r"[.!?…]\s*$", gen):
            gen = gen.rstrip() + "."
        try:
            for k in range(3):
                wav, sr = self._synth(gen, seed + k * 100)
                if len(wav) and float(np.abs(wav).max()) >= 0.05:
                    break
                print(f"    [чимээгүй гарлаа, seed {seed + k * 100}] {text}")
            return wav, sr
        finally:
            # PyTorch MPS кэшийг суллахгүй бол GPU-д түгжигдсэн санах ой ~6GB хүрч бүх зүйл swap-д орсон
            import torch
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()

    def _synth(self, text: str, seed: int = 0):
        if not (self.en_ckpt and re.search(r"[A-Za-z]", text)):
            wav, sr = self._synth_mn(text, seed)
            return finish_clip(wav, sr), sr
        parts, sr = [], 24000
        segs = split_language(text)
        for i, (seg, en) in enumerate(segs):
            wav, sr = self._synth_en(seg) if en else self._synth_mn(seg, seed)
            # Өгүүлбэрийн хамгийн эхэн, төгсгөлийг тайрахгүй (эхний авиа тасрахаас сэргийлнэ)
            parts.append(trim_silence(wav, sr, start=i > 0, end=i < len(segs) - 1))
        if EN_UNLOAD and self.en_tts is not None:
            import gc
            self.en_tts = None
            gc.collect()
        return finish_clip(join_segments(parts, segs, sr), sr), sr

    def warmup(self):
        self.synth("Сайн байна уу.")


def hold_tone(sr: int = 24000) -> np.ndarray:
    """Hold хэллэгүүдийн хооронд тоглох намуухан хоёр нотын аялгуу (~1.6с)."""
    def note(freq, dur):
        t = np.arange(int(sr * dur)) / sr
        env = np.minimum(1, t / 0.02) * np.exp(-t * 4)
        return 0.08 * env * np.sin(2 * np.pi * freq * t)
    gap = np.zeros(int(sr * 0.25))
    return np.concatenate([note(660, 0.5), gap, note(880, 0.5), gap]).astype(np.float32)


# ---------------- FAQ + RAG router ----------------

class FAQRouter:
    def __init__(self, index_dir: str | None = None, kb_dir: str | None = None, embedder=None):
        """Нэг байгууллагын индекс (default: TENANT). embedder: олон байгууллага нэг загварыг хуваалцана."""
        import tenant
        from embed import Embedder

        t = tenant.current()
        self.index_dir, self.kb_dir = index_dir or t.faq_index_dir, kb_dir or t.kb_index_dir
        self.embedder = embedder
        self._load()
        self.embedder = embedder or Embedder(self.meta["embed_model"])

    def _stamp(self):
        paths = [os.path.join(self.index_dir, "faq_index.json"), self._config_path(),
                 os.path.join(self.kb_dir, "facts.json"), os.path.join(self.kb_dir, "chunks.json"),
                 os.path.join(self.kb_dir, "selector.json")]
        return tuple(os.path.getmtime(p) if os.path.exists(p) else 0 for p in paths)

    def reload_if_changed(self) -> bool:
        """Веб/скриптээр аудио дахин бэлдсэн бол AI серверийг унтраалгүйгээр шинэ өгөгдлийг ачаална
        (embedding моделийг дахин ачаалахгүй)."""
        if self._stamp() == self.stamp:
            return False
        fresh = object.__new__(FAQRouter)      # бүрэн ачаалагдсан үед л солино (алдаа гарвал хуучин хэвээр)
        fresh.index_dir, fresh.kb_dir, fresh.embedder = self.index_dir, self.kb_dir, self.embedder
        fresh._load()
        self.__dict__.update(fresh.__dict__)
        return True

    def _config_path(self) -> str:
        return os.path.join(os.path.dirname(os.path.abspath(self.index_dir)), "config.json")

    def _load_stt_fixes(self):
        """Яриа таних байнгын алдааны засвар (байгууллагын config.json "stt_fixes": [{"heard": regex, "fix": "..."}]).
        Бодит дуудлага 10-06: "зээл"->"дээл", "Bootcamp хөтөлбөр"->"бүдгээ бүтэлбэр", "Pinecone"->"понь кон"."""
        self.stt_fixes = []
        try:
            with open(self._config_path(), encoding="utf-8") as f:
                items = json.load(f).get("stt_fixes", [])
        except (OSError, ValueError):
            items = []
        for x in items:
            try:   # үгийн эхнээс (өмнө нь үсэг биш) таарна: "дээл" -> "зээл", "дээлийн" -> "зээлийн"
                self.stt_fixes.append((re.compile(r"(?<![а-яөүёa-z])(?:" + x["heard"] + ")", re.I), x["fix"]))
            except (re.error, KeyError):
                print(f"  [анхаар] буруу stt_fixes: {x}")

    def fix_stt(self, text: str) -> str:
        for pattern, fix in self.stt_fixes:
            text = pattern.sub(fix, text)
        return text

    def _load(self):
        index_dir, kb_dir = self.index_dir, self.kb_dir
        self.stamp = self._stamp()
        self._load_stt_fixes()
        with open(os.path.join(index_dir, "faq_index.json"), encoding="utf-8") as f:
            self.meta = json.load(f)
        self.emb = np.load(os.path.join(index_dir, "faq_index.npz"))["emb"]

        # RAG индекс (scripts/ingest.py) - байхгүй бол бүх тодорхойгүй асуулт -> ажилтан
        self.kb_chunks, self.kb_emb = [], np.zeros((0, self.emb.shape[1]), np.float32)
        kb_json = os.path.join(kb_dir, "chunks.json")
        if os.path.exists(kb_json):
            with open(kb_json, encoding="utf-8") as f:
                kb = json.load(f)
            if kb["embed_model"] != self.meta["embed_model"]:
                raise RuntimeError("knowledge_index болон faq_audio өөр embedding модельтой. "
                                   "Хоёуланг нь дахин үүсгэнэ үү.")
            self.kb_chunks = kb["chunks"]
            self.kb_emb = np.load(os.path.join(kb_dir, "index.npz"))["emb"]

        # Урьдчилсан аудиотой өгүүлбэрүүд (аудиогүйг нь алгасна)
        self.facts, self.fact_emb = [], np.zeros((0, self.emb.shape[1]), np.float32)
        self.fact_stems: list[set[str]] = []
        facts_json = os.path.join(kb_dir, "facts.json")
        if os.path.exists(facts_json):
            with open(facts_json, encoding="utf-8") as f:
                fj = json.load(f)
            if fj["embed_model"] != self.meta["embed_model"]:
                raise RuntimeError("knowledge_index болон faq_audio өөр embedding модельтой. "
                                   "Хоёуланг нь дахин үүсгэнэ үү.")
            emb = np.load(os.path.join(kb_dir, "facts.npz"))["emb"]
            keep = [i for i, x in enumerate(fj["facts"])
                    if x.get("audio") and os.path.exists(x["audio"])]
            self.facts = [fj["facts"][i] for i in keep]
            self.fact_stems = [lex_stems(f["text"]) for f in self.facts]
            if keep:
                self.fact_emb = emb[keep]

        # Бүх аудиог санах ойд ачаална -> тоглуулахад 0 хүлээлт
        self.audio = {}
        for path in self.meta["all_audio"]:
            wav, sr = sf.read(path, dtype="float32")
            self.audio[path] = (wav, sr)
        for fact in self.facts:
            self.audio[fact["audio"]] = sf.read(fact["audio"], dtype="float32")
        self.tone = hold_tone()
        self._last_hold = getattr(self, "_last_hold", None)
        # Байгууллагын тодруулах сэдэв, ерөнхий үгс (build_faq_audio.py config-оос). Хуучин индекст алга.
        opts = self.meta.get("clarify_options")
        self.clarify_options = ([(set(o["keys"]), o["question"]) for o in opts] if opts is not None
                                else CLARIFY_OPTIONS)
        self.generic_stems = set(self.meta.get("generic_stems") or GENERIC_STEMS)

        # Сургасан сонгогч (scripts/train_selector.py) - байхгүй/эвдэрсэн бол зөвхөн дүрмээр
        self.selector, self.sel_answers, self.sel_label_stems = None, {}, {}
        if SELECTOR and os.path.exists(os.path.join(kb_dir, "selector.json")):
            try:
                self.attach_selector(Selector(kb_dir))
            except Exception as e:
                print(f"  [сонгогч] ачаалж чадсангүй: {e}")

    def attach_selector(self, sel: "Selector"):
        """Сонгогчийн шошго бүрийг тоглуулах аудиотой холбоно. Мэдээлэл өөрчлөгдөж өгүүлбэр нь
        алга болсон шошгыг алгасна (тэр үед дүрмээр шийднэ)."""
        if sel.meta.get("embed_model") != self.meta["embed_model"]:
            print("  [сонгогч] өөр embedding модельтой -> дахин сургана уу")
            return
        faqs = {f["id"]: f for f in self.meta["faq"]}
        facts = {normalize(f["text"]): f for f in self.facts}
        resolved = {}
        for label, spec in sel.answers.items():
            if spec["kind"] == "faq" and spec["id"] in faqs:
                resolved[label] = ("faq", faqs[spec["id"]])
            elif spec["kind"] == "facts":
                items = [facts.get(normalize(t)) for t in spec["texts"]]
                if None not in items:
                    resolved[label] = ("facts", items)
            elif spec["kind"] in ("other", "clarify"):
                resolved[label] = (spec["kind"], None)
        self.selector, self.sel_answers = sel, resolved
        self.sel_label_stems = {k: set(v) for k, v in sel.meta.get("label_stems", {}).items()}

    def fact_supported(self, text: str, v: np.ndarray, facts: list, label: str | None = None) -> bool:
        """Асуулт тэдгээр өгүүлбэртэй эсвэл тухайн хариултын сургалтын асуултуудтай үг, утгаараа холбоотой юу
        (сонгогчийн хуурамч итгэлээс хамгаална). Сургалтын асуулт: "ивент" гэх мэт мэдээлэлд байхгүй ижил утгатай үг."""
        idx = [i for i, f in enumerate(self.facts) if any(f is x for x in facts)]
        if not idx:
            return False
        q = lex_stems(text) - self.generic_stems
        if label and q & self.sel_label_stems.get(label, set()):
            return True
        lex = max(len(q & self.fact_stems[i]) for i in idx)
        return lex >= 1 or float(max(self.fact_emb[idx] @ v)) >= SEL_FACT_SIM

    def select(self, text: str, v: np.ndarray):
        """-> (label, (kind, item) | None, магадлал) эсвэл None (сонгогчгүй/идэвхгүй)."""
        if not self.selector or not self.selector.enabled:
            return None
        (label, p), *_ = self.selector.predict(text, v)
        return label, self.sel_answers.get(label), p

    def clip(self, item):
        return self.audio[item["audio"]]

    def filler(self):
        return random.choice(self.meta["fillers"])

    def hold(self):
        options = [h for h in self.meta["holds"] if h["audio"] != self._last_hold]
        h = random.choice(options or self.meta["holds"])
        self._last_hold = h["audio"]
        return h

    def error(self):
        return self.meta["error"]

    def repeat(self):
        return self.meta.get("repeat")

    def clarify(self):
        return self.meta.get("clarify")

    @staticmethod
    def expand_query(text: str, prev_user: str | None) -> str:
        """'Төлбөр нь хэд вэ?' гэх мэт үргэлжлэл асуултад өмнөх асуултыг нэмнэ."""
        words = set(re.findall(r"\w+", text.lower()))
        if prev_user and (words & FOLLOWUP_WORDS) and len(text) < 40:
            return f"{prev_user} {text}"
        return text

    def route(self, text: str, prev_user: str | None = None):
        """Буцаах: (kind, item, score, query_vec). kind = faq | topic | unknown"""
        # Хэд хэдэн хувилбараар хайж хамгийн тод таарсныг сонгоно:
        #  - дангаар нь
        #  - өмнөх асуулттай нийлүүлсэн ("Төлбөр нь хэд вэ?"). "Үнэ нь хэд вэ?" бие даасан ч "нь" агуулдаг.
        #  - урт өгүүлбэрийн сүүл ("...зээл болсон, за яахав, хөтөлбөр хэдэн сар байдаг вэ")
        variants = [text]
        expanded = self.expand_query(text, prev_user)
        if expanded != text:
            variants.append(expanded)
        words = text.split()
        if len(words) > LONG_WORDS:
            variants.append(" ".join(words[-TAIL_WORDS:]))
        vecs = self.embedder.query(variants)
        if len(variants) == 1:
            v, self.last_query = vecs[0], text
        else:
            pool = np.vstack([self.emb, self.fact_emb]) if len(self.fact_emb) else self.emb
            best = [float((pool @ vec).max()) if len(pool) else 0.0 for vec in vecs]
            i = int(np.argmax(best))
            v, self.last_query = vecs[i], (variants[i] if variants[i] != expanded else text)
        if len(self.emb) == 0:
            return "unknown", None, 0.0, v

        scores = self.emb @ v
        best = int(np.argmax(scores))
        score = float(scores[best])

        faq_idx = self.meta["row_to_faq"][best]
        if faq_idx >= 0:
            faq = self.meta["faq"][faq_idx]
            if score >= FAQ_MATCH and self.faq_intent_supported(self.last_query, faq_idx):
                return "faq", faq, score, v
            topic = faq.get("topic")
        else:
            topic = self.meta["row_topic"][best]

        if score >= TOPIC_MATCH and topic in self.meta["topics"]:
            return "topic", self.meta["topics"][topic], score, v
        return "unknown", None, score, v

    def faq_intent_supported(self, text: str, faq_idx: int) -> bool:
        """Цагийн хуваарь асуусныг сар/хоногийн үргэлжлэх хугацаатай FAQ руу бүү холбо."""
        if not CLOCK_TIME.search(text):
            return True
        rows = [question for question, index in zip(self.meta["questions"], self.meta["row_to_faq"])
                if index == faq_idx]
        faq = self.meta["faq"][faq_idx]
        return any(CLOCK_TIME.search(value) for value in [*rows, faq.get("answer", "")])

    def faq_candidates(self, v: np.ndarray, text: str = ""):
        """FAQ_MATCH-д хүрээгүй ч төстэй FAQ хариултууд: [(fact-маягийн dict, score), ...].
        STT бага зэрэг алдсан ("хэдэн сард сардаг") үед LLM зөв FAQ-г сонгох боломж олгоно."""
        if len(self.emb) == 0:
            return []
        scores = self.emb @ v
        best: dict[int, float] = {}
        for row, faq_idx in enumerate(self.meta["row_to_faq"]):
            if faq_idx >= 0 and scores[row] > best.get(faq_idx, -1):
                best[faq_idx] = float(scores[row])
        out = []
        for faq_idx, sc in best.items():
            if sc >= FAQ_CANDIDATE and self.faq_intent_supported(text, faq_idx):
                faq = self.meta["faq"][faq_idx]
                out.append(({"text": faq["answer"], "audio": faq["audio"], "faq": True, "id": faq["id"]}, sc))
        return out

    def fact_candidates(self, v: np.ndarray, text: str = "", k: int = FACT_CANDIDATES):
        """Асуулттай хамгийн төстэй, аудиотой өгүүлбэрүүд: [(fact, score), ...].
        score = embedding төстэй байдал + LEX_WEIGHT * (асуултын язгуурын хэд нь өгүүлбэрт байгаа)"""
        if not self.facts:
            return []
        scores = self.fact_emb @ v
        q = lex_stems(text)
        if q:
            scores = scores + LEX_WEIGHT * np.array([len(q & st) / len(q) for st in self.fact_stems])
        top = np.argsort(-scores)[:k]
        return [(self.facts[i], float(scores[i])) for i in top if scores[i] >= FACT_MIN]

    def retrieve(self, v: np.ndarray, k: int = RAG_TOP_K):
        """knowledge_index-ээс хамгийн төстэй k хэсэг: [(text, score), ...]"""
        if len(self.kb_chunks) == 0:
            return []
        scores = self.kb_emb @ v
        top = np.argsort(-scores)[:k]
        return [(self.kb_chunks[i]["text"], float(scores[i])) for i in top]


# ---------------- LLM: өгүүлбэр сонгох ----------------

SELECT_PROMPT = (
    "You decide which numbered statements answer a caller's question for a school receptionist. "
    "Reply ONLY with the numbers of the statements that directly answer the question, "
    f"separated by commas (at most {FACT_MAX}). "
    "If none of the statements answers the question, reply 0. No other text."
)


async def select_facts(question: str, candidates) -> list:
    """LLM зөвхөн дугаар сонгоно (шинэ текст бичихгүй) -> мэдээлэл зохиох боломжгүй, ~1с."""
    listing = "\n".join(f"{i}. {f['text']}" for i, (f, _) in enumerate(candidates, 1))
    payload = {
        "model": SELECT_MODEL, "stream": False, "think": False, "keep_alive": -1,
        "options": {"temperature": 0, "num_predict": 8},
        "messages": [{"role": "system", "content": SELECT_PROMPT},
                     {"role": "user",
                      "content": f"Question: {question}\nStatements:\n{listing}\nAnswer:"}],
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
            r.raise_for_status()
            out = r.json()["message"]["content"]
    except (httpx.HTTPError, KeyError, ValueError) as e:
        print(f"  [LLM сонголт алдаа] {e}")
        return []
    picks = []
    for n in re.findall(r"\d+", out):
        i = int(n)
        if 1 <= i <= len(candidates) and candidates[i - 1][0] not in picks:
            picks.append(candidates[i - 1][0])
    return picks[:FACT_MAX]


async def wait_with_holds(task, router, play_fn, first_clip):
    """task дуустал first_clip-ийг, дараа нь hold хэллэг/аялгууг ээлжлэн тоглуулна."""
    await play_fn(*router.clip(first_clip))
    holds = 0
    while not task.done():
        try:
            await asyncio.wait_for(asyncio.shield(task), HOLD_AFTER)
        except asyncio.TimeoutError:
            holds += 1
            if holds % 2 == 0:
                await play_fn(router.tone, 24000)
            else:
                await play_fn(*router.clip(router.hold()))
    return task.result()


# ---------------- LLM stream ----------------

async def llm_tokens(messages):
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": True,
        "think": False,
        "keep_alive": -1,
        "options": {"num_predict": LLM_MAX_TOKENS, "temperature": 0.2},
    }
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line:
                    continue
                data = json.loads(line)
                token = data.get("message", {}).get("content", "")
                if token:
                    yield token
                if data.get("done"):
                    break


# ---------------- Chunker ----------------

def _find_cut(buf: str, first: bool):
    min_len = FIRST_CHUNK_MIN if first else CHUNK_MIN
    for m in HARD_END.finditer(buf):
        if m.end() >= min_len:
            return m.end()
    if first:
        for m in SOFT_END.finditer(buf):
            if m.end() >= min_len:
                return m.end()
    if len(buf) >= CHUNK_MAX:
        cut = buf.rfind(" ", 0, CHUNK_MAX)
        return cut if cut > min_len else CHUNK_MAX
    return None


def _clean(text: str) -> str:
    """TTS-д уншигдахгүй тэмдэгт (emoji, markdown) хасна."""
    text = re.sub(r"[*_#`>\[\]]", "", text)
    return re.sub(r"[^\w\s.,!?…:;'\"()%-]", "", text).strip()


async def chunker(tokens, text_q: asyncio.Queue, transcript: list):
    buf = ""
    first = True
    try:
        async for tok in tokens:
            transcript.append(tok)
            buf += tok
            while True:
                cut = _find_cut(buf, first)
                if cut is None:
                    break
                piece, buf = _clean(buf[:cut]), buf[cut:]
                if piece:
                    await text_q.put(piece)
                    first = False
        if _clean(buf):
            await text_q.put(_clean(buf))
    except httpx.HTTPError as e:
        print(f"  [LLM алдаа] {e}")
        await text_q.put(("__error__",))
    await text_q.put(None)


# ---------------- TTS worker ----------------

async def tts_worker(text_q, audio_q, engine: OronTTS, router: FAQRouter,
                     executor, t0):
    loop = asyncio.get_running_loop()
    errored = False
    while True:
        text = await text_q.get()
        if text is None:
            await audio_q.put(None)
            return
        if errored:
            continue
        if isinstance(text, tuple) or "олж чадсангүй" in text:
            # LLM алдаа эсвэл "олж чадсангүй" -> бэлэн аудио, үлдсэн текстийг алгасна
            errored = True
            await audio_q.put(("answer", *router.clip(router.error())))
            continue
        wav, sr = await loop.run_in_executor(executor, engine.synth, text)
        print(f"  [TTS {time.perf_counter() - t0:.2f}s] {text}")
        await audio_q.put(("answer", wav, sr))


# ---------------- Player (чимээгүй хамгаалалттай) ----------------

async def play(wav, sr):
    sd.play(wav, sr)
    await asyncio.to_thread(sd.wait)


async def player(audio_q, t0, router: FAQRouter | None = None, play_fn=play,
                 stream_answer: bool = STREAM_ANSWER):
    """
    Дарааллаас аудио авч тоглуулна.
    Хариу тоглож эхлэхээс өмнө HOLD_AFTER секунд чимээгүй болбол hold хэллэг,
    hold аялгууг ээлжлэн тоглуулна.
    stream_answer=False үед хариуны хэсгүүдийг бүгдийг нь цуглуулж байгаад
    (hold тоглуулсаар) эцэст нь завсаргүй тоглуулна.
    """
    answer_started = False
    pending = []
    holds_used = 0
    while True:
        can_hold = router is not None and not answer_started and holds_used < MAX_HOLDS
        try:
            item = await asyncio.wait_for(audio_q.get(),
                                          HOLD_AFTER if can_hold else None)
        except asyncio.TimeoutError:
            holds_used += 1
            if holds_used % 2 == 0:
                await play_fn(router.tone, 24000)
            else:
                h = router.hold()
                print(f"  [hold {time.perf_counter() - t0:.2f}s] {h['text']}")
                await play_fn(*router.clip(h))
            continue

        if item is None:
            if pending:
                print(f"  >>> Хариу эхэлсэн: {time.perf_counter() - t0:.2f}s")
                await play_fn(np.concatenate([w for w, _ in pending]), pending[0][1])
            return
        kind, wav, sr = item
        if kind == "filler":
            await play_fn(wav, sr)
            continue
        if not stream_answer:
            if pending and sr != pending[0][1]:   # sr өөр бол нийлүүлж болохгүй
                for w, s in pending:
                    await play_fn(w, s)
                pending.clear()
            pending.append((wav, sr))
            continue
        if not answer_started:
            answer_started = True
            print(f"  >>> Хариу эхэлсэн: {time.perf_counter() - t0:.2f}s")
        await play_fn(wav, sr)


# ---------------- Нэг ээлжийн хариу ----------------

async def respond(user_text, history, router: FAQRouter, engine: OronTTS,
                  executor, play_fn=play, meta: dict | None = None) -> str:
    """play_fn(wav, sr): чанга яригч (default) эсвэл утасны AudioSocket.
    meta: хариултын замыг (route, score) бичнэ -> дуудлагын лог, веб."""
    t0 = time.perf_counter()
    meta = meta if meta is not None else {}

    def note(route: str, score: float | None = None):
        meta["route"], meta["score"] = route, score
    prev_user = next((m["content"] for m in reversed(history)
                      if m["role"] == "user"), None)
    fixed = router.fix_stt(user_text) if hasattr(router, "fix_stt") else user_text
    if fixed != user_text:
        print(f"  [STT засвар] {user_text!r} -> {fixed!r}")
        user_text = meta["stt_fixed"] = fixed

    clarify_text = router.clarify()["text"] if router.clarify() else CLARIFY_PHRASE
    repeat_text = router.repeat()["text"] if router.repeat() else REPEAT_PHRASE
    error_text = router.error()["text"]
    last_ai = next((m["content"] for m in reversed(history) if m["role"] == "assistant"), None)
    if last_ai == clarify_text:
        stems = lex_stems(user_text)
        hits = [q for keys, q in router.clarify_options
                if any(st.startswith(k) or k.startswith(st) for st in stems for k in keys)]
        if len(hits) == 1:
            print(f"  [тодруулга] {user_text!r} -> {hits[0]!r}")
            user_text = hits[0]

    kind, item, score, v = await asyncio.to_thread(router.route, user_text, prev_user)
    query = getattr(router, "last_query", user_text)   # урт өгүүлбэрт сүүл хэсэг нь сонгогдож болно
    print(f"  [route {time.perf_counter() - t0:.2f}s] {kind} ({score:.2f})")

    async def play_now(clip):
        await play_fn(*router.clip(clip))

    # "Сургалтын/bootcamp-ийн талаар мэдээлэл авъя" -> тодруулна. FAQ-ийн өмнө: үгүй бол
    # "Bootcamp-д орох гэсэн юм" (бүртгэл) гэх мэт FAQ-тай андуурна. Маш тод FAQ (>=0.92) бол FAQ.
    # Ерөнхий үг (сургалт, мэдээлэл, талаар) л байвал тодруулна. Ийм үг огт байхгүй ("байна уу",
    # "а а а") бол тодруулахгүй — мэндчилгээ/дахин асуухыг доорх алхмууд шийднэ (бодит дуудлага 10-05).
    raw = {w[:4] for w in re.findall(r"[а-яөүёa-z]+", query.lower()) if len(w) >= 3}
    asks_generic = bool(raw & (router.generic_stems | INFO_STEMS))
    if router.clarify() and asks_generic and not (lex_stems(query) - router.generic_stems) and score < 0.92:
        note("clarify", score)
        await play_now(router.clarify())
        return clarify_text

    # 0. Сургасан сонгогч: итгэлтэй бол шууд. "Мэдээлэлд алга" гэж итгэлтэй бол төстэй ч буруу
    #    хариулт ("хэдэн цагт эхэлдэг" -> хугацаа) тоглуулахгүй, дахин асууна.
    skip_rules = False
    sel = router.select(query, v)
    if sel:
        label, answer, p = sel
        print(f"  [сонгогч] {label} {p:.2f}")
        supported = not (answer and answer[0] == "facts") or router.fact_supported(query, v, answer[1], label)
        if not supported:
            print("  [сонгогч] асуулттай холбоогүй өгүүлбэр -> дүрмээр шийднэ")
        if answer and p >= SEL_MIN and answer[0] in ("faq", "facts") and supported:
            note("model", p)
            if answer[0] == "faq":
                meta["faq_id"] = answer[1].get("id")
                await play_now(answer[1])
                return answer[1]["answer"]
            for fact in answer[1]:
                await play_now(fact)
            return " ".join(fact["text"] for fact in answer[1])
        if answer and answer[0] == "clarify" and p >= SEL_MIN and router.clarify():
            note("clarify", p)
            await play_now(router.clarify())
            return clarify_text
        skip_rules = label == "other" and p >= OTHER_MIN

    # 1. Бэлэн хариу -> шууд тоглуулна
    if kind == "faq" and not skip_rules:
        note("faq", score)
        meta["faq_id"] = item.get("id")
        await play_now(item)
        return item["answer"]

    # 2. RAG мэдээллийн урьдчилсан аудиотой өгүүлбэр (TTS ажиллахгүй)
    cands = [] if skip_rules else router.fact_candidates(v, query)
    if cands:
        print("  [facts] " + " | ".join(f"{sc:.2f} {f['text'][:28]}" for f, sc in cands))
    faqs = [] if skip_rules else sorted(router.faq_candidates(v, query), key=lambda x: -x[1])
    top = cands[0][1] if cands else 0.0
    margin = top - (cands[1][1] if len(cands) > 1 else 0.0)
    picks = []
    if cands and top >= FACT_DIRECT and margin >= FACT_MARGIN:
        picks = [cands[0][0]]
        note("fact", top)
    elif (len(cands) > 1 and cands[1][1] >= FACT_DIRECT and top >= FACT_DIRECT
          and (len(cands) < 3 or cands[1][1] - cands[2][1] >= TOP2_GAP or top >= TOP2_STRONG)):
        # Хоёр өгүүлбэр хоёулаа өндөр бөгөөд ойролцоо -> хоёуланг нь ("хуваан төлөх" + "нэмэгдэх дүн")
        picks = [cands[0][0], cands[1][0]]
        note("fact2", top)
    elif faqs and faqs[0][1] >= FAQ_NEAR:
        picks = [faqs[0][0]]
        note("faq_near", faqs[0][1])
        meta["faq_id"] = faqs[0][0].get("id")
    elif cands and top >= FACT_OK and margin >= FACT_OK_MARGIN:
        picks = [cands[0][0]]
        note("fact", top)
    elif (len(cands) >= 3 and top >= FACT_DIRECT - 0.08 and router.clarify()
          and top - cands[-1][1] < FLAT_SPREAD):
        # "Сургалтын талаар мэдээлэл" гэх мэт ерөнхий асуулт: олон өгүүлбэр ижил оноотой
        note("clarify", top)
        await play_now(router.clarify())
        return clarify_text
    elif SELECT_LLM:
        # Эргэлзээтэй -> өгүүлбэрүүд + ойролцоо FAQ хариултуудаас LLM сонгоно
        pool = sorted(cands + faqs, key=lambda x: -x[1])
        seen, merged = set(), []
        for fact, sc in pool:
            if fact["text"] not in seen:
                seen.add(fact["text"])
                merged.append((fact, sc))
        cands = merged[:FACT_CANDIDATES]
    if not picks and cands and SELECT_LLM:
        # filler тоглуулж байх зуур LLM аль нь хариулт болохыг дугаараар сонгоно
        task = asyncio.create_task(select_facts(router.expand_query(user_text, prev_user), cands))
        bridge = item if kind == "topic" else router.filler()
        try:
            picks = await wait_with_holds(task, router, play_fn, bridge)
        finally:
            task.cancel()
        print(f"  [LLM сонголт {time.perf_counter() - t0:.2f}s] {len(picks)} өгүүлбэр")
        note("llm", top)
    if picks:
        for fact in picks:
            await play_now(fact)
        return " ".join(fact["text"] for fact in picks)

    # Ойлгосонгүй: эхний удаа дахин асууна (STT алдах нь элбэг), дараалан 2 дахь бол ажилтан
    last_ai = next((m["content"] for m in reversed(history) if m["role"] == "assistant"), None)
    if router.repeat() and last_ai != repeat_text:
        note("repeat", top)
        await play_now(router.repeat())
        return repeat_text

    if not LLM_GENERATE or engine is None:
        note("handoff", top)
        await play_now(router.error())
        return error_text

    # 3. (LLM_GENERATE=1) RAG хэсгүүдээр LLM шинэ хариулт бичиж, TTS хийнэ. Удаан.
    context = router.retrieve(v)
    best = context[0][1] if context else 0.0
    print(f"  [RAG] best={best:.2f} " + " | ".join(f"{s:.2f}" for _, s in context))
    if best < RAG_MATCH:
        note("handoff", best)
        await play_now(router.error())
        return error_text
    note("generate", best)

    # Bridge эсвэл filler-ийг ШУУД тоглуулж, ард нь хариу бэлдэнэ
    audio_q: asyncio.Queue = asyncio.Queue()
    bridge = item if kind == "topic" else router.filler()
    await audio_q.put(("filler", *router.clip(bridge)))

    info = "\n\n".join(text for text, s in context if s >= RAG_MATCH)
    system = (SYSTEM_PROMPT +
              f"\n\nМЭДЭЭЛЭЛ:\n{info}\n\n"
              f"Та дөнгөж '{bridge['text']}' гэж хэлсэн. "
              "Мэндчилгээ, давталтгүйгээр шууд хариултаа хэл.")
    messages = ([{"role": "system", "content": system}] + history[-6:] +
                [{"role": "user", "content": user_text}])

    text_q: asyncio.Queue = asyncio.Queue()
    transcript: list = []
    tasks = [
        asyncio.create_task(chunker(llm_tokens(messages), text_q, transcript)),
        asyncio.create_task(tts_worker(text_q, audio_q, engine, router, executor, t0)),
        asyncio.create_task(player(audio_q, t0, router, play_fn)),
    ]
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        for t in tasks:
            t.cancel()
        if play_fn is play:
            sd.stop()
        raise
    return "".join(transcript).strip()


# ---------------- Main (текстээр тест) ----------------

async def main():
    print("Ачаалж байна...")
    engine = OronTTS()
    engine.warmup()
    router = FAQRouter()
    executor = ThreadPoolExecutor(max_workers=1)

    await play(*router.clip(router.meta["greeting"]))
    print("Бэлэн. Асуултаа бичнэ үү (гарах: q)\n")

    history: list = []
    while True:
        q = await asyncio.to_thread(input, "Та: ")
        if q.strip().lower() in {"q", "quit", "exit"}:
            break
        reply = await respond(q, history, router, engine, executor)
        print(f"AI: {reply}\n")
        history += [{"role": "user", "content": q},
                    {"role": "assistant", "content": reply}]


if __name__ == "__main__":
    asyncio.run(main())
