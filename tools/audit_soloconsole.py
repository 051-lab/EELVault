#!/usr/bin/env python3
"""Dependency-free validation harness for SoloConsole.

Run from any working directory:
    python tools/audit_soloconsole.py

The script exits non-zero when any required v0.2.2 invariant fails.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DSP = ROOT / "dsp" / "soloconsole" / "soloconsole.eel"
ARCHIVE = ROOT / "dsp" / "soloconsole" / "versions" / "v0.2.2-validation-hardening.eel"
METADATA = ROOT / "dsp" / "soloconsole" / "metadata.json"


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


def main() -> int:
    source = load_text(DSP)
    metadata = json.loads(load_text(METADATA))
    results: list[bool] = []

    slider_numbers = [int(m.group(1)) for m in re.finditer(r"(?m)^slider([1-8]):", source)]
    section_lines = [name for name in ("@init", "@slider", "@block", "@sample")
                     if re.search(rf"(?m)^{re.escape(name)}\s*$", source)]
    sections_ok = len(section_lines) == 4
    results.append(require(
        "native EEL2 sections and sequential sliders",
        sections_ok and slider_numbers == list(range(1, 9)),
        f"sliders={slider_numbers} sections={section_lines}",
    ))

    legacy_names = ("inDb:", "drvDb:", "evenPct:", "bassDb:", "trebDb:", "outDb:", "osMode:", "mixPct:")
    present_legacy = [name for name in legacy_names if name in source]
    results.append(require("no legacy named slider declarations", not present_legacy, str(present_legacy)))

    results.append(require(
        "source version is v0.2.2",
        source.startswith("desc: SoloConsole Drive v0.2.2\n"),
    ))

    archive_ok = ARCHIVE.exists() and ARCHIVE.read_bytes() == DSP.read_bytes()
    results.append(require("v0.2.2 current/archive byte identity", archive_ok))

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

    versions = metadata.get("versions", {})
    params = metadata.get("parameters", {})
    metadata_ok = (
        metadata.get("version") == "0.2.2"
        and versions.get("v0.2.2") == "versions/v0.2.2-validation-hardening.eel"
        and metadata.get("latencySamples2x") == 15
        and params.get("dcBlockHz") == 5.0
        and "latencyMs" not in metadata
    )
    results.append(require("metadata version/DC/latency semantics match v0.2.2", metadata_ok))

    passed = sum(results)
    total = len(results)
    print(f"\nSoloConsole audit: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
