#!/usr/bin/env python3
"""Dependency-free audit entry point for DRAGON adaptive-control experiments.

Run from any working directory:
    python tools/audit_dragon_experiments.py
    python tools/audit_dragon_experiments.py --section core

The production DRAGON audit remains ``tools/audit_dragon.py``.  This script
covers only experiment infrastructure and candidate research added on the
``dragon-adaptive-control-experiments`` branch.
"""

from __future__ import annotations

import argparse
import math

from dragon_experiments import (
    amp_to_db,
    db_to_amp,
    make_sine,
    make_two_tone,
    project_tone_amplitude,
    rms,
)


def require(name: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return condition


def check_core() -> list[bool]:
    results: list[bool] = []

    results.append(require(
        "-6 dB converts to amplitude",
        abs(db_to_amp(-6.0) - (10.0 ** (-6.0 / 20.0))) < 1e-15,
    ))
    results.append(require(
        "amplitude round-trip is stable",
        abs(amp_to_db(db_to_amp(-42.5)) + 42.5) < 1e-12,
    ))

    fs = 48000.0
    tone = make_sine(fs, 1000.0, -12.0, 0.1)
    expected_rms = db_to_amp(-12.0) / math.sqrt(2.0)
    results.append(require(
        "sine RMS is correct",
        abs(rms(tone) - expected_rms) < 1e-9,
    ))

    measured = project_tone_amplitude(tone, fs, 1000.0)
    results.append(require(
        "coherent tone projection recovers amplitude",
        abs(amp_to_db(measured) + 12.0) < 1e-6,
    ))

    dual = make_two_tone(fs, 60.0, -6.0, 10000.0, -30.0, 0.5)
    results.append(require(
        "two-tone fixture preserves 10 kHz component",
        abs(amp_to_db(project_tone_amplitude(dual, fs, 10000.0)) + 30.0) < 1e-5,
    ))
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--section",
        choices=("all", "core"),
        default="all",
        help="run one experiment-audit section (default: all)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results: list[bool] = []

    if args.section in ("all", "core"):
        results += check_core()

    passed = sum(results)
    total = len(results)
    print(f"\nDRAGON experiment audit: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
