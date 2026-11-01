import os
import unittest
from unittest.mock import Mock, patch

import email_service


class EmailServiceTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ["EMAIL_PROVIDER"] = "resend"
        os.environ["RESEND_API_KEY"] = "re_test_key"
        os.environ.pop("EMAIL_FROM", None)

    def tearDown(self):
        self.env.stop()

    def test_resend_is_the_default_provider(self):
        with patch.dict(os.environ, {"EMAIL_PROVIDER": ""}):
            self.assertEqual(email_service._email_provider(), "resend")

    def test_resend_requires_api_key(self):
        os.environ.pop("RESEND_API_KEY", None)
        self.assertFalse(email_service.is_email_configured())

    @patch("email_service.httpx.Client")
    def test_resend_acceptance_returns_true(self, client_cls):
        response = Mock(status_code=200)
        response.json.return_value = {"id": "email_test_123"}
        client_cls.return_value.__enter__.return_value.post.return_value = response

        self.assertTrue(email_service.send_verification_email(
            "recipient@example.com", "123456"
        ))

    @patch("email_service.httpx.Client")
    def test_resend_rejection_returns_false(self, client_cls):
        response = Mock(status_code=403, text='{"message":"domain not verified"}')
        client_cls.return_value.__enter__.return_value.post.return_value = response

        self.assertFalse(email_service.send_verification_email(
            "recipient@example.com", "123456"
        ))


if __name__ == "__main__":
    unittest.main()
