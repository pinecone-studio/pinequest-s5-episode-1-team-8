"""Бодит асуултыг зөв FAQ/мэдээлэлтэй холбох сургалтын жишээнүүд."""
import json
import os
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import current_tenant
import knowledge_jobs
from tenant import Tenant, load_faq, write_json

router = APIRouter(prefix="/api/train", tags=["training"])


def examples_path(t: Tenant) -> str:
    return t.training_path


def load_examples(t: Tenant) -> dict:
    try:
        with open(examples_path(t), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"examples": []}


@router.get("")
def status(t: Tenant = Depends(current_tenant)):
    rows = load_examples(t)["examples"]
    meta_path = t.path("knowledge_index", "selector.json")   # SIM-TRUNK-ийн train_selector.py энд бичнэ
    try:
        with open(meta_path, encoding="utf-8") as f:
            model = json.load(f)
    except (OSError, ValueError):
        model = None
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
    faq = load_faq(t).get("faq", [])
    facts = load_json(os.path.join(t.kb_index_dir, "facts.json"), {}).get("facts", [])
    texts = [row.get("text", "") for row in facts if row.get("text")]
    if not texts and os.path.isdir(t.knowledge_dir):
        for name in sorted(os.listdir(t.knowledge_dir)):
            if name.lower().endswith((".md", ".txt")):
                with open(os.path.join(t.knowledge_dir, name), encoding="utf-8") as f:
                    texts += [line.strip() for line in f if line.strip() and not line.lstrip().startswith("#")]
    return {"faq": [{"value": f"faq:{x['id']}", "title": f"{x['id']} — {x['answer'][:100]}"}
                    for x in faq if "TODO" not in x.get("answer", "")],
            "facts": [{"value": f"fact:{i}", "title": text[:120], "text": text}
                      for i, text in enumerate(texts[:500])],
            "special": [{"value": "label:other", "title": "Мэдээлэлд алга / хамааралгүй"},
                        {"value": "label:clarify", "title": "Хэт ерөнхий — тодруулах шаардлагатай"}]}


class TeachBody(BaseModel):
    q: str
    answer: str


@router.post("/examples")
def teach(body: TeachBody, t: Tenant = Depends(current_tenant)):
    question = " ".join(body.q.split())[:300]
    kind, _, value = body.answer.partition(":")
    if not question:
        raise HTTPException(400, "Асуулт хоосон байна")
    available = answers(t)
    choices = {x["value"] for group in available.values() for x in group}
    if body.answer not in choices:
        raise HTTPException(400, "Зөв хариулт олдсонгүй")
    row = {"q": question, "source": "web", "ts": int(time.time())}
    if kind == "faq": row["faq"] = value
    elif kind == "fact": row["fact"] = available["facts"][int(value)].get("text", available["facts"][int(value)]["title"])
    else: row["label"] = value
    data = load_examples(t)
    comparable = {k: v for k, v in row.items() if k not in {"source", "ts"}}
    if not any(all(x.get(k) == v for k, v in comparable.items()) for x in data["examples"]):
        data["examples"].append(row)
        write_json(examples_path(t), data)
    return {"ok": True}


@router.delete("/examples/{index}")
def remove_example(index: int, t: Tenant = Depends(current_tenant)):
    data = load_examples(t)
    if not 0 <= index < len(data["examples"]) or data["examples"][index].get("source") != "web":
        raise HTTPException(404, "Жишээ олдсонгүй")
    data["examples"].pop(index)
    write_json(examples_path(t), data)
    return {"ok": True}
