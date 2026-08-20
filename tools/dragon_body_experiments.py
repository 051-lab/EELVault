#!/usr/bin/env python3
"""Focused Pear Body experiments for DRAGON.

Implements the exact eight-stage PearLite core first, then evaluates a one-knob
Body macro. Production DRAGON remains untouched.
"""

from __future__ import annotations

import itertools
import math
import statistics
import time
from dataclasses import dataclass

from dragon_experiments import DragonExperimentEngine, measure_stress_telemetry
from dragon_hf_experiments import HF_CANDIDATES

APPROVED_LEAN_LMID_DROP = (0.10, 0.20, 0.30)
APPROVED_LEAN_BASS_DROP = (0.00, 0.05, 0.10)
APPROVED_FULL_LMID_RISE = (0.05, 0.10)
APPROVED_FULL_BASS_RISE = (0.025, 0.05)
BODY_POSITIONS = (-1.0, -0.5, 0.0, 0.5, 1.0)

# Evidence-driven refinement: the original grid showed that reducing Pear LMid
# also reduces 50 Hz even with Bass unchanged. Negative "drop" means a small
# Bass compensation rise on the Lean side.
COMPENSATED_PROFILES = (
    (0.10, -0.05, 0.10, 0.025),
    (0.15, -0.075, 0.10, 0.025),
    (0.20, -0.10, 0.10, 0.025),
)

BODY_RESPONSE_FREQS = (50.0, 80.0, 100.0, 150.0, 200.0, 300.0, 500.0, 1000.0)
BODY_GROUP_DELAY_FREQS = (80.0, 100.0, 150.0, 200.0, 300.0, 500.0, 1000.0)
FULL_PEAR_STATE_COUNT = 96
FULL_PEAR_OPS_ESTIMATE = 528


class PearLiteStage:
    """Source-faithful PearLiteEQ core without dither."""

    def __init__(self, fs: float, high: float = 0.5, hmid: float = 0.5,
                 lmid: float = 0.5, bass: float = 0.5, stages: int = 8):
        if stages < 1:
            raise ValueError("stages must be >= 1")
        for value in (high, hmid, lmid, bass):
            if not 0.0 <= value <= 1.0:
                raise ValueError("Pear parameters must be in [0, 1]")

        self.fs = fs
        self.stages = stages
        self.parameters = (high, hmid, lmid, bass)
        overallscale = fs / 44100.0
        self.top_level = math.sqrt(high + 0.5)
        self.a_level = math.sqrt(hmid + 0.5)
        self.b_level = math.sqrt(lmid + 0.5)
        self.c_level = math.sqrt(bass + 0.5)
        freq_factor = math.sqrt(overallscale) + overallscale * 0.5
        self.freq_a = 0.564 ** (freq_factor + 0.85)
        self.freq_b = 0.564 ** (freq_factor + 4.1)
        self.freq_c = 0.564 ** (freq_factor + 7.1)

        self.state = {}
        for channel in ("L", "R"):
            self.state[channel] = {
                "A": [[0.0, 0.0] for _ in range(stages)],
                "B": [[0.0, 0.0] for _ in range(stages)],
                "C": [[0.0, 0.0] for _ in range(stages)],
            }

    @staticmethod
    def _filter(fig: float, pair: list[float], freq: float) -> float:
        previous, previous_slew = pair
        slew = ((fig - previous) + previous_slew) * freq * 0.5
        new_value = freq * fig + (1.0 - freq) * (previous + previous_slew)
        pair[0] = new_value
        pair[1] = slew
        return new_value

    def process_sample(self, channel: str, sample: float) -> float:
        x = sample
        states = self.state[channel]
        for index in range(self.stages):
            new_a = self._filter(x, states["A"][index], self.freq_a)
            x -= new_a
            new_b = self._filter(new_a, states["B"][index], self.freq_b)
            band_a = new_a - new_b
            new_c = self._filter(new_b, states["C"][index], self.freq_c)
            band_b = new_b - new_c
            x = (
                x * self.top_level
                + band_a * self.a_level
                + band_b * self.b_level
                + new_c * self.c_level
            )
        return x


@dataclass(frozen=True)
class PearBodyProfile:
    lean_lmid_drop: float
    lean_bass_drop: float
    full_lmid_rise: float
    full_bass_rise: float


def body_parameters(body: float, profile: PearBodyProfile) -> tuple[float, float, float, float]:
    body = max(-1.0, min(1.0, body))
    high = 0.5
    hmid = 0.5
    if body < 0.0:
        depth = -body
        lmid = 0.5 - depth * profile.lean_lmid_drop
        bass = 0.5 - depth * profile.lean_bass_drop
    else:
        lmid = 0.5 + body * profile.full_lmid_rise
        bass = 0.5 + body * profile.full_bass_rise
    return high, hmid, max(0.0, min(1.0, lmid)), max(0.0, min(1.0, bass))


class PearBodyStage:
    """One-control Body macro over exact PearLite LMid/Bass levels."""

    def __init__(self, fs: float, body: float, profile: PearBodyProfile, stages: int = 8):
        self.body = max(-1.0, min(1.0, body))
        self.profile = profile
        self.parameters = body_parameters(self.body, profile)
        self.core = PearLiteStage(fs, *self.parameters, stages=stages)

    def process_sample(self, channel: str, sample: float) -> float:
        processed = self.core.process_sample(channel, sample)
        if self.body == 0.0:
            return sample
        return processed


BODY_CANDIDATES = {
    "body-none": lambda fs, **params: None,
    "body-pear": lambda fs, **params: PearBodyStage(fs, **params),
}


def iter_body_profiles():
    for values in itertools.product(
        APPROVED_LEAN_LMID_DROP,
        APPROVED_LEAN_BASS_DROP,
        APPROVED_FULL_LMID_RISE,
        APPROVED_FULL_BASS_RISE,
    ):
        yield "approved", PearBodyProfile(*values)
    for values in COMPENSATED_PROFILES:
        yield "compensated", PearBodyProfile(*values)


def _pear_filter_transfer(freq_hz: float, fs: float, coeff: float) -> complex:
    """Exact z-domain transfer of one Pear two-state filter."""
    z = complex(math.cos(-2.0 * math.pi * freq_hz / fs), math.sin(-2.0 * math.pi * freq_hz / fs))
    a00 = 1.0 - coeff
    a01 = 1.0 - coeff
    a10 = -coeff * 0.5
    a11 = coeff * 0.5
    b0 = coeff
    b1 = coeff * 0.5
    c0 = 1.0 - coeff
    c1 = 1.0 - coeff
    d = coeff
    m00 = 1.0 - a00 * z
    m01 = -a01 * z
    m10 = -a10 * z
    m11 = 1.0 - a11 * z
    determinant = m00 * m11 - m01 * m10
    v0 = (m11 * b0 - m01 * b1) / determinant
    v1 = (-m10 * b0 + m00 * b1) / determinant
    return d + z * (c0 * v0 + c1 * v1)


def pear_transfer(fs: float, freq_hz: float,
                  parameters: tuple[float, float, float, float], stages: int = 8) -> complex:
    high, hmid, lmid, bass = parameters
    overallscale = fs / 44100.0
    freq_factor = math.sqrt(overallscale) + overallscale * 0.5
    freq_a = 0.564 ** (freq_factor + 0.85)
    freq_b = 0.564 ** (freq_factor + 4.1)
    freq_c = 0.564 ** (freq_factor + 7.1)
    ha = _pear_filter_transfer(freq_hz, fs, freq_a)
    hb = _pear_filter_transfer(freq_hz, fs, freq_b)
    hc = _pear_filter_transfer(freq_hz, fs, freq_c)
    top_level = math.sqrt(high + 0.5)
    a_level = math.sqrt(hmid + 0.5)
    b_level = math.sqrt(lmid + 0.5)
    c_level = math.sqrt(bass + 0.5)
    one_stage = (
        top_level * (1.0 - ha)
        + a_level * ha * (1.0 - hb)
        + b_level * ha * hb * (1.0 - hc)
        + c_level * ha * hb * hc
    )
    return one_stage ** stages


def body_response(fs: float, body: float, profile: PearBodyProfile,
                  stages: int = 8, frequencies=BODY_RESPONSE_FREQS) -> dict[float, float]:
    if body == 0.0:
        return {float(freq): 0.0 for freq in frequencies}
    parameters = body_parameters(body, profile)
    return {
        float(freq): 20.0 * math.log10(max(abs(pear_transfer(fs, float(freq), parameters, stages)), 1e-300))
        for freq in frequencies
    }


def group_delay_ms(fs: float, body: float, profile: PearBodyProfile,
                   center_hz: float, delta_hz: float = 1.0, stages: int = 8) -> float:
    if body == 0.0:
        return 0.0
    parameters = body_parameters(body, profile)
    low = pear_transfer(fs, center_hz - delta_hz, parameters, stages)
    high = pear_transfer(fs, center_hz + delta_hz, parameters, stages)
    ratio = high / low
    phase_delta = math.atan2(ratio.imag, ratio.real)
    seconds = -phase_delta / (2.0 * math.pi * (2.0 * delta_hz))
    return seconds * 1000.0


def make_body_engine(fs: float, body: float, profile: PearBodyProfile,
                     hf_key: str = "current-s6", hf_params: dict | None = None):
    hf_params = {} if hf_params is None else hf_params
    hf_stage = None
    if hf_key != "current-s6":
        hf_stage = HF_CANDIDATES[hf_key](fs, **hf_params)
    return DragonExperimentEngine(
        fs,
        hf_stage=hf_stage,
        body_stage=PearBodyStage(fs, body, profile),
        wf=0.0,
        hiss=-200.0,
        instrument=True,
    )


def measure_body_headroom(fs: float, body: float, profile: PearBodyProfile,
                          hf_key: str = "current-s6", hf_params: dict | None = None) -> dict[str, float]:
    return measure_stress_telemetry(
        lambda: make_body_engine(fs, body, profile, hf_key, hf_params),
        fs,
        frames=8192,
    )


def benchmark_full_pear(fs: float = 48000.0, repeats: int = 5) -> float:
    """Median local Python time for 48k stereo samples; not Android CPU truth."""
    timings = []
    for _ in range(repeats):
        stage = PearLiteStage(fs, 0.5, 0.5, 0.35, 0.575, stages=8)
        start = time.perf_counter()
        for index in range(48000):
            left = 0.3 * math.sin(2.0 * math.pi * 997.0 * index / fs)
            right = 0.3 * math.sin(2.0 * math.pi * 1511.0 * index / fs + 0.2)
            stage.process_sample("L", left)
            stage.process_sample("R", right)
        timings.append(time.perf_counter() - start)
    return statistics.median(timings)


def profile_static_metrics(fs: float, profile: PearBodyProfile, family: str) -> dict:
    lean = body_response(fs, -1.0, profile)
    full = body_response(fs, 1.0, profile)
    lean_group_delay = {
        str(int(freq)): group_delay_ms(fs, -1.0, profile, freq)
        for freq in BODY_GROUP_DELAY_FREQS
    }
    full_group_delay = {
        str(int(freq)): group_delay_ms(fs, 1.0, profile, freq)
        for freq in BODY_GROUP_DELAY_FREQS
    }
    return {
        "family": family,
        "profile": {
            "lean_lmid_drop": profile.lean_lmid_drop,
            "lean_bass_drop": profile.lean_bass_drop,
            "full_lmid_rise": profile.full_lmid_rise,
            "full_bass_rise": profile.full_bass_rise,
        },
        "lean_response_db": {str(int(k)): v for k, v in lean.items()},
        "full_response_db": {str(int(k)): v for k, v in full.items()},
        "lean_group_delay_ms": lean_group_delay,
        "full_group_delay_ms": full_group_delay,
        "headroom_lean": measure_body_headroom(fs, -1.0, profile),
        "headroom_reference": measure_body_headroom(fs, 0.0, profile),
        "headroom_full": measure_body_headroom(fs, 1.0, profile),
        "state_count": FULL_PEAR_STATE_COUNT,
        "ops_estimate": FULL_PEAR_OPS_ESTIMATE,
    }


def _body_dominates(a: dict, b: dict) -> bool:
    ar = a["lean_response_db"]
    br = b["lean_response_db"]
    a_obj = (
        ar["150"], ar["200"], ar["300"], abs(ar["50"]),
        max(abs(a["lean_group_delay_ms"]["100"]), abs(a["lean_group_delay_ms"]["200"]), abs(a["lean_group_delay_ms"]["300"])),
        a["headroom_lean"]["peak_pre_limiter"],
    )
    b_obj = (
        br["150"], br["200"], br["300"], abs(br["50"]),
        max(abs(b["lean_group_delay_ms"]["100"]), abs(b["lean_group_delay_ms"]["200"]), abs(b["lean_group_delay_ms"]["300"])),
        b["headroom_lean"]["peak_pre_limiter"],
    )
    return all(x <= y + 1e-12 for x, y in zip(a_obj, b_obj)) and any(
        x < y - 1e-12 for x, y in zip(a_obj, b_obj)
    )


def build_body_report() -> dict:
    report = {
        "full_pear_state_count": FULL_PEAR_STATE_COUNT,
        "full_pear_ops_estimate": FULL_PEAR_OPS_ESTIMATE,
        "sample_rates": {},
    }
    for fs in (44100.0, 48000.0):
        rows = [profile_static_metrics(fs, profile, family) for family, profile in iter_body_profiles()]
        for row in rows:
            row["non_dominated"] = not any(
                _body_dominates(other, row) for other in rows if other is not row
            )
        report["sample_rates"][str(int(fs))] = rows
    return report
