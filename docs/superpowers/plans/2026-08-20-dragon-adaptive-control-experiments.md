# DRAGON Adaptive Control Experiments Implementation Plan Suite

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan suite task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the approved DRAGON adaptive-control research as four reviewable implementation stages: baseline harness, LF candidates, HF candidates, then Pear Body/combination elimination.

**Architecture:** The existing v1.0.0 audit/model remains authoritative. All experimental code lives in `tools/dragon_experiments.py` and `tools/audit_dragon_experiments.py` until numerical finalists are selected. Production `.eel` work is explicitly deferred to a new post-selection plan.

**Tech Stack:** Python 3 standard library only; EELVault audit conventions; RootlessJamesDSP/JDSP4Linux production constraints remain relevant only to the later `.eel` finalist plan.

**Spec:** `docs/superpowers/specs/2026-08-19-dragon-adaptive-control-experiments-design.md`

## Global Constraints

- Branch: `dragon-adaptive-control-experiments`.
- Frozen during this suite: `dsp/dragon/dragon.eel`, `dsp/dragon/versions/v1.0.0-absolute-lab-calibration.eel`, `dsp/dragon/metadata.json`, and `tools/audit_dragon.py`.
- Standard-library-only experiment tooling.
- 44.1 and 48 kHz are mandatory measurement rates.
- `NONE`/baseline remains eligible in LF, HF, and Body categories.
- No candidate `.eel` is created before the numerical combination gate is complete.
- No automatic script is allowed to promote a production winner.

---

## Execution Order

Execute these plans in order and stop at any failed acceptance gate:

1. `docs/superpowers/plans/2026-08-20-dragon-experiment-harness-baseline.md`
2. `docs/superpowers/plans/2026-08-20-dragon-lf-experiments.md`
3. `docs/superpowers/plans/2026-08-20-dragon-hf-experiments.md`
4. `docs/superpowers/plans/2026-08-20-dragon-body-combination-gate.md`

Do not begin a later plan merely because its code is easy to write. Each preceding plan must pass its own audit and frozen-file check first.

---

## Self-Review Corrections That Are Authoritative

These corrections were found during the plan-suite self-review. They override any contradictory wording in the individual plan snippets.

### Correction 1 — baseline engine delegation

In `DragonExperimentEngine._channel()`, the very first branch must be:

```python
def _channel(self, ch, x, driveLin, makeup, asym, gcomp, da,
             hissGain, trimLin, nz):
    if not self._instrument:
        return super()._channel(
            ch, x, driveLin, makeup, asym, gcomp, da,
            hissGain, trimLin, nz,
        )
    # instrumented/candidate copy of the authoritative path follows
```

Reason: `DragonEngine.process()` calls `self._channel()`, so calling `super().process()` alone does not bypass an overridden `_channel()`. This explicit delegation is required for the `1e-15` baseline parity gate.

When Task 5 of the baseline plan adds explicit instrumentation, the constructor signature becomes:

```python
def __init__(
    self,
    fs,
    *,
    lf_stage=None,
    hf_stage=None,
    body_stage=None,
    instrument: bool = False,
    **kwargs,
):
    super().__init__(fs, **kwargs)
    self.lf_stage = lf_stage
    self.hf_stage = hf_stage
    self.body_stage = body_stage
    self.telemetry = StageTelemetry()
    self._instrument = instrument or any(
        stage is not None for stage in (lf_stage, hf_stage, body_stage)
    )
```

### Correction 2 — ToTape inactive-path assertion

The ToTape-DRAGON experiment intentionally reuses current Dragon's one-pole S6 action to isolate the detector change. At negligible HF envelope its damping cutoff approaches 30 kHz, which is very mild but not an exact time-domain bypass.

Therefore replace the individual HF plan's `-60 dBFS 1 kHz max sample error < 1e-9` assertion with this response assertion:

```python
input_tone = make_sine(48000.0, 1000.0, -60.0, 0.5)
stage = ToTapeHFStage(
    48000.0,
    ToTapeHFConfig(crossover_hz=4000.0, env_gain=4.0),
)
output_tone = [stage.process_sample("L", x) for x in input_tone]
start = int(0.1 * 48000.0)
in_db = amp_to_db(project_tone_amplitude(input_tone, 48000.0, 1000.0, start))
out_db = amp_to_db(project_tone_amplitude(output_tone, 48000.0, 1000.0, start))
assert abs(out_db - in_db) < 0.01
```

This checks that the inactive/low-activity action is negligible at 1 kHz without pretending a 30 kHz one-pole is mathematical identity.

### Correction 3 — Body registry is explicit

The Body plan must define:

```python
BODY_CANDIDATES = {
    "body-none": lambda fs, **params: None,
    "body-pear": make_pear_body_stage,
}
```

`make_pear_body_stage(fs, **params)` validates and constructs `PearBodyProfile` plus `PearBodyStage`. `tools/dragon_experiment_selection.json` may use only these two Body keys during this plan suite.

### Correction 4 — combination LF pressure metric is defined

Where the Body/combination plan uses `lf_peak_pressure_db`, define it exactly as:

```python
lf_peak_pressure_db = amp_to_db(metrics["peak_pre_limiter"])
```

The combination report must include both the raw `peak_pre_limiter` amplitude and this dB representation so redundancy flags operate on a defined quantity.

### Correction 5 — no hidden shared mutable stages across factories

Every registry factory must create a fresh candidate stage/engine instance. Do not store a single stage object in `LF_CANDIDATES`, `HF_CANDIDATES`, or `BODY_CANDIDATES` and reuse it across fixtures, because filter/envelope history would contaminate measurements.

Valid pattern:

```python
LF_CANDIDATES = {
    "none": lambda fs, **params: None,
    "lf-foundation": lambda fs, **params: FoundationGuard(
        fs, FoundationGuardConfig(**params)
    ),
}
```

Invalid pattern:

```python
LF_CANDIDATES = {
    "lf-foundation": FoundationGuard(48000.0, config),
}
```

### Correction 6 — reports are evidence, not tests of taste

Audit exit status covers deterministic correctness, source parity, numerical stability, neutral/null invariants, registry validity, and finite/bounded measurements. Relative sonic metrics such as lower THD, lower coupling span, or better Body response are printed/serialized as evidence and must not make the audit fail merely because a candidate performs worse than baseline. A poor candidate is a valid experimental result and may be rejected by review.

---

## Suite-Level Verification

After each plan, run:

```bash
python tools/audit_dragon.py
python tools/audit_dragon_experiments.py
```

and verify frozen files:

```bash
git diff --exit-code main -- \
  dsp/dragon/dragon.eel \
  dsp/dragon/versions/v1.0.0-absolute-lab-calibration.eel \
  dsp/dragon/metadata.json \
  tools/audit_dragon.py
```

At the end of the full plan suite, save same-commit local evidence:

```bash
python tools/audit_dragon_experiments.py --section lf --json-out /tmp/dragon-lf-results.json
python tools/audit_dragon_experiments.py --section hf --json-out /tmp/dragon-hf-results.json
python tools/audit_dragon_experiments.py --section body-metrics --json-out /tmp/dragon-body-results.json
python tools/audit_dragon_experiments.py --section combination --json-out /tmp/dragon-combination-results.json
```

The next design/plan gate is **not** “merge these experiments.” It is: review the four evidence reports, record numerical finalists or baseline/NONE outcomes, and then write a separate `.eel` on-device prototype plan for only those selected mechanisms.
