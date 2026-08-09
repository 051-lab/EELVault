# SoloConsole — Oversampled Console Drive

**Version:** 0.3.1  
**Status:** Experimental  
**Type:** User-controlled console saturation  
**Target:** RootlessJamesDSP / JDSP4Linux  
**File:** `soloconsole.eel`

## Description

SoloConsole is an oversampled analog console drive: input gain → tone shaping → tunable saturation → transformer-style rolloff. It is a console strip rather than a fixed "magic box": drive, tone, output, oversampling, and blend remain under user control.

Its signature is an arithmetic **polynomial soft-clip with bias** — no `tanh` in the per-sample nonlinear core — tuned for tube-like even/odd harmonic behavior and wrapped in **2x oversampling** for lower aliasing. A **Style** selector swaps the nonlinear core between four curves.

## Signal Flow

```text
Input
  -> Input gain (dB)
  -> Bass shelf (pre-drive, 250 Hz RBJ biquad)
  -> optional 2x OVERSAMPLING (windowed-sinc halfband, 32 taps)
  -> Polynomial saturation + bias (even/odd harmonics)
  -> DC blocker (sample-rate-derived 5 Hz pole)
  -> Treble shelf (post-drive, 6 kHz RBJ biquad)
  -> Transformer rolloff (one-pole, 16 kHz tuning constant)
  -> Soft-knee wet-path ceiling
  -> DOWNSAMPLE (halfband + causal odd-phase decimation)
  -> Output gain (dB)
  -> Pre-drive blend
  -> Output stereo
```

## Key Parameters

| Parameter | Default | Range | Purpose |
|-----------|---------|-------|---------|
| Input | 0 dB | -18..18 | input gain staging |
| Drive | 6 dB | -18..18 | saturation / drive |
| Even harmonics | 25 % | 0..100 | tube-bias asymmetry |
| Bass | 0 dB | -12..12 | pre-drive RBJ low shelf |
| Treble | 0 dB | -12..12 | post-drive RBJ high shelf |
| Output | 0 dB | -12..12 | wet-path makeup / trim |
| Oversampling | 2x | 1x / 2x | anti-aliasing on/off |
| Mix | 100 % | 0..100 | pre-drive blend |
| Style | 0 | 0..3 (dropdown) | saturation core: Polysoft / Foldback / Asymmetric / Bitcrush |

### Mix semantics

`Mix` is intentionally a **pre-drive blend**, not a raw-input dry/wet control. The blend's dry side already contains Input gain and the Bass shelf. Drive, Even, Treble, transformer rolloff, wet-path ceiling, and Output belong to the wet side.

At 2x, the dry side is delayed to match the oversampled wet path before blending.

## Oversampling and latency

SoloConsole uses a 32-tap windowed-sinc halfband design. Interpolation is implemented as two fused 16-tap polyphase convolutions over the same real-sample history. Decimation begins its FIR read on the newest odd oversample, matching the causal reference convolution.

The 2x path has exactly **15 base-rate samples of latency**:

- 44.1 kHz: about **0.340 ms**
- 48 kHz: **0.3125 ms**

The sample count is the invariant; milliseconds vary with sample rate.

## Why this saturation curve

The core curve is a polynomial soft clip:

```text
y = u - u^3 / 3
```

inside the ±1 region, with a ±2/3 continuation outside it. A small controllable bias is applied before the polynomial and compensated afterward to create even-harmonic asymmetry while retaining a zero output for zero input. A DC blocker follows the nonlinear stage.

### Style selector

`Style` (`slider9`) picks the saturation core used in all six chain sites; every style shares the same bias staging, DC block, treble shelf, transformer rolloff, and soft-knee ceiling:

| Style | Curve |
|-------|-------|
| 0 Polysoft | `\|u\|>1 ? ±2/3 : u - u^3/3` (v0.2.2, bit-identical) |
| 1 Foldback | `\|u\|≤1 ? u : sign(u) * (1 - \|(\|u\| mod 2) - 1\|)` — triangle wave beyond ±1 |
| 2 Asymmetric | `u>0 ? u/(1+0.3u) : u/(1-0.6u)` — monotonic, asymmetric compression |
| 3 Bitcrush | `round(u·2^bits)/2^bits`, bits 3..11 from Even |

Hosts that do not expose a ninth control keep `Style = 0` and behave exactly like v0.2.2.

Earlier workbench measurements found the polynomial curve substantially easier to oversample effectively than harder rational saturation curves. The 32-tap halfband remains a deliberately mobile-conscious compromise between anti-aliasing and CPU cost.

## DC blocker

v0.2.2 derives the DC-block pole from sample rate rather than using a fixed feedback constant:

```eel
dcbR = exp(-2 * $pi * 5 / srate);
dcbR2 = exp(-2 * $pi * 5 / (srate * 2));
```

This keeps the intended pole at **5 Hz** in both the 1x and 2x processing paths across common host sample rates.

## Validation

The repository includes a dependency-free audit harness:

```bash
python tools/audit_soloconsole.py
```

It uses only the Python standard library and validates the native slider/section structure (now `slider1`–`slider9`), current/archive identity, polyphase interpolation parity, causal decimation parity, 15-sample impulse latency, 5 Hz DC-block coefficients, Treble-to-transformer handoffs, OS-switch state clearing, style dispatch coverage, style numeric invariants, dropdown declaration, decimator allocation, and release metadata — 21 checks total.

## Version History

| Version | Name | File | Key Addition |
|---------|------|------|-------------|
| v0.1.0 | Oversampled Console | `versions/v0.1.0-oversampled-polysoft-console.eel` | Polysoft core with bias + 2x oversampling + tone/blend console |
| v0.2.0 | Fused Polyphase | `versions/v0.2.0-fused-polyphase.eel` | Fused 16-tap polyphase interpolator, rate-adjusted 2x DC blocker, mode-switch state flush |
| v0.2.1 | Corrective Release | `versions/v0.2.1-corrective-release.eel` | Restored audible Treble routing, causal odd-phase decimation/15-sample latency, and complete OS-switch state flushing |
| v0.2.2 | Validation & Hardening | `versions/v0.2.2-validation-hardening.eel` | Repository audit harness, sample-rate-derived 5 Hz DC blocker, initial OS-state hardening, and 32-slot decimator allocation |
| v0.3.0 | Style Select | `versions/v0.3.0-mode-select.eel` | `Style` selector: Polysoft / Foldback / Asymmetric / Bitcrush saturation cores + 20-check audit |
| v0.3.1 | Style Dropdown | `versions/v0.3.1-style-dropdown.eel` | `Style` rendered as a native option dropdown where the host supports it + 21-check audit |

The current version is always available as `soloconsole.eel` in this directory.

## Installation

### RootlessJamesDSP (Android)

1. Copy `soloconsole.eel` to your RootlessJamesDSP Liveprog scripts directory.
2. Enable the Liveprog effect.
3. Select `soloconsole.eel` from the script dropdown.

### JDSP4Linux (Linux Desktop)

```bash
jamesdsp --set liveprog_enable=true
jamesdsp --set 'liveprog_file=/path/to/soloconsole.eel'
```

## UI note

SoloConsole uses native EEL2/JSFX slider declarations (`slider1` through `slider8`, plus `slider9` for `Style`). It checks whether the oversampling slider reads back as 1 or 2; if not, the effect falls back to curated defaults rather than going silent. `Style` is declared as a dropdown (`0<0,3,1{Polysoft,Foldback,Asymmetric,Bitcrush}>`); hosts that only render bare sliders show it as a 0..3 fader, and hosts without a ninth control leave it at 0 — preserving v0.3.0 behavior.

## Known limitations / future work

- 2x oversampling is a mobile-conscious compromise; 4x remains a future quality option rather than a v0.3.0 feature.
- Style changes are not crossfaded: switching cores mid-playback is an instantaneous curve step (downstream filters see continuous input, but the treble shelf may ring briefly).
- Bass/Treble coefficient changes are not yet smoothed, so rapid tone-control movement may deserve dedicated zipper-noise hardening later.
- The soft-knee ceiling protects the wet nonlinear path before Output gain; it is not a final full-output safety limiter.
- The transformer rolloff is a one-pole tuning stage, not a claim of a textbook -3 dB cutoff at exactly 16 kHz.
- Not yet tuned by ear against specific hardware references.

## References

- *DAFX — Digital Audio Effects* — Udo Zölzer (ch. 5, nonlinear processing)
- *Designing Audio Effect Plug-Ins in C++* — Will Pirkle
- *Audio Effects: Theory, Implementation and Application* — Reiss & McPherson
