# Material Memory Engine — P0.1 Matter

**Version:** 0.0.1
**Status:** Experimental — internal laboratory prototype
**Type:** Stateful virtual material resonator
**Target:** RootlessJamesDSP / JDSP4Linux
**File:** `materialmemory.eel`

## Description

Material Memory Engine is an original, stateful virtual-material audio processor in development. Audio excites a small internal resonant "material"; the changed material then alters how future audio is processed.

**P0.1 — Matter** is the first laboratory prototype. It exists to answer exactly one question:

> Is the virtual material body itself special enough to build the rest of the processor around?

P0.1 deliberately implements **no** Memory, Charge, Life, Fatigue, Recovery, Fracture, or stereo cross-coupling. Those are future prototypes (P0.2–P0.4). Smuggling them in now would hide weaknesses in the core.

## Signal Flow

```text
Input L/R
  -> Non-finite + denormal input sanitation (soft +/-4 pad)
  -> Body / Edge excitation decomposition (one-pole, 700+500*M Hz)
  -> Six damped two-state modal cells per channel
     p' = r*(c*p - s*q) + drive
     q' = r*(s*p + c*q)
  -> Energy-preserving alternating Givens coupling
     (A: M1<->M2 M3<->M4 M5<->M6 / B: M2<->M3 M4<->M5)
  -> Weighted modal emission (renormalized weights * 2.2)
  -> wet = input + materialGain*modal
  -> Mix (wet/dry) -> Output (dB) -> emergency +/-0.999 containment
  -> Output L/R
```

## Modal Cell

Each of the six modes per channel is a damped two-state oscillator:

```text
p' = r*(c*p - s*q) + drive
q' = r*(s*p + c*q)
```

with `theta = 2*pi*f/Fs`, `c = cos(theta)`, `s = sin(theta)`, and
`r = exp(-6.907755278982137/(T60*Fs))`. The homogeneous oscillator is contractive whenever `0 < r < 1`, so every tail decays to silence when drive stops. All `sin/cos/exp/sqrt/pow` live in control-rate coefficient derivation, never unconditionally in `@sample`.

## Material anchors

The Material control morphs between a **Soft** endpoint and a **Hard** endpoint.

### Soft endpoint (M = 0)

| Mode | Frequency (Hz) | T60 (sec) |
|------|---------------:|----------:|
| M1 | 150 | 0.180 |
| M2 | 285 | 0.150 |
| M3 | 610 | 0.120 |
| M4 | 1180 | 0.090 |
| M5 | 2470 | 0.065 |
| M6 | 5100 | 0.045 |

### Hard endpoint (M = 1)

| Mode | Frequency (Hz) | T60 (sec) |
|------|---------------:|----------:|
| M1 | 170 | 0.260 |
| M2 | 390 | 0.340 |
| M3 | 910 | 0.420 |
| M4 | 1980 | 0.500 |
| M5 | 4370 | 0.580 |
| M6 | 9050 | 0.660 |

Frequency morphs logarithmically between endpoints; T60 morphs with `M^2`. Frequencies are clamped below `0.22 * Fs`.

## Key Parameters

| Parameter | Default | Range | Purpose |
|-----------|---------|-------|---------|
| Excite | 42 % | 0..100 | how strongly input activates the material |
| Material | 48 % | 0..100 | soft ↔ hard internal matter continuum |
| Mix | 65 % | 0..100 | dry / material balance |
| Output | 0 dB | -12..+6 | final trim |

## Energy-preserving coupling

Neighboring modes exchange state through Givens rotations:

```text
a' = C*a - S*b
b' = S*a + C*b
```

with `C = cos(kappa)`, `S = sin(kappa)`. This preserves `a^2 + b^2` (and `q^2`) to floating-point precision per pair. The lattice alternates between two topologies each sample (A: M1↔M2, M3↔M4, M5↔M6; B: M2↔M3, M4↔M5), with direction multipliers `[+0.70, -1.00, +1.25, -0.90, +1.15]` at `1.5 + 10*M^2` Hz. The coupling redistributes modal state — it never manufactures energy.

## Deviations from the supplied design (documented in source, D1–D10)

| # | Supplied design | Implemented | Why |
|---|-----------------|-------------|-----|
| D1 | Drive `(1-r)` | `(1-r)` kept (revised) | First tried `sqrt(1-r*r)`; measurement proved its resonant gain grows without bound at low damping (18 dB spread, max 95.8). `(1-r)` normalizes each mode's *resonant* amplitude to ~0.5 (measured 0.5000–0.5009, 0.01 dB across the full grid). Not a DC-gain claim |
| D2 | Output weights `[.26 .24 .22 .18 .14 .10]` | `[.34 .31 .29 .24 .18 .13]` (sum 1.49) | Draft ratios scaled ~1.3 for audibility. **Sum is 1.49, not 1.0** — the earlier "unit sum" wording was wrong; there is no sum=1 invariant |
| D3 | Coupling kappa unclamped | Defensive `±0.045 rad` cap (never reached; max raw ~0.002 rad) | Corruption hygiene only |
| D4 | Material smoothing + recalc every 32 samples while moving | Per-sample material smoothing; bounded re-derive every 32 samples always | ~32x fewer coefficient recalculations (estimated); removes zipper/CPU hazard |
| D5 | `pow(hf/sf, m)` | `exp(log(hf/sf)*m)`, log ratios precomputed once at init | Algebraically identical; `exp()` faster; six `log()` moved to init |
| D6 | Four slider compares + full target recompute per sample | Four compares per sample; recompute only on change | Cheapest SoloConsole-proven fallback |
| D7 | Per-state 1024-sample scrubs | Signed 1e-20 input dither | Denormal hygiene without per-sample state writes |
| D8 | — | NaN→0 guard; clamp activity instrumented in `clampCount` | Audit proves 0 activations under nominal probes |
| D9 | — | Per-mode emission trim `owc[]` (log-frequency taper) | Makes Material a timbre knob, not a level knob: Material sweep is 0.3 dB for mid/high/impulse/multitone probes (low-frequency and noise probes show 0.4–3.0 dB — D9 shapes the low region most) |
| D10 | User-defined `function` helpers | **All functions inlined** into `@init`/`@slider`/`@sample` | **Parser-verified**: the ysfx/WDL-eel2 runtime (same EEL2 family as RootlessJamesDSP) rejects *any* `function` with `'name' undefined`, even defined-before-use. Static inspection missed this; only running the parser caught it. The draft and first implementation would NOT have loaded |

## Validation

`tools/audit_materialmemory.py` is a dependency-free Python harness (same spirit as `tools/audit_soloconsole.py`). It validates package identity, native EEL2 structure, slider contract, current/archive byte identity, the full sample-rate × material grid (44.1k/48k/96k/192k × 0/.25/.5/.75/1), finite coefficients, `0 < r < 1`, `(1-r)` resonant-gain normalization, coupling energy preservation, homogeneous decay, impulse tail decay, stereo independence, NaN/Inf stress, no self-excitation from silence, clamp activity, forbidden-section markers, and forbidden feature creep (FFT/FIR/oversampling/large delays).

```bash
python tools/audit_materialmemory.py
```

**Parser/runtime validation (performed):** the file was compiled and run through a local ysfx/WDL-eel2 runtime (`eeldsp_rt`, the same EEL2 engine family RootlessJamesDSP uses) — `Script compiled OK`, all four sliders enumerated, and a 5-second audio smoke run completed without crashing. This is a generic EEL2 parser test, not RootlessJamesDSP device validation.

## Installation

### RootlessJamesDSP (Android)

1. Copy `materialmemory.eel` to your RootlessJamesDSP Liveprog scripts directory.
2. Enable the Liveprog effect.
3. Select `materialmemory.eel` from the script dropdown.

### JDSP4Linux (Linux Desktop)

```bash
jamesdsp --set liveprog_enable=true
jamesdsp --set 'liveprog_file=/path/to/materialmemory.eel'
```

## Psychoacoustic Design Principles

- **Body/Edge decomposition**: lower modes receive more low-passed "body", upper modes receive more "edge" — so a kick, a snare, a hi-hat and a pad excite the material differently without classification or FFT.
- **Perceptual T60 anchoring**: decay is defined as a time-to-−60 dB per mode and normalized by sample rate, keeping decay behavior portable.
- **Energy conservation as a design law**: the coupling can move energy around the lattice but cannot create it, so the material cannot "ring itself up" from silence.
- **Injection normalization**: `(1-r)` keeps each mode's displacement DC gain at exactly 1 (steady-state `p` bounded by the body level), while the D9 emission trim flattens the Material sweep to 0.3 dB — so the Material control is a timbre knob, not a loudness knob.

## Known Limitations

- **Not yet auditioned.** Numerical tests prove stability, boundedness, decay, coupling, and stereo independence. They cannot prove the processor sounds like "something was struck" rather than "six ringing filters". That is the core sonic gate and requires on-device listening (see the return report for the exact protocol).
- **Not host-validated.** No EEL2 parser/runtime was available in this environment; loadability on RootlessJamesDSP is static-inspection only.
- Material endpoint loudness is flat to 0.3 dB, but the *timbre* changes substantially (soft → hard), which is the intended behavior; whether that timbre shift is musical is an on-device listening question.
- Single-sample state scrubs use a 1024-sample cadence; the alternating-sign input dither is the primary denormal defense.
- The Modal `stateBound` of 8.0 is a corruption barrier only — normal operation stays far below it.

## References

- Airwindows engineering spirit (compact perceptual DSP, small unusual state machines)
- Giorgio Sancristoforo / TOBOR Experiment (sound as material, memory, disintegration — conceptual influence, not code)
- EEL2/EEL_VM, RootlessJamesDSP Liveprog Modern conventions
- *DAFX — Digital Audio Effects* (Udo Zölzer); *Designing Audio Effect Plug-Ins in C++* (Will Pirkle)
