import unittest

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from src.advisor.incident_plan import (
    build_verified_incident_queue,
)
from src.reports.analytics import (
    build_verified_report_analytics,
)


class VerifiedReportAnalyticsTests(unittest.TestCase):
    def test_verified_reports_join_to_villages(self):
        villages = gpd.GeoDataFrame(
            [
                {
                    "village_id": "A",
                    "county_name": "花蓮縣",
                    "town_name": "測試鄉",
                    "village_name": "甲村",
                    "geometry": box(
                        121.0,
                        23.0,
                        121.5,
                        23.5,
                    ),
                },
                {
                    "village_id": "B",
                    "county_name": "花蓮縣",
                    "town_name": "測試鄉",
                    "village_name": "乙村",
                    "geometry": box(
                        121.5,
                        23.0,
                        122.0,
                        23.5,
                    ),
                },
            ],
            crs="EPSG:4326",
        )

        now = pd.Timestamp.now(tz="UTC")

        reports = [
            {
                "report_id": "R1",
                "status": "verified",
                "category": "flooding",
                "severity": 2,
                "created_at": (
                    now - pd.Timedelta(hours=1)
                ).isoformat(),
                "reviewed_at": now.isoformat(),
                "latitude": 23.2,
                "longitude": 121.2,
            },
            {
                "report_id": "R2",
                "status": "verified",
                "category": "road_blocked",
                "severity": 3,
                "created_at": (
                    now - pd.Timedelta(hours=12)
                ).isoformat(),
                "reviewed_at": now.isoformat(),
                "latitude": 23.2,
                "longitude": 121.7,
            },
            {
                "report_id": "R3",
                "status": "pending",
                "category": "flooding",
                "severity": 3,
                "created_at": now.isoformat(),
                "latitude": 23.2,
                "longitude": 121.2,
            },
        ]

        features, incidents, metadata = (
            build_verified_report_analytics(
                villages,
                reports,
                run_id="test_run",
                generated_at=now.isoformat(),
                analysis_time=now,
            )
        )

        feature_a = features[
            features["village_id"] == "A"
        ].iloc[0]

        feature_b = features[
            features["village_id"] == "B"
        ].iloc[0]

        self.assertEqual(
            feature_a["verified_report_count_6h"],
            1,
        )

        self.assertEqual(
            feature_a["verified_report_count_24h"],
            1,
        )

        self.assertEqual(
            feature_b["verified_report_count_6h"],
            0,
        )

        self.assertEqual(
            feature_b["verified_report_count_24h"],
            1,
        )

        self.assertEqual(
            metadata["matched_report_count"],
            2,
        )

        self.assertEqual(len(incidents), 2)

    def test_incident_queue_prioritizes_i1(self):
        queue = build_verified_incident_queue(
            [
                {
                    "incident_priority": "I2",
                    "village_id": "A",
                    "village_label": "甲村",
                    "category": "flooding",
                    "severity": 2,
                    "reported_at": "2026-06-24T10:00:00+00:00",
                },
                {
                    "incident_priority": "I1",
                    "village_id": "B",
                    "village_label": "乙村",
                    "category": "trapped_people",
                    "severity": 3,
                    "reported_at": "2026-06-24T11:00:00+00:00",
                },
            ]
        )

        self.assertEqual(
            queue[0]["village_id"],
            "B",
        )

        self.assertEqual(
            queue[0]["priority"],
            "I1",
        )


if __name__ == "__main__":
    unittest.main()