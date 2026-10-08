"""
Англи горимын бэлдэлт (config.json "languages"-д "en" байвал): english.json-ийн орчуулга, англи хэллэгийг
урьдчилан аудио болгож (F5 base + англи лавлах хоолой), хайлтын индекс үүсгэнэ. Идэвхгүй бол индексийг устгана.

  TENANT=pinecone .venv/bin/python scripts/build_en.py
  -> tenants/<slug>/knowledge_index/english.json + english.npz, аудио data/en_cache/full_*.wav (нийтлэг кэш)

Англи хоолой: voices/en.wav + en.txt (зөвшөөрөлтэй хүний бичлэг) байвал түүнийг, үгүй бол F5-ийн жишээ хоолой.
"""
import gc
import hashlib
import json
import os
import re
import sys

import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import offline  # noqa: E402,F401
import english  # noqa: E402
import tenant as tenants  # noqa: E402

T = tenants.current()
OUT_JSON = os.path.join(T.kb_index_dir, "english.json")
OUT_NPZ = os.path.join(T.kb_index_dir, "english.npz")
CACHE = os.path.join(ROOT, "data", "en_cache")
EN_SPEED = float(os.getenv("EN_SPEED", "0.9"))      # утсаар арай удаан нь ойлгомжтой
EN_NFE = int(os.getenv("EN_NFE_STEP", "32"))
F5_REF_TEXT = "Some call me nature, others call me mother nature."

def ref_voice() -> tuple[str, str]:
    custom = os.path.join(ROOT, "voices", "en.wav")
    if os.path.exists(custom) and os.path.exists(custom[:-4] + ".txt"):
        with open(custom[:-4] + ".txt", encoding="utf-8") as f:
            return custom, f.read().strip()
    import f5_tts
    return os.path.join(f5_tts.__path__[0], "infer", "examples", "basic", "basic_ref_en.wav"), F5_REF_TEXT


REF_FILE, REF_TEXT = ref_voice()
with open(REF_FILE, "rb") as _f:
    VOICE = hashlib.sha1(_f.read() + REF_TEXT.encode()).hexdigest()[:8]
# F5 урт текстийг өөрөө 2+ batch болгоход MPS "command encoder is already encoding" assertion-оор унасан
# (монголтой адил) -> F5-ийн batch хязгаараас (лавлах бичлэгийн урт, хурдаас хамаарна) 15% бага хэсгүүдээр
_REF_SEC = sf.info(REF_FILE).duration
MAX_CHARS = int(0.85 * len(REF_TEXT.encode()) / _REF_SEC * (22 - _REF_SEC) * EN_SPEED)


def cache_path(text: str) -> str:
    key = hashlib.sha1(f"{text}|{VOICE}|{EN_NFE}|{EN_SPEED}|full1".encode()).hexdigest()[:16]
    return os.path.join(CACHE, f"full_{key}.wav")


def chunks(text: str) -> list[str]:
    """Өгүүлбэрээр бүлэглэнэ. Нэг өгүүлбэр хэт урт бол таслалаар."""
    out = []
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    sents = [p for x in sents for p in ([x] if len(x) <= MAX_CHARS else re.split(r"(?<=,)\s+", x))]
    for sent in sents:
        if out and len(out[-1]) + len(sent) + 1 <= MAX_CHARS:
            out[-1] += " " + sent
        elif sent:
            out.append(sent)
    return out


class EnglishTTS:
    def __init__(self):
        from f5_tts.api import F5TTS
        from stream_voice import _en_checkpoint, _patch_torchaudio_load
        _patch_torchaudio_load()        # шинэ torchaudio ffmpeg dylib шаарддаг -> soundfile
        ckpt = _en_checkpoint()
        if not ckpt:
            raise SystemExit("F5 base (англи) загвар кэшэд алга: SWivid/F5-TTS F5TTS_v1_Base")
        self.tts = F5TTS(model="F5TTS_v1_Base", ckpt_file=ckpt)

    def synth(self, text: str):
        from stream_voice import finish_clip, trim_silence
        pieces, sr = [], 24000
        parts = chunks(english.speak_en(text))
        for k, part in enumerate(parts):
            wav, sr, _ = self.tts.infer(ref_file=REF_FILE, ref_text=REF_TEXT, gen_text=part, nfe_step=EN_NFE,
                                        cfg_strength=2.0, sway_sampling_coef=-1.0, speed=EN_SPEED, seed=0,
                                        show_info=lambda *a, **k: None)
            wav = trim_silence(np.asarray(wav, np.float32), sr, start=k > 0, end=k < len(parts) - 1)
            pieces += [wav] + ([np.zeros(int(sr * 0.3), np.float32)] if k < len(parts) - 1 else [])
        return finish_clip(np.concatenate(pieces), sr), sr


def main():
    if not english.enabled(T):
        for p in (OUT_JSON, OUT_NPZ):
            if os.path.exists(p):
                os.remove(p)
        print("Англи горим идэвхгүй (config.json \"languages\") -> алгаслаа")
        return
    os.makedirs(CACHE, exist_ok=True)
    items, ph = english.items(T), english.phrases(T)
    tts = None
    made = 0

    def clip(text: str) -> dict:
        nonlocal tts, made
        path = cache_path(text)
        if not os.path.exists(path):
            if tts is None:
                print("Англи TTS ачаалж байна...")
                tts = EnglishTTS()
            wav, sr = tts.synth(text)
            sf.write(path, wav, sr)
            made += 1
            print(f"  [шинэ] {text}")
        return {"text": text, "audio": path}

    print(f"Байгууллага: {T.slug} · англи хоолой {os.path.basename(REF_FILE)} ({VOICE})")
    phrases = {k: (clip(v) if isinstance(v, str) else [clip(x) for x in v]) for k, v in ph.items() if k != "lead"}
    phrases["lead"] = {k: clip(v) for k, v in ph["lead"].items()}
    digits = [clip(d) for d in english.EN_DIGITS]
    meta_items = []
    for x in items:
        meta_items.append({"kind": x["kind"], "id": x["id"], "hash": x["hash"], "mn": x["mn"],
                           "clip": clip(x["en"]) if x["en"] else None})
    if tts is not None:
        del tts
        gc.collect()
        try:
            import torch
            torch.mps.empty_cache()
        except Exception:
            pass

    from embed import Embedder
    embedder = Embedder()
    queries, passages = [], []        # (мөр, item index)
    for i, x in enumerate(items):
        queries += [(q, i) for q in x["questions_en"] + x["mn_questions"]]
        passages += [(t, i) for t in (x["en"], x["mn"]) if t]
    emb = []
    if queries:
        emb.append(embedder.query([q for q, _ in queries]))
    if passages:
        emb.append(embedder.passage([p for p, _ in passages]))
    emb = np.vstack(emb) if emb else np.zeros((0, 1024), np.float32)
    rows = [i for _, i in queries] + [i for _, i in passages]
    os.makedirs(T.kb_index_dir, exist_ok=True)
    np.savez(OUT_NPZ, emb=emb)
    meta = {"tenant": T.slug, "embed_model": embedder.model_name, "voice": VOICE, "phrases": phrases,
            "digits": digits, "items": meta_items, "rows": rows}
    with open(OUT_JSON + ".tmp", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    os.replace(OUT_JSON + ".tmp", OUT_JSON)
    done = sum(1 for x in meta_items if x["clip"])
    print(f"Дууслаа: орчуулгатай {done}/{len(meta_items)} хариулт, шинэ аудио {made}, хайлтын мөр {len(rows)}")
    if done < len(meta_items):
        print(f"  Орчуулаагүй {len(meta_items) - done}: англиар асуувал \"монголоор л байна\" гэж ажилтан руу шилжүүлнэ")


if __name__ == "__main__":
    main()
