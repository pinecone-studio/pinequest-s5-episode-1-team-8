"""
Англи горимын шалгалт (scripts/build_en.py-ийн дараа).

  TENANT=pinecone .venv/bin/python scripts/test_english.py              # бичвэрээр: асуулт -> хариулт
  TENANT=pinecone .venv/bin/python scripts/test_english.py --audio DIR  # DIR/NN.(aiff|wav) = асуулт NN, утасны чанараар
  TENANT=pinecone .venv/bin/python scripts/test_english.py --mn         # монгол клипүүдийг англи гэж андуурах эсэх

Асуултууд: tenants/<slug>/tests/english_eval.json {"q", "expect": [хариултад агуулагдах] | "REPEAT"}
"""
import argparse
import glob
import json
import os
import sys
import time
import warnings

import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import offline  # noqa: E402,F401
import english  # noqa: E402
import tenant as tenants  # noqa: E402

T = tenants.current()


def phone(wav: np.ndarray, sr: int) -> np.ndarray:
    """Утасны зам: 8kHz + μ-law (sip_bridge-тэй адил)."""
    from math import gcd
    from scipy.signal import resample_poly
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import audioop
    g = gcd(8000, sr)
    pcm = (np.clip(resample_poly(wav, 8000 // g, sr // g), -1, 1) * 32767).astype("<i2").tobytes()
    return np.frombuffer(audioop.ulaw2lin(audioop.lin2ulaw(pcm, 2), 2), "<i2").astype(np.float32) / 32768


def check(r: dict, expect) -> bool:
    if expect == "REPEAT":
        return r["route"] in ("repeat", "handoff") and "missing" not in r
    return any(e in r["text"] for e in expect)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio")
    ap.add_argument("--mn", action="store_true")
    args = ap.parse_args()
    from stt import BilingualSTT, WhisperSTT

    if args.mn:
        stt = BilingualSTT(WhisperSTT())
        meta = json.load(open(os.path.join(T.faq_index_dir, "faq_index.json"), encoding="utf-8"))
        files = sorted(set(meta["all_audio"]))
        from stream_voice import reference_voice
        files.append(reference_voice()[0])                 # Oron-ийн лавлах: жинхэнэ хүний монгол яриа
        wrong, shares, t0 = [], [], time.time()
        for f in files:
            wav, sr = sf.read(f, dtype="float32", always_2d=True)
            lang, share = stt.detect(phone(wav.mean(axis=1), sr), 8000)
            shares.append(share)
            if lang != "mn":
                wrong.append((share, f))
        print(f"Монгол {len(files)} клип: англи гэж андуурсан {len(wrong)} "
              f"(P(en) max {max(shares):.3f}, {1000 * (time.time() - t0) / len(files):.0f}мс/клип)")
        for share, f in wrong:
            print(f"  ✗ {share:.2f} {f}")
        return

    from embed import Embedder
    router = english.EnglishRouter(T, Embedder())
    qs = json.load(open(os.path.join(T.path("tests", "english_eval.json")), encoding="utf-8"))["questions"]
    stt = BilingualSTT(WhisperSTT()) if args.audio else None
    ok = 0
    for i, x in enumerate(qs):
        text, lang, extra = x["q"], "en", ""
        if stt:
            path = (glob.glob(os.path.join(args.audio, f"{i:02d}.*")) or [None])[0]
            wav, sr = sf.read(path, dtype="float32", always_2d=True)
            audio = phone(wav.mean(axis=1), sr)
            t0 = time.time()
            text, lang = stt.transcribe(audio, 8000)
            extra = f" [{lang} {time.time() - t0:.2f}с: {text!r}]"
        r = router.respond(text) if lang == "en" else {"route": "mn", "text": "(монгол гэж танив)", "score": 0}
        good = lang == "en" and check(r, x["expect"])
        ok += good
        print(f"{'✓' if good else '✗'} {r['score']:.2f} {r['route']:8} {x['q']}{extra}\n      -> {r['text'][:90]}")
    print(f"\nАнгли: {ok}/{len(qs)}")


if __name__ == "__main__":
    main()
