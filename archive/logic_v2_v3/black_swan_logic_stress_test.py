#!/usr/bin/env python3
"""
Stress-test for the Black Swan detection logic.

Goal:
1) Test detection under variable shock size instead of a fixed +50.
2) Add realistic normal noise and gradual drift.
3) Measure TP/FN/FP/TN, Recall, Precision, FPR.
4) Separate DETECTION from ACTION.
5) Compare two detector styles:
   v2 = change-based detector
   v3 = gap-based detector

This is a testing harness based on the logic visible in the screenshots.
It is intentionally parameterized so thresholds and distributions can be changed.
"""

from dataclasses import dataclass
import random
import math
import csv

@dataclass
class Metrics:
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0

    @property
    def recall(self):
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

    @property
    def precision(self):
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0

    @property
    def fpr(self):
        return self.fp / (self.fp + self.tn) if (self.fp + self.tn) else 0.0

    @property
    def accuracy(self):
        total = self.tp + self.fp + self.tn + self.fn
        return (self.tp + self.tn) / total if total else 0.0


def percentile(values, p):
    if not values:
        return 0.0
    xs = sorted(values)
    k = (len(xs) - 1) * p
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def robust_scale(values):
    """MAD-based robust scale, avoids letting one shock define the threshold."""
    if len(values) < 5:
        return max(1e-9, math.sqrt(sum(v*v for v in values) / max(1, len(values))))
    med = percentile(values, 0.50)
    mad = percentile([abs(v - med) for v in values], 0.50)
    return max(1e-9, 1.4826 * mad)


def simulate(
    *,
    trials=200,
    steps=200,
    black_swan_prob=0.20,
    shock=10.0,
    noise_sigma=2.0,
    drift_sigma=0.15,
    threshold_mult=3.0,
    seed=42,
):
    rng = random.Random(seed)

    m2 = Metrics()
    m3 = Metrics()

    # Action-layer metrics:
    # "good action" = action on a true Black Swan, no action on normal.
    action_correct_2 = action_correct_3 = 0
    action_total = 0
    response_2 = response_3 = 0

    # Keep enough examples to estimate a baseline without future information.
    warmup = 25

    for _ in range(trials):
        expected_prev = 100.0
        actual_prev = 100.0
        history_deltas = []

        for t in range(steps):
            expected = expected_prev + rng.gauss(0.0, drift_sigma)
            normal_delta = rng.gauss(0.0, noise_sigma)
            is_bs = rng.random() < black_swan_prob

            # True process. The Black Swan shock can be positive or negative.
            sign = -1.0 if rng.random() < 0.20 else 1.0
            actual = expected + normal_delta + (sign * shock if is_bs else 0.0)

            # Observed one-step changes
            actual_delta = actual - actual_prev
            expected_delta = expected - expected_prev

            # -------------------------
            # v2: change-based detector
            # -------------------------
            delta_gap = actual_delta - expected_delta
            history_deltas.append(delta_gap)
            baseline = robust_scale(history_deltas[-warmup:])
            detected2 = len(history_deltas) >= warmup and abs(delta_gap) > threshold_mult * baseline

            # -------------------------
            # v3: gap-based detector
            # -------------------------
            gap = actual - expected
            # Use a rolling scale of prior residuals; current point is not allowed
            # to inflate its own threshold.
            prior = history_deltas[:-1][-warmup:] if len(history_deltas) > 1 else []
            base3 = robust_scale(prior) if len(prior) >= 5 else max(noise_sigma, 1e-9)
            detected3 = len(history_deltas) >= warmup and abs(gap) > threshold_mult * base3

            # Detection metrics
            for detected, m in ((detected2, m2), (detected3, m3)):
                if is_bs and detected:
                    m.tp += 1
                elif (not is_bs) and detected:
                    m.fp += 1
                elif (not is_bs) and (not detected):
                    m.tn += 1
                else:
                    m.fn += 1

            # -------------------------
            # Separate action layer
            # -------------------------
            # Risk score: deviation relative to baseline risk.
            # X < 1 => ACTION, following the screenshot's decision convention.
            risk2 = abs(delta_gap) / max(threshold_mult * baseline, 1e-9)
            risk3 = abs(gap) / max(threshold_mult * base3, 1e-9)

            action2 = (detected2 or risk2 >= 1.0)
            action3 = (detected3 or risk3 >= 1.0)

            if is_bs:
                response_2 += int(action2)
                response_3 += int(action3)
            action_correct_2 += int(action2 == is_bs)
            action_correct_3 += int(action3 == is_bs)
            action_total += 1

            expected_prev = expected
            actual_prev = actual

    return {
        "v2": m2,
        "v3": m3,
        "action_accuracy_v2": action_correct_2 / action_total,
        "action_accuracy_v3": action_correct_3 / action_total,
        "response_rate_v2": response_2 / max(1, trials * steps * black_swan_prob),
        "response_rate_v3": response_3 / max(1, trials * steps * black_swan_prob),
    }


def main():
    rows = []

    # Core stress matrix:
    # shock amplitude, noise level, and Black Swan frequency.
    shocks = [2, 3, 5, 8, 10, 15, 20, 30, 50]
    noises = [1, 2, 4]
    probabilities = [0.08, 0.20, 0.35]

    for noise in noises:
        for prob in probabilities:
            for shock in shocks:
                result = simulate(
                    trials=200,
                    steps=200,
                    black_swan_prob=prob,
                    shock=shock,
                    noise_sigma=noise,
                    threshold_mult=3.0,
                    seed=1000 + int(shock * 10 + noise * 100 + prob * 1000),
                )
                for version in ("v2", "v3"):
                    m = result[version]
                    rows.append({
                        "version": version,
                        "noise_sigma": noise,
                        "black_swan_prob": prob,
                        "shock": shock,
                        "tp": m.tp,
                        "fn": m.fn,
                        "fp": m.fp,
                        "tn": m.tn,
                        "recall": m.recall,
                        "precision": m.precision,
                        "false_positive_rate": m.fpr,
                        "accuracy": m.accuracy,
                        "action_accuracy": result[f"action_accuracy_{version}"],
                        "response_rate_on_true_bs": result[f"response_rate_{version}"],
                    })

    with open("black_swan_logic_stress_test_results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    # Human-readable summary
    print("=" * 78)
    print("BLACK SWAN LOGIC STRESS TEST")
    print("=" * 78)
    print("A fixed +50 shock is NOT used. Shock size is swept from 2 to 50.")
    print("Normal noise is swept across sigma = 1, 2, 4.")
    print("Black Swan probability is swept across 8%, 20%, 35%.")
    print()

    # Print compact table for noise=2 and probability=20%, which is a useful baseline.
    print("BASELINE: noise_sigma=2, black_swan_prob=20%, threshold=3x robust scale")
    print("Shock | v2 Recall | v2 Prec | v2 FPR | v3 Recall | v3 Prec | v3 FPR")
    print("-" * 78)
    for shock in shocks:
        for version_pair in [("v2", "v3")]:
            a = next(r for r in rows if r["version"] == "v2" and r["noise_sigma"] == 2 and
                     abs(r["black_swan_prob"] - 0.20) < 1e-9 and r["shock"] == shock)
            b = next(r for r in rows if r["version"] == "v3" and r["noise_sigma"] == 2 and
                     abs(r["black_swan_prob"] - 0.20) < 1e-9 and r["shock"] == shock)
            print(f"{shock:>5} | {a['recall']*100:>9.2f}% | {a['precision']*100:>7.2f}% | "
                  f"{a['false_positive_rate']*100:>6.2f}% | {b['recall']*100:>9.2f}% | "
                  f"{b['precision']*100:>7.2f}% | {b['false_positive_rate']*100:>6.2f}%")

    print()
    print("Interpretation:")
    print("- Small shocks near the normal noise floor are the important failure region.")
    print("- Precision alone is not enough: watch false-positive rate and recall together.")
    print("- v2 and v3 are being tested under the same random process.")
    print("- Detection and action are reported separately so a correct detector cannot hide")
    print("  a poor action policy, and vice versa.")
    print()
    print("CSV written to: black_swan_logic_stress_test_results.csv")


if __name__ == "__main__":
    main()
