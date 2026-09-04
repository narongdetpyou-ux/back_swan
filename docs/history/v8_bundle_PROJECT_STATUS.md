# Black Swan continuation record

Status: v8 implementation/evaluation cycle complete; production and 10k full-decisions/s target NOT complete.

Delivery blocker: persistent save was attempted but failed with `Library prepare_uploads is not available`. No v8 artifact is confirmed saved persistently. The verified bundle and individual files currently exist in this session; download them or resume persistent saving when the normal channel is available. Do not claim a successful persistent save.

## Verified starting point

- Actual saved v7 source inspected and reproduced, SHA-256 `9f0d58ebad4f09f7be1be23e7b76520f904472f8e877391d8895c872cedbe663`.
- Prior audit measured 9 engine exceptions among 27 control/malformed/config edge cases, silent no-alerts on empty/NaN, and attack suppression through unverified context/unrelated lifecycle.
- v7 remains unchanged. Fixed calibration retained; no threshold tuning.

## Implemented

- `black_swan_v8_engine.py`: input/calibration validation, explicit review, per-metric exclusion, operator-installed trusted context registry, bounded content-keyed cache, immutable registered-history updates.
- `black_swan_v8_runtime.py`: bounded local queue, per-worker pipes, active deadline kill/restart, cancellation, transport type/size preflight.
- `test_black_swan_v8.py`: 24 tests including 27 audit cases, 450 reference comparisons, 300 malformed fuzz fixtures, 60 full-vs-prepared comparisons, cache/snapshot/thread invariants and runtime faults.
- `evaluate_black_swan_v8.py`: paired latency, fresh-seed quality/novel patterns, fault injection, controlled-offering local load and 30s mini-soak.

## Final observed results (2026-09-04)

- Unit tests: 24/24 pass in 5.724s in stored final run.
- Full-input mean: v7 2.271637 ms; v8 warm 0.746902 ms, P99 2.433015 ms.
- Registered-window mean: 0.288436 ms, P99 0.889266 ms; preparation excluded and conditions differ from full input.
- Complete-input held-out subset: exact score/route agreement 1500/1500, out of 1900 synthetic scenarios.
- Strong alerts 600/600; evasive observable 286/300; benign false alerts 1/600 with synthetic trusted fixtures. Empty trust registry benign alerts 348/600.
- 27 audit cases return finite JSON-safe outcomes, with data/config problems in review and strong mixed-fault attacks retaining alert.
- Fault stall cutoffs 250.525–250.889 ms for 250ms budget, recovery successful after every stall/crash/exception; zero workers after fault-runtime close.
- Registered-window 1000/s for 30s: offered/computed 30000, rejected/timeouts/pending 0; E2E P95 4.70ms/P99 33.58ms.
- High-rate tests do NOT meet 10k. Full-payload emitter/ingress reaches only ~1653–1819/s on attempted 10k runs; registered mode reaches near 10k offering but rejects most requests.
- RSS telemetry incomplete in environment; raw zero readings mean unavailable, not zero RAM. Do not use it for sizing.

## Reproduce

```bash
python3 -m unittest discover -s black_swan_v8 -p test_black_swan_v8.py -v
python3 -m unittest discover -s black_swan_v7 -p test_black_swan_v7.py -v
python3 black_swan_v8/evaluate_black_swan_v8.py --output black_swan_v8/rerun_results.json
```

## Limits / next action

- No production traffic, external deployment, real context authentication or raw-event ingestion implemented.
- No universal zero-day detection, no calibrated OOD confidence, no production SLA. Weak patterns can remain silent.
- Next engineering task: profile/refactor ingress and IPC, separate load generator, evaluate bounded batching without changing outcomes; then establish sustained target rate with no rejection/timeouts. Keep fixed labels/splits and record new conditions.
- Registered histories require operator freshness/revision updates; trusted contexts require a real verified source and authorization boundary.
- Canonical final evidence is `v8_evaluation_results.json`; iteration-1 results are intermediate and not the final runtime configuration.
