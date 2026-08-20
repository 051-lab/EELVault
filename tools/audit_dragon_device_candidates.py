#!/usr/bin/env python3
"""Static + numerical gate for DRAGON on-device experimental finalists."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCEL = ROOT / "dsp" / "dragon" / "experiments" / "dragon-acceleration-body.eel"
TOTAPE = ROOT / "dsp" / "dragon" / "experiments" / "dragon-totape-body.eel"


def require(name: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return condition


def _slider_count(source: str) -> int:
    return len(re.findall(r"(?m)^[A-Za-z_]\w*:[^<\n]+<[^>\n]+>", source))


def _check_common(path: Path, source: str, label: str) -> list[bool]:
    results: list[bool] = []
    results.append(require(f"{label} exists", path.exists()))
    results.append(require(
        f"{label} is clearly experimental",
        source.startswith("desc: Dragon Cassette Emulator - EXP"),
    ))
    results.append(require(
        f"{label} has native EEL sections",
        all(re.search(rf"(?m)^{section}\s*$", source) for section in ("@init", "@slider", "@block", "@sample")),
    ))
    results.append(require(
        f"{label} has exactly eight sliders",
        _slider_count(source) == 8,
        f"count={_slider_count(source)}",
    ))
    results.append(require(
        f"{label} exposes Body instead of LF Contour slider",
        "body:0<-1,1,0.05>Body" in source and not re.search(r"(?m)^bump:", source),
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
    hf_pos = source.find("// S8 BQ4: HF rolloff shelf")
    pear_pos = source.find("// BODY: refined eight-stage Pear")
    hiss_pos = source.find("// S9: tape hiss")
    results.append(require(
        f"{label} places Pear after replay HF shelf and before hiss",
        -1 not in (hf_pos, pear_pos, hiss_pos) and hf_pos < pear_pos < hiss_pos,
        f"positions={hf_pos},{pear_pos},{hiss_pos}",
    ))
    results.append(require(
        f"{label} exact Body reference bypass is explicit",
        "abs(body_s) > 0.000001 ?" in source,
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
        "Acceleration finalist omits current broadband S6 damping",
        "30000/(1 + 3.0*envN)" not in source,
    ))
    results.append(require(
        "Acceleration finalist allocates non-overlapping history rings",
        "ACC_BASE_L = 224;" in source and "ACC_BASE_R = 288;" in source,
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
