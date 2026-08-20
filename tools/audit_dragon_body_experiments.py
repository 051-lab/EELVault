#!/usr/bin/env python3
"""Dependency-free audit for DRAGON Pear Body experiments."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from dragon_body_experiments import (
    BODY_CANDIDATES,
    BODY_GROUP_DELAY_FREQS,
    BODY_POSITIONS,
    COMPENSATED_PROFILES,
    PearBodyProfile,
    PearBodyStage,
    PearLiteStage,
    benchmark_full_pear,
    body_parameters,
    body_response,
    build_body_report,
    group_delay_ms,
    iter_body_profiles,
)

BALANCED_PROFILE = PearBodyProfile(0.15, -0.075, 0.10, 0.025)


def require(name: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return condition


def check_pear_core() -> list[bool]:
    results: list[bool] = []

    neutral = PearLiteStage(48000.0)
    max_error = 0.0
    for index in range(4096):
        left = 0.31 * math.sin(2.0 * math.pi * 997.0 * index / 48000.0)
        right = 0.27 * math.sin(2.0 * math.pi * 1511.0 * index / 48000.0 + 0.31)
        max_error = max(
            max_error,
            abs(neutral.process_sample("L", left) - left),
            abs(neutral.process_sample("R", right) - right),
        )
    results.append(require(
        "neutral eight-stage Pear reconstructs input",
        max_error < 1e-12,
        f"max error={max_error:.3e}",
    ))

    reference_in = [0.0, 0.25, -0.5, 0.75, -1.0, 0.5, -0.25, 0.0]
    reference_out = [
        0.0,
        0.24747170923694406,
        -0.5013933237712032,
        0.7458792032603025,
        -1.001327429796749,
        0.502977462320823,
        -0.2438757912466743,
        0.009025645480079064,
    ]
    source = PearLiteStage(
        48000.0,
        high=0.5,
        hmid=0.5,
        lmid=0.25,
        bass=0.45,
        stages=8,
    )
    measured = [source.process_sample("L", value) for value in reference_in]
    source_error = max(abs(a - b) for a, b in zip(measured, reference_out))
    results.append(require(
        "Pear core matches source-derived 48 kHz vector",
        source_error < 1e-12,
        f"max error={source_error:.3e}",
    ))

    for fs in (44100.0, 48000.0):
        stage = PearLiteStage(fs, 0.5, 0.5, 0.35, 0.575, stages=8)
        finite = True
        for index in range(8192):
            sample = 0.8 * math.sin(2.0 * math.pi * 200.0 * index / fs)
            output = stage.process_sample("L", sample)
            if not math.isfinite(output):
                finite = False
                break
        results.append(require(
            f"Pear core finite @ {int(fs)} Hz",
            finite,
        ))
    return results


def check_body_macro() -> list[bool]:
    results: list[bool] = []

    reference_stage = PearBodyStage(48000.0, 0.0, BALANCED_PROFILE)
    results.append(require(
        "Body=0 maps to exact neutral Pear parameters",
        reference_stage.parameters == (0.5, 0.5, 0.5, 0.5),
        str(reference_stage.parameters),
    ))

    max_error = 0.0
    for index in range(4096):
        sample = 0.42 * math.sin(2.0 * math.pi * 1003.0 * index / 48000.0)
        output = reference_stage.process_sample("L", sample)
        max_error = max(max_error, abs(output - sample))
    results.append(require(
        "Body=0 is exact reference bypass",
        max_error == 0.0,
        f"max error={max_error:.3e}",
    ))

    lean_params = body_parameters(-1.0, BALANCED_PROFILE)
    full_params = body_parameters(1.0, BALANCED_PROFILE)
    results.append(require(
        "Lean lowers LMid while compensating Pear Bass",
        lean_params[2] < 0.5 and lean_params[3] > 0.5,
        str(lean_params),
    ))
    results.append(require(
        "Full raises LMid and Bass only within profile",
        abs(full_params[2] - 0.60) < 1e-15
        and abs(full_params[3] - 0.525) < 1e-15,
        str(full_params),
    ))

    profile_count = 0
    stable = True
    for family, profile in iter_body_profiles():
        profile_count += 1
        for fs in (44100.0, 48000.0):
            for body in BODY_POSITIONS:
                response = body_response(fs, body, profile)
                if not all(math.isfinite(value) for value in response.values()):
                    stable = False
                    break
            if not stable:
                break
        if not stable:
            break
    results.append(require(
        "approved + compensated Body profile grids are finite",
        stable,
        f"profiles={profile_count}",
    ))
    results.append(require(
        "compensated profile set is frozen",
        COMPENSATED_PROFILES == (
            (0.10, -0.05, 0.10, 0.025),
            (0.15, -0.075, 0.10, 0.025),
            (0.20, -0.10, 0.10, 0.025),
        ),
    ))
    return results


def check_body_metrics(run_timing: bool = False) -> list[bool]:
    results: list[bool] = []

    for fs in (44100.0, 48000.0):
        response = body_response(fs, -1.0, BALANCED_PROFILE)
        results.append(require(
            f"balanced Lean preserves 50 Hz @ {int(fs)} Hz",
            abs(response[50.0]) < 0.10,
            f"50 Hz={response[50.0]:+.3f} dB",
        ))
        results.append(require(
            f"balanced Lean controls 150-300 Hz @ {int(fs)} Hz",
            all(response[freq] < -4.0 for freq in (150.0, 200.0, 300.0)),
            ", ".join(
                f"{int(freq)}={response[freq]:+.3f} dB"
                for freq in (150.0, 200.0, 300.0)
            ),
        ))

        delays = [
            group_delay_ms(fs, -1.0, BALANCED_PROFILE, freq)
            for freq in BODY_GROUP_DELAY_FREQS
        ]
        results.append(require(
            f"balanced Lean group delay finite/sub-ms @ {int(fs)} Hz",
            all(math.isfinite(value) and abs(value) < 1.0 for value in delays),
            f"max |GD|={max(abs(value) for value in delays):.3f} ms",
        ))

        neutral = body_response(fs, 0.0, BALANCED_PROFILE)
        results.append(require(
            f"Body response model is exact neutral @ {int(fs)} Hz",
            all(value == 0.0 for value in neutral.values()),
        ))

    results.append(require(
        "Body candidate registry is exact",
        set(BODY_CANDIDATES) == {"body-none", "body-pear"},
        str(set(BODY_CANDIDATES)),
    ))

    if run_timing:
        timing = benchmark_full_pear(48000.0, repeats=3)
        results.append(require(
            "full Pear local timing proxy is finite",
            math.isfinite(timing) and timing > 0.0,
            f"median={timing:.4f} s / 48k stereo frames",
        ))
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--section",
        choices=("all", "body-pear-core", "body-pear", "body-metrics", "body"),
        default="all",
    )
    parser.add_argument("--json-out", type=Path)
    parser.add_argument(
        "--timing",
        action="store_true",
        help="include the local Python timing proxy in body-metrics",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results: list[bool] = []

    if args.section in ("all", "body-pear-core"):
        results += check_pear_core()
    if args.section in ("all", "body-pear"):
        results += check_body_macro()
    if args.section in ("all", "body-metrics"):
        results += check_body_metrics(run_timing=args.timing)
    if args.section in ("all", "body"):
        report = build_body_report()
        if args.json_out is not None:
            args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        for rate, rows in report["sample_rates"].items():
            print(f"\nBody profiles @ {rate} Hz")
            for row in rows:
                marker = "*" if row["non_dominated"] else " "
                lean = row["lean_response_db"]
                print(
                    f"{marker} {row['family']:11s} {str(row['profile']):93s} "
                    f"50={lean['50']:+.2f} 150={lean['150']:+.2f} "
                    f"200={lean['200']:+.2f} 300={lean['300']:+.2f} "
                    f"prelim={row['headroom_lean']['peak_pre_limiter']:.4f}"
                )

    passed = sum(results)
    total = len(results)
    print(f"\nDRAGON Body experiment audit: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
