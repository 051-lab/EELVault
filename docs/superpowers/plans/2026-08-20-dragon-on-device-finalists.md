# DRAGON On-Device Finalists Implementation Plan

> **Execution method:** test-driven. Create the candidate audit before either `.eel` finalist, verify the candidate paths are absent/RED, then implement only enough candidate code to satisfy the audit and numerical model gates.

**Goal:** Build two experiment-only RootlessJamesDSP LiveProg finalists from frozen DRAGON v1.0.0 for device A/B testing, without modifying production `dsp/dragon/dragon.eel`.

**Numerical evidence:** `docs/superpowers/reports/2026-08-20-dragon-lf-none-combination-evidence.md`

## Finalists

1. `dsp/dragon/experiments/dragon-acceleration-body.eel`
   - LF guard: NONE
   - S6 replacement: Acceleration-DRAGON, `limit=0.32`
   - Body: refined eight-stage Pear macro

2. `dsp/dragon/experiments/dragon-totape-body.eel`
   - LF guard: NONE
   - S6 replacement: ToTape-DRAGON, crossover `2500 Hz`, envelope gain `2`
   - Body: refined eight-stage Pear macro

## Shared UI contract

Both finalists retain exactly eight controls:

```text
Record Drive
Tape Bias
Tape Compression
Wow & Flutter
Body
HF Rolloff
Tape Hiss
Output Trim
```

`LF Contour` is replaced by:

```eel
body:0<-1,1,0.05>Body (Lean < Reference > Full)
```

The historical v1.0.0 `LF Contour=1 dB` reference setting becomes a fixed replay calibration (`rbj_peak(50, 0.95, 1)`). `Body=0` must bypass Pear processing exactly so the Body control does not alter the reference playback curve.

## Shared Pear Body implementation

- Position: after S8 HF rolloff shelf, before S9 hiss.
- Eight Pear stages.
- High/HMid neutral.
- Full Lean (`body=-1`):
  - LMid parameter `0.35` (`0.15` drop)
  - Bass parameter `0.579` (`+0.079` compensation)
- Full Full (`body=+1`):
  - LMid parameter `0.60`
  - Bass parameter `0.525`
- Smooth Body at block/control rate.
- If smoothed Body is effectively zero, bypass the Pear loop.
- Pear history occupies `mem[128..223]`; existing W&F memory remains `mem[0..127]`.

## Acceleration finalist

Replace current S6 one-pole damping with the source-derived Acceleration2 core already validated by the Python experiment:

- `limit=0.32`
- `intensity = limit^3 * 32`
- sample-rate-aware spacing, max 16
- detector from signed-square difference curvature
- dynamic blend toward the first Acceleration2 smoothing biquad
- **omit** Acceleration2's unconditional final 20 kHz output low-pass
- **omit** Airwindows dither/wet-mix infrastructure
- independent L/R detector/smoother state
- generic 64-sample per-channel history rings so spacing remains sample-rate-aware

Memory layout:

- W&F: `0..127`
- Pear: `128..223`
- Acceleration L history: `224..287`
- Acceleration R history: `288..351`

## ToTape finalist

Replace current S6 one-pole damping with the validated HF-residual detector/action:

- crossover `2500 Hz`
- per-channel one-pole HF residual detector
- envelope gain `2`
- attack `2 ms`
- release `50 ms`
- dynamic damping map `30 kHz -> 7 kHz`
- detector independent of the S4 broadband envelope
- independent L/R detector/action state

No additional memory-array region is needed beyond Pear.

## TDD / audit requirements

Create `tools/audit_dragon_device_candidates.py` first. It must fail while the candidate files are absent, then require:

1. both candidate files exist;
2. both contain native `@init/@slider/@block/@sample` sections;
3. exactly eight slider declarations;
4. `body:0<-1,1,0.05>` exists and `bump:` does not;
5. fixed 1 dB reference head contour is present;
6. Pear memory/state constants and refined profile constants are present;
7. Pear processing appears after S8 HF shelf and before S9 hiss;
8. Acceleration candidate contains `limit=0.32`, curvature detector, dynamic smoothing, and no current S6 broadband-envelope damping statement;
9. ToTape candidate contains 2500 Hz residual detection, envelope gain 2, 2/50 ms ballistics, and no dependence on linked S4 `env` for its HF detector;
10. candidate descriptions clearly say experimental/finalist;
11. production `dsp/dragon/dragon.eel`, archive, metadata, and `tools/audit_dragon.py` remain untouched relative to `main`;
12. numerical Python finalists still satisfy the LF=NONE combination audit.

## Execution tasks

### Task 1 — RED audit

Create `tools/audit_dragon_device_candidates.py`. Before candidate creation, verify both candidate paths are absent and therefore the candidate audit cannot pass.

### Task 2 — Acceleration finalist

Create `dsp/dragon/experiments/dragon-acceleration-body.eel` from v1.0.0 with only the approved S6/UI/Body changes. No Foundation, Stone, Sinew, or ToTape code.

### Task 3 — ToTape finalist

Create `dsp/dragon/experiments/dragon-totape-body.eel` from v1.0.0 with only the approved S6/UI/Body changes. No Foundation, Stone, Sinew, or Acceleration code.

### Task 4 — verification

Run/verify where available:

```bash
python tools/audit_dragon.py
python tools/audit_dragon_hf_experiments.py
python tools/audit_dragon_body_experiments.py
python tools/audit_dragon_combination_experiments.py
python tools/audit_dragon_device_candidates.py
```

Then verify frozen production files have no branch diff.

## Promotion rule

Neither candidate is production DRAGON. Device listening must compare:

- v1.0.0 control
- Acceleration + Body finalist
- ToTape + Body finalist

The primary listening questions are:

1. Does bass cease making the presentation artificially dark?
2. Does Body around `-0.5` solve the Challenger low-mid problem without thinning real bass?
3. Does Acceleration sound too open or alter transient attack compared with ToTape?
4. Does ToTape retain too much of current S6's dark character?
5. Is eight-stage Pear stable and smooth enough on the target Android device?

Only after that A/B round may one candidate be proposed for production integration.
