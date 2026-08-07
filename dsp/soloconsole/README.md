# SoloConsole — Oversampled Console Drive

**Version:** 0.2.0
**Status:** Experimental
**Type:** User-controlled console saturation
**Target:** RootlessJamesDSP / JDSP4Linux
**File:** `soloconsole.eel`

## Description

SoloConsole is an oversampled analog console drive: input gain → tone shaping → tunable
saturation → transformer-style rolloff. It is a *console strip*, not a "magic box" — drive,
tone, and output are yours to control.

Its signature is an arithmetic **polynomial soft-clip with bias** — no `tanh`, no
transcendentals — tuned for tube-like even/odd harmonic behavior, wrapped in **2x
oversampling** for clean high frequencies.

It aims to satisfy three listeners at once: engineers (precise controls), artists (musical,
non-fatiguing harmonics), and casual listeners (one knob and it sounds better).

## Signal Flow

```text
Input
  -> Input gain (dB)
  -> Bass shelf (pre-drive, 250 Hz, one-pole low shelf)
  -> 2x OVERSAMPLING (windowed-sinc halfband, 32 taps)
  -> Polynomial saturation + bias (even/odd harmonics)
  -> DC blocker
  -> Treble shelf (post-drive, 6 kHz)
  -> Transformer rolloff (one-pole, 16 kHz)
  -> Soft-knee ceiling limiter
  -> DOWNSAMPLE (halfband + decimate)
  -> Output gain (dB)
  -> Dry/wet mix
  -> Output stereo
```

## Key Parameters

| Parameter | Default | Range | Purpose |
|-----------|---------|-------|---------|
| Input | 0 dB | -18..18 | input gain staging |
| Drive | 6 dB | -18..18 | saturation / drive |
| Even harmonics | 25 % | 0..100 | tube bias (even/odd balance) |
| Bass | 0 dB | -12..12 | pre-drive low shelf |
| Treble | 0 dB | -12..12 | post-drive high shelf |
| Output | 0 dB | -12..12 | makeup / trim |
| Oversampling | 2x | 1x / 2x | anti-aliasing on/off |
| Mix | 100 % | 0..100 | dry / wet |

## Why this saturation curve

Measured in the dev workbench (`tools/measure_curves.py`):

- Rational soft-clip curves (like ANIMA's) alias hard — ~-9 dB at 12 kHz — and 2x
  oversampling barely recovers them (~-2 dB gain).
- A polynomial soft-clip `y = u - u³/3`, clamped at ±2/3, with a small bias produces the
  tube signature (weak even harmonics at low level, strong odd at high drive) while its
  harmonics fall off fast, so **2x oversampling delivers real alias suppression**: -39.9 dB
  at 7 kHz and -25.7 dB at 12 kHz (vs -17 / -8 dB without oversampling).
- 32 halfband taps measured optimum (64-128 taps gained <1 dB).

## Version History

| Version | Name | File | Key Addition |
|---------|------|------|-------------|
| v0.1.0 | Oversampled Console | `versions/v0.1.0-oversampled-polysoft-console.eel` | Polysoft core with bias + 2x oversampling + tone/mix console (EXPERIMENTAL) |
| v0.2.0 | Fused Polyphase | `versions/v0.2.0-fused-polyphase.eel` | Fused 16-tap polyphase interpolator (bit-identical, ~half the loop cost), rate-corrected 2x DC blocker, mode-switch state flush |

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

## UI note (requires verification)

The UI parameter syntax (`varName:0<min,max,step>Label`) has no working example in the
vault yet. SoloConsole detects whether the UI is alive via the `oversampling` control: if it
reads back as 1 or 2 the controls are used; otherwise the effect silently falls back to
curated defaults rather than going silent.

## Known limitations

- 2x oversampling is good, not "silver". 4x oversampling is the documented path to -50 dB+.
- Once-pole tone shelves are placeholders; console-glue (program-dependent release + auto
  makeup gain) is deferred to later versions.
- Not yet tuned by ear against hardware references.

## References

- *DAFX — Digital Audio Effects* — Udo Zölzer (ch. 5, nonlinear processing)
- *Designing Audio Effect Plug-Ins in C++* — Will Pirkle
- *Audio Effects: Theory, Implementation and Application* — Reiss & McPherson