#!/usr/bin/env python3
"""Dependency-free audit entry point for DRAGON adaptive-control experiments.

Run from any working directory:
    python tools/audit_dragon_experiments.py
    python tools/audit_dragon_experiments.py --section core
    python tools/audit_dragon_experiments.py --section parity
    python tools/audit_dragon_experiments.py --section baseline-fr

The production DRAGON audit remains ``tools/audit_dragon.py``. This script
covers only experiment infrastructure and candidate research added on the
``dragon-adaptive-control-experiments`` branch.
"""

from __future__ import annotations

import argparse
import math

from audit_dragon import DragonEngine
from dragon_experiments import (
    FREQUENCY_PROBES,
    DragonExperimentEngine,
    amp_to_db,
    current_s6_cutoff,
    db_to_amp,
    make_sine,
    make_two_tone,
    measure_frequency_response,
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


def _parity_error(fs: float, instrument: bool) -> float:
    reference = DragonEngine(fs, wf=0.0, hiss=-200.0)
    experiment = DragonExperimentEngine(
        fs,
        wf=0.0,
        hiss=-200.0,
        instrument=instrument,
    )
    max_error = 0.0
    for n in range(4096):
        left = math.sin(2.0 * math.pi * 997.0 * n / fs) * 0.35
        right = math.sin(2.0 * math.pi * 1511.0 * n / fs + 0.37) * 0.27
        ref_l, ref_r = reference.process(left, right)
        exp_l, exp_r = experiment.process(left, right)
        max_error = max(
            max_error,
            abs(ref_l - exp_l),
            abs(ref_r - exp_r),
        )
    return max_error


def check_parity() -> list[bool]:
    results: list[bool] = []
    for fs in (44100.0, 48000.0):
        max_error = _parity_error(fs, instrument=False)
        results.append(require(
            f"experiment engine baseline parity @ {int(fs)} Hz",
            max_error < 1e-15,
            f"max error={max_error:.3e}",
        ))

        instrumented_error = _parity_error(fs, instrument=True)
        results.append(require(
            f"instrumented path parity @ {int(fs)} Hz",
            instrumented_error < 1e-15,
            f"max error={instrumented_error:.3e}",
        ))
    return results


def check_baseline_fr() -> list[bool]:
    results: list[bool] = []
    results.append(require(
        "S6 cutoff at zero envelope is 30 kHz",
        abs(current_s6_cutoff(0.0) - 30000.0) < 1e-12,
    ))
    results.append(require(
        "S6 cutoff lower bound is 7 kHz",
        current_s6_cutoff(10.0) == 7000.0,
    ))

    for fs in (44100.0, 48000.0):
        fr = measure_frequency_response(
            lambda fs=fs: DragonEngine(fs, wf=0.0, hiss=-200.0),
            fs,
        )
        results.append(require(
            f"baseline FR finite @ {int(fs)} Hz",
            all(math.isfinite(value) for value in fr.values()),
        ))
        results.append(require(
            f"baseline FR contains required probes @ {int(fs)} Hz",
            all(freq in fr for freq in (50.0, 200.0, 10000.0, 18000.0)),
        ))
        print(f"\nBaseline small-signal FR @ {int(fs)} Hz")
        for freq in FREQUENCY_PROBES:
            print(f"  {freq:8.1f} Hz  {fr[freq]:+8.3f} dB")
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--section",
        choices=("all", "core", "parity", "baseline-fr"),
        default="all",
        help="run one experiment-audit section (default: all)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results: list[bool] = []

    if args.section in ("all", "core"):
        results += check_core()
    if args.section in ("all", "parity"):
        results += check_parity()
    if args.section in ("all", "baseline-fr"):
        results += check_baseline_fr()

    passed = sum(results)
    total = len(results)
    print(f"\nDRAGON experiment audit: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
