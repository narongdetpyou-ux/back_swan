#!/usr/bin/env python3
"""Reproducible cybersecurity simulation benchmark for Black Swan Logic v7."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from black_swan_v7_engine import (
    BlackSwanV6Baseline,
    BlackSwanV7,
    Calibration,
    ContextEvent,
    Decision,
    ScenarioInput,
    calibrate,
)


@dataclass(frozen=True)
class MetricSpec:
    baseline: float
    relative_noise: float
    diurnal_amplitude: float
    integer: bool


METRICS: Dict[str, MetricSpec] = {
    "auth_failures": MetricSpec(120, 0.10, 0.30, True),
    "unique_failed_accounts": MetricSpec(34, 0.09, 0.25, True),
    "unique_source_ips": MetricSpec(245, 0.08, 0.20, True),
    "successful_logins": MetricSpec(1500, 0.06, 0.40, True),
    "privileged_changes": MetricSpec(1.8, 0.22, 0.15, True),
    "outbound_mb": MetricSpec(850, 0.07, 0.35, False),
    "api_5xx": MetricSpec(18, 0.18, 0.30, True),
    "endpoint_alerts": MetricSpec(4.5, 0.25, 0.10, True),
    "file_rename_events": MetricSpec(42, 0.12, 0.20, True),
    "inbound_requests": MetricSpec(50000, 0.05, 0.45, True),
}


@dataclass(frozen=True)
class ScenarioDefinition:
    scenario_id: str
    group: str
    family: str
    attack_present: bool
    designed_evasive: bool
    desired_security_alert: bool
    expected_route: str
    description: str


SCENARIOS: Tuple[ScenarioDefinition, ...] = (
    ScenarioDefinition("normal_control", "control", "normal_activity", False, False, False, "NO_SECURITY_ALERT", "Ordinary seasonal telemetry."),
    ScenarioDefinition("planned_cloud_drift", "benign", "concept_drift", False, False, False, "NO_SECURITY_ALERT", "Small gradual baseline shift."),
    ScenarioDefinition("isolated_noise_burst", "benign", "isolated_noise_burst", False, False, False, "NO_SECURITY_ALERT", "One sub-threshold noisy point without persistence."),
    ScenarioDefinition("approved_backup", "benign", "backup_window", False, False, False, "BENIGN_EXPLAINED_BREAK", "Large approved outbound transfer."),
    ScenarioDefinition("software_release", "benign", "release_error_burst", False, False, False, "BENIGN_EXPLAINED_BREAK", "Documented release error burst."),
    ScenarioDefinition("campaign_traffic", "benign", "legitimate_traffic_surge", False, False, False, "BENIGN_EXPLAINED_BREAK", "Approved demand campaign."),
    ScenarioDefinition("password_spray", "attack", "password_spray", True, False, True, "SECURITY_ANOMALY_REVIEW", "Abrupt authentication attack."),
    ScenarioDefinition("credential_stuffing", "attack", "credential_stuffing", True, False, True, "SECURITY_ANOMALY_REVIEW", "High-volume credential replay."),
    ScenarioDefinition("ddos_burst", "attack", "denial_of_service", True, False, True, "SECURITY_ANOMALY_REVIEW", "Request flood plus 5xx errors."),
    ScenarioDefinition("exfiltration_burst", "attack", "data_exfiltration", True, False, True, "SECURITY_ANOMALY_REVIEW", "Abrupt outbound transfer."),
    ScenarioDefinition("ransomware_burst", "attack", "ransomware", True, False, True, "SECURITY_ANOMALY_REVIEW", "Endpoint and rename burst."),
    ScenarioDefinition("privilege_escalation", "attack", "privilege_escalation", True, False, True, "SECURITY_ANOMALY_REVIEW", "Burst of privileged changes."),
    ScenarioDefinition("slow_exfiltration", "evasive_attack", "low_and_slow_exfiltration", True, True, True, "SECURITY_ANOMALY_REVIEW", "Persistent outbound drift remains below the v6 25% gate."),
    ScenarioDefinition("correlated_subthreshold", "evasive_attack", "correlated_low_signal_intrusion", True, True, True, "SECURITY_ANOMALY_REVIEW", "Four persistent weak signals remain below the v6 univariate gate."),
    ScenarioDefinition("stale_context_exfiltration", "evasive_attack", "stale_context_attack", True, True, True, "SECURITY_ANOMALY_REVIEW", "A stale change record must not explain current exfiltration."),
    ScenarioDefinition("collector_failure", "data_quality", "telemetry_failure", False, False, False, "TELEMETRY_HOLD", "Collector failure remains non-numeric."),
    ScenarioDefinition("log_suppression_attack", "evasive_attack", "telemetry_suppression", True, True, False, "TELEMETRY_HOLD_SECURITY_RISK", "Suppressed telemetry is a security-risk hold, not a numeric zero."),
    ScenarioDefinition("new_edr_sensor", "lifecycle", "new_telemetry_series", False, False, False, "SERIES_LIFECYCLE_CHANGE", "New EDR series activation."),
    ScenarioDefinition("retired_proxy_metric", "lifecycle", "retired_telemetry_series", False, False, False, "SERIES_LIFECYCLE_CHANGE", "Retired legacy proxy."),
)


def _base_value(spec: MetricSpec, index: int, rng: random.Random) -> float:
    hour = index % 24
    day = index / 24.0
    seasonal = 1.0 + spec.diurnal_amplitude * math.sin(2.0 * math.pi * (hour - 7) / 24.0)
    slow_drift = 1.0 + 0.00035 * day
    noisy = spec.baseline * seasonal * slow_drift * (1.0 + rng.gauss(0.0, spec.relative_noise))
    value = max(0.0, noisy)
    return float(round(value)) if spec.integer else round(value, 3)


def _multiply(value: Optional[float], multiplier: float, integer: bool) -> Optional[float]:
    if value is None:
        return None
    changed = max(0.0, value * multiplier)
    return float(round(changed)) if integer else round(changed, 3)


def _set_status(
    scenario: ScenarioInput, metric: str, status: str, offsets: Iterable[int]
) -> None:
    statuses = scenario.recent_status[metric]
    for offset in offsets:
        statuses[offset] = status
        scenario.recent[metric][offset] = None


def generate_scenario(
    definition: ScenarioDefinition,
    *,
    seed: int,
    history_hours: int = 168,
    window_hours: int = 12,
) -> ScenarioInput:
    rng = random.Random(seed)
    history: Dict[str, List[Optional[float]]] = {}
    recent: Dict[str, List[Optional[float]]] = {}
    history_status: Dict[str, List[str]] = {}
    recent_status: Dict[str, List[str]] = {}
    for metric, spec in METRICS.items():
        history[metric] = [_base_value(spec, index, rng) for index in range(history_hours)]
        recent[metric] = [
            _base_value(spec, history_hours + offset, rng)
            for offset in range(window_hours)
        ]
        history_status[metric] = ["complete"] * history_hours
        recent_status[metric] = ["complete"] * window_hours

    scenario = ScenarioInput(
        scenario_id=definition.scenario_id,
        history=history,
        recent=recent,
        history_status=history_status,
        recent_status=recent_status,
    )

    def multiply(metric: str, offsets: Iterable[int], multiplier) -> None:
        spec = METRICS[metric]
        for offset in offsets:
            factor = multiplier(offset) if callable(multiplier) else multiplier
            scenario.recent[metric][offset] = _multiply(
                scenario.recent[metric][offset], factor, spec.integer
            )

    sid = definition.scenario_id
    tail4 = range(window_hours - 4, window_hours)
    tail3 = range(window_hours - 3, window_hours)
    tail2 = range(window_hours - 2, window_hours)
    if sid == "planned_cloud_drift":
        for metric in ("outbound_mb", "inbound_requests"):
            multiply(metric, range(window_hours), lambda offset: 1.01 + 0.09 * offset / (window_hours - 1))
        scenario.context_events.append(ContextEvent("cloud_migration", ("outbound_mb", "inbound_requests"), confidence=0.91))
    elif sid == "isolated_noise_burst":
        multiply("outbound_mb", [window_hours - 1], 1.20)
    elif sid == "approved_backup":
        multiply("outbound_mb", tail3, 4.0)
        scenario.context_events.append(ContextEvent("approved_backup", ("outbound_mb",), confidence=0.995))
    elif sid == "software_release":
        multiply("api_5xx", tail3, 8.0)
        scenario.context_events.append(ContextEvent("software_release", ("api_5xx",), confidence=0.98))
    elif sid == "campaign_traffic":
        multiply("successful_logins", tail4, 2.4)
        multiply("inbound_requests", tail4, 3.0)
        scenario.context_events.append(ContextEvent("campaign", ("successful_logins", "inbound_requests"), confidence=0.99))
    elif sid == "password_spray":
        for metric, factor in (("auth_failures", 6.0), ("unique_failed_accounts", 4.0), ("unique_source_ips", 3.0)):
            multiply(metric, tail4, factor)
    elif sid == "credential_stuffing":
        for metric, factor in (("auth_failures", 10.0), ("successful_logins", 2.0), ("unique_source_ips", 5.0)):
            multiply(metric, tail4, factor)
    elif sid == "ddos_burst":
        multiply("inbound_requests", tail4, 10.0)
        multiply("api_5xx", tail4, 12.0)
    elif sid == "exfiltration_burst":
        multiply("outbound_mb", tail2, 7.0)
    elif sid == "ransomware_burst":
        multiply("endpoint_alerts", tail3, 12.0)
        multiply("file_rename_events", tail3, 20.0)
    elif sid == "privilege_escalation":
        multiply("privileged_changes", tail3, 15.0)
    elif sid == "slow_exfiltration":
        # Persistent 16% elevation: individually below v6's 25% gate, but the
        # sequence carries substantially more evidence than an isolated point.
        multiply("outbound_mb", range(window_hours), 1.16)
    elif sid == "correlated_subthreshold":
        for metric in ("auth_failures", "unique_failed_accounts", "outbound_mb", "endpoint_alerts"):
            multiply(metric, range(window_hours), 1.12)
    elif sid == "stale_context_exfiltration":
        multiply("outbound_mb", range(window_hours), 1.18)
        scenario.context_events.append(ContextEvent("old_backup_ticket", ("outbound_mb",), active=False, confidence=0.995))
    elif sid == "collector_failure":
        _set_status(scenario, "api_5xx", "failed", range(window_hours))
    elif sid == "log_suppression_attack":
        _set_status(scenario, "endpoint_alerts", "suppressed", range(window_hours - 6, window_hours))
    elif sid == "new_edr_sensor":
        scenario.history["endpoint_alerts"] = [None] * history_hours
        scenario.history_status["endpoint_alerts"] = ["not_published"] * history_hours
        scenario.lifecycle["endpoint_alerts"] = "new_series"
    elif sid == "retired_proxy_metric":
        _set_status(scenario, "api_5xx", "not_published", range(window_hours))
        scenario.lifecycle["api_5xx"] = "retired_series"
    return scenario


def calibration_scenarios(seed: int, count: int) -> Iterable[ScenarioInput]:
    # Context-free null only. Documented drift is handled by the critic and is
    # evaluated on holdout, not allowed to define the statistical null.
    benign_ids = ("normal_control", "isolated_noise_burst")
    by_id = {definition.scenario_id: definition for definition in SCENARIOS}
    for index in range(count):
        scenario_id = benign_ids[index % len(benign_ids)]
        yield generate_scenario(by_id[scenario_id], seed=seed + index * 7919)


def wilson_interval(successes: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    if total == 0:
        return 0.0, 0.0
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    radius = z * math.sqrt(
        proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total)
    ) / denominator
    return max(0.0, center - radius), min(1.0, center + radius)


def evaluate_engine(
    name: str,
    engine,
    *,
    seed: int,
    repeats: int,
) -> Tuple[List[dict], List[dict]]:
    runs: List[dict] = []
    family_rows: List[dict] = []
    for definition_index, definition in enumerate(SCENARIOS):
        family_decisions: List[Decision] = []
        for repeat in range(repeats):
            scenario_seed = seed + definition_index * 1_000_003 + repeat * 1009
            scenario = generate_scenario(definition, seed=scenario_seed)
            decision = engine.decide(scenario)
            family_decisions.append(decision)
            record = {
                "engine": name,
                "scenario_id": definition.scenario_id,
                "scenario_group": definition.group,
                "family": definition.family,
                "repeat": repeat,
                "attack_present": definition.attack_present,
                "designed_evasive": definition.designed_evasive,
                "desired_security_alert": definition.desired_security_alert,
                "expected_route": definition.expected_route,
                **decision.as_record(),
                "route_matches_expectation": decision.final_route == definition.expected_route,
                "security_detection_correct": decision.security_alert == definition.desired_security_alert,
                "ledger_json": json.dumps(decision.ledger, sort_keys=True, separators=(",", ":")),
            }
            record.pop("ledger", None)
            runs.append(record)
        alerts = sum(decision.security_alert for decision in family_decisions)
        escalations = sum(decision.operational_escalation for decision in family_decisions)
        route_matches = sum(decision.final_route == definition.expected_route for decision in family_decisions)
        corrections = sum(decision.correction_applied for decision in family_decisions)
        channel_counts = {
            channel: sum(decision.dominant_channel == channel for decision in family_decisions)
            for channel in ("point", "temporal", "collective")
        }
        lower, upper = wilson_interval(alerts, repeats)
        family_rows.append(
            {
                "engine": name,
                "scenario_id": definition.scenario_id,
                "scenario_group": definition.group,
                "family": definition.family,
                "runs": repeats,
                "attack_present": definition.attack_present,
                "designed_evasive": definition.designed_evasive,
                "desired_security_alert": definition.desired_security_alert,
                "expected_route": definition.expected_route,
                "security_alert_rate": alerts / repeats,
                "alert_rate_ci95_low": lower,
                "alert_rate_ci95_high": upper,
                "operational_escalation_rate": escalations / repeats,
                "expected_route_rate": route_matches / repeats,
                "critic_correction_rate": corrections / repeats,
                "dominant_point_rate": channel_counts["point"] / repeats,
                "dominant_temporal_rate": channel_counts["temporal"] / repeats,
                "dominant_collective_rate": channel_counts["collective"] / repeats,
                "description": definition.description,
            }
        )
    return runs, family_rows


def aggregate_metrics(family_rows: Sequence[dict], engine: str) -> dict:
    rows = [row for row in family_rows if row["engine"] == engine]
    by_family = {row["family"]: row for row in rows}
    benign = [row for row in rows if row["scenario_group"] in {"control", "benign"}]
    strong = [row for row in rows if row["scenario_group"] == "attack"]
    evasive_observable = [
        row for row in rows
        if row["scenario_group"] == "evasive_attack" and row["desired_security_alert"]
    ]
    all_attacks = [row for row in rows if row["attack_present"]]

    def weighted_rate(selected: Sequence[dict], field: str) -> float:
        denominator = sum(row["runs"] for row in selected)
        return sum(row[field] * row["runs"] for row in selected) / denominator if denominator else 0.0

    return {
        "engine": engine,
        "benign_false_alert_rate": weighted_rate(benign, "security_alert_rate"),
        "strong_attack_recall": weighted_rate(strong, "security_alert_rate"),
        "evasive_observable_recall": weighted_rate(evasive_observable, "security_alert_rate"),
        "all_attack_operational_capture": weighted_rate(all_attacks, "operational_escalation_rate"),
        "overall_expected_route_rate": weighted_rate(rows, "expected_route_rate"),
        "low_and_slow_recall": by_family["low_and_slow_exfiltration"]["security_alert_rate"],
        "correlated_weak_recall": by_family["correlated_low_signal_intrusion"]["security_alert_rate"],
        "suppression_risk_capture": by_family["telemetry_suppression"]["operational_escalation_rate"],
        "lifecycle_route_accuracy": weighted_rate(
            [row for row in rows if row["scenario_group"] == "lifecycle"],
            "expected_route_rate",
        ),
    }


def _write_csv(path: Path, rows: Sequence[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--seed", type=int, default=20260904)
    parser.add_argument("--calibration-runs", type=int, default=900)
    parser.add_argument("--repeats", type=int, default=200)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    calibration = calibrate(
        calibration_scenarios(args.seed + 50_000_000, args.calibration_runs),
        quantile=0.99,
        target_false_alert_rate=0.01,
    )
    v7 = BlackSwanV7(calibration)
    v6 = BlackSwanV6Baseline(min_history=calibration.min_history)

    v6_runs, v6_families = evaluate_engine("v6_baseline", v6, seed=args.seed, repeats=args.repeats)
    v7_runs, v7_families = evaluate_engine("v7", v7, seed=args.seed, repeats=args.repeats)
    runs = v6_runs + v7_runs
    families = v6_families + v7_families
    aggregates = [aggregate_metrics(families, "v6_baseline"), aggregate_metrics(families, "v7")]

    _write_csv(args.output_dir / "black_swan_v7_run_results.csv", runs)
    _write_csv(args.output_dir / "black_swan_v7_family_summary.csv", families)
    _write_csv(args.output_dir / "black_swan_v7_engine_comparison.csv", aggregates)

    manifest_payload = {
        "benchmark_version": "v7-cybersecurity-sequential-1",
        "seed": args.seed,
        "calibration": asdict(calibration),
        "repeats_per_family": args.repeats,
        "scenario_count": len(SCENARIOS),
        "metric_count": len(METRICS),
        "engines": aggregates,
        "limitations": [
            "Synthetic aggregate telemetry is not a production IDS/EDR evaluation.",
            "The v6 comparator freezes the published v6 gates; it is not the original missing implementation.",
            "Context events are synthetic records and do not prove real-world causality.",
            "Calibration controls this generator distribution and must be repeated after domain shift.",
        ],
    }
    canonical = json.dumps(manifest_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest_payload["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    with (args.output_dir / "black_swan_v7_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest_payload, handle, ensure_ascii=False, indent=2)

    print(json.dumps(manifest_payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
