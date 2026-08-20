#!/usr/bin/env python3
"""Shared numerical helpers for DRAGON adaptive-control experiments.

This module is intentionally standard-library-only and import-safe.  It does
not modify or replace the authoritative DRAGON v1.0.0 audit in
``tools/audit_dragon.py``; later experiment stages import these helpers and add
candidate-only models around the frozen baseline.
"""

from __future__ import annotations

import math


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
    """Project a coherent tone and return its peak sinusoidal amplitude.

    The direct complex projection is deliberately dependency-free.  Experiment
    fixtures use coherent durations so leakage is negligible for the requested
    probe frequencies.
    """
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
