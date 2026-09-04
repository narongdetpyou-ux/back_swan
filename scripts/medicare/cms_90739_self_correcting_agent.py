#!/usr/bin/env python3
"""
Self-correcting CMS Medicare HCPCS 90739 retrieval + anomaly test.

Goal
----
Retrieve annual national Medicare Physician & Other Practitioners
"by Geography and Service" data for HCPCS 90739, years 2020-2024,
without depending on a single CMS endpoint.

Self-correction / fallback order per year
-----------------------------------------
1) CMS Data API with exact HCPCS filter
2) Alternate CMS Data API UUID when known
3) Official CMS annual CSV (streaming download, filter rows locally)
4) Fail CLOSED: do not invent data

Then:
- Aggregate National rows across place-of-service using service-weighted amounts.
- v2: year-over-year change anomaly
- v3: actual-vs-expected residual anomaly
- v4: v3 + known external-event classification
      (2024 §411.355(h) / 90739 code-list correction context)

This script intentionally does not treat "unexplained" as proof of a Black Swan.
It labels it "Black-Swan candidate".
"""

from __future__ import annotations
import argparse
import csv
import io
import json
import math
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Iterable, Tuple

try:
    import requests
except Exception:
    requests = None


HCPCS = "90739"

# Official CMS resources discovered from the HHS/Data.gov catalog.
SOURCES = {
    2020: {
        "api": [
            "https://data.cms.gov/data-api/v1/dataset/31eb3018-43e0-4259-a0d8-e7a1112ffd08/data"
        ],
        "csv": "https://data.cms.gov/sites/default/files/2022-07/0d730fe9-deb8-453b-a2fd-ce778286d9f6/MUP_PHY_R22_P05_V10_D20_Geo.csv",
    },
    2021: {
        "api": [
            "https://data.cms.gov/data-api/v1/dataset/f00f462f-bb61-48b1-a321-1c50d78ce175/data"
        ],
        "csv": "https://data.cms.gov/sites/default/files/2023-05/0a47308e-812e-42cb-8ecf-0c1f457ab849/MUP_PHY_R23_P05_V10_D21_Geo.csv",
    },
    2022: {
        "api": [
            "https://data.cms.gov/data-api/v1/dataset/87304f15-9ed0-41dc-a141-6141a0327453/data"
        ],
        "csv": "https://data.cms.gov/sites/default/files/2024-05/3167b4d9-10c0-48f0-a680-1165f4eec064/MUP_PHY_R24_P05_V10_D22_Geo.csv",
    },
    2023: {
        "api": [
            "https://data.cms.gov/data-api/v1/dataset/ddee9e22-7889-4bef-975a-7853e4cd0fbb/data"
        ],
        "csv": "https://data.cms.gov/sites/default/files/2025-04/3b718a11-a28d-4c38-a13b-2c6eeb649980/MUP_PHY_R25_P05_V20_D23_Geo.csv",
    },
    2024: {
        "api": [
            "https://data.cms.gov/data-api/v1/dataset/6fea9d79-0129-4e4c-b1b8-23cd86a4f435/data",
            # Catalog also exposes a second 2024 distribution; use as failover.
            "https://data.cms.gov/data-api/v1/dataset/0c75b0b3-b40f-4007-a5ac-f9f2fed95862/data",
        ],
        "csv": "https://data.cms.gov/sites/default/files/2026-05/e534c74b-79b8-4892-8a95-5a17e2dfec9f/MUP_PHY_R26_P05_V10_D24_Geo.csv",
    },
}

# Aliases accommodate modest schema renames across years.
ALIASES = {
    "geo_level": ["Rndrng_Prvdr_Geo_Lvl", "Rndrng_Prvdr_Geo_Level", "Geography_Level"],
    "geo_desc": ["Rndrng_Prvdr_Geo_Desc", "Rndrng_Prvdr_Geo_Description", "Geography_Description"],
    "hcpcs": ["HCPCS_Cd", "HCPCS_Code", "HCPCS"],
    "pos": ["Place_Of_Srvc", "Place_Of_Service", "Place_of_Service"],
    "providers": ["Tot_Rndrng_Prvdrs", "Tot_Rndrng_Prvdr", "Total_Rendering_Providers"],
    "beneficiaries": ["Tot_Benes", "Total_Beneficiaries"],
    "services": ["Tot_Srvcs", "Total_Services"],
    "submitted": ["Avg_Sbmtd_Chrg", "Avg_Submitted_Charge", "Average_Submitted_Charge"],
    "allowed": ["Avg_Mdcr_Alowd_Amt", "Avg_Medicare_Allowed_Amt", "Average_Medicare_Allowed_Amount"],
    "payment": ["Avg_Mdcr_Pymt_Amt", "Avg_Medicare_Payment_Amt", "Average_Medicare_Payment"],
    "std_payment": ["Avg_Mdcr_Stdzd_Amt", "Avg_Medicare_Standardized_Amt", "Average_Standardized_Payment"],
}


@dataclass
class Annual:
    year: int
    services: float
    beneficiaries: Optional[float]
    providers: Optional[float]
    avg_submitted: Optional[float]
    avg_allowed: Optional[float]
    avg_payment: Optional[float]
    avg_std_payment: Optional[float]
    source_method: str
    source_url: str
    rows_used: int


def pick(row: dict, key: str):
    for k in ALIASES[key]:
        if k in row:
            return row.get(k)
    return None


def fnum(x) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip().replace(",", "").replace("$", "")
    if s in ("", "NA", "N/A", "*", "nan", "None"):
        return None
    try:
        return float(s)
    except Exception:
        return None


def is_national_90739(row: dict) -> bool:
    hcpcs = str(pick(row, "hcpcs") or "").strip()
    if hcpcs != HCPCS:
        return False

    lvl = str(pick(row, "geo_level") or "").strip().lower()
    desc = str(pick(row, "geo_desc") or "").strip().lower()

    # Some files explicitly label the row "National"; others may leave
    # geography description as "National".
    return ("national" in lvl) or (desc == "national")


def aggregate(year: int, rows: List[dict], method: str, url: str) -> Annual:
    hits = [r for r in rows if is_national_90739(r)]
    if not hits:
        raise RuntimeError(f"{year}: no National {HCPCS} rows found")

    services = sum(fnum(pick(r, "services")) or 0.0 for r in hits)
    if services <= 0:
        raise RuntimeError(f"{year}: National {HCPCS} rows found but services are missing/zero")

    # Provider and beneficiary counts may overlap between office/facility.
    # We report the sum as published-row total ONLY when present, and flag
    # aggregation semantics in output.
    benes = [fnum(pick(r, "beneficiaries")) for r in hits]
    provs = [fnum(pick(r, "providers")) for r in hits]

    def weighted(alias_key: str) -> Optional[float]:
        num = den = 0.0
        for r in hits:
            s = fnum(pick(r, "services"))
            a = fnum(pick(r, alias_key))
            if s is not None and a is not None:
                num += s * a
                den += s
        return num / den if den else None

    return Annual(
        year=year,
        services=services,
        beneficiaries=sum(x for x in benes if x is not None) if any(x is not None for x in benes) else None,
        providers=sum(x for x in provs if x is not None) if any(x is not None for x in provs) else None,
        avg_submitted=weighted("submitted"),
        avg_allowed=weighted("allowed"),
        avg_payment=weighted("payment"),
        avg_std_payment=weighted("std_payment"),
        source_method=method,
        source_url=url,
        rows_used=len(hits),
    )


def request_with_retry(url, *, params=None, stream=False, tries=4, timeout=45):
    if requests is None:
        raise RuntimeError("Python package 'requests' is required for network retrieval.")
    err = None
    for i in range(tries):
        try:
            r = requests.get(
                url,
                params=params,
                timeout=timeout,
                stream=stream,
                headers={"User-Agent": "cms-90739-self-correcting-agent/1.0"},
            )
            if r.status_code == 200:
                return r
            err = RuntimeError(f"HTTP {r.status_code}: {r.text[:300] if not stream else ''}")
        except Exception as e:
            err = e
        if i + 1 < tries:
            time.sleep(2 ** i)
    raise RuntimeError(f"request failed after {tries} tries: {err}")


def fetch_api(year: int, url: str) -> Annual:
    # CMS uses JSONAPI-style filters. Try both field spellings because older
    # annual distributions occasionally differ.
    attempts = [
        {"offset": 0, "size": 500, "filter[HCPCS_Cd]": HCPCS},
        {"offset": 0, "size": 500, "filter[HCPCS_Code]": HCPCS},
    ]
    last = None
    for params in attempts:
        try:
            r = request_with_retry(url, params=params)
            payload = r.json()
            if isinstance(payload, dict):
                # tolerate wrappers
                rows = payload.get("data") or payload.get("results") or payload.get("records") or []
            else:
                rows = payload
            if not isinstance(rows, list):
                raise RuntimeError("unexpected API JSON structure")
            return aggregate(year, rows, "CMS Data API", r.url)
        except Exception as e:
            last = e
    raise RuntimeError(f"API path failed: {last}")


def fetch_csv(year: int, url: str) -> Annual:
    # Stream the official CSV; keep only 90739 rows so memory stays bounded.
    r = request_with_retry(url, stream=True, timeout=120)
    r.raw.decode_content = True
    wrapper = io.TextIOWrapper(r.raw, encoding="utf-8-sig", errors="replace", newline="")
    reader = csv.DictReader(wrapper)
    kept = []
    for row in reader:
        if str(pick(row, "hcpcs") or "").strip() == HCPCS:
            kept.append(row)
    return aggregate(year, kept, "CMS official annual CSV", url)


def fetch_local_csv(year: int, directory: Path) -> Optional[Annual]:
    names = [
        Path(SOURCES[year]["csv"]).name,
    ]
    for name in names:
        p = directory / name
        if p.exists():
            with p.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
                rows = [r for r in csv.DictReader(f) if str(pick(r, "hcpcs") or "").strip() == HCPCS]
            return aggregate(year, rows, "local official CMS CSV", str(p))
    return None


def retrieve_year(year: int, local_dir: Optional[Path] = None) -> Annual:
    errors = []

    if local_dir:
        try:
            a = fetch_local_csv(year, local_dir)
            if a:
                return a
        except Exception as e:
            errors.append(f"local CSV: {e}")

    for api in SOURCES[year]["api"]:
        try:
            return fetch_api(year, api)
        except Exception as e:
            errors.append(f"API {api}: {e}")

    try:
        return fetch_csv(year, SOURCES[year]["csv"])
    except Exception as e:
        errors.append(f"CSV {SOURCES[year]['csv']}: {e}")

    raise RuntimeError(
        f"{year}: all official-source retrieval paths failed.\n  - "
        + "\n  - ".join(errors)
    )


def median_mad(xs: List[float]) -> Tuple[float, float]:
    med = statistics.median(xs)
    dev = [abs(x - med) for x in xs]
    mad = statistics.median(dev)
    return med, mad


def robust_z(value: float, center: float, mad: float, floor_scale: float) -> float:
    # 1.4826*MAD approximates sigma under a normal distribution.
    scale = max(1.4826 * mad, floor_scale, 1e-9)
    return abs(value - center) / scale


def analyze(annuals: List[Annual]) -> dict:
    annuals = sorted(annuals, key=lambda x: x.year)
    by = {a.year: a for a in annuals}
    base_years = [2020, 2021, 2022, 2023]
    if any(y not in by for y in base_years + [2024]):
        raise RuntimeError("Need complete 2020-2024 data for the planned test.")

    s = {y: by[y].services for y in base_years + [2024]}

    growths = []
    for y0, y1 in [(2020, 2021), (2021, 2022), (2022, 2023)]:
        if s[y0] <= 0:
            raise RuntimeError(f"Cannot compute growth from non-positive services in {y0}.")
        growths.append(s[y1] / s[y0] - 1.0)

    g_med, g_mad = median_mad(growths)
    observed_growth_2024 = s[2024] / s[2023] - 1.0
    expected_2024 = s[2023] * (1.0 + g_med)
    rel_resid = (s[2024] - expected_2024) / expected_2024 if expected_2024 else math.nan

    # Avoid false certainty with only 3 historical growth observations.
    # The 10 percentage-point floor prevents a tiny MAD from creating absurd z-scores.
    v2_z = robust_z(observed_growth_2024, g_med, g_mad, floor_scale=0.10)
    v2_anomaly = (v2_z >= 3.0) and (abs(observed_growth_2024 - g_med) >= 0.25)

    expected_growth_band_scale = max(1.4826 * g_mad, 0.10)
    expected_services_scale = max(abs(expected_2024) * expected_growth_band_scale, 1.0)
    v3_z = abs(s[2024] - expected_2024) / expected_services_scale
    v3_anomaly = (v3_z >= 3.0) and (abs(rel_resid) >= 0.25)

    known_external_event_2024 = True
    if v3_anomaly and known_external_event_2024:
        v4_class = "EXPLAINED STRUCTURAL BREAK CANDIDATE"
    elif v3_anomaly:
        v4_class = "UNEXPLAINED ANOMALY / BLACK-SWAN CANDIDATE"
    else:
        v4_class = "NO LARGE ANOMALY UNDER THIS TEST"

    return {
        "historical_growth_rates": growths,
        "median_historical_growth": g_med,
        "mad_historical_growth": g_mad,
        "observed_2024_growth": observed_growth_2024,
        "expected_2024_services": expected_2024,
        "actual_2024_services": s[2024],
        "relative_residual_2024": rel_resid,
        "v2_z": v2_z,
        "v2_anomaly": v2_anomaly,
        "v3_z": v3_z,
        "v3_anomaly": v3_anomaly,
        "known_external_event_2024": known_external_event_2024,
        "v4_classification": v4_class,
    }


def save_outputs(annuals: List[Annual], result: dict, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)

    csv_path = outdir / "cms_90739_2020_2024.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(Annual.__annotations__.keys()))
        w.writeheader()
        for a in annuals:
            w.writerow(a.__dict__)

    json_path = outdir / "cms_90739_anomaly_result.json"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    return csv_path, json_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local-dir", type=Path, default=None,
                    help="Optional folder containing official annual CMS CSV files.")
    ap.add_argument("--outdir", type=Path, default=Path("."))
    args = ap.parse_args()

    annuals = []
    print("CMS 90739 self-correcting retrieval")
    print("=" * 72)

    for year in range(2020, 2025):
        try:
            a = retrieve_year(year, args.local_dir)
            annuals.append(a)
            print(f"[PASS] {year}: services={a.services:,.0f} via {a.source_method}")
        except Exception as e:
            print(f"[FAIL-CLOSED] {e}", file=sys.stderr)
            print("\nNo anomaly verdict produced because the evidence chain is incomplete.",
                  file=sys.stderr)
            sys.exit(2)

    result = analyze(annuals)
    csv_path, json_path = save_outputs(annuals, result, args.outdir)

    print("\nANALYSIS")
    print("-" * 72)
    print(f"Median historical YoY growth : {result['median_historical_growth']*100:,.2f}%")
    print(f"Observed 2024 YoY growth     : {result['observed_2024_growth']*100:,.2f}%")
    print(f"Expected 2024 services       : {result['expected_2024_services']:,.0f}")
    print(f"Actual 2024 services         : {result['actual_2024_services']:,.0f}")
    print(f"2024 relative residual       : {result['relative_residual_2024']*100:,.2f}%")
    print(f"v2 anomaly                   : {result['v2_anomaly']} (z={result['v2_z']:.2f})")
    print(f"v3 anomaly                   : {result['v3_anomaly']} (z={result['v3_z']:.2f})")
    print(f"v4 classification            : {result['v4_classification']}")
    print()
    print("Important: v4's known-event flag does NOT prove causation. It prevents the")
    print("system from automatically calling a detected structural break a Black Swan.")
    print(f"\nSaved:\n  {csv_path}\n  {json_path}")


if __name__ == "__main__":
    main()
