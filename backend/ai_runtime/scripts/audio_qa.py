"""
Аудио чанарын шалгалт: байгууллагын бэлдсэн клип бүрийг яриа танихаар (MLX Whisper) буцааж уншуулж,
буруу дуудагдсан, хэт хурдан/удаан, тасарсан, урт чимээгүйтэй клипийг тэмдэглэнэ. Вэбийн "Хоолой"
хуудас үүгээр "Шалгах шаардлагатай" клипүүдийг харуулж, "Дахин үүсгэх" / "Өөрөө бичих" санал болгоно.

  TENANT=<slug> .venv/bin/python scripts/audio_qa.py   # -> tenants/<slug>/knowledge_index/audio_qa.json

Англи горимын клипүүд (scripts/build_en.py) олон хэлтэй Whisper-ээр англиар шалгагдана ("english").

Монгол клип доторх англи хэсэг: монгол Whisper англи үгийг галигладаг -> англи хэсэг бүрийг
"дурын текст" гэж үзээд (галиглал нь торгуульгүй) монгол хэсгийн алдааг тооцно. Хурдыг зөвхөн бүрэн монгол
клипэд хэмжинэ (англи хэсгийн хугацааг найдвартай тооцох арга алга).
"""
import json
import os
import re
import sys
import time

import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import offline  # noqa: E402,F401
import english  # noqa: E402
import tenant as tenants  # noqa: E402
from recordings import text_hash  # noqa: E402
from stream_voice import spoken, split_language  # noqa: E402
from stt import cer  # noqa: E402

T = tenants.current()
MAX_CER = 0.3           # монгол хэсгийн тэмдэгтийн алдаа (STT өөрөө ~0.1 алддаг)
EN_MAX_CER = 0.35       # англи: оноосон нэр (Pinebaatars, Shunkhlai) STT-д алдаатай гардаг
CPS = (8.0, 19.0)       # секундэд монгол үсэг: Pinecone-ийн клипүүд 11-17
LONG_SILENCE = 1.2      # клипийн дунд
QA_FILE = os.path.join(T.kb_index_dir, "audio_qa.json")
PAD = 0.5               # богино клипэд Whisper үг зохиодог ("хоёр үнээр үнээр...") -> чимээгүйгээр жийргэнэ
WILD = None


def ref_tokens(text: str) -> list:
    """Монгол үсгүүд + англи хэсэг бүрийн оронд нэг WILD (дурын текст)."""
    out = []
    for seg, en in split_language(text):
        if en:
            if out[-1:] != [WILD]:
                out.append(WILD)
        else:
            out += re.findall(r"[а-яөүё0-9]", seg.lower())
    return out


def mn_cer(ref: str, hyp: str) -> float:
    """Монгол хэсгийн тэмдэгтийн алдаа. Англи хэсэг (WILD) hyp-ийн дурын хэсгийг үнэгүй залгина."""
    toks = ref_tokens(ref)
    h = re.findall(r"[а-яөүёa-z0-9]", hyp.lower())
    n = sum(t is not WILD for t in toks)
    if not n:
        return 0.0
    ar = np.arange(len(h) + 1)
    prev = ar.astype(float)                                    # hyp-ийн эхний j үсэг илүү
    for t in toks:
        if t is WILD:
            prev = np.minimum.accumulate(prev)
            continue
        sub = np.array([c != t for c in h], float)
        cur = prev + 1                                         # лавлах үсэг алга
        cur[1:] = np.minimum(cur[1:], prev[:-1] + sub)         # таарсан / солигдсон
        prev = np.minimum.accumulate(cur - ar) + ar            # hyp-д илүү үсэг
    return float(prev[-1]) / n


def silences(wav: np.ndarray, sr: int) -> tuple[float, float]:
    """(дуу бүхий хугацаа, клипийн дундах хамгийн урт чимээгүй) — 20мс цонхоор."""
    win = int(sr * 0.02)
    n = len(wav) // win
    if not n:
        return 0.0, 0.0
    loud = np.sqrt((wav[: n * win].reshape(n, win) ** 2).mean(axis=1)) > 0.01
    idx = np.flatnonzero(loud)
    if not len(idx):
        return 0.0, 0.0
    inner = loud[idx[0]: idx[-1] + 1]
    longest = run = 0
    for v in inner:
        run = 0 if v else run + 1
        longest = max(longest, run)
    return len(inner) * 0.02, longest * 0.02


def clips() -> list[dict]:
    meta = json.load(open(os.path.join(T.faq_index_dir, "faq_index.json"), encoding="utf-8"))
    out = [dict(meta[k], kind=k) for k in ("greeting", "error", "repeat", "clarify")]
    out += [dict(c, kind="hold") for c in meta["holds"]] + [dict(c, kind="filler") for c in meta["fillers"]]
    out += [dict(c, kind="бүртгэл") for c in meta["lead"].values()] + [dict(c, kind="цифр") for c in meta["digits"]]
    out += [{"text": f["answer"], "audio": f["audio"], "kind": f"FAQ {f['id']}"} for f in meta["faq"]]
    facts = json.load(open(os.path.join(T.kb_index_dir, "facts.json"), encoding="utf-8"))["facts"]
    out += [{"text": f["text"], "audio": f["audio"], "kind": "мэдээлэл"} for f in facts if f.get("audio")]
    seen, uniq = set(), []
    for c in out:
        if c["text"] not in seen:
            seen.add(c["text"])
            uniq.append(c)
    return uniq


def english_clips() -> list[dict]:
    """Англи горимын бүх клип: хэллэг, цифр, хариулт (key = монгол бичвэрийн hash, хэллэгт англи бичвэрийн)."""
    path = os.path.join(T.kb_index_dir, "english.json")
    if not os.path.exists(path):
        return []
    meta = json.load(open(path, encoding="utf-8"))
    ph = meta["phrases"]
    out = [dict(ph[k], kind=f"EN {k}") for k in ph if k not in ("holds", "lead")]
    out += [dict(c, kind="EN hold") for c in ph["holds"]] + [dict(c, kind="EN бүртгэл") for c in ph["lead"].values()]
    out += [dict(c, kind="EN цифр") for c in meta["digits"]]
    out += [dict(x["clip"], kind=f"EN {x['id'] or 'мэдээлэл'}", key=x["hash"]) for x in meta["items"] if x.get("clip")]
    seen, uniq = set(), []
    for c in out:
        if c["text"] not in seen:
            seen.add(c["text"])
            uniq.append({**c, "key": c.get("key") or text_hash(c["text"])})
    return uniq


def en_letters(text: str) -> str:
    return re.sub(r"[^a-z]", "", english.speak_en(text).lower())


def check_english(stt, items: list[dict]) -> dict:
    report = {}
    for c in items:
        wav, sr = sf.read(c["audio"], dtype="float32")
        if wav.ndim > 1:
            wav = wav.mean(axis=1)
        pad = np.zeros(int(sr * PAD), np.float32)
        hyp = stt.transcribe(np.concatenate([pad, wav, pad]), sr, language="en")
        ref, got = en_letters(c["text"]), en_letters(hyp)
        err = cer(ref, got) if ref else 0.0
        speech, longest = silences(wav, sr)
        peak = float(np.abs(wav).max())
        flags = []
        if peak < 0.05 or speech < 0.12:
            flags.append("дуугүй")
        elif len(ref) >= 3 and err > EN_MAX_CER:
            flags.append("буруу дуудлага?")
        if peak >= 0.999:
            flags.append("дуу тасарсан")
        if longest > LONG_SILENCE:
            flags.append(f"урт чимээгүй {longest:.1f}с")
        report[c["key"]] = {"text": c["text"], "kind": c["kind"], "cer": round(err, 3),
                            "seconds": round(len(wav) / sr, 1), "hyp": hyp, "flags": flags}
    return report


def main():
    from stt import WhisperSTT
    stt = WhisperSTT()
    items = clips()
    t0, report = time.time(), {}
    for c in items:
        h = text_hash(c["text"])
        if c["audio"].startswith(T.recordings_dir):
            report[h] = {"text": c["text"], "kind": c["kind"], "recorded": True, "flags": []}
            continue
        wav, sr = sf.read(c["audio"], dtype="float32")
        if wav.ndim > 1:
            wav = wav.mean(axis=1)
        sp = spoken(c["text"])
        pad = np.zeros(int(sr * PAD), np.float32)
        hyp = stt.transcribe(np.concatenate([pad, wav, pad]), sr)
        err = mn_cer(sp, hyp)
        speech, longest = silences(wav, sr)
        peak = float(np.abs(wav).max())
        letters = sum(t is not WILD for t in ref_tokens(sp))
        en_segs = [seg for seg, en in split_language(sp) if en]
        cps = letters / max(speech, 0.3) if letters and not en_segs else None
        flags = []
        if peak < 0.05 or speech < 0.12:
            flags.append("дуугүй")
        elif letters >= 6 and err > MAX_CER:
            flags.append("буруу дуудлага?")
        if cps and letters >= 15 and cps > CPS[1]:
            flags.append("хэт хурдан")
        if cps and letters >= 15 and cps < CPS[0]:
            flags.append("хэт удаан")
        if peak >= 0.999:
            flags.append("дуу тасарсан")
        if longest > LONG_SILENCE:
            flags.append(f"урт чимээгүй {longest:.1f}с")
        report[h] = {"text": c["text"], "kind": c["kind"], "cer": round(err, 3), "cps": round(cps, 1) if cps else None,
                     "seconds": round(len(wav) / sr, 1), "english": en_segs, "hyp": hyp, "flags": flags}
    en_items, en_report = english_clips(), {}
    if en_items:
        from stt import MLX_MULTI
        en_report = check_english(WhisperSTT(MLX_MULTI), en_items)
    tmp = QA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"checked_at": time.time(), "clips": report, "english": en_report}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, QA_FILE)
    for name, rep_ in (("", report), ("англи ", en_report)):
        if not rep_:
            continue
        bad = [r for r in rep_.values() if r["flags"]]
        print(f"Шалгалаа: {len(rep_)} {name}клип ({time.time() - t0:.0f}с), шалгах шаардлагатай: {len(bad)}")
        for r in bad:
            print(f"  ⚠ {', '.join(r['flags'])}: {r['text'][:60]}  -> {r.get('hyp', '')[:50]!r}")


if __name__ == "__main__":
    main()
