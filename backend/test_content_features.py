"""Мэдээлэл, FAQ, хоолой, AI сургалт, англи хэлний API integration тест."""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="pc_content_test_")

import app as server  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def owner(company: str, email: str) -> TestClient:
    server.SIGNUPS.clear()
    client = TestClient(server.app)
    response = client.post("/api/signup", json={"company": company, "phone": "", "email": email,
                                                 "password": "content-pass-1"})
    assert response.status_code == 200, response.text
    return client


def test_content_features():
    client = owner("Контент тест", "content@example.mn")
    other = owner("Өөр контент", "other-content@example.mn")

    assert client.put("/api/knowledge/file/info.md", json={"content": "Сургалтын төлбөр 100₮."}).status_code == 200
    assert client.get("/api/knowledge").json()["files"][0]["name"] == "info.md"
    assert client.get("/api/knowledge/file/info.md").json()["content"] == "Сургалтын төлбөр 100₮."
    assert other.get("/api/knowledge").json()["files"] == []
    assert client.post("/api/knowledge/upload", files={"file": ("note.txt", b"hello")}).status_code == 200

    faq = client.get("/api/faq").json()
    faq["faq"].append({"id": "price", "questions": ["Үнэ хэд вэ"], "answer": "Төлбөр 100 төгрөг."})
    assert client.put("/api/faq", json=faq).status_code == 200
    assert any(x["id"] == "price" for x in client.get("/api/faq").json()["faq"])

    voice = client.get("/api/voice").json()
    assert any(x["text"] == "Төлбөр 100 төгрөг." for x in voice["items"])
    assert client.put("/api/voice/settings", json={"speed": 0.9, "pause_ms": 350,
                                                    "lexicon": [{"word": "AI", "say": "эй ай"}]}).status_code == 200
    assert client.get("/api/voice").json()["settings"]["lexicon"][0]["say"] == "эй ай"

    choices = client.get("/api/train/answers").json()
    price = next(x["value"] for x in choices["faq"] if x["value"] == "faq:price")
    assert client.post("/api/train/examples", json={"q": "Хэдэн төгрөг вэ", "answer": price}).status_code == 200
    trained = client.get("/api/train").json()["taught"]
    assert trained and trained[0]["faq"] == "price"
    assert client.delete(f"/api/train/examples/{trained[0]['i']}").status_code == 200

    english = client.get("/api/english").json()
    target = next(x for x in english["items"] if x.get("id") == "price")
    body = {"enabled": True, "answers": {target["hash"]: "The fee is 100 tugriks."},
            "questions": {"price": ["How much is it?"]}, "phrases": english["phrases"]}
    assert client.put("/api/english", json=body).status_code == 200
    saved = client.get("/api/english").json()
    assert saved["enabled"] and next(x for x in saved["items"] if x.get("id") == "price")["en"]


if __name__ == "__main__":
    test_content_features()
    print("Контент feature тестүүд ТЭНЦЛЭЭ ✓")
