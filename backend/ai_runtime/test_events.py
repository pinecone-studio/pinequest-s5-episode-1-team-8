"""Эвентийн бүртгэл утсаар (lead.py): "Эвентэд бүртгүүлмээр байна" ба энгийн бүртгэлийг ялгах, эвент сонгох."""
import os
import unittest
from unittest.mock import AsyncMock, Mock

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


class BookingAfterRegistrationTest(unittest.TestCase):
    def registered(self, book=True, events=None, state="name"):
        f = LeadFlow("event" if events else "lead", "event_start" if events else state, None,
                     events=events, book=book)
        if events:
            f.handle("эвентэд бүртгүүлье")
            f.handle("1")
        f.handle("Номин")
        f.handle("85222634")
        return f

    def test_offer_time_then_book(self):
        f = self.registered()
        self.assertEqual(f.handle("зөв"), ["done_book"])
        self.assertTrue(f.save_pending)                 # бүртгэлийг одоо хадгална, урсгал үргэлжилнэ
        self.assertFalse(f.finished)
        self.assertEqual(f.handle("1"), ["@book"])       # -> account.py цаг санал болгоно
        self.assertEqual(f.result, "book")

    def test_decline_booking_or_new_question(self):
        f = self.registered()
        f.handle("зөв")
        self.assertEqual(f.handle("2"), ["declined"])
        self.assertEqual(f.result, "saved")
        f = self.registered()
        f.handle("зөв")
        self.assertEqual(f.handle("төлбөр хэд вэ"), [])  # шинэ асуулт -> энгийн горим
        self.assertEqual(f.result, "saved")

    def test_no_booking_without_slots_or_for_events(self):
        f = self.registered(book=False)
        self.assertEqual(f.handle("зөв"), ["done"])
        f = self.registered(events=EVENTS[:1])
        self.assertEqual(f.handle("зөв"), ["event_done"])


class DuplicateEventTest(unittest.TestCase):
    def test_active_lead(self):
        import os
        import tempfile
        import db
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "r.db")
            a = db.add_lead("c1", "Номин", "85222634", None, None, "event", course="AI Hackathon", path=path)
            self.assertEqual(db.active_lead("85222634", "AI Hackathon", path=path), a)
            self.assertIsNone(db.active_lead("85222634", "How We Leap", path=path))
            self.assertIsNone(db.active_lead("99112233", "AI Hackathon", path=path))
            with db.connect(path) as con:
                con.execute("UPDATE leads SET status='canceled' WHERE id=?", (a,))
            self.assertIsNone(db.active_lead("85222634", "AI Hackathon", path=path))   # цуцалсан -> дахин бүртгэнэ


class SpokenEventChoiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_stt_number_reaches_event_selection(self):
        import numpy as np
        from phone_server import Call

        for text, index in [("1", 0), ("2", 1), ("3", 2), ("1.", 0),
                            ("нэг", 0), ("хоёр", 1), ("гурав", 2), ("эхнийх", 0)]:
            with self.subTest(text=text):
                call = Call.__new__(Call)
                call.lead = LeadFlow("event", "event_start", None, events=EVENTS)
                call.lead.handle("эвентэд бүртгүүлмээр байна")
                call.account, call.en = None, None
                call.m = Mock(stt_pool=None)
                call.transcribe = Mock(return_value=(text, "mn"))
                call.hold_while = AsyncMock()
                call.log = Mock()

                async def lead_turn(answer):
                    call.lead.handle(answer)
                    return True

                call.lead_turn = AsyncMock(side_effect=lead_turn)
                await call.handle_utterance(np.zeros(800, dtype=np.float32))
                call.lead_turn.assert_awaited_once_with(text)
                self.assertEqual(call.lead.event, EVENTS[index])
                self.assertEqual(call.lead.state, "event_offer")
                self.assertFalse(call.lead.finished)

    def test_event_selection_uses_registration_language(self):
        from phone_server import Call, SR

        call = Call.__new__(Call)
        call.en, call.m = Mock(), Mock()
        call.lang = "en"
        call.lead = LeadFlow("event", "event_pick", None, events=EVENTS)
        call.m.bilingual.transcribe_as.return_value = "1"
        audio = object()
        self.assertEqual(call.transcribe(audio), ("1", "mn"))
        call.m.bilingual.transcribe_as.assert_called_once_with(audio, SR, "mn")
        call.m.bilingual.transcribe.assert_not_called()

    def test_unavailable_number_is_not_selected(self):
        flow = LeadFlow("event", "event_start", None, events=EVENTS[:2])
        flow.handle("эвентэд бүртгүүлмээр байна")
        for text in ("3", "0"):
            with self.subTest(text=text):
                self.assertIsNone(flow._pick_event(text))

class NoisyEventSttTest(unittest.TestCase):
    """10-15 бодит дуудлага: STT "эвентэд бүртгүүлмээр байна"-г эвдэж бичсэн."""
    def test_misheard_requests(self):
        from lead import wants_event
        for t in ("эвээн түртгэлдсэн", "ивээн тэтгэвэрт гүйлмээр байна", "эвээн тэтгэвэл төсөө", "эвээн тэтгэвэл мэр байна аа", "эвентэд бүртгүүлмээр байна", "ивэнтэд оролцмоор байна"):
            self.assertTrue(wants_event(t, []), t)
        for t in ("эвентийн талаар мэдмээр байна", "эвентийн мэдээлэл авмаар байна", "эвентийн бүртгэлээ цуцлах"):
            self.assertFalse(wants_event(t, []), t)


class WhichRegistrationTest(unittest.TestCase):
    """10-15: "юмэнд бүртгүүлмээр" -> хөтөлбөр гэж ойлгоод уулзалтын цаг санал болгосон."""
    EV = [{"name": "AI Hackathon", "at": "2026-10-18T10:00"}]

    def test_stt_variant_is_event(self):
        from lead import wants_event
        self.assertTrue(wants_event("юмэнд бүртгүүлмээр байна аа", []))

    def test_generic_register_asks_which(self):
        from lead import LeadFlow, wants_register
        self.assertTrue(wants_register("бүртгүүлмээр байна"))
        self.assertFalse(wants_register("хөтөлбөрт бүртгүүлмээр байна"))
        f = LeadFlow("lead", "which_start", None, events=self.EV, book=True)
        self.assertEqual(f.handle("бүртгүүлмээр байна"), ["which_ask"])
        self.assertEqual(f.handle("арга хэмжээнд"), ["ev:AI Hackathon", "date:2026-10-18T10:00", "event_ask"])
        self.assertEqual((f.reason, f.book), ("event", False))
        g = LeadFlow("lead", "which_start", None, events=self.EV, book=True)
        g.handle("бүртгүүлмээр байна")
        self.assertEqual(g.handle("хөтөлбөрт"), ["ask_name_again"])
        self.assertEqual((g.reason, g.book), ("lead", True))



class DailyEventTest(unittest.TestCase):
    def test_daily_expands_and_courses_are_per_day(self):
        import tempfile, people
        from datetime import datetime
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "data"))
            people.set_events(d, [{"name": "Нээлттэй өдөрлөг", "at": "2026-10-15T18:00", "repeat": "daily"}])
            now = datetime(2026, 10, 20, 19, 0, tzinfo=people.TZ)        # 18:00 өнгөрсөн -> маргаашаас
            evs = people.events(d, now)
            self.assertEqual(len(evs), people.REPEAT_DAYS)
            self.assertEqual(evs[0]["at"], "2026-10-21T18:00")
            course = people.event_course(evs[1])
            self.assertEqual(course, "Нээлттэй өдөрлөг 2026-10-22")
            self.assertEqual(people.event_defs(d)[0]["repeat"], "daily")


if __name__ == "__main__":
    unittest.main()
