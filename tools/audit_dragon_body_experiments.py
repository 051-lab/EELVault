#!/usr/bin/env python3
"""Focused dependency-free audit for DRAGON Pear Body experiments."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from dragon_body_experiments import (
    BODY_CANDIDATES,
    BODY_GROUP_DELAY_FREQS,
    BODY_POSITIONS,
    PearBodyProfile,
    PearBodyStage,
    PearLiteStage,
    body_parameters,
    body_response,
    build_body_report,
    group_delay_ms,
    iter_body_profiles,
)

# Cross-rate refinement of the initial compensated profile.  A +0.079 Pear
# Bass compensation at full Lean balances 50 Hz across both 44.1 and 48 kHz
# while retaining >4 dB authority through 150-300 Hz.
REFINED_PROFILE = PearBodyProfile(0.15, -0.079, 0.10, 0.025)


def require(name: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return condition


def check_core() -> list[bool]:
    results: list[bool] = []

    neutral = PearLiteStage(48000.0)
    max_error = 0.0
    for n in range(4096):
        left = 0.31 * math.sin(2.0 * math.pi * 997.0 * n / 48000.0)
        right = 0.27 * math.sin(2.0 * math.pi * 1511.0 * n / 48000.0 + 0.31)
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
    source = PearLiteStage(48000.0, 0.5, 0.5, 0.25, 0.45, stages=8)
    measured = [source.process_sample("L", x) for x in reference_in]
    source_error = max(abs(a - b) for a, b in zip(measured, reference_out))
    results.append(require(
        "Pear core matches source-derived vector",
        source_error < 1e-12,
        f"max error={source_error:.3e}",
    ))

    stage = PearBodyStage(48000.0, body=0.0, profile=REFINED_PROFILE)
    bypass_error = 0.0
    for n in range(4096):
        sample = 0.42 * math.sin(2.0 * math.pi * 1003.0 * n / 48000.0)
        bypass_error = max(
            bypass_error,
            abs(stage.process_sample("L", sample) - sample),
        )
    results.append(require(
        "Body=0 is exact reference bypass",
        bypass_error == 0.0,
        f"max error={bypass_error:.3e}",
    ))
    results.append(require(
        "Body registry is exact",
        set(BODY_CANDIDATES) == {"body-none", "body-pear"},
    ))
    return results


def check_profile_grid() -> list[bool]:
    results: list[bool] = []
    count = 0
    finite = True
    for _, profile in iter_body_profiles():
        count += 1
        for fs in (44100.0, 48000.0):
            for body in BODY_POSITIONS:
                values = body_response(fs, body, profile)
                if not all(math.isfinite(value) for value in values.values()):
                    finite = False
                    break
    results.append(require(
        "approved and exploratory Body grids are finite",
        finite,
        f"profiles={count}",
    ))

    lean = body_parameters(-1.0, REFINED_PROFILE)
    full = body_parameters(1.0, REFINED_PROFILE)
    results.append(require(
        "refined Lean lowers LMid and compensates Bass",
        abs(lean[2] - 0.35) < 1e-15 and abs(lean[3] - 0.579) < 1e-15,
        str(lean),
    ))
    results.append(require(
        "Full side remains modest",
        abs(full[2] - 0.60) < 1e-15 and abs(full[3] - 0.525) < 1e-15,
        str(full),
    ))
    return results


def check_refined_metrics() -> list[bool]:
    results: list[bool] = []
    for fs in (44100.0, 48000.0):
        lean = body_response(fs, -1.0, REFINED_PROFILE)
        results.append(require(
            f"refined Lean preserves 50 Hz @ {int(fs)} Hz",
            abs(lean[50.0]) < 0.10,
            f"50={lean[50.0]:+.3f} dB",
        ))
        results.append(require(
            f"refined Lean controls 150-300 Hz @ {int(fs)} Hz",
            all(lean[f] < -4.0 for f in (150.0, 200.0, 300.0)),
            ", ".join(f"{int(f)}={lean[f]:+.3f}" for f in (150.0, 200.0, 300.0)),
        ))
        delays = [
            group_delay_ms(fs, -1.0, REFINED_PROFILE, f)
            for f in BODY_GROUP_DELAY_FREQS
        ]
        results.append(require(
            f"refined Lean group delay remains sub-ms @ {int(fs)} Hz",
            all(math.isfinite(x) and abs(x) < 1.0 for x in delays),
            f"max |GD|={max(abs(x) for x in delays):.3f} ms",
        ))
        reference = body_response(fs, 0.0, REFINED_PROFILE)
        results.append(require(
            f"Body response is exact neutral @ {int(fs)} Hz",
            all(value == 0.0 for value in reference.values()),
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results: list[bool] = []
    if args.section in ("all", "body-pear-core"):
        results += check_core()
    if args.section in ("all", "body-pear"):
        results += check_profile_grid()
    if args.section in ("all", "body-metrics"):
        results += check_refined_metrics()
    if args.section in ("all", "body"):
        report = build_body_report()
        report["refined_profile"] = {
            "lean_lmid_drop": REFINED_PROFILE.lean_lmid_drop,
            "lean_bass_drop": REFINED_PROFILE.lean_bass_drop,
            "full_lmid_rise": REFINED_PROFILE.full_lmid_rise,
            "full_bass_rise": REFINED_PROFILE.full_bass_rise,
        }
        report["refined_response"] = {
            str(int(fs)): {
                str(body): {
                    str(int(freq)): value
                    for freq, value in body_response(fs, body, REFINED_PROFILE).items()
                }
                for body in BODY_POSITIONS
            }
            for fs in (44100.0, 48000.0)
        }
        if args.json_out is not None:
            args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        for fs in (44100.0, 48000.0):
            lean = body_response(fs, -1.0, REFINED_PROFILE)
            print(f"\nRefined Body Lean @ {int(fs)} Hz")
            for freq, value in lean.items():
                print(f"  {freq:7.1f} Hz  {value:+7.3f} dB")

    passed = sum(results)
    total = len(results)
    print(f"\nDRAGON Body experiment audit: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
