#!/usr/bin/env python3
"""Formal LF=NONE combination audit for DRAGON adaptive-control experiments."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from dragon_body_experiments import body_response
from dragon_combination_experiments import (
    BODY_CONTEXTS,
    HF_CONTEXTS,
    REFINED_BODY_PROFILE,
    build_initial_combination_report,
    load_selection,
    selection_baseline_error,
)

RATES = ("44100", "48000")
HF_KEYS = ("current-s6", "hf-acceleration", "hf-totape")
BODY_KEYS = ("body-none", "body-lean-half", "body-lean-full")


def require(name: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return condition


def _row_map(rows: list[dict]) -> dict[tuple[str, str], dict]:
    return {(row["hf"], row["body"]): row for row in rows}


def check_selection() -> list[bool]:
    results: list[bool] = []
    selection = load_selection()
    results.append(require(
        "safe selection remains LF=none/current-S6/body-none",
        selection == {
            "lf": {"key": "none", "params": {}},
            "hf": {"key": "current-s6", "params": {}},
            "body": {"key": "body-none", "params": {}},
        },
        str(selection),
    ))
    for fs in (44100.0, 48000.0):
        error = selection_baseline_error(fs)
        results.append(require(
            f"safe selection reproduces baseline @ {int(fs)} Hz",
            error < 1e-15,
            f"max error={error:.3e}",
        ))
    return results


def check_refined_body() -> list[bool]:
    results: list[bool] = []
    for fs in (44100.0, 48000.0):
        lean = body_response(fs, -1.0, REFINED_BODY_PROFILE)
        results.append(require(
            f"refined Body preserves 50 Hz @ {int(fs)} Hz",
            abs(lean[50.0]) < 0.10,
            f"50 Hz={lean[50.0]:+.3f} dB",
        ))
        results.append(require(
            f"refined Body controls 150-300 Hz @ {int(fs)} Hz",
            all(lean[freq] < -4.0 for freq in (150.0, 200.0, 300.0)),
            ", ".join(f"{int(freq)}={lean[freq]:+.3f}" for freq in (150.0, 200.0, 300.0)),
        ))
    return results


def check_report(report: dict) -> list[bool]:
    results: list[bool] = []
    results.append(require(
        "combination gate is explicitly LF=NONE",
        report.get("scope") == "LF fixed to NONE",
    ))
    results.append(require(
        "HF context registry is frozen",
        set(HF_CONTEXTS) == set(HF_KEYS),
        str(set(HF_CONTEXTS)),
    ))
    results.append(require(
        "Body context registry is frozen",
        set(BODY_CONTEXTS) == set(BODY_KEYS),
        str(set(BODY_CONTEXTS)),
    ))

    for rate in RATES:
        rows = report["sample_rates"][rate]
        mapping = _row_map(rows)
        results.append(require(
            f"nine HF x Body combinations reported @ {rate} Hz",
            set(mapping) == {(hf, body) for hf in HF_KEYS for body in BODY_KEYS},
            f"rows={len(rows)}",
        ))

        for hf in HF_KEYS:
            spans = [mapping[(hf, body)]["coupling_span_db"] for body in BODY_KEYS]
            variation = max(spans) - min(spans)
            results.append(require(
                f"Body/HF coupling remains orthogonal for {hf} @ {rate} Hz",
                variation < 0.01,
                f"span variation={variation:.4f} dB",
            ))

        for body in BODY_KEYS:
            baseline = mapping[("current-s6", body)]["coupling_span_db"]
            acceleration = mapping[("hf-acceleration", body)]["coupling_span_db"]
            totape = mapping[("hf-totape", body)]["coupling_span_db"]
            results.append(require(
                f"Acceleration reduces bass-driven HF coupling ({body}) @ {rate} Hz",
                acceleration < baseline - 3.0,
                f"{baseline:.3f}->{acceleration:.3f} dB",
            ))
            results.append(require(
                f"ToTape reduces bass-driven HF coupling ({body}) @ {rate} Hz",
                totape < baseline - 3.0,
                f"{baseline:.3f}->{totape:.3f} dB",
            ))
            results.append(require(
                f"Acceleration coupling is no worse than ToTape ({body}) @ {rate} Hz",
                acceleration <= totape + 0.03,
                f"Acceleration={acceleration:.3f}, ToTape={totape:.3f}",
            ))

            current_drop = abs(mapping[("current-s6", body)]["inverse_efficiency_drop_db"])
            for hf in ("hf-acceleration", "hf-totape"):
                candidate_drop = abs(mapping[(hf, body)]["inverse_efficiency_drop_db"])
                results.append(require(
                    f"{hf} retains HF-level responsiveness ({body}) @ {rate} Hz",
                    candidate_drop >= current_drop * 0.90,
                    f"candidate={candidate_drop:.3f}, current={current_drop:.3f}",
                ))

        results.append(require(
            f"all LF=NONE combinations avoid limiter on deterministic stress @ {rate} Hz",
            all(row["stress"]["limiter_rate"] == 0.0 for row in rows),
        ))
        results.append(require(
            f"all LF=NONE combination metrics finite @ {rate} Hz",
            all(
                math.isfinite(row["coupling_span_db"])
                and math.isfinite(row["inverse_efficiency_drop_db"])
                and all(math.isfinite(value) for value in row["stress"].values())
                for row in rows
            ),
        ))
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--section", choices=("all", "selection", "matrix"), default="all")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results: list[bool] = []
    if args.section in ("all", "selection"):
        results += check_selection()
        results += check_refined_body()

    if args.section in ("all", "matrix"):
        report = build_initial_combination_report()
        results += check_report(report)
        if args.json_out is not None:
            args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    passed = sum(results)
    total = len(results)
    print(f"\nDRAGON combination audit: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
