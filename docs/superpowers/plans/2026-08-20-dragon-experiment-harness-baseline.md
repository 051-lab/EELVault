# DRAGON Experimental Harness & Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dependency-free experimental harness that reproduces DRAGON v1.0.0 exactly, exposes measurement hooks without modifying production DSP, and locks the baseline measurements needed by the LF/HF/Body candidate plans.

**Architecture:** Keep `tools/audit_dragon.py` unchanged as the authoritative v1.0.0 audit/model. Add `tools/dragon_experiments.py` for reusable measurement primitives and an instrumented experiment engine derived from `audit_dragon.DragonEngine`; add `tools/audit_dragon_experiments.py` as the deterministic CLI/audit entry point. Candidate stages are injectable only in the experiment engine, and baseline mode must match the authoritative model sample-for-sample within floating-point tolerance.

**Tech Stack:** Python 3 standard library only (`argparse`, `dataclasses`, `math`, `json`, `pathlib`, `typing`); existing EELVault `tools/audit_dragon.py`; no NumPy/SciPy.

**Spec:** `docs/superpowers/specs/2026-08-19-dragon-adaptive-control-experiments-design.md`

## Global Constraints

- Work only on branch `dragon-adaptive-control-experiments`.
- Do not modify `dsp/dragon/dragon.eel`.
- Do not modify `dsp/dragon/versions/v1.0.0-absolute-lab-calibration.eel`.
- Do not modify `dsp/dragon/metadata.json`.
- Do not modify `tools/audit_dragon.py` in this plan.
- Python tooling must remain standard-library-only.
- v1.0.0 is the frozen baseline and `NONE` remains a valid outcome for every later experiment family.
- Sample rates required by the approved design are 44.1 and 48 kHz.
- The experiment harness must be runnable from any working directory with `python path/to/tools/audit_dragon_experiments.py`.
- No candidate `.eel` file is created in this plan.

---

## File Structure

- Create `tools/dragon_experiments.py` — shared constants, fixtures, spectral/level measurements, instrumentation, and experiment-engine stage injection.
- Create `tools/audit_dragon_experiments.py` — CLI checks and deterministic baseline report.
- Keep `tools/audit_dragon.py` unchanged — authoritative v1.0.0 source/model audit.

The later LF, HF, and Body plans extend the two new experiment files; they do not duplicate baseline infrastructure.

---

### Task 1: Add dependency-free measurement primitives

**Files:**
- Create: `tools/dragon_experiments.py`
- Create: `tools/audit_dragon_experiments.py`

**Interfaces:**
- Produces: `db_to_amp(db: float) -> float`
- Produces: `amp_to_db(amp: float, floor_db: float = -300.0) -> float`
- Produces: `rms(values: list[float]) -> float`
- Produces: `project_tone_amplitude(values: list[float], fs: float, freq: float, start: int = 0) -> float`
- Produces: `make_sine(fs: float, freq: float, level_db: float, seconds: float, phase: float = 0.0) -> list[float]`
- Produces: `make_two_tone(fs: float, freq_a: float, level_a_db: float, freq_b: float, level_b_db: float, seconds: float) -> list[float]`
- Produces CLI section: `core`

- [ ] **Step 1: Write the failing core-math checks**

Create `tools/audit_dragon_experiments.py` with an argparse shell and checks that import the six interfaces above. The test body must include these exact invariants:

```python
import argparse
import math

from dragon_experiments import (
    amp_to_db,
    db_to_amp,
    make_sine,
    make_two_tone,
    project_tone_amplitude,
    rms,
)


def require(name: str, condition: bool, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return condition


def check_core() -> list[bool]:
    results: list[bool] = []
    results.append(require(
        "-6 dB converts to amplitude",
        abs(db_to_amp(-6.0) - (10.0 ** (-6.0 / 20.0))) < 1e-15,
    ))
    results.append(require(
        "amplitude round-trip is stable",
        abs(amp_to_db(db_to_amp(-42.5)) + 42.5) < 1e-12,
    ))

    fs = 48000.0
    tone = make_sine(fs, 1000.0, -12.0, 0.1)
    expected_rms = db_to_amp(-12.0) / math.sqrt(2.0)
    results.append(require(
        "sine RMS is correct",
        abs(rms(tone) - expected_rms) < 1e-9,
    ))
    measured = project_tone_amplitude(tone, fs, 1000.0)
    results.append(require(
        "coherent tone projection recovers amplitude",
        abs(amp_to_db(measured) + 12.0) < 1e-6,
    ))

    dual = make_two_tone(fs, 60.0, -6.0, 10000.0, -30.0, 0.5)
    results.append(require(
        "two-tone fixture preserves 10 kHz component",
        abs(amp_to_db(project_tone_amplitude(dual, fs, 10000.0)) + 30.0) < 1e-5,
    ))
    return results
```

The CLI must accept `--section core` and return non-zero if any core check fails.

- [ ] **Step 2: Run the core section and verify it fails**

Run:

```bash
python tools/audit_dragon_experiments.py --section core
```

Expected: FAIL during import because `tools/dragon_experiments.py` does not yet define the requested interfaces.

- [ ] **Step 3: Implement the measurement primitives**

Create `tools/dragon_experiments.py` with the following implementation shape:

```python
from __future__ import annotations

import math


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


def project_tone_amplitude(
    values: list[float], fs: float, freq: float, start: int = 0
) -> float:
    data = values[start:]
    if not data:
        return 0.0
    re = 0.0
    im = 0.0
    omega = 2.0 * math.pi * freq / fs
    for n, sample in enumerate(data, start=start):
        angle = omega * n
        re += sample * math.cos(angle)
        im -= sample * math.sin(angle)
    return 2.0 * math.hypot(re, im) / len(data)


def make_sine(
    fs: float, freq: float, level_db: float, seconds: float, phase: float = 0.0
) -> list[float]:
    frames = int(round(fs * seconds))
    amp = db_to_amp(level_db)
    omega = 2.0 * math.pi * freq / fs
    return [amp * math.sin(omega * n + phase) for n in range(frames)]


def make_two_tone(
    fs: float,
    freq_a: float,
    level_a_db: float,
    freq_b: float,
    level_b_db: float,
    seconds: float,
) -> list[float]:
    a = make_sine(fs, freq_a, level_a_db, seconds)
    b = make_sine(fs, freq_b, level_b_db, seconds)
    return [x + y for x, y in zip(a, b)]
```

Keep the module import-safe: no prints and no file writes at import time.

- [ ] **Step 4: Run the core section and verify it passes**

Run:

```bash
python tools/audit_dragon_experiments.py --section core
```

Expected: all core checks PASS and process exit code 0.

- [ ] **Step 5: Commit the measurement core**

```bash
git add tools/dragon_experiments.py tools/audit_dragon_experiments.py
git commit -m "test: add Dragon experiment measurement core"
```

---

### Task 2: Add an instrumented experiment engine with exact baseline parity

**Files:**
- Modify: `tools/dragon_experiments.py`
- Modify: `tools/audit_dragon_experiments.py`

**Interfaces:**
- Consumes: `audit_dragon.DragonEngine`, `audit_dragon.LIMIT_T`, `audit_dragon.CLAMP`
- Produces: `StageTelemetry`
- Produces: `DragonExperimentEngine(fs: float, *, lf_stage=None, hf_stage=None, body_stage=None, **dragon_kwargs)`
- Produces: `DragonExperimentEngine.telemetry`
- Produces CLI section: `parity`

`lf_stage` consumes a stereo frame before S1 with `process_frame(left, right) -> (left, right)`. `hf_stage` consumes one channel immediately after S5 with `process_sample(channel, sample) -> sample`. `body_stage` consumes one channel after S8 replay EQ and before S9 hiss with the same per-channel interface.

- [ ] **Step 1: Write a failing sample-parity check**

Add a `check_parity()` section that compares authoritative `DragonEngine` with `DragonExperimentEngine` using no candidate stages:

```python
from audit_dragon import DragonEngine
from dragon_experiments import DragonExperimentEngine


def check_parity() -> list[bool]:
    results: list[bool] = []
    for fs in (44100.0, 48000.0):
        ref = DragonEngine(fs, wf=0.0, hiss=-200.0)
        exp = DragonExperimentEngine(fs, wf=0.0, hiss=-200.0)
        max_err = 0.0
        for n in range(4096):
            left = math.sin(2.0 * math.pi * 997.0 * n / fs) * 0.35
            right = math.sin(2.0 * math.pi * 1511.0 * n / fs + 0.37) * 0.27
            ref_l, ref_r = ref.process(left, right)
            exp_l, exp_r = exp.process(left, right)
            max_err = max(max_err, abs(ref_l - exp_l), abs(ref_r - exp_r))
        results.append(require(
            f"experiment engine baseline parity @ {int(fs)} Hz",
            max_err < 1e-15,
            f"max error={max_err:.3e}",
        ))
    return results
```

- [ ] **Step 2: Run parity and verify it fails**

Run:

```bash
python tools/audit_dragon_experiments.py --section parity
```

Expected: FAIL because `DragonExperimentEngine` does not exist.

- [ ] **Step 3: Implement telemetry and stage injection without changing baseline mode**

In `tools/dragon_experiments.py`, import the authoritative engine and define telemetry:

```python
from dataclasses import dataclass, field

from audit_dragon import CLAMP, LIMIT_K, LIMIT_T, DragonEngine


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
```

Implement `DragonExperimentEngine` as a subclass. Its `process()` must apply `lf_stage` before calling the baseline processing logic. Its `_channel()` must take an exact copy of the authoritative `_channel()` path only when instrumentation or candidate stages are active, with these insertion points:

```python
class DragonExperimentEngine(DragonEngine):
    def __init__(self, fs, *, lf_stage=None, hf_stage=None, body_stage=None, **kwargs):
        super().__init__(fs, **kwargs)
        self.lf_stage = lf_stage
        self.hf_stage = hf_stage
        self.body_stage = body_stage
        self.telemetry = StageTelemetry()
        self._instrument = any(stage is not None for stage in (lf_stage, hf_stage, body_stage))

    def process(self, in_l, in_r):
        if self.lf_stage is not None:
            in_l, in_r = self.lf_stage.process_frame(in_l, in_r)
        if not self._instrument:
            return super().process(in_l, in_r)
        out_l, out_r = super().process(in_l, in_r)
        self.telemetry.frames += 1
        self.telemetry.max_output = max(
            self.telemetry.max_output, abs(out_l), abs(out_r)
        )
        return out_l, out_r
```

For the instrumented `_channel()` copy, preserve all authoritative lines and add only these stage/telemetry operations at the approved points:

```python
# after S4
x *= gcomp
self.telemetry.peak_s4 = max(self.telemetry.peak_s4, abs(x))

# after S5
s = x * driveLin
v = math.tanh(s)
x = (v + asym * v * v) * makeup
self.telemetry.peak_s5 = max(self.telemetry.peak_s5, abs(x))

# S6 replacement hook
if self.hf_stage is None:
    x = c["dm"].process(x)
else:
    x = self.hf_stage.process_sample(ch, x)
self.telemetry.peak_s6 = max(self.telemetry.peak_s6, abs(x))

# after the final replay-EQ high shelf and before hiss
x = c["hf"].process(x)
if self.body_stage is not None:
    x = self.body_stage.process_sample(ch, x)

# immediately before soft limiter
x = c["dc2"].process(x)
self.telemetry.peak_pre_limiter = max(self.telemetry.peak_pre_limiter, abs(x))
ax = abs(x)
if ax > LIMIT_T:
    self.telemetry.limiter_hits += 1
    y = LIMIT_T + (1.0 - LIMIT_T) * math.tanh((ax - LIMIT_T) * LIMIT_K)
    x = y if x > 0.0 else -y
```

Because no-stage mode delegates directly to `DragonEngine`, the parity test must be exact. Candidate-mode parity against the copied path is tested later with explicit pass-through stages.

- [ ] **Step 4: Run authoritative and experiment audits**

Run:

```bash
python tools/audit_dragon.py
python tools/audit_dragon_experiments.py --section parity
```

Expected: both exit 0; experiment baseline parity reports max error below `1e-15` at both rates.

- [ ] **Step 5: Commit the experiment engine**

```bash
git add tools/dragon_experiments.py tools/audit_dragon_experiments.py
git commit -m "test: add instrumented Dragon experiment engine"
```

---

### Task 3: Lock small-signal response and current S6 coupling measurements

**Files:**
- Modify: `tools/dragon_experiments.py`
- Modify: `tools/audit_dragon_experiments.py`

**Interfaces:**
- Produces: `FREQUENCY_PROBES = (20.0, 30.0, 50.0, 80.0, 100.0, 150.0, 200.0, 300.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0, 14000.0, 18000.0, 20000.0)`
- Produces: `measure_frequency_response(engine_factory, fs, frequencies=FREQUENCY_PROBES, level_db=-60.0) -> dict[float, float]`
- Produces: `current_s6_cutoff(env: float) -> float`
- Produces CLI section: `baseline-fr`

- [ ] **Step 1: Write failing baseline-FR checks**

Add checks for analytically known S6 endpoints and finite response results:

```python
def check_baseline_fr() -> list[bool]:
    results: list[bool] = []
    results.append(require(
        "S6 cutoff at zero envelope is 30 kHz",
        abs(current_s6_cutoff(0.0) - 30000.0) < 1e-12,
    ))
    results.append(require(
        "S6 cutoff lower bound is 7 kHz",
        current_s6_cutoff(10.0) == 7000.0,
    ))
    for fs in (44100.0, 48000.0):
        fr = measure_frequency_response(
            lambda: DragonEngine(fs, wf=0.0, hiss=-200.0), fs
        )
        results.append(require(
            f"baseline FR finite @ {int(fs)} Hz",
            all(math.isfinite(value) for value in fr.values()),
        ))
        results.append(require(
            f"baseline FR contains 50/200/10k/18k probes @ {int(fs)} Hz",
            all(freq in fr for freq in (50.0, 200.0, 10000.0, 18000.0)),
        ))
    return results
```

- [ ] **Step 2: Run and verify failure**

```bash
python tools/audit_dragon_experiments.py --section baseline-fr
```

Expected: FAIL because the measurement functions/constants are absent.

- [ ] **Step 3: Implement coherent response measurement**

Use `0.5 s` fixtures and discard the first `0.1 s` to let IIR state settle:

```python
FREQUENCY_PROBES = (
    20.0, 30.0, 50.0, 80.0, 100.0, 150.0, 200.0, 300.0,
    500.0, 1000.0, 2000.0, 5000.0, 10000.0, 14000.0,
    18000.0, 20000.0,
)


def current_s6_cutoff(env: float) -> float:
    env_n = min(1.6, env * 2.0)
    return max(7000.0, 30000.0 / (1.0 + 3.0 * env_n))


def measure_frequency_response(engine_factory, fs, frequencies=FREQUENCY_PROBES, level_db=-60.0):
    result: dict[float, float] = {}
    seconds = 0.5
    start = int(0.1 * fs)
    for freq in frequencies:
        engine = engine_factory()
        signal = make_sine(fs, freq, level_db, seconds)
        output: list[float] = []
        for sample in signal:
            left, _ = engine.process(sample, sample)
            output.append(left)
        measured = project_tone_amplitude(output, fs, freq, start=start)
        result[freq] = amp_to_db(measured) - level_db
    return result
```

The report must print each frequency/gain pair; do not bake the previously estimated response numbers into pass/fail assertions. This task establishes the measured baseline from the current authoritative model.

- [ ] **Step 4: Run both baseline audits**

```bash
python tools/audit_dragon.py
python tools/audit_dragon_experiments.py --section baseline-fr
```

Expected: both exit 0; FR table prints for 44.1 and 48 kHz.

- [ ] **Step 5: Commit baseline FR characterization**

```bash
git add tools/dragon_experiments.py tools/audit_dragon_experiments.py
git commit -m "test: characterize Dragon baseline response"
```

---

### Task 4: Implement the canonical Challenger coupling regression

**Files:**
- Modify: `tools/dragon_experiments.py`
- Modify: `tools/audit_dragon_experiments.py`

**Interfaces:**
- Produces: `CHALLENGER_LF_DB = (-30.0, -20.0, -12.0, -6.0, -3.0, 0.0)`
- Produces: `CHALLENGER_HF_DB = -30.0`
- Produces: `measure_challenger_coupling(engine_factory, fs) -> list[dict[str, float]]`
- Produces: `measure_inverse_hf_sweep(engine_factory, fs) -> list[dict[str, float]]`
- Produces CLI section: `challenger`

- [ ] **Step 1: Write a failing fixture-integrity check**

Add checks that the LF sweep is exact and the HF measurement is normalized to the `-30 dBFS` LF reference condition:

```python
def check_challenger() -> list[bool]:
    results: list[bool] = []
    results.append(require(
        "canonical LF sweep is frozen",
        CHALLENGER_LF_DB == (-30.0, -20.0, -12.0, -6.0, -3.0, 0.0),
    ))
    for fs in (44100.0, 48000.0):
        rows = measure_challenger_coupling(
            lambda: DragonEngine(fs, wf=0.0, hiss=-200.0), fs
        )
        results.append(require(
            f"Challenger sweep returns six rows @ {int(fs)} Hz",
            len(rows) == 6,
        ))
        results.append(require(
            f"Challenger reference delta is zero @ {int(fs)} Hz",
            abs(rows[0]["delta_hf_db"]) < 1e-12,
        ))
        results.append(require(
            f"baseline demonstrates measurable LF-to-HF coupling @ {int(fs)} Hz",
            min(row["delta_hf_db"] for row in rows[1:]) < -0.05,
        ))
    return results
```

The `-0.05 dB` assertion is not a candidate promotion threshold; it only verifies that the regression fixture exposes the already-identified v1.0.0 coupling.

- [ ] **Step 2: Run and verify failure**

```bash
python tools/audit_dragon_experiments.py --section challenger
```

Expected: FAIL because the fixture functions do not exist.

- [ ] **Step 3: Implement the two-tone and inverse sweeps**

Use `0.5 s` per row and discard the first `0.1 s`. Keep `10 kHz` fixed at `-30 dBFS` for the canonical sweep. For the inverse sweep keep LF at `-12 dBFS` and sweep HF through `(-42, -36, -30, -24, -18, -12) dBFS`.

```python
CHALLENGER_LF_DB = (-30.0, -20.0, -12.0, -6.0, -3.0, 0.0)
CHALLENGER_HF_DB = -30.0
INVERSE_HF_DB = (-42.0, -36.0, -30.0, -24.0, -18.0, -12.0)


def measure_challenger_coupling(engine_factory, fs):
    rows = []
    start = int(0.1 * fs)
    reference_hf = None
    for lf_db in CHALLENGER_LF_DB:
        engine = engine_factory()
        signal = make_two_tone(fs, 60.0, lf_db, 10000.0, CHALLENGER_HF_DB, 0.5)
        output = []
        for sample in signal:
            left, _ = engine.process(sample, sample)
            output.append(left)
        hf_db = amp_to_db(project_tone_amplitude(output, fs, 10000.0, start))
        if reference_hf is None:
            reference_hf = hf_db
        rows.append({
            "lf_db": lf_db,
            "hf_out_db": hf_db,
            "delta_hf_db": hf_db - reference_hf,
        })
    return rows
```

Implement `measure_inverse_hf_sweep()` analogously and report measured 10 kHz output versus HF input level. Do not require a particular compression curve yet; later HF candidates use this as evidence that they still respond to increasing HF activity.

- [ ] **Step 4: Run the canonical fixture at both rates**

```bash
python tools/audit_dragon_experiments.py --section challenger
```

Expected: exit 0 and print the six-row baseline coupling table for 44.1 and 48 kHz.

- [ ] **Step 5: Commit the Challenger regression**

```bash
git add tools/dragon_experiments.py tools/audit_dragon_experiments.py
git commit -m "test: lock Dragon Challenger coupling regression"
```

---

### Task 5: Add baseline LF/headroom/limiter characterization and an all-section CLI

**Files:**
- Modify: `tools/dragon_experiments.py`
- Modify: `tools/audit_dragon_experiments.py`

**Interfaces:**
- Produces: `LF_PROBES = (50.0, 60.0, 80.0, 100.0, 150.0, 200.0, 300.0)`
- Produces: `LEVEL_PROBES_DB = (-30.0, -18.0, -12.0, -6.0, -3.0)`
- Produces: `measure_lf_level_grid(engine_factory, fs) -> list[dict[str, float]]`
- Produces: `measure_stress_telemetry(engine_factory, fs, frames=8192) -> dict[str, float]`
- Produces CLI section: `baseline-dynamics`
- Produces default CLI behavior: run `core`, `parity`, `baseline-fr`, `challenger`, and `baseline-dynamics`.

- [ ] **Step 1: Write failing dynamics checks**

The check must verify finite telemetry, bounded output, and valid limiter hit rate:

```python
def check_baseline_dynamics() -> list[bool]:
    results: list[bool] = []
    for fs in (44100.0, 48000.0):
        rows = measure_lf_level_grid(
            lambda: DragonExperimentEngine(fs, wf=0.0, hiss=-200.0), fs
        )
        results.append(require(
            f"LF level grid complete @ {int(fs)} Hz",
            len(rows) == len(LF_PROBES) * len(LEVEL_PROBES_DB),
        ))
        metrics = measure_stress_telemetry(
            lambda: DragonExperimentEngine(fs), fs
        )
        results.append(require(
            f"stress telemetry finite @ {int(fs)} Hz",
            all(math.isfinite(value) for value in metrics.values()),
        ))
        results.append(require(
            f"limiter rate valid @ {int(fs)} Hz",
            0.0 <= metrics["limiter_rate"] <= 1.0,
        ))
        results.append(require(
            f"output respects hard clamp @ {int(fs)} Hz",
            metrics["max_output"] <= 0.99999 + 1e-9,
        ))
    return results
```

- [ ] **Step 2: Run and verify failure**

```bash
python tools/audit_dragon_experiments.py --section baseline-dynamics
```

Expected: FAIL because LF-grid/stress helpers are absent.

- [ ] **Step 3: Implement the LF grid and deterministic stress telemetry**

Use coherent `0.25 s` sine fixtures for the LF grid, discarding `0.05 s`. For stress telemetry use the same deterministic integer-noise construction already used by `audit_dragon.stress_probe`, but route through `DragonExperimentEngine` so S4/S5/S6/pre-limiter peaks are captured.

Return this exact metric set:

```python
{
    "peak_s4": engine.telemetry.peak_s4,
    "peak_s5": engine.telemetry.peak_s5,
    "peak_s6": engine.telemetry.peak_s6,
    "peak_pre_limiter": engine.telemetry.peak_pre_limiter,
    "max_output": engine.telemetry.max_output,
    "limiter_rate": engine.telemetry.limiter_hits / max(1, engine.telemetry.frames * 2),
}
```

Ensure `DragonExperimentEngine` enables instrumentation when `instrument=True` is passed even when no candidate stages are installed. Add `instrument: bool = False` to its constructor and include that flag in `_instrument`.

- [ ] **Step 4: Run every baseline check and the authoritative v1.0.0 audit**

```bash
python tools/audit_dragon.py
python tools/audit_dragon_experiments.py
```

Expected: both exit 0. The experiment audit prints baseline FR, Challenger coupling, LF level grid summary, and stage/headroom metrics for both sample rates.

- [ ] **Step 5: Confirm frozen files are untouched**

Run:

```bash
git diff --exit-code main -- \
  dsp/dragon/dragon.eel \
  dsp/dragon/versions/v1.0.0-absolute-lab-calibration.eel \
  dsp/dragon/metadata.json \
  tools/audit_dragon.py
```

Expected: no diff and exit 0.

- [ ] **Step 6: Commit the complete baseline harness**

```bash
git add tools/dragon_experiments.py tools/audit_dragon_experiments.py
git commit -m "test: complete Dragon experimental baseline harness"
```

---

## Plan Acceptance Gate

This plan is complete only when all of the following are true:

1. `python tools/audit_dragon.py` passes unchanged.
2. `python tools/audit_dragon_experiments.py` passes.
3. The experiment engine no-stage mode matches `DragonEngine` below `1e-15` max absolute error at 44.1/48 kHz.
4. The canonical 60 Hz + 10 kHz fixture demonstrates measurable v1.0.0 LF-to-HF coupling.
5. Baseline FR, LF grid, stage peaks, limiter rate, and clamp behavior are reported deterministically.
6. Production Dragon files and `tools/audit_dragon.py` are unchanged from `main`.
7. No third-party Python dependency has been introduced.

Only after this gate passes should the LF and HF experiment plans begin.
