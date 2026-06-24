import tempfile
import unittest
from pathlib import Path

from src.advisor.command_plan import build_command_plan
from src.reports.store import (
    create_report,
    get_report_summary,
    review_report,
)


class ReportStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

        self.db_path = (
            Path(self.temp_dir.name)
            / "reports.sqlite3"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_and_review_report(self):
        report, created = create_report(
            source="manual",
            reporter_hash="demo-user-hash",
            category="flooding",
            severity=2,
            description="道路邊溝出現積水。",
            latitude=23.75,
            longitude=121.45,
            external_event_id="demo-event-001",
            db_path=self.db_path,
        )

        self.assertTrue(created)
        self.assertEqual(report["status"], "pending")

        reviewed = review_report(
            report_id=report["report_id"],
            decision="verified",
            reviewer_id="tester",
            reviewer_note="人工確認為有效測試資料。",
            db_path=self.db_path,
        )

        self.assertEqual(
            reviewed["status"],
            "verified",
        )

        summary = get_report_summary(
            db_path=self.db_path
        )

        self.assertEqual(summary["verified"], 1)

    def test_duplicate_external_event_is_idempotent(self):
        first, first_created = create_report(
            source="manual",
            reporter_hash="demo-user-hash",
            category="road_blocked",
            severity=1,
            description="道路有落石。",
            external_event_id="duplicate-event",
            db_path=self.db_path,
        )

        second, second_created = create_report(
            source="manual",
            reporter_hash="demo-user-hash",
            category="road_blocked",
            severity=1,
            description="道路有落石。",
            external_event_id="duplicate-event",
            db_path=self.db_path,
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)

        self.assertEqual(
            first["report_id"],
            second["report_id"],
        )


class CommandPlanTests(unittest.TestCase):
    def test_plan_keeps_deterministic_priority(self):
        records = [
            {
                "village_id": "A",
                "county_name": "花蓮縣",
                "town_name": "測試鄉",
                "village_name": "甲村",
                "silent_risk_score": 0.72,
                "static_risk_score": 0.7,
                "sensor_gap_score": 1.0,
                "realtime_event_score": 0.2,
                "report_count_6h": 0,
                "report_count_24h": 0,
                "elderly_ratio": 0.25,
            },
            {
                "village_id": "B",
                "county_name": "花蓮縣",
                "town_name": "測試鄉",
                "village_name": "乙村",
                "silent_risk_score": 0.30,
                "static_risk_score": 0.2,
                "sensor_gap_score": 0.0,
                "realtime_event_score": 0.0,
                "report_count_6h": 0,
                "report_count_24h": 0,
                "elderly_ratio": 0.1,
            },
        ]

        plan = build_command_plan(
            records=records,
            dataset_metadata={
                "data_mode": "batch",
                "verification": "verified",
                "freshness": "not_realtime",
                "has_source_issues": False,
            },
            report_summary={
                "total": 1,
                "pending": 1,
                "verified": 0,
                "rejected": 0,
            },
            limit=2,
        )

        self.assertEqual(
            plan["priority_queue"][0]["village_id"],
            "A",
        )

        self.assertEqual(
            plan["priority_queue"][0]["priority"],
            "P1",
        )

        self.assertTrue(
            plan["priority_queue"][0][
                "needs_human_confirmation"
            ]
        )


if __name__ == "__main__":
    unittest.main()