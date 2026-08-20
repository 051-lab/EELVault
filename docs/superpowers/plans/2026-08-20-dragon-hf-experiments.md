# DRAGON HF Dynamic-Control Experiments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace vague broadband-level-driven HF damping with a measured shootout between exact Sinew, an Acceleration2-derived conditional smoother, and a ToTape9-inspired HF-residual detector while keeping current S6 as the control.

**Architecture:** All HF candidates are injected immediately after S5 saturation in `DragonExperimentEngine`. Sinew and Acceleration operate per channel as their Airwindows sources do; ToTape-DRAGON uses independent per-channel HF residual envelopes in the first pass and must pass the approved stereo-integrity tests before promotion. None of the candidate action stages may add an unconditional linear HF rolloff when inactive.

**Tech Stack:** Python 3 standard library only; shared experiment harness; Airwindows source equations already captured by the approved design/research.

**Spec:** `docs/superpowers/specs/2026-08-19-dragon-adaptive-control-experiments-design.md`

## Global Constraints

- Requires the completed baseline-harness plan.
- Work only on `dragon-adaptive-control-experiments`.
- Production Dragon `.eel`, archive, metadata, and baseline audit remain unchanged.
- `current-s6` remains in every comparison table and is allowed to win.
- No two HF mechanisms may be stacked in this plan.
- No candidate may add a permanent output low-pass merely because the original Airwindows plugin did.
- Sinew must use exact `cos()` first; approximation work is deferred.
- Slew4 is not implemented unless Sinew, Acceleration-DRAGON, and ToTape-DRAGON all fail to produce a viable finalist.

---

## File Structure

- Modify `tools/dragon_experiments.py` — HF stage implementations, registries, edge/IMD/slew helpers.
- Modify `tools/audit_dragon_experiments.py` — source-parity checks and HF comparison report.

---

### Task 1: Implement exact Sinew

**Files:**
- Modify: `tools/dragon_experiments.py`
- Modify: `tools/audit_dragon_experiments.py`

**Interfaces:**
- Produces: `SinewStage(fs: float, amount: float = 0.5)`
- Produces: `SinewStage.process_sample(channel: str, sample: float) -> float`
- Produces candidate key: `hf-sinew`
- Produces CLI section: `hf-sinew`

The experiment parameter `amount` maps directly to Airwindows Sinew `A`, so:

```python
threshold = ((1.0 - amount) ** 4) / (fs / 44100.0)
```

- [ ] **Step 1: Write a failing source-derived vector check**

At 48 kHz and `amount=0.5`, starting from zero state, the left-channel vector must match:

```python
REFERENCE_IN = [0.0, 0.2, -0.4, 0.8, -1.0]
REFERENCE_OUT = [
    0.0,
    0.057421875,
    3.12145054151558e-07,
    0.05742218714505415,
    6.242968956238215e-07,
]
```

Add a max-error assertion below `1e-12`.

- [ ] **Step 2: Run and verify failure**

```bash
python tools/audit_dragon_experiments.py --section hf-sinew
```

Expected: FAIL because `SinewStage` is absent.

- [ ] **Step 3: Implement exact Sinew without dither**

```python
class SinewStage:
    def __init__(self, fs: float, amount: float = 0.5):
        self.threshold = ((1.0 - amount) ** 4) / (fs / 44100.0)
        self.last = {"L": 0.0, "R": 0.0}
        self.clamp_events = 0

    def process_sample(self, channel: str, sample: float) -> float:
        previous = self.last[channel]
        allowed = self.threshold * math.cos(previous * previous)
        delta = sample - previous
        output = sample
        if delta > allowed:
            output = previous + allowed
            self.clamp_events += 1
        elif -delta > allowed:
            output = previous - allowed
            self.clamp_events += 1
        output = max(-1.0, min(1.0, output))
        self.last[channel] = output
        return output
```

- [ ] **Step 4: Add inactive-region behavior check**

Generate a low-amplitude 1 kHz sine at `-60 dBFS` with `amount=0.1`; require max absolute input/output error below `1e-12`. This confirms conditional behavior rather than an unconditional filter.

Run:

```bash
python tools/audit_dragon_experiments.py --section hf-sinew
```

Expected: source vector and inactive-region checks pass.

- [ ] **Step 5: Commit Sinew**

```bash
git add tools/dragon_experiments.py tools/audit_dragon_experiments.py
git commit -m "test: add exact Sinew HF experiment"
```

---

### Task 2: Implement Acceleration-DRAGON without the unconditional output LP

**Files:**
- Modify: `tools/dragon_experiments.py`
- Modify: `tools/audit_dragon_experiments.py`

**Interfaces:**
- Produces: `AccelerationStage(fs: float, limit: float = 0.32)`
- Produces: `AccelerationStage.process_sample(channel: str, sample: float) -> float`
- Produces candidate key: `hf-acceleration`
- Produces CLI section: `hf-acceleration`

- [ ] **Step 1: Write a failing source-derived core vector check**

For 48 kHz, `limit=0.32`, and input:

```python
REFERENCE_IN = [0.0, 0.25, -0.5, 0.75, -1.0, 0.5, -0.25, 0.0]
```

The Acceleration-DRAGON core—Airwindows detector plus its first dynamic smoothing biquad, but **without** the original plugin's final unconditional 20 kHz low-pass—must produce:

```python
REFERENCE_OUT = [
    0.0,
    0.2408485758052058,
    -0.38270495973647617,
    0.599029209386089,
    -1.0,
    0.20487324615905156,
    0.06866910261967105,
    0.004107805504075277,
]
```

The corresponding detector `sense` values must be:

```python
REFERENCE_SENSE = [
    0.0,
    0.06871947673600003,
    0.2748779069440001,
    0.20615843020800007,
    0.0,
    0.34359738368000015,
    0.8933531975680004,
    0.20615843020800007,
]
```

Require max error below `1e-12` for both vectors.

- [ ] **Step 2: Run and verify failure**

```bash
python tools/audit_dragon_experiments.py --section hf-acceleration
```

Expected: FAIL because the stage is absent.

- [ ] **Step 3: Implement source-faithful detector and conditional smoothing**

Use:

```python
overallscale = fs / 44100.0
intensity = (limit ** 3) * 32.0
spacing = min(16, int(1.73 * overallscale) + 1)
smooth_fc = 20000.0 * (1.0 - limit * 0.6180339887498948)
```

For each channel maintain a 34-sample history buffer and one RBJ-style 2-pole low-pass state using the same coefficients as Acceleration2's first biquad (`Q=0.7071`). For each sample:

```python
d1 = s[0] - s[spacing]
d2 = s[spacing] - s[spacing * 2]
m1 = d1 * abs(d1)
m2 = d2 * abs(d2)
sense = min(1.0, intensity * intensity * abs(m1 - m2))
output = sample * (1.0 - sense) + smooth * sense
```

Do **not** implement Acceleration2's final 20 kHz biquadB.

Expose `last_sense` and `max_sense` per channel.

- [ ] **Step 4: Add LF rejection behavior check**

At 48 kHz with `limit=0.32`, compare 1-second pure tones at equal `-6 dBFS` level. Require mean detector sense for 10 kHz to be at least 20 times mean sense for 60 Hz. This is a detector-behavior test, not a sonic promotion threshold.

Run:

```bash
python tools/audit_dragon_experiments.py --section hf-acceleration
```

Expected: vector parity and LF-rejection checks pass.

- [ ] **Step 5: Commit Acceleration-DRAGON**

```bash
git add tools/dragon_experiments.py tools/audit_dragon_experiments.py
git commit -m "test: add Acceleration-derived HF experiment"
```

---

### Task 3: Implement ToTape-DRAGON HF-residual detection

**Files:**
- Modify: `tools/dragon_experiments.py`
- Modify: `tools/audit_dragon_experiments.py`

**Interfaces:**
- Produces: `ToTapeHFConfig`
- Produces: `ToTapeHFStage(fs: float, config: ToTapeHFConfig)`
- Produces candidate key: `hf-totape`
- Produces CLI section: `hf-totape`

Use this first-pass search grid:

```python
TOTAPE_CROSSOVER_HZ = (2500.0, 4000.0, 6000.0)
TOTAPE_ENV_GAIN = (2.0, 4.0, 8.0)
TOTAPE_ATTACK_MS = 2.0
TOTAPE_RELEASE_MS = 50.0
TOTAPE_MIN_DAMP_HZ = 7000.0
TOTAPE_MAX_DAMP_HZ = 30000.0
```

- [ ] **Step 1: Write failing detector-selectivity checks**

For config `crossover_hz=4000`, `env_gain=4`, process equal-level `-12 dBFS` pure 60 Hz and 10 kHz fixtures separately. Require settled HF envelope for 10 kHz to exceed the 60 Hz envelope by at least 20x.

Also process a `-60 dBFS` 1 kHz signal and require output/input max error below `1e-9` after settling, proving the action stage is essentially inactive when the HF envelope is negligible.

- [ ] **Step 2: Run and verify failure**

```bash
python tools/audit_dragon_experiments.py --section hf-totape
```

Expected: FAIL because the stage is absent.

- [ ] **Step 3: Implement residual detection and conditional one-pole damping**

Define:

```python
@dataclass(frozen=True)
class ToTapeHFConfig:
    crossover_hz: float
    env_gain: float
    attack_ms: float = 2.0
    release_ms: float = 50.0
    min_damp_hz: float = 7000.0
    max_damp_hz: float = 30000.0
```

Per channel:

1. One-pole LP at `crossover_hz`.
2. `residual = sample - lowpassed`.
3. Envelope target `abs(residual)` with 2 ms attack/50 ms release.
4. `env_n = min(1.6, envelope * env_gain)`.
5. Reuse DRAGON's existing damping map: `dfc = max(min_damp_hz, max_damp_hz / (1 + 3*env_n))`.
6. Convert `dfc` to one-pole coefficient and low-pass the audio sample.

Expose `last_env`, `last_dfc`, and per-channel maxima. Do not reference the S4 broadband envelope anywhere in this class.

- [ ] **Step 4: Run the entire 3x3 grid at both sample rates**

Require finite output, `7000 <= last_dfc <= 30000`, and detector selectivity. Print 60 Hz/10 kHz envelope ratios for each row.

```bash
python tools/audit_dragon_experiments.py --section hf-totape
```

Expected: exit 0.

- [ ] **Step 5: Commit ToTape-DRAGON**

```bash
git add tools/dragon_experiments.py tools/audit_dragon_experiments.py
git commit -m "test: add ToTape-derived HF detector experiment"
```

---

### Task 4: Add HF edge, IMD, slew, and transient metrics

**Files:**
- Modify: `tools/dragon_experiments.py`
- Modify: `tools/audit_dragon_experiments.py`

**Interfaces:**
- Produces: `measure_max_slew(values: list[float]) -> float`
- Produces: `measure_hf_imd(engine_factory, fs, low_freq, high_freq) -> dict[str, float]`
- Produces: `measure_tone_burst(engine_factory, fs, freq, level_db=-6.0) -> dict[str, float]`
- Produces: `measure_edge_response(engine_factory, fs) -> dict[str, float]`
- Produces CLI section: `hf-metrics`

- [ ] **Step 1: Write failing pass-through sanity tests**

Require `measure_max_slew([0, 0.25, -0.5, 0.75]) == 1.25`. Require a pass-through 1 kHz + 10 kHz fixture to have projected non-source sidebands below `-120 dB` relative to the 10 kHz carrier.

- [ ] **Step 2: Run and verify failure**

```bash
python tools/audit_dragon_experiments.py --section hf-metrics
```

Expected: FAIL because metrics are absent.

- [ ] **Step 3: Implement the required approved metrics**

Implement:

- 1/5/10/15 kHz tone bursts: 20 ms silence, 40 ms tone, 40 ms silence; report attack peak, settled RMS, release tail peak.
- 1 kHz + 10 kHz IMD: levels `-12/-18 dBFS`; project sidebands at 9 and 11 kHz.
- 60 Hz + 10 kHz IMD: levels `-6/-18 dBFS`; project sidebands at 9940 and 10060 Hz.
- impulse: unit impulse followed by 4095 zeros; report peak and first 32 output samples' absolute sum.
- square edge: 1 kHz square at `-12 dBFS`; report max sample-to-sample slew and overshoot beyond source amplitude.

All measurements run at 44.1 and 48 kHz.

- [ ] **Step 4: Run metric sanity tests**

```bash
python tools/audit_dragon_experiments.py --section hf-metrics
```

Expected: exit 0; all reported metrics finite.

- [ ] **Step 5: Commit HF metrics**

```bash
git add tools/dragon_experiments.py tools/audit_dragon_experiments.py
git commit -m "test: add Dragon HF transient and IMD metrics"
```

---

### Task 5: Build the full HF comparison matrix

**Files:**
- Modify: `tools/dragon_experiments.py`
- Modify: `tools/audit_dragon_experiments.py`

**Interfaces:**
- Produces: `HF_CANDIDATES: dict[str, callable]`
- Produces CLI section: `hf`
- Reuses: `measure_challenger_coupling`, `measure_inverse_hf_sweep`, `measure_frequency_response`

- [ ] **Step 1: Write a failing registry check**

Require these candidate families:

```python
{
    "current-s6",
    "hf-sinew",
    "hf-acceleration",
    "hf-totape",
}
```

`current-s6` must instantiate `DragonExperimentEngine` with no replacement HF stage.

- [ ] **Step 2: Run and verify failure**

```bash
python tools/audit_dragon_experiments.py --section hf
```

Expected: FAIL until the registry/report exists.

- [ ] **Step 3: Run every candidate through the approved evidence set**

For every candidate/config at 44.1/48 kHz report:

1. canonical 60 Hz + 10 kHz LF-amplitude sweep;
2. inverse fixed-LF/HF-amplitude sweep;
3. small-signal FR at all baseline probe frequencies;
4. 1/5/10/15 kHz burst metrics;
5. 1 kHz + 10 kHz IMD;
6. 60 Hz + 10 kHz IMD;
7. impulse metrics;
8. square-edge metrics;
9. max sample-to-sample slew;
10. limiter rate and peak-pre-limiter from the full Dragon path;
11. state-count estimate;
12. primitive-operation estimate per stereo frame.

For Sinew sweep `amount` over `(0.10, 0.20, 0.30, 0.40, 0.50)`.
For Acceleration sweep `limit` over `(0.16, 0.24, 0.32, 0.40)`.
For ToTape use the full `3 x 3` crossover/env-gain grid.

Do not auto-select a single winner. Mark non-dominated rows across LF-to-HF coupling reduction, inverse-HF responsiveness, small-signal FR error, IMD, and operation count.

- [ ] **Step 4: Explicitly test the architectural goal**

For each row calculate:

```python
coupling_span_db = max(delta_hf_db) - min(delta_hf_db)
```

and print it beside the baseline `current-s6` coupling span. A candidate is not called “coupling-improved” unless its span is smaller than baseline while its inverse-HF sweep still shows decreasing 10 kHz output efficiency as HF input rises.

This label is evidence only; it does not override IMD/FR/CPU review.

- [ ] **Step 5: Save a local JSON report and run all audits**

```bash
python tools/audit_dragon.py
python tools/audit_dragon_experiments.py --section hf --json-out /tmp/dragon-hf-results.json
```

Expected: both exit 0.

- [ ] **Step 6: Verify frozen production files**

```bash
git diff --exit-code main -- \
  dsp/dragon/dragon.eel \
  dsp/dragon/versions/v1.0.0-absolute-lab-calibration.eel \
  dsp/dragon/metadata.json \
  tools/audit_dragon.py
```

Expected: exit 0.

- [ ] **Step 7: Commit the HF matrix**

```bash
git add tools/dragon_experiments.py tools/audit_dragon_experiments.py
git commit -m "test: complete Dragon HF candidate matrix"
```

---

## Plan Acceptance Gate

The HF plan is complete only when:

1. Sinew matches its source-derived vector below `1e-12`.
2. Acceleration-DRAGON matches both source-derived output and sense vectors below `1e-12` while omitting the unconditional final LP.
3. ToTape-DRAGON detector is independent of S4 and demonstrably more responsive to 10 kHz than 60 Hz at equal level.
4. Current S6 and all candidate grids have Challenger, inverse-HF, FR, burst, IMD, impulse, edge, slew, limiter, state, and operation metrics.
5. `current-s6` remains eligible; no code chooses a winner automatically.
6. No two candidate HF mechanisms are stacked.
7. Production Dragon files and baseline audit remain unchanged.
8. `python tools/audit_dragon.py` and `python tools/audit_dragon_experiments.py --section hf` exit 0.
