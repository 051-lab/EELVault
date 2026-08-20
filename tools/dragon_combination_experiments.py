#!/usr/bin/env python3
"""Initial DRAGON combination gate: HF finalist x Pear Body, LF fixed to NONE.

The purpose is elimination, not automatic promotion.  Production DRAGON remains
untouched and the selection file defaults to the current v1.0.0 path.
"""

from __future__ import annotations

import json
from pathlib import Path

from audit_dragon import DragonEngine
from dragon_body_experiments import PearBodyProfile, PearBodyStage, body_response
from dragon_experiments import (
    DragonExperimentEngine,
    measure_challenger_coupling,
    measure_inverse_hf_sweep,
    measure_stress_telemetry,
)
from dragon_hf_experiments import (
    AccelerationStage,
    ToTapeHFConfig,
    ToTapeHFStage,
    coupling_span,
    inverse_efficiency_drop,
)

SELECTION_PATH = Path(__file__).with_name("dragon_experiment_selection.json")

REFINED_BODY_PROFILE = PearBodyProfile(
    lean_lmid_drop=0.15,
    lean_bass_drop=-0.079,
    full_lmid_rise=0.10,
    full_bass_rise=0.025,
)

HF_CONTEXTS = {
    "current-s6": {},
    "hf-acceleration": {"limit": 0.32},
    "hf-totape": {"crossover_hz": 2500.0, "env_gain": 2.0},
}

BODY_CONTEXTS = {
    "body-none": None,
    "body-lean-half": -0.5,
    "body-lean-full": -1.0,
}


def load_selection(path: Path = SELECTION_PATH) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if set(data) != {"lf", "hf", "body"}:
        raise ValueError("selection must contain exactly lf/hf/body")
    if data["lf"].get("key") != "none" or data["lf"].get("params") != {}:
        raise ValueError("initial combination gate requires LF=none")
    if data["hf"].get("key") not in {"current-s6", "hf-acceleration", "hf-totape"}:
        raise ValueError("unsupported HF selection")
    if data["body"].get("key") not in {"body-none", "body-pear"}:
        raise ValueError("unsupported Body selection")
    return data


def _hf_stage(fs: float, key: str):
    if key == "current-s6":
        return None
    if key == "hf-acceleration":
        return AccelerationStage(fs, limit=0.32)
    if key == "hf-totape":
        return ToTapeHFStage(
            fs,
            ToTapeHFConfig(crossover_hz=2500.0, env_gain=2.0),
        )
    raise ValueError(f"unknown HF context: {key}")


def _body_stage(fs: float, body_key: str):
    body = BODY_CONTEXTS[body_key]
    if body is None:
        return None
    return PearBodyStage(fs, body=body, profile=REFINED_BODY_PROFILE)


def make_combination_engine(fs: float, hf_key: str, body_key: str):
    return DragonExperimentEngine(
        fs,
        hf_stage=_hf_stage(fs, hf_key),
        body_stage=_body_stage(fs, body_key),
        wf=0.0,
        hiss=-200.0,
        instrument=True,
    )


def make_selection_engine(fs: float, selection: dict | None = None):
    selection = load_selection() if selection is None else selection
    hf_key = selection["hf"]["key"]
    body_key = selection["body"]["key"]

    if hf_key == "current-s6":
        hf_stage = None
    elif hf_key == "hf-acceleration":
        params = selection["hf"].get("params", {})
        hf_stage = AccelerationStage(fs, **params)
    elif hf_key == "hf-totape":
        params = selection["hf"].get("params", {})
        hf_stage = ToTapeHFStage(fs, ToTapeHFConfig(**params))
    else:
        raise ValueError("unsupported HF selection")

    if body_key == "body-none":
        body_stage = None
    else:
        params = selection["body"].get("params", {})
        body = float(params.get("body", 0.0))
        profile_data = params.get("profile")
        profile = (
            REFINED_BODY_PROFILE
            if profile_data is None
            else PearBodyProfile(**profile_data)
        )
        body_stage = PearBodyStage(fs, body=body, profile=profile)

    return DragonExperimentEngine(
        fs,
        hf_stage=hf_stage,
        body_stage=body_stage,
        wf=0.0,
        hiss=-200.0,
        instrument=True,
    )


def selection_baseline_error(fs: float, frames: int = 4096) -> float:
    """Safe default must reproduce baseline experiment path sample-for-sample."""
    reference = DragonEngine(fs, wf=0.0, hiss=-200.0)
    selected = make_selection_engine(fs)
    maximum = 0.0
    import math

    for n in range(frames):
        left = 0.35 * math.sin(2.0 * math.pi * 997.0 * n / fs)
        right = 0.27 * math.sin(2.0 * math.pi * 1511.0 * n / fs + 0.37)
        ref_l, ref_r = reference.process(left, right)
        out_l, out_r = selected.process(left, right)
        maximum = max(maximum, abs(ref_l - out_l), abs(ref_r - out_r))
    return maximum


def measure_combination(fs: float, hf_key: str, body_key: str) -> dict:
    factory = lambda: make_combination_engine(fs, hf_key, body_key)
    challenger = measure_challenger_coupling(factory, fs)
    inverse = measure_inverse_hf_sweep(factory, fs)
    stress = measure_stress_telemetry(factory, fs, frames=8192)

    body = BODY_CONTEXTS[body_key]
    static_body = (
        {str(int(freq)): 0.0 for freq in (50.0, 80.0, 100.0, 150.0, 200.0, 300.0, 500.0, 1000.0)}
        if body is None
        else {
            str(int(freq)): value
            for freq, value in body_response(
                fs, body, REFINED_BODY_PROFILE
            ).items()
        }
    )

    return {
        "hf": hf_key,
        "body": body_key,
        "challenger": challenger,
        "coupling_span_db": coupling_span(challenger),
        "inverse": inverse,
        "inverse_efficiency_drop_db": inverse_efficiency_drop(inverse),
        "body_response_db": static_body,
        "stress": stress,
    }


def build_initial_combination_report() -> dict:
    report = {
        "scope": "LF fixed to NONE",
        "body_profile": {
            "lean_lmid_drop": REFINED_BODY_PROFILE.lean_lmid_drop,
            "lean_bass_drop": REFINED_BODY_PROFILE.lean_bass_drop,
            "full_lmid_rise": REFINED_BODY_PROFILE.full_lmid_rise,
            "full_bass_rise": REFINED_BODY_PROFILE.full_bass_rise,
        },
        "sample_rates": {},
    }
    for fs in (44100.0, 48000.0):
        report["sample_rates"][str(int(fs))] = [
            measure_combination(fs, hf_key, body_key)
            for hf_key in HF_CONTEXTS
            for body_key in BODY_CONTEXTS
        ]
    return report
