# Change log

## 2026-09-20 — Validation phases and repository status sync

- Complete Phase 1 Dataset Admission Contract with manifest validator, valid/invalid fixtures, six contract tests and GitHub CI.
- Verify the full repository regression at 85/85 tests on the Phase 1 CI run; keep Logic v8 decision code and thresholds unchanged.
- Add the Phase 2 Experiment & Attack Scenario Contract with G01–G15 acceptance gates; execution and blind evaluation remain not started.
- Record completion of the one-time credential-path history purge while keeping upstream revoke/rotate status explicitly unverified.
- Add repository-wide CI for `main` and pull requests; update Colab and archive workflows to follow current `main` paths.
- Close redundant PR #7 after all seven changed blobs matched `main`; keep PR #6 open and blocked because its telemetry admission is rejected and its branch reported 84/85 tests.
- Refresh README and project status without claiming production readiness, real-world accuracy or a complete external raw-byte backup.

## 2026-09-04 — Storage policy and experiment records

- Keep `back_swan` repository / `black_swan` package mapping explicit.
- Add UTC-unique run IDs, finalized manifests, source/config and artifact SHA-256, honest Git identity for snapshots, and failure/timeout recording.
- Integrate manifests into regression checks and v8 evaluation; reject reused run directories and incompatible evaluation flags.
- Add automatic snapshot SHA-256 sidecars and checked, non-overwriting restoration.
- Add 13 workflow tests; all 46 tests pass. Repeat v8 quality: all 1,900 rows match the original; no new load sweep or model logic changes.
- Preserve checked run evidence and losslessly compressed results; document private external backup destination awaiting confirmation/upload.

## 2026-09-04 — Repository recovery and organization

- Merge PR #1 to remove tracked credential from main and add ignore rules; revocation remains unverified.
- Recover the original v8 engine/runtime, tests, evaluation, status and report from its checked ZIP.
- Make v8 the canonical `black_swan` package and retain original v7 reference math.
- Restore empty historical reports and stress-test artifacts from the saved originals.
- Separate source, tests, benchmarks, configs, data, experiments, reports and immutable releases.
- Preserve engine/runtime function/class AST and original v8 test-class AST during relocation.
- Add inventory/hash checks, reproducible regression runner and checked current-file snapshot export.
- Preserve original results; relocated evaluator uses new output paths and source hashes.

This is packaging/recovery of existing Logic v8, not a newly trained model or a change to detection thresholds.
