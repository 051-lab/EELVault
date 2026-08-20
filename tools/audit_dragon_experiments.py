#!/usr/bin/env python3
"""Dependency-free audit entry point for DRAGON adaptive-control experiments."""

from __future__ import annotations

import argparse
import math

from audit_dragon import DragonEngine
from dragon_experiments import (
    CHALLENGER_LF_DB,
    FOUNDATION_ATTACK_MS,
    FOUNDATION_DETECTOR_HZ,
    FOUNDATION_MAX_HP_HZ,
    FOUNDATION_RELEASE_MS,
    FREQUENCY_PROBES,
    LEVEL_PROBES_DB,
    LF_PROBES,
    STONE_MAX_GR_DB,
    STONE_SPLIT_HZ,
    STONE_THRESHOLD,
    DragonExperimentEngine,
    FoundationGuard,
    FoundationGuardConfig,
    LiteralHighpassTight,
    StoneGuard,
    StoneGuardConfig,
    amp_to_db,
    current_s6_cutoff,
    db_to_amp,
    make_sine,
    make_two_tone,
    measure_challenger_coupling,
    measure_frequency_response,
    measure_inverse_hf_sweep,
    measure_lf_level_grid,
    measure_stress_telemetry,
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
    results.append(require("-6 dB converts to amplitude", abs(db_to_amp(-6.0) - 10.0 ** (-6.0 / 20.0)) < 1e-15))
    results.append(require("amplitude round-trip is stable", abs(amp_to_db(db_to_amp(-42.5)) + 42.5) < 1e-12))
    fs = 48000.0
    tone = make_sine(fs, 1000.0, -12.0, 0.1)
    results.append(require("sine RMS is correct", abs(rms(tone) - db_to_amp(-12.0) / math.sqrt(2.0)) < 1e-9))
    measured = project_tone_amplitude(tone, fs, 1000.0)
    results.append(require("coherent tone projection recovers amplitude", abs(amp_to_db(measured) + 12.0) < 1e-6))
    dual = make_two_tone(fs, 60.0, -6.0, 10000.0, -30.0, 0.5)
    results.append(require("two-tone fixture preserves 10 kHz component", abs(amp_to_db(project_tone_amplitude(dual, fs, 10000.0)) + 30.0) < 1e-5))
    return results


def _parity_error(fs: float, instrument: bool) -> float:
    reference = DragonEngine(fs, wf=0.0, hiss=-200.0)
    experiment = DragonExperimentEngine(fs, wf=0.0, hiss=-200.0, instrument=instrument)
    max_error = 0.0
    for n in range(4096):
        left = math.sin(2.0 * math.pi * 997.0 * n / fs) * 0.35
        right = math.sin(2.0 * math.pi * 1511.0 * n / fs + 0.37) * 0.27
        ref_l, ref_r = reference.process(left, right)
        exp_l, exp_r = experiment.process(left, right)
        max_error = max(max_error, abs(ref_l - exp_l), abs(ref_r - exp_r))
    return max_error


def check_parity() -> list[bool]:
    results: list[bool] = []
    for fs in (44100.0, 48000.0):
        err = _parity_error(fs, False)
        results.append(require(f"experiment engine baseline parity @ {int(fs)} Hz", err < 1e-15, f"max error={err:.3e}"))
        err = _parity_error(fs, True)
        results.append(require(f"instrumented path parity @ {int(fs)} Hz", err < 1e-15, f"max error={err:.3e}"))
    return results


def check_baseline_fr() -> list[bool]:
    results: list[bool] = []
    results.append(require("S6 cutoff at zero envelope is 30 kHz", abs(current_s6_cutoff(0.0) - 30000.0) < 1e-12))
    results.append(require("S6 cutoff lower bound is 7 kHz", current_s6_cutoff(10.0) == 7000.0))
    for fs in (44100.0, 48000.0):
        fr = measure_frequency_response(lambda fs=fs: DragonEngine(fs, wf=0.0, hiss=-200.0), fs)
        results.append(require(f"baseline FR finite @ {int(fs)} Hz", all(math.isfinite(value) for value in fr.values())))
        results.append(require(f"baseline FR contains required probes @ {int(fs)} Hz", all(freq in fr for freq in (50.0, 200.0, 10000.0, 18000.0))))
        print(f"\nBaseline small-signal FR @ {int(fs)} Hz")
        for freq in FREQUENCY_PROBES:
            print(f"  {freq:8.1f} Hz  {fr[freq]:+8.3f} dB")
    return results


def check_challenger() -> list[bool]:
    results: list[bool] = [require("canonical LF sweep is frozen", CHALLENGER_LF_DB == (-30.0, -20.0, -12.0, -6.0, -3.0, 0.0))]
    for fs in (44100.0, 48000.0):
        rows = measure_challenger_coupling(lambda fs=fs: DragonEngine(fs, wf=0.0, hiss=-200.0), fs)
        inverse = measure_inverse_hf_sweep(lambda fs=fs: DragonEngine(fs, wf=0.0, hiss=-200.0), fs)
        results.append(require(f"Challenger sweep returns six rows @ {int(fs)} Hz", len(rows) == 6))
        results.append(require(f"Challenger reference delta is zero @ {int(fs)} Hz", abs(rows[0]["delta_hf_db"]) < 1e-12))
        min_delta = min(row["delta_hf_db"] for row in rows[1:])
        results.append(require(f"baseline exposes LF-to-HF coupling @ {int(fs)} Hz", min_delta < -0.05, f"minimum delta={min_delta:+.3f} dB"))
        print(f"\nChallenger LF -> fixed 10 kHz coupling @ {int(fs)} Hz")
        for row in rows:
            print(f"  LF {row['lf_db']:+6.1f} dBFS  HF out {row['hf_out_db']:+8.3f} dBFS  delta {row['delta_hf_db']:+8.3f} dB")
        print(f"\nInverse fixed -12 dBFS LF / swept 10 kHz @ {int(fs)} Hz")
        for row in inverse:
            print(f"  HF in {row['hf_in_db']:+6.1f} dBFS  HF out {row['hf_out_db']:+8.3f} dBFS  transfer {row['delta_from_input_db']:+8.3f} dB")
    return results


def check_baseline_dynamics() -> list[bool]:
    results: list[bool] = []
    for fs in (44100.0, 48000.0):
        rows = measure_lf_level_grid(lambda fs=fs: DragonExperimentEngine(fs, wf=0.0, hiss=-200.0, instrument=True), fs)
        results.append(require(f"LF level grid complete @ {int(fs)} Hz", len(rows) == len(LF_PROBES) * len(LEVEL_PROBES_DB), f"rows={len(rows)}"))
        metrics = measure_stress_telemetry(lambda fs=fs: DragonExperimentEngine(fs, instrument=True), fs)
        results.append(require(f"stress telemetry finite @ {int(fs)} Hz", all(math.isfinite(value) for value in metrics.values())))
        results.append(require(f"limiter rate valid @ {int(fs)} Hz", 0.0 <= metrics["limiter_rate"] <= 1.0, f"rate={metrics['limiter_rate']:.6f}"))
        results.append(require(f"output respects hard clamp @ {int(fs)} Hz", metrics["max_output"] <= 0.99999 + 1e-9, f"peak={metrics['max_output']:.6f}"))
        print(f"\nBaseline LF level-grid summary @ {int(fs)} Hz")
        for freq in LF_PROBES:
            subset = [row for row in rows if row["freq_hz"] == freq]
            transfers = ", ".join(f"{row['input_db']:+.0f}:{row['transfer_db']:+.2f}dB" for row in subset)
            print(f"  {freq:6.1f} Hz  {transfers}")
        print(f"\nBaseline stage telemetry @ {int(fs)} Hz")
        for key, value in metrics.items():
            print(f"  {key:18s} {value:.9f}")
    return results


def check_lf_highpass() -> list[bool]:
    reference_in = [0.0, 0.25, -0.5, 0.75, -1.0]
    reference_out = [0.0, 0.2481625, -0.4951, 0.738997509375, -0.98047203]
    stage = LiteralHighpassTight(48000.0, highpass=0.20, tight_param=1.0)
    measured = [stage.process_frame(x, x)[0] for x in reference_in]
    error = max(abs(a - b) for a, b in zip(measured, reference_out))
    return [require("literal Highpass/Tight matches source-derived vector", error < 1e-12, f"max error={error:.3e}")]


def check_lf_foundation() -> list[bool]:
    results: list[bool] = []
    cfg = FoundationGuardConfig(detector_hz=120.0, attack_ms=5.0, release_ms=120.0, max_hp_hz=60.0)
    bypass = FoundationGuard(48000.0, cfg, amount=0.0)
    samples = [(0.1, -0.2), (0.5, 0.0), (-0.75, 0.25)]
    results.append(require("Foundation amount=0 is exact bypass", [bypass.process_frame(l, r) for l, r in samples] == samples))
    linked = FoundationGuard(48000.0, cfg, amount=1.0)
    linked.process_frame(0.9, 0.05)
    results.append(require("Foundation detector is stereo-linked", linked.last_env_l == linked.last_env_r == linked.env))

    stable = True
    combinations = 0
    for fs in (44100.0, 48000.0):
        for detector_hz in FOUNDATION_DETECTOR_HZ:
            for attack_ms in FOUNDATION_ATTACK_MS:
                for release_ms in FOUNDATION_RELEASE_MS:
                    for max_hp_hz in FOUNDATION_MAX_HP_HZ:
                        combinations += 1
                        stage = FoundationGuard(fs, FoundationGuardConfig(detector_hz, attack_ms, release_ms, max_hp_hz))
                        for n in range(int(2.0 * fs)):
                            left = 0.75 * math.sin(2.0 * math.pi * 40.0 * n / fs) + 0.45 * math.sin(2.0 * math.pi * 80.0 * n / fs) + 0.2 * math.sin(2.0 * math.pi * 200.0 * n / fs)
                            right = 0.6 * math.sin(2.0 * math.pi * 55.0 * n / fs + 0.3) + 0.25 * math.sin(2.0 * math.pi * 120.0 * n / fs)
                            out_l, out_r = stage.process_frame(left, right)
                            if not (math.isfinite(out_l) and math.isfinite(out_r) and stage.config.min_hp_hz <= stage.last_hp_hz <= max_hp_hz):
                                stable = False
                                break
                        if not stable:
                            break
    results.append(require("Foundation grid is finite and cutoff-bounded", stable, f"rate/config cases={combinations}"))
    return results


def check_lf_stone() -> list[bool]:
    results: list[bool] = []
    cfg = StoneGuardConfig(split_hz=120.0, threshold=0.25, max_gr_db=2.0)
    bypass = StoneGuard(48000.0, cfg, amount=0.0)
    values = [(0.1, -0.1), (0.7, 0.2), (-0.4, 0.9)]
    results.append(require("Stone guard amount=0 recombines to exact input", [bypass.process_frame(l, r) for l, r in values] == values))

    stable = True
    combinations = 0
    for fs in (44100.0, 48000.0):
        for split_hz in STONE_SPLIT_HZ:
            for threshold in STONE_THRESHOLD:
                for max_gr_db in STONE_MAX_GR_DB:
                    combinations += 1
                    stage = StoneGuard(fs, StoneGuardConfig(split_hz, threshold, max_gr_db))
                    for n in range(4096):
                        left = 0.9 * math.sin(2.0 * math.pi * 60.0 * n / fs)
                        right = 0.4 * math.sin(2.0 * math.pi * 90.0 * n / fs)
                        out_l, out_r = stage.process_frame(left, right)
                        if not (math.isfinite(out_l) and math.isfinite(out_r) and 0.0 <= stage.last_gr_db <= max_gr_db + 1e-12):
                            stable = False
                            break
    results.append(require("Stone guard grid is finite and GR-bounded", stable, f"rate/config cases={combinations}"))
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--section", choices=("all", "core", "parity", "baseline-fr", "challenger", "baseline-dynamics", "lf-highpass", "lf-foundation", "lf-stone"), default="all")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results: list[bool] = []
    if args.section in ("all", "core"): results += check_core()
    if args.section in ("all", "parity"): results += check_parity()
    if args.section in ("all", "baseline-fr"): results += check_baseline_fr()
    if args.section in ("all", "challenger"): results += check_challenger()
    if args.section in ("all", "baseline-dynamics"): results += check_baseline_dynamics()
    if args.section in ("all", "lf-highpass"): results += check_lf_highpass()
    if args.section in ("all", "lf-foundation"): results += check_lf_foundation()
    if args.section in ("all", "lf-stone"): results += check_lf_stone()
    passed = sum(results)
    total = len(results)
    print(f"\nDRAGON experiment audit: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
