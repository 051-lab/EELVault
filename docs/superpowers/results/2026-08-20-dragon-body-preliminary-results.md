# DRAGON Pear Body Preliminary Results

## Status

This document records the numerical Pear Body findings before the final combination/promotion gate. Production `dsp/dragon/dragon.eel` remains unchanged.

The exact experiment implementation lives in:

- `tools/dragon_body_experiments.py`
- `tools/audit_dragon_body_experiments.py`

## Exact Pear core validation

The full eight-stage PearLite core was reconstructed from the Airwindows source equations without dither.

- Neutral High/HMid/LMid/Bass parameters at `0.5/0.5/0.5/0.5` reconstruct the input to floating-point noise.
- The approved non-neutral 48 kHz source-derived vector at `0.5/0.5/0.25/0.45` matches exactly in the sandbox reconstruction.
- `Body = 0` explicitly returns the original sample after warming the internal Pear state, guaranteeing a true reference/bypass output rather than merely relying on approximate neutral reconstruction.

## Why the approved Lean grid needed refinement

Pear's nominal `LMid` region is broad. Reducing LMid alone also reduces true bass.

For example, with full eight-stage Pear and LMid drop `0.10` while Bass remains neutral, the approximate 48 kHz response is:

- 50 Hz: -1.17 dB
- 150 Hz: -3.02 dB
- 200 Hz: -3.09 dB
- 300 Hz: -2.72 dB

That is useful body control, but too much collateral 50 Hz loss for the intended DRAGON `Body` macro.

## Evidence-driven compensated Lean mapping

The solution is to lower Pear LMid while applying a small Pear Bass compensation on the Lean side.

The first compensated candidate used:

```text
Lean LMid drop: 0.150
Lean Bass compensation: +0.075
Full LMid rise: 0.100
Full Bass rise: 0.025
```

It was excellent at 48 kHz but left about -0.153 dB at 50 Hz at 44.1 kHz, just outside the explicit +/-0.10 dB cross-rate preservation gate.

A small cross-rate refinement produced the current Body finalist profile:

```text
Lean LMid drop: 0.150
Lean Bass compensation: +0.079
Full LMid rise: 0.100
Full Bass rise: 0.025
```

The internal `PearBodyProfile` representation stores the compensation as `lean_bass_drop = -0.079`.

### Full Lean response — refined profile

At 44.1 kHz:

| Frequency | Relative response |
|---|---:|
| 50 Hz | -0.064 dB |
| 80 Hz | -2.166 dB |
| 100 Hz | -3.179 dB |
| 150 Hz | -4.512 dB |
| 200 Hz | -4.827 dB |
| 300 Hz | -4.322 dB |
| 500 Hz | -2.667 dB |
| 1 kHz | -0.637 dB |

At 48 kHz:

| Frequency | Relative response |
|---|---:|
| 50 Hz | +0.066 dB |
| 80 Hz | -2.008 dB |
| 100 Hz | -3.035 dB |
| 150 Hz | -4.439 dB |
| 200 Hz | -4.820 dB |
| 300 Hz | -4.396 dB |
| 500 Hz | -2.776 dB |
| 1 kHz | -0.691 dB |

This meets the intended behavior much better than a normal bass control: true 50 Hz weight is approximately preserved while the upper-bass/low-mid body region receives substantial corrective authority.

At `Body = -0.5`, the same macro produces roughly half the correction, making it a practical everyday adaptation rather than only an extreme rescue setting.

## Full side

The positive side intentionally remains gentler. At 48 kHz / `Body = +1`, the current full-side mapping is approximately:

- 50 Hz: +1.7 dB
- 80 Hz: +2.3 dB
- 100 Hz: +2.5 dB
- 150-200 Hz: about +2.8 dB
- 300 Hz: about +2.4 dB
- 1 kHz: below +0.4 dB

This retains DRAGON's ability to sound fuller without making the macro a conventional deep-bass boost.

## Phase / group-delay behavior

The refined full-Lean profile remains sub-millisecond through the manipulated range.

Approximate 48 kHz group delay:

- 80 Hz: -0.238 ms
- 100 Hz: -0.452 ms
- 150 Hz: -0.536 ms
- 200 Hz: -0.435 ms
- 300 Hz: -0.230 ms
- 500 Hz: -0.037 ms
- 1 kHz: +0.025 ms

At 44.1 kHz the maximum magnitude remains around 0.55 ms. No large phase-delay penalty was found.

## Independence from the HF mechanism

Body is inserted after replay EQ and before generated hiss. It does not alter record drive, tape compression, saturation, or the HF candidate detector/action.

In full-DRAGON numerical checks, the relative Body correction was effectively the same with:

1. current S6;
2. Acceleration 0.32;
3. ToTape 2500 Hz / env gain 2.

That independence was confirmed again by the first combination chunks at 48 kHz / full Lean:

| HF path | LF-to-HF coupling span |
|---|---:|
| Current S6 | 9.754 dB |
| Acceleration 0.32 | 5.929 dB |
| ToTape 2500/2 | 5.950 dB |

The Body stage therefore does not undo the HF architecture fix.

## Headroom interaction

A 4,096-frame deterministic full-range stress chunk at 48 kHz / `Body=-1` produced:

| HF path | Peak pre-limiter | Limiter hits |
|---|---:|---:|
| Current S6 | 0.3231 | 0 |
| Acceleration 0.32 | 0.5058 | 0 |
| ToTape 2500/2 | 0.3233 | 0 |

The higher Acceleration peak reflects its more-open sustained-HF behavior already observed in the HF report, not a Body-specific headroom failure. All three retain substantial output-stage margin in this fixture.

## CPU / state concern

Full eight-stage Pear uses:

```text
3 filters x 8 stages x 2 states x 2 channels = 96 history states
```

The experiment implementation estimates about 528 primitive arithmetic operations per stereo frame before Python overhead. It is therefore one of the heavier proposed DRAGON additions and must not be accepted on response shape alone.

### Four-stage optimization candidate

Only after the exact eight-stage response had been established, a retuned four-stage Pear was explored as a mobile optimization.

For the refined full-Lean eight-stage target:

```text
8-stage target: High=.5, HMid=.5, LMid=.350000, Bass=.579000
4-stage fit:    High=.5, HMid=.5, LMid~.216872, Bass~.655226
```

Across 20 Hz-20 kHz at both 44.1 and 48 kHz, the retuned four-stage Lean fit is approximately:

- magnitude RMS error: ~0.043 dB;
- maximum magnitude error: <0.10 dB;
- phase RMS error: ~0.36 degrees;
- maximum phase error: <0.80 degrees.

For the full-side target, a four-stage fit around `LMid~0.70799 / Bass~0.55052` is even closer, around 0.01 dB magnitude RMS error.

A four-stage implementation would reduce Pear history from 96 to 48 scalar states and approximately halve the repeated stage work.

**Disposition:** keep eight-stage Pear as the numerical reference. Treat four-stage Pear only as a post-selection mobile optimization candidate. It must pass direct EEL2/on-device parity before replacing the reference implementation.

## Current Body disposition

### Primary Body finalist

```text
Body macro: Pear-derived
Reference: 0.0 exact bypass
Lean LMid authority: 0.150 normalized parameter
Lean Bass compensation: +0.079 normalized parameter
Full LMid rise: 0.100
Full Bass rise: 0.025
Reference implementation: exact eight-stage Pear
```

### UI intent

The production intent remains eight controls total. `LF Contour` would be repurposed as:

```text
Body
Lean  <----  Reference  ---->  Full
-100             0             +100
```

No Bass/LMid/HMid/High Pear controls are exposed.

## Next gate

Run the combination matrix with **LF = NONE first**:

- current S6 + no Body / Lean Body;
- Acceleration 0.32 + no Body / Lean Body;
- ToTape 2500/2 + no Body / Lean Body.

Only after that matrix is reviewed should the provisional Foundation Guard be added. If HF + Body already solves the identified playback-control problem without LF-headroom evidence demanding another mechanism, LF `NONE` wins by simplicity.
