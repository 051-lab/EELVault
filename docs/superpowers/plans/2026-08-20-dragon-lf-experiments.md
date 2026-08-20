# DRAGON LF Control Experiments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and measure the three approved LF candidates—literal Airwindows Highpass/Tight, a DRAGON-specific Foundation Guard, and a lightweight StoneFire-inspired guard—without modifying production DRAGON.

**Architecture:** Extend the shared experiment module with stereo-frame LF stages that run before DRAGON S1. Every candidate is measured inside the same `DragonExperimentEngine` and against the same baseline fixtures. The literal Highpass model is a source-faithful reference; the Foundation Guard and Stone guard are DRAGON-specific candidates. No automatic production winner is declared by code.

**Tech Stack:** Python 3 standard library only; `tools/dragon_experiments.py`; `tools/audit_dragon_experiments.py`; authoritative `tools/audit_dragon.py` baseline.

**Spec:** `docs/superpowers/specs/2026-08-19-dragon-adaptive-control-experiments-design.md`

## Global Constraints

- Requires the completed baseline-harness plan `docs/superpowers/plans/2026-08-20-dragon-experiment-harness-baseline.md`.
- Work only on branch `dragon-adaptive-control-experiments`.
- Production Dragon `.eel`, archive, metadata, and baseline audit remain unchanged.
- All candidate code stays in Python during this plan.
- `NONE` is a valid LF outcome.
- No new user-facing compressor/threshold/attack/release controls are introduced.
- The DRAGON Foundation Guard must be stereo-linked and zero-lookahead.
- Literal Airwindows Highpass is an experimental reference, not the default production recommendation.

---

## File Structure

- Modify `tools/dragon_experiments.py` — LF stage classes, distortion/headroom helpers, candidate registry.
- Modify `tools/audit_dragon_experiments.py` — LF source-parity checks, grid measurements, comparison report.

---

### Task 1: Implement literal Airwindows Highpass/Tight

**Files:**
- Modify: `tools/dragon_experiments.py`
- Modify: `tools/audit_dragon_experiments.py`

**Interfaces:**
- Produces: `LiteralHighpassTight(fs: float, highpass: float = 0.20, tight_param: float = 1.0)`
- Produces: `LiteralHighpassTight.process_frame(left: float, right: float) -> tuple[float, float]`
- Produces candidate key: `lf-highpass-literal`
- Produces CLI section: `lf-highpass`

- [ ] **Step 1: Write a failing source-parity vector check**

Use this exact 48 kHz source-derived reference vector for the left channel at `highpass=0.20`, `tight_param=1.0`, starting from zero state:

```python
REFERENCE_IN = [0.0, 0.25, -0.5, 0.75, -1.0]
REFERENCE_OUT = [
    0.0,
    0.2481625,
    -0.4951,
    0.738997509375,
    -0.98047203,
]
```

Add:

```python
def check_lf_highpass() -> list[bool]:
    stage = LiteralHighpassTight(48000.0, highpass=0.20, tight_param=1.0)
    measured = [stage.process_frame(x, x)[0] for x in REFERENCE_IN]
    err = max(abs(a - b) for a, b in zip(measured, REFERENCE_OUT))
    return [require(
        "literal Highpass/Tight matches source-derived vector",
        err < 1e-12,
        f"max error={err:.3e}",
    )]
```

- [ ] **Step 2: Run and verify failure**

```bash
python tools/audit_dragon_experiments.py --section lf-highpass
```

Expected: FAIL because `LiteralHighpassTight` is absent.

- [ ] **Step 3: Implement the exact source mechanism**

Use the Airwindows equations without dither or wet mix:

```python
class LiteralHighpassTight:
    def __init__(self, fs: float, highpass: float = 0.20, tight_param: float = 1.0):
        self.fs = fs
        overallscale = fs / 44100.0
        self.iir_amount = (highpass ** 3) / overallscale
        tight = (tight_param * 2.0) - 1.0
        self.iir_amount += self.iir_amount * tight * tight
        self.tight = tight / 1.5 if tight > 0.0 else tight / 3.0
        self.iir_amount = max(0.0, min(1.0, self.iir_amount))
        self.flip = True
        self.a_l = self.b_l = 0.0
        self.a_r = self.b_r = 0.0

    def _one(self, x: float, channel: str) -> float:
        if self.tight > 0.0:
            offset = (1.0 - self.tight) + abs(x) * self.tight
        else:
            offset = (1.0 + self.tight) + (1.0 - abs(x)) * self.tight
        offset = max(0.0, min(1.0, offset))
        coeff = offset * self.iir_amount
        if channel == "L":
            if self.flip:
                self.a_l = self.a_l * (1.0 - coeff) + x * coeff
                return x - self.a_l
            self.b_l = self.b_l * (1.0 - coeff) + x * coeff
            return x - self.b_l
        if self.flip:
            self.a_r = self.a_r * (1.0 - coeff) + x * coeff
            return x - self.a_r
        self.b_r = self.b_r * (1.0 - coeff) + x * coeff
        return x - self.b_r

    def process_frame(self, left: float, right: float) -> tuple[float, float]:
        out_l = self._one(left, "L")
        out_r = self._one(right, "R")
        self.flip = not self.flip
        return out_l, out_r
```

- [ ] **Step 4: Run source parity and baseline audit**

```bash
python tools/audit_dragon_experiments.py --section lf-highpass
python tools/audit_dragon.py
```

Expected: both exit 0.

- [ ] **Step 5: Commit literal Highpass**

```bash
git add tools/dragon_experiments.py tools/audit_dragon_experiments.py
git commit -m "test: model Airwindows Highpass Tight for Dragon"
```

---

### Task 2: Implement the DRAGON Foundation Guard

**Files:**
- Modify: `tools/dragon_experiments.py`
- Modify: `tools/audit_dragon_experiments.py`

**Interfaces:**
- Produces: `FoundationGuardConfig`
- Produces: `FoundationGuard(fs: float, config: FoundationGuardConfig, amount: float = 1.0)`
- Produces candidate key: `lf-foundation`
- Produces CLI section: `lf-foundation`

Use this exact search grid for the first numerical sweep:

```python
FOUNDATION_DETECTOR_HZ = (80.0, 100.0, 120.0, 150.0)
FOUNDATION_ATTACK_MS = (5.0, 10.0)
FOUNDATION_RELEASE_MS = (80.0, 120.0)
FOUNDATION_MAX_HP_HZ = (45.0, 60.0, 75.0)
FOUNDATION_MIN_HP_HZ = 5.0
FOUNDATION_ENV_FLOOR = 0.10
FOUNDATION_ENV_CEIL = 0.70
```

- [ ] **Step 1: Write failing neutral/linking checks**

Add checks that `amount=0` is a numerical bypass and that asymmetric input still produces one shared detector value:

```python
def check_lf_foundation() -> list[bool]:
    cfg = FoundationGuardConfig(
        detector_hz=120.0,
        attack_ms=5.0,
        release_ms=120.0,
        max_hp_hz=60.0,
    )
    bypass = FoundationGuard(48000.0, cfg, amount=0.0)
    samples = [(0.1, -0.2), (0.5, 0.0), (-0.75, 0.25)]
    out = [bypass.process_frame(l, r) for l, r in samples]
    results = [require(
        "Foundation amount=0 is exact bypass",
        out == samples,
    )]

    linked = FoundationGuard(48000.0, cfg, amount=1.0)
    linked.process_frame(0.9, 0.05)
    results.append(require(
        "Foundation detector is stereo-linked",
        linked.last_env_l == linked.last_env_r == linked.env,
    ))
    return results
```

- [ ] **Step 2: Run and verify failure**

```bash
python tools/audit_dragon_experiments.py --section lf-foundation
```

Expected: FAIL because config/stage are absent.

- [ ] **Step 3: Implement linked LF detection and smoothed cutoff modulation**

Define:

```python
@dataclass(frozen=True)
class FoundationGuardConfig:
    detector_hz: float
    attack_ms: float
    release_ms: float
    max_hp_hz: float
    min_hp_hz: float = 5.0
    env_floor: float = 0.10
    env_ceil: float = 0.70
```

Implement the stage with these exact mechanics:

1. Per-channel one-pole detector LP: `a = 1 - exp(-2*pi*detector_hz/fs)`.
2. Linked instantaneous target: `target = max(abs(det_l), abs(det_r))`.
3. Envelope smoothing: attack coefficient when target rises, release coefficient when it falls.
4. Normalize: `u = clamp((env-env_floor)/(env_ceil-env_floor), 0, 1)`.
5. Apply `u = u*u` so moderate bass is preserved.
6. Dynamic cutoff: `fc = min_hp_hz + amount*u*(max_hp_hz-min_hp_hz)`.
7. Convert cutoff to one-pole LP coefficient `hp_a = 1 - exp(-2*pi*fc/fs)`.
8. Maintain independent L/R LP states but subtract them from each channel: `out = x - lp_state`.
9. When `amount <= 0`, return the input before updating any processing state.

Expose `env`, `last_env_l`, `last_env_r`, and `last_hp_hz` for measurements.

- [ ] **Step 4: Run the Foundation grid stability check**

The audit must instantiate all `4*2*2*3 = 48` grid combinations at 44.1/48 kHz and process a 2-second deterministic LF stress signal. Require all samples finite, `5 <= last_hp_hz <= max_hp_hz`, and max output below `2.0` in the float-domain experiment path.

Run:

```bash
python tools/audit_dragon_experiments.py --section lf-foundation
```

Expected: all 96 rate/config combinations stable.

- [ ] **Step 5: Commit Foundation Guard**

```bash
git add tools/dragon_experiments.py tools/audit_dragon_experiments.py
git commit -m "test: add Dragon Foundation Guard experiment"
```

---

### Task 3: Implement the lightweight StoneFire-inspired guard

**Files:**
- Modify: `tools/dragon_experiments.py`
- Modify: `tools/audit_dragon_experiments.py`

**Interfaces:**
- Produces: `StoneGuardConfig`
- Produces: `StoneGuard(fs: float, config: StoneGuardConfig, amount: float = 1.0)`
- Produces candidate key: `lf-stone-light`
- Produces CLI section: `lf-stone`

Use the first-pass search grid:

```python
STONE_SPLIT_HZ = (80.0, 100.0, 120.0, 150.0)
STONE_THRESHOLD = (0.15, 0.25)
STONE_MAX_GR_DB = (1.0, 2.0)
STONE_ATTACK_MS = 10.0
STONE_RELEASE_MS = 120.0
```

- [ ] **Step 1: Write failing unity-recombination checks**

```python
def check_lf_stone() -> list[bool]:
    cfg = StoneGuardConfig(split_hz=120.0, threshold=0.25, max_gr_db=2.0)
    stage = StoneGuard(48000.0, cfg, amount=0.0)
    values = [(0.1, -0.1), (0.7, 0.2), (-0.4, 0.9)]
    measured = [stage.process_frame(l, r) for l, r in values]
    return [require(
        "Stone guard amount=0 recombines to exact input",
        measured == values,
    )]
```

- [ ] **Step 2: Run and verify failure**

```bash
python tools/audit_dragon_experiments.py --section lf-stone
```

Expected: FAIL because Stone guard interfaces are absent.

- [ ] **Step 3: Implement complementary split and shallow linked gain control**

Define:

```python
@dataclass(frozen=True)
class StoneGuardConfig:
    split_hz: float
    threshold: float
    max_gr_db: float
    attack_ms: float = 10.0
    release_ms: float = 120.0
```

Use a one-pole low-pass foundation per channel:

```text
stone = LP(input)
remainder = input - stone
```

Use one linked envelope from `max(abs(stone_l), abs(stone_r))`. Above threshold, compute normalized overdrive:

```python
over = max(0.0, env - threshold) / max(1e-12, 1.0 - threshold)
gr_db = min(max_gr_db, amount * max_gr_db * over * over)
gain = 10.0 ** (-gr_db / 20.0)
```

Recombine:

```python
out_l = remainder_l + stone_l * gain
out_r = remainder_r + stone_r * gain
```

At `amount=0`, bypass before updating state.

- [ ] **Step 4: Run grid stability and unity checks**

Test all `4*2*2 = 16` configurations at both rates on silence, -30 dBFS sine, -3 dBFS sine, and deterministic stress. Require finite output, `0 <= last_gr_db <= max_gr_db`, exact bypass at amount 0, and no channel-to-channel gain mismatch because gain is linked.

```bash
python tools/audit_dragon_experiments.py --section lf-stone
```

Expected: exit 0.

- [ ] **Step 5: Commit Stone guard**

```bash
git add tools/dragon_experiments.py tools/audit_dragon_experiments.py
git commit -m "test: add lightweight Stone foundation guard"
```

---

### Task 4: Add LF distortion, headroom, and stereo measurements

**Files:**
- Modify: `tools/dragon_experiments.py`
- Modify: `tools/audit_dragon_experiments.py`

**Interfaces:**
- Produces: `measure_thd(stage_factory, fs, freq=60.0, level_db=-6.0) -> float`
- Produces: `measure_dynamic_imd(stage_factory, fs) -> dict[str, float]`
- Produces: `measure_lf_headroom(engine_factory, fs) -> dict[str, float]`
- Produces: `measure_stereo_integrity(engine_factory, fs) -> dict[str, float]`
- Produces CLI section: `lf-metrics`

- [ ] **Step 1: Write failing metric-sanity checks**

Use a pass-through stage as the mathematical control. Require THD below `-120 dB`, IMD sidebands below `-120 dB`, and zero L/R gain mismatch for identical input.

- [ ] **Step 2: Run and verify failure**

```bash
python tools/audit_dragon_experiments.py --section lf-metrics
```

Expected: FAIL because metric helpers are absent.

- [ ] **Step 3: Implement THD and dynamic-IMD projections**

For THD:

- fixture: 60 Hz, -6 dBFS, 2.0 s;
- discard first 0.5 s;
- measure harmonics 2 through 8 by direct projection;
- `thd = sqrt(sum(harmonic_amp**2)) / fundamental_amp`;
- return `amp_to_db(thd)`.

For dynamic IMD:

- fixture: 60 Hz at -6 dBFS + 1 kHz at -18 dBFS, 2.0 s;
- discard first 0.5 s;
- measure `940 Hz` and `1060 Hz` sidebands;
- report each relative to the 1 kHz carrier.

- [ ] **Step 4: Implement full-Dragon headroom and stereo tests**

Headroom fixture:

- 60 Hz at `(-12, -6, -3, 0) dBFS`;
- run each LF stage before `DragonExperimentEngine` with default DRAGON settings, `wf=0`, `hiss=-200`;
- capture `peak_s4`, `peak_s5`, `peak_s6`, `peak_pre_limiter`, and limiter rate.

Stereo integrity fixture:

- L: 60 Hz `-3 dBFS` + 1 kHz `-18 dBFS`;
- R: 60 Hz `-18 dBFS` + 1 kHz `-18 dBFS`;
- measure resulting 1 kHz L/R levels;
- report `abs(left_1k_db - right_1k_db)` as non-LF image disturbance.

Do not hard-code a promotion threshold here. Report comparable metrics for every candidate.

- [ ] **Step 5: Run LF metrics**

```bash
python tools/audit_dragon_experiments.py --section lf-metrics
```

Expected: pass-through sanity checks pass and all candidate measurements are finite.

- [ ] **Step 6: Commit LF metrics**

```bash
git add tools/dragon_experiments.py tools/audit_dragon_experiments.py
git commit -m "test: add Dragon LF distortion and headroom metrics"
```

---

### Task 5: Build the LF comparison matrix and evidence report

**Files:**
- Modify: `tools/dragon_experiments.py`
- Modify: `tools/audit_dragon_experiments.py`

**Interfaces:**
- Produces: `LF_CANDIDATES: dict[str, callable]`
- Produces CLI section: `lf`
- Produces CLI option: `--json-out PATH`

- [ ] **Step 1: Write a failing registry-completeness check**

Require these keys exactly:

```python
{
    "none",
    "lf-highpass-literal",
    "lf-foundation",
    "lf-stone-light",
}
```

- [ ] **Step 2: Run and verify failure**

```bash
python tools/audit_dragon_experiments.py --section lf
```

Expected: FAIL because the registry/report is incomplete.

- [ ] **Step 3: Register baseline and candidate factories**

The report must include, for every candidate/config at both rates:

- 50/60/80/100/150/200/300 Hz level behavior;
- THD at 60 Hz/-6 dBFS;
- 60 Hz + 1 kHz IMD sidebands;
- S4/S5/S6/pre-limiter peaks;
- limiter rate;
- stereo integrity metric;
- state-count estimate;
- primitive-operation estimate per stereo frame, excluding Python overhead.

For `lf-foundation` and `lf-stone-light`, print the full configuration grid but additionally identify the non-dominated configurations: a row is dominated only when another row is no worse in LF restraint, THD, IMD, limiter rate, and operation count and strictly better in at least one of those metrics.

Do not print a single automatic “winner”. Print `eligible/non-dominated` rows and retain `none` in the table.

- [ ] **Step 4: Run the full LF report and save a local JSON artifact**

```bash
python tools/audit_dragon_experiments.py --section lf --json-out /tmp/dragon-lf-results.json
```

Expected: exit 0; JSON contains both sample rates and all four candidate families.

- [ ] **Step 5: Verify production files are still unchanged**

```bash
git diff --exit-code main -- \
  dsp/dragon/dragon.eel \
  dsp/dragon/versions/v1.0.0-absolute-lab-calibration.eel \
  dsp/dragon/metadata.json \
  tools/audit_dragon.py
```

Expected: exit 0.

- [ ] **Step 6: Commit the LF comparison matrix**

```bash
git add tools/dragon_experiments.py tools/audit_dragon_experiments.py
git commit -m "test: complete Dragon LF candidate matrix"
```

---

## Plan Acceptance Gate

The LF plan is complete when:

1. Literal Highpass matches the fixed source-derived reference vector below `1e-12` max error.
2. Foundation Guard is exact bypass at amount 0, stereo-linked, bounded, and stable across its full 48-point configuration grid at both rates.
3. Stone guard is exact bypass at amount 0, unity-recombining with no gain reduction, and stable across its full grid.
4. THD, IMD, headroom, limiter, stereo, state, and operation metrics exist for all candidate families.
5. The report preserves `none` and does not auto-promote a winner.
6. Production Dragon files and `tools/audit_dragon.py` remain unchanged.
7. `python tools/audit_dragon.py` and `python tools/audit_dragon_experiments.py --section lf` both exit 0.
