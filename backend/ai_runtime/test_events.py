"""Эвентийн бүртгэл утсаар (lead.py): "Эвентэд бүртгүүлмээр байна" ба энгийн бүртгэлийг ялгах, эвент сонгох."""
import unittest

from lead import LeadFlow, match_event, wants_event

EVENTS = [{"name": "PineQuest Demo Day", "at": "2026-10-16T14:00"},
          {"name": "AI Hackathon", "at": "2026-10-18T10:00"},
          {"name": "How We Leap", "at": "2026-10-20T18:00"}]


class EventDetectTest(unittest.TestCase):
    def test_event_vs_program_registration(self):
        for text in ["эвентэд бүртгүүлмээр байна", "хакатонд бүртгүүлмээр байна", "арга хэмжээнд оролцмоор байна",
                     "демо дэйд очмоор байна", "эвентэд бүтгүүлмээр байна", "эвээнтэд бүртгүүлмээр байна",
                     "ивэнтэд оролцмоор байна"]:
            with self.subTest(text=text):
                self.assertTrue(wants_event(text, EVENTS))
        # хөтөлбөрийн бүртгэл, мэдээлэл асуух, цуцлах -> эвентийн бүртгэл биш
        for text in ["бүртгүүлмээр байна", "хөтөлбөрт бүртгүүлмээр байна", "хакатоны талаар мэдээлэл авъя",
                     "эвентийн бүртгэлээ цуцлах", "эвентэд бүртгүүлсэн цагаа солимоор байна"]:
            with self.subTest(text=text):
                self.assertFalse(wants_event(text, EVENTS))

    def test_named_event(self):
        self.assertEqual(match_event("хакатонд бүртгүүлье", EVENTS)["name"], "AI Hackathon")
        self.assertEqual(match_event("пайнквест демо дэйд", EVENTS)["name"], "PineQuest Demo Day")
        self.assertIsNone(match_event("эвентэд бүртгүүлье", EVENTS))


class EventFlowTest(unittest.TestCase):
    def test_no_events(self):
        f = LeadFlow("event", "event_start", None, events=[])
        self.assertEqual(f.handle("эвентэд бүртгүүлмээр байна"), ["event_none"])
        self.assertEqual(f.result, "declined")

    def test_single_event_said_name_and_time(self):
        f = LeadFlow("event", "event_start", None, events=EVENTS[1:2])
        self.assertEqual(f.handle("эвентэд бүртгүүлмээр байна"),
                         ["ev:AI Hackathon", "date:2026-10-18T10:00", "event_ask"])
        self.assertEqual(f.handle("1"), ["ask_name_again"])
        f.handle("Номин")
        f.handle("85222634")
        self.assertEqual(f.handle("зөв"), ["event_done"])
        self.assertEqual((f.result, f.event["name"]), ("saved", "AI Hackathon"))

    def test_named_event_skips_list(self):
        f = LeadFlow("event", "event_start", None, events=EVENTS)
        self.assertEqual(f.handle("хакатонд бүртгүүлмээр байна")[0], "ev:AI Hackathon")

    def test_pick_from_list_by_key_ordinal_or_name(self):
        for answer, name in [("2", "AI Hackathon"), ("гуравдугаарт", "How We Leap"), ("демо дэй", "PineQuest Demo Day")]:
            with self.subTest(answer=answer):
                f = LeadFlow("event", "event_start", None, events=EVENTS)
                keys = f.handle("эвентэд бүртгүүлмээр байна")
                self.assertEqual((keys[0], keys[-1], f.state), ("event_list", "event_pick", "event_pick"))
                self.assertEqual(f.handle(answer)[0], f"ev:{name}")

    def test_decline_or_new_question(self):
        f = LeadFlow("event", "event_start", None, events=EVENTS[:1])
        f.handle("эвентэд бүртгүүлмээр байна")
        self.assertEqual(f.handle("2"), ["declined"])
        f = LeadFlow("event", "event_start", None, events=EVENTS[:1])
        f.handle("эвентэд бүртгүүлмээр байна")
        self.assertEqual(f.handle("хаана болох вэ"), [])          # шинэ асуулт -> энгийн горим
        self.assertTrue(f.finished)


if __name__ == "__main__":
    unittest.main()
