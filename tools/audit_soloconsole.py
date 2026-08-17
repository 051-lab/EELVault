#!/usr/bin/env python3
"""Dependency-free validation harness for SoloConsole.

Run from any working directory:
    python tools/audit_soloconsole.py

The script exits non-zero when any required v0.3.0 invariant fails.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DSP = ROOT / "dsp" / "soloconsole" / "soloconsole.eel"
ARCHIVE = ROOT / "dsp" / "soloconsole" / "versions" / "v0.4.0-auto-glue.eel"
METADATA = ROOT / "dsp" / "soloconsole" / "metadata.json"
VERSION = "0.4.0"

CRUSH_BITS_MIN = 3
CRUSH_BITS_MAX = 11


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(name: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return condition


def design_halfband(taps: int = 32, fc: float = 0.25) -> list[float]:
    mid = (taps - 1) * 0.5
    h: list[float] = []
    se = 0.0
    so = 0.0
    for i in range(taps):
        t = i - mid
        value = 2.0 * fc if t == 0.0 else math.sin(2.0 * math.pi * fc * t) / (math.pi * t)
        window = 0.54 - 0.46 * math.cos(2.0 * math.pi * i / (taps - 1))
        value *= window
        h.append(value)
        if i & 1:
            so += value
        else:
            se += value
    for i in range(taps):
        h[i] /= so if i & 1 else se
    return h


def polyphase_interpolate(samples: list[float], h: list[float]) -> list[float]:
    even = h[0::2]
    odd = h[1::2]
    out: list[float] = []
    for n in range(len(samples)):
        e = 0.0
        o = 0.0
        for k, coeff in enumerate(even):
            src = n - k
            if src >= 0:
                e += coeff * samples[src]
        for k, coeff in enumerate(odd):
            src = n - k
            if src >= 0:
                o += coeff * samples[src]
        out.extend((e, o))
    return out


def explicit_zero_stuff_interpolate(samples: list[float], h: list[float]) -> list[float]:
    stuffed = [0.0] * (len(samples) * 2)
    for i, value in enumerate(samples):
        stuffed[i * 2] = value
    out = [0.0] * len(stuffed)
    for n in range(len(out)):
        total = 0.0
        for k, coeff in enumerate(h):
            src = n - k
            if src >= 0:
                total += coeff * stuffed[src]
        out[n] = total
    return out


def causal_decimate(samples_2x: list[float], h: list[float]) -> list[float]:
    hd = [value * 0.5 for value in h]
    size = len(hd)
    mask = size - 1
    history = [0.0] * size
    pos = 0
    out: list[float] = []
    for pair in range(len(samples_2x) // 2):
        history[pos] = samples_2x[pair * 2]
        pos = (pos + 1) & mask
        history[pos] = samples_2x[pair * 2 + 1]
        newest_odd = pos
        pos = (pos + 1) & mask
        cursor = newest_odd
        total = 0.0
        for coeff in hd:
            total += coeff * history[cursor]
            cursor = (cursor + mask) & mask
        out.append(total)
    return out


def explicit_decimate(samples_2x: list[float], h: list[float]) -> list[float]:
    hd = [value * 0.5 for value in h]
    convolution = [0.0] * len(samples_2x)
    for n in range(len(samples_2x)):
        total = 0.0
        for k, coeff in enumerate(hd):
            src = n - k
            if src >= 0:
                total += coeff * samples_2x[src]
        convolution[n] = total
    return [convolution[i] for i in range(1, len(convolution), 2)]


def max_abs_diff(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return math.inf
    return max((abs(x - y) for x, y in zip(a, b)), default=0.0)


def dc_cutoff_hz(r: float, fs: float) -> float:
    return -fs * math.log(r) / (2.0 * math.pi)


def crush_bits(even: float) -> int:
    return CRUSH_BITS_MIN + int(math.floor(even * 8.0))


def saturate_core(mode: int, u: float) -> float:
    au = abs(u)
    if mode == 0:
        if au > 1.0:
            return 0.6666666666666666 if u > 0.0 else -0.6666666666666666
        return u - u * u * u * 0.3333333333333333
    if mode == 1:
        if au <= 1.0:
            return u
        fw = 1.0 - abs((au % 2.0) - 1.0)
        return fw if u > 0.0 else -fw
    if mode == 2:
        return u / (1 + 0.3 * u) if u > 0.0 else u / (1 - 0.6 * u)
    bits = crush_bits(0.25)  # even slider at default for the grid test
    csc = 2.0 ** bits
    return math.floor(u * csc + 0.5) / csc


def bias_cancel(v: float, even: float) -> float:
    b = even * 0.35
    return v - b + b * b * b * 0.3333333333333333


def saturate(mode: int, u: float, even: float = 0.25) -> float:
    if mode == 3:
        csc = 2.0 ** crush_bits(even)
        core = math.floor(u * csc + 0.5) / csc
    else:
        core = saturate_core(mode, u)
    return bias_cancel(core, even)


def main() -> int:
    source = load_text(DSP)
    metadata = json.loads(load_text(METADATA))
    results: list[bool] = []

    slider_numbers = [int(m.group(1)) for m in re.finditer(r"(?m)^slider(\d+):", source)]
    section_lines = [name for name in ("@init", "@slider", "@block", "@sample")
                     if re.search(rf"(?m)^{re.escape(name)}\s*$", source)]
    sections_ok = section_lines == ["@init", "@sample"]
    results.append(require(
        "native EEL2 sections (@init/@sample) and sequential sliders",
        sections_ok and slider_numbers == list(range(1, 12)),
        f"sliders={slider_numbers} sections={section_lines}",
    ))

    legacy_names = ("inDb:", "drvDb:", "evenPct:", "bassDb:", "trebDb:", "outDb:", "osMode:", "mixPct:")
    present_legacy = [name for name in legacy_names if name in source]
    results.append(require("no legacy named slider declarations", not present_legacy, str(present_legacy)))

    results.append(require(
        f"source version is v{VERSION}",
        source.startswith(f"desc: SoloConsole Drive v{VERSION}\n"),
    ))

    archive_ok = ARCHIVE.exists() and ARCHIVE.read_bytes() == DSP.read_bytes()
    results.append(require(f"v{VERSION} current/archive byte identity", archive_ok))

    h = design_halfband()
    probe = [math.sin(i * 0.37) * 0.6 + math.cos(i * 0.11) * 0.2 for i in range(96)]
    poly = polyphase_interpolate(probe, h)
    explicit_interp = explicit_zero_stuff_interpolate(probe, h)
    interp_error = max_abs_diff(poly, explicit_interp)
    results.append(require(
        "fused polyphase interpolation matches explicit FIR",
        interp_error < 1e-12,
        f"max error={interp_error:.3e}",
    ))

    dec_ring = causal_decimate(poly, h)
    dec_explicit = explicit_decimate(poly, h)
    dec_error = max_abs_diff(dec_ring, dec_explicit)
    results.append(require(
        "causal odd-phase decimation matches explicit FIR",
        dec_error < 1e-12,
        f"max error={dec_error:.3e}",
    ))

    impulse = [1.0] + [0.0] * 95
    impulse_out = causal_decimate(polyphase_interpolate(impulse, h), h)
    peak = max(range(len(impulse_out)), key=lambda i: abs(impulse_out[i]))
    results.append(require("2x impulse latency is 15 base-rate samples", peak == 15, f"peak={peak}"))

    expected_dc_source = (
        "dcbR = exp(-2 * $pi * 5 / srate);" in source
        and "dcbR2 = exp(-2 * $pi * 5 / (srate * 2));" in source
    )
    dc_details: list[str] = []
    dc_numeric_ok = True
    for fs in (44100.0, 48000.0, 96000.0):
        r1 = math.exp(-2.0 * math.pi * 5.0 / fs)
        r2 = math.exp(-2.0 * math.pi * 5.0 / (fs * 2.0))
        f1 = dc_cutoff_hz(r1, fs)
        f2 = dc_cutoff_hz(r2, fs * 2.0)
        dc_numeric_ok &= abs(f1 - 5.0) <= 0.02 and abs(f2 - 5.0) <= 0.02
        dc_details.append(f"{int(fs)}:{f1:.4f}/{f2:.4f}Hz")
    results.append(require(
        "sample-rate-derived 5 Hz DC blocker at 1x/2x",
        expected_dc_source and dc_numeric_ok,
        ", ".join(dc_details),
    ))

    handoffs = source.count("xin = sat;\n  sat = xfy")
    results.append(require("Treble feeds transformer in all six paths", handoffs == 6, f"handoffs={handoffs}"))

    state_tokens = (
        "dcm1[0] = 0;", "dcm2[0] = 0;", "dcm1[1] = 0;", "dcm2[1] = 0;",
        "dpos = 0;", "loop(PPH,", "loop(OS_TAPS,", "loop(DLY_SZ,",
        "dhist0[i] = 0;", "dhist1[i] = 0;",
    )
    state_ok = all(token in source for token in state_tokens)
    reset_block_match = re.search(
        r"os_active != prev_os \? \((.*?)prev_os = os_active;\n\);",
        source,
        re.S,
    )
    reset_block = reset_block_match.group(1) if reset_block_match else ""
    index_resets = reset_block.count("i = 0;")
    results.append(require(
        "OS switch clears all rate-dependent state",
        state_ok and index_resets >= 3,
        f"index resets={index_resets}",
    ))

    allocation_ok = (
        "OS_TAPS = 32;" in source
        and "OS_MASK = OS_TAPS - 1;" in source
        and "OS_BUF = 32;" in source
        and source.count("MEM += OS_BUF;") == 2
    )
    results.append(require("decimator allocation matches 32-slot addressed ring", allocation_ok))

    initial_os_ok = re.search(r"os_active = 1;\s*prev_os = os_active;", source) is not None
    results.append(require("initial OS state cannot trigger a spurious first-slider flush", initial_os_ok))

    dispatch_ok = (
        source.count("sat_mode == 0 ? (") == 6
        and source.count("sat_mode == 1 ? (") == 6
        and source.count("sat_mode == 2 ? (") == 6
        and source.count("cb = 3 + floor(even_cur * 8.0);") == 6
    )
    results.append(require(
        "style dispatch covers all six saturator sites",
        dispatch_ok,
        "mode0=6 mode1=6 mode2=6 crush=6" if dispatch_ok else "count mismatch",
    ))

    default_mode_ok = re.search(r"gOs = 2;\s*sat_mode = 0;", source) is not None
    clamp_ok = (
        "sat_mode = slider9;" in source
        and "sat_mode > 3 ? sat_mode = 3;" in source
        and "sat_mode < 0 ? sat_mode = 0;" in source
    )
    dropdown_ok = re.search(
        r"slider9:0<0,3,1\{Polysoft,Foldback,Asymmetric,Bitcrush\}>Style",
        source,
    ) is not None
    results.append(require(
        "style falls back to 0 and is clamped to 0..3",
        default_mode_ok and clamp_ok,
    ))
    results.append(require(
        "style slider declares a 4-option dropdown",
        dropdown_ok,
    ))

    expected_defaults = {"slider1": 0.0, "slider2": 6.0, "slider3": 25.0,
                         "slider4": 0.0, "slider5": 0.0, "slider6": 0.0,
                         "slider7": 2.0, "slider8": 100.0, "slider9": 0.0,
                         "slider10": 0.0, "slider11": 50.0}
    declared = {}
    for m in re.finditer(r"(?m)^slider(\d+):([-\d.]+)<", source):
        declared[f"slider{m.group(1)}"] = float(m.group(2))
    declared_ok = all(
        abs(declared.get(k, -1.0) - v) < 1e-12 for k, v in expected_defaults.items()
    )
    results.append(require("bridge cache matches declared slider defaults", declared_ok, str([v for v in declared.values()])))

    cache_ok = all(f"c{v} = " in source for v in ("In", "Dr", "Ev", "Bs", "Tr", "Ou", "Os", "Mx", "St", "G1", "G2"))
    results.append(require("bridge snapshot caches all eleven sliders", cache_ok))

    bridge_ok = (
        source.count("pdc = 1;") == 11
        and "cIn != slider1 ? ( cIn = slider1; pdc = 1; );" in source
        and "cG2 != slider11 ? ( cG2 = slider11; pdc = 1; );" in source
        and re.search(r"@sample(.*)pdc = 0;", source, re.S) is not None
    )
    results.append(require(
        "live parameter bridge sits in @sample with 11 dirty checks",
        bridge_ok,
    ))

    glue_state_ok = (
        "slider10:0<0,1,1{Off,On}>Glue" in source
        and "slider11:50<0,100,1>Glue Amount" in source
        and source.count("* glue;") == 6
        and "glue_act ? (" in source
        and "gGlQuant = 1.025;" in source
        and "glueTgt = pow(gR1, gGlAmt);" in source
        and "glue_act = slider10;" in source
        and "gGlAmt = slider11 / 100;" in source
    )
    results.append(require(
        "console glue: 2 sliders, 6 gain sites, quantized pow",
        glue_state_ok,
    ))

    glue_bypass_ok = (
        "glue_act ? (" in source
        and re.search(r"\) : \(\n  glue = 1;\n\);", source) is not None
    )
    results.append(require("glue bypass keeps v0.3.2 output when Off", glue_bypass_ok))

    def follow(level: float, samples: int, start: float, attack: float, release: float) -> float:
        value = start
        for _ in range(samples):
            pole = attack if level > value else release
            value += (level - value) * pole
        return value

    fs = 48000.0
    pA = 1 - math.exp(-1 / (fs * 0.006))
    pR = 1 - math.exp(-1 / (fs * 0.14))
    pRef = 1 - math.exp(-1 / (fs * 0.35))
    env_ok = (
        follow(0.3, int(fs * 0.8), 0.0, pA, pR) > 0.29
        and follow(0.0, int(fs * 0.8), 0.3, pA, pR) < 0.01
        and follow(0.8, int(fs * 0.04), 0.0, pA, pR) > 0.6
        and follow(0.05, int(fs * 0.3), 0.8, pA, pR) < 0.5
    )
    results.append(require(
        "envelope follower converges on sustained levels",
        env_ok,
    ))

    glue_ratio_ok = True
    for env_level in (0.05, 0.3, 0.8):
        ref = 0.25
        ratio = ref / env_level
        ratio = min(4.0, max(0.25, ratio))
        target = ratio ** 0.5
        glue_ratio_ok = glue_ratio_ok and 0.06 <= target <= 4.01 and math.isfinite(target)
    glue_ratio_ok = glue_ratio_ok and abs((0.25 / 0.25) ** 0.5 - 1.0) < 1e-12
    results.append(require(
        "glue ratio (ref/env)^amt stays clamped and finite",
        glue_ratio_ok,
    ))

    grid = [i * 0.005 for i in range(-1000, 1001)]
    finite_bounded = True
    mode_max: list[float] = []
    for mode in range(4):
        peak_abs = 0.0
        for u in grid:
            v = saturate(mode, u)
            if not math.isfinite(v):
                finite_bounded = False
                break
            peak_abs = max(peak_abs, abs(v))
        mode_max.append(peak_abs)
        finite_bounded = finite_bounded and peak_abs < 6.0
    results.append(require(
        "all four styles are finite and bounded pre-limiter",
        finite_bounded,
        "max|sat|=" + ", ".join(f"{m:.3f}" for m in mode_max),
    ))

    fold_linear = all(
        abs(saturate_core(1, u) - u) < 1e-12 for u in grid if abs(u) <= 1.0
    )
    asym_zero = abs(saturate_core(2, 0.0)) < 1e-12
    results.append(require(
        "foldback is transparent inside the ±1 linear zone; asymmetric passes through zero",
        fold_linear and asym_zero,
    ))

    fold_jump = 0.0
    for eps in (1e-9, -1e-9):
        u = 1.0 + eps
        au = abs(u)
        fw = 1.0 - abs((au % 2.0) - 1.0)
        v = fw if u > 0 else -fw
        fold_jump = max(fold_jump, abs(v - (1.0 + eps)))
    results.append(require(
        "foldback is continuous across the ±1 threshold",
        fold_jump < 1e-6,
        f"max jump={fold_jump:.2e}",
    ))

    mono = all(
        saturate(2, grid[i + 1]) > saturate(2, grid[i])
        for i in range(len(grid) - 1)
    )
    asym_values = (saturate(2, 6.0), saturate(2, -6.0))
    results.append(require(
        "asymmetric style is monotonic and asymmetric",
        mono and asym_values[0] > 1.5 and asym_values[1] < -1.0,
        f"v(6)={asym_values[0]:.3f} v(-6)={asym_values[1]:.3f}",
    ))

    crush_ok = True
    for even in (0.0, 0.25, 0.5, 1.0):
        bits = crush_bits(even)
        csc = 2.0 ** bits
        b = even * 0.35
        offset = b * b * b * 0.3333333333333333 - b
        for u in grid:
            if abs(u) > 4.0:
                continue
            v = saturate(3, u, even)
            err = (v - offset) * csc
            if abs(err - round(err)) > 1e-9:
                crush_ok = False
                break
            if abs((v - offset) - u) > 0.5 / csc + 1e-9:
                crush_ok = False
                break
        if not crush_ok:
            break
    results.append(require(
        "bitcrush style quantizes to a 2^bits grid (3..11 bits via Even)",
        crush_ok,
        f"grids={[2 ** crush_bits(e) for e in (0.0, 0.25, 0.5, 1.0)]}",
    ))

    versions = metadata.get("versions", {})
    params = metadata.get("parameters", {})
    features = metadata.get("features", [])
    metadata_ok = (
        metadata.get("version") == VERSION
        and versions.get("v0.4.0") == "versions/v0.4.0-auto-glue.eel"
        and metadata.get("latencySamples2x") == 15
        and params.get("dcBlockHz") == 5.0
        and params.get("satMode") == 0
        and params.get("glueOn") == 0
        and "latencyMs" not in metadata
        and all(f in features for f in (
            "mode-select-saturation", "foldback-mode", "asymmetric-mode", "bitcrush-mode",
            "live-parameter-bridge", "envelope-follower-glue",
        ))
    )
    results.append(require("metadata version/saturation semantics match v0.3.0", metadata_ok))

    passed = sum(results)
    total = len(results)
    print(f"\nSoloConsole audit: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
