#!/usr/bin/env python3
"""Focused HF candidate models and measurements for DRAGON experiments.

This module intentionally sits beside ``dragon_experiments.py`` instead of
making that shared LF/baseline module larger. Production DRAGON is not touched.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

from dragon_experiments import (
    DragonExperimentEngine,
    amp_to_db,
    db_to_amp,
    make_sine,
    make_two_tone,
    measure_challenger_coupling,
    measure_frequency_response,
    measure_inverse_hf_sweep,
)

SINEW_AMOUNTS = (0.10, 0.20, 0.30, 0.40, 0.50)
ACCEL_LIMITS = (0.16, 0.24, 0.32, 0.40)
TOTAPE_CROSSOVER_HZ = (2500.0, 4000.0, 6000.0)
TOTAPE_ENV_GAIN = (2.0, 4.0, 8.0)

HF_COSTS = {
    "current-s6": {"state_count": 2, "ops_estimate": 18, "transcendentals_per_frame": 1},
    "hf-sinew": {"state_count": 2, "ops_estimate": 20, "transcendentals_per_frame": 2},
    "hf-acceleration": {"state_count": 16, "ops_estimate": 58, "transcendentals_per_frame": 0},
    "hf-totape": {"state_count": 6, "ops_estimate": 50, "transcendentals_per_frame": 2},
}


class PassthroughHF:
    """Reference hook that removes S6 without adding a replacement action."""

    def process_sample(self, channel: str, sample: float) -> float:
        return sample


class SinewStage:
    """Exact Airwindows Sinew core, excluding dither."""

    def __init__(self, fs: float, amount: float = 0.5):
        if not 0.0 <= amount <= 1.0:
            raise ValueError("amount must be in [0, 1]")
        self.threshold = ((1.0 - amount) ** 4) / (fs / 44100.0)
        self.last = {"L": 0.0, "R": 0.0}
        self.clamp_events = 0

    def process_sample(self, channel: str, sample: float) -> float:
        previous = self.last[channel]
        allowed = self.threshold * math.cos(previous * previous)
        delta = sample - previous
        output = sample
        if delta > allowed:
            output = previous + allowed
            self.clamp_events += 1
        elif -delta > allowed:
            output = previous - allowed
            self.clamp_events += 1
        output = max(-1.0, min(1.0, output))
        self.last[channel] = output
        return output


class AccelerationStage:
    """Acceleration2 detector + first dynamic smoother, without final 20 kHz LP."""

    def __init__(self, fs: float, limit: float = 0.32):
        if not 0.0 <= limit <= 1.0:
            raise ValueError("limit must be in [0, 1]")
        self.fs = fs
        self.limit = limit
        overallscale = fs / 44100.0
        self.intensity = (limit ** 3) * 32.0
        self.spacing = min(16, int(1.73 * overallscale) + 1)

        cutoff = 20000.0 * (1.0 - limit * 0.6180339887498948)
        normalized = cutoff / fs
        k = math.tan(math.pi * normalized)
        q = 0.7071
        norm = 1.0 / (1.0 + k / q + k * k)
        self.b0 = k * k * norm
        self.b1 = 2.0 * self.b0
        self.b2 = self.b0
        self.a1 = 2.0 * (k * k - 1.0) * norm
        self.a2 = (1.0 - k / q + k * k) * norm

        self.history = {"L": [0.0] * 34, "R": [0.0] * 34}
        self.z1 = {"L": 0.0, "R": 0.0}
        self.z2 = {"L": 0.0, "R": 0.0}
        self.last_sense = {"L": 0.0, "R": 0.0}
        self.max_sense = {"L": 0.0, "R": 0.0}

    def process_sample(self, channel: str, sample: float) -> float:
        smooth = sample * self.b0 + self.z1[channel]
        self.z1[channel] = sample * self.b1 - smooth * self.a1 + self.z2[channel]
        self.z2[channel] = sample * self.b2 - smooth * self.a2

        history = self.history[channel]
        for count in range(self.spacing * 2, -1, -1):
            history[count + 1] = history[count]
        history[0] = sample

        d1 = history[0] - history[self.spacing]
        d2 = history[self.spacing] - history[self.spacing * 2]
        m1 = d1 * abs(d1)
        m2 = d2 * abs(d2)
        sense = min(1.0, self.intensity * self.intensity * abs(m1 - m2))
        self.last_sense[channel] = sense
        self.max_sense[channel] = max(self.max_sense[channel], sense)
        return sample * (1.0 - sense) + smooth * sense


@dataclass(frozen=True)
class ToTapeHFConfig:
    crossover_hz: float
    env_gain: float
    attack_ms: float = 2.0
    release_ms: float = 50.0
    min_damp_hz: float = 7000.0
    max_damp_hz: float = 30000.0


class ToTapeHFStage:
    """HF-residual detector driving DRAGON's existing one-pole damping map."""

    def __init__(self, fs: float, config: ToTapeHFConfig):
        self.fs = fs
        self.config = config
        self.lp_a = 1.0 - math.exp(-2.0 * math.pi * config.crossover_hz / fs)
        self.attack = math.exp(-1.0 / (config.attack_ms * 0.001 * fs))
        self.release = math.exp(-1.0 / (config.release_ms * 0.001 * fs))
        self.low = {"L": 0.0, "R": 0.0}
        self.env = {"L": 0.0, "R": 0.0}
        self.damp = {"L": 0.0, "R": 0.0}
        self.last_dfc = {"L": config.max_damp_hz, "R": config.max_damp_hz}
        self.max_env = {"L": 0.0, "R": 0.0}

    def process_sample(self, channel: str, sample: float) -> float:
        self.low[channel] += self.lp_a * (sample - self.low[channel])
        residual = sample - self.low[channel]
        target = abs(residual)
        coeff = self.attack if target >= self.env[channel] else self.release
        self.env[channel] = coeff * self.env[channel] + (1.0 - coeff) * target
        self.max_env[channel] = max(self.max_env[channel], self.env[channel])

        env_n = min(1.6, self.env[channel] * self.config.env_gain)
        dfc = max(
            self.config.min_damp_hz,
            self.config.max_damp_hz / (1.0 + 3.0 * env_n),
        )
        self.last_dfc[channel] = dfc
        damp_a = 1.0 - math.exp(-2.0 * math.pi * dfc / self.fs)
        self.damp[channel] += damp_a * (sample - self.damp[channel])
        return self.damp[channel]


HF_CANDIDATES = {
    "current-s6": None,
    "hf-sinew": lambda fs, **params: SinewStage(fs, **params),
    "hf-acceleration": lambda fs, **params: AccelerationStage(fs, **params),
    "hf-totape": lambda fs, **params: ToTapeHFStage(fs, ToTapeHFConfig(**params)),
}


def iter_hf_configs():
    yield "current-s6", {}
    for amount in SINEW_AMOUNTS:
        yield "hf-sinew", {"amount": amount}
    for limit in ACCEL_LIMITS:
        yield "hf-acceleration", {"limit": limit}
    for crossover_hz, env_gain in itertools.product(
        TOTAPE_CROSSOVER_HZ, TOTAPE_ENV_GAIN
    ):
        yield "hf-totape", {
            "crossover_hz": crossover_hz,
            "env_gain": env_gain,
        }


def make_hf_engine(fs: float, key: str, params: dict):
    if key == "current-s6":
        return DragonExperimentEngine(
            fs, wf=0.0, hiss=-200.0, instrument=True
        )
    stage = HF_CANDIDATES[key](fs, **params)
    return DragonExperimentEngine(
        fs,
        hf_stage=stage,
        wf=0.0,
        hiss=-200.0,
        instrument=True,
    )


def make_no_s6_engine(fs: float):
    return DragonExperimentEngine(
        fs,
        hf_stage=PassthroughHF(),
        wf=0.0,
        hiss=-200.0,
        instrument=True,
    )


def coupling_span(rows: list[dict[str, float]]) -> float:
    values = [row["delta_hf_db"] for row in rows]
    return max(values) - min(values)


def inverse_efficiency_drop(rows: list[dict[str, float]]) -> float:
    """Change in HF transfer from quietest to hottest HF probe.

    Negative means output efficiency falls as HF input rises.
    """
    return rows[-1]["delta_from_input_db"] - rows[0]["delta_from_input_db"]


def measure_max_slew(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return max(abs(b - a) for a, b in zip(values, values[1:]))


def _run_engine(engine_factory, signal: list[float]) -> list[float]:
    engine = engine_factory()
    return [engine.process(sample, sample)[0] for sample in signal]


def _project_ratio(
    values: list[float], fs: float, numerator_hz: float, denominator_hz: float,
    start: int
) -> float:
    from dragon_experiments import project_tone_amplitude

    numerator = project_tone_amplitude(values, fs, numerator_hz, start)
    denominator = project_tone_amplitude(values, fs, denominator_hz, start)
    return amp_to_db(numerator / max(denominator, 1e-300))


def measure_hf_imd(
    engine_factory,
    fs: float,
    low_freq: float,
    low_level_db: float,
    high_freq: float = 10000.0,
    high_level_db: float = -18.0,
) -> dict[str, float]:
    signal = make_two_tone(
        fs, low_freq, low_level_db, high_freq, high_level_db, 0.5
    )
    output = _run_engine(engine_factory, signal)
    start = int(0.1 * fs)
    lower = high_freq - low_freq
    upper = high_freq + low_freq
    return {
        "lower_db": _project_ratio(output, fs, lower, high_freq, start),
        "upper_db": _project_ratio(output, fs, upper, high_freq, start),
    }


def measure_tone_burst(
    engine_factory, fs: float, freq: float, level_db: float = -6.0
) -> dict[str, float]:
    pre = int(round(0.020 * fs))
    tone_n = int(round(0.040 * fs))
    post = int(round(0.040 * fs))
    amp = db_to_amp(level_db)
    signal = [0.0] * pre
    signal.extend(
        amp * math.sin(2.0 * math.pi * freq * n / fs)
        for n in range(tone_n)
    )
    signal.extend([0.0] * post)
    output = _run_engine(engine_factory, signal)

    tone = output[pre : pre + tone_n]
    settled = tone[-max(1, int(0.010 * fs)) :]
    release = output[pre + tone_n : pre + tone_n + max(1, int(0.020 * fs))]
    return {
        "attack_peak": max(abs(x) for x in tone) if tone else 0.0,
        "settled_rms": math.sqrt(
            sum(x * x for x in settled) / max(1, len(settled))
        ),
        "release_tail_peak": max(abs(x) for x in release) if release else 0.0,
    }


def measure_edge_response(engine_factory, fs: float) -> dict[str, float]:
    impulse = [1.0] + [0.0] * 4095
    impulse_out = _run_engine(engine_factory, impulse)

    amp = db_to_amp(-12.0)
    square = [
        amp if math.sin(2.0 * math.pi * 1000.0 * n / fs) >= 0.0 else -amp
        for n in range(4096)
    ]
    square_out = _run_engine(engine_factory, square)
    return {
        "impulse_peak": max(abs(x) for x in impulse_out),
        "impulse_first32_abs_sum": sum(abs(x) for x in impulse_out[:32]),
        "square_max_slew": measure_max_slew(square_out),
        "square_overshoot": max(
            0.0, max(abs(x) for x in square_out) - amp
        ),
    }


def _fr_rms_error(candidate: dict[float, float], baseline: dict[float, float]) -> float:
    diffs = [candidate[f] - baseline[f] for f in baseline]
    return math.sqrt(sum(x * x for x in diffs) / len(diffs))


def _hf_dominates(a: dict, b: dict) -> bool:
    aa = (
        a["coupling_span_db"],
        a["fr_rms_error_db"],
        a["imd_worst_db"],
        a["ops_estimate"],
    )
    bb = (
        b["coupling_span_db"],
        b["fr_rms_error_db"],
        b["imd_worst_db"],
        b["ops_estimate"],
    )
    return all(x <= y + 1e-12 for x, y in zip(aa, bb)) and any(
        x < y - 1e-12 for x, y in zip(aa, bb)
    )


def build_hf_report() -> dict:
    report = {"sample_rates": {}}
    for fs in (44100.0, 48000.0):
        baseline_fr = measure_frequency_response(
            lambda fs=fs: make_hf_engine(fs, "current-s6", {}), fs
        )
        no_s6_coupling = measure_challenger_coupling(
            lambda fs=fs: make_no_s6_engine(fs), fs
        )
        no_s6_inverse = measure_inverse_hf_sweep(
            lambda fs=fs: make_no_s6_engine(fs), fs
        )
        no_s6_span = coupling_span(no_s6_coupling)
        no_s6_drop = inverse_efficiency_drop(no_s6_inverse)

        rows = []
        for key, params in iter_hf_configs():
            factory = lambda fs=fs, key=key, params=params: make_hf_engine(
                fs, key, params
            )
            coupling = measure_challenger_coupling(factory, fs)
            inverse = measure_inverse_hf_sweep(factory, fs)
            fr = measure_frequency_response(factory, fs)
            imd_60 = measure_hf_imd(factory, fs, 60.0, -6.0)
            imd_1k = measure_hf_imd(factory, fs, 1000.0, -12.0)
            edge = measure_edge_response(factory, fs)
            bursts = {
                str(int(freq)): measure_tone_burst(factory, fs, freq)
                for freq in (1000.0, 5000.0, 10000.0, 15000.0)
            }

            imd_worst = max(
                imd_60["lower_db"],
                imd_60["upper_db"],
                imd_1k["lower_db"],
                imd_1k["upper_db"],
            )
            cost = HF_COSTS[key]
            row = {
                "key": key,
                "params": params,
                "coupling": coupling,
                "coupling_span_db": coupling_span(coupling),
                "coupling_excess_over_no_s6_db": (
                    coupling_span(coupling) - no_s6_span
                ),
                "inverse": inverse,
                "inverse_efficiency_drop_db": inverse_efficiency_drop(inverse),
                "hf_action_drop_vs_no_s6_db": (
                    inverse_efficiency_drop(inverse) - no_s6_drop
                ),
                "fr": fr,
                "fr_rms_error_db": _fr_rms_error(fr, baseline_fr),
                "imd_60_10k": imd_60,
                "imd_1k_10k": imd_1k,
                "imd_worst_db": imd_worst,
                "bursts": bursts,
                "edge": edge,
                **cost,
            }
            row["inverse_responsive"] = row["inverse_efficiency_drop_db"] < 0.0
            rows.append(row)

        for row in rows:
            eligible = [x for x in rows if x["inverse_responsive"]]
            row["non_dominated"] = (
                row["inverse_responsive"]
                and not any(
                    _hf_dominates(other, row)
                    for other in eligible
                    if other is not row
                )
            )

        report["sample_rates"][str(int(fs))] = {
            "no_s6_reference": {
                "coupling_span_db": no_s6_span,
                "inverse_efficiency_drop_db": no_s6_drop,
            },
            "rows": rows,
        }
    return report
