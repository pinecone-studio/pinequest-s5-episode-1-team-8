"""Бодит асуултыг зөв FAQ/мэдээлэлтэй холбох сургалтын жишээнүүд — SIM-TRUNK web/app.py (AI сургалт)-тай ЯГ ижил:
шалгах дүрэм, мессеж, хариултын жагсаалт, examples.json-ийн формат (мөр бүрт нэг жишээ)."""
import json
import os
import threading
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import current_tenant
import knowledge_jobs
from tenant import Tenant

router = APIRouter(prefix="/api/train", tags=["training"])


def examples_path(t: Tenant) -> str:
    return t.training_path


examples_lock = threading.Lock()
NOTE = ("Хариулт сонгогчийн сургалтын жишээ: залгагчийн асуулт -> зөв хариулт. faq | fact | facts | "
        "label (other, clarify). source: seed | web.")


def load_examples(t: Tenant) -> dict:
    return load_json(examples_path(t), {"examples": []})


def save_examples(t: Tenant, data: dict):
    """Мөр бүрт нэг жишээ (git diff, гараар засахад уншигдахуйц)."""
    path = examples_path(t)
    rows = ",\n".join("    " + json.dumps(ex, ensure_ascii=False) for ex in data["examples"])
    body = (f'{{\n  "_note": {json.dumps(data.get("_note") or NOTE, ensure_ascii=False)},\n'
            f'  "examples": [\n{rows}\n  ]\n}}\n')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(body)
    os.replace(tmp, path)


@router.get("")
def status(t: Tenant = Depends(current_tenant)):
    rows = load_examples(t)["examples"]
    meta_path = t.path("knowledge_index", "selector.json")   # SIM-TRUNK-ийн train_selector.py энд бичнэ
    meta = load_json(meta_path, None)
    # SIM-TRUNK web/app.py · train_status: хураангуй л (selector.json-ийн answers нь dict, label_stems, per_label том)
    model = None
    if meta:
        model = {k: meta.get(k) for k in ("trained_at", "examples", "rows", "cv_acc", "eval", "enabled", "warnings")}
        model["answers"] = len(meta.get("labels", []))
    auto = load_json(t.auto_training_path, {"examples": []})
    return {**knowledge_jobs.status(t), "model": model,
            "auto": len(auto.get("examples", [])),
            "seed": sum(x.get("source") != "web" for x in rows),
            "taught": [{"i": i, **x} for i, x in enumerate(rows) if x.get("source") == "web"][::-1]}


def load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except (OSError, ValueError):
        return default


@router.post("")
def start_training(t: Tenant = Depends(current_tenant)):
    try:
        return knowledge_jobs.enqueue(t, "train")
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/answers")
def answers(t: Tenant = Depends(current_tenant)):
    """Зөв хариултыг заахад сонгох жагсаалт: FAQ, мэдээллийн өгүүлбэр, "мэдээлэлд алга"."""
    faq = load_json(t.faq_path, {"faq": []})
    facts = load_json(os.path.join(t.kb_index_dir, "facts.json"), {}).get("facts", [])
    return {"faq": [{"value": f"faq:{f['id']}", "title": f"{f['id']} — {f['answer'][:70]}"}
                    for f in faq["faq"] if "TODO" not in f["answer"]],
            "facts": [{"value": f"fact:{i}", "title": f["text"][:90]} for i, f in enumerate(facts)],
            "special": [{"value": "label:other", "title": "Мэдээлэлд алга / хамааралгүй (дахин асууна)"},
                        {"value": "label:clarify", "title": "Хэт ерөнхий (тодруулж асууна)"}]}


class TeachBody(BaseModel):
    q: str
    answer: str          # faq:<id> | fact:<index> | label:other | label:clarify


@router.post("/examples")
def teach(body: TeachBody, t: Tenant = Depends(current_tenant)):
    return save_example(t, body.q, body.answer)


def save_example(t: Tenant, question: str, answer: str) -> dict:
    """Бодит дуудлагын асуулт -> зөв хариулт. "AI сургах" дарахад хэрэгжинэ (AI сургалт, Хариулж чадаагүй)."""
    q = question.strip()
    kind, _, value = answer.partition(":")
    if not q or len(q) > 300:
        raise HTTPException(400, "Асуулт хоосон эсвэл хэт урт")
    if kind == "faq":
        ex = {"q": q, "faq": value}
    elif kind == "fact":
        facts = load_json(os.path.join(t.kb_index_dir, "facts.json"), {}).get("facts", [])
        if not value.isdigit() or int(value) >= len(facts):
            raise HTTPException(400, "Өгүүлбэр олдсонгүй")
        ex = {"q": q, "fact": facts[int(value)]["text"]}
    elif kind == "label" and value in ("other", "clarify"):
        ex = {"q": q, "label": value}
    else:
        raise HTTPException(400, "Хариулт буруу")
    with examples_lock:
        data = load_examples(t)
        if not any(all(e.get(k) == v for k, v in ex.items()) for e in data["examples"]):
            data["examples"].append({**ex, "source": "web", "ts": int(time.time())})
            save_examples(t, data)
    return {"ok": True}


@router.delete("/examples/{index}")
def remove_example(index: int, t: Tenant = Depends(current_tenant)):
    with examples_lock:
        data = load_examples(t)
        if not 0 <= index < len(data["examples"]) or data["examples"][index].get("source") != "web":
            raise HTTPException(404, "Жишээ олдсонгүй")
        data["examples"].pop(index)
        save_examples(t, data)
    return {"ok": True}
