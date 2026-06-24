import tempfile
import unittest
from pathlib import Path

from src.line_bot.client import (
    make_webhook_signature,
    verify_webhook_signature,
)
from src.line_bot.flow import handle_line_event
from src.line_bot.store import claim_webhook_event
from src.reports.store import (
    get_report_summary,
    list_reports,
)


class LineWebhookSignatureTests(unittest.TestCase):
    def test_signature_verification(self):
        body = b'{"events":[]}'

        secret = "test-line-secret"

        signature = make_webhook_signature(
            body,
            secret,
        )

        self.assertTrue(
            verify_webhook_signature(
                body,
                signature,
                channel_secret=secret,
            )
        )

        self.assertFalse(
            verify_webhook_signature(
                body,
                "invalid-signature",
                channel_secret=secret,
            )
        )


class LineReportFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

        self.db_path = (
            Path(self.temp_dir.name)
            / "line_reports.sqlite3"
        )

        self.reporter_secret = (
            "test-reporter-secret"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def base_event(self, event_id):
        return {
            "webhookEventId": event_id,
            "source": {
                "type": "user",
                "userId": "U-test-user-001",
            },
            "replyToken": "test-reply-token",
        }

    def text_event(
        self,
        event_id,
        text,
    ):
        event = self.base_event(event_id)

        event["type"] = "message"
        event["message"] = {
            "type": "text",
            "text": text,
        }

        return event

    def location_event(
        self,
        event_id,
    ):
        event = self.base_event(event_id)

        event["type"] = "message"
        event["message"] = {
            "type": "location",
            "title": "測試位置",
            "address": "花蓮縣測試鄉測試路",
            "latitude": 23.75,
            "longitude": 121.45,
        }

        return event

    def postback_event(
        self,
        event_id,
        data,
    ):
        event = self.base_event(event_id)

        event["type"] = "postback"
        event["postback"] = {
            "data": data,
        }

        return event

    def handle(self, event):
        return handle_line_event(
            event,
            db_path=self.db_path,
            reporter_hash_secret=self.reporter_secret,
        )

    def test_complete_line_report_flow(self):
        self.handle(
            self.text_event(
                "event-start",
                "災情回報",
            )
        )

        self.handle(
            self.postback_event(
                "event-category",
                (
                    "flow=report"
                    "&action=category"
                    "&value=flooding"
                ),
            )
        )

        self.handle(
            self.postback_event(
                "event-severity",
                (
                    "flow=report"
                    "&action=severity"
                    "&value=2"
                ),
            )
        )

        self.handle(
            self.location_event(
                "event-location",
            )
        )

        self.handle(
            self.text_event(
                "event-description",
                "道路旁邊有積水，"
                "車輛通行受到影響。",
            )
        )

        response = self.handle(
            self.postback_event(
                "event-confirm",
                "flow=report&action=confirm",
            )
        )

        self.assertIn(
            "已收到你的回報",
            response[0]["text"],
        )

        summary = get_report_summary(
            db_path=self.db_path
        )

        self.assertEqual(
            summary["pending"],
            1,
        )

        reports = list_reports(
            status="pending",
            db_path=self.db_path,
        )

        self.assertEqual(
            reports[0]["source"],
            "line",
        )

        self.assertEqual(
            reports[0]["category"],
            "flooding",
        )

        self.assertEqual(
            reports[0]["severity"],
            2,
        )

    def test_webhook_event_deduplication(self):
        self.assertTrue(
            claim_webhook_event(
                "same-event",
                db_path=self.db_path,
            )
        )

        self.assertFalse(
            claim_webhook_event(
                "same-event",
                db_path=self.db_path,
            )
        )


if __name__ == "__main__":
    unittest.main()