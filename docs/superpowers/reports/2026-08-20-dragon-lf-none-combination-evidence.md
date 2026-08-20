# DRAGON LF=NONE Combination Gate Evidence

## Decision scope

This report records the first complete numerical combination gate after the isolated LF, HF, and Pear Body experiments.

Production DRAGON remains unchanged. The persistent selection file remains at the safe baseline:

- LF: `none`
- HF: `current-s6`
- Body: `body-none`

This report does **not** promote a production implementation. It identifies the numerical finalists to carry into the later on-device `.eel` round.

## Candidates in this gate

HF:

- `current-s6` — v1.0.0 control
- `hf-acceleration` — Acceleration-DRAGON, `limit=0.32`
- `hf-totape` — ToTape-DRAGON, `crossover_hz=2500`, `env_gain=2`

Body:

- Reference (`Body=0` / no Body stage)
- Half Lean (`Body=-0.5`)
- Full Lean (`Body=-1.0`)

LF is fixed to `NONE` for all rows.

Refined Pear Body profile:

- Lean LMid drop: `0.150`
- Lean Bass compensation: `+0.079` (stored as `lean_bass_drop=-0.079`)
- Full LMid rise: `0.100`
- Full Bass rise: `0.025`

## Canonical LF -> fixed-HF coupling

Metric: span of the 10 kHz output delta while 60 Hz input is swept from -30 to 0 dBFS with the 10 kHz probe fixed.

Lower is better for this architectural test.

### 44.1 kHz

| HF path | Body | Coupling span (dB) |
|---|---|---:|
| Current S6 | Reference | 9.702 |
| Current S6 | Half Lean | 9.699 |
| Current S6 | Full Lean | 9.698 |
| Acceleration 0.32 | Reference | **5.939** |
| Acceleration 0.32 | Half Lean | **5.935** |
| Acceleration 0.32 | Full Lean | **5.935** |
| ToTape 2500/2 | Reference | 5.956 |
| ToTape 2500/2 | Half Lean | 5.953 |
| ToTape 2500/2 | Full Lean | 5.953 |

### 48 kHz

| HF path | Body | Coupling span (dB) |
|---|---|---:|
| Current S6 | Reference | 9.757 |
| Current S6 | Half Lean | 9.755 |
| Current S6 | Full Lean | 9.754 |
| Acceleration 0.32 | Reference | **5.934** |
| Acceleration 0.32 | Half Lean | **5.931** |
| Acceleration 0.32 | Full Lean | **5.931** |
| ToTape 2500/2 | Reference | 5.956 |
| ToTape 2500/2 | Half Lean | 5.953 |
| ToTape 2500/2 | Full Lean | 5.953 |

### Interpretation

Body is effectively orthogonal to the HF detector/action choice: changing Body from Reference to Full Lean changes the coupling span by only a few thousandths of a dB.

Both candidate HF paths remove roughly 3.75-3.83 dB of avoidable S6-induced bass-to-HF coupling. Acceleration is consistently slightly better than ToTape on this metric.

Previous no-S6 decomposition work measured about 5.9 dB of residual full-path coupling from the upstream linked tape compression/saturation behavior itself. The candidate values therefore sit very close to the practical floor available without redesigning the tape core.

## Inverse HF-responsiveness test

Metric: change in 10 kHz output efficiency while the 10 kHz input is swept upward with LF fixed. Negative values mean the processor increasingly restrains the HF probe as HF input rises.

### 44.1 kHz

| HF path | Reference | Half Lean | Full Lean |
|---|---:|---:|---:|
| Current S6 | -2.562 | -2.562 | -2.562 |
| Acceleration 0.32 | **-2.394** | **-2.394** | **-2.394** |
| ToTape 2500/2 | -2.325 | -2.325 | -2.325 |

### 48 kHz

| HF path | Reference | Half Lean | Full Lean |
|---|---:|---:|---:|
| Current S6 | -2.564 | -2.564 | -2.564 |
| Acceleration 0.32 | **-2.572** | **-2.572** | **-2.572** |
| ToTape 2500/2 | -2.378 | -2.378 | -2.378 |

Acceleration retains at least 93% of the current S6 inverse-response strength at 44.1 kHz and approximately matches/slightly exceeds it at 48 kHz. ToTape remains deliberately more conservative but still retains more than 90% of the current response under the gate used by the formal audit.

## Refined Body response

Full Lean (`Body=-1`) with the cross-rate-refined Pear profile:

| Frequency | 44.1 kHz | 48 kHz |
|---:|---:|---:|
| 50 Hz | -0.064 dB | +0.066 dB |
| 80 Hz | -2.166 | -2.008 |
| 100 Hz | -3.179 | -3.035 |
| 150 Hz | -4.512 | -4.439 |
| 200 Hz | -4.827 | -4.820 |
| 300 Hz | -4.322 | -4.396 |
| 500 Hz | -2.667 | -2.776 |
| 1 kHz | -0.637 | -0.691 |

The intended result is achieved: true 50 Hz bass remains approximately unchanged while the 100-300 Hz body region receives meaningful corrective authority.

## Deterministic stress headroom

No LF=NONE combination hit the output limiter in the 8192-frame deterministic stress fixture at either rate.

Representative pre-limiter peaks:

### 44.1 kHz

| HF path | Reference | Half Lean | Full Lean |
|---|---:|---:|---:|
| Current S6 | 0.3391 | 0.3380 | 0.3369 |
| Acceleration 0.32 | 0.5044 | 0.5057 | 0.5284 |
| ToTape 2500/2 | 0.3393 | 0.3382 | 0.3371 |

### 48 kHz

| HF path | Reference | Half Lean | Full Lean |
|---|---:|---:|---:|
| Current S6 | 0.3250 | 0.3241 | 0.3231 |
| Acceleration 0.32 | 0.4979 | 0.4872 | 0.5058 |
| ToTape 2500/2 | 0.3252 | 0.3243 | 0.3233 |

Acceleration is the more open/high-peak HF path, but remains comfortably below the limiter in this deterministic fixture.

## Foundation-Guard necessity gate

A narrow second-round check was run only to decide whether the LF guard solves a remaining problem after HF + Body.

Representative safety-tuned Foundation configuration:

- detector: 120 Hz
- attack: 5 ms
- release: 120 ms
- min HP: 5 Hz
- max HP: 60 Hz
- revised envelope floor tested around 0.30

At 48 kHz the safety-tuned guard is almost inactive at ordinary LF levels:

- -12 dBFS / 60 Hz: about -0.03 dB transfer
- -6 dBFS / 60 Hz: about -0.08 dB transfer
- -3 dBFS / 60 Hz: about -0.8 dB transfer
- 0 dBFS / 60 Hz: about -3.0 dB transfer

It can remove limiter activity from a pathological full-scale 60 Hz fixture, but the normal deterministic combination stress already has zero limiter hits without the guard, and DRAGON already contains a soft-limiter safety stage.

### LF decision

**HOLD Foundation Guard. Do not include it in the first on-device finalists.**

Reason: its remaining benefit is predominantly extreme-bass protection, while HF redesign + Pear Body already solve the identified architectural coupling and playback-body problems. Adding Foundation now would violate the minimal-combination rule unless device listening demonstrates a remaining LF-headroom failure.

## Numerical review decision

### Primary on-device candidate

`LF=NONE + HF=Acceleration 0.32 + refined Pear Body`

Rationale:

1. lowest coupling span of the tested HF finalists at both rates;
2. preserves strong HF-level-dependent behavior;
3. numerically independent from Body;
4. prior isolated HF tests showed improved IMD behavior;
5. no limiter activity in the deterministic combination stress fixture.

### Conservative alternate

`LF=NONE + HF=ToTape 2500/2 + refined Pear Body`

Rationale:

1. nearly the same coupling correction;
2. more closely preserves current DRAGON sustained-HF/impulse character;
3. useful A/B candidate if Acceleration sounds too open or changes transient character perceptually.

### Not promoted to first device round

- current S6: remains the baseline/control;
- Sinew: hold;
- Foundation Guard: hold;
- Stone guard: hold;
- literal Highpass/Tight: reject for production reference path.

## Next gate

Create **two isolated on-device `.eel` finalists**, not a production replacement:

1. Acceleration + refined Pear Body
2. ToTape + refined Pear Body

Both must retain the eight-control target by repurposing `LF Contour` as `Body`. The production `dsp/dragon/dragon.eel` must remain untouched until device testing and final review are complete.
