"""Дуудлагын дараах нэрийн засвар (names.py): STT-ийн бодит алдаанууд -> зөв нэр."""
import os
import tempfile
import unittest

import names


class NamesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lex = names.lexicon()

    def test_real_stt_mistakes(self):
        # Бодит дуудлага, туршилтаас: STT ойр эгшгийг ялгадаггүй, нийлмэл нэрийг салгадаг
        for heard, name in [("бэлэг сайхан", "Билэгсайхан"), ("нөмийн", "Номин"), ("немин", "Номин"),
                            ("мунх баяр", "Мөнхбаяр"), ("тэмүлэн", "Тэмүүлэн"), ("оюн чимэг", "Оюунчимэг"),
                            ("батболт", "Батболд"), ("ганзорик", "Ганзориг")]:
            with self.subTest(heard=heard):
                self.assertEqual(names.fix(heard, self.lex), name)

    def test_phrases_around_name(self):
        self.assertEqual(names.fix("миний нэр бат болд", self.lex), "Батболд")
        self.assertEqual(names.fix("намайг номин гэдэг", self.lex), "Номин")

    def test_unknown_name_is_joined_not_replaced(self):
        # Жагсаалтад алга, ойр нэр ч алга -> өөр нэр болгохгүй
        self.assertEqual(names.fix("чингүүн", self.lex), "Чингүүн")
        self.assertEqual(names.fix("хайр", self.lex), "Хайр")

    def test_patronymic_kept_when_unknown(self):
        self.assertEqual(names.fix("батын болд", self.lex), "Болд")

    def test_best_text_skips_stuck_decode(self):
        # Санууллагатай таниулалт шуугиантай үед "гүгүгү..." гацсан (туршилт)
        texts = ["Нөгөө Минь", "г" + "гү" * 30, "биелэх сайхан"]
        self.assertEqual(names.best_text(texts, self.lex), "биелэх сайхан")
        self.assertEqual(names.fix(names.best_text(texts, self.lex), self.lex), "Билэгсайхан")

    def test_tenant_names_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "names.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("Хүдэрчулуун\n")
            self.assertEqual(names.fix("хүдэр чулуун", names.lexicon(path)), "Хүдэрчулуун")


if __name__ == "__main__":
    unittest.main()
