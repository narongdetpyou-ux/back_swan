# Evaluation splits

v7 calibration uses 900 context-free benign simulations with a separate seed stream from holdout evaluation. The saved v7 manifest contains seed 20260904 and repeats 200 across 19 families.

The original v8 evaluation uses fresh seeds from the same synthetic generator; exact per-case seeds are retained in `experiments/20260904T033307Z_v8_original/results.json`. This is not an independently collected real-world test set.

For a real dataset, add explicit timestamp ranges/entity exclusions or a case-ID manifest here before tuning. Keep calibration, validation and final holdout separate. Do not infer a real train/test split from the synthetic files.
