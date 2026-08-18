#!/usr/bin/env python3
"""Dependency-free validation harness for ANIMA v1.0.2.

Run from any working directory:
    python tools/audit_anima.py

The script exits non-zero when any required invariant fails. Same spirit as
tools/audit_dragon.py / audit_soloconsole.py / audit_materialmemory.py /
audit_stillroom.py: package/source identity plus a numerical reference model
of the actual signal path (fixed-parameter analog emulation: 30 Hz HPF,
120 Hz transformer shelf, rational mixed-harmonic saturation, tape damping,
program-dependent compression with auto makeup, level-dependent tilt,
5 Hz DC blocker, quadrature-LFO micro-flutter with Hermite interpolation,
mid/side width lift, and a transition-aware safety limiter).

ANIMA is a fixed-parameter processor (hasUserControls=false), so there are no
slider checks here; the contract is instead that @init/@sample exist, no
@slider/@block or user-control syntax appears, and the hard-coded parameter
literals match metadata.json.

Everything here is stdlib-only.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DSP = ROOT / "dsp" / "anima" / "anima.eel"
ARCHIVE = ROOT / "dsp" / "anima" / "versions" / "v1.0.2-mobile-optimization.eel"
METADATA = ROOT / "dsp" / "anima" / "metadata.json"
VERSION = "1.0.2"

# ------------------------------------------------------------------
# Design constants (must mirror the EEL source exactly)
# ------------------------------------------------------------------

DB2L = 0.11512925464970228          # ln(10)/20

HP_HZ = 30.0
SHELF_HZ = 120.0
SHELF_DB = 1.5
DRIVE_DB = 4.0
WARMTH = 0.12
TAPE_LP_HZ = 14000.0
TAPE_AMT = 0.45
TILT_HZ = 1000.0
TILT_DEPTH = 0.06
BASE_DELAY_MS = 2.0
FLUTTER_MS = 0.35
SIDE_DB = 0.7
AUTO_BASE_DB = 2.4
AUTO_MAKEUP_MAX_DB = 3.0
AUTO_ATT_SEC = 0.050
AUTO_REL_SEC = 0.400
REL_FAST_SEC = 0.150
REL_SLOW_SEC = 0.600
HIST_TIME_SEC = 0.200
ISP_COEFF = 0.25
DC_BLOCK_HZ = 5.0
OUT_DB = -0.6
CEIL_DB = -0.3

DELAY_SIZE = 4096
DELAY_MASK = DELAY_SIZE - 1
LFO_NORM_INTERVAL = 48000

SAMPLE_RATES = (44100.0, 48000.0)

MARKDOWN_SECTIONS = ("[init](init)", "[slider](slider1)", "[block](block)",
                     "[sample](sample)")


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(name: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return condition


# ------------------------------------------------------------------
# Reference model — mirrors anima.eel @sample exactly
# ------------------------------------------------------------------

class OnePole:
    __slots__ = ("a", "y")

    def __init__(self, a):
        self.a = a
        self.y = 0.0

    def process(self, x):
        self.y += self.a * (x - self.y)
        return self.y


class AnimaEngine:
    """Python port of the ANIMA sample path (fixed parameters)."""

    def __init__(self, fs):
        self.fs = fs

        # Coefficients
        self.hp_coeff = 1.0 - math.exp(-2.0 * math.pi * HP_HZ / fs)
        self.shelf_coeff = 1.0 - math.exp(-2.0 * math.pi * SHELF_HZ / fs)
        self.tape_lp_coeff = 1.0 - math.exp(-2.0 * math.pi * TAPE_LP_HZ / fs)
        self.tilt_coeff = 1.0 - math.exp(-2.0 * math.pi * TILT_HZ / fs)
        self.dc_coeff = 1.0 - math.exp(-2.0 * math.pi * DC_BLOCK_HZ / fs)

        self.drive_lin = math.exp(DRIVE_DB * DB2L)
        self.shelf_gain = math.exp(SHELF_DB * DB2L) - 1.0
        self.side_gain = math.exp(SIDE_DB * DB2L)
        self.out_gain = math.exp(OUT_DB * DB2L)
        self.ceil_lin = math.exp(CEIL_DB * DB2L)

        self.auto_base_lin = math.exp(AUTO_BASE_DB * DB2L)
        self.auto_makeup_max_lin = math.exp(AUTO_MAKEUP_MAX_DB * DB2L)
        self.auto_att_coeff = 1.0 - math.exp(-1.0 / (AUTO_ATT_SEC * fs))
        self.auto_rel_coeff = 1.0 - math.exp(-1.0 / (AUTO_REL_SEC * fs))

        self.rel_fast = math.exp(-1.0 / (REL_FAST_SEC * fs))
        self.rel_slow = math.exp(-1.0 / (REL_SLOW_SEC * fs))
        self.hist_coeff = 1.0 - math.exp(-1.0 / (HIST_TIME_SEC * fs))
        self.lim_rel = math.exp(-1.0 / (0.080 * fs))

        # Delay memory
        self.delay = [0.0] * (DELAY_SIZE * 2)
        self.wpos = 0
        self.base_delay = min(BASE_DELAY_MS * 0.001 * fs, 1600.0)
        self.flutter_depth = min(FLUTTER_MS * 0.001 * fs, 160.0)

        # Quadrature LFOs
        self.lfo1_sin_inc = math.sin(2.0 * math.pi * 0.15 / fs)
        self.lfo1_cos_inc = math.cos(2.0 * math.pi * 0.15 / fs)
        self.lfo1_sin = 0.0
        self.lfo1_cos = 1.0
        l2f = 0.23 * 1.7
        self.lfo2_sin_inc = math.sin(2.0 * math.pi * l2f / fs)
        self.lfo2_cos_inc = math.cos(2.0 * math.pi * l2f / fs)
        self.lfo2_sin = math.sin(1.3)
        self.lfo2_cos = math.cos(1.3)
        self.lfo_norm_count = 0

        # Filter state
        self.hp_l = self.hp_r = 0.0
        self.shelf_l = self.shelf_r = 0.0
        self.tape_l = self.tape_r = 0.0
        self.tilt_l = self.tilt_r = 0.0
        self.dc_l = self.dc_r = 0.0

        # Dynamics state
        self.env = 0.0
        self.history = 0.0
        self.auto_gain = self.auto_base_lin
        self.lim_gain = 1.0
        self.prev_l = self.prev_r = 0.0

        # Denormal guard
        self.denormal_guard = 10.0 ** -20
        self.denormal_sign = 1.0

        # Exposed for tests
        self.last_delay = self.base_delay
        self.lfo_mag1 = 1.0
        self.lfo_mag2 = 1.0

    def _rotate_lfos(self):
        # LFO1
        s1 = self.lfo1_sin * self.lfo1_cos_inc + self.lfo1_cos * self.lfo1_sin_inc
        c1 = self.lfo1_cos * self.lfo1_cos_inc - self.lfo1_sin * self.lfo1_sin_inc
        self.lfo1_sin, self.lfo1_cos = s1, c1
        # LFO2
        s2 = self.lfo2_sin * self.lfo2_cos_inc + self.lfo2_cos * self.lfo2_sin_inc
        c2 = self.lfo2_cos * self.lfo2_cos_inc - self.lfo2_sin * self.lfo2_sin_inc
        self.lfo2_sin, self.lfo2_cos = s2, c2

        self.lfo_norm_count += 1
        if self.lfo_norm_count >= LFO_NORM_INTERVAL:
            m1 = math.sqrt(self.lfo1_sin ** 2 + self.lfo1_cos ** 2)
            if m1 > 0:
                self.lfo1_sin /= m1
                self.lfo1_cos /= m1
            m2 = math.sqrt(self.lfo2_sin ** 2 + self.lfo2_cos ** 2)
            if m2 > 0:
                self.lfo2_sin /= m2
                self.lfo2_cos /= m2
            self.lfo_norm_count = 0

    def process(self, in_l, in_r):
        # Denormal protection
        self.denormal_sign = -self.denormal_sign
        in_l += self.denormal_guard * self.denormal_sign
        in_r += self.denormal_guard * self.denormal_sign

        # Non-finite input protection
        if in_l != in_l:
            in_l = 0.0
        if in_r != in_r:
            in_r = 0.0
        if abs(in_l) > 100.0:
            in_l = 0.0
        if abs(in_r) > 100.0:
            in_r = 0.0

        # Stage 1: 30 Hz high-pass
        self.hp_l += self.hp_coeff * (in_l - self.hp_l)
        x_l = in_l - self.hp_l
        self.hp_r += self.hp_coeff * (in_r - self.hp_r)
        x_r = in_r - self.hp_r

        # Stage 2: transformer shelf
        self.shelf_l += self.shelf_coeff * (x_l - self.shelf_l)
        x_l += self.shelf_gain * self.shelf_l
        self.shelf_r += self.shelf_coeff * (x_r - self.shelf_r)
        x_r += self.shelf_gain * self.shelf_r

        # Stage 3: asymmetric mixed-harmonic saturation
        pre_l = x_l * self.drive_lin
        pre_r = x_r * self.drive_lin
        odd_l = pre_l / (1.0 + abs(pre_l))
        odd_r = pre_r / (1.0 + abs(pre_r))
        even_l = odd_l * odd_l * 2.0
        even_r = odd_r * odd_r * 2.0
        sat_l = (odd_l + WARMTH * (even_l - odd_l)) / self.drive_lin
        sat_r = (odd_r + WARMTH * (even_r - odd_r)) / self.drive_lin

        # Stage 4: tape damping
        self.tape_l += self.tape_lp_coeff * (sat_l - self.tape_l)
        self.tape_r += self.tape_lp_coeff * (sat_r - self.tape_r)
        sat_l = self.tape_l
        sat_r = self.tape_r

        # Stage 5: tape compression, program-dependent release
        peak = max(abs(sat_l), abs(sat_r))
        self.history = self.history * (1.0 - self.hist_coeff) + peak * self.hist_coeff
        hist_clamp = min(max(self.history, 0.0), 1.0)
        dyn_rel = self.rel_fast * (1.0 - hist_clamp) + self.rel_slow * hist_clamp
        self.env = peak if peak > self.env else self.env * dyn_rel
        tape_gain = 1.0 / (1.0 + TAPE_AMT * self.env)
        sat_l *= tape_gain
        sat_r *= tape_gain

        # Stage 5.5: auto makeup gain target
        inv_tape_gain = 1.0 + TAPE_AMT * self.env
        auto_target = self.auto_base_lin * (1.0 + (inv_tape_gain - 1.0) * 0.30)
        auto_target = min(auto_target, self.auto_makeup_max_lin)
        auto_coeff = (self.auto_att_coeff if auto_target > self.auto_gain
                      else self.auto_rel_coeff)
        self.auto_gain += auto_coeff * (auto_target - self.auto_gain)
        self.auto_gain = min(max(self.auto_gain, self.auto_base_lin),
                             self.auto_makeup_max_lin)

        # Stage 6: level-dependent warmth tilt
        self.tilt_l += self.tilt_coeff * (sat_l - self.tilt_l)
        low_l = self.tilt_l
        high_l = sat_l - low_l
        self.tilt_r += self.tilt_coeff * (sat_r - self.tilt_r)
        low_r = self.tilt_r
        high_r = sat_r - low_r
        tilt_amt = TILT_DEPTH * self.env
        sat_l = low_l * (1.0 + tilt_amt) + high_l * (1.0 - 0.75 * tilt_amt)
        sat_r = low_r * (1.0 + tilt_amt) + high_r * (1.0 - 0.75 * tilt_amt)

        # Stage 7: DC removal
        self.dc_l += self.dc_coeff * (sat_l - self.dc_l)
        sat_l -= self.dc_l
        self.dc_r += self.dc_coeff * (sat_r - self.dc_r)
        sat_r -= self.dc_r

        # Stage 8: micro-flutter + delay write
        self._rotate_lfos()
        mod = self.flutter_depth * (0.65 * self.lfo1_sin + 0.35 * self.lfo2_sin)
        delay = self.base_delay + mod
        delay = max(4.0, min(float(DELAY_MASK - 3), delay))
        self.last_delay = delay
        self.lfo_mag1 = math.sqrt(self.lfo1_sin ** 2 + self.lfo1_cos ** 2)
        self.lfo_mag2 = math.sqrt(self.lfo2_sin ** 2 + self.lfo2_cos ** 2)

        self.delay[self.wpos] = sat_l
        self.delay[DELAY_SIZE + self.wpos] = sat_r

        rp = self.wpos - delay
        if rp < 0:
            rp += DELAY_SIZE

        # Stage 8.5: 4-point Hermite cubic interpolation
        i0 = int(rp)
        frac = rp - i0
        im1 = (i0 + DELAY_MASK) & DELAY_MASK
        i1 = (i0 + 1) & DELAY_MASK
        i2 = (i0 + 2) & DELAY_MASK
        wet_l = self._hermite(self.delay, im1, i0, i1, i2, frac)
        wet_r = self._hermite(self.delay, DELAY_SIZE + im1, DELAY_SIZE + i0,
                              DELAY_SIZE + i1, DELAY_SIZE + i2, frac)

        self.wpos = (self.wpos + 1) & DELAY_MASK

        # Stage 9: mid/side width lift
        mid = (wet_l + wet_r) * 0.5
        side = (wet_l - wet_r) * 0.5 * self.side_gain
        out_l = mid + side
        out_r = mid - side

        # Stage 9.5: auto makeup gain application
        out_l *= self.auto_gain
        out_r *= self.auto_gain

        # Stage 10: output trim
        out_l *= self.out_gain
        out_r *= self.out_gain

        # Stage 10.5: transition-aware safety limiter
        isp_l = abs(out_l) + ISP_COEFF * abs(out_l - self.prev_l)
        isp_r = abs(out_r) + ISP_COEFF * abs(out_r - self.prev_r)
        self.prev_l = out_l
        self.prev_r = out_r
        pk = max(isp_l, isp_r)
        lim_target = self.ceil_lin / pk if pk > self.ceil_lin else 1.0
        self.lim_gain = (lim_target if lim_target < self.lim_gain
                         else self.lim_gain * self.lim_rel
                         + lim_target * (1.0 - self.lim_rel))
        out_l *= self.lim_gain
        out_r *= self.lim_gain
        out_l = max(min(out_l, self.ceil_lin), -self.ceil_lin)
        out_r = max(min(out_r, self.ceil_lin), -self.ceil_lin)

        return out_l, out_r

    @staticmethod
    def _hermite(buf, im1, i0, i1, i2, frac):
        y0 = buf[im1]
        y1 = buf[i0]
        y2 = buf[i1]
        y3 = buf[i2]
        c0 = y1
        c1 = 0.5 * (y2 - y0)
        c2 = y0 - 2.5 * y1 + 2.0 * y2 - 0.5 * y3
        c3 = 0.5 * (y3 - y0) + 1.5 * (y1 - y2)
        return c0 + frac * (c1 + frac * (c2 + frac * c3))


# ------------------------------------------------------------------
# Numerical checks
# ------------------------------------------------------------------

def latency_window(fs: float) -> tuple[int, int]:
    """The README documents a 1.65-2.35 ms all-wet modulated delay."""
    lo = (BASE_DELAY_MS - FLUTTER_MS) * 0.001 * fs
    hi = (BASE_DELAY_MS + FLUTTER_MS) * 0.001 * fs
    return int(math.floor(lo)) - 1, int(math.ceil(hi)) + 1


def impulse_latency(fs: float) -> tuple[int, int]:
    """Unit impulse into L; return (first nonzero sample, peak sample)."""
    e = AnimaEngine(fs)
    first = peak_at = None
    peak_val = 0.0
    for n in range(512):
        x = 1.0 if n == 0 else 0.0
        ol, _ = e.process(x, 0.0)
        if abs(ol) > peak_val:
            peak_val = abs(ol)
            peak_at = n
        if first is None and abs(ol) > 1e-6:
            first = n
    return (first if first is not None else -1), (peak_at if peak_at is not None else -1)


def dc_removal(fs: float, warmup: int = 24000, settle: int = 24000) -> float:
    """Feed a DC offset; after warmup the 30 Hz HPF + 5 Hz blocker must
    reject it. Returns max |output| over the settled window."""
    e = AnimaEngine(fs)
    for _ in range(warmup):
        e.process(0.5, 0.5)
    worst = 0.0
    for _ in range(settle):
        ol, or_ = e.process(0.5, 0.5)
        worst = max(worst, abs(ol), abs(or_))
    return worst


def stress_probe(fs: float, n: int = 8192) -> tuple[bool, float]:
    """Deterministic bounded pseudo-random stress at defaults."""
    e = AnimaEngine(fs)
    peak = 0.0
    for i in range(n):
        state = (i * 2654435761) & 0xFFFFFFFF
        x = (state / 0xFFFFFFFF) * 2.0 - 1.0
        state = (i * 2654435761 + 1013904223) & 0xFFFFFFFF
        y = (state / 0xFFFFFFFF) * 2.0 - 1.0
        ol, or_ = e.process(x, y)
        peak = max(peak, abs(ol), abs(or_))
        if not (math.isfinite(ol) and math.isfinite(or_)):
            return False, float("inf")
    return True, peak


def nan_safety(fs: float, n: int = 128) -> bool:
    """NaN/Inf on the input must be sanitized to silence, not propagate."""
    e = AnimaEngine(fs)
    for _ in range(n):
        ol, or_ = e.process(float("nan"), float("inf"))
        if not (math.isfinite(ol) and math.isfinite(or_)):
            return False
    return True


def mono_safety(fs: float, n: int = 48000) -> float:
    """Identical L/R input -> identical L/R output (mid/side must collapse
    to mono). Returns max |outL - outR|."""
    e = AnimaEngine(fs)
    worst = 0.0
    for i in range(n):
        x = math.sin(2.0 * math.pi * 440.0 * i / fs) * 0.5
        ol, or_ = e.process(x, x)
        worst = max(worst, abs(ol - or_))
    return worst


def auto_gain_bounds(fs: float, n: int = 24000) -> tuple[bool, float, float]:
    """Auto makeup must stay inside [autoBaseLin, autoMakeupMaxLin]."""
    e = AnimaEngine(fs)
    lo = hi = e.auto_gain
    for i in range(n):
        x = 0.9 if (i % 256) < 128 else 0.05
        e.process(x, x)
        lo = min(lo, e.auto_gain)
        hi = max(hi, e.auto_gain)
    base = math.exp(AUTO_BASE_DB * DB2L)
    ceiling = math.exp(AUTO_MAKEUP_MAX_DB * DB2L)
    return lo >= base - 1e-12 and hi <= ceiling + 1e-12, lo, hi


def flutter_bounds(fs: float, n: int = 240000) -> tuple[bool, float, float]:
    """The modulated delay must stay within (4, DELAY_MASK-3) at all times."""
    e = AnimaEngine(fs)
    lo = hi = e.last_delay
    for i in range(n):
        x = math.sin(2.0 * math.pi * 997.0 * i / fs) * 0.5
        e.process(x, x)
        lo = min(lo, e.last_delay)
        hi = max(hi, e.last_delay)
    return lo > 4.0 and hi < float(DELAY_MASK - 3), lo, hi


def lfo_stability(fs: float, n: int = 200000) -> tuple[bool, float, float]:
    """Quadrature renormalization must keep both LFO magnitudes near 1."""
    e = AnimaEngine(fs)
    worst_lo1 = worst_hi1 = 1.0
    worst_lo2 = worst_hi2 = 1.0
    for i in range(n):
        e.process(0.0, 0.0)
        if i % 1000 == 0:
            worst_lo1 = min(worst_lo1, e.lfo_mag1)
            worst_hi1 = max(worst_hi1, e.lfo_mag1)
            worst_lo2 = min(worst_lo2, e.lfo_mag2)
            worst_hi2 = max(worst_hi2, e.lfo_mag2)
    ok = (worst_lo1 > 0.999 and worst_hi1 < 1.001
          and worst_lo2 > 0.999 and worst_hi2 < 1.001)
    return ok, min(worst_lo1, worst_lo2), max(worst_hi1, worst_hi2)


def impulse_decay(fs: float) -> float:
    """After an impulse the tail must decay toward silence (no
    self-oscillation). Measure the settled 0.5-1.0 s window."""
    e = AnimaEngine(fs)
    for n in range(64):
        e.process(1.0 if n == 0 else 0.0, 0.0)
    tail = 0.0
    for i in range(int(1.0 * fs)):
        ol, or_ = e.process(0.0, 0.0)
        if i >= int(0.5 * fs):
            tail = max(tail, abs(ol), abs(or_))
    return tail


# ------------------------------------------------------------------
# Static source checks
# ------------------------------------------------------------------

def check_source(source: str) -> list[bool]:
    results: list[bool] = []

    results.append(require(
        "desc first line with ANIMA identity",
        source.startswith("desc: ANIMA - Vintage Harmonic Engine"),
    ))

    present = [name for name in ("@init", "@sample")
               if re.search(rf"(?m)^{re.escape(name)}\s*$", source)]
    absent = [name for name in ("@slider", "@block")
              if re.search(rf"(?m)^{re.escape(name)}\s*$", source)]
    results.append(require(
        "fixed-parameter section contract (@init + @sample only)",
        len(present) == 2 and not absent,
        f"present={present} absent={absent}",
    ))

    results.append(require(
        "no user-control syntax (no slider declarations or :param UI)",
        not re.search(r"(?m)^slider\d+:", source)
        and not re.search(r"(?m)^\w+:\d*\.?\d*<", source),
    ))

    expected_literals = {
        "hpHz = 30;": True, "shelfHz = 120;": True, "shelfDb = 1.5;": True,
        "driveDb = 4.0;": True, "warmth = 0.12;": True,
        "tapeLpHz = 14000;": True, "tapeAmt = 0.45;": True,
        "tiltHz = 1000;": True, "tiltDepth = 0.06;": True,
        "baseDelayMs = 2.0;": True, "flutterMs = 0.35;": True,
        "sideDb = 0.7;": True, "outDb = -0.6;": True, "ceilDb = -0.3;": True,
        "autoBaseDb = 2.4;": True, "autoMakeupMaxDb = 3.0;": True,
        "relFastSec = 0.150;": True, "relSlowSec = 0.600;": True,
        "histTimeSec = 0.200;": True, "ispCoeff = 0.25;": True,
        "dcBlockHz = 5;": True,
    }
    missing = [lit for lit, _ in expected_literals.items() if lit not in source]
    results.append(require(
        "hard-coded parameter literals match v1.0.2",
        not missing,
        f"missing={missing}",
    ))

    results.append(require(
        "recursive quadrature LFOs present",
        "lfo1Sin" in source and "lfo2Sin" in source
        and "lfoNormInterval = 48000;" in source,
    ))

    results.append(require(
        "4-point Hermite cubic interpolation present",
        "c3 = 0.5 * (y3 - y0) + 1.5 * (y1 - y2);" in source,
    ))

    results.append(require(
        "non-finite input sanitizer present",
        "inL != inL ? inL = 0;" in source
        and "inR != inR ? inR = 0;" in source
        and "abs(inL) > 100 ? inL = 0;" in source,
    ))

    results.append(require(
        "denormal guard present",
        "denormalGuard = pow(10, -20);" in source,
    ))

    results.append(require(
        "inline-only body (no function or malloc — mobile discipline)",
        "function " not in source and "malloc" not in source,
    ))

    results.append(require(
        "no Markdown-corrupted section markers",
        not any(marker in source for marker in MARKDOWN_SECTIONS),
    ))

    results.append(require(
        "README labels ANIMA Definitive",
        "Definitive" in load_text(ROOT / "dsp" / "anima" / "README.md"),
    ))

    results.append(require(
        "CHANGELOG describes v1.0.2 quadrature-oscillator release",
        "1.0.2" in load_text(ROOT / "dsp" / "anima" / "CHANGELOG.md")
        and "quadrature" in load_text(ROOT / "dsp" / "anima" / "CHANGELOG.md"),
    ))

    return results


def check_metadata() -> list[bool]:
    results: list[bool] = []
    try:
        metadata = json.loads(load_text(METADATA))
    except json.JSONDecodeError:
        results.append(require("metadata.json is valid JSON", False))
        return results

    results.append(require(
        "metadata identity: version/status/type/display",
        metadata.get("name") == "ANIMA"
        and metadata.get("version") == VERSION
        and metadata.get("status") == "definitive"
        and metadata.get("type") == "fixed-parameter-analog-emulation"
        and metadata.get("displayName") == "ANIMA — Vintage Harmonic Engine",
    ))

    results.append(require(
        "metadata file/latency/controls contract",
        metadata.get("file") == "anima.eel"
        and metadata.get("latencyMs") == 2.0
        and metadata.get("hasUserControls") is False,
    ))

    results.append(require(
        "metadata version map points at v1.0.2 archive",
        metadata.get("versions", {}).get("v1.0.2")
        == "versions/v1.0.2-mobile-optimization.eel",
    ))

    results.append(require(
        "metadata feature list includes core ANIMA features",
        all(f in metadata.get("features", []) for f in (
            "even-harmonic-saturation",
            "program-dependent-compression",
            "auto-makeup-gain",
            "micro-flutter",
            "hermite-interpolation",
            "mid-side-width",
            "quadrature-lfo-oscillator",
        )),
    ))

    # Parameter parity between metadata and the hard-coded values.
    params = metadata.get("parameters", {})
    parity_ok = all(abs(params.get(k, 1e9) - v) < 1e-9 for k, v in (
        ("highPassHz", HP_HZ), ("shelfHz", SHELF_HZ), ("shelfDb", SHELF_DB),
        ("driveDb", DRIVE_DB), ("warmth", WARMTH), ("tapeLpHz", TAPE_LP_HZ),
        ("tapeAmt", TAPE_AMT), ("tiltHz", TILT_HZ), ("tiltDepth", TILT_DEPTH),
        ("baseDelayMs", BASE_DELAY_MS), ("flutterMs", FLUTTER_MS),
        ("sideDb", SIDE_DB), ("autoBaseDb", AUTO_BASE_DB),
        ("autoMakeupMaxDb", AUTO_MAKEUP_MAX_DB), ("relFastSec", REL_FAST_SEC),
        ("relSlowSec", REL_SLOW_SEC), ("histTimeSec", HIST_TIME_SEC),
        ("ispCoeff", ISP_COEFF), ("dcBlockHz", DC_BLOCK_HZ),
        ("outDb", OUT_DB), ("ceilDb", CEIL_DB),
    ))
    results.append(require(
        "metadata parameters match the hard-coded v1.0.2 values",
        parity_ok,
    ))

    results.append(require(
        "archive/current byte identity",
        ARCHIVE.exists() and ARCHIVE.read_bytes() == DSP.read_bytes(),
    ))

    return results


def check_numerics() -> list[bool]:
    results: list[bool] = []

    # Latency: all-wet modulated delay in the documented 1.65-2.35 ms window.
    lat_ok = True
    details = []
    for fs in SAMPLE_RATES:
        first, peak_at = impulse_latency(fs)
        lo, hi = latency_window(fs)
        in_win = lo <= first <= hi and lo <= peak_at <= hi
        lat_ok = lat_ok and in_win
        details.append(f"{fs:.0f}Hz first={first} peak={peak_at} window=[{lo},{hi}]")
    results.append(require(
        "impulse latency is the documented 1.65-2.35 ms modulated delay",
        lat_ok and (BASE_DELAY_MS + FLUTTER_MS) < 5.0,
        "; ".join(details) + " (Haas zone < 5 ms)",
    ))

    # DC removal.
    dc_ok = True
    for fs in SAMPLE_RATES:
        worst = dc_removal(fs)
        if worst > 1e-3:
            dc_ok = False
    results.append(require(
        "DC offset rejected by the 30 Hz HPF + 5 Hz blocker",
        dc_ok,
        "settled |out| < 1e-3 under 0.5 DC input",
    ))

    # Stress / boundedness.
    stress_ok = True
    peak = 0.0
    for fs in SAMPLE_RATES:
        ok, pk = stress_probe(fs)
        stress_ok = stress_ok and ok
        peak = max(peak, pk)
    ceil = math.exp(CEIL_DB * DB2L)
    results.append(require(
        "stress probe: no NaN/Inf, output within limiter ceiling",
        stress_ok and peak <= ceil + 1e-9,
        f"peak out={peak:.5f} (ceiling {ceil:.5f})",
    ))

    # NaN/Inf input sanitization.
    results.append(require(
        "NaN/Inf input is sanitized to finite output",
        all(nan_safety(fs) for fs in SAMPLE_RATES),
    ))

    # Mono safety: mid/side collapses to mono on a centered signal.
    mono_ok = True
    for fs in SAMPLE_RATES:
        if mono_safety(fs) > 1e-9:
            mono_ok = False
    results.append(require(
        "mono safety: identical L/R input yields identical L/R output",
        mono_ok,
        "mid/side width lift is mono-compatible",
    ))

    # Auto makeup gain bounded.
    ag_ok = True
    for fs in SAMPLE_RATES:
        ok, lo, hi = auto_gain_bounds(fs)
        ag_ok = ag_ok and ok
    results.append(require(
        "auto makeup gain stays within [autoBaseLin, autoMakeupMaxLin]",
        ag_ok,
    ))

    # Flutter delay bounds.
    fb_ok = True
    for fs in SAMPLE_RATES:
        ok, lo, hi = flutter_bounds(fs)
        fb_ok = fb_ok and ok
    results.append(require(
        "flutter delay stays within (4, 4093) across the LFO cycle",
        fb_ok,
        "delay in legal read range of the 4096-slot ring",
    ))

    # Quadrature renormalization keeps LFO magnitude ~1.
    lfo_ok = True
    for fs in SAMPLE_RATES:
        ok, lo, hi = lfo_stability(fs)
        lfo_ok = lfo_ok and ok
    results.append(require(
        "quadrature renormalization holds LFO magnitude ~1",
        lfo_ok,
        "magnitude stays within [0.999, 1.001] over 200k samples",
    ))

    # No self-oscillation.
    decay_ok = True
    for fs in SAMPLE_RATES:
        if impulse_decay(fs) > 1e-4:
            decay_ok = False
    results.append(require(
        "impulse response decays to silence (no self-oscillation)",
        decay_ok,
        "tail < 1e-4 in the 0.5-1.0 s window",
    ))

    return results


def main() -> int:
    source = load_text(DSP)
    results: list[bool] = []
    results += check_source(source)
    results += check_metadata()
    results += check_numerics()

    passed = sum(results)
    total = len(results)
    print(f"\nANIMA v1.0.2 audit: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
