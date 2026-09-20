# Phase-1 telemetry admission evidence

Each `<dataset_id>/revision-<revision>/` directory contains only aggregate,
non-sensitive evidence. Raw events, features, and labels remain under the
Git-ignored `data/private/<dataset_id>/` path (or an explicitly private external
URI). Evidence can be checked without reading private telemetry:

```bash
python3 scripts/validate_admission_evidence.py \
  data/evidence/controlled_local_auth_20260920/revision-1
```

An `ADMITTED` decision only admits a dataset to the next review gate; it does
not authorize Phase 2 automatically. The recorded revision must always state
`phase_2_started: false` at this boundary.
