#!/usr/bin/env python3
"""Shared numerical helpers for DRAGON adaptive-control experiments.

Standard-library-only. The authoritative v1.0.0 model remains
``tools/audit_dragon.py``; this module contains experiment-only hooks, fixtures,
and candidate models.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

from audit_dragon import CLAMP, LIMIT_K, LIMIT_T, WF_SIZE, XTK, DragonEngine

FREQUENCY_PROBES = (20.0, 30.0, 50.0, 80.0, 100.0, 150.0, 200.0, 300.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0, 14000.0, 18000.0, 20000.0)
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

LF_COSTS = {
    "none": {"state_count": 0, "ops_estimate": 0, "transcendentals_per_frame": 0},
    "lf-highpass-literal": {"state_count": 5, "ops_estimate": 26, "transcendentals_per_frame": 0},
    "lf-foundation": {"state_count": 5, "ops_estimate": 45, "transcendentals_per_frame": 1},
    "lf-stone-light": {"state_count": 3, "ops_estimate": 34, "transcendentals_per_frame": 1},
}


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
    real = imag = 0.0
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
    a = make_sine(fs, freq_a, level_a_db, seconds)
    b = make_sine(fs, freq_b, level_b_db, seconds)
    return [x + y for x, y in zip(a, b)]


def current_s6_cutoff(env: float) -> float:
    env_n = min(1.6, env * 2.0)
    return max(7000.0, 30000.0 / (1.0 + 3.0 * env_n))


def measure_frequency_response(engine_factory, fs: float, frequencies=FREQUENCY_PROBES, level_db: float = -60.0) -> dict[float, float]:
    result: dict[float, float] = {}
    start = int(0.1 * fs)
    for freq in frequencies:
        engine = engine_factory()
        signal = make_sine(fs, freq, level_db, 0.5)
        output = [engine.process(sample, sample)[0] for sample in signal]
        result[freq] = amp_to_db(project_tone_amplitude(output, fs, freq, start)) - level_db
    return result


def measure_challenger_coupling(engine_factory, fs: float) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    start = int(0.1 * fs)
    reference_hf = None
    for lf_db in CHALLENGER_LF_DB:
        engine = engine_factory()
        signal = make_two_tone(fs, 60.0, lf_db, 10000.0, CHALLENGER_HF_DB, 0.5)
        output = [engine.process(sample, sample)[0] for sample in signal]
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
        output = [engine.process(sample, sample)[0] for sample in signal]
        hf_out_db = amp_to_db(project_tone_amplitude(output, fs, 10000.0, start))
        rows.append({"hf_in_db": hf_db, "hf_out_db": hf_out_db, "delta_from_input_db": hf_out_db - hf_db})
    return rows


def measure_lf_level_grid(engine_factory, fs: float) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    start = int(0.05 * fs)
    for freq in LF_PROBES:
        for level_db in LEVEL_PROBES_DB:
            engine = engine_factory()
            signal = make_sine(fs, freq, level_db, 0.25)
            output = [engine.process(sample, sample)[0] for sample in signal]
            output_db = amp_to_db(project_tone_amplitude(output, fs, freq, start))
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
    t = engine.telemetry
    return {"peak_s4": t.peak_s4, "peak_s5": t.peak_s5, "peak_s6": t.peak_s6, "peak_pre_limiter": t.peak_pre_limiter, "max_output": t.max_output, "limiter_rate": t.limiter_hits / max(1, t.frames * 2)}


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
        self.lf_stage, self.hf_stage, self.body_stage = lf_stage, hf_stage, body_stage
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
        x = c["dc1"].process(x); x = c["em"].process(x); x = c["aa2"].process(c["aa1"].process(x))
        x *= gcomp; self.telemetry.peak_s4 = max(self.telemetry.peak_s4, abs(x))
        s = x * driveLin; v = math.tanh(s); x = (v + asym * v * v) * makeup
        self.telemetry.peak_s5 = max(self.telemetry.peak_s5, abs(x))
        x = c["dm"].process(x) if self.hf_stage is None else self.hf_stage.process_sample(ch, x)
        self.telemetry.peak_s6 = max(self.telemetry.peak_s6, abs(x))
        if ch == "L": self.mem[self.wp] = x; x = self.dl_L + XTK * self.dl_R
        else: self.mem[WF_SIZE + self.wp] = x; x = self.dl_R + XTK * self.dl_L
        x = c["de"].process(x); x = c["iec"].process(x); x = c["hb"].process(x); x = c["lt"].process(x); x = c["hf"].process(x)
        if self.body_stage is not None: x = self.body_stage.process_sample(ch, x)
        hn = nz - c["hp"].process(nz); hn = c["h1"].process(hn); hn = c["h2"].process(hn); x += hn * hissGain
        x *= trimLin; x = c["dc2"].process(x); self.telemetry.peak_pre_limiter = max(self.telemetry.peak_pre_limiter, abs(x))
        ax = abs(x)
        if ax > LIMIT_T:
            self.telemetry.limiter_hits += 1
            y = LIMIT_T + (1.0 - LIMIT_T) * math.tanh((ax - LIMIT_T) * LIMIT_K); x = y if x > 0.0 else -y
        return max(-CLAMP, min(CLAMP, x))


class PassthroughLF:
    def process_frame(self, left: float, right: float) -> tuple[float, float]: return left, right


class LiteralHighpassTight:
    def __init__(self, fs: float, highpass: float = 0.20, tight_param: float = 1.0):
        overallscale = fs / 44100.0
        self.iir_amount = (highpass ** 3) / overallscale
        tight = tight_param * 2.0 - 1.0
        self.iir_amount += self.iir_amount * tight * tight
        self.tight = tight / 1.5 if tight > 0.0 else tight / 3.0
        self.iir_amount = max(0.0, min(1.0, self.iir_amount)); self.flip = True
        self.a_l = self.b_l = self.a_r = self.b_r = 0.0

    def _one(self, sample: float, channel: str) -> float:
        offset = (1.0 - self.tight) + abs(sample) * self.tight if self.tight > 0.0 else (1.0 + self.tight) + (1.0 - abs(sample)) * self.tight
        offset = max(0.0, min(1.0, offset)); coeff = offset * self.iir_amount
        if channel == "L":
            if self.flip: self.a_l = self.a_l * (1.0 - coeff) + sample * coeff; return sample - self.a_l
            self.b_l = self.b_l * (1.0 - coeff) + sample * coeff; return sample - self.b_l
        if self.flip: self.a_r = self.a_r * (1.0 - coeff) + sample * coeff; return sample - self.a_r
        self.b_r = self.b_r * (1.0 - coeff) + sample * coeff; return sample - self.b_r

    def process_frame(self, left: float, right: float) -> tuple[float, float]:
        out_l, out_r = self._one(left, "L"), self._one(right, "R"); self.flip = not self.flip; return out_l, out_r


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
    def __init__(self, fs: float, config: FoundationGuardConfig, amount: float = 1.0):
        self.fs, self.config, self.amount = fs, config, amount
        self.det_a = 1.0 - math.exp(-2.0 * math.pi * config.detector_hz / fs)
        self.attack = math.exp(-1.0 / (config.attack_ms * 0.001 * fs)); self.release = math.exp(-1.0 / (config.release_ms * 0.001 * fs))
        self.det_l = self.det_r = self.hp_l = self.hp_r = self.env = 0.0
        self.last_env_l = self.last_env_r = 0.0; self.last_hp_hz = config.min_hp_hz

    def process_frame(self, left: float, right: float) -> tuple[float, float]:
        if self.amount <= 0.0: return left, right
        self.det_l += self.det_a * (left - self.det_l); self.det_r += self.det_a * (right - self.det_r)
        target = max(abs(self.det_l), abs(self.det_r)); coeff = self.attack if target >= self.env else self.release
        self.env = coeff * self.env + (1.0 - coeff) * target; self.last_env_l = self.last_env_r = self.env
        span = max(1e-12, self.config.env_ceil - self.config.env_floor); u = max(0.0, min(1.0, (self.env - self.config.env_floor) / span)); u *= u
        cutoff = self.config.min_hp_hz + self.amount * u * (self.config.max_hp_hz - self.config.min_hp_hz); cutoff = max(self.config.min_hp_hz, min(self.config.max_hp_hz, cutoff)); self.last_hp_hz = cutoff
        hp_a = 1.0 - math.exp(-2.0 * math.pi * cutoff / self.fs); self.hp_l += hp_a * (left - self.hp_l); self.hp_r += hp_a * (right - self.hp_r)
        return left - self.hp_l, right - self.hp_r


@dataclass(frozen=True)
class StoneGuardConfig:
    split_hz: float
    threshold: float
    max_gr_db: float
    attack_ms: float = STONE_ATTACK_MS
    release_ms: float = STONE_RELEASE_MS


class StoneGuard:
    def __init__(self, fs: float, config: StoneGuardConfig, amount: float = 1.0):
        self.fs, self.config, self.amount = fs, config, amount
        self.split_a = 1.0 - math.exp(-2.0 * math.pi * config.split_hz / fs)
        self.attack = math.exp(-1.0 / (config.attack_ms * 0.001 * fs)); self.release = math.exp(-1.0 / (config.release_ms * 0.001 * fs))
        self.stone_l = self.stone_r = self.env = self.last_gr_db = 0.0

    def process_frame(self, left: float, right: float) -> tuple[float, float]:
        if self.amount <= 0.0: return left, right
        self.stone_l += self.split_a * (left - self.stone_l); self.stone_r += self.split_a * (right - self.stone_r)
        remainder_l, remainder_r = left - self.stone_l, right - self.stone_r
        target = max(abs(self.stone_l), abs(self.stone_r)); coeff = self.attack if target >= self.env else self.release; self.env = coeff * self.env + (1.0 - coeff) * target
        over = max(0.0, self.env - self.config.threshold) / max(1e-12, 1.0 - self.config.threshold); gr_db = min(self.config.max_gr_db, self.amount * self.config.max_gr_db * over * over); self.last_gr_db = gr_db
        gain = db_to_amp(-gr_db); return remainder_l + self.stone_l * gain, remainder_r + self.stone_r * gain


def _process_lf_mono(stage, signal: list[float]) -> list[float]:
    return [stage.process_frame(sample, sample)[0] for sample in signal]


def measure_thd(stage_factory, fs: float, freq: float = 60.0, level_db: float = -6.0) -> float:
    signal = make_sine(fs, freq, level_db, 2.0); output = _process_lf_mono(stage_factory(), signal); start = int(0.5 * fs)
    fundamental = project_tone_amplitude(output, fs, freq, start)
    harmonics = [project_tone_amplitude(output, fs, freq * h, start) for h in range(2, 9) if freq * h < fs * 0.5]
    ratio = math.sqrt(sum(value * value for value in harmonics)) / max(1e-300, fundamental)
    return amp_to_db(ratio)


def measure_dynamic_imd(stage_factory, fs: float) -> dict[str, float]:
    signal = make_two_tone(fs, 60.0, -6.0, 1000.0, -18.0, 2.0); output = _process_lf_mono(stage_factory(), signal); start = int(0.5 * fs)
    carrier = project_tone_amplitude(output, fs, 1000.0, start)
    lower = project_tone_amplitude(output, fs, 940.0, start); upper = project_tone_amplitude(output, fs, 1060.0, start)
    return {"lower_db": amp_to_db(lower / max(carrier, 1e-300)), "upper_db": amp_to_db(upper / max(carrier, 1e-300))}


def measure_lf_headroom(stage_factory, fs: float) -> list[dict[str, float]]:
    rows = []
    for level_db in (-12.0, -6.0, -3.0, 0.0):
        engine = DragonExperimentEngine(fs, lf_stage=stage_factory(), wf=0.0, hiss=-200.0, instrument=True)
        for sample in make_sine(fs, 60.0, level_db, 0.5): engine.process(sample, sample)
        t = engine.telemetry
        rows.append({"input_db": level_db, "peak_s4": t.peak_s4, "peak_s5": t.peak_s5, "peak_s6": t.peak_s6, "peak_pre_limiter": t.peak_pre_limiter, "limiter_rate": t.limiter_hits / max(1, t.frames * 2)})
    return rows


def measure_stereo_integrity(stage_factory, fs: float) -> dict[str, float]:
    seconds = 0.5; start = int(0.1 * fs)
    l60 = make_sine(fs, 60.0, -3.0, seconds); l1k = make_sine(fs, 1000.0, -18.0, seconds)
    r60 = make_sine(fs, 60.0, -18.0, seconds); r1k = make_sine(fs, 1000.0, -18.0, seconds, phase=0.11)
    engine = DragonExperimentEngine(fs, lf_stage=stage_factory(), wf=0.0, hiss=-200.0, instrument=True); out_l, out_r = [], []
    for a, b, c, d in zip(l60, l1k, r60, r1k):
        left, right = engine.process(a + b, c + d); out_l.append(left); out_r.append(right)
    left_db = amp_to_db(project_tone_amplitude(out_l, fs, 1000.0, start)); right_db = amp_to_db(project_tone_amplitude(out_r, fs, 1000.0, start))
    return {"left_1k_db": left_db, "right_1k_db": right_db, "mismatch_db": abs(left_db - right_db)}


LF_CANDIDATES = {
    "none": lambda fs, **params: None,
    "lf-highpass-literal": lambda fs, **params: LiteralHighpassTight(fs, **params),
    "lf-foundation": lambda fs, **params: FoundationGuard(fs, FoundationGuardConfig(**params)),
    "lf-stone-light": lambda fs, **params: StoneGuard(fs, StoneGuardConfig(**params)),
}


def _stage_factory(key: str, fs: float, params: dict):
    def build():
        stage = LF_CANDIDATES[key](fs, **params)
        return PassthroughLF() if stage is None else stage
    return build


def iter_lf_configs():
    yield "none", {}
    yield "lf-highpass-literal", {"highpass": 0.20, "tight_param": 1.0}
    for detector_hz, attack_ms, release_ms, max_hp_hz in itertools.product(FOUNDATION_DETECTOR_HZ, FOUNDATION_ATTACK_MS, FOUNDATION_RELEASE_MS, FOUNDATION_MAX_HP_HZ):
        yield "lf-foundation", {"detector_hz": detector_hz, "attack_ms": attack_ms, "release_ms": release_ms, "max_hp_hz": max_hp_hz}
    for split_hz, threshold, max_gr_db in itertools.product(STONE_SPLIT_HZ, STONE_THRESHOLD, STONE_MAX_GR_DB):
        yield "lf-stone-light", {"split_hz": split_hz, "threshold": threshold, "max_gr_db": max_gr_db}


def build_lf_report() -> dict:
    report = {"sample_rates": {}}
    for fs in (44100.0, 48000.0):
        rows = []
        for key, params in iter_lf_configs():
            factory = _stage_factory(key, fs, params)
            thd_db = measure_thd(factory, fs); imd = measure_dynamic_imd(factory, fs); headroom = measure_lf_headroom(factory, fs); stereo = measure_stereo_integrity(factory, fs)
            lf_stage = None if key == "none" else LF_CANDIDATES[key](fs, **params)
            grid = measure_lf_level_grid(lambda fs=fs, lf_stage=lf_stage: DragonExperimentEngine(fs, lf_stage=lf_stage, wf=0.0, hiss=-200.0, instrument=True), fs)
            hot = headroom[-1]; cost = LF_COSTS[key]
            rows.append({"key": key, "params": params, "thd_db": thd_db, "imd": imd, "imd_worst_db": max(imd.values()), "headroom": headroom, "peak_pre_limiter": hot["peak_pre_limiter"], "limiter_rate": hot["limiter_rate"], "stereo": stereo, "lf_grid": grid, **cost})
        for row in rows:
            row["non_dominated"] = not any(_lf_dominates(other, row) for other in rows if other is not row)
        report["sample_rates"][str(int(fs))] = rows
    return report


def _lf_dominates(a: dict, b: dict) -> bool:
    objectives_a = (a["peak_pre_limiter"], a["thd_db"], a["imd_worst_db"], a["limiter_rate"], a["ops_estimate"])
    objectives_b = (b["peak_pre_limiter"], b["thd_db"], b["imd_worst_db"], b["limiter_rate"], b["ops_estimate"])
    return all(x <= y + 1e-12 for x, y in zip(objectives_a, objectives_b)) and any(x < y - 1e-12 for x, y in zip(objectives_a, objectives_b))
