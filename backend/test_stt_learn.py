"""STT засвараас сурах (stt_learn) — сервер, загваргүй."""
import unittest

import re

import stt_learn
from stt_learn import word_fixes


class WordFixesTest(unittest.TestCase):
    def test_misheard_words(self):
        self.assertEqual(word_fixes("цургалтын дээл хэд вэ", "сургалтын зээл хэд вэ"),
                         [("цургалтын дээл", "сургалтын зээл")])
        self.assertEqual(word_fixes("бүтгүүлмээр байна", "бүртгүүлмээр байна"), [("бүтгүүлмээр", "бүртгүүлмээр")])

    def test_brand_transliteration(self):
        self.assertEqual(word_fixes("пайн кун хаана байдаг вэ", "Pinecone хаана байдаг вэ"), [("пайн кун", "Pinecone")])

    def test_paraphrase_is_not_a_fix(self):
        self.assertEqual(word_fixes("мэдээлэл авъя", "мэдээлэл авмаар байна"), [])
        self.assertEqual(word_fixes("төлбөр хэд вэ", "сургалт хэдэн сар үргэлжлэх вэ"), [])


class LearnTest(unittest.TestCase):
    def test_learned_fix_matches_whole_word_only(self):
        saved = {}
        t = type("T", (), {"config": lambda self: {"stt_fixes": []},
                           "save_config": lambda self, cfg: saved.update(cfg)})()
        [item] = stt_learn.learn(t, "арга хэмжээн тухай", "арга хэмжээний тухай")
        rx = re.compile(r"(?<![а-яөүёa-z])(?:" + item["heard"] + ")", re.I)
        self.assertEqual(rx.sub(item["fix"], "хэмжээн тухай"), "хэмжээний тухай")
        self.assertEqual(rx.sub(item["fix"], "арга хэмжээнд бүртгүүлэх"), "арга хэмжээнд бүртгүүлэх")


if __name__ == "__main__":
    unittest.main()
