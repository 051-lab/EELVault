#!/usr/bin/env python3
"""Static preflight gate for DRAGON on-device experimental finalists.

This audit intentionally checks host-dialect and memory-layout hazards in addition
to candidate DSP invariants.  It does not replace an actual RootlessJamesDSP EEL
parse/runtime test on Android.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCEL = ROOT / "dsp" / "dragon" / "experiments" / "dragon-acceleration-body.eel"
TOTAPE = ROOT / "dsp" / "dragon" / "experiments" / "dragon-totape-body.eel"
SECTIONS = ("@init", "@slider", "@block", "@sample")
EXPECTED_SLIDERS = (
    "drive", "bias", "comp", "wflutter", "body", "rolloff", "hiss", "trim"
)
SAFE_BODY_SLIDER = "body:0<-1,1,0.05>Body (Lean / Reference / Full)"


def require(name: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return condition


def _slider_lines(source: str) -> list[tuple[str, str]]:
    pattern = re.compile(r"(?m)^([A-Za-z_]\w*):[^<\n]+<[^>\n]+>.*$")
    return [(match.group(1), match.group(0)) for match in pattern.finditer(source)]


def _function_definitions(source: str) -> list[tuple[str, str]]:
    return re.findall(r"function\s+([A-Za-z_]\w*)\(([^)]*)\)", source)


def _sections_exact_and_ordered(source: str) -> tuple[bool, str]:
    positions: list[int] = []
    counts: list[int] = []
    for section in SECTIONS:
        matches = list(re.finditer(rf"(?m)^{re.escape(section)}\s*$", source))
        counts.append(len(matches))
        positions.append(matches[0].start() if matches else -1)
    ok = all(count == 1 for count in counts) and positions == sorted(positions)
    return ok, f"counts={counts}, positions={positions}"


def _function_args_are_rjdsp_safe(source: str) -> tuple[bool, str]:
    bad = [(name, args) for name, args in _function_definitions(source) if "," in args]
    return not bad, f"comma-arg definitions={bad}"


def _pear_state_is_warm_before_bypass(source: str) -> tuple[bool, str]:
    left_process = source.find("pear_out = pear_body_process(x, PEAR_BASE_L)")
    left_bypass = source.find("abs(body_s) > 0.000001 ?", left_process)
    right_process = source.find("pear_out = pear_body_process(x, PEAR_BASE_R)")
    right_bypass = source.find("abs(body_s) > 0.000001 ?", right_process)
    ok = (
        left_process >= 0
        and left_bypass > left_process
        and right_process >= 0
        and right_bypass > right_process
    )
    return ok, (
        f"L process/bypass={left_process}/{left_bypass}, "
        f"R process/bypass={right_process}/{right_bypass}"
    )


def _check_common(path: Path, source: str, label: str) -> list[bool]:
    results: list[bool] = []
    results.append(require(f"{label} exists", path.exists()))
    results.append(require(
        f"{label} is clearly experimental",
        source.startswith("desc: Dragon Cassette Emulator - EXP"),
    ))

    section_ok, section_detail = _sections_exact_and_ordered(source)
    results.append(require(
        f"{label} has exactly one ordered native section set",
        section_ok,
        section_detail,
    ))
    results.append(require(
        f"{label} contains no markdown-style EEL section markers",
        not any(token in source for token in ("[init](init)", "[slider](slider1)", "[block](block)", "[sample](sample)")),
    ))

    function_ok, function_detail = _function_args_are_rjdsp_safe(source)
    results.append(require(
        f"{label} function definitions use RJDSP space-separated args",
        function_ok,
        function_detail,
    ))

    sliders = _slider_lines(source)
    slider_names = tuple(name for name, _ in sliders)
    results.append(require(
        f"{label} has exactly the expected eight sliders in order",
        slider_names == EXPECTED_SLIDERS,
        f"sliders={slider_names}",
    ))
    results.append(require(
        f"{label} uses parser-conservative Body display text",
        any(line == SAFE_BODY_SLIDER for _, line in sliders),
        f"expected={SAFE_BODY_SLIDER!r}",
    ))
    results.append(require(
        f"{label} exposes Body instead of LF Contour slider",
        not re.search(r"(?m)^bump:", source),
    ))
    results.append(require(
        f"{label} retains fixed 1 dB reference head contour",
        "rbj_peak(50, 0.95, 1)" in source,
    ))
    results.append(require(
        f"{label} contains refined Pear profile constants",
        "PEAR_LEAN_LMID = 0.15;" in source
        and "PEAR_LEAN_BASS_COMP = 0.079;" in source
        and "PEAR_FULL_LMID = 0.10;" in source
        and "PEAR_FULL_BASS = 0.025;" in source,
    ))
    results.append(require(
        f"{label} reserves Pear memory outside W&F",
        "PEAR_BASE_L = 128;" in source and "PEAR_BASE_R = 176;" in source,
    ))
    results.append(require(
        f"{label} initializes W&F and Pear memory without overlap",
        "i = 0; loop(128, mem[i] = 0; i += 1;);" in source
        and "i = 128; loop(96, mem[i] = 0; i += 1;);" in source,
    ))

    hf_pos = source.find("// S8 BQ4: HF rolloff shelf")
    pear_pos = source.find("// BODY: refined eight-stage Pear")
    hiss_pos = source.find("// S9: tape hiss")
    results.append(require(
        f"{label} places Pear after replay HF shelf and before hiss",
        -1 not in (hf_pos, pear_pos, hiss_pos) and hf_pos < pear_pos < hiss_pos,
        f"positions={hf_pos},{pear_pos},{hiss_pos}",
    ))

    warm_ok, warm_detail = _pear_state_is_warm_before_bypass(source)
    results.append(require(
        f"{label} keeps Pear state warm before exact Body bypass",
        warm_ok,
        warm_detail,
    ))
    results.append(require(
        f"{label} exact Body reference bypass is explicit",
        source.count("abs(body_s) > 0.000001 ?") >= 2,
    ))
    results.append(require(
        f"{label} contains no Foundation Guard path",
        "foundation" not in source.lower(),
    ))
    return results


def check_acceleration() -> list[bool]:
    if not ACCEL.exists():
        return [require("Acceleration finalist exists", False, str(ACCEL))]
    source = ACCEL.read_text(encoding="utf-8")
    results = _check_common(ACCEL, source, "Acceleration finalist")
    results.append(require(
        "Acceleration finalist fixes limit at 0.32",
        "ACC_LIMIT = 0.32;" in source,
    ))
    results.append(require(
        "Acceleration finalist uses curvature detector",
        "acc_m1 = acc_d1*abs(acc_d1);" in source
        and "acc_m2 = acc_d2*abs(acc_d2);" in source
        and "acc_sense = min(1, acc_intensity*acc_intensity*abs(acc_m1 - acc_m2));" in source,
    ))
    results.append(require(
        "Acceleration finalist omits current broadband S6 damping map",
        "30000/(1 + 3.0*envN)" not in source
        and "30000/(1 + 3*envN)" not in source,
    ))
    results.append(require(
        "Acceleration finalist allocates non-overlapping history rings",
        "ACC_BASE_L = 224;" in source
        and "ACC_BASE_R = 288;" in source
        and "i = 224; loop(128, mem[i] = 0; i += 1;);" in source,
    ))
    return results


def check_totape() -> list[bool]:
    if not TOTAPE.exists():
        return [require("ToTape finalist exists", False, str(TOTAPE))]
    source = TOTAPE.read_text(encoding="utf-8")
    results = _check_common(TOTAPE, source, "ToTape finalist")
    results.append(require(
        "ToTape finalist fixes crossover and gain",
        "TT_CROSS_HZ = 2500;" in source and "TT_ENV_GAIN = 2;" in source,
    ))
    results.append(require(
        "ToTape finalist fixes 2/50 ms detector ballistics",
        "TT_ATTACK_S = 0.002;" in source and "TT_RELEASE_S = 0.050;" in source,
    ))
    results.append(require(
        "ToTape finalist uses HF residual detector",
        "tt_res = x - tt_lpL;" in source and "tt_res = x - tt_lpR;" in source,
    ))
    start = source.find("// S6: ToTape-DRAGON")
    stop = source.find("// S7", start)
    totape_section = source[start:stop] if start >= 0 and stop > start else ""
    results.append(require(
        "ToTape finalist detector is independent of linked S4 envelope",
        "TT_ENV_GAIN*env" not in source and "envN" not in totape_section,
    ))
    results.append(require(
        "ToTape finalist adds no memory region beyond W&F + Pear",
        "ACC_BASE_" not in source and "loop(128, mem[i] = 0; i += 1;);" in source,
    ))
    return results


def main() -> int:
    results: list[bool] = []
    results += check_acceleration()
    results += check_totape()
    passed = sum(results)
    total = len(results)
    print(f"\nDRAGON device-candidate audit: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
