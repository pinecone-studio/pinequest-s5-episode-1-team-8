"""
Хариултын аудиог ӨӨРӨӨ бичих хэрэгсэл (TTS-ийн оронд хүний хоолой).

  .venv/bin/python scripts/record.py            # бичлэггүй өгүүлбэрүүдийг дарааллаар нь
  .venv/bin/python scripts/record.py --all      # бүгдийг дахин бичих
  .venv/bin/python scripts/record.py --list     # аль нь бичигдсэнийг харах

Өгүүлбэр бүрт: [Enter] бичиж эхлэх -> [Enter] зогсоох -> автоматаар сонсгоно ->
  [Enter] хадгалах | r дахин бичих | s алгасах | q гарах
Эхэн/төгсгөлийн чимээгүйг тайрч, дууны түвшинг тэнцүүлээд recordings/<hash>.wav болгоно.

Бичиж дууссаны дараа:
  .venv/bin/python build_faq_audio.py && .venv/bin/python scripts/ingest.py
  (бичлэгтэй өгүүлбэрт TTS ажиллахгүй, таны бичлэгийг ашиглана)

Зөвлөгөө: чимээгүй өрөө, микрофоноос 15-20 см, жигд хэмнэлээр.
Англи нэр томьёог (Pinecone Academy, AI, CV) англиар нь уншина.
"""
import json
import os
import queue
import sys

import numpy as np
import sounddevice as sd
import soundfile as sf
from scipy.signal import resample_poly

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import tenant as tenants  # noqa: E402
from recordings import recording_for, recording_path, text_hash  # noqa: E402

REC_DIR = tenants.current().recordings_dir

MIC_SR = 48000
OUT_SR = 24000          # TTS-тэй ижил -> phone_server 8kHz болгож хөрвүүлнэ
TARGET_RMS = 0.08       # ~ -22 dBFS
PAD_START, PAD_END = 0.15, 0.25


def all_texts(t: "tenants.Tenant | None" = None) -> list[tuple[str, str]]:
    """(төрөл, текст) - байгууллагын faq.json, хэллэгүүд, knowledge/ доторх тоглогдох бүх өгүүлбэр."""
    import ingest
    from lead import DIGITS
    import people

    t = t or tenants.current()
    with open(t.faq_path, encoding="utf-8") as f:
        src = json.load(f)
    ph = t.phrases()
    items = [("мэндчилгээ", src.get("greeting") or ph["greeting"])]
    items += [("filler", x) for x in (src.get("fillers") or ph["fillers"])]
    items += [("hold", x) for x in ph["holds"]]
    items += [("алдаа", ph["error"]), ("дахин асуух", ph["repeat"]), ("тодруулах", ph["clarify"])]
    items += [("bridge", x["bridge"]) for x in src.get("topics", {}).values()]
    items += [("бүртгэл", x) for x in ph["lead"].values()]
    items += [("цифр", d) for d in DIGITS]
    items += [("бүртгэлээ шалгах", x) for x in ph["account"].values()]
    items += [("огноо", x) for x in people.all_date_texts(people.booking(t.dir))]
    items += [(f"FAQ {x['id']}", x["answer"]) for x in src["faq"] if "TODO" not in x["answer"]]

    kdir = t.knowledge_dir
    for dp, _, fs in os.walk(kdir):
        for name in sorted(fs):
            if name.lower().endswith((".txt", ".md", ".pdf", ".docx")) and name.lower() != "readme.md":
                path = os.path.join(dp, name)
                items += [(f"мэдээлэл {name}", x) for x, _ in ingest.split_facts(ingest.read_file(path))]

    seen, unique = set(), []
    for kind, text in items:
        if text not in seen:
            seen.add(text)
            unique.append((kind, text))
    return unique


def record_until_enter() -> np.ndarray:
    q: queue.Queue = queue.Queue()
    with sd.InputStream(samplerate=MIC_SR, channels=1, dtype="float32",
                        callback=lambda d, *_: q.put(d[:, 0].copy())):
        input("  ● Бичиж байна... дуусмагц [Enter]")
    chunks = []
    while not q.empty():
        chunks.append(q.get())
    return np.concatenate(chunks) if chunks else np.zeros(0, np.float32)


def clean(audio: np.ndarray, sr: int = MIC_SR) -> np.ndarray | None:
    """Чимээгүйг тайрч, 24kHz болгож, дууны түвшинг тэнцүүлнэ (вэб бичлэгт ч ашиглана)."""
    if len(audio) < sr * 0.3:
        return None
    frame = int(sr * 0.02)
    n = len(audio) // frame
    rms = np.sqrt((audio[:n * frame].reshape(n, frame) ** 2).mean(axis=1))
    thresh = max(0.01, 0.1 * np.percentile(rms, 95))
    voiced = np.where(rms > thresh)[0]
    if len(voiced) == 0:
        return None
    start = max(0, voiced[0] * frame - int(PAD_START * sr))
    end = min(len(audio), (voiced[-1] + 1) * frame + int(PAD_END * sr))
    from math import gcd
    g = gcd(OUT_SR, sr)
    audio = resample_poly(audio[start:end], OUT_SR // g, sr // g).astype(np.float32)

    speech = audio[np.abs(audio) > 0.02]
    level = np.sqrt((speech ** 2).mean()) if len(speech) else np.sqrt((audio ** 2).mean())
    audio = audio * (TARGET_RMS / max(level, 1e-4))
    peak = np.abs(audio).max()
    if peak > 0.95:
        audio *= 0.95 / peak
    fade = int(OUT_SR * 0.01)
    audio[:fade] *= np.linspace(0, 1, fade)
    audio[-fade:] *= np.linspace(1, 0, fade)
    return audio


def save_index(texts):
    index = {text_hash(t): {"kind": k, "text": t, "recorded": bool(recording_for(t))} for k, t in texts}
    with open(os.path.join(REC_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def main():
    os.makedirs(REC_DIR, exist_ok=True)
    texts = all_texts()
    done = sum(1 for _, t in texts if recording_for(t))

    if "--list" in sys.argv:
        for kind, text in texts:
            print(f"{'✓' if recording_for(text) else ' '} [{kind}] {text}")
        print(f"\n{done}/{len(texts)} бичигдсэн")
        return

    todo = texts if "--all" in sys.argv else [(k, t) for k, t in texts if not recording_for(t)]
    print(__doc__.split("Бичиж дууссаны")[0])
    print(f"Нийт {len(texts)} өгүүлбэр, {done} нь бичигдсэн, {len(todo)} бичнэ.\n")

    for i, (kind, text) in enumerate(todo, 1):
        print(f"\n[{i}/{len(todo)}] ({kind})\n\n    {text}\n")
        while True:
            cmd = input("  [Enter] эхлэх | s алгасах | q гарах: ").strip().lower()
            if cmd == "q":
                save_index(texts)
                print("Гарлаа. Дараа нь үргэлжлүүлэхэд бичигдсэнийг алгасна.")
                return
            if cmd == "s":
                break
            audio = clean(record_until_enter())
            if audio is None:
                print("  Дуу сонсогдсонгүй. Микрофоны зөвшөөрлөө шалгаад дахин оролдоно уу.")
                continue
            print(f"  ▶ Сонсгож байна ({len(audio) / OUT_SR:.1f}с)...")
            sd.play(audio, OUT_SR)
            sd.wait()
            ans = input("  [Enter] хадгалах | r дахин бичих: ").strip().lower()
            if ans == "r":
                continue
            sf.write(recording_path(text), audio, OUT_SR)
            print("  ✓ Хадгаллаа")
            break
    save_index(texts)
    print("\nДууслаа. Одоо: .venv/bin/python build_faq_audio.py && .venv/bin/python scripts/ingest.py")


if __name__ == "__main__":
    main()
