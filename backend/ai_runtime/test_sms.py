"""SMS gateway payload ба аюулгүй алдаа боловсруулах хурдан тест."""
import os
import unittest
from unittest.mock import patch

import notify


class RegistrationSmsTest(unittest.TestCase):
    @patch.dict(os.environ, {"SMS_API_URL": "https://sms.example.test/send", "SMS_API_KEY": "", "SMS_API_TOKEN": "test-token"})
    @patch("notify.httpx.post")
    def test_confirmed_phone_receives_code(self, post):
        post.return_value.raise_for_status.return_value = None
        self.assertTrue(notify.send_registration_code("9911 2233", "4720", "Pinecone"))
        post.assert_called_once_with(
            "https://sms.example.test/send",
            json={"to": "+97699112233", "message":
                  "Pinecone: Бүртгэлийн код: 4720. Бусдад бүү хэл."},
            headers={"Authorization": "Bearer test-token"}, timeout=10)

    @patch.dict(os.environ, {"SMS_API_URL": "https://sms.example.test/send", "SMS_API_KEY": "", "SMS_API_TOKEN": "test-token"})
    @patch("notify.httpx.post")
    def test_unconfirmed_phone_does_not_send(self, post):
        self.assertFalse(notify.send_registration_code(None, "4720"))
        self.assertFalse(notify.send_registration_code("123", "4720"))
        post.assert_not_called()

    @patch.dict(os.environ, {"SMS_API_URL": "", "SMS_API_KEY": "", "SMS_API_TOKEN": ""})
    @patch("notify.httpx.post")
    def test_unconfigured_gateway_does_not_send(self, post):
        self.assertFalse(notify.send_registration_code("99112233", "4720"))
        post.assert_not_called()

    @patch.dict(os.environ, {"SMS_API_URL": "https://sms.example.test/send", "SMS_API_KEY": "", "SMS_API_TOKEN": "test-token"})
    @patch("notify.httpx.post")
    def test_gateway_failure_does_not_interrupt_call(self, post):
        post.side_effect = notify.httpx.ConnectError("offline")
        self.assertFalse(notify.send_registration_code("99112233", "4720"))

    @patch.dict(os.environ, {"SMS_API_URL": "", "SMS_API_KEY": "test-key", "SMS_API_TOKEN": "test-token"})
    @patch("notify.httpx.post")
    def test_provider_can_reject_with_http_200(self, post):
        post.return_value.json.return_value = {"success": False, "error": "insufficient balance"}
        self.assertFalse(notify.send_registration_code("99112233", "4720"))

    @patch.dict(os.environ, {"SMS_API_URL": "", "SMS_API_KEY": "test-key", "SMS_API_TOKEN": "test-token"})
    @patch("notify.httpx.post")
    def test_local_provider_receives_eight_digit_phone(self, post):
        self.assertTrue(notify.send_registration_code("99112233", "4720"))
        args, kwargs = post.call_args
        self.assertEqual(args, (notify.SENDSMS_API,))
        self.assertEqual(kwargs["json"]["phone"], "99112233")
        self.assertEqual(kwargs["json"]["apiKey"], "test-key")
        self.assertEqual(kwargs["json"]["apiToken"], "test-token")

    @patch.dict(os.environ, {"SMS_API_URL": "", "SMS_API_KEY": "test-key", "SMS_API_TOKEN": "test-token"})
    @patch("notify.httpx.post")
    def test_cyrillic_message_fits_one_sms(self, post):
        self.assertTrue(notify.send_registration_code("99112233", "4720", "Урт нэртэй байгууллагын нэр"))
        self.assertLessEqual(len(post.call_args.kwargs["json"]["message"]), 69)


class EventSmsTextTest(unittest.TestCase):
    def test_event_reminder_text(self):
        import notify
        t = notify.event_sms_text("Pinecone Academy", "AI Hackathon", "2026-10-18T10:00", "4052")
        self.assertEqual(t, "Pinecone Academy: AI Hackathon 10/18 10:00 бүртгэгдлээ. Код: 4052")
        long = notify.event_sms_text("Pinecone Academy", "Нээлттэй өдөрлөг " * 4, "2026-10-15T18:00", "3746")
        self.assertLessEqual(len(long), notify.SMS_MAX)             # SendSMS.mn: >70 бол HTTP 400
        self.assertTrue(long.endswith("Код: 3746"))
        self.assertNotIn("Код", notify.event_sms_text("", "Demo Day", "bad", None))


if __name__ == "__main__":
    unittest.main()
