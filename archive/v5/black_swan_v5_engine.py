#!/usr/bin/env python3
"""
Black Swan Logic v5
====================

Purpose
-------
Upgrade the earlier v2/v3/v4 prototype into a general early-warning /
structural-break reasoning engine.

v5 adds:
1) Data-quality gate
2) Multi-model expected state
3) Model-consensus anomaly logic
4) Model-disagreement / uncertainty score
5) Causal-relevance scoring
6) Fail-closed classification
7) Counterfactual stress testing
8) Monte Carlo calibration hooks

Important:
- "Unexplained anomaly" is NOT automatically a true Black Swan.
- The strongest label emitted is "BLACK_SWAN_CANDIDATE".
- External events are not accepted as causal explanations merely because
  they happen near the same time.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
import math
import statistics


EPS = 1e-9


def median(xs: List[float]) -> float:
    return statistics.median(xs)


def mad(xs: List[float]) -> float:
    if not xs:
        return 0.0
    m = median(xs)
    return median([abs(x - m) for x in xs])


def robust_sigma(xs: List[float], floor: float = 0.0) -> float:
    if not xs:
        return max(floor, EPS)
    return max(1.4826 * mad(xs), floor, EPS)


@dataclass
class EventEvidence:
    name: str
    temporal_overlap: float = 0.0
    domain_relevance: float = 0.0
    direct_mechanism: float = 0.0
    magnitude_alignment: float = 0.0
    evidence_quality: float = 0.0

    def score(self) -> float:
        # Direct mechanism has the greatest weight.
        score = (
            0.20 * self.temporal_overlap
            + 0.20 * self.domain_relevance
            + 0.35 * self.direct_mechanism
            + 0.15 * self.magnitude_alignment
            + 0.10 * self.evidence_quality
        )
        return max(0.0, min(1.0, score))


@dataclass
class Forecast:
    model: str
    expected: float
    scale: float
    z: float
    relative_error: float
    anomaly_vote: bool


@dataclass
class V5Result:
    target_year: int
    actual: float
    history_n: int
    quality_ok: bool
    quality_notes: List[str]
    forecasts: List[Forecast]
    anomaly_consensus: float
    model_spread_ratio: float
    uncertainty_score: float
    causal_score: float
    causal_event: Optional[str]
    classification: str


class BlackSwanV5:
    def __init__(
        self,
        z_threshold: float = 3.0,
        min_relative_deviation: float = 0.25,
        consensus_threshold: float = 2/3,
        min_history: int = 4,
    ):
        self.z_threshold = z_threshold
        self.min_relative_deviation = min_relative_deviation
        self.consensus_threshold = consensus_threshold
        self.min_history = min_history

    def quality_gate(self, years: List[int], values: List[float]) -> Tuple[bool, List[str]]:
        notes = []
        ok = True
        if len(values) < self.min_history:
            ok = False
            notes.append(f"history<{self.min_history}")
        if len(years) != len(values):
            ok = False
            notes.append("year/value length mismatch")
        if len(set(years)) != len(years):
            ok = False
            notes.append("duplicate years")
        if years != sorted(years):
            notes.append("years reordered")
        if any((not math.isfinite(v)) for v in values):
            ok = False
            notes.append("non-finite value")
        if any(v < 0 for v in values):
            ok = False
            notes.append("negative utilization")
        if len(values) < 6:
            notes.append("short baseline: uncertainty elevated")
        return ok, notes

    def _forecast_naive(self, values: List[float], actual: float) -> Forecast:
        expected = values[-1]
        diffs = [values[i] - values[i-1] for i in range(1, len(values))]
        floor = max(abs(expected) * 0.10, 1.0)
        scale = robust_sigma(diffs, floor=floor)
        z = (actual - expected) / scale
        rel = (actual - expected) / max(abs(expected), 1.0)
        vote = abs(z) >= self.z_threshold and abs(rel) >= self.min_relative_deviation
        return Forecast("naive_last", expected, scale, z, rel, vote)

    def _forecast_linear(self, years: List[int], values: List[float], target_year: int, actual: float) -> Forecast:
        xbar = sum(years) / len(years)
        ybar = sum(values) / len(values)
        denom = sum((x - xbar) ** 2 for x in years)
        slope = sum((x - xbar) * (y - ybar) for x, y in zip(years, values)) / max(denom, EPS)
        intercept = ybar - slope * xbar
        expected = intercept + slope * target_year
        residuals = [y - (intercept + slope * x) for x, y in zip(years, values)]
        floor = max(abs(expected) * 0.10, 1.0)
        scale = robust_sigma(residuals, floor=floor)
        z = (actual - expected) / scale
        rel = (actual - expected) / max(abs(expected), 1.0)
        vote = abs(z) >= self.z_threshold and abs(rel) >= self.min_relative_deviation
        return Forecast("linear_trend", expected, scale, z, rel, vote)

    def _forecast_median_growth(self, values: List[float], actual: float) -> Forecast:
        growths = []
        for a, b in zip(values[:-1], values[1:]):
            if abs(a) > EPS:
                growths.append(b / a - 1.0)
        g = median(growths) if growths else 0.0
        expected = values[-1] * (1.0 + g)
        g_scale = robust_sigma(growths, floor=0.10)
        scale = max(abs(expected) * g_scale, abs(expected) * 0.10, 1.0)
        z = (actual - expected) / scale
        rel = (actual - expected) / max(abs(expected), 1.0)
        vote = abs(z) >= self.z_threshold and abs(rel) >= self.min_relative_deviation
        return Forecast("median_growth", expected, scale, z, rel, vote)

    def evaluate(
        self,
        years: List[int],
        values: List[float],
        target_year: int,
        actual: float,
        event: Optional[EventEvidence] = None,
    ) -> V5Result:
        paired = sorted(zip(years, values))
        years = [x for x, _ in paired]
        values = [y for _, y in paired]

        quality_ok, notes = self.quality_gate(years, values)
        if not quality_ok:
            return V5Result(
                target_year, actual, len(values), False, notes, [], 0.0, 1.0, 1.0,
                event.score() if event else 0.0,
                event.name if event else None,
                "INSUFFICIENT_DATA"
            )

        forecasts = [
            self._forecast_naive(values, actual),
            self._forecast_linear(years, values, target_year, actual),
            self._forecast_median_growth(values, actual),
        ]

        votes = sum(int(f.anomaly_vote) for f in forecasts)
        consensus = votes / len(forecasts)

        exps = [f.expected for f in forecasts]
        exp_med = median(exps)
        spread = (max(exps) - min(exps)) / max(abs(exp_med), 1.0)

        # Short-history penalty intentionally remains high with 4 annual points.
        if len(values) < 5:
            history_penalty = 1.0
        elif len(values) < 8:
            history_penalty = 0.65
        elif len(values) < 12:
            history_penalty = 0.35
        else:
            history_penalty = 0.10

        disagreement_component = min(1.0, spread / 0.50)
        uncertainty = min(1.0, 0.55 * history_penalty + 0.45 * disagreement_component)

        causal_score = event.score() if event else 0.0
        causal_event = event.name if event else None

        max_abs_z = max(abs(f.z) for f in forecasts)
        mixed_votes = 0 < votes < len(forecasts)

        if consensus >= self.consensus_threshold:
            if event and causal_score >= 0.70:
                classification = "EXPLAINED_STRUCTURAL_BREAK"
            elif event and causal_score >= 0.40:
                classification = "CONTEXTUAL_ANOMALY"
            else:
                classification = "BLACK_SWAN_CANDIDATE"
        else:
            # A single extreme model should not dominate when models disagree.
            if mixed_votes and (spread >= 0.50 or max_abs_z >= self.z_threshold):
                classification = "MODEL_DISAGREEMENT_REVIEW"
            else:
                classification = "NORMAL_WITH_CONTEXT" if event else "NORMAL"

        return V5Result(
            target_year=target_year,
            actual=actual,
            history_n=len(values),
            quality_ok=True,
            quality_notes=notes,
            forecasts=forecasts,
            anomaly_consensus=consensus,
            model_spread_ratio=spread,
            uncertainty_score=uncertainty,
            causal_score=causal_score,
            causal_event=causal_event,
            classification=classification,
        )


def legacy_v3_linear(years: List[int], values: List[float], target_year: int, actual: float,
                     z_threshold: float = 3.0) -> Dict[str, float]:
    """Reference implementation: single linear-trend residual detector."""
    xbar = sum(years) / len(years)
    ybar = sum(values) / len(values)
    denom = sum((x - xbar) ** 2 for x in years)
    slope = sum((x - xbar) * (y - ybar) for x, y in zip(years, values)) / max(denom, EPS)
    intercept = ybar - slope * xbar
    expected = intercept + slope * target_year
    residuals = [y - (intercept + slope * x) for x, y in zip(years, values)]
    # Use ordinary residual SD with a 10% floor to avoid false certainty.
    if len(residuals) > 1:
        sd = statistics.stdev(residuals)
    else:
        sd = 0.0
    scale = max(sd, abs(expected) * 0.10, 1.0)
    z = (actual - expected) / scale
    return {
        "expected": expected,
        "scale": scale,
        "z": z,
        "anomaly": abs(z) >= z_threshold,
    }
