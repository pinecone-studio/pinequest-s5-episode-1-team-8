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


def is_empty(value):
    """None, "" эсвэл зөвхөн зайтай текстийг хоосон гэж үзнэ."""
    return value is None or str(value).strip() == ""


def check_duplicate_ids(faqs):
    """Нэг ID хэдэн удаа гарсныг тоолж, 1-ээс олон бол алдаа буцаана."""
    counts = {}
    for faq in faqs:
        faq_id = faq.get("id")
        if is_empty(faq_id):
            continue  # хоосон ID-г check_empty_fields шалгана
        counts[faq_id] = counts.get(faq_id, 0) + 1

    errors = []
    for faq_id, count in counts.items():
        if count > 1:
            errors.append(f"Давхардсан ID: {faq_id} ({count} удаа)")
    return errors


def check_empty_fields(faqs):
    """Хоосон ID, хоосон асуулт, хоосон хариулт хайна."""
    errors = []
    for index, faq in enumerate(faqs, start=1):
        faq_id = faq.get("id")

        # ID хоосон бол FAQ-г дарааллын дугаараар нь нэрлэнэ
        if is_empty(faq_id):
            errors.append(f"Хоосон ID: {index}-р FAQ")
            name = f"{index}-р FAQ"
        else:
            name = faq_id

        questions = faq.get("questions", [])
        if not questions:
            errors.append(f"Асуултгүй FAQ: {name}")
        for question in questions:
            if is_empty(question):
                errors.append(f"Хоосон асуулт: {name}")

        if is_empty(faq.get("answer")):
            errors.append(f"Хоосон хариулт: {name}")
    return errors


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    faqs = load_faqs(path)

    question_count = 0
    for faq in faqs:
        question_count += len(faq.get("questions", []))

    print("FAQ:", len(faqs))
    print("Асуулт:", question_count)

    errors = check_duplicate_ids(faqs) + check_empty_fields(faqs)
    for error in errors:
        print("Алдаа:", error)

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()