"""Уулзалт/эвент эхлэхээс өмнөх SMS сануулга (reminders.sms_due) — бодит SMS илгээхгүй."""
import os
import unittest
from datetime import datetime
from unittest.mock import patch

os.environ.setdefault("OUTBOUND_SCHEDULER", "0")
import reminders  # noqa: E402

TZ = reminders.TZ


class FakeTenant:
    slug = "pinecone"

    def config(self):
        return {"name": "Pinecone Academy", "phone": "72700800"}


class SmsReminderTest(unittest.TestCase):
    def run_due(self, items, now, enabled=True, leads=None):
        data = {"items": items}
        sent = []
        leads = leads or {}
        with patch.object(reminders, "all_tenants", return_value=[FakeTenant()]), \
                patch.object(reminders, "settings", return_value={"sms_reminders": enabled}), \
                patch.object(reminders, "load", return_value=data), patch.object(reminders, "save"), \
                patch.object(reminders, "lead_of", side_effect=lambda t, i: leads.get(i, {"phone": "85222634"})):
            done = reminders.sms_due(now, send=lambda phone, text: sent.append((phone, text)) or True)
        return done, sent, data

    def test_event_two_hours_before(self):
        items = {"7": {"appointment": "2026-10-18T10:00", "event": "AI Hackathon", "status": "scheduled"}}
        _, sent, _ = self.run_due(items, datetime(2026, 10, 18, 7, 0, tzinfo=TZ))
        self.assertEqual(sent, [])                                      # 3 цагийн өмнө -> хэт эрт
        done, sent, data = self.run_due(items, datetime(2026, 10, 18, 8, 30, tzinfo=TZ))
        self.assertEqual(done, [("pinecone", 7, True)])
        self.assertEqual(sent, [("85222634", "Pinecone Academy: Сануулга - AI Hackathon өнөөдөр 10:00 цагт.")])
        self.assertLessEqual(len(sent[0][1]), reminders.SMS_MAX)
        self.assertTrue(data["items"]["7"]["sms_at"])
        _, sent, _ = self.run_due(items, datetime(2026, 10, 18, 9, 0, tzinfo=TZ))
        self.assertEqual(sent, [])                                      # нэг л удаа

    def test_failed_sms_is_retried_then_given_up(self):
        items = {"7": {"appointment": "2026-10-18T10:00", "event": "AI Hackathon", "status": "scheduled"}}
        now = datetime(2026, 10, 18, 8, 30, tzinfo=TZ)
        data = {"items": items}
        for i in range(1, 4):
            with patch.object(reminders, "all_tenants", return_value=[FakeTenant()]), \
                    patch.object(reminders, "settings", return_value={"sms_reminders": True}), \
                    patch.object(reminders, "load", return_value=data), patch.object(reminders, "save"), \
                    patch.object(reminders, "lead_of", return_value={"phone": "85222634"}):
                reminders.sms_due(now, send=lambda phone, text: False)          # ConnectError гэх мэт
            self.assertEqual(items["7"]["sms_tries"], i)
            self.assertEqual(bool(items["7"].get("sms_at")), i == 3)         # 3 дахь удаад л больно

    def test_skips_canceled_declined_and_disabled(self):
        now = datetime(2026, 10, 16, 13, 0, tzinfo=TZ)
        items = {"1": {"appointment": "2026-10-16T14:00", "status": "canceled"},
                 "2": {"appointment": "2026-10-16T14:00", "status": "scheduled", "attendance": False},
                 "3": {"appointment": "2026-10-16T14:00", "status": "scheduled"}}
        _, sent, _ = self.run_due(items, now, leads={3: {"phone": "85222634", "status": "canceled"}})
        self.assertEqual(sent, [])
        items = {"4": {"appointment": "2026-10-16T14:00", "status": "confirmed"}}
        _, sent, _ = self.run_due(items, now, enabled=False)
        self.assertEqual(sent, [])
        _, sent, _ = self.run_due(items, now)
        self.assertIn("таны уулзалт өнөөдөр 14:00", sent[0][1])


if __name__ == "__main__":
    unittest.main()
