# DRAGON HF Dynamic-Control Preliminary Results

## Status

This document records the first source-validated and full-DRAGON numerical results for the HF replacement experiment. It is **not** a production-selection document. `current-s6` remains eligible, and production `dsp/dragon/dragon.eel` is unchanged.

The focused implementation lives in:

- `tools/dragon_hf_experiments.py`
- `tools/audit_dragon_hf_experiments.py`

## Source-parity gates

- Exact Sinew core at 48 kHz / amount 0.5 matches the approved source-derived output vector to floating-point equality in the sandbox validation.
- Acceleration-DRAGON at 48 kHz / limit 0.32 matches both the approved source-derived output vector and detector-sense vector to floating-point equality while omitting Acceleration2's unconditional final 20 kHz low-pass.
- The ToTape-DRAGON 3x3 crossover/env-gain grid exceeds the required 20x equal-level 10 kHz-vs-60 Hz detector selectivity at both 44.1 and 48 kHz. The observed minimum ratio in the sandbox validation was about 40.5x.

## Critical decomposition: S6 coupling vs tape-core coupling

The canonical regression fixture keeps the 10 kHz probe fixed while sweeping only 60 Hz from -30 to 0 dBFS.

At 48 kHz:

| Path | Coupling span |
|---|---:|
| Current S6 | 9.734 dB |
| No-S6 passthrough reference | 5.902 dB |
| Acceleration 0.32 | 5.873 dB |
| ToTape 2500 Hz / gain 2 | 5.897 dB |
| Sinew 0.2 | 5.902 dB |

At 44.1 kHz:

| Path | Coupling span |
|---|---:|
| Current S6 | 9.853 dB |
| No-S6 passthrough reference | 6.036 dB |
| Acceleration 0.32 | 6.011 dB |
| ToTape 2500 Hz / gain 2 | 6.032 dB |
| Sinew 0.2 | 6.036 dB |

Interpretation: approximately 3.8 dB of the full-path bass-to-HF attenuation span is attributable to current S6's broadband-envelope coupling. The remaining ~5.9-6.0 dB is present even with S6 replaced by an identity stage and therefore belongs to the upstream nonlinear tape path rather than to the HF damping detector alone. The HF replacement should not be required to eliminate that residual behavior.

## Inverse HF responsiveness

The inverse fixture holds LF at -12 dBFS and sweeps 10 kHz from -42 to -12 dBFS. The metric below is the change in 10 kHz transfer efficiency from the quietest to hottest HF probe; more-negative values mean stronger level-dependent HF softening.

| Path | 44.1 kHz | 48 kHz |
|---|---:|---:|
| Current S6 | -2.454 dB | -2.586 dB |
| No-S6 reference | -0.670 dB | -0.773 dB |
| Acceleration 0.32 | -2.323 dB | -2.613 dB |
| ToTape 2500 / 2 | -2.252 dB | -2.417 dB |
| Sinew 0.2 | -1.020 dB | -1.069 dB |

Acceleration 0.32 is notable because it nearly reproduces current S6's desired HF-level-dependent efficiency loss while reducing the unwanted LF-driven coupling to the no-S6 floor.

## IMD comparison

Projected sidebands are relative to the 10 kHz carrier. More-negative is cleaner.

### 60 Hz + 10 kHz fixture

| Path | 44.1 kHz worst sideband | 48 kHz worst sideband |
|---|---:|---:|
| Current S6 | -35.39 dB | -35.38 dB |
| Sinew 0.2 | -35.42 dB | -35.41 dB |
| Acceleration 0.32 | **-35.93 dB** | **-35.99 dB** |
| ToTape 2500 / 2 | -35.35 dB | -35.34 dB |

### 1 kHz + 10 kHz fixture

| Path | 44.1 kHz worst sideband | 48 kHz worst sideband |
|---|---:|---:|
| Current S6 | -39.25 dB | -39.15 dB |
| Sinew 0.2 | -39.64 dB | -39.57 dB |
| Acceleration 0.32 | **-40.13 dB** | **-39.90 dB** |
| ToTape 2500 / 2 | -39.47 dB | -39.37 dB |

Sinew 0.3 was not promoted because its 48 kHz 1 kHz+10 kHz lower sideband worsened to roughly -32.9 dB in the same preliminary measurement, showing that the coarse Sinew amount range can cross into noticeably stronger nonlinear action quickly.

## Small-signal HF response

At -60 dBFS / 48 kHz:

| Frequency | Current S6 | No-S6 / Acceleration-inactive | ToTape 2500/2 |
|---|---:|---:|---:|
| 1 kHz | +1.979 dB | +1.980 dB | approximately current |
| 5 kHz | -1.717 dB | -1.679 dB | approximately current |
| 10 kHz | -3.613 dB | -3.479 dB | approximately current |
| 14 kHz | -5.778 dB | -5.552 dB | approximately current |
| 18 kHz | -7.836 dB | -7.533 dB | approximately current |

Removing current S6's inactive 30 kHz one-pole changes 18 kHz by only about +0.30 dB. Therefore the previously observed overly-dark static 18 kHz response is not primarily caused by S6; a later calibration audit must examine the stacked replay/record EQ independently.

Do **not** interpret digital 0 dBFS as the cassette deck's hardware 0 dB reference level. The current README's -6 dB @18 kHz hardware target cannot be directly compared to a 0 dBFS sine without first defining the digital-to-reference operating-level mapping.

## Transient character at 48 kHz

Representative 10 kHz burst settled RMS:

| Path | Settled RMS |
|---|---:|
| Current S6 | 0.1107 |
| Acceleration 0.32 | 0.1596 |
| ToTape 2500/2 | 0.1188 |
| Sinew 0.2 | 0.1238 |

Representative impulse peak:

| Path | Peak |
|---|---:|
| Current S6 | 0.3462 |
| Acceleration 0.32 | 0.1903 |
| ToTape 2500/2 | 0.3464 |
| Sinew 0.2 | 0.1500 |

Acceleration therefore has a distinct profile: it is more open on sustained HF energy while constraining very rapid waveform changes more strongly. ToTape preserves current Dragon's sustained-HF and impulse character much more closely.

## Candidate disposition

### Primary finalist A — Acceleration 0.32

Keep for the combination gate because it:

- nearly eliminates S6-specific LF-to-HF coupling;
- preserves almost exactly the current HF-level-dependent compression strength;
- improves the measured IMD sidebands;
- has no per-sample transcendental in the core action once coefficients are initialized;
- produces a more open sustained-HF / stronger-edge-control presentation that may better separate "brightness" from "harshness".

Risk: transient and sustained-HF behavior differs materially from current S6, so on-device listening and calibration matter.

### Primary finalist B — ToTape 2500 Hz / env gain 2

Keep as the conservative/reference-like finalist because it:

- nearly eliminates S6-specific LF-to-HF coupling;
- retains strong HF-level responsiveness;
- preserves current small-signal FR and impulse character closely;
- changes the architecture mainly by replacing the detector rather than the action.

Risk: the dynamic one-pole coefficient requires expensive per-sample coefficient work in the direct experiment implementation and will need optimization if selected for mobile EEL2.

### Secondary only — Sinew

Sinew remains useful research evidence but is no longer a primary production finalist. Amount 0.2 is too close to no-S6 behavior in the inverse-HF fixture, while 0.3 crosses into substantially stronger nonlinear/transient effects. An intermediate ~0.25 brackets the desired inverse-HF behavior in exploratory testing, but Acceleration 0.32 currently reaches the same architectural goal with cleaner measured behavior and a more favorable transcendental-cost profile.

## Next gate

Carry both primary HF finalists into the Pear Body experiment:

1. Acceleration 0.32
2. ToTape 2500 Hz / gain 2
3. current S6 baseline

Body should be evaluated independently first, then against both HF finalists. The combination gate—not this preliminary report—decides whether either HF replacement should reach an on-device `.eel` candidate.
