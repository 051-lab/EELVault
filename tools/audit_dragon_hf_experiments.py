#!/usr/bin/env python3
"""Dependency-free audit for DRAGON HF candidate experiments."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from dragon_experiments import amp_to_db, make_sine, project_tone_amplitude
from dragon_hf_experiments import (
    ACCEL_LIMITS,
    HF_CANDIDATES,
    SINEW_AMOUNTS,
    TOTAPE_CROSSOVER_HZ,
    TOTAPE_ENV_GAIN,
    AccelerationStage,
    SinewStage,
    ToTapeHFConfig,
    ToTapeHFStage,
    build_hf_report,
    measure_max_slew,
)


def require(name: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return condition


def check_sinew() -> list[bool]:
    results = []
    reference_in = [0.0, 0.2, -0.4, 0.8, -1.0]
    reference_out = [
        0.0,
        0.057421875,
        3.12145054151558e-07,
        0.05742218714505415,
        6.242968956238215e-07,
    ]
    stage = SinewStage(48000.0, amount=0.5)
    measured = [stage.process_sample("L", x) for x in reference_in]
    error = max(abs(a - b) for a, b in zip(measured, reference_out))
    results.append(require(
        "Sinew matches source-derived vector",
        error < 1e-12,
        f"max error={error:.3e}",
    ))

    stage = SinewStage(48000.0, amount=0.1)
    signal = make_sine(48000.0, 1000.0, -60.0, 1.0)
    output = [stage.process_sample("L", x) for x in signal]
    inactive_error = max(abs(a - b) for a, b in zip(signal, output))
    results.append(require(
        "Sinew is exact in inactive low-level region",
        inactive_error < 1e-12,
        f"max error={inactive_error:.3e}",
    ))
    return results


def check_acceleration() -> list[bool]:
    reference_in = [0.0, 0.25, -0.5, 0.75, -1.0, 0.5, -0.25, 0.0]
    reference_out = [
        0.0,
        0.2408485758052058,
        -0.38270495973647617,
        0.599029209386089,
        -1.0,
        0.20487324615905156,
        0.06866910261967105,
        0.004107805504075277,
    ]
    reference_sense = [
        0.0,
        0.06871947673600003,
        0.2748779069440001,
        0.20615843020800007,
        0.0,
        0.34359738368000015,
        0.8933531975680004,
        0.20615843020800007,
    ]

    stage = AccelerationStage(48000.0, limit=0.32)
    measured = []
    senses = []
    for sample in reference_in:
        measured.append(stage.process_sample("L", sample))
        senses.append(stage.last_sense["L"])
    output_error = max(abs(a - b) for a, b in zip(measured, reference_out))
    sense_error = max(abs(a - b) for a, b in zip(senses, reference_sense))
    results = [
        require(
            "Acceleration output matches source-derived core vector",
            output_error < 1e-12,
            f"max error={output_error:.3e}",
        ),
        require(
            "Acceleration sense matches source-derived vector",
            sense_error < 1e-12,
            f"max error={sense_error:.3e}",
        ),
    ]

    def mean_sense(freq: float) -> float:
        detector = AccelerationStage(48000.0, limit=0.32)
        signal = make_sine(48000.0, freq, -6.0, 1.0)
        values = []
        for index, sample in enumerate(signal):
            detector.process_sample("L", sample)
            if index >= 24000:
                values.append(detector.last_sense["L"])
        return sum(values) / len(values)

    low = mean_sense(60.0)
    high = mean_sense(10000.0)
    ratio = high / max(low, 1e-300)
    results.append(require(
        "Acceleration detector strongly rejects LF",
        ratio >= 20.0,
        f"10k/60 mean-sense ratio={ratio:.1f}x",
    ))
    return results


def check_totape() -> list[bool]:
    results = []
    for fs in (44100.0, 48000.0):
        for crossover in TOTAPE_CROSSOVER_HZ:
            for gain in TOTAPE_ENV_GAIN:
                cfg = ToTapeHFConfig(crossover_hz=crossover, env_gain=gain)

                def settled_env(freq: float) -> tuple[float, bool]:
                    stage = ToTapeHFStage(fs, cfg)
                    signal = make_sine(fs, freq, -12.0, 1.0)
                    envs = []
                    finite = True
                    for index, sample in enumerate(signal):
                        output = stage.process_sample("L", sample)
                        finite = finite and math.isfinite(output)
                        if index >= int(0.5 * fs):
                            envs.append(stage.env["L"])
                    return sum(envs) / len(envs), finite

                low, finite_low = settled_env(60.0)
                high, finite_high = settled_env(10000.0)
                ratio = high / max(low, 1e-300)
                results.append(require(
                    f"ToTape selectivity {int(fs)} Hz / {int(crossover)} / {gain:g}",
                    finite_low and finite_high and ratio >= 20.0,
                    f"10k/60 envelope ratio={ratio:.1f}x",
                ))

    cfg = ToTapeHFConfig(crossover_hz=4000.0, env_gain=4.0)
    stage = ToTapeHFStage(48000.0, cfg)
    input_tone = make_sine(48000.0, 1000.0, -60.0, 0.5)
    output_tone = [stage.process_sample("L", x) for x in input_tone]
    start = int(0.1 * 48000.0)
    in_db = amp_to_db(project_tone_amplitude(input_tone, 48000.0, 1000.0, start))
    out_db = amp_to_db(project_tone_amplitude(output_tone, 48000.0, 1000.0, start))
    results.append(require(
        "ToTape inactive 1 kHz response is negligible",
        abs(out_db - in_db) < 0.01,
        f"delta={out_db-in_db:+.6f} dB",
    ))
    return results


def check_metrics() -> list[bool]:
    return [
        require(
            "max-slew helper matches hand calculation",
            abs(measure_max_slew([0.0, 0.25, -0.5, 0.75]) - 1.25) < 1e-15,
        )
    ]


def check_registry() -> list[bool]:
    expected = {"current-s6", "hf-sinew", "hf-acceleration", "hf-totape"}
    return [
        require("HF candidate registry is complete", set(HF_CANDIDATES) == expected),
        require("Sinew sweep is frozen", SINEW_AMOUNTS == (0.10, 0.20, 0.30, 0.40, 0.50)),
        require("Acceleration sweep is frozen", ACCEL_LIMITS == (0.16, 0.24, 0.32, 0.40)),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--section",
        choices=("all", "hf-sinew", "hf-acceleration", "hf-totape", "hf-metrics", "hf"),
        default="all",
    )
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results = []
    if args.section in ("all", "hf-sinew"):
        results += check_sinew()
    if args.section in ("all", "hf-acceleration"):
        results += check_acceleration()
    if args.section in ("all", "hf-totape"):
        results += check_totape()
    if args.section in ("all", "hf-metrics"):
        results += check_metrics()
    if args.section in ("all", "hf"):
        results += check_registry()
        report = build_hf_report()
        if args.json_out is not None:
            args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")

        for rate, payload in report["sample_rates"].items():
            no_s6 = payload["no_s6_reference"]
            print(f"\nHF comparison @ {rate} Hz")
            print(
                "  no-S6 reference: "
                f"coupling={no_s6['coupling_span_db']:.3f} dB, "
                f"inverse-drop={no_s6['inverse_efficiency_drop_db']:.3f} dB"
            )
            for row in payload["rows"]:
                marker = "*" if row["non_dominated"] else " "
                print(
                    f"{marker} {row['key']:16s} {str(row['params']):46s} "
                    f"coupling={row['coupling_span_db']:.3f} "
                    f"excess={row['coupling_excess_over_no_s6_db']:+.3f} "
                    f"inverse={row['inverse_efficiency_drop_db']:+.3f} "
                    f"action={row['hf_action_drop_vs_no_s6_db']:+.3f} "
                    f"FRerr={row['fr_rms_error_db']:.3f} "
                    f"IMD={row['imd_worst_db']:.1f} "
                    f"ops={row['ops_estimate']}"
                )

    passed = sum(results)
    total = len(results)
    print(f"\nDRAGON HF experiment audit: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
