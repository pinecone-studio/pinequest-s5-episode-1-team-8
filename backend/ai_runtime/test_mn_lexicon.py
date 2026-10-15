"""Монгол толиор STT засах (mn_lexicon) — загваргүй, Википедиагийн толь байхгүй ч ажиллана."""
import unittest

import mn_lexicon

DOMAIN = ["Сургалтын төлбөр хэд вэ", "Хөтөлбөрт бүртгүүлмээр байна", "Сургалтын зээл авч болох уу",
          "Арга хэмжээнд бүртгүүлэх"]


class CorrectorTest(unittest.TestCase):
    def setUp(self):
        self.c = mn_lexicon.Corrector(DOMAIN, known=["Номин"])

    def test_out_of_vocabulary_to_org_word(self):
        self.assertEqual(self.c.fix("цургалтын төлбөр")[0], "сургалтын төлбөр")
        self.assertEqual(self.c.fix("бүтгүүлмээр байна")[0], "бүртгүүлмээр байна")

    def test_context_fixes_wrong_but_valid_word(self):
        self.c.valid.add("дээл")          # толинд байгаа үг ч энд утгагүй
        self.assertEqual(self.c.fix("сургалтын дээл")[0], "сургалтын зээл")

    def test_names_and_short_words_untouched(self):
        self.assertEqual(self.c.fix("номин")[0], "номин")
        self.assertEqual(self.c.fix("тэр ба")[0], "тэр ба")


if __name__ == "__main__":
    unittest.main()
