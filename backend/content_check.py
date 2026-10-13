"""Байгууллагын faq.json-г шалгах жижиг скрипт.

Ажиллуулах:
    python3 backend/content_check.py
    python3 backend/content_check.py ЗАМ/faq.json
"""
import json
import sys
from pathlib import Path

DEFAULT_PATH = Path(__file__).parent / "data" / "tenants" / "pinecone" / "faq.json"


def load_faqs(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("faq", [])


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    faqs = load_faqs(path)

    question_count = 0
    for faq in faqs:
        question_count += len(faq.get("questions", []))

    print("FAQ:", len(faqs))
    print("Асуулт:", question_count)


if __name__ == "__main__":
    main()