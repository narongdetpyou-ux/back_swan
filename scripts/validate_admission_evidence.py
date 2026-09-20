#!/usr/bin/env python3
"""Validate linkage, hashes, privacy paths, and the Phase-1 admission result."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from validate_real_world_dataset import validate_manifest


REQUIRED = {
    "dataset_manifest.json", "data_quality_report.json", "metric_mapping.json",
    "split_manifest.json", "checksums.json", "validation.log", "admission_decision.json",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def validate(directory: Path) -> list[str]:
    errors: list[str] = []
    missing = sorted(name for name in REQUIRED if not (directory / name).is_file())
    if missing:
        return ["missing required artifact: " + name for name in missing]
    try:
        docs = {name: json.loads((directory / name).read_text(encoding="utf-8")) for name in REQUIRED if name.endswith(".json")}
    except (OSError, json.JSONDecodeError) as exc:
        return [f"evidence JSON unreadable: {type(exc).__name__}"]

    manifest = docs["dataset_manifest.json"]
    errors.extend(f"dataset_manifest.json: {item}" for item in validate_manifest(manifest))
    identity = (manifest.get("dataset_id"), manifest.get("revision"), manifest.get("evidence_link_sha256"))
    if not SHA256_RE.fullmatch(str(identity[2])):
        errors.append("dataset_manifest.json: invalid evidence_link_sha256")
    for name, doc in docs.items():
        if (doc.get("dataset_id"), doc.get("revision"), doc.get("evidence_link_sha256")) != identity:
            errors.append(f"{name}: dataset revision linkage mismatch")

    expected_link = hashlib.sha256(f"{identity[0]}:{identity[1]}".encode()).hexdigest()
    if identity[2] != expected_link:
        errors.append("evidence_link_sha256 does not match dataset_id:revision")
    checksums = docs["checksums.json"].get("evidence_artifacts", {})
    for name in REQUIRED - {"checksums.json"}:
        actual = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        if checksums.get(name) != actual:
            errors.append(f"{name}: SHA-256 mismatch")

    for role in ("raw", "features", "labels"):
        path = manifest.get("inputs", {}).get(role, {}).get("path_or_uri", "")
        required_prefix = f"data/private/{identity[0]}/"
        if not path.startswith(required_prefix):
            errors.append(f"inputs.{role}.path_or_uri: must be under {required_prefix}")
    decision = docs["admission_decision.json"]
    if decision.get("decision") not in {"ADMITTED", "CONDITIONAL", "REJECTED"}:
        errors.append("admission_decision.json: unsupported decision")
    if decision.get("phase_2_started") is not False:
        errors.append("admission_decision.json: Phase 2 must not be started")
    log = (directory / "validation.log").read_text(encoding="utf-8")
    for value in identity:
        if str(value) not in log:
            errors.append("validation.log: missing dataset revision linkage")
            break
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence_directory", type=Path)
    args = parser.parse_args()
    errors = validate(args.evidence_directory)
    print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
