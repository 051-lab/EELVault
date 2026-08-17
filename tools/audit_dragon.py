#!/usr/bin/env python3
"""Dependency-free validation harness for DRAGON v1.0.0.

Run from any working directory:
    python tools/audit_dragon.py

The script exits non-zero when any required invariant fails.
Same spirit as tools/audit_stillroom.py / audit_soloconsole.py /
audit_materialmemory.py: package/source identity plus a numerical
reference model of the actual signal path (linked tape compression,
tanh saturator, 3-component wow & flutter delay, replay EQ chain,
Dolby-C-shaped hiss, soft limiter).

Everything here is stdlib-only.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DSP = ROOT / "dsp" / "dragon" / "dragon.eel"
ARCHIVE = ROOT / "dsp" / "dragon" / "versions" / "v1.0.0-absolute-lab-calibration.eel"
METADATA = ROOT / "dsp" / "dragon" / "metadata.json"
VERSION = "1.0.0"

# ------------------------------------------------------------------
# Design constants (must mirror the EEL source exactly)
# ------------------------------------------------------------------

DB2L = 0.11512925464970228          # ln(10)/20
WF_BASE = 12.0                      # base delay samples
WF_SIZE = 64                        # delay line length per channel
WF_MASK = WF_SIZE - 1
XTK = 0.001                         # 10^(-60/20) tape separation bleed
LIMIT_T = 0.891                     # soft limiter threshold
LIMIT_K = 9.174311926605505         # 1/(1-0.891) - limiter knee slope
CLAMP = 0.99999

# W&F components: (frequency Hz, peak deviation) at depth 1.0
WF_COMPONENTS = ((1.0, 0.00010), (4.0, 0.00012), (8.5, 0.00007))

# Slider defaults
DEF_DRIVE = 3.0
DEF_BIAS = 3.0
DEF_COMP = 2.0
DEF_WF = 1.0
DEF_BUMP = 1.0
DEF_ROLL = 3.5
DEF_HISS = -82.0
DEF_TRIM = 0.0

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
# Coefficient helpers (mirror the EEL rbj_* functions)
# ------------------------------------------------------------------

def rbj_hishelf(f, dB, S, fs):
    A = pow(10.0, dB / 40.0)
    w0 = 2.0 * math.pi * f / fs
    cw = math.cos(w0)
    sA = math.sqrt(A)
    alpha = math.sin(w0) / 2.0 * math.sqrt((A + 1.0 / A) * (1.0 / S - 1.0) + 2.0)
    beta = 2.0 * sA * alpha
    a0i = 1.0 / ((A + 1.0) - (A - 1.0) * cw + beta)
    return (
        A * ((A + 1.0) + (A - 1.0) * cw + beta) * a0i,
        -2.0 * A * ((A - 1.0) + (A + 1.0) * cw) * a0i,
        A * ((A + 1.0) + (A - 1.0) * cw - beta) * a0i,
        2.0 * ((A - 1.0) - (A + 1.0) * cw) * a0i,
        ((A + 1.0) - (A - 1.0) * cw - beta) * a0i,
    )


def rbj_lowshelf(f, dB, S, fs):
    A = pow(10.0, dB / 40.0)
    w0 = 2.0 * math.pi * f / fs
    cw = math.cos(w0)
    sA = math.sqrt(A)
    alpha = math.sin(w0) / 2.0 * math.sqrt((A + 1.0 / A) * (1.0 / S - 1.0) + 2.0)
    beta = 2.0 * sA * alpha
    a0i = 1.0 / ((A + 1.0) + (A - 1.0) * cw + beta)
    return (
        A * ((A + 1.0) - (A - 1.0) * cw + beta) * a0i,
        2.0 * A * ((A - 1.0) - (A + 1.0) * cw) * a0i,
        A * ((A + 1.0) - (A - 1.0) * cw - beta) * a0i,
        -2.0 * ((A - 1.0) + (A + 1.0) * cw) * a0i,
        ((A + 1.0) + (A - 1.0) * cw - beta) * a0i,
    )


def rbj_peak(f, q, dB, fs):
    A = pow(10.0, dB / 40.0)
    w0 = 2.0 * math.pi * f / fs
    cw = math.cos(w0)
    alpha = math.sin(w0) / (2.0 * q)
    a0i = 1.0 / (1.0 + alpha / A)
    return (
        (1.0 + alpha * A) * a0i,
        -2.0 * cw * a0i,
        (1.0 - alpha * A) * a0i,
        -2.0 * cw * a0i,
        (1.0 - alpha / A) * a0i,
    )


# ------------------------------------------------------------------
# Reference model — mirrors dragon.eel @sample exactly
# ------------------------------------------------------------------

class Biquad:
    __slots__ = ("b0", "b1", "b2", "a1", "a2", "x1", "x2", "y1", "y2")

    def __init__(self, coeffs):
        self.b0, self.b1, self.b2, self.a1, self.a2 = coeffs
        self.x1 = self.x2 = self.y1 = self.y2 = 0.0

    def process(self, x):
        y = (self.b0 * x + self.b1 * self.x1 + self.b2 * self.x2
             - self.a1 * self.y1 - self.a2 * self.y2)
        self.x2 = self.x1
        self.x1 = x
        self.y2 = self.y1
        self.y1 = y
        return y


class OnePole:
    __slots__ = ("a", "y")

    def __init__(self, a):
        self.a = a
        self.y = 0.0

    def process(self, x):
        self.y += self.a * (x - self.y)
        return self.y


class DCBlock:
    __slots__ = ("r", "xm1", "ym1")

    def __init__(self, r):
        self.r = r
        self.xm1 = 0.0
        self.ym1 = 0.0

    def process(self, x):
        y = x - self.xm1 + self.r * self.ym1
        self.xm1 = x
        self.ym1 = y
        return y


class DragonEngine:
    """Python port of the DRAGON sample path.

    Coefficients follow the v1.0.0 calibration at the given slider
    values and sample rate. The per-sample loop matches @sample:
    linked pass (smoothing, envelope, W&F, hiss, delay reads) then
    the per-channel S1..S13 chains.
    """

    def __init__(self, fs, drive=DEF_DRIVE, bias=DEF_BIAS, comp=DEF_COMP,
                 wf=DEF_WF, bump=DEF_BUMP, roll=DEF_ROLL, hiss=DEF_HISS,
                 trim=DEF_TRIM):
        self.fs = fs

        # Targets + smoothed states (start at targets: no sweep on load)
        self.t_drive, self.t_bias = drive, bias
        self.t_comp, self.t_wf = comp, wf
        self.t_bump, self.t_roll = bump, roll
        self.t_hiss, self.t_trim = hiss, trim
        self.drive_s = drive
        self.bias_s = bias
        self.comp_s = comp
        self.wf_s = wf
        self.bump_s = bump
        self.roll_s = roll
        self.hiss_s = hiss
        self.trim_s = trim
        self.bump_last = bump
        self.roll_last = roll

        # One-pole / ballistics coefficients (from update_rate_coeffs)
        self.sm_a = 1.0 - math.exp(-1.0 / (0.012 * fs))
        self.ca = math.exp(-1.0 / (0.004 * fs))
        self.cr = math.exp(-1.0 / (0.090 * fs))
        self.dcr = math.exp(-2.0 * math.pi * 7.0 / fs)
        aa_fc = 18000.0
        self.aaa = 1.0 - math.exp(-2.0 * math.pi * aa_fc / fs)
        self.hp90a = 1.0 - math.exp(-2.0 * math.pi * 90.0 / fs)
        self.lp38a = 1.0 - math.exp(-2.0 * math.pi * 3800.0 / fs)
        self.lp90a = 1.0 - math.exp(-2.0 * math.pi * 9000.0 / fs)
        self.wanda = 1.0 - math.exp(-2.0 * math.pi * 0.2 / fs)

        # W&F oscillators (quadrature pairs; init to y[-1], y[-2])
        self.kw = 2.0 * math.cos(2.0 * math.pi * 1.0 / fs)
        self.km = 2.0 * math.cos(2.0 * math.pi * 4.0 / fs)
        self.kf = 2.0 * math.cos(2.0 * math.pi * 8.5 / fs)
        self.awc = 0.00010 / (2.0 * math.pi * 1.0) * fs
        self.amc = 0.00012 / (2.0 * math.pi * 4.0) * fs
        self.afc = 0.00007 / (2.0 * math.pi * 8.5) * fs
        self.w_s1 = -math.sin(2.0 * math.pi * 1.0 / fs)
        self.w_s2 = -math.sin(4.0 * math.pi * 1.0 / fs)
        self.w_c1 = math.cos(2.0 * math.pi * 1.0 / fs)
        self.w_c2 = math.cos(4.0 * math.pi * 1.0 / fs)
        self.m_s1 = -math.sin(2.0 * math.pi * 4.0 / fs)
        self.m_s2 = -math.sin(4.0 * math.pi * 4.0 / fs)
        self.m_c1 = math.cos(2.0 * math.pi * 4.0 / fs)
        self.m_c2 = math.cos(4.0 * math.pi * 4.0 / fs)
        self.f_s1 = -math.sin(2.0 * math.pi * 8.5 / fs)
        self.f_s2 = -math.sin(4.0 * math.pi * 8.5 / fs)
        self.f_c1 = math.cos(2.0 * math.pi * 8.5 / fs)
        self.f_c2 = math.cos(4.0 * math.pi * 8.5 / fs)
        self.agc_ctr = 0
        self.wp = 0
        self.wander = 0.0

        # Biquad banks (fixed + user at current defaults)
        em = rbj_hishelf(3183.0, 3.5, 0.9, fs)
        de = rbj_hishelf(3183.0, -3.5, 0.9, fs)
        iec = rbj_hishelf(2273.6, -4.0, 0.707, fs)
        lt = rbj_lowshelf(50.0, 1.0, 0.9, fs)
        hb = rbj_peak(50.0, 0.95, bump, fs)
        hf = rbj_hishelf(14000.0, -roll, 0.8, fs)

        self.chains = {}
        for ch in ("L", "R"):
            self.chains[ch] = {
                "dc1": DCBlock(self.dcr),
                "em": Biquad(em),
                "aa1": OnePole(self.aaa),
                "aa2": OnePole(self.aaa),
                "dm": OnePole(0.0),          # damping coeff set per sample
                "de": Biquad(de),
                "iec": Biquad(iec),
                "hb": Biquad(hb),
                "lt": Biquad(lt),
                "hf": Biquad(hf),
                "hp": OnePole(self.hp90a),
                "h1": OnePole(self.lp38a),
                "h2": OnePole(self.lp90a),
                "dc2": DCBlock(self.dcr),
            }

        self.mem = [0.0] * (2 * WF_SIZE)
        self.env = 0.0
        self.dl_L = 0.0
        self.dl_R = 0.0
        self.hiss_l = 0.0
        self.hiss_r = 0.0

        # Deterministic RNG for hiss (mirrors sequential rand() draws)
        self.rng_state = 0x2545F4914F6CDD1D & 0xFFFFFFFFFFFFFFFF

    def _rand(self):
        # xorshift64 — deterministic stand-in for EEL rand()
        self.rng_state ^= (self.rng_state << 13) & 0xFFFFFFFFFFFFFFFF
        self.rng_state ^= self.rng_state >> 7
        self.rng_state ^= (self.rng_state << 17) & 0xFFFFFFFFFFFFFFFF
        return (self.rng_state & 0xFFFFFFFF) / 0xFFFFFFFF

    def process(self, in_l, in_r):
        # ---- LINKED PASS (once per frame) ----
        sm_a = self.sm_a
        self.drive_s += (self.t_drive - self.drive_s) * sm_a
        self.bias_s  += (self.t_bias  - self.bias_s)  * sm_a
        self.comp_s  += (self.t_comp  - self.comp_s)  * sm_a
        self.wf_s    += (self.t_wf    - self.wf_s)    * sm_a
        self.hiss_s  += (self.t_hiss  - self.hiss_s)  * sm_a
        self.trim_s  += (self.t_trim  - self.trim_s)  * sm_a
        driveLin = math.exp(self.drive_s * DB2L)
        makeup = 1.0 / (1.0 + 0.18 * max(0.0, driveLin - 1.0))
        asym = 0.004 + self.bias_s * 0.010

        # S4 linked envelope detector
        ein = max(abs(in_l), abs(in_r)) * driveLin
        if ein >= self.env:
            self.env = self.ca * self.env + (1.0 - self.ca) * ein
        else:
            self.env = self.cr * self.env + (1.0 - self.cr) * ein
        envN = min(1.6, self.env * 2.0)
        gr = self.comp_s * envN * envN / (1.0 + envN * envN)
        gcomp = math.exp(-gr * DB2L)

        # S6 damping coefficient
        dfc = max(7000.0, 30000.0 / (1.0 + 3.0 * envN))
        da = 1.0 - math.exp(-2.0 * math.pi * dfc / self.fs)

        # S7 W&F oscillators (recursive resonators)
        kw, km, kf = self.kw, self.km, self.kf
        wn = kw * self.w_s1 - self.w_s2; self.w_s2 = self.w_s1; self.w_s1 = wn
        cn = kw * self.w_c1 - self.w_c2; self.w_c2 = self.w_c1; self.w_c1 = cn
        mn = km * self.m_s1 - self.m_s2; self.m_s2 = self.m_s1; self.m_s1 = mn
        cq = km * self.m_c1 - self.m_c2; self.m_c2 = self.m_c1; self.m_c1 = cq
        fn = kf * self.f_s1 - self.f_s2; self.f_s2 = self.f_s1; self.f_s1 = fn
        qn = kf * self.f_c1 - self.f_c2; self.f_c2 = self.f_c1; self.f_c1 = qn
        self.agc_ctr += 1
        if self.agc_ctr >= 512:
            self._agc()
            self.agc_ctr = 0

        off = WF_BASE + self.wf_s * (self.awc * wn + self.amc * mn + self.afc * fn)
        self.last_off = off

        # S9 hiss: uncorrelated TPDF + slow wander
        nzL = (self._rand() + self._rand() - 2.0) * 0.5
        nzR = (self._rand() + self._rand() - 2.0) * 0.5
        self.hiss_l = nzL
        self.hiss_r = nzR
        self.wander += self.wanda * (nzL - self.wander)
        hissGain = math.exp((self.hiss_s - 0.15 * self.bias_s) * DB2L) * (1.0 + 0.1 * self.wander)
        trimLin = math.exp(self.trim_s * DB2L)

        # Shared delay-line reads (read before write this frame)
        rr = self.wp - off + WF_SIZE
        i0 = int(math.floor(rr)) & WF_MASK
        fr = rr - math.floor(rr)
        self.dl_L = self.mem[i0] * (1.0 - fr) + self.mem[(i0 + 1) & WF_MASK] * fr
        self.dl_R = self.mem[WF_SIZE + i0] * (1.0 - fr) + self.mem[WF_SIZE + ((i0 + 1) & WF_MASK)] * fr

        # ---- PER-CHANNEL CHAINS ----
        out_l = self._channel("L", in_l, driveLin, makeup, asym, gcomp, da,
                              hissGain, trimLin, nzL)
        out_r = self._channel("R", in_r, driveLin, makeup, asym, gcomp, da,
                              hissGain, trimLin, nzR)

        self.wp = (self.wp + 1) & WF_MASK
        return out_l, out_r

    def _agc(self):
        """Explicit AGC renormalization (called when agc_ctr reaches 512)."""
        for name in ("w", "m", "f"):
            s1 = getattr(self, f"{name}_s1")
            c1 = getattr(self, f"{name}_c1")
            amp = math.sqrt(s1 * s1 + c1 * c1)
            if amp > 1e-6:
                sc = 1.0 / amp
                setattr(self, f"{name}_s1", s1 * sc)
                setattr(self, f"{name}_s2", getattr(self, f"{name}_s2") * sc)
                setattr(self, f"{name}_c1", c1 * sc)
                setattr(self, f"{name}_c2", getattr(self, f"{name}_c2") * sc)

    def _channel(self, ch, x, driveLin, makeup, asym, gcomp, da,
                 hissGain, trimLin, nz):
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
        # S5 saturator
        s = x * driveLin
        v = math.tanh(s)
        x = (v + asym * v * v) * makeup
        # S6 dynamic HF damping
        x = c["dm"].process(x)
        # S7 write into delay line
        if ch == "L":
            self.mem[self.wp] = x
            # S7b tape separation bleed
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
        # S9 hiss
        hn = nz - c["hp"].process(nz)
        hn = c["h1"].process(hn)
        hn = c["h2"].process(hn)
        x += hn * hissGain
        # S10 trim
        x *= trimLin
        # S11 output DC blocker
        x = c["dc2"].process(x)
        # S12 soft limiter
        ax = abs(x)
        if ax > LIMIT_T:
            y = LIMIT_T + (1.0 - LIMIT_T) * math.tanh((ax - LIMIT_T) * LIMIT_K)
            x = y if x > 0.0 else -y
        # S13 hard clamp
        return max(-CLAMP, min(CLAMP, x))


# ------------------------------------------------------------------
# Numerical checks
# ------------------------------------------------------------------

def computed_wrms_pct() -> float:
    """Actual combined WRMS deviation from the three components."""
    wrms = math.sqrt(sum(dev * dev / 2.0 for _, dev in WF_COMPONENTS))
    return wrms * 100.0


def wf_offset_bounds() -> tuple[bool, float, float]:
    """off = WF_BASE + wf_s*(...): must stay inside (0, 64) for all
    depths and both target rates, so the delay read never wraps into
    unwritten memory."""
    ok = True
    lo, hi = 1e9, -1e9
    for fs in SAMPLE_RATES:
        awc = 0.00010 / (2.0 * math.pi * 1.0) * fs
        amc = 0.00012 / (2.0 * math.pi * 4.0) * fs
        afc = 0.00007 / (2.0 * math.pi * 8.5) * fs
        for depth in (0.0, 0.5, 1.0, 1.5, 2.0):
            peak = depth * (awc + amc + afc)
            lo = min(lo, WF_BASE - peak)
            hi = max(hi, WF_BASE + peak)
    if lo < 1.0 or hi > 63.0:
        ok = False
    return ok, lo, hi


def impulse_latency(fs: float) -> tuple[int, float]:
    """Unit impulse into L; return (first nonzero output sample, peak)."""
    e = DragonEngine(fs, wf=0.0, hiss=-200.0, drive=0.0, bias=0.0,
                     comp=0.0, bump=0.0, roll=0.0, trim=0.0)
    first = None
    peak = 0.0
    for n in range(64):
        x = 1.0 if n == 0 else 0.0
        ol, _ = e.process(x, 0.0)
        peak = max(peak, abs(ol))
        if first is None and abs(ol) > 1e-6:
            first = n
    return (first if first is not None else -1), peak


def stress_probe(fs: float, n: int = 8192) -> tuple[bool, float]:
    """Deterministic bounded pseudo-random stress at full defaults.
    Returns (all_finite, peak_out_abs)."""
    e = DragonEngine(fs)
    peak = 0.0
    for i in range(n):
        state = (i * 2654435761) & 0xFFFFFFFF
        x = (state / 0xFFFFFFFF) * 2.0 - 1.0
        state = ((i * 2654435761 + 1013904223) & 0xFFFFFFFF)
        y = (state / 0xFFFFFFFF) * 2.0 - 1.0
        ol, or_ = e.process(x, y)
        peak = max(peak, abs(ol), abs(or_))
        if not (math.isfinite(ol) and math.isfinite(or_)):
            return False, float("inf")
    return True, peak


def corner_case_stack(fs: float) -> tuple[bool, float]:
    """Worst legal stack: drive 10, bump 4, rolloff 0, trim +12 dB,
    full-scale input. Output must stay within the hard clamp."""
    e = DragonEngine(fs, drive=10.0, bump=4.0, roll=0.0, trim=12.0,
                     comp=6.0, wf=2.0, bias=10.0, hiss=-42.0)
    peak = 0.0
    for i in range(4096):
        x = 0.99 if (i % 64) < 32 else -0.99
        ol, or_ = e.process(x, x)
        peak = max(peak, abs(ol), abs(or_))
        if not (math.isfinite(ol) and math.isfinite(or_)):
            return False, float("inf")
    return peak <= CLAMP + 1e-9, peak


def hiss_uncorrelated() -> tuple[bool, float]:
    """L/R TPDF hiss draws must be uncorrelated (sequential rand())."""
    e = DragonEngine(48000.0)
    lv, rv = [], []
    for _ in range(4096):
        e.process(0.0, 0.0)
        lv.append(e.hiss_l)
        rv.append(e.hiss_r)
    ml, mr = sum(lv) / len(lv), sum(rv) / len(rv)
    cov = sum((a - ml) * (b - mr) for a, b in zip(lv, rv)) / len(lv)
    vl = sum((a - ml) ** 2 for a in lv) / len(lv)
    vr = sum((b - mr) ** 2 for b in rv) / len(rv)
    corr = cov / math.sqrt(vl * vr) if vl > 0 and vr > 0 else 1.0
    return abs(corr) < 0.1, corr


def impulse_decay(fs: float) -> float:
    """After an impulse, the tail must decay to the hiss floor (no
    self-oscillation, stable IIRs). The 7 Hz DC blockers legitimately
    ring for ~200 ms (22.7 ms time constant); measure the settled
    200-300 ms window. Returns max |output| in that window."""
    e = DragonEngine(fs, wf=1.0)
    for n in range(64):
        e.process(1.0 if n == 0 else 0.0, 0.0)
    tail = 0.0
    for i in range(int(0.3 * fs)):
        ol, or_ = e.process(0.0, 0.0)
        if i >= int(0.2 * fs):
            tail = max(tail, abs(ol), abs(or_))
    return tail


# ------------------------------------------------------------------
# Static source checks
# ------------------------------------------------------------------

def check_source(source: str) -> list[bool]:
    results: list[bool] = []

    expected = {"drive": DEF_DRIVE, "bias": DEF_BIAS, "comp": DEF_COMP,
                "wflutter": DEF_WF, "bump": DEF_BUMP, "rolloff": DEF_ROLL,
                "hiss": DEF_HISS, "trim": DEF_TRIM}
    declared = {}
    for m in re.finditer(r"(?m)^(\w+):([-\d.]+)<", source):
        declared[m.group(1)] = float(m.group(2))
    results.append(require(
        "eight slider declarations with v1.0.0 defaults",
        all(abs(declared.get(k, 1e9) - v) < 1e-12 for k, v in expected.items()),
        str([(k, declared.get(k)) for k in expected]),
    ))

    section_lines = [name for name in ("@init", "@slider", "@block", "@sample")
                     if re.search(rf"(?m)^{re.escape(name)}\s*$", source)]
    results.append(require(
        "native EEL2 sections present",
        len(section_lines) == 4, str(section_lines),
    ))

    order_ok = (source.find("drive:") < source.find("@init")
                and source.find("@init") < source.find("@slider")
                and source.find("@slider") < source.find("@block")
                and source.find("@block") < source.find("@sample"))
    results.append(require("EEL2 section order and slider-first layout", order_ok))

    results.append(require(
        "desc first line with Dragon identity",
        source.startswith("desc: Dragon Cassette Emulator"),
    ))

    results.append(require(
        "no C/C++ braces in body",
        "{" not in source.replace("//", ""),
    ))

    results.append(require(
        "function definitions are space-separated (RJDSP dialect)",
        "function rbj_hishelf(f dB S)" in source
        and "function rbj_lowshelf(f dB S)" in source
        and "function rbj_peak(f q dB)" in source,
    ))
    results.append(require(
        "no comma-separated function definitions (RJDSP silent-NaN trap)",
        "function rbj_hishelf(f, dB, S)" not in source
        and "function rbj_lowshelf(f, dB, S)" not in source
        and "function rbj_peak(f, q, dB)" not in source,
    ))

    results.append(require(
        "delay memory is mem[0..63] L / mem[64..127] R, size 64 wrap",
        "loop(128, mem[i] = 0;" in source
        and "mem[64 + wp] = x;" in source
        and "& 63" in source
        and "WF_BASE = 12;" in source,
    ))

    results.append(require(
        "calibration constants present",
        "XTK = 0.001;" in source
        and "3183" in source and "2273.6" in source
        and "14000" in source and "-82" in source
        and "0.017" in source,
    ))

    results.append(require(
        "linked envelope + three-component W&F present",
        "max(abs(spl0), abs(spl1))" in source
        and "kw = 2*cos(2*$pi*1.0/srate)" in source
        and "km = 2*cos(2*$pi*4.0/srate)" in source
        and "kf = 2*cos(2*$pi*8.5/srate)" in source,
    ))

    results.append(require(
        "output protection chain present",
        "0.891 + 0.109*tanh" in source
        and "min(max(x, -0.99999), 0.99999)" in source
        and "spl0 = min(max(x, -0.99999), 0.99999)" in source
        and "spl1 = min(max(x, -0.99999), 0.99999)" in source,
    ))

    results.append(require(
        "AGC renormalization every 512 samples",
        "agc_ctr >= 512 ? (" in source,
    ))

    results.append(require(
        "sample-rate change re-cooks coefficients",
        "srate != route_srate ?" in source,
    ))

    results.append(require(
        "no Markdown-corrupted section markers",
        not any(marker in source for marker in MARKDOWN_SECTIONS),
    ))

    results.append(require(
        "README labels DRAGON experimental",
        "Experimental" in load_text(ROOT / "dsp" / "dragon" / "README.md"),
    ))

    results.append(require(
        "CHANGELOG describes v1.0.0 Absolute Lab Calibration",
        "1.0.0" in load_text(ROOT / "dsp" / "dragon" / "CHANGELOG.md")
        and "Absolute Lab Calibration" in load_text(ROOT / "dsp" / "dragon" / "CHANGELOG.md"),
    ))
    return results


def check_metadata(source: str) -> list[bool]:
    results: list[bool] = []
    try:
        metadata = json.loads(load_text(METADATA))
    except json.JSONDecodeError:
        results.append(require("metadata.json is valid JSON", False))
        return results

    results.append(require(
        "metadata identity: version/status/type/display",
        metadata.get("name") == "dragon"
        and metadata.get("version") == VERSION
        and metadata.get("status") == "experimental"
        and metadata.get("type") == "reference-cassette-deck-emulation"
        and metadata.get("displayName") == "DRAGON — Reference Cassette Deck Emulator",
    ))
    results.append(require(
        "metadata file/latency/controls contract",
        metadata.get("file") == "dragon.eel"
        and metadata.get("latencyMs") == 0.27
        and metadata.get("hasUserControls") is True,
    ))
    results.append(require(
        "metadata version map points at v1.0.0 archive",
        metadata.get("versions", {}).get("v1.0.0")
        == "versions/v1.0.0-absolute-lab-calibration.eel",
    ))
    results.append(require(
        "metadata feature list includes core DRAGON features",
        all(f in metadata.get("features", []) for f in (
            "record-pre-emphasis-de-emphasis-pair",
            "iec-70us-type-iv-playback-corner",
            "linked-tape-compression",
            "asymmetric-tanh-saturation",
            "three-component-wow-flutter",
            "inter-channel-tape-bleed",
            "tpdf-hiss",
        )),
    ))
    results.append(require(
        "archive/current byte identity",
        ARCHIVE.exists() and ARCHIVE.read_bytes() == DSP.read_bytes(),
    ))
    return results


def check_numerics() -> list[bool]:
    results: list[bool] = []

    wrms = computed_wrms_pct()
    results.append(require(
        "combined W&F deviation is sub-0.02% WRMS (Nakamichi class)",
        wrms < 0.02,
        f"computed {wrms:.4f}% WRMS at depth 1.0",
    ))

    ok, lo, hi = wf_offset_bounds()
    results.append(require(
        "W&F read offset stays inside (0, 64) at all depths/rates",
        ok,
        f"offset range [{lo:.2f}, {hi:.2f}] samples",
    ))

    lat_ok = True
    for fs in SAMPLE_RATES:
        first, _ = impulse_latency(fs)
        if first != 12:
            lat_ok = False
    results.append(require(
        "impulse latency is exactly the 12-sample W&F base",
        lat_ok,
        "first nonzero output at sample 12 (44.1k/48k)",
    ))

    stress_ok = True
    peak = 0.0
    for fs in SAMPLE_RATES:
        ok, pk = stress_probe(fs)
        stress_ok = stress_ok and ok
        peak = max(peak, pk)
    results.append(require(
        "stress probe: no NaN/Inf, output bounded",
        stress_ok and peak <= CLAMP + 1e-9,
        f"peak out={peak:.5f} (clamp {CLAMP})",
    ))

    stack_ok = True
    for fs in SAMPLE_RATES:
        ok, pk = corner_case_stack(fs)
        stack_ok = stack_ok and ok
    results.append(require(
        "worst legal slider stack stays within hard clamp",
        stack_ok,
        "drive 10 + bump 4 + trim +12 dB, full-scale input",
    ))

    corr_ok, corr = hiss_uncorrelated()
    results.append(require(
        "L/R hiss draws are uncorrelated (diffuse, non-localizing)",
        corr_ok,
        f"|corr| = {abs(corr):.4f}",
    ))

    decay_ok = True
    for fs in SAMPLE_RATES:
        tail = impulse_decay(fs)
        if tail > 1e-3:
            decay_ok = False
    results.append(require(
        "impulse response decays to hiss floor (no self-oscillation)",
        decay_ok,
        "tail < 1e-3 in the 200-300 ms window (7 Hz DC blockers ring ~200 ms by design)",
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
    print(f"\nDRAGON v1.0.0 audit: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
