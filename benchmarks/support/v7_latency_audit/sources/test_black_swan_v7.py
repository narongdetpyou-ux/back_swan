#!/usr/bin/env python3

from __future__ import annotations

import unittest

from black_swan_v7_benchmark import (
    SCENARIOS,
    calibration_scenarios,
    generate_scenario,
)
from black_swan_v7_engine import BlackSwanV6Baseline, BlackSwanV7, calibrate


DEFINITIONS = {definition.scenario_id: definition for definition in SCENARIOS}


class BlackSwanV7Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calibration = calibrate(calibration_scenarios(990_000, 300), quantile=0.99)
        cls.v7 = BlackSwanV7(cls.calibration)
        cls.v6 = BlackSwanV6Baseline(min_history=cls.calibration.min_history)

    def scenario(self, scenario_id: str, seed: int = 42):
        return generate_scenario(DEFINITIONS[scenario_id], seed=seed)

    def test_calibration_is_deterministic(self):
        again = calibrate(calibration_scenarios(990_000, 300), quantile=0.99)
        self.assertAlmostEqual(self.calibration.composite_threshold, again.composite_threshold, places=12)

    def test_low_and_slow_is_new_evidence_channel(self):
        caught = 0
        missed_by_v6 = 0
        for seed in range(100, 140):
            scenario = self.scenario("slow_exfiltration", seed)
            caught += self.v7.decide(scenario).security_alert
            missed_by_v6 += not self.v6.decide(scenario).security_alert
        self.assertGreaterEqual(caught, 30)
        self.assertGreaterEqual(missed_by_v6, 30)

    def test_correlated_weak_signals_are_fused(self):
        caught = sum(
            self.v7.decide(self.scenario("correlated_subthreshold", seed)).security_alert
            for seed in range(200, 240)
        )
        self.assertGreaterEqual(caught, 30)

    def test_context_cannot_create_anomaly(self):
        scenario = self.scenario("normal_control", 501)
        scenario.context_events = self.scenario("approved_backup", 501).context_events
        decision = self.v7.decide(scenario)
        self.assertFalse(decision.security_alert)
        self.assertNotEqual(decision.final_route, "BENIGN_EXPLAINED_BREAK")

    def test_stale_context_cannot_suppress_alert(self):
        alerts = sum(
            self.v7.decide(self.scenario("stale_context_exfiltration", seed)).security_alert
            for seed in range(300, 340)
        )
        self.assertGreaterEqual(alerts, 30)

    def test_approved_context_is_auditable_correction(self):
        decision = self.v7.decide(self.scenario("approved_backup", 601))
        self.assertEqual(decision.final_route, "BENIGN_EXPLAINED_BREAK")
        self.assertTrue(decision.correction_applied)
        self.assertTrue(any(row["stage"] == "critic" for row in decision.ledger))

    def test_suppression_has_security_risk_hold(self):
        decision = self.v7.decide(self.scenario("log_suppression_attack", 701))
        self.assertEqual(decision.final_route, "TELEMETRY_HOLD_SECURITY_RISK")
        self.assertTrue(decision.operational_escalation)
        self.assertFalse(decision.security_alert)

    def test_lifecycle_precedes_forecast(self):
        decision = self.v7.decide(self.scenario("new_edr_sensor", 801))
        self.assertEqual(decision.final_route, "SERIES_LIFECYCLE_CHANGE")
        self.assertFalse(decision.security_alert)

    def test_benign_holdout_false_alert_is_bounded(self):
        alerts = 0
        total = 240
        definitions = ("normal_control", "planned_cloud_drift", "isolated_noise_burst")
        for index in range(total):
            scenario_id = definitions[index % len(definitions)]
            decision = self.v7.decide(self.scenario(scenario_id, 10_000 + index * 17))
            alerts += decision.security_alert
        self.assertLessEqual(alerts / total, 0.03)


if __name__ == "__main__":
    unittest.main()
