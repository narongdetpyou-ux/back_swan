#!/usr/bin/env python3
"""Validate a Phase-1 real-world telemetry dataset manifest.

This validates dataset identity, provenance, chronological split isolation and
ground-truth separation. It does not inspect private telemetry content and does
not run Black Swan detection logic.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = ROOT / "configs" / "real_world_validation_v1.json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractError(ValueError):
    pass


def _utc(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ContractError(f"{field}: must be UTC ISO-8601 ending in Z")
    try:
        dt = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ContractError(f"{field}: invalid ISO-8601 timestamp") from exc
    if dt.tzinfo != timezone.utc:
        raise ContractError(f"{field}: must be UTC")
    return dt


def _input_errors(name: str, item: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(item, dict):
        return [f"inputs.{name}: must be an object"]
    required = {
        "path_or_uri", "sha256", "bytes", "source_system",
        "collected_start_utc", "collected_end_utc",
        "provenance", "authorization"
    }
    for key in sorted(required - set(item)):
        errors.append(f"inputs.{name}.{key}: missing")
    path = item.get("path_or_uri")
    if not isinstance(path, str) or not path.strip():
        errors.append(f"inputs.{name}.path_or_uri: must be non-empty")
    digest = item.get("sha256")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest.lower()):
        errors.append(f"inputs.{name}.sha256: must be 64 lowercase hex characters")
    size = item.get("bytes")
    if type(size) is not int or size < 0:
        errors.append(f"inputs.{name}.bytes: must be a non-negative integer")
    for key in ("source_system", "provenance", "authorization"):
        value = item.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"inputs.{name}.{key}: must be non-empty")
    try:
        start = _utc(item.get("collected_start_utc"), f"inputs.{name}.collected_start_utc")
        end = _utc(item.get("collected_end_utc"), f"inputs.{name}.collected_end_utc")
        if end <= start:
            errors.append(f"inputs.{name}: collection end must be after start")
    except ContractError as exc:
        errors.append(str(exc))
    return errors


def validate_manifest(doc: object, contract: dict | None = None) -> list[str]:
    if contract is None:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        return ["manifest: top-level JSON value must be an object"]

    errors: list[str] = []
    required_top = {
        "schema_version", "dataset_id", "dataset_type", "timezone",
        "split_policy", "blind_test_locked", "labels_hidden_from_engine",
        "splits", "inputs", "metric_contract", "privacy"
    }
    for key in sorted(required_top - set(doc)):
        errors.append(f"{key}: missing")

    if doc.get("schema_version") != contract["schema_version"]:
        errors.append("schema_version: unsupported")
    if not isinstance(doc.get("dataset_id"), str) or not doc.get("dataset_id", "").strip():
        errors.append("dataset_id: must be non-empty")
    if doc.get("dataset_type") not in contract["dataset_types"]:
        errors.append("dataset_type: unsupported")
    if doc.get("timezone") != "UTC":
        errors.append("timezone: must be UTC")
    if doc.get("split_policy") != "chronological":
        errors.append("split_policy: must be chronological")
    if doc.get("blind_test_locked") is not True:
        errors.append("blind_test_locked: must be true before evaluation")
    if doc.get("labels_hidden_from_engine") is not True:
        errors.append("labels_hidden_from_engine: must be true")

    splits = doc.get("splits")
    parsed: dict[str, tuple[datetime, datetime]] = {}
    if not isinstance(splits, dict):
        errors.append("splits: must be an object")
    else:
        for name in contract["split_policy"]["required_splits"]:
            item = splits.get(name)
            if not isinstance(item, dict):
                errors.append(f"splits.{name}: missing or invalid")
                continue
            try:
                start = _utc(item.get("start_utc"), f"splits.{name}.start_utc")
                end = _utc(item.get("end_utc"), f"splits.{name}.end_utc")
                if end <= start:
                    errors.append(f"splits.{name}: end must be after start")
                else:
                    parsed[name] = (start, end)
            except ContractError as exc:
                errors.append(str(exc))
        if all(k in parsed for k in ("baseline", "calibration", "blind_test")):
            b, c, h = parsed["baseline"], parsed["calibration"], parsed["blind_test"]
            if b[1] > c[0]:
                errors.append("splits: baseline overlaps calibration")
            if c[1] > h[0]:
                errors.append("splits: calibration overlaps blind_test")
            if not (b[0] < c[0] < h[0]):
                errors.append("splits: must be ordered baseline -> calibration -> blind_test")

    inputs = doc.get("inputs")
    if not isinstance(inputs, dict):
        errors.append("inputs: must be an object")
    else:
        for name in contract["required_dataset_inputs"]:
            errors.extend(_input_errors(name, inputs.get(name)))
        labels = inputs.get("labels")
        if isinstance(labels, dict):
            if labels.get("dataset_role") != "ground_truth_hidden":
                errors.append("inputs.labels.dataset_role: must be ground_truth_hidden")
            if labels.get("independent_of_predictions") is not True:
                errors.append("inputs.labels.independent_of_predictions: must be true")
            if not isinstance(labels.get("adjudication_method"), str) or not labels.get("adjudication_method", "").strip():
                errors.append("inputs.labels.adjudication_method: must be non-empty")
        features = inputs.get("features")
        if isinstance(features, dict):
            if features.get("dataset_role") != "engine_input":
                errors.append("inputs.features.dataset_role: must be engine_input")
            if not isinstance(features.get("transformation_id"), str) or not features.get("transformation_id", "").strip():
                errors.append("inputs.features.transformation_id: must be non-empty")
        raw = inputs.get("raw")
        if isinstance(raw, dict) and raw.get("dataset_role") != "source_evidence":
            errors.append("inputs.raw.dataset_role: must be source_evidence")

    metric = doc.get("metric_contract")
    catalog = set(contract["canonical_metric_catalog"])
    if not isinstance(metric, dict):
        errors.append("metric_contract: must be an object")
    else:
        selected = metric.get("selected_metrics")
        mapping = metric.get("source_mapping")
        if not isinstance(selected, list) or not selected:
            errors.append("metric_contract.selected_metrics: must be a non-empty list")
            selected = []
        elif len(selected) != len(set(selected)):
            errors.append("metric_contract.selected_metrics: duplicates are not allowed")
        unknown = sorted(set(selected) - catalog)
        if unknown:
            errors.append("metric_contract.selected_metrics: unknown metrics " + ",".join(unknown))
        if not isinstance(mapping, dict):
            errors.append("metric_contract.source_mapping: must be an object")
        else:
            for name in selected:
                value = mapping.get(name)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"metric_contract.source_mapping.{name}: missing")
        cadence = metric.get("decision_cadence_seconds")
        if type(cadence) not in (int, float) or isinstance(cadence, bool) or cadence <= 0:
            errors.append("metric_contract.decision_cadence_seconds: must be > 0")

    privacy = doc.get("privacy")
    if not isinstance(privacy, dict):
        errors.append("privacy: must be an object")
    else:
        if privacy.get("credentials_in_git") is not False:
            errors.append("privacy.credentials_in_git: must be false")
        if privacy.get("direct_identifiers_in_git") is not False:
            errors.append("privacy.direct_identifiers_in_git: must be false")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        doc = json.loads(args.manifest.read_text(encoding="utf-8"))
        errors = validate_manifest(doc)
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "errors": [type(exc).__name__]}, indent=2))
        return 2
    result = {"valid": not errors, "errors": errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
