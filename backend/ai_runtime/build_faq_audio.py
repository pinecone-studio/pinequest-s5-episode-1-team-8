"""
Байгууллагын faq.json + хэллэгүүд -> урьдчилан бэлдсэн аудио + embedding index

  TENANT=pinecone python build_faq_audio.py

Хийх зүйл:
  1. Мэндчилгээ, filler, hold, тодруулах/дахин асуух/ажилтан, бүртгэл, цифр, FAQ хариулт бүрийг WAV болгоно
     (хэллэгүүд tenants/<slug>/config.json-оос, tenant.py-ийн загвараар)
  2. FAQ асуулт бүрийн embedding-ийг тооцоолно
  3. tenants/<slug>/faq_audio/ руу индекс, data/tts_cache/ руу аудио (бүх байгууллагад нийтлэг кэш)

Текст өөрчлөгдөөгүй бол аудиог дахин үүсгэхгүй (hash кэш). Байгууллагын recordings/ дотор
хүний бичлэг байвал TTS-ийн оронд түүнийг ашиглана.
"""

import json
import os
import shutil

import numpy as np
import soundfile as sf

import tenant as tenants
from lead import DIGITS
import people
from recordings import recording_for, text_hash
from stream_voice import OronTTS, clip_key, clip_seed, eleven_sample_path, engine_for, tts_engine, tts_seeds, voice_tag

SEEDS = tts_seeds()             # "Дахин үүсгэх" дарсан клипүүд


def synth_cached(get_tts, text: str, rec_dir: str) -> str:
    rec = recording_for(text, rec_dir)
    if rec:
        print(f"  [бичлэг] {text}")
        return rec
    engine = engine_for(text)       # "oron" | "eleven" (Хоолой хуудсанд өгүүлбэр бүрээр сонгоно)
    seed = clip_seed(text, engine, SEEDS)
    path = os.path.join(tenants.TTS_CACHE, f"{clip_key(text, seed, voice_tag(engine))}.wav")
    if os.path.exists(path):
        print(f"  [кэш]  {text}")
    elif engine == "eleven" and not seed and os.path.exists(eleven_sample_path(text)):
        shutil.copyfile(eleven_sample_path(text), path)      # харьцуулалтад үүсгэсэн -> API дахин дуудахгүй
        print(f"  [eleven жишээ] {text}")
    else:
        wav, sr = get_tts(engine).synth(text, seed)
        sf.write(path, wav, sr)
        print(f"  [шинэ {engine}] {text}")
    return path


def main():
    from embed import Embedder
    from stream_voice import lex_stems

    t = tenants.current()
    out = t.faq_index_dir
    os.makedirs(out, exist_ok=True)
    os.makedirs(tenants.TTS_CACHE, exist_ok=True)
    with open(t.faq_path, encoding="utf-8") as f:
        src = json.load(f)
    cfg = t.config()
    phrases = t.phrases()

    eng = tts_engine()
    print(f"Байгууллага: {cfg.get('name', t.slug)} ({t.slug}) · анхдагч хоолой: {eng['engine']}"
          f"{' ' + str(eng['voice']) if eng['engine'] == 'eleven' else ''}")
    engines = {}

    def get_tts(engine: str = "oron"):  # бүх өгүүлбэр бичлэг/кэштэй бол TTS ачаалахгүй
        if engine not in engines:
            print(f"TTS ачаалж байна ({engine})...")
            if engine == "eleven":
                from stream_voice import ElevenTTS
                engines[engine] = ElevenTTS()
            else:
                tts = engines[engine] = OronTTS()
                from stt import HF_MN, WhisperSTT
                from stream_voice import TTS_CANDIDATES
                if TTS_CANDIDATES > 1:   # 1 бол STT ачаалахгүй (8GB машинд санах ой хэмнэнэ)
                    # MLX (Metal) + TTS-ийн torch MPS нэг процесст -> Metal assertion-оор унасан -> CPU
                    tts.scorer = WhisperSTT(HF_MN, device="cpu")
        return engines[engine]

    all_audio = []

    def clip(text):
        path = synth_cached(get_tts, text, t.recordings_dir)
        all_audio.append(path)
        return {"text": text, "audio": path}

    print("\nМэндчилгээ / filler / hold:")
    greeting = clip(src.get("greeting") or phrases["greeting"])
    fillers = [clip(x) for x in (src.get("fillers") or phrases["fillers"])]
    holds = [clip(x) for x in phrases["holds"]]
    error = clip(phrases["error"])
    repeat = clip(phrases["repeat"])
    clarify = clip(phrases["clarify"])

    print("\nБүртгэл (lead) / цифр:")
    lead = {key: clip(text) for key, text in phrases["lead"].items()}
    digits = [clip(d) for d in DIGITS]

    print("\nБүртгэлээ шалгах/өөрчлөх (account) / огноо:")
    account = {key: clip(text) for key, text in phrases["account"].items()}
    dates = {x: clip(x) for x in people.all_date_texts(people.booking(t.dir))}

    print("\nСэдвийн bridge:")
    topics = {tid: clip(x["bridge"]) for tid, x in src.get("topics", {}).items()}

    print("\nFAQ хариулт:")
    faq, questions, row_to_faq = [], [], []
    for item in src["faq"]:
        if "TODO" in item["answer"]:
            print(f"  [алгасав] {item['id']} (TODO хариулт)")
            continue
        c = clip(item["answer"])
        faq.append({"id": item["id"], "topic": item.get("topic"),
                    "answer": c["text"], "audio": c["audio"]})
        for q in item["questions"]:
            questions.append(q)
            row_to_faq.append(len(faq) - 1)

    # Хариултгүй (TODO) асуултуудыг сэдэв таних зорилгоор embedding-д оруулна
    topic_rows = []
    for item in src["faq"]:
        if "TODO" in item["answer"] and item.get("topic"):
            for q in item["questions"]:
                questions.append(q)
                row_to_faq.append(-1)
                topic_rows.append(item["topic"])
    row_topic = [None] * (len(row_to_faq) - len(topic_rows)) + topic_rows

    embedder = Embedder()
    print(f"\nEmbedding ({embedder.model_name}), {len(questions)} асуулт...")
    # Асуулт-асуулттай харьцуулна -> хоёулаа query хэлбэрээр
    emb = embedder.query(questions) if questions else np.zeros((0, embedder.model.get_sentence_embedding_dimension()), np.float32)
    np.savez(os.path.join(out, "faq_index.npz"), emb=emb)

    # Тодруулах асуултын дараах богино хариулт ("төлбөр") -> бүтэн асуулт
    clarify_options = [{"keys": x.get("keys") or sorted(lex_stems(x["label"])),
                        "question": x.get("question") or x["label"]}
                       for x in cfg.get("clarify_topics", [])]
    meta = {
        "tenant": t.slug,
        "embed_model": embedder.model_name,
        "greeting": greeting,
        "fillers": fillers,
        "holds": holds,
        "error": error,
        "repeat": repeat,
        "clarify": clarify,
        "clarify_options": clarify_options,
        "generic_stems": sorted(t.generic_stems()),
        "lead": lead,
        "digits": digits,
        "account": account,
        "dates": dates,
        "topics": topics,
        "faq": faq,
        "questions": questions,
        "row_to_faq": row_to_faq,
        "row_topic": row_topic,
        "all_audio": sorted(set(all_audio)),
    }
    with open(os.path.join(out, "faq_index.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\nДууслаа: {len(faq)} FAQ, {len(meta['all_audio'])} аудио -> {out}/")


if __name__ == "__main__":
    main()
