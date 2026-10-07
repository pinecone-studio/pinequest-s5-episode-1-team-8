"""
Локал STT. Монгол fine-tune (bayartsogt/whisper-small-mn-8)-ийг Apple MLX руу хөрвүүлж ажиллуулна:
утасны аудио дээр ижил нарийвчлал (CER 19.3% vs 19.2%), ~4.4x хурдан (дундаж 0.47с vs 2.09с, max 1.0с vs 7.1с).

  .venv/bin/python scripts/convert_whisper_mlx.py   # нэг удаа -> models/whisper-small-mn-mlx/
  WHISPER_MODEL=bayartsogt/whisper-small-mn-8         # хуучин transformers (MPS) зам
  WHISPER_MODEL=mlx-community/whisper-large-v3-turbo  # ерөнхий загвар (монголд муу)
"""
import offline  # noqa: F401  (хамгийн эхэнд: HF загварыг зөвхөн локалаас)
import os
import re
import threading
import time

import numpy as np
from scipy.signal import resample_poly

HF_MN = "bayartsogt/whisper-small-mn-8"
MLX_MN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "whisper-small-mn-mlx")
# Хоёр хэлтэй горим: хэл таних + англи яриа (монгол fine-tune хэл таньж чадахгүй, англид муу)
MLX_MULTI = os.getenv("WHISPER_MULTI", "mlx-community/whisper-small-mlx")
EN_SHARE = float(os.getenv("EN_SHARE", "0.7"))     # P(en) / (P(en) + P(mn)) үүнээс их -> англи
# mlx_whisper санах ойд НЭГ л загвар барьдаг (ModelHolder) -> монгол, олон хэлтэйг ээлжлэн дуудахад
# дахин дахин ачаална. Загвар бүрийг өөрт нь барьж, дуудахын өмнө ModelHolder-т тавина.
_MLX_LOCK = threading.Lock()


def is_mlx(model: str) -> bool:
    return model.startswith("mlx-community/") or os.path.exists(os.path.join(model, "weights.safetensors"))


WHISPER_MODEL = os.getenv("WHISPER_MODEL") or (MLX_MN if is_mlx(MLX_MN) else HF_MN)
WHISPER_LANG = os.getenv("WHISPER_LANG", "mn")
# Whisper-т сэдвийн үгсийг санууллага болгон өгнө -> англи нэр томьёо зөв бичигдэнэ
INITIAL_PROMPT = os.getenv(
    "WHISPER_PROMPT",
    "Pinecone Academy, Software Engineer, bootcamp, AI, coding. Сайн байна уу.",
)


SPECIAL = re.compile(r"<\|[^|>]*\|>")
# Утасны дугаарт "тэг тэг тэг" (000) жинхэнэ байж болно -> тоон үг, цифрт хүрэхгүй
NUMBER_WORDS = {"тэг", "нэг", "хоёр", "гурав", "гурван", "дөрөв", "дөрвөн", "тав", "таван", "зургаа", "зургаан",
                "долоо", "долоон", "найм", "найман", "ес", "есөн", "арав", "арван", "хорь", "хорин", "гуч",
                "гучин", "дөч", "дөчин", "тавь", "тавин", "жар", "жаран", "дал", "далан", "ная", "наян", "ер",
                "ерэн", "зуу", "зуун", "мянга", "мянган"}


def clean(text: str) -> str:
    """Whisper-ийн гацалтыг цэвэрлэнэ (бодит дуудлага 10-05): <|mn|> мэт тусгай тэмдэгт,
    3+ удаа дараалан давтагдсан үг ("үлдээд үлдээд үлдээд" -> "үлдээд"), 4+ ижил үсэг ("аааа").
    Тоон үг, цифрт хүрэхгүй: утасны дугаарт "тэг тэг тэг" (000) жинхэнэ байж болно."""
    import itertools
    text = SPECIAL.sub(" ", text)
    text = re.sub(r"([^\W\d])\1{3,}", r"\1", text)                 # аааа -> а (0000 хэвээр)
    out: list[str] = []
    for w, group in itertools.groupby(text.split()):
        n = len(list(group))
        keep = n if (w.lower() in NUMBER_WORDS or w.isdigit() or n < 3) else 1
        out += [w] * keep
    return " ".join(out).strip()


def cer(ref: str, hyp: str) -> float:
    """Тэмдэгтийн алдааны хувь (Levenshtein / урт), цэг таслал, том жижиг үсгийг үл тооно."""
    norm = lambda t: re.sub(r"[^\w]", "", t.lower())  # noqa: E731
    a, b = norm(ref), norm(hyp)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] / max(len(a), 1)


class WhisperSTT:
    """MLX загвар (хөрвүүлсэн хавтас эсвэл mlx-community/*) -> mlx-whisper,
    бусад HF загвар -> transformers (MPS/CPU)."""

    def __init__(self, model: str = WHISPER_MODEL, device: str | None = None):
        """device="cpu": transformers замд GPU санах ойг эзлэхгүй (MLX-д хамаарахгүй)."""
        self.model = model
        self.use_mlx = is_mlx(model)
        self._lock = _MLX_LOCK if self.use_mlx else threading.Lock()   # MLX-ийг хоёр thread зэрэг дуудахгүй
        if self.use_mlx:
            import mlx.core as mx
            import mlx_whisper
            from mlx_whisper.load_models import load_model
            self._mlx = mlx_whisper
            self._model = load_model(model, dtype=mx.float16)
            # Санууллага (prompt) монгол fine-tune дээр нарийвчлалыг бага зэрэг бууруулсан (19.9% vs 19.3%)
            self.prompt = INITIAL_PROMPT if model.startswith("mlx-community/") else None
        else:
            import torch
            from transformers import pipeline
            device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
            self._pipe = pipeline("automatic-speech-recognition", model=model, device=device,
                                  torch_dtype=torch.float32 if device == "cpu" else torch.float16)

    def transcribe(self, audio: np.ndarray, sr: int, language: str = WHISPER_LANG) -> str:
        """audio: float32 mono [-1, 1]. Whisper 16kHz шаарддаг тул хөрвүүлнэ."""
        if sr != 16000:
            audio = resample_poly(audio, 16000, sr).astype(np.float32)
        if not self.use_mlx:
            out = self._pipe({"raw": audio, "sampling_rate": 16000},
                             generate_kwargs={"num_beams": 1})
            return out["text"].strip()
        with self._lock:
            from mlx_whisper.transcribe import ModelHolder
            ModelHolder.model, ModelHolder.model_path = self._model, self.model
            result = self._mlx.transcribe(
                audio,
                path_or_hf_repo=self.model,
                language=language,
                # монгол үгтэй санууллага англи таниулахад саад болно -> латин хэсгийг нь л
                initial_prompt=(re.sub(r"[^\x00-\x7f]+[^.]*\.?", "", self.prompt).strip() if language == "en"
                                else self.prompt) if self.prompt else None,
                condition_on_previous_text=False,
                # Давталтад гацвал (compression ratio > 2.4) өндөр temperature-ээр дахин таниулна.
                # Бодит дуудлагад "л л л ...", "үлдээд үлдээд ..." гарсан (10-05).
                temperature=(0.0, 0.2, 0.4),
            )
        return clean(result["text"])

    def language_probs(self, audio: np.ndarray, sr: int) -> dict[str, float]:
        """Олон хэлтэй загвар: эхний 30с-ээс хэл бүрийн магадлал (encoder + 1 токен, ~0.1с)."""
        import mlx.core as mx
        from mlx_whisper.audio import N_FRAMES, N_SAMPLES, log_mel_spectrogram, pad_or_trim
        if sr != 16000:
            audio = resample_poly(audio, 16000, sr).astype(np.float32)
        with self._lock:
            mel = log_mel_spectrogram(audio, n_mels=self._model.dims.n_mels, padding=N_SAMPLES)
            _, probs = self._model.detect_language(pad_or_trim(mel, N_FRAMES, axis=-2).astype(mx.float16))
        return probs

    def warmup(self):
        self.transcribe(np.zeros(16000, dtype=np.float32), 16000)


class BilingualSTT:
    """Монгол/англи: олон хэлтэй загвар хэлийг тодорхойлно. Англи -> олон хэлтэй загвар таниулна,
    монгол -> монгол fine-tune (англи үгтэй монгол яриа ч монгол гэж танигдана)."""

    def __init__(self, mn: WhisperSTT, multi: str = MLX_MULTI):
        self.mn = mn
        self.multi = WhisperSTT(multi)

    def detect(self, audio: np.ndarray, sr: int, prev: str = "mn") -> tuple[str, float]:
        """-> (хэл, P(en)/(P(en)+P(mn))). Өмнө нь англиар ярьж байсан бол босгыг бууруулна."""
        p = self.multi.language_probs(audio, sr)
        share = p.get("en", 0.0) / max(p.get("en", 0.0) + p.get("mn", 0.0), 1e-9)
        return ("en" if share >= (0.5 if prev == "en" else EN_SHARE) else "mn"), share

    def transcribe(self, audio: np.ndarray, sr: int, prev: str = "mn") -> tuple[str, str]:
        lang, _ = self.detect(audio, sr, prev)
        if lang == "en":
            return self.multi.transcribe(audio, sr, language="en"), "en"
        return self.mn.transcribe(audio, sr), "mn"

    def transcribe_as(self, audio: np.ndarray, sr: int, lang: str) -> str:
        """Хэл нь мэдэгдэж байгаа үед (бүртгэлийн нэр/дугаар) таних алгасна."""
        return self.multi.transcribe(audio, sr, language="en") if lang == "en" else self.mn.transcribe(audio, sr)

    def warmup(self):
        self.multi.warmup()


if __name__ == "__main__":
    # .venv/bin/python stt.py file.wav
    import sys
    import soundfile as sf

    wav, sr = sf.read(sys.argv[1], dtype="float32", always_2d=True)
    stt = WhisperSTT()
    t = time.perf_counter()
    stt.warmup()
    print(f"warmup {time.perf_counter() - t:.1f}s")
    t = time.perf_counter()
    text = stt.transcribe(wav.mean(axis=1), sr)
    print(f"{time.perf_counter() - t:.2f}s  ({len(wav) / sr:.1f}s аудио)")
    print(text)
