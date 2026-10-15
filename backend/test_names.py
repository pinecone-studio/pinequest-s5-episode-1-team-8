"""Нэрийн хайлт: нөхцөл, бичлэгийн алдаа, төстэй нэрс."""
import unittest

import people
from speech_parse import clean_name


class NameTest(unittest.TestCase):
    def test_case_endings_and_misheard_names(self):
        for text, name in (("Болдын цагийг солих", "Болд"),
                           ("Балдын цаг хэзээ вэ", "Болд"),
                           ("Сараагийн бүртгэлийг цуцал", "Сараа"),
                           ("Номин-Эрдэнийн цаг", "Номин-Эрдэнэ"),
                           ("Энхтүвшнээс асуу", "Энхтүвшин")):
            with self.subTest(text=text):
                self.assertGreaterEqual(people.name_score(text, name), people.NAME_MATCH)

    def test_exact_names_rank_above_typos(self):
        self.assertGreater(people.name_score("Болдын цаг", "Болд"),
                           people.name_score("Болдын цаг", "Балд"))

    def test_longer_names_are_not_prefix_matches(self):
        for text, name in (("Болдбаатарын цаг", "Болд"), ("Номингоогийн цаг", "Номин"),
                           ("сайн байна уу", "Сараа"), ("цагийг солих", "Болд")):
            with self.subTest(text=text):
                self.assertLess(people.name_score(text, name), people.NAME_MATCH)

    def test_strip_uses_same_matching_rules(self):
        self.assertEqual(people.strip_name("Балдын цагийг баасан руу шилжүүл", "Болд"),
                         "цагийг баасан руу шилжүүл")
        self.assertEqual(people.strip_name("Болдбаатарын цагийг солих", "Болд"),
                         "Болдбаатарын цагийг солих")

    def test_name_parser_keeps_hyphens_and_patronymics(self):
        self.assertEqual(clean_name("Миний нэр Доржийн Оюун-Эрдэнэ байна"), "Доржийн Оюун-Эрдэнэ")
        self.assertEqual(clean_name("Намайг Номин гэдэг юм аа"), "Номин")
        self.assertEqual(clean_name("99112233"), "")


if __name__ == "__main__":
    unittest.main()
