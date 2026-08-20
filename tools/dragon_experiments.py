#!/usr/bin/env python3
"""Shared numerical helpers for DRAGON adaptive-control experiments.

This module is intentionally standard-library-only and import-safe. It does
not modify or replace the authoritative DRAGON v1.0.0 audit in
``tools/audit_dragon.py``; later experiment stages add candidate-only models
around that frozen baseline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from audit_dragon import (
    CLAMP,
    LIMIT_K,
    LIMIT_T,
    WF_SIZE,
    XTK,
    DragonEngine,
)

FREQUENCY_PROBES = (
    20.0, 30.0, 50.0, 80.0, 100.0, 150.0, 200.0, 300.0,
    500.0, 1000.0, 2000.0, 5000.0, 10000.0, 14000.0,
    18000.0, 20000.0,
)
CHALLENGER_LF_DB = (-30.0, -20.0, -12.0, -6.0, -3.0, 0.0)
CHALLENGER_HF_DB = -30.0
INVERSE_HF_DB = (-42.0, -36.0, -30.0, -24.0, -18.0, -12.0)
LF_PROBES = (50.0, 60.0, 80.0, 100.0, 150.0, 200.0, 300.0)
LEVEL_PROBES_DB = (-30.0, -18.0, -12.0, -6.0, -3.0)

FOUNDATION_DETECTOR_HZ = (80.0, 100.0, 120.0, 150.0)
FOUNDATION_ATTACK_MS = (5.0, 10.0)
FOUNDATION_RELEASE_MS = (80.0, 120.0)
FOUNDATION_MAX_HP_HZ = (45.0, 60.0, 75.0)
FOUNDATION_MIN_HP_HZ = 5.0
FOUNDATION_ENV_FLOOR = 0.10
FOUNDATION_ENV_CEIL = 0.70

STONE_SPLIT_HZ = (80.0, 100.0, 120.0, 150.0)
STONE_THRESHOLD = (0.15, 0.25)
STONE_MAX_GR_DB = (1.0, 2.0)
STONE_ATTACK_MS = 10.0
STONE_RELEASE_MS = 120.0


def db_to_amp(db: float) -> float:
    return 10.0 ** (db / 20.0)


def amp_to_db(amp: float, floor_db: float = -300.0) -> float:
    if amp <= 0.0:
        return floor_db
    return max(floor_db, 20.0 * math.log10(amp))


def rms(values: list[float]) -> float:
    if not values:
        return 0.0
    return math.sqrt(sum(x * x for x in values) / len(values))


def project_tone_amplitude(values: list[float], fs: float, freq: float, start: int = 0) -> float:
    data = values[start:]
    if not data:
        return 0.0
    real = 0.0
    imag = 0.0
    omega = 2.0 * math.pi * freq / fs
    for n, sample in enumerate(data, start=start):
        angle = omega * n
        real += sample * math.cos(angle)
        imag -= sample * math.sin(angle)
    return 2.0 * math.hypot(real, imag) / len(data)


def make_sine(fs: float, freq: float, level_db: float, seconds: float, phase: float = 0.0) -> list[float]:
    frames = int(round(fs * seconds))
    amp = db_to_amp(level_db)
    omega = 2.0 * math.pi * freq / fs
    return [amp * math.sin(omega * n + phase) for n in range(frames)]


def make_two_tone(fs: float, freq_a: float, level_a_db: float, freq_b: float, level_b_db: float, seconds: float) -> list[float]:
    tone_a = make_sine(fs, freq_a, level_a_db, seconds)
    tone_b = make_sine(fs, freq_b, level_b_db, seconds)
    return [a + b for a, b in zip(tone_a, tone_b)]


def current_s6_cutoff(env: float) -> float:
    env_n = min(1.6, env * 2.0)
    return max(7000.0, 30000.0 / (1.0 + 3.0 * env_n))


def measure_frequency_response(engine_factory, fs: float, frequencies=FREQUENCY_PROBES, level_db: float = -60.0) -> dict[float, float]:
    result: dict[float, float] = {}
    seconds = 0.5
    start = int(0.1 * fs)
    for freq in frequencies:
        engine = engine_factory()
        signal = make_sine(fs, freq, level_db, seconds)
        output: list[float] = []
        for sample in signal:
            left, _ = engine.process(sample, sample)
            output.append(left)
        measured = project_tone_amplitude(output, fs, freq, start=start)
        result[freq] = amp_to_db(measured) - level_db
    return result


def measure_challenger_coupling(engine_factory, fs: float) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    start = int(0.1 * fs)
    reference_hf = None
    for lf_db in CHALLENGER_LF_DB:
        engine = engine_factory()
        signal = make_two_tone(fs, 60.0, lf_db, 10000.0, CHALLENGER_HF_DB, 0.5)
        output: list[float] = []
        for sample in signal:
            left, _ = engine.process(sample, sample)
            output.append(left)
        hf_out_db = amp_to_db(project_tone_amplitude(output, fs, 10000.0, start))
        if reference_hf is None:
            reference_hf = hf_out_db
        rows.append({"lf_db": lf_db, "hf_out_db": hf_out_db, "delta_hf_db": hf_out_db - reference_hf})
    return rows


def measure_inverse_hf_sweep(engine_factory, fs: float) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    start = int(0.1 * fs)
    for hf_db in INVERSE_HF_DB:
        engine = engine_factory()
        signal = make_two_tone(fs, 60.0, -12.0, 10000.0, hf_db, 0.5)
        output: list[float] = []
        for sample in signal:
            left, _ = engine.process(sample, sample)
            output.append(left)
        hf_out_db = amp_to_db(project_tone_amplitude(output, fs, 10000.0, start))
        rows.append({"hf_in_db": hf_db, "hf_out_db": hf_out_db, "delta_from_input_db": hf_out_db - hf_db})
    return rows


def measure_lf_level_grid(engine_factory, fs: float) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    seconds = 0.25
    start = int(0.05 * fs)
    for freq in LF_PROBES:
        for level_db in LEVEL_PROBES_DB:
            engine = engine_factory()
            signal = make_sine(fs, freq, level_db, seconds)
            output: list[float] = []
            for sample in signal:
                left, _ = engine.process(sample, sample)
                output.append(left)
            measured = project_tone_amplitude(output, fs, freq, start=start)
            output_db = amp_to_db(measured)
            rows.append({"freq_hz": freq, "input_db": level_db, "output_db": output_db, "transfer_db": output_db - level_db})
    return rows


def measure_stress_telemetry(engine_factory, fs: float, frames: int = 8192) -> dict[str, float]:
    engine = engine_factory()
    for i in range(frames):
        state = (i * 2654435761) & 0xFFFFFFFF
        left = (state / 0xFFFFFFFF) * 2.0 - 1.0
        state = (i * 2654435761 + 1013904223) & 0xFFFFFFFF
        right = (state / 0xFFFFFFFF) * 2.0 - 1.0
        out_l, out_r = engine.process(left, right)
        if not (math.isfinite(out_l) and math.isfinite(out_r)):
            return {key: float("inf") for key in ("peak_s4", "peak_s5", "peak_s6", "peak_pre_limiter", "max_output", "limiter_rate")}
    telemetry = engine.telemetry
    return {
        "peak_s4": telemetry.peak_s4,
        "peak_s5": telemetry.peak_s5,
        "peak_s6": telemetry.peak_s6,
        "peak_pre_limiter": telemetry.peak_pre_limiter,
        "max_output": telemetry.max_output,
        "limiter_rate": telemetry.limiter_hits / max(1, telemetry.frames * 2),
    }


@dataclass
class StageTelemetry:
    frames: int = 0
    limiter_hits: int = 0
    peak_s4: float = 0.0
    peak_s5: float = 0.0
    peak_s6: float = 0.0
    peak_pre_limiter: float = 0.0
    max_output: float = 0.0
    extras: dict[str, float] = field(default_factory=dict)


class DragonExperimentEngine(DragonEngine):
    def __init__(self, fs, *, lf_stage=None, hf_stage=None, body_stage=None, instrument: bool = False, **kwargs):
        super().__init__(fs, **kwargs)
        self.lf_stage = lf_stage
        self.hf_stage = hf_stage
        self.body_stage = body_stage
        self.telemetry = StageTelemetry()
        self._instrument = instrument or any(stage is not None for stage in (lf_stage, hf_stage, body_stage))

    def process(self, in_l, in_r):
        if self.lf_stage is not None:
            in_l, in_r = self.lf_stage.process_frame(in_l, in_r)
        out_l, out_r = super().process(in_l, in_r)
        if self._instrument:
            self.telemetry.frames += 1
            self.telemetry.max_output = max(self.telemetry.max_output, abs(out_l), abs(out_r))
        return out_l, out_r

    def _channel(self, ch, x, driveLin, makeup, asym, gcomp, da, hissGain, trimLin, nz):
        if not self._instrument:
            return super()._channel(ch, x, driveLin, makeup, asym, gcomp, da, hissGain, trimLin, nz)
        c = self.chains[ch]
        c["dm"].a = da
        x = c["dc1"].process(x)
        x = c["em"].process(x)
        x = c["aa2"].process(c["aa1"].process(x))
        x *= gcomp
        self.telemetry.peak_s4 = max(self.telemetry.peak_s4, abs(x))
        s = x * driveLin
        v = math.tanh(s)
        x = (v + asym * v * v) * makeup
        self.telemetry.peak_s5 = max(self.telemetry.peak_s5, abs(x))
        if self.hf_stage is None:
            x = c["dm"].process(x)
        else:
            x = self.hf_stage.process_sample(ch, x)
        self.telemetry.peak_s6 = max(self.telemetry.peak_s6, abs(x))
        if ch == "L":
            self.mem[self.wp] = x
            x = self.dl_L + XTK * self.dl_R
        else:
            self.mem[WF_SIZE + self.wp] = x
            x = self.dl_R + XTK * self.dl_L
        x = c["de"].process(x)
        x = c["iec"].process(x)
        x = c["hb"].process(x)
        x = c["lt"].process(x)
        x = c["hf"].process(x)
        if self.body_stage is not None:
            x = self.body_stage.process_sample(ch, x)
        hn = nz - c["hp"].process(nz)
        hn = c["h1"].process(hn)
        hn = c["h2"].process(hn)
        x += hn * hissGain
        x *= trimLin
        x = c["dc2"].process(x)
        self.telemetry.peak_pre_limiter = max(self.telemetry.peak_pre_limiter, abs(x))
        ax = abs(x)
        if ax > LIMIT_T:
            self.telemetry.limiter_hits += 1
            y = LIMIT_T + (1.0 - LIMIT_T) * math.tanh((ax - LIMIT_T) * LIMIT_K)
            x = y if x > 0.0 else -y
        return max(-CLAMP, min(CLAMP, x))


class PassthroughLF:
    def process_frame(self, left: float, right: float) -> tuple[float, float]:
        return left, right


class LiteralHighpassTight:
    """Source-faithful Airwindows Highpass Tight core, without wet/dither."""
    def __init__(self, fs: float, highpass: float = 0.20, tight_param: float = 1.0):
        overallscale = fs / 44100.0
        self.iir_amount = (highpass ** 3) / overallscale
        tight = tight_param * 2.0 - 1.0
        self.iir_amount += self.iir_amount * tight * tight
        self.tight = tight / 1.5 if tight > 0.0 else tight / 3.0
        self.iir_amount = max(0.0, min(1.0, self.iir_amount))
        self.flip = True
        self.a_l = self.b_l = self.a_r = self.b_r = 0.0

    def _one(self, sample: float, channel: str) -> float:
        if self.tight > 0.0:
            offset = (1.0 - self.tight) + abs(sample) * self.tight
        else:
            offset = (1.0 + self.tight) + (1.0 - abs(sample)) * self.tight
        offset = max(0.0, min(1.0, offset))
        coeff = offset * self.iir_amount
        if channel == "L":
            if self.flip:
                self.a_l = self.a_l * (1.0 - coeff) + sample * coeff
                return sample - self.a_l
            self.b_l = self.b_l * (1.0 - coeff) + sample * coeff
            return sample - self.b_l
        if self.flip:
            self.a_r = self.a_r * (1.0 - coeff) + sample * coeff
            return sample - self.a_r
        self.b_r = self.b_r * (1.0 - coeff) + sample * coeff
        return sample - self.b_r

    def process_frame(self, left: float, right: float) -> tuple[float, float]:
        out_l = self._one(left, "L")
        out_r = self._one(right, "R")
        self.flip = not self.flip
        return out_l, out_r


@dataclass(frozen=True)
class FoundationGuardConfig:
    detector_hz: float
    attack_ms: float
    release_ms: float
    max_hp_hz: float
    min_hp_hz: float = FOUNDATION_MIN_HP_HZ
    env_floor: float = FOUNDATION_ENV_FLOOR
    env_ceil: float = FOUNDATION_ENV_CEIL


class FoundationGuard:
    """Smoothed stereo-linked DRAGON derivative of Highpass Tight."""
    def __init__(self, fs: float, config: FoundationGuardConfig, amount: float = 1.0):
        self.fs = fs
        self.config = config
        self.amount = amount
        self.det_a = 1.0 - math.exp(-2.0 * math.pi * config.detector_hz / fs)
        self.attack = math.exp(-1.0 / (config.attack_ms * 0.001 * fs))
        self.release = math.exp(-1.0 / (config.release_ms * 0.001 * fs))
        self.det_l = self.det_r = 0.0
        self.hp_l = self.hp_r = 0.0
        self.env = 0.0
        self.last_env_l = self.last_env_r = 0.0
        self.last_hp_hz = config.min_hp_hz

    def process_frame(self, left: float, right: float) -> tuple[float, float]:
        if self.amount <= 0.0:
            return left, right
        self.det_l += self.det_a * (left - self.det_l)
        self.det_r += self.det_a * (right - self.det_r)
        target = max(abs(self.det_l), abs(self.det_r))
        coeff = self.attack if target >= self.env else self.release
        self.env = coeff * self.env + (1.0 - coeff) * target
        self.last_env_l = self.last_env_r = self.env
        span = max(1.0e-12, self.config.env_ceil - self.config.env_floor)
        normalized = max(0.0, min(1.0, (self.env - self.config.env_floor) / span))
        normalized *= normalized
        cutoff = self.config.min_hp_hz + self.amount * normalized * (self.config.max_hp_hz - self.config.min_hp_hz)
        cutoff = max(self.config.min_hp_hz, min(self.config.max_hp_hz, cutoff))
        self.last_hp_hz = cutoff
        hp_a = 1.0 - math.exp(-2.0 * math.pi * cutoff / self.fs)
        self.hp_l += hp_a * (left - self.hp_l)
        self.hp_r += hp_a * (right - self.hp_r)
        return left - self.hp_l, right - self.hp_r


@dataclass(frozen=True)
class StoneGuardConfig:
    split_hz: float
    threshold: float
    max_gr_db: float
    attack_ms: float = STONE_ATTACK_MS
    release_ms: float = STONE_RELEASE_MS


class StoneGuard:
    """Lightweight complementary foundation split with shallow linked GR."""
    def __init__(self, fs: float, config: StoneGuardConfig, amount: float = 1.0):
        self.fs = fs
        self.config = config
        self.amount = amount
        self.split_a = 1.0 - math.exp(-2.0 * math.pi * config.split_hz / fs)
        self.attack = math.exp(-1.0 / (config.attack_ms * 0.001 * fs))
        self.release = math.exp(-1.0 / (config.release_ms * 0.001 * fs))
        self.stone_l = self.stone_r = 0.0
        self.env = 0.0
        self.last_gr_db = 0.0

    def process_frame(self, left: float, right: float) -> tuple[float, float]:
        if self.amount <= 0.0:
            return left, right
        self.stone_l += self.split_a * (left - self.stone_l)
        self.stone_r += self.split_a * (right - self.stone_r)
        remainder_l = left - self.stone_l
        remainder_r = right - self.stone_r
        target = max(abs(self.stone_l), abs(self.stone_r))
        coeff = self.attack if target >= self.env else self.release
        self.env = coeff * self.env + (1.0 - coeff) * target
        over = max(0.0, self.env - self.config.threshold) / max(1.0e-12, 1.0 - self.config.threshold)
        gr_db = min(self.config.max_gr_db, self.amount * self.config.max_gr_db * over * over)
        self.last_gr_db = gr_db
        gain = db_to_amp(-gr_db)
        return remainder_l + self.stone_l * gain, remainder_r + self.stone_r * gain
