import unittest

import pandas as pd

from src.scoring.silent_risk import apply_silent_risk_scoring


class SilentRiskScoringTests(unittest.TestCase):
    def make_row(
        self,
        static_risk_score=0.8,
        sensor_gap_score=1.0,
        sensor_realtime_score=0.0,
        realtime_event_score=0.0,
        report_count_6h=0,
        report_count_24h=0,
    ):
        return {
            "static_risk_score": static_risk_score,
            "sensor_gap_score": sensor_gap_score,
            "sensor_realtime_score": sensor_realtime_score,
            "realtime_event_score": realtime_event_score,
            "report_count_6h": report_count_6h,
            "report_count_24h": report_count_24h,
        }

    def test_no_report_has_higher_score_than_one_report(self):
        frame = pd.DataFrame([
            self.make_row(report_count_6h=0, report_count_24h=0),
            self.make_row(report_count_6h=1, report_count_24h=1),
        ])

        scored = apply_silent_risk_scoring(frame)

        self.assertGreater(
            scored.loc[0, "silent_risk_score"],
            scored.loc[1, "silent_risk_score"],
        )
        self.assertGreater(
            scored.loc[1, "silent_risk_score"],
            0,
        )

    def test_sensor_gap_changes_priority_independently(self):
        frame = pd.DataFrame([
            self.make_row(sensor_gap_score=1.0),
            self.make_row(sensor_gap_score=0.0),
        ])

        scored = apply_silent_risk_scoring(frame)

        self.assertEqual(
            scored.loc[0, "risk_evidence_score"],
            scored.loc[1, "risk_evidence_score"],
        )
        self.assertGreater(
            scored.loc[0, "silent_risk_score"],
            scored.loc[1, "silent_risk_score"],
        )

    def test_24h_report_count_is_not_lower_than_6h_count(self):
        frame = pd.DataFrame([
            self.make_row(report_count_6h=4, report_count_24h=1),
        ])

        scored = apply_silent_risk_scoring(frame)

        self.assertEqual(scored.loc[0, "report_count_24h"], 4)
        self.assertEqual(scored.loc[0, "recent_report_score"], 1.0)
        self.assertGreater(scored.loc[0, "silence_factor"], 0)

    def test_optional_realtime_columns_default_to_zero(self):
        frame = pd.DataFrame([
            {
                "static_risk_score": 0.8,
                "sensor_gap_score": 1.0,
                "report_count_6h": 0,
                "report_count_24h": 0,
            },
        ])

        scored = apply_silent_risk_scoring(frame)

        self.assertEqual(scored.loc[0, "sensor_realtime_score"], 0.0)
        self.assertEqual(scored.loc[0, "realtime_event_score"], 0.0)
        self.assertGreater(scored.loc[0, "silent_risk_score"], 0)

    def test_missing_required_columns_raise_error(self):
        frame = pd.DataFrame([
            {
                "static_risk_score": 0.8,
                "report_count_6h": 0,
                "report_count_24h": 0,
            },
        ])

        with self.assertRaises(ValueError):
            apply_silent_risk_scoring(frame)

    def test_scoring_metadata_is_present(self):
        frame = pd.DataFrame([
            self.make_row(),
        ])

        scored = apply_silent_risk_scoring(frame)

        self.assertEqual(
            scored.loc[0, "scoring_mode"],
            "rule_based_mvp",
        )
        self.assertEqual(
            scored.loc[0, "model_status"],
            "not_applied",
        )
        self.assertTrue(
            pd.isna(scored.loc[0, "silent_risk_nn_score"])
        )


if __name__ == "__main__":
    unittest.main()