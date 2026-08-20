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
    20.0,
    30.0,
    50.0,
    80.0,
    100.0,
    150.0,
    200.0,
    300.0,
    500.0,
    1000.0,
    2000.0,
    5000.0,
    10000.0,
    14000.0,
    18000.0,
    20000.0,
)
CHALLENGER_LF_DB = (-30.0, -20.0, -12.0, -6.0, -3.0, 0.0)
CHALLENGER_HF_DB = -30.0
INVERSE_HF_DB = (-42.0, -36.0, -30.0, -24.0, -18.0, -12.0)


def db_to_amp(db: float) -> float:
    """Convert dB amplitude to linear amplitude."""
    return 10.0 ** (db / 20.0)


def amp_to_db(amp: float, floor_db: float = -300.0) -> float:
    """Convert linear amplitude to dB with a finite floor for zero."""
    if amp <= 0.0:
        return floor_db
    return max(floor_db, 20.0 * math.log10(amp))


def rms(values: list[float]) -> float:
    """Root-mean-square level of a finite sample vector."""
    if not values:
        return 0.0
    return math.sqrt(sum(x * x for x in values) / len(values))


def project_tone_amplitude(
    values: list[float],
    fs: float,
    freq: float,
    start: int = 0,
) -> float:
    """Project a coherent tone and return its peak sinusoidal amplitude."""
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


def make_sine(
    fs: float,
    freq: float,
    level_db: float,
    seconds: float,
    phase: float = 0.0,
) -> list[float]:
    """Generate a sine fixture at peak level ``level_db`` dBFS."""
    frames = int(round(fs * seconds))
    amp = db_to_amp(level_db)
    omega = 2.0 * math.pi * freq / fs
    return [amp * math.sin(omega * n + phase) for n in range(frames)]


def make_two_tone(
    fs: float,
    freq_a: float,
    level_a_db: float,
    freq_b: float,
    level_b_db: float,
    seconds: float,
) -> list[float]:
    """Generate a coherent two-tone fixture in floating-point headroom."""
    tone_a = make_sine(fs, freq_a, level_a_db, seconds)
    tone_b = make_sine(fs, freq_b, level_b_db, seconds)
    return [a + b for a, b in zip(tone_a, tone_b)]


def current_s6_cutoff(env: float) -> float:
    """Current DRAGON v1.0.0 S6 cutoff for a linked envelope value."""
    env_n = min(1.6, env * 2.0)
    return max(7000.0, 30000.0 / (1.0 + 3.0 * env_n))


def measure_frequency_response(
    engine_factory,
    fs: float,
    frequencies=FREQUENCY_PROBES,
    level_db: float = -60.0,
) -> dict[float, float]:
    """Measure coherent small-signal transfer magnitude in dB."""
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
    """Sweep LF level while keeping the 10 kHz probe fixed."""
    rows: list[dict[str, float]] = []
    start = int(0.1 * fs)
    reference_hf = None

    for lf_db in CHALLENGER_LF_DB:
        engine = engine_factory()
        signal = make_two_tone(
            fs,
            60.0,
            lf_db,
            10000.0,
            CHALLENGER_HF_DB,
            0.5,
        )
        output: list[float] = []
        for sample in signal:
            left, _ = engine.process(sample, sample)
            output.append(left)

        hf_out_db = amp_to_db(
            project_tone_amplitude(output, fs, 10000.0, start)
        )
        if reference_hf is None:
            reference_hf = hf_out_db
        rows.append({
            "lf_db": lf_db,
            "hf_out_db": hf_out_db,
            "delta_hf_db": hf_out_db - reference_hf,
        })
    return rows


def measure_inverse_hf_sweep(engine_factory, fs: float) -> list[dict[str, float]]:
    """Hold LF fixed and sweep 10 kHz level to verify HF responsiveness."""
    rows: list[dict[str, float]] = []
    start = int(0.1 * fs)

    for hf_db in INVERSE_HF_DB:
        engine = engine_factory()
        signal = make_two_tone(
            fs,
            60.0,
            -12.0,
            10000.0,
            hf_db,
            0.5,
        )
        output: list[float] = []
        for sample in signal:
            left, _ = engine.process(sample, sample)
            output.append(left)

        hf_out_db = amp_to_db(
            project_tone_amplitude(output, fs, 10000.0, start)
        )
        rows.append({
            "hf_in_db": hf_db,
            "hf_out_db": hf_out_db,
            "delta_from_input_db": hf_out_db - hf_db,
        })
    return rows


@dataclass
class StageTelemetry:
    """Peak/counter telemetry captured only by the experiment engine."""

    frames: int = 0
    limiter_hits: int = 0
    peak_s4: float = 0.0
    peak_s5: float = 0.0
    peak_s6: float = 0.0
    peak_pre_limiter: float = 0.0
    max_output: float = 0.0
    extras: dict[str, float] = field(default_factory=dict)


class DragonExperimentEngine(DragonEngine):
    """DRAGON reference engine with optional experiment-only stage hooks.

    With no hooks and ``instrument=False``, `_channel()` delegates directly to
    the authoritative `DragonEngine` implementation. This keeps baseline mode
    sample-identical while allowing later LF/HF/Body experiments to be inserted
    at explicit signal-path positions.
    """

    def __init__(
        self,
        fs,
        *,
        lf_stage=None,
        hf_stage=None,
        body_stage=None,
        instrument: bool = False,
        **kwargs,
    ):
        super().__init__(fs, **kwargs)
        self.lf_stage = lf_stage
        self.hf_stage = hf_stage
        self.body_stage = body_stage
        self.telemetry = StageTelemetry()
        self._instrument = instrument or any(
            stage is not None for stage in (lf_stage, hf_stage, body_stage)
        )

    def process(self, in_l, in_r):
        if self.lf_stage is not None:
            in_l, in_r = self.lf_stage.process_frame(in_l, in_r)

        out_l, out_r = super().process(in_l, in_r)
        if self._instrument:
            self.telemetry.frames += 1
            self.telemetry.max_output = max(
                self.telemetry.max_output,
                abs(out_l),
                abs(out_r),
            )
        return out_l, out_r

    def _channel(
        self,
        ch,
        x,
        driveLin,
        makeup,
        asym,
        gcomp,
        da,
        hissGain,
        trimLin,
        nz,
    ):
        if not self._instrument:
            return super()._channel(
                ch,
                x,
                driveLin,
                makeup,
                asym,
                gcomp,
                da,
                hissGain,
                trimLin,
                nz,
            )

        c = self.chains[ch]
        c["dm"].a = da

        # S1 input DC blocker
        x = c["dc1"].process(x)
        # S2 record emphasis shelf
        x = c["em"].process(x)
        # S3 anti-alias 2-pole LP
        x = c["aa2"].process(c["aa1"].process(x))
        # S4 compression gain (linked)
        x *= gcomp
        self.telemetry.peak_s4 = max(self.telemetry.peak_s4, abs(x))
        # S5 saturator
        s = x * driveLin
        v = math.tanh(s)
        x = (v + asym * v * v) * makeup
        self.telemetry.peak_s5 = max(self.telemetry.peak_s5, abs(x))
        # S6 baseline or experiment replacement
        if self.hf_stage is None:
            x = c["dm"].process(x)
        else:
            x = self.hf_stage.process_sample(ch, x)
        self.telemetry.peak_s6 = max(self.telemetry.peak_s6, abs(x))
        # S7 write into delay line / S7b bleed
        if ch == "L":
            self.mem[self.wp] = x
            x = self.dl_L + XTK * self.dl_R
        else:
            self.mem[WF_SIZE + self.wp] = x
            x = self.dl_R + XTK * self.dl_L
        # S8 replay EQ chain
        x = c["de"].process(x)
        x = c["iec"].process(x)
        x = c["hb"].process(x)
        x = c["lt"].process(x)
        x = c["hf"].process(x)
        # Body hook is post-replay-EQ and pre-hiss
        if self.body_stage is not None:
            x = self.body_stage.process_sample(ch, x)
        # S9 hiss
        hn = nz - c["hp"].process(nz)
        hn = c["h1"].process(hn)
        hn = c["h2"].process(hn)
        x += hn * hissGain
        # S10 trim
        x *= trimLin
        # S11 output DC blocker
        x = c["dc2"].process(x)
        self.telemetry.peak_pre_limiter = max(
            self.telemetry.peak_pre_limiter,
            abs(x),
        )
        # S12 soft limiter
        ax = abs(x)
        if ax > LIMIT_T:
            self.telemetry.limiter_hits += 1
            y = LIMIT_T + (1.0 - LIMIT_T) * math.tanh(
                (ax - LIMIT_T) * LIMIT_K
            )
            x = y if x > 0.0 else -y
        # S13 hard clamp
        return max(-CLAMP, min(CLAMP, x))
