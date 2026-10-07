"""Мэдээллийн файлыг унших, утсаар уншигдах өгүүлбэрт хуваах — SIM-TRUNK scripts/ingest.py · read_file, split_facts-тай
ЯГ ижил (Хоолойн жагсаалт "Аудио бэлдэх"-ийн үүсгэх өгүүлбэрүүдтэй таарна)."""
import os
import re

FACT_MIN_CHARS = 15    # үүнээс богино мөрийг (гарчиг гэх мэт) өгүүлбэр гэж үзэхгүй


def read_file(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".txt", ".md"):
        with open(path, encoding="utf-8") as f:
            return f.read()
    if ext == ".pdf":
        from pypdf import PdfReader
        return "\n\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
    if ext == ".docx":
        from docx import Document
        return "\n\n".join(p.text for p in Document(path).paragraphs)
    return ""


def split_facts(text: str) -> list[tuple[str, str | None]]:
    """Утсаар чангаар уншихад тохирох өгүүлбэрүүд + харьяалах гарчиг (## Төлбөр). Гарчиг нь
    тодруулах сэдэв, асуулт автоматаар үүсгэхэд хэрэглэгдэнэ. Жагсаалтын тэмдэг, богино мөрийг хасна."""
    facts, section = [], None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            if line.startswith("##") and title:
                section = title
            continue
        if not line:
            continue
        line = re.sub(r"^([-*•]|\d+[.)])\s+", "", line)
        line = re.sub(r"[*_`]", "", line)
        for sent in re.split(r"(?<=[.!?])\s+", line):
            sent = sent.strip()
            if len(sent) >= FACT_MIN_CHARS:
                facts.append((sent, section))
    return facts
