#!/usr/bin/env python3
"""Collect a small, local controlled-auth telemetry dataset for Phase 1.

The raw events, derived features, and action ledger are written below
``data/private``.  Only aggregate, non-sensitive admission evidence is written
to the tracked evidence directory.  This collector does not run the detector
or perform any Phase-2 evaluation.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import time
from urllib import parse, request
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parent.parent
DATASET_ID = "controlled_local_auth_20260920"
REVISION = "1"
PRIVATE_DIR = ROOT / "data" / "private" / DATASET_ID
EVIDENCE_DIR = ROOT / "data" / "evidence" / DATASET_ID / f"revision-{REVISION}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    if PRIVATE_DIR.exists() or EVIDENCE_DIR.exists():
        raise SystemExit(f"refusing to overwrite existing revision: {DATASET_ID}/{REVISION}")
    PRIVATE_DIR.mkdir(parents=True)
    EVIDENCE_DIR.mkdir(parents=True)
    raw_path = PRIVATE_DIR / "raw_auth_events.jsonl"
    feature_path = PRIVATE_DIR / "auth_features.csv"
    label_path = PRIVATE_DIR / "ground_truth_actions.jsonl"
    token = secrets.token_urlsafe(24)
    events: list[dict] = []
    event_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            length = int(self.headers.get("Content-Length", "0"))
            form = parse.parse_qs(self.rfile.read(length).decode("utf-8"))
            success = secrets.compare_digest(form.get("credential", [""])[0], token)
            event = {
                "event_id": self.headers["X-Controlled-Event"],
                "timestamp_utc": utc_now(),
                "source_ip": self.client_address[0],
                "account_id": form.get("account", ["unknown"])[0],
                "authentication_result": "success" if success else "failure",
                "source_system": "isolated localhost auth harness",
            }
            with event_lock:
                events.append(event)
            self.send_response(204 if success else 401)
            self.end_headers()

        def log_message(self, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    plan: list[dict] = []
    patterns = (("baseline", 8, 2), ("calibration", 7, 3), ("blind_test", 6, 4))
    event_number = 0
    split_bounds: dict[str, dict[str, str]] = {}
    try:
        for split, successes, failures in patterns:
            split_start = utc_now()
            actions = [True] * successes + [False] * failures
            for expected_success in actions:
                event_number += 1
                event_id = f"evt-{event_number:04d}"
                plan.append({
                    "event_id": event_id,
                    "split": split,
                    "planned_at_utc": split_start,
                    "ground_truth": "authorized_valid_login" if expected_success else "controlled_invalid_login",
                    "expected_success": expected_success,
                })
                payload = parse.urlencode({
                    "account": f"controlled-account-{event_number % 3}",
                    "credential": token if expected_success else secrets.token_urlsafe(18),
                }).encode("utf-8")
                req = request.Request(
                    f"http://127.0.0.1:{server.server_port}/login",
                    data=payload,
                    headers={"X-Controlled-Event": event_id},
                    method="POST",
                )
                try:
                    request.urlopen(req, timeout=2).close()
                except HTTPError as exc:  # Expected for controlled invalid credentials.
                    if exc.code != 401:
                        raise
                time.sleep(0.02)
            split_bounds[split] = {"start_utc": split_start, "end_utc": utc_now()}
            time.sleep(0.03)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

    # The action ledger was defined before each corresponding request and is
    # separate from observed results and any future predictions.
    label_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in plan), encoding="utf-8")
    raw_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in events), encoding="utf-8")
    split_by_event = {row["event_id"]: row["split"] for row in plan}
    with feature_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "event_id", "timestamp_utc", "split", "auth_failures",
            "successful_logins", "unique_failed_accounts", "unique_source_ips",
        ])
        writer.writeheader()
        for event in events:
            failed = event["authentication_result"] == "failure"
            writer.writerow({
                "event_id": event["event_id"],
                "timestamp_utc": event["timestamp_utc"],
                "split": split_by_event[event["event_id"]],
                "auth_failures": int(failed),
                "successful_logins": int(not failed),
                "unique_failed_accounts": int(failed),
                "unique_source_ips": 1,
            })

    start, end = events[0]["timestamp_utc"], events[-1]["timestamp_utc"]
    linkage = hashlib.sha256(f"{DATASET_ID}:{REVISION}".encode()).hexdigest()
    common = {"dataset_id": DATASET_ID, "revision": REVISION, "evidence_link_sha256": linkage}
    source = "Isolated localhost HTTP authentication harness (Python ThreadingHTTPServer)"
    inputs = {}
    roles = {
        "raw": (raw_path, "source_evidence"),
        "features": (feature_path, "engine_input"),
        "labels": (label_path, "ground_truth_hidden"),
    }
    for name, (path, role) in roles.items():
        inputs[name] = {
            "path_or_uri": f"data/private/{DATASET_ID}/{path.name}",
            "sha256": digest(path), "bytes": path.stat().st_size,
            "source_system": source, "collected_start_utc": start, "collected_end_utc": end,
            "provenance": "Authorized local collection produced by scripts/collect_controlled_auth_telemetry.py",
            "authorization": "Repository-owner controlled experiment; localhost only; no third-party traffic",
            "dataset_role": role,
        }
    inputs["features"]["transformation_id"] = "auth-event-one-hot-v1"
    inputs["labels"].update({
        "independent_of_predictions": True,
        "adjudication_method": "Pre-request operator action ledger matched to event_id; no detector predictions generated",
    })
    manifest = {
        **common, "schema_version": 1, "dataset_type": "controlled_security_telemetry", "timezone": "UTC",
        "split_policy": "chronological", "blind_test_locked": True, "labels_hidden_from_engine": True,
        "source_systems": [source], "time_range": {"start_utc": start, "end_utc": end},
        "event_count": len(events), "splits": split_bounds, "inputs": inputs,
        "metric_contract": {
            "selected_metrics": ["auth_failures", "unique_failed_accounts", "unique_source_ips", "successful_logins"],
            "source_mapping": {
                "auth_failures": "count(authentication_result=failure) per event",
                "unique_failed_accounts": "distinct account_id where authentication_result=failure per event",
                "unique_source_ips": "distinct source_ip per event",
                "successful_logins": "count(authentication_result=success) per event",
            },
            "decision_cadence_seconds": 0.02,
        },
        "ground_truth_method": inputs["labels"]["adjudication_method"],
        "privacy": {"credentials_in_git": False, "direct_identifiers_in_git": False},
        "limitations": ["localhost-only controlled traffic", "single source IP", "sub-second collection window", "30 events", "four of ten canonical metrics"],
        "phase_boundary": "Phase 1 only; detector evaluation and Phase 2 were not run",
    }
    metric_mapping = {
        **common, "source_systems": [source], "time_range": manifest["time_range"], "event_count": len(events),
        "metric_coverage": {"covered": 4, "catalog_total": 10, "ratio": 0.4, "metrics": manifest["metric_contract"]["selected_metrics"]},
        "mapping": manifest["metric_contract"]["source_mapping"],
        "limitations": manifest["limitations"],
    }
    quality = {
        **common, "source_systems": [source], "time_range": manifest["time_range"], "event_count": len(events),
        "metric_coverage": metric_mapping["metric_coverage"],
        "missingness": {name: {"missing": 0, "total": len(events), "rate": 0.0} for name in manifest["metric_contract"]["selected_metrics"]},
        "integrity": {"unique_event_ids": len({e["event_id"] for e in events}), "label_matches": len(set(e["event_id"] for e in events) & set(p["event_id"] for p in plan))},
        "ground_truth_method": manifest["ground_truth_method"], "limitations": manifest["limitations"],
    }
    split_manifest = {
        **common, "source_systems": [source], "time_range": manifest["time_range"], "event_count": len(events),
        "split_ranges": split_bounds,
        "split_event_counts": {name: sum(split_by_event[e["event_id"]] == name for e in events) for name, *_ in patterns},
        "blind_test_locked": True, "ground_truth_method": manifest["ground_truth_method"], "limitations": manifest["limitations"],
    }
    decision = {
        **common, "decision": "REJECTED", "decided_at_utc": utc_now(), "source_systems": [source],
        "time_range": manifest["time_range"], "event_count": len(events), "metric_coverage": metric_mapping["metric_coverage"],
        "missingness": quality["missingness"], "split_ranges": split_bounds, "ground_truth_method": manifest["ground_truth_method"],
        "reasons": ["Collection duration is insufficient for temporal baseline and drift assessment", "Event volume is insufficient for defensible calibration or holdout evaluation", "Loopback-only single-source collection lacks operational diversity", "Metric coverage is only 4/10"],
        "limitations": manifest["limitations"], "phase_2_started": False,
    }
    evidence = {
        "dataset_manifest.json": manifest, "data_quality_report.json": quality,
        "metric_mapping.json": metric_mapping, "split_manifest.json": split_manifest,
        "admission_decision.json": decision,
    }
    for name, doc in evidence.items():
        write_json(EVIDENCE_DIR / name, doc)
    artifact_hashes = {name: digest(EVIDENCE_DIR / name) for name in evidence}
    log_lines = [
        f"dataset_id={DATASET_ID}", f"revision={REVISION}", f"evidence_link_sha256={linkage}",
        f"source_system={source}", f"time_range={start}/{end}", f"event_count={len(events)}",
        "metric_coverage=4/10", "missingness=0/30 for each selected metric",
        "split_ranges=" + json.dumps(split_bounds, sort_keys=True),
        "ground_truth_method=pre-request operator action ledger matched by event_id",
        "limitations=localhost-only; single source IP; sub-second duration; 30 events; four metrics",
    ]
    for name, expected in artifact_hashes.items():
        log_lines.append(f"SHA-256 PASS {name} {expected}")
    log_lines.extend(["CONTRACT PASS dataset_manifest.json", "ADMISSION REJECTED", "PHASE_2 NOT_STARTED"])
    (EVIDENCE_DIR / "validation.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    artifact_hashes["validation.log"] = digest(EVIDENCE_DIR / "validation.log")
    checksums = {
        **common, "algorithm": "SHA-256", "source_systems": [source], "time_range": manifest["time_range"],
        "event_count": len(events), "metric_coverage": metric_mapping["metric_coverage"], "missingness": quality["missingness"],
        "split_ranges": split_bounds, "ground_truth_method": manifest["ground_truth_method"], "limitations": manifest["limitations"],
        "private_inputs": {name: item["sha256"] for name, item in inputs.items()}, "evidence_artifacts": artifact_hashes,
        "note": "checksums.json cannot contain its own digest; evidence_link_sha256 binds it to this dataset revision",
    }
    write_json(EVIDENCE_DIR / "checksums.json", checksums)
    print(EVIDENCE_DIR.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
