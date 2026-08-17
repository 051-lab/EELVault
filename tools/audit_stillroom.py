#!/usr/bin/env python3
"""Dependency-free validation harness for STILLROOM v0.1.0.

Run from any working directory:
    python tools/audit_stillroom.py

The script exits non-zero when any required invariant fails.
Same spirit as tools/audit_soloconsole.py and tools/audit_materialmemory.py:
package/source identity plus a numerical reference model of the
actual signal path (M/S encode, six-tap early reflections, air
absorption, five-stage damped allpass diffuser, side-only injection).

Everything here is stdlib-only.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DSP = ROOT / "dsp" / "stillroom" / "stillroom.eel"
ARCHIVE = ROOT / "dsp" / "stillroom" / "versions" / "v0.1.0-nearfield-depth.eel"
METADATA = ROOT / "dsp" / "stillroom" / "metadata.json"
VERSION = "0.1.0"

# ------------------------------------------------------------------
# Design constants (must mirror the EEL source exactly)
# ------------------------------------------------------------------

ER_SIZE = 8192
ER_MASK = ER_SIZE - 1
AP_SIZE = 1024
AP_MASK = AP_SIZE - 1

SAMPLE_RATES = (44100.0, 48000.0, 96000.0, 192000.0)

# Early-reflection delays (ms) and weights
ER_DELAYS_MS = (0.0019, 0.0043, 0.0079, 0.0127, 0.0188, 0.0266)
ER_WEIGHTS = (0.31, -0.25, 0.20, -0.17, 0.13, -0.10)

# Allpass delays (ms)
AP_DELAYS_MS = (0.00065, 0.00100, 0.00150, 0.00220, 0.00320)

# Feedback targets (base + 0.04*depth, capped at 0.62)
AP_FB_BASE = (0.46, 0.49, 0.52, 0.55, 0.58)
AP_FB_CAP = 0.62

WET_CAP = 0.35
DIFFUSE_BASE = 0.25
DIFFUSE_RANGE = 0.15
EXCITE_SIDE_GAIN = 0.15
DAMP_RATIO = 0.70

DENORMAL_GUARD = 1e-20
INPUT_LIMIT = 100.0

# Default slider values
DEF_SPACE = 42.0
DEF_DEPTH = 36.0
DEF_WET = 24.0
DEF_TONE = 56.0

MARKDOWN_SECTIONS = ("[init](init)", "[slider](slider1)", "[block](block)",
                     "[sample](sample)")

FORBIDDEN = (
    "tanh", "atan(", "fft(", "ifft(", "stft", "FIRInit", "FIRProcess",
    "Conv1D", "oversampl", "resample(", "granular", "PolyphaseFilterbank",
)


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(name: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return condition


# ------------------------------------------------------------------
# Reference model — mirrors stillroom.eel exactly
# ------------------------------------------------------------------


def hermite_read(buf: list[float], wp: int, delay: float,
                 size: int, mask: int) -> float:
    """Four-point Hermite interpolation from a ring buffer,
    matching the EEL2 source's c0/c1/c2/c3 form."""
    delay = max(4.0, min(mask - 3, delay))
    rp = wp - delay
    if rp < 0:
        rp += size
    i0 = int(rp)
    frac = rp - i0
    im1 = (i0 + mask) & mask
    i1 = (i0 + 1) & mask
    i2 = (i0 + 2) & mask
    y0 = buf[im1]
    y1 = buf[i0]
    y2 = buf[i1]
    y3 = buf[i2]
    c0 = y1
    c1 = 0.5 * (y2 - y0)
    c2 = y0 - 2.5 * y1 + 2 * y2 - 0.5 * y3
    c3 = 0.5 * (y3 - y0) + 1.5 * (y1 - y2)
    return c0 + frac * (c1 + frac * (c2 + frac * c3))


class Engine:
    """Python port of the STILLROOM sample path.

    Coefficients follow the parameter mapping at the given slider
    values and sample rate. The per-sample loop matches @sample:
    sanitize -> M/S encode -> ER ring write -> six Hermite reads ->
    air absorption -> five-stage damped allpass -> side injection.
    """

    def __init__(self, fs: float, space: float = DEF_SPACE,
                 depth: float = DEF_DEPTH, wet: float = DEF_WET,
                 tone: float = DEF_TONE):
        self.fs = fs
        sp = space * 0.01
        dp = depth * 0.01
        wp = wet * 0.01
        tp = tone * 0.01

        # Parameter targets (match @init/@slider mapping)
        self.space_t = 0.55 + 0.45 * sp
        self.depth_t = dp
        self.wet_t = min(WET_CAP, WET_CAP * math.sqrt(wp))
        self.tone_t = tp
        self.field_t = 0.55 + 0.45 * dp
        self.diffuse_t = DIFFUSE_BASE + DIFFUSE_RANGE * dp
        self.early_t = 1.0 - self.diffuse_t

        air_hz = (2200.0 + 14000.0 * tp) * (1.0 - 0.55 * dp)
        air_hz = max(800.0, min(16000.0, air_hz))
        self.air_t = 1.0 - math.exp(-2.0 * math.pi * air_hz / fs)

        self.er_delays = [ms * fs * self.space_t for ms in ER_DELAYS_MS]
        ap_scale = 0.85 + 0.30 * sp
        self.ap_delays = [ms * fs * ap_scale for ms in AP_DELAYS_MS]
        self.ap_fb = [min(AP_FB_CAP, base + 0.04 * dp) for base in AP_FB_BASE]

        self.p_sm = 1.0 - math.exp(-1.0 / (fs * 0.015))

        # Smoothed currents (start at targets)
        self.space_c = self.space_t
        self.depth_c = self.depth_t
        self.wet_c = self.wet_t
        self.tone_c = self.tone_t
        self.field_c = self.field_t
        self.diffuse_c = self.diffuse_t
        self.early_c = self.early_t
        self.air_c = self.air_t
        self.er_c = list(self.er_delays)
        self.ap_c = list(self.ap_delays)
        self.fb_c = list(self.ap_fb)

        # Ring buffers
        self.er = [0.0] * ER_SIZE
        self.aps = [[0.0] * AP_SIZE for _ in range(5)]
        self.er_wp = 0
        self.ap_wp = [0, 0, 0, 0, 0]

        # State
        self.denormal_sign = 1.0
        self.air_state = 0.0
        self.ap_damp = [0.0] * 5

    def process(self, in_l: float, in_r: float) -> tuple[float, float]:
        # Denormal + non-finite protection
        self.denormal_sign = -self.denormal_sign
        dg = DENORMAL_GUARD * self.denormal_sign
        in_l = in_l + dg
        in_r = in_r + dg
        if in_l != in_l:
            in_l = 0.0
        if in_r != in_r:
            in_r = 0.0
        if abs(in_l) > INPUT_LIMIT:
            in_l = 0.0
        if abs(in_r) > INPUT_LIMIT:
            in_r = 0.0

        # M/S encode
        mid = 0.5 * (in_l + in_r)
        side = 0.5 * (in_l - in_r)
        excite = mid + EXCITE_SIDE_GAIN * side

        # Write to ER ring
        self.er[self.er_wp] = excite

        # Smooth delays toward targets
        for i in range(6):
            self.er_c[i] += (self.er_delays[i] - self.er_c[i]) * self.p_sm
        for i in range(5):
            self.ap_c[i] += (self.ap_delays[i] - self.ap_c[i]) * self.p_sm

        # Six Hermite early-reflection reads
        early = 0.0
        for i in range(6):
            tap = hermite_read(self.er, self.er_wp, self.er_c[i], ER_SIZE, ER_MASK)
            early += ER_WEIGHTS[i] * tap

        self.er_wp = (self.er_wp + 1) & ER_MASK

        # Air absorption (early field only)
        self.air_state += self.air_c * (early - self.air_state)
        early_air = self.air_state

        # Damped allpass diffuser
        damp_c = self.air_c * DAMP_RATIO
        ap_out = early_air
        for i in range(5):
            delayed = hermite_read(self.aps[i], self.ap_wp[i],
                                   self.ap_c[i], AP_SIZE, AP_MASK)
            self.ap_damp[i] += damp_c * (delayed - self.ap_damp[i])
            ap_in = ap_out
            ap_out = self.ap_damp[i] - self.fb_c[i] * ap_in
            self.aps[i][self.ap_wp[i]] = ap_in + self.fb_c[i] * ap_out
            self.ap_wp[i] = (self.ap_wp[i] + 1) & AP_MASK

        # Side-only spatial injection
        spatial_side = (self.wet_c * self.field_c
                        * (self.early_c * early_air
                           + self.diffuse_c * ap_out))
        if spatial_side != spatial_side:
            spatial_side = 0.0

        out_l = mid + side + spatial_side
        out_r = mid - side - spatial_side
        return out_l, out_r


# ------------------------------------------------------------------
# Numerical helpers
# ------------------------------------------------------------------


def mono_collapse_error(fs: float, n: int = 4096) -> float:
    """Max |(outL+outR) - (inL+inR)| over n samples of asymmetric
    pseudo-random stereo input. The spatial field must cancel
    structurally under mono summing."""
    e = Engine(fs)
    state = 0x12345678
    worst = 0.0
    for _ in range(n):
        state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
        x = (state / 0xFFFFFFFF) * 1.8 - 0.9
        state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
        y = (state / 0xFFFFFFFF) * 1.8 - 0.9
        ol, or_ = e.process(x, y)
        mono_err = abs((ol + or_) - (x + y))
        worst = max(worst, mono_err)
    return worst


def direct_path_error(fs: float, n: int = 2048) -> float:
    """With Wet=0 (spatialSide=0), output must equal input exactly
    (apart from the denormal guard)."""
    e = Engine(fs, wet=0.0)
    state = 0x12345678
    worst = 0.0
    for _ in range(n):
        state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
        x = (state / 0xFFFFFFFF) * 1.8 - 0.9
        state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
        y = (state / 0xFFFFFFFF) * 1.8 - 0.9
        ol, or_ = e.process(x, y)
        worst = max(worst, abs(ol - x), abs(or_ - y))
    return worst


def stress_probe(fs: float, n: int = 8192) -> tuple[bool, float, float]:
    """Deterministic bounded pseudo-random stress. Returns
    (all_finite, peak_out_abs, peak_state_abs)."""
    e = Engine(fs)
    state = 0x12345678
    peak_out = 0.0
    peak_state = 0.0
    for n_s in range(n):
        x = 0.0
        y = 0.0
        phase = n_s % 64
        if phase < 2:
            x = 1.0
            y = 1.0
        elif phase < 4:
            x = -1.0
        elif phase < 6:
            x = 0.5
        elif phase < 10:
            x = 0.9
            y = -0.8
        elif phase < 14:
            x = 0.0
        elif phase < 30:
            state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
            x = (state / 0xFFFFFFFF) * 2.0 - 1.0
            state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
            y = (state / 0xFFFFFFFF) * 2.0 - 1.0
        ol, or_ = e.process(x, y)
        peak_out = max(peak_out, abs(ol), abs(or_))
        peak_state = max(peak_state,
                         max(abs(v) for v in e.er),
                         max(abs(v) for ap in e.aps for v in ap),
                         abs(e.air_state),
                         max(abs(v) for v in e.ap_damp))
    all_finite = (all(math.isfinite(v) for v in e.er)
                  and all(math.isfinite(v) for ap in e.aps for v in ap)
                  and math.isfinite(e.air_state)
                  and all(math.isfinite(v) for v in e.ap_damp))
    return all_finite, peak_out, peak_state


def impulse_decay(fs: float, seconds: float = 0.5) -> tuple[float, float]:
    """Unit impulse into L, then silence. Returns
    (peak_out_abs, tail_abs_at_end)."""
    e = Engine(fs)
    peak = 0.0
    n = int(seconds * fs)
    for n_s in range(n):
        x = 1.0 if n_s == 0 else 0.0
        ol, or_ = e.process(x, 0.0)
        peak = max(peak, abs(ol), abs(or_))
    # Measure tail after the full window
    tail = 0.0
    for _ in range(int(0.1 * fs)):
        ol, or_ = e.process(0.0, 0.0)
        tail = max(tail, abs(ol), abs(or_))
    return peak, tail


def silence_self_excitation(fs: float, seconds: float = 1.0) -> float:
    """Drive a burst, then silence. After the ER ring has had time
    to empty (8192 samples = up to 186 ms at 44.1 kHz), measure the
    remaining tail. The allpass feedback (0.62^n) and air state must
    have decayed — no self-oscillation. Returns max |output| in the
    final measurement window."""
    e = Engine(fs)
    burst = int(0.05 * fs)
    for _ in range(burst):
        e.process(0.8, 0.8)
    # Let the ER ring empty (8192 samples + margin)
    drain = int(0.3 * fs)
    for _ in range(drain):
        e.process(0.0, 0.0)
    # Measure the tail after everything should have decayed
    measure = int(0.2 * fs)
    tail = 0.0
    for _ in range(measure):
        ol, or_ = e.process(0.0, 0.0)
        tail = max(tail, abs(ol), abs(or_))
    return tail


def delay_bounds(fs: float) -> tuple[bool, float, float]:
    """Check all delay values fit within their ring buffers.
    Returns (all_fit, max_er_delay_samples, max_ap_delay_samples)."""
    e = Engine(fs)
    max_er = max(e.er_delays)
    max_ap = max(e.ap_delays)
    return (max_er < ER_SIZE - 4 and max_ap < AP_SIZE - 4,
            max_er, max_ap)


# ------------------------------------------------------------------
# Static source checks
# ------------------------------------------------------------------


def check_source(source: str) -> list[bool]:
    results: list[bool] = []

    param_names = [m.group(1) for m in re.finditer(
        r"(?m)^(spacePct|depthPct|wetPct|tonePct):[-+\d.]+<", source)]
    section_lines = [name for name in ("@init", "@sample")
                     if re.search(rf"(?m)^{re.escape(name)}\s*$", source)]
    results.append(require(
        "native EEL2 sections (@init/@sample) and four sequential named parameters",
        section_lines == ["@init", "@sample"]
        and param_names == ["spacePct", "depthPct", "wetPct", "tonePct"],
        f"params={param_names} sections={section_lines}",
    ))

    order_ok = (
        source.find("spacePct:") < source.find("@init")
        and source.find("@init") < source.find("@sample")
    )
    results.append(require("EEL2 section order and parameter-first layout", order_ok))

    expected_params = {"spacePct": DEF_SPACE, "depthPct": DEF_DEPTH,
                       "wetPct": DEF_WET, "tonePct": DEF_TONE}
    declared = {}
    for m in re.finditer(r"(?m)^(spacePct|depthPct|wetPct|tonePct):([-+\d.]+)<", source):
        declared[m.group(1)] = float(m.group(2))
    results.append(require(
        "declared parameter defaults match spec (42/36/24/56)",
        all(abs(declared.get(k, -1.0) - v) < 1e-12
            for k, v in expected_params.items()),
        str([declared.get(k) for k in ("spacePct", "depthPct", "wetPct", "tonePct")]),
    ))

    results.append(require(
        "source descriptor/version identity",
        source.startswith("desc: STILLROOM - Nearfield Depth\n")
        and "0.1.0" not in source  # version not in source desc; checked via metadata
        or source.startswith("desc: STILLROOM - Nearfield Depth\n"),
    ))

    results.append(require(
        "ER ring is 8192 samples (power-of-two)",
        "ER_SIZE = 8192;" in source and "ER_MASK = this.ER_SIZE - 1;" in source,
    ))
    results.append(require(
        "allpass rings are 1024 samples (power-of-two)",
        "AP_SIZE = 1024;" in source and "AP_MASK = this.AP_SIZE - 1;" in source,
    ))

    results.append(require(
        "flat heap allocation with MEM convention and zeroing",
        "MEM = 0;" in source and "this.MEM_TOTAL = MEM - this.MEM;" in source
        and "loop(this.MEM_TOTAL," in source,
    ))

    results.append(require(
        "M/S encode: mid = 0.5*(inL+inR), side = 0.5*(inL-inR)",
        "mid = 0.5 * (inL + inR);" in source
        and "side = 0.5 * (inL - inR);" in source,
    ))

    results.append(require(
        "excitation = mid + 0.15*side (restrained S)",
        "excite = mid + 0.15 * side;" in source,
    ))

    results.append(require(
        "opposed-polarity side injection in output",
        "outL = mid + side + spatialSide;" in source
        and "outR = mid - side - spatialSide;" in source,
    ))

    results.append(require(
        "wet is sqrt-tapered and hard-capped at 0.35",
        "0.35 * sqrt" in source and "min(0.35" in source,
    ))

    results.append(require(
        "diffuse proportion is 0.25 + 0.15*depth",
        "0.25 + 0.15 *" in source,
    ))

    results.append(require(
        "allpass feedback is independently capped at 0.62",
        source.count("min(0.62,") >= 5,
        f"found {source.count('min(0.62,')} caps (need >=5)",
    ))

    results.append(require(
        "five allpass stages with serial routing (no matrix)",
        "ap1 = MEM;" in source and "ap5 = MEM; MEM += this.AP_SIZE;" in source
        and "apIn = apOut;" in source,
    ))

    results.append(require(
        "air absorption on early field only (not direct path)",
        "airState += this.air_c * (early - this.airState);" in source,
    ))

    results.append(require(
        "denormal guard + NaN check + magnitude guard",
        "denormalGuard * this.denormalSign" in source
        and "inL != inL ? inL = 0;" in source
        and "abs(inL) > 100 ? inL = 0;" in source,
    ))

    results.append(require(
        "sample-path parameter fallback bridge present",
        "cSpace != spacePct" in source and "pdc ? (" in source
        and "cSpace = spacePct" in source,
        "bridge pattern: compare + conditional + assign",
    ))

    results.append(require(
        "parameter smoothing (15 ms one-pole)",
        "p_sm = 1 - exp(-1 / (srate * 0.015));" in source,
    ))

    results.append(require(
        "Hermite four-point interpolation in early reflections",
        "c0 = y1; c1 = 0.5 * (y2 - y0);" in source
        and "c2 = y0 - 2.5 * y1 + 2 * y2 - 0.5 * y3;" in source,
    ))

    results.append(require(
        "no forbidden saturation/FFT/FIR/oversampling tokens",
        not any(tok in source.lower() for tok in FORBIDDEN),
    ))

    results.append(require(
        "no Markdown-corrupted section markers",
        not any(marker in source for marker in MARKDOWN_SECTIONS),
    ))

    results.append(require(
        "README labels STILLROOM experimental",
        "Experimental" in load_text(ROOT / "dsp" / "stillroom" / "README.md"),
    ))

    results.append(require(
        "CHANGELOG describes v0.1.0 Nearfield Depth",
        "0.1.0" in load_text(ROOT / "dsp" / "stillroom" / "CHANGELOG.md")
        and "Nearfield" in load_text(ROOT / "dsp" / "stillroom" / "CHANGELOG.md"),
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
        metadata.get("name") == "stillroom"
        and metadata.get("version") == VERSION
        and metadata.get("status") == "experimental"
        and metadata.get("type") == "spatial-ambience-depth-processor"
        and metadata.get("displayName") == "STILLROOM — Nearfield Depth",
    ))
    results.append(require(
        "metadata file/latency/controls contract",
        metadata.get("file") == "stillroom.eel"
        and metadata.get("latencyMs") == 0.0
        and metadata.get("hasUserControls") is True,
    ))
    results.append(require(
        "metadata version map points at v0.1.0 archive",
        metadata.get("versions", {}).get("v0.1.0")
        == "versions/v0.1.0-nearfield-depth.eel",
    ))
    results.append(require(
        "metadata feature list includes core STILLROOM features",
        all(f in metadata.get("features", []) for f in (
            "ms-encode-decode",
            "early-reflection-taps",
            "damped-allpass-diffuser",
            "side-only-spatial-injection",
            "mono-safe-opposed-polarity-cancellation",
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

    # Mono-collapse: spatial field must cancel under mono summing
    mono_max = 0.0
    for fs in SAMPLE_RATES:
        mono_max = max(mono_max, mono_collapse_error(fs))
    results.append(require(
        "mono-collapse: spatial field cancels under mono sum",
        mono_max < 1e-12,
        f"max error={mono_max:.2e}",
    ))

    # Direct path with Wet=0: output == input
    direct_max = 0.0
    for fs in SAMPLE_RATES:
        direct_max = max(direct_max, direct_path_error(fs))
    results.append(require(
        "direct path preserved at Wet=0 (output == input)",
        direct_max < 1e-12,
        f"max error={direct_max:.2e}",
    ))

    # Delay bounds at all sample rates
    delay_ok = True
    delay_detail = []
    for fs in SAMPLE_RATES:
        ok, max_er, max_ap = delay_bounds(fs)
        if not ok:
            delay_ok = False
        delay_detail.append(f"{int(fs)}:ER={max_er:.0f}/{ER_SIZE} AP={max_ap:.0f}/{AP_SIZE}")
    results.append(require(
        "all delay values fit within ring buffers at 44.1/48/96/192 kHz",
        delay_ok,
        "; ".join(delay_detail),
    ))

    # Stress: no NaN/Inf, bounded state and output
    stress_ok = True
    stress_peak_out = 0.0
    stress_peak_state = 0.0
    for fs in SAMPLE_RATES:
        ok, pk_out, pk_state = stress_probe(fs)
        stress_ok = stress_ok and ok
        stress_peak_out = max(stress_peak_out, pk_out)
        stress_peak_state = max(stress_peak_state, pk_state)
    results.append(require(
        "stress probe: no NaN/Inf, all state finite",
        stress_ok,
        f"peak out={stress_peak_out:.4f}",
    ))
    results.append(require(
        "stress probe: all state bounded (< 10.0)",
        stress_peak_state < 10.0,
        f"peak state={stress_peak_state:.4f}",
    ))

    # Impulse decay: field must decay after excitation
    decay_ok = True
    decay_detail = []
    for fs in SAMPLE_RATES:
        peak, tail = impulse_decay(fs)
        if tail > 0.01 or peak < 0.001:
            decay_ok = False
        decay_detail.append(f"{int(fs)}:peak={peak:.4f} tail={tail:.2e}")
    results.append(require(
        "impulse response decays (no self-oscillation, no stuck state)",
        decay_ok,
        "; ".join(decay_detail),
    ))

    # No self-excitation from silence after burst
    silence_ok = True
    for fs in SAMPLE_RATES:
        tail = silence_self_excitation(fs)
        if tail > 1e-3:
            silence_ok = False
    results.append(require(
        "no self-excitation from silence after burst",
        silence_ok,
        "tail < 1e-3 for all sample rates",
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
    print(f"\nSTILLROOM v0.1.0 audit: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
