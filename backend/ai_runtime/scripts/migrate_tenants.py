"""
Нэг удаагийн шилжүүлэлт: хуучин (нэг байгууллагын) бүтэц -> tenants/pinecone/.

  .venv/bin/python scripts/migrate_tenants.py        # AI, вэб, SIP-ийг зогсоосны дараа

  knowledge/, faq.json, training/, tests/eval_questions.json, recordings/  -> tenants/pinecone/
  faq_audio/*.wav, knowledge_index/audio/*.wav                         -> data/tts_cache/ (нийтлэг кэш)
  faq_audio/faq_index.*, knowledge_index/*                             -> tenants/pinecone/ (аудио зам шинэчилнэ)
  data/receptionist.db, data/settings.json                             -> tenants/pinecone/data/
Pinecone-ийн одоогийн хэллэгүүдийг config.json-д яг хэвээр нь бичнэ (аудио дахин үүсгэхгүй).
Дахин ажиллуулахад юу ч хийхгүй.
"""
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import tenant as tenants  # noqa: E402

T = tenants.Tenant("pinecone")
CONFIG = {
    "name": "Pinecone Academy",
    "extension": "1000",
    "phone": "72700800",
    "email": "social@pinecone.mn",
    "lead_label": "Pinecone Bootcamp",
    "generic_words": ["сургалт", "хөтөлбөр", "bootcamp", "pinecone", "academy", "академи", "бүүткэмп"],
    "clarify_custom": True,      # autogen.py гараар тохируулсан сэдвийг дарахгүй
    "clarify_topics": [
        {"label": "хөтөлбөрийн хугацаа", "keys": ["хуга", "сар", "удаа"],
         "question": "Хөтөлбөр хэдэн сар үргэлжилдэг вэ"},
        {"label": "төлбөрийн нөхцөл", "keys": ["төлб", "үнэ", "зээл", "хуваа"],
         "question": "Сургалтын төлбөр хэд вэ"},
        {"label": "карьерын дэмжлэг", "keys": ["карь", "ажил", "дэмж"],
         "question": "Карьерын дэмжлэг үзүүлдэг үү, ажилд ороход тусалдаг уу"},
    ],
    # Өмнө нь кодонд байсан хэллэгүүд яг хэвээр (бэлдсэн аудио нь кэшээс)
    "phrases": {
        "error": ("Энэ мэдээллийг баталгаатай олж чадсангүй. "
                  "Pinecone Academy-ийн ажилтан тан руу эргэж холбогдох уу?"),
        "clarify": ("Та хөтөлбөрийн хугацаа, төлбөрийн нөхцөл, карьерын дэмжлэгийн "
                    "алиных нь талаар мэдэхийг хүсэж байна вэ?"),
        "lead": {
            "done": ("Таны мэдээллийг амжилттай бүртгэлээ. Pinecone Academy-ийн ажилтан тантай удахгүй "
                     "холбогдоно. Өөр асуух зүйл байна уу?"),
            "done_no_phone": ("Таны нэрийг бүртгэлээ. Дугаарыг тань авч чадсангүй тул Pinecone Academy руу "
                              "далан хоёр, долоон зуу, найман зуу дугаараар залгаарай. Өөр асуух зүйл байна уу?"),
        },
    },
    "plan": "active",
}


def move(src: str, dst: str):
    src, dst = os.path.join(ROOT, src), os.path.join(ROOT, dst)
    if os.path.exists(src) and not os.path.exists(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        print(f"  {os.path.relpath(src, ROOT)} -> {os.path.relpath(dst, ROOT)}")


def main():
    if T.exists():
        print("tenants/pinecone аль хэдийн байна -> алгасав")
        return
    cache = tenants.TTS_CACHE
    os.makedirs(cache, exist_ok=True)
    print("Аудио -> data/tts_cache/")
    renamed = {}
    for d in ("faq_audio", os.path.join("knowledge_index", "audio")):
        full = os.path.join(ROOT, d)
        if not os.path.isdir(full):
            continue
        for name in os.listdir(full):
            if name.endswith(".wav"):
                src, dst = os.path.join(full, name), os.path.join(cache, name)
                if not os.path.exists(dst):
                    shutil.move(src, dst)
                renamed[os.path.join(d, name)] = dst
                renamed[src] = dst
        print(f"  {d}: {sum(1 for k in renamed if k.startswith(d))} файл")

    def fix(path):         # хуучин зам (харьцангуй эсвэл бүтэн) -> кэш
        return renamed.get(path, renamed.get(os.path.relpath(path, ROOT) if os.path.isabs(path) else path, path))

    print("Индекс, мэдээлэл -> tenants/pinecone/")
    os.makedirs(T.dir, exist_ok=True)
    for name in ("faq_index.json", "faq_index.npz"):
        move(os.path.join("faq_audio", name), os.path.join("tenants", "pinecone", "faq_audio", name))
    for name in ("index.npz", "facts.npz", "chunks.json", "facts.json", "selector.json", "selector.npz"):
        move(os.path.join("knowledge_index", name), os.path.join("tenants", "pinecone", "knowledge_index", name))
    for src, dst in (("knowledge", "knowledge"), ("faq.json", "faq.json"), ("training", "training"),
                     (os.path.join("tests", "eval_questions.json"), os.path.join("tests", "eval_questions.json")),
                     ("recordings", "recordings"),
                     (os.path.join("data", "receptionist.db"), os.path.join("data", "receptionist.db")),
                     (os.path.join("data", "settings.json"), os.path.join("data", "settings.json"))):
        move(src, os.path.join("tenants", "pinecone", dst))

    # Аудио замуудыг шинэчилнэ
    fi = os.path.join(T.faq_index_dir, "faq_index.json")
    if os.path.exists(fi):
        meta = json.load(open(fi, encoding="utf-8"))

        def walk(x):
            if isinstance(x, dict):
                return {k: (fix(v) if k == "audio" and isinstance(v, str) else walk(v)) for k, v in x.items()}
            if isinstance(x, list):
                return [walk(v) for v in x]
            return x
        meta = walk(meta)
        meta["all_audio"] = [fix(p) for p in meta["all_audio"]]
        json.dump(meta, open(fi, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    ff = os.path.join(T.kb_index_dir, "facts.json")
    if os.path.exists(ff):
        data = json.load(open(ff, encoding="utf-8"))
        for f in data["facts"]:
            if f.get("audio"):
                f["audio"] = fix(f["audio"])
        json.dump(data, open(ff, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    T.save_config(CONFIG)
    for d in ("faq_audio", "knowledge_index"):
        full = os.path.join(ROOT, d)
        try:
            shutil.rmtree(os.path.join(full, "audio"), ignore_errors=True)
            os.rmdir(full)
        except OSError:
            print(f"  анхаар: {d}/ хоосон биш тул үлдээв")
    print("Дууслаа. Дараа нь: TENANT=pinecone .venv/bin/python build_faq_audio.py (кэшээс, ~30с)")


if __name__ == "__main__":
    main()
