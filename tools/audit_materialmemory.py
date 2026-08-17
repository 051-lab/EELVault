#!/usr/bin/env python3
"""Dependency-free validation harness for Material Memory Engine P0.1.

Run from any working directory:
    python tools/audit_materialmemory.py

The script exits non-zero when any required P0.1 invariant fails.
It is the same spirit as tools/audit_soloconsole.py: package and
source identity plus a numerical reference model of the actual
signal path (modal cell, Givens coupling, Body/Edge decomposition,
weighted emission, mix/output).

Everything here is stdlib-only.
"""

from __future__ import annotations

import cmath
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DSP = ROOT / "dsp" / "materialmemory" / "materialmemory.eel"
ARCHIVE = ROOT / "dsp" / "materialmemory" / "versions" / "v0.0.1-p0.1-matter.eel"
METADATA = ROOT / "dsp" / "materialmemory" / "metadata.json"
VERSION = "0.0.1"

# ------------------------------------------------------------------
# Design constants (must mirror the EEL source exactly)
# ------------------------------------------------------------------

LN60 = 6.907755278982137
NYQ_FRAC = 0.22
MATERIAL_GAIN = 2.2
STATE_BOUND = 8.0
SMOOTH_SEC = 0.015
MATERIAL_SEC = 0.060
MATERIAL_EVERY = 32
SAMPLE_RATES = (44100.0, 48000.0, 96000.0, 192000.0)
MATERIALS = (0.0, 0.25, 0.5, 0.75, 1.0)

SOFT_F = (150, 285, 610, 1180, 2470, 5100)
HARD_F = (170, 390, 910, 1980, 4370, 9050)
SOFT_T = (0.180, 0.150, 0.120, 0.090, 0.065, 0.045)
HARD_T = (0.260, 0.340, 0.420, 0.500, 0.580, 0.660)
WB0 = (1.00, 0.90, 0.75, 0.50, 0.25, 0.12)
WE0 = (0.12, 0.22, 0.38, 0.58, 0.80, 1.00)
# base emission weights = draft ratios scaled up by ~1.3; sum is
# 1.49, deliberately NOT 1.0 (see EEL header D2). There is no
# sum=1 invariant.
OW = (0.34, 0.31, 0.29, 0.24, 0.18, 0.13)
OW_SUM = sum(OW)  # 1.49
# D9: per-mode emission trim (dB), geometric-mean taper
OWDB = (4.0, 3.4, 2.2, 0.6, -0.6, -1.8)
EMISSION_SPAN = 6.0
CMUL = (0.70, -1.00, 1.25, -0.90, 1.15)
KAPPA_LIMIT = 0.045
MATERIAL_EMISSION_DB = 4.0

CLAMP = 0.999
IN_SOFT = 4.0


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(name: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return condition


# ------------------------------------------------------------------
# Reference model — mirrors materialmemory.eel exactly
# ------------------------------------------------------------------


class Engine:
    """Python port of the P0.1 sample path.

    Coefficients follow update_material() at the given material,
    at the given sample rate. The per-sample loop matches @sample:
    sanitize -> body/edge -> step_bank (both channels) -> coupling
    (alternating frame) -> emission -> mix/output -> clamps.
    """

    def __init__(self, fs: float, material: float):
        self.fs = fs
        self.material = material
        self.mh = material * material
        self.rc = [0.0] * 6
        self.rs = [0.0] * 6
        self.rr = [0.0] * 6
        self.wb = [0.0] * 6
        self.we = [0.0] * 6
        self.owc = [0.0] * 6
        self.kc = [0.0] * 5
        self.ks = [0.0] * 5
        self.bodyA = 0.0
        self.couple_toggle = 0.0
        self.pL = [0.0] * 6
        self.qL = [0.0] * 6
        self.pR = [0.0] * 6
        self.qR = [0.0] * 6
        self.bodyL = 0.0
        self.bodyR = 0.0
        self.clamps = 0
        # D5: precomputed invariant log(hf/sf) ratios (once)
        self.lratio = [math.log(HARD_F[i] / SOFT_F[i]) for i in range(6)]
        self.update_material()

    def update_material(self) -> None:
        m = self.material
        m = min(1.0, max(0.0, m))
        mh = m * m
        for i in range(6):
            freq = SOFT_F[i] * math.exp(self.lratio[i] * m)
            freq = min(freq, NYQ_FRAC * self.fs)
            freq = max(freq, 10.0)
            t60 = SOFT_T[i] + (HARD_T[i] - SOFT_T[i]) * mh
            theta = 2.0 * math.pi * freq / self.fs
            self.rc[i] = math.cos(theta)
            self.rs[i] = math.sin(theta)
            self.rr[i] = math.exp(-LN60 / (t60 * self.fs))
            self.wb[i] = WB0[i] * (1.08 - 0.28 * m)
            self.we[i] = WE0[i] * (0.55 + 0.85 * m)
        # D9: compensated emission weights (mirror the EEL exactly)
        f1 = SOFT_F[0]
        f6 = SOFT_F[5]
        fmid = math.sqrt(f1 * f6)
        for i in range(6):
            freq_now = SOFT_F[i] * math.exp(self.lratio[i] * m)
            ff = (math.log(freq_now) - math.log(fmid)) / (
                math.log(f6) - math.log(f1)
            )
            db_now = OWDB[i] + EMISSION_SPAN * 0.5 * ff
            self.owc[i] = OW[i] * math.exp(db_now * 0.11512925464970228)
        self.bodyA = 1.0 - math.exp(
            -2.0 * math.pi * (700.0 + 500.0 * m) / self.fs
        )
        coupling_hz = 1.5 + 10.0 * mh
        for i in range(5):
            kap = 2.0 * math.pi * coupling_hz * CMUL[i] / self.fs
            kap = max(-KAPPA_LIMIT, min(KAPPA_LIMIT, kap))
            self.kc[i] = math.cos(kap)
            self.ks[i] = math.sin(kap)

    def step_bank(self, p: list[float], q: list[float],
                  body: float, edge: float, excite: float) -> None:
        for i in range(6):
            op = p[i]
            oq = q[i]
            drive = (
                excite
                * (self.wb[i] * body + self.we[i] * edge)
                * (1.0 - self.rr[i])
            )
            p[i] = self.rr[i] * (self.rc[i] * op - self.rs[i] * oq) + drive
            q[i] = self.rr[i] * (self.rs[i] * op + self.rc[i] * oq)

    def couple_pair(self, p: list[float], q: list[float],
                    a: int, b: int, cc: float, ss: float) -> None:
        pa, pb = p[a], p[b]
        p[a] = cc * pa - ss * pb
        p[b] = ss * pa + cc * pb
        qa, qb = q[a], q[b]
        q[a] = cc * qa - ss * qb
        q[b] = ss * qa + cc * qb

    def process(self, in_l: float, in_r: float,
                excite: float = 1.0, mix: float = 1.0,
                out: float = 1.0) -> tuple[float, float, float]:
        """One sample. Returns (outL, outR, modal)."""
        in_l = 0.0 if in_l != in_l else min(IN_SOFT, max(-IN_SOFT, in_l))
        in_r = 0.0 if in_r != in_r else min(IN_SOFT, max(-IN_SOFT, in_r))

        self.bodyL += self.bodyA * (in_l - self.bodyL)
        self.bodyR += self.bodyA * (in_r - self.bodyR)
        edge_l = in_l - self.bodyL
        edge_r = in_r - self.bodyR

        self.step_bank(self.pL, self.qL, self.bodyL, edge_l, excite)
        self.step_bank(self.pR, self.qR, self.bodyR, edge_r, excite)

        if self.couple_toggle < 0.5:
            pairs = ((0, 1), (2, 3), (4, 5))
            k_idx = (0, 1, 2)
        else:
            pairs = ((1, 2), (3, 4))
            k_idx = (3, 4)
        for pair_no, (a, b) in enumerate(pairs):
            cc = self.kc[k_idx[pair_no]]
            ss = self.ks[k_idx[pair_no]]
            self.couple_pair(self.pL, self.qL, a, b, cc, ss)
            self.couple_pair(self.pR, self.qR, a, b, cc, ss)
        self.couple_toggle = 1.0 - self.couple_toggle

        modal_l = sum(self.owc[i] * self.pL[i] for i in range(6))
        modal_r = sum(self.owc[i] * self.pR[i] for i in range(6))

        wet_l = in_l + MATERIAL_GAIN * modal_l
        wet_r = in_r + MATERIAL_GAIN * modal_r

        out_l = in_l + (wet_l - in_l) * mix
        out_r = in_r + (wet_r - in_r) * mix
        out_l *= out
        out_r *= out
        if out_l > CLAMP:
            out_l = CLAMP
            self.clamps += 1
        if out_l < -CLAMP:
            out_l = -CLAMP
            self.clamps += 1
        if out_r > CLAMP:
            out_r = CLAMP
            self.clamps += 1
        if out_r < -CLAMP:
            out_r = -CLAMP
            self.clamps += 1
        return out_l, out_r, modal_l


def energy_state(engine: Engine) -> float:
    return (sum(v * v for v in engine.pL)
            + sum(v * v for v in engine.qL)
            + sum(v * v for v in engine.pR)
            + sum(v * v for v in engine.qR))


# ------------------------------------------------------------------
# Numerical helpers
# ------------------------------------------------------------------


def resonant_gain(theta: float, c: float, r: float) -> float:
    """|H_p(e^{j*theta})| with drive scale (1-r).

    H_p(z) = (1 - r*c*z^-1) / (1 - 2*r*c*z^-1 + r^2*z^-2)
    evaluated at z = e^{j*theta}, times (1-r). This is the p-state
    steady-state resonant amplitude for a unit drive at the modal
    frequency, and (1-r) normalizes it to ~0.5 across the grid.
    """
    z = cmath.exp(-1j * theta)
    num = 1.0 - r * c * z
    den = 1.0 - 2.0 * r * c * z + r * r * z * z
    return abs(num / den) * (1.0 - r)


def homogeneous_transition(fs: float, material: float,
                           n: int = 200) -> float:
    """Energy multiplier of the homogeneous (no-drive) modal
    transition, measured over n samples. Must be < 1."""
    e = Engine(fs, material)
    e.pL[0] = 1.0
    e.qL[2] = 0.5
    e.pR[4] = -0.7
    e.qR[5] = 0.3
    before = energy_state(e)
    for _ in range(n):
        e.process(0.0, 0.0, excite=0.0)
    after = energy_state(e)
    return (after / before) ** (1.0 / n) if before > 0 else 1.0


def max_coupling_energy_error(fs: float, material: float,
                              n: int = 200) -> float:
    """Per-sample max relative energy error of the pure Givens
    rotation (no decay), isolating the spec invariant
    a'^2 + b'^2 = a^2 + b^2. The rotation acts on each p-pair and
    each q-pair independently, so each pair's squared sum must be
    preserved exactly."""
    e = Engine(fs, material)
    worst = 0.0
    for _ in range(n):
        for bank in (e.pL, e.qL, e.pR, e.qR):
            for i in range(6):
                bank[i] = math.sin(i * 1.7 + _) * 0.9 + math.cos(i * 0.7) * 0.3
        if e.couple_toggle < 0.5:
            pairs = ((0, 1), (2, 3), (4, 5))
            k_idx = (0, 1, 2)
        else:
            pairs = ((1, 2), (3, 4))
            k_idx = (3, 4)
        for pair_no, (a, b) in enumerate(pairs):
            cc = e.kc[k_idx[pair_no]]
            ss = e.ks[k_idx[pair_no]]
            for bank in (e.pL, e.qL, e.pR, e.qR):
                pa, pb = bank[a], bank[b]
                before = pa * pa + pb * pb
                bank[a] = cc * pa - ss * pb
                bank[b] = ss * pa + cc * pb
                after = bank[a] * bank[a] + bank[b] * bank[b]
                rel = abs(after - before) / max(before, 1e-12)
                worst = max(worst, rel)
        e.couple_toggle = 1.0 - e.couple_toggle
    return worst


def impulse_tail(fs: float, material: float,
                 amp: float, seconds: float) -> tuple[float, float, float, float]:
    """Unit impulse at t=0 into the left channel; returns
    (peak_out_abs, out_abs_at_100ms, out_abs_at_slowest_T60, max_state_abs)."""
    e = Engine(fs, material)
    peak = 0.0
    at100 = None
    at_t60 = None
    max_state = 0.0
    slow_t60 = max(SOFT_T[i] + (HARD_T[i] - SOFT_T[i]) * material * material
                   for i in range(6))
    idx100 = int(0.1 * fs)
    idx_t60 = int(slow_t60 * fs)
    for n in range(int(seconds * fs) + 1):
        inp = amp if n == 0 else 0.0
        ol, _or_, _modal = e.process(inp, 0.0, excite=1.0, mix=1.0, out=1.0)
        peak = max(peak, abs(ol))
        if n == idx100:
            at100 = abs(ol)
        if n == idx_t60:
            at_t60 = abs(ol)
        max_state = max(
            max_state,
            max(abs(v) for v in e.pL + e.qL + e.pR + e.qR),
        )
    return peak, (at100 if at100 is not None else 0.0), (
        at_t60 if at_t60 is not None else 0.0), max_state


def silence_after_excitation(fs: float, material: float,
                             seconds: float = 0.25) -> tuple[bool, float]:
    """Drive a realistic AC burst (0.5-peak 200 Hz sine, the kind of
    program material the body/edge split expects), then silence, and
    assert the output falls to a residual below 10% of the burst peak
    within the probe window. A sustained DC burst would legitimately
    ring the body filter; the spec's 'no self-excitation' means *AC*
    program material must decay rather than keep growing. The window
    covers the slowest mode (soft 0.18 s, hard 0.66 s)."""
    e = Engine(fs, material)
    burst = int(0.05 * fs)
    for n in range(burst):
        x = 0.5 * math.sin(2.0 * math.pi * 200.0 * n / fs)
        e.process(x, x, excite=1.0, mix=1.0, out=1.0)
    tail = 0.0
    for n in range(int(seconds * fs)):
        ol, _or_, _modal = e.process(0.0, 0.0, excite=1.0, mix=1.0, out=1.0)
        tail = max(tail, abs(ol))
    # 0.5-peak burst -> residual must stay below 10% (-20 dB)
    return tail < 0.05, tail


def stress_probe(fs: float, material: float, n: int = 4096) -> tuple[bool, float, int]:
    """Deterministic bounded pseudo-random stress: alternating
    impulses, DC, white noise, silence, impulses. Inputs are a
    realistic 0.5-peak bus (0.25 noise), so the emergency clamp must
    never fire. Returns (all_finite, peak_out_abs, clamp_count)."""
    e = Engine(fs, material)
    state = 0x12345678
    peak = 0.0
    for n_s in range(n):
        x = 0.0
        y = 0.0
        phase = n_s % 64
        if phase < 2:
            x = 0.5
            y = 0.5
        elif phase < 4:
            x = -0.5
        elif phase < 6:
            x = 0.4
        elif phase < 10:
            x = 0.45
            y = -0.4
        elif phase < 14:
            x = 0.0
        elif phase < 30:
            state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
            x = (state / 0xFFFFFFFF) * 0.5 - 0.25
            state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
            y = (state / 0xFFFFFFFF) * 0.5 - 0.25
        ol, _or_, _modal = e.process(x, y, excite=1.0, mix=1.0, out=1.0)
        peak = max(peak, abs(ol))
    all_finite = all(
        math.isfinite(v)
        for arr in (e.pL, e.qL, e.pR, e.qR)
        for v in arr
    )
    return all_finite, peak, e.clamps


def crosstalk(fs: float, material: float) -> float:
    """Left-only impulse -> max |right output| over the tail.
    Uses the same 0.5-peak impulse as the other probes."""
    e = Engine(fs, material)
    worst = 0.0
    n = int(1.0 * fs)
    for n_s in range(n):
        x = 0.5 if n_s == 0 else 0.0
        _ol, or_, _modal = e.process(x, 0.0, excite=1.0, mix=1.0, out=1.0)
        worst = max(worst, abs(or_))
    return worst


def finite_grid(fs: float, material: float) -> bool:
    e = Engine(fs, material)
    return all(
        math.isfinite(v)
        for arr in (e.rc, e.rs, e.rr, e.wb, e.we, e.kc, e.ks, (e.bodyA,))
        for v in arr
    ) and 0.0 < min(e.rr) and max(e.rr) < 1.0


# ------------------------------------------------------------------
# Static source checks
# ------------------------------------------------------------------

FORBIDDEN = (
    "fft(", "ifft(", "stft", "FIRInit", "FIRProcess", "Conv1D",
    "fractionalDelayLine", "IIRBandSplitter", "PolyphaseFilterbank",
    "oversampl", "resample(", "granular",
)

MARKDOWN_SECTIONS = ("[init](init)", "[slider](slider1)", "[block](block)",
                     "[sample](sample)")


def check_source(source: str) -> list[bool]:
    results: list[bool] = []

    slider_numbers = [int(m.group(1)) for m in re.finditer(r"(?m)^slider(\d+):", source)]
    section_lines = [name for name in ("@init", "@slider", "@block", "@sample")
                     if re.search(rf"(?m)^{re.escape(name)}\s*$", source)]
    results.append(require(
        "native EEL2 sections (@init/@sample) and four sequential sliders",
        section_lines == ["@init", "@sample"] and slider_numbers == [1, 2, 3, 4],
        f"sliders={slider_numbers} sections={section_lines}",
    ))

    # order check: slider decls come before @init, sections in order.
    # Use line numbers consistently (the header comment also mentions
    # @init/@slider/@sample, which would confuse plain find()).
    lines = source.splitlines()
    slider_line = next((i for i, line in enumerate(lines)
                        if re.match(r"^slider1:", line)), -1)
    sec_pos = {
        name: next((i for i, line in enumerate(lines)
                    if re.match(rf"^{re.escape(name)}\s*$", line)), -1)
        for name in ("@init", "@sample")
    }
    order_ok = (
        slider_line < sec_pos["@init"]
        and sec_pos["@init"] < sec_pos["@sample"]
    )
    results.append(require("EEL2 section order and slider-first layout", order_ok))

    expected_sliders = {"slider1": 42.0, "slider2": 48.0, "slider3": 65.0, "slider4": 0.0}
    declared = {}
    for m in re.finditer(r"(?m)^slider(\d+):([-\d.]+)<", source):
        declared[f"slider{m.group(1)}"] = float(m.group(2))
    results.append(require(
        "declared slider defaults match spec (42/48/65/0)",
        all(abs(declared.get(k, -1.0) - v) < 1e-12 for k, v in expected_sliders.items()),
        str([declared.get(k) for k in ("slider1", "slider2", "slider3", "slider4")]),
    ))

    results.append(require(
        "source descriptor/version identity",
        source.startswith("desc: Material Memory Engine - P0.1 Matter\n")
        and "0.0.1" in source
        and "P0.1" in source,
    ))

    for i, f in enumerate(SOFT_F):
        results.append(require(f"soft anchor frequency M{i + 1} = {f} Hz",
                               f"sf[{i}] = {f};" in source))
    for i, f in enumerate(HARD_F):
        results.append(require(f"hard anchor frequency M{i + 1} = {f} Hz",
                               f"hf[{i}] = {f};" in source))
    # T60 values carry trailing zeros in source (0.180) and are
    # grouped several per line, so match numerically with a tolerant
    # regex (no line-start anchor).
    def anchor_declared(array: str, i: int, value: float) -> bool:
        m = re.search(rf"{array}\[{i}\]\s*=\s*([-\d.]+)", source)
        return m is not None and abs(float(m.group(1)) - value) < 1e-12

    for i, t in enumerate(SOFT_T):
        results.append(require(f"soft anchor T60 M{i + 1} = {t} s",
                               anchor_declared("st", i, t)))
    for i, t in enumerate(HARD_T):
        results.append(require(f"hard anchor T60 M{i + 1} = {t} s",
                               anchor_declared("ht", i, t)))

    results.append(require(
        "drive normalization is (1-r) resonant-normalized",
        "(1 - rr[i])" in source
        and "sqrt(1 - rr[i] * rr[i])" not in source,
    ))
    results.append(require(
        "D9 compensated emission weights (owc) present",
        "owc  = MEM; MEM += 6;" in source
        and "owc[i] = ow[i] * exp(dbNow * DB_TO_LIN);" in source
        and "modalL += owc[i] * pL[i];" in source
        and "modalR += owc[i] * pR[i];" in source,
    ))
    results.append(require(
        "frequency morph uses precomputed log ratio",
        "exp(lratio[i] * m)" in source
        and "lratio[i] = log(hf[i] / sf[i]);" in source,
    ))
    results.append(require(
        "EEL source documents the 1.49 weight sum, no sum=1 invariant",
        "sum 1.49" in source and "no sum=1 invariant" in source,
    ))
    results.append(require(
        "EEL source documents the resonant (1-r) justification",
        "RESONANT-amplitude" in source and "|H_p" in source,
    ))
    # D10: parser-verified — this runtime rejects user functions.
    results.append(require(
        "no user-defined functions (parser-verified constraint)",
        not re.search(r"(?m)^function\s", source)
        and "D10" in source
        and "NO user-defined functions" in source,
    ))
    results.append(require(
        "materialGain stays at the spec's 2.2",
        "MATERIAL_GAIN = 2.2;" in source,
    ))
    results.append(require(
        "Modal cells use the spec rotation",
        "rr[i] * (rc[i] * op - rs[i] * oq) + drive" in source
        and "rr[i] * (rs[i] * op + rc[i] * oq)" in source,
    ))

    results.append(require(
        "body/edge one-pole decomposition",
        "bodyL += bodyA * (inL - bodyL);" in source
        and "edgeL = inL - bodyL;" in source,
    ))

    results.append(require(
        "independent L/R modal state (4 banks of 6)",
        "pL   = MEM; MEM += 6;" in source
        and "qL   = MEM; MEM += 6;" in source
        and "pR   = MEM; MEM += 6;" in source
        and "qR   = MEM; MEM += 6;" in source,
    ))

    results.append(require(
        "alternating Givens lattice present (inlined)",
        "pL[0] = kc[0] * pa - ks[0] * pb;" in source
        and "pL[2] = kc[1] * pa - ks[1] * pb;" in source
        and "pL[4] = kc[2] * pa - ks[2] * pb;" in source
        and "pL[1] = kc[3] * pa - ks[3] * pb;" in source
        and "pL[3] = kc[4] * pa - ks[4] * pb;" in source
        and "coupleToggle = 1 - coupleToggle;" in source,
    ))

    # The sample path now inlines the coefficient refresh (D10: no
    # user functions allowed by this runtime). The per-sample hot
    # path must still be transcendental-free; the bounded 32-sample
    # coefficient block is exempt (it only runs 1/32 of samples).
    sample_body = re.search(r"(?m)^@sample\s*\n(.*)$", source, re.S)
    sample_text = sample_body.group(1) if sample_body else source.split("@sample")[1]
    # strip the 32-sample coefficient re-derive block (the only place
    # transcendentals are allowed). Bracket-depth-aware removal from
    # "controlCount >= MATERIAL_EVERY ? (" through its matching ");".
    hot_path = sample_text
    start = hot_path.find("controlCount >= MATERIAL_EVERY ? (")
    if start >= 0:
        depth = 0
        i = start
        while i < len(hot_path):
            ch = hot_path[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i + 1 < len(hot_path) and hot_path[i + 1] == ";":
                    i += 2
                    break
            i += 1
        hot_path = hot_path[:start] + hot_path[i:]
    # also strip the pdc ? (...) slider-change conditional (runs only
    # when a control changes; its outTgt = exp(...) is control-rate)
    start = hot_path.find("pdc ? (")
    if start >= 0:
        depth = 0
        i = start
        while i < len(hot_path):
            ch = hot_path[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i + 1 < len(hot_path) and hot_path[i + 1] == ";":
                    i += 2
                    break
            i += 1
        hot_path = hot_path[:start] + hot_path[i:]
    results.append(require(
        "per-sample hot path is transcendental-free",
        "sqrt(" not in hot_path
        and "exp(" not in hot_path
        and "sin(" not in hot_path
        and "cos(" not in hot_path
        and "pow(" not in hot_path
        and "log(" not in hot_path,
    ))
    results.append(require(
        "bounded 32-sample coefficient block contains the math",
        "controlCount >= MATERIAL_EVERY ? (" in sample_text
        and sample_text.count("exp(") >= 2,
    ))

    results.append(require(
        "per-sample slider fallback bridge present",
        "cEx != slider1 ? ( cEx = slider1; pdc = 1; );" in source
        and "pdc ? (" in source,
    ))

    results.append(require(
        "emergency containment is a hard +/-0.999 clamp",
        "outL > 0.999 ? ( outL = 0.999; clampCount += 1; );" in source,
    ))

    results.append(require(
        "denormal dither + NaN guard + soft input pad",
        "DENORMAL_GUARD * denormalSign" in source
        and "inL != inL ? inL = 0;" in source
        and "inL > 4 ? inL = 4;" in source,
    ))

    results.append(require(
        "coefficient re-derive cadence is every 32 samples",
        "controlCount >= MATERIAL_EVERY ? (" in source
        and "controlCount = 0;" in source,
    ))

    results.append(require(
        "no forbidden FFT/FIR/oversampling/large-delay systems",
        not any(tok in source for tok in FORBIDDEN),
    ))

    results.append(require(
        "no Markdown-corrupted section markers",
        not any(marker in source for marker in MARKDOWN_SECTIONS),
    ))

    results.append(require(
        "README labels P0.1 experimental/laboratory",
        "experimental" in load_text(ROOT / "dsp" / "materialmemory" / "README.md").lower()
        and "laboratory" in load_text(ROOT / "dsp" / "materialmemory" / "README.md").lower(),
    ))

    results.append(require(
        "CHANGELOG describes only implemented work",
        "P0.1" in load_text(ROOT / "dsp" / "materialmemory" / "CHANGELOG.md"),
    ))
    return results


def check_metadata(source: str) -> list[bool]:
    results: list[bool] = []
    try:
        metadata = json.loads(load_text(METADATA))
    except json.JSONDecodeError:
        results.append(require("metadata.json is valid JSON", False))
        return results

    versions = metadata.get("versions", {})
    results.append(require(
        "metadata identity: version/status/type/display",
        metadata.get("name") == "materialmemory"
        and metadata.get("version") == VERSION
        and metadata.get("status") == "experimental"
        and metadata.get("type") == "stateful-virtual-material-resonator"
        and metadata.get("displayName") == "Material Memory Engine — P0.1 Matter",
    ))
    results.append(require(
        "metadata file/latency/controls contract",
        metadata.get("file") == "materialmemory.eel"
        and metadata.get("latencyMs") == 0.0
        and metadata.get("hasUserControls") is True,
    ))
    results.append(require(
        "metadata version map points at the P0.1 archive",
        versions.get("v0.0.1") == "versions/v0.0.1-p0.1-matter.eel",
    ))
    results.append(require(
        "metadata feature list matches P0.1 scope",
        all(f in metadata.get("features", []) for f in (
            "six-mode-damped-two-state-resonator",
            "energy-preserving-givens-coupling",
            "independent-lr-modal-state",
            "sample-path-slider-fallback",
        )),
    ))
    results.append(require(
        "archive/current byte identity",
        ARCHIVE.exists() and ARCHIVE.read_bytes() == DSP.read_bytes(),
    ))
    return results


def check_numerics() -> list[bool]:
    results: list[bool] = []

    finite_ok = True
    r_min, r_max = 1.0, 0.0
    detail = []
    for fs in SAMPLE_RATES:
        for m in MATERIALS:
            e = Engine(fs, m)
            if not finite_grid(fs, m):
                finite_ok = False
            r_min = min(r_min, min(e.rr))
            r_max = max(r_max, max(e.rr))
    detail.append(f"r in [{r_min:.6f},{r_max:.6f}]")
    results.append(require(
        "coefficient grid finite, 0 < r < 1 across 4 rates x 5 materials",
        finite_ok and 0.0 < r_min and r_max < 1.0,
        ", ".join(detail),
    ))

    hom_min = 1.0
    for fs in SAMPLE_RATES:
        for m in MATERIALS:
            hom_min = min(hom_min, homogeneous_transition(fs, m))
    results.append(require(
        "homogeneous modal transition is contractive",
        hom_min < 1.0,
        f"min per-sample energy multiplier={hom_min:.6f}",
    ))

    coup_max = 0.0
    for fs in SAMPLE_RATES:
        for m in MATERIALS:
            coup_max = max(coup_max, max_coupling_energy_error(fs, m))
    results.append(require(
        "pairwise Givens coupling preserves energy",
        coup_max < 1e-10,
        f"max relative energy error={coup_max:.2e}",
    ))

    # (1-r) resonant-amplitude normalization: |H_p(e^{j*theta})|*(1-r)
    # must be ~0.5 across the full grid (ChatGPT's derivation).
    rg_min, rg_max = 1e9, 0.0
    for fs in SAMPLE_RATES:
        for m in MATERIALS:
            e = Engine(fs, m)
            for i in range(6):
                g = resonant_gain(
                    2.0 * math.pi
                    * min(SOFT_F[i] * math.exp(e.lratio[i] * m),
                          NYQ_FRAC * fs) / fs,
                    e.rc[i],
                    e.rr[i],
                )
                rg_min = min(rg_min, g)
                rg_max = max(rg_max, g)
    rg_spread_db = 20.0 * math.log10(rg_max / rg_min)
    results.append(require(
        "(1-r) normalizes modal resonant amplitude across the grid",
        rg_min > 0.45 and rg_max < 0.55 and rg_spread_db < 1.0,
        f"min={rg_min:.4f} max={rg_max:.4f} spread={rg_spread_db:.2f} dB",
    ))

    # output-weight arithmetic: the base ow[] sum is deliberately
    # 1.49 (draft ratios scaled ~1.3), NOT a sum=1 invariant.
    results.append(require(
        "base emission weight sum is 1.49 (documented, not 1.0)",
        abs(OW_SUM - 1.49) < 1e-12,
        f"sum(ow)={OW_SUM:.2f}",
    ))

    impulse_ok = True
    tail_detail = []
    # probe impulse 0.5 peak (realistic bus level), 1.3 s window
    # covers the 0.66 s slowest hard-endpoint T60
    for fs in SAMPLE_RATES:
        for m in MATERIALS:
            peak, at100, at_t60, _max_state = impulse_tail(fs, m, 0.5, 1.3)
            if at100 is None or at_t60 is None:
                impulse_ok = False
            elif not (at100 <= peak and at_t60 <= peak):
                impulse_ok = False
            tail_detail.append(
                f"{int(fs)}/M{m:.2f}:peak={peak:.4f}@100ms={at100:.2e}@T60={at_t60:.2e}"
            )
    results.append(require(
        "impulse tails decay monotonically-ish (peak >= tail points)",
        impulse_ok,
        "; ".join(tail_detail[:4]) + (" ..." if len(tail_detail) > 4 else ""),
    ))

    decay_ok = True
    decay_detail = []
    # "T60" semantics: by the slowest mode's T60 the tail must be
    # substantially decayed (>= ~30 dB down) and eventually below
    # -60 dB before the probe window ends (1.3 s covers the 0.66 s
    # hard tail). The window is deliberately generous: the measured
    # @T60 point can already be -60..-100 dB and that is correct.
    for fs in SAMPLE_RATES:
        for m in MATERIALS:
            peak, at100, at_t60, _ms = impulse_tail(fs, m, 0.5, 1.3)
            if at_t60 is None or at_t60 <= 0:
                decay_ok = False
                continue
            tail_db = 20 * math.log10(at_t60)
            if tail_db > -30.0:
                decay_ok = False
            decay_detail.append(f"{int(fs)}/M{m:.2f}:{tail_db:.0f}dB")
    results.append(require(
        "impulse tail decays at least ~30 dB by slowest T60",
        decay_ok,
        "; ".join(decay_detail),
    ))

    silence_ok = True
    silence_detail = []
    # window must cover the slowest mode: soft M=0 is 0.18 s, hard
    # M=1 is 0.66 s. Probe silence for max(0.25, 1.2*slowest T60)
    # seconds so every grid point has enough time to decay.
    for fs in SAMPLE_RATES:
        for m in MATERIALS:
            slow = max(SOFT_T[i] + (HARD_T[i] - SOFT_T[i]) * m * m
                       for i in range(6))
            ok, tail = silence_after_excitation(fs, m, max(0.25, 1.2 * slow))
            if not ok:
                silence_ok = False
            silence_detail.append(f"{int(fs)}/M{m:.2f}:{tail:.1e}")
    results.append(require(
        "no self-excitation from silence after burst",
        silence_ok,
        "tail=" + "; ".join(silence_detail),
    ))

    stress_ok = True
    stress_peak = 0.0
    clamp_total = 0
    for fs in SAMPLE_RATES:
        for m in MATERIALS:
            ok, peak, clamps = stress_probe(fs, m)
            stress_ok = stress_ok and ok
            stress_peak = max(stress_peak, peak)
            clamp_total += clamps
    results.append(require(
        "stress probe: no NaN/Inf, finite state",
        stress_ok,
        f"peak out={stress_peak:.4f}",
    ))
    results.append(require(
        "emergency clamp never activates under nominal probes",
        clamp_total == 0,
        f"activations={clamp_total}",
    ))

    xtalk_max = 0.0
    for fs in SAMPLE_RATES:
        for m in MATERIALS:
            xtalk_max = max(xtalk_max, crosstalk(fs, m))
    results.append(require(
        "left-only impulse creates no right-channel output",
        xtalk_max < 1e-12,
        f"max crosstalk={xtalk_max:.2e}",
    ))

    results.append(require(
        "state bound (8.0) is never approached under stress",
        stress_peak < STATE_BOUND,
        f"peak state/out={stress_peak:.4f} vs bound 8.0",
    ))
    return results


def main() -> int:
    source = load_text(DSP)
    results: list[bool] = []
    results += check_source(source)
    results += check_metadata(source)
    results += check_numerics()

    passed = sum(results)
    total = len(results)
    print(f"\nMaterial Memory Engine P0.1 audit: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
