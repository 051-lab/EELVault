# DRAGON Pear Body & Combination Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement an exact PearLite-derived Body experiment with a true neutral reference, measure its low-mid authority and cost, then provide a controlled combination gate for the evidence-selected LF/HF finalists without modifying production DRAGON.

**Architecture:** Implement the exact eight-stage PearLite decomposition first. `Body` is a macro over only Pear's LMid/Bass level parameters; High and HMid remain at neutral. The experiment engine inserts Body after replay EQ and before hiss. Combination testing is registry-driven and starts from an explicit selection file whose safe default is the current DRAGON path (`none` LF, `current-s6` HF, `none` Body). Candidate promotion remains a review decision based on generated evidence.

**Tech Stack:** Python 3 standard library only; existing experiment harness and LF/HF candidate registries.

**Spec:** `docs/superpowers/specs/2026-08-19-dragon-adaptive-control-experiments-design.md`

## Global Constraints

- Requires completion of the baseline harness and numerical LF/HF plans before the final combination-selection task.
- Work only on `dragon-adaptive-control-experiments`.
- Production Dragon `.eel`, archive, metadata, and baseline audit remain unchanged.
- Target UI remains eight controls; Body is a future repurpose of `LF Contour`, not a ninth control.
- `Body = 0` must be numerical reference/bypass behavior.
- Full eight-stage PearLite is implemented and measured before reduced-stage variants are considered.
- Pear sits after S8 replay EQ and before S9 hiss in experiments.
- No Body control changes record-stage drive, compression, saturation, W&F, or generated hiss.
- `NONE` remains valid for Body, LF, and HF.
- This plan does not create a production `.eel`; on-device finalists receive a separate implementation plan after numerical review.

---

## File Structure

- Modify `tools/dragon_experiments.py` — exact PearLite stage, Body macro profiles, phase/group-delay helpers, combination factories.
- Modify `tools/audit_dragon_experiments.py` — Pear source-parity, Body response/cost report, combination matrix.
- Create `tools/dragon_experiment_selection.json` — explicit registry selection; initial content is safe baseline only.

---

### Task 1: Implement exact eight-stage PearLiteEQ decomposition

**Files:**
- Modify: `tools/dragon_experiments.py`
- Modify: `tools/audit_dragon_experiments.py`

**Interfaces:**
- Produces: `PearLiteStage(fs: float, high: float = 0.5, hmid: float = 0.5, lmid: float = 0.5, bass: float = 0.5, stages: int = 8)`
- Produces: `PearLiteStage.process_sample(channel: str, sample: float) -> float`
- Produces CLI section: `body-pear-core`

- [ ] **Step 1: Write failing neutral and source-derived vector checks**

Neutral test: at `high=hmid=lmid=bass=0.5`, process a deterministic stereo sequence and require max input/output error below `1e-12` after zero-state startup.

Non-neutral source-derived test at 48 kHz:

```python
REFERENCE_IN = [0.0, 0.25, -0.5, 0.75, -1.0, 0.5, -0.25, 0.0]
REFERENCE_OUT = [
    0.0,
    0.24747170923694406,
    -0.5013933237712032,
    0.7458792032603025,
    -1.001327429796749,
    0.502977462320823,
    -0.2438757912466743,
    0.009025645480079064,
]
```

Use `high=0.5`, `hmid=0.5`, `lmid=0.25`, `bass=0.45`, `stages=8`. Require max error below `1e-12`.

- [ ] **Step 2: Run and verify failure**

```bash
python tools/audit_dragon_experiments.py --section body-pear-core
```

Expected: FAIL because `PearLiteStage` is absent.

- [ ] **Step 3: Implement exact source equations**

Use these coefficient equations:

```python
overallscale = fs / 44100.0
top_level = math.sqrt(high + 0.5)
a_level = math.sqrt(hmid + 0.5)
b_level = math.sqrt(lmid + 0.5)
c_level = math.sqrt(bass + 0.5)
freq_factor = math.sqrt(overallscale) + overallscale * 0.5
freq_a = 0.564 ** (freq_factor + 0.85)
freq_b = 0.564 ** (freq_factor + 4.1)
freq_c = 0.564 ** (freq_factor + 7.1)
```

Maintain eight `[prev_sample, prev_slew]` state pairs per channel for each Pear A/B/C filter. For each stage, reproduce the source order exactly:

```python
fig_a = x
slew_a = ((fig_a - prev_a) + prev_slew_a) * freq_a * 0.5
new_a = freq_a * fig_a + (1.0 - freq_a) * (prev_a + prev_slew_a)
# store new_a/slew_a
x -= new_a

fig_b = new_a
slew_b = ((fig_b - prev_b) + prev_slew_b) * freq_b * 0.5
new_b = freq_b * fig_b + (1.0 - freq_b) * (prev_b + prev_slew_b)
# store new_b/slew_b
band_a = new_a - new_b

fig_c = new_b
slew_c = ((fig_c - prev_c) + prev_slew_c) * freq_c * 0.5
new_c = freq_c * fig_c + (1.0 - freq_c) * (prev_c + prev_slew_c)
# store new_c/slew_c
band_b = new_b - new_c

x = x * top_level + band_a * a_level + band_b * b_level + new_c * c_level
```

Do not implement Airwindows dither.

- [ ] **Step 4: Run parity at 44.1 and 48 kHz**

```bash
python tools/audit_dragon_experiments.py --section body-pear-core
```

Expected: neutral and 48 kHz fixed-vector tests pass; all outputs finite at both supported sample rates.

- [ ] **Step 5: Commit exact Pear core**

```bash
git add tools/dragon_experiments.py tools/audit_dragon_experiments.py
git commit -m "test: add exact PearLite Body core"
```

---

### Task 2: Implement the one-control Body macro and profile grid

**Files:**
- Modify: `tools/dragon_experiments.py`
- Modify: `tools/audit_dragon_experiments.py`

**Interfaces:**
- Produces: `PearBodyProfile`
- Produces: `PearBodyStage(fs: float, body: float, profile: PearBodyProfile)`
- Produces candidate key: `body-pear`
- Produces CLI section: `body-pear`

Use the approved semantic domain:

```text
-1.0 = Lean
 0.0 = Reference
+1.0 = Full
```

Use this exact exploratory profile grid:

```python
LEAN_LMID_DROP = (0.10, 0.20, 0.30)
LEAN_BASS_DROP = (0.00, 0.05, 0.10)
FULL_LMID_RISE = (0.05, 0.10)
FULL_BASS_RISE = (0.025, 0.05)
BODY_POSITIONS = (-1.0, -0.5, 0.0, 0.5, 1.0)
```

- [ ] **Step 1: Write failing macro-neutral and direction checks**

Require exact neutral parameter mapping:

```python
profile = PearBodyProfile(0.20, 0.05, 0.10, 0.05)
stage = PearBodyStage(48000.0, body=0.0, profile=profile)
assert stage.parameters == (0.5, 0.5, 0.5, 0.5)
```

Require Lean to reduce LMid at least as much as Bass in normalized parameter units, and Full to increase both no more than their profile values.

- [ ] **Step 2: Run and verify failure**

```bash
python tools/audit_dragon_experiments.py --section body-pear
```

Expected: FAIL because macro interfaces are absent.

- [ ] **Step 3: Implement asymmetric Body mapping**

Define:

```python
@dataclass(frozen=True)
class PearBodyProfile:
    lean_lmid_drop: float
    lean_bass_drop: float
    full_lmid_rise: float
    full_bass_rise: float
```

Map Body:

```python
def body_parameters(body: float, profile: PearBodyProfile):
    body = max(-1.0, min(1.0, body))
    high = 0.5
    hmid = 0.5
    if body < 0.0:
        depth = -body
        lmid = 0.5 - depth * profile.lean_lmid_drop
        bass = 0.5 - depth * profile.lean_bass_drop
    else:
        lmid = 0.5 + body * profile.full_lmid_rise
        bass = 0.5 + body * profile.full_bass_rise
    return high, hmid, lmid, bass
```

Construct an internal exact `PearLiteStage` from those four parameters. No other band is touched.

- [ ] **Step 4: Run the 36-profile grid for finite output and exact Body=0 null**

There are `3*3*2*2 = 36` profiles. At both sample rates, require every profile to be finite at all five Body positions and every `Body=0` profile to null against the no-Body experiment path below `1e-12` on a deterministic no-hiss/no-W&F fixture.

```bash
python tools/audit_dragon_experiments.py --section body-pear
```

Expected: all profiles stable and all neutral nulls pass.

- [ ] **Step 5: Commit Body macro**

```bash
git add tools/dragon_experiments.py tools/audit_dragon_experiments.py
git commit -m "test: add Pear-derived Dragon Body macro"
```

---

### Task 3: Add Body FR, phase/group-delay, headroom, and cost evidence

**Files:**
- Modify: `tools/dragon_experiments.py`
- Modify: `tools/audit_dragon_experiments.py`

**Interfaces:**
- Produces: `project_tone_complex(...) -> complex`
- Produces: `measure_group_delay(engine_factory, fs, center_hz, delta_hz=2.0) -> float`
- Produces: `measure_body_profile(profile, fs) -> dict`
- Produces CLI section: `body-metrics`

- [ ] **Step 1: Write failing complex-projection sanity checks**

For a coherent 1 kHz sine at phase `0.37 rad`, direct complex projection must recover amplitude within `1e-6 dB` and phase within `1e-6 rad` after wrapping to `[-pi, pi]`.

- [ ] **Step 2: Run and verify failure**

```bash
python tools/audit_dragon_experiments.py --section body-metrics
```

Expected: FAIL because phase/group-delay helpers are absent.

- [ ] **Step 3: Implement phase/group-delay measurements**

Use direct complex projection. For group delay at center frequency `f`, measure output/input phase at `f-delta` and `f+delta`, unwrap the phase difference into `[-pi, pi]`, then:

```python
group_delay_seconds = -(phase_hi - phase_lo) / (2.0 * math.pi * (2.0 * delta_hz))
```

Measure centers `(80, 100, 150, 200, 300, 500, 1000) Hz`.

- [ ] **Step 4: Measure every Body profile at Lean/Reference/Full**

For each profile/sample rate report:

- FR at `50/80/100/150/200/300/500/1000 Hz`;
- exact neutral null error;
- group delay at the seven centers above;
- peak pre-limiter and limiter rate in full DRAGON;
- state count: `3 filters * 8 stages * 2 states * 2 channels = 96 scalar history states` for full Pear, plus fixed coefficient/level scalars;
- primitive arithmetic estimate per stereo frame based on the implemented loop;
- Python relative timing using `time.perf_counter()` over 48000 stereo samples, repeated 5 times, reporting median only as a local relative proxy, never as Android CPU truth.

- [ ] **Step 5: Identify useful non-dominated Body profiles**

A Body profile is considered dominated only when another profile provides:

- at least as much reduction at 150/200/300 Hz at `Body=-1`;
- no more deep-bass reduction at 50 Hz;
- no greater absolute group-delay deviation at 100/200/300 Hz;
- no greater peak-pre-limiter value;
- and is strictly better in at least one of those dimensions.

Keep `body-none` in the report.

- [ ] **Step 6: Run and commit Body metrics**

```bash
python tools/audit_dragon_experiments.py --section body-metrics --json-out /tmp/dragon-body-results.json
git add tools/dragon_experiments.py tools/audit_dragon_experiments.py
git commit -m "test: measure Dragon Pear Body profiles"
```

---

### Task 4: Add explicit selection state with a safe baseline default

**Files:**
- Create: `tools/dragon_experiment_selection.json`
- Modify: `tools/dragon_experiments.py`
- Modify: `tools/audit_dragon_experiments.py`

**Interfaces:**
- Produces: `load_selection(path) -> dict`
- Produces CLI section: `selection`

- [ ] **Step 1: Create the safe default selection file**

Create exactly:

```json
{
  "lf": {
    "key": "none",
    "params": {}
  },
  "hf": {
    "key": "current-s6",
    "params": {}
  },
  "body": {
    "key": "body-none",
    "params": {}
  }
}
```

This file is intentionally conservative. It does not represent the eventual review result.

- [ ] **Step 2: Write selection validation checks**

Require:

- `lf.key` exists in `LF_CANDIDATES`;
- `hf.key` exists in `HF_CANDIDATES`;
- `body.key` exists in `BODY_CANDIDATES`;
- supplied params contain only constructor fields accepted by the chosen candidate factory;
- safe default selection reproduces experiment baseline below `1e-15` in no-hiss/no-W&F parity.

- [ ] **Step 3: Run selection audit**

```bash
python tools/audit_dragon_experiments.py --section selection
```

Expected: exit 0 and baseline parity.

- [ ] **Step 4: Commit safe selection infrastructure**

```bash
git add tools/dragon_experiment_selection.json tools/dragon_experiments.py tools/audit_dragon_experiments.py
git commit -m "test: add Dragon experiment selection gate"
```

---

### Task 5: Review LF/HF/Body evidence and record finalists

**Files:**
- Modify only if evidence supports promotion: `tools/dragon_experiment_selection.json`

**Interfaces:**
- Consumes local reports from:
  - `/tmp/dragon-lf-results.json`
  - `/tmp/dragon-hf-results.json`
  - `/tmp/dragon-body-results.json`

- [ ] **Step 1: Re-run all three evidence reports from the same commit**

```bash
python tools/audit_dragon_experiments.py --section lf --json-out /tmp/dragon-lf-results.json
python tools/audit_dragon_experiments.py --section hf --json-out /tmp/dragon-hf-results.json
python tools/audit_dragon_experiments.py --section body-metrics --json-out /tmp/dragon-body-results.json
```

Expected: all exit 0.

- [ ] **Step 2: Select at most one LF row and at most one HF row**

Selection rule:

- choose only from the report's non-dominated/eligible rows;
- if no row clearly improves its target problem enough to justify added complexity, retain `none` or `current-s6`;
- copy the chosen row's exact registry key and constructor parameters into `tools/dragon_experiment_selection.json`;
- do not combine two HF mechanisms;
- Body remains `body-none` unless a Pear profile demonstrates useful 100–300 Hz authority while preserving neutral null and acceptable deep-bass/group-delay behavior.

This is a reviewer gate, not an automatic script decision.

- [ ] **Step 3: If the safe defaults remain best, make no selection-file commit**

Run:

```bash
git diff -- tools/dragon_experiment_selection.json
```

If empty, record the review conclusion in the session report and continue to Task 6 with baseline selections.

- [ ] **Step 4: If finalists are selected, validate and commit only the selection JSON**

```bash
python tools/audit_dragon_experiments.py --section selection
git add tools/dragon_experiment_selection.json
git commit -m "test: record Dragon numerical finalists"
```

Expected: selection audit exits 0.

- [ ] **Step 5: Do not touch production DSP**

```bash
git diff --exit-code main -- \
  dsp/dragon/dragon.eel \
  dsp/dragon/versions/v1.0.0-absolute-lab-calibration.eel \
  dsp/dragon/metadata.json \
  tools/audit_dragon.py
```

Expected: exit 0.

---

### Task 6: Run the combination elimination matrix

**Files:**
- Modify: `tools/dragon_experiments.py`
- Modify: `tools/audit_dragon_experiments.py`

**Interfaces:**
- Produces: `build_selected_engine(fs, selection, enabled=("lf", "hf", "body"))`
- Produces CLI section: `combination`

- [ ] **Step 1: Write a failing combination-key check**

Require these seven enabled sets exactly:

```python
(
    ("hf",),
    ("body",),
    ("lf",),
    ("hf", "body"),
    ("hf", "lf"),
    ("body", "lf"),
    ("hf", "body", "lf"),
)
```

When a selected category is the baseline/none choice, its enabled set must resolve to the same path rather than inventing processing.

- [ ] **Step 2: Run and verify failure**

```bash
python tools/audit_dragon_experiments.py --section combination
```

Expected: FAIL until combination runner exists.

- [ ] **Step 3: Implement the combination runner**

For each enabled set at 44.1/48 kHz report:

- Challenger coupling span;
- inverse HF sweep response;
- FR at all baseline probes;
- 50/80/100/150/200/300/500/1000 Hz Body/LF response;
- 60 Hz THD and dynamic IMD;
- HF IMD fixtures;
- peak S4/S5/S6/pre-limiter;
- limiter rate;
- stereo integrity;
- state/operation estimate.

Also report the full baseline row.

- [ ] **Step 4: Apply the smallest-sufficient-combination rule**

The script may label a combination `redundant_superset` only when every added category fails to produce a measurable improvement in its own target metric compared with the simpler subset while not improving another approved metric. It must not auto-label a single overall winner.

Concrete example implemented in code:

```python
if metrics["hf+body+lf"]["coupling_span_db"] >= metrics["hf+body"]["coupling_span_db"] \
   and metrics["hf+body+lf"]["lf_peak_pressure_db"] >= metrics["hf+body"]["lf_peak_pressure_db"] - 0.05:
    flags["hf+body+lf"].add("lf_addition_not_demonstrated")
```

Use flags as review evidence only; do not modify selection automatically.

- [ ] **Step 5: Run complete experiment audit and save combination report**

```bash
python tools/audit_dragon.py
python tools/audit_dragon_experiments.py --section combination --json-out /tmp/dragon-combination-results.json
python tools/audit_dragon_experiments.py
```

Expected: all exit 0.

- [ ] **Step 6: Commit combination tooling**

```bash
git add tools/dragon_experiments.py tools/audit_dragon_experiments.py
git commit -m "test: add Dragon combination elimination gate"
```

---

## Plan Acceptance Gate

This plan is complete only when:

1. Exact eight-stage PearLite passes neutral and non-neutral source-derived parity checks.
2. Every Body profile produces an exact `Body=0` neutral null below `1e-12`.
3. FR, group delay, headroom, limiter, state, and relative timing evidence exists for all Body profiles.
4. The selection file begins from a safe current-Dragon baseline and can only reference registered candidates/configs.
5. LF/HF/Body finalist selection is a reviewer decision based on same-commit reports; `NONE/current-s6/body-none` may remain selected.
6. All seven approved combination sets are measured and the smallest-sufficient rule is reported without automatically changing selection.
7. Production Dragon files and `tools/audit_dragon.py` remain unchanged.
8. No candidate `.eel` has been created yet.
9. `python tools/audit_dragon.py` and full `python tools/audit_dragon_experiments.py` exit 0.

After this gate, write a new implementation plan specifically for the numerical finalists' `.eel` on-device prototypes. That later plan must use the exact selected algorithms/configurations rather than reopening the candidate search.
