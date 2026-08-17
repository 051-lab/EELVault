# STILLROOM — Nearfield Depth

**Version:** 0.1.0
**Status:** Experimental
**Type:** Spatial ambience depth processor
**Target:** RootlessJamesDSP / JDSP4Linux
**File:** `stillroom.eel`

## Description

STILLROOM is a compact spatial field processor that gives dry digital music a believable sense of space and depth — not louder, wetter, or wider. It is not a reverb. It is a nearfield depth processor: a handful of very short, asymmetric early reflections establish walls and distance, followed by a tiny, strongly damped allpass scattering network that supplies diffuse continuity without a recognizable tail. The dry signal remains the anchor throughout.

Designed for everyday audiophile listening on headphones and speakers alike. Spaciousness is derived from decorrelated side energy while the mid path stays phase-coherent. The spatial field is injected as opposed-polarity side energy, so it cancels cleanly under mono summing rather than producing comb-filtering — making STILLROOM mono-safe by construction.

## Signal Flow

```text
Input L/R
  -> Non-finite + denormal input sanitation
  -> M/S encode (M = (L+R)*0.5, S = (L-R)*0.5)
  -> Direct anchor (M_direct, S_direct pass through untouched)
  -> Spatial excitation (primarily M, restrained S)
     -> 6 asymmetric short-tap early reflection ring
     -> Depth air-absorption filter
     -> 5-stage damped allpass diffuser (delays ~0.65/1.0/1.5/2.2/3.2 ms)
     -> Wet-tapered, side-only spatial injection
  -> M_out = M_direct
  -> S_out = S_direct + spatial_side (opposed-polarity)
  -> M/S decode
  -> Output L/R
```

### Mono-safety property

The generated spatial field is injected as opposed-polarity side energy. When summed to mono, it cancels rather than producing delayed-mid combing:

```text
(L + spatial_side) + (R - spatial_side) = L + R
```

Mono retains the direct signal at a stable level. STILLROOM can create width and depth even for mono material because the mid signal may excite the side-only field, but it cannot contaminate the collapsed mono path.

## Key Parameters

| Parameter | Default | Range | Purpose |
|-----------|---------|-------|---------|
| Space | 42 % | 0..100 | Scales early reflection timing from compact to spacious and slightly increases diffuser extent. Never reaches zero-delay or long-tail territory. |
| Depth | 36 % | 0..100 | Raises reflected-field contribution, shifts early/diffuse balance toward recession, and applies progressively stronger high-frequency air absorption. |
| Wet | 24 % | 0..100 | Perceptually tapered side-field injection. Internally capped conservatively (~0.0–0.35 spatial-send range) to protect headroom and long-session listenability. |
| Tone | 56 % | 0..100 | Ambient-field brightness only: low values are absorbent/dark; high values retain air. Does not EQ the direct path. |

### Semantic endpoints

| Control | Low | High |
|---------|-----|------|
| Space | Booth | Room |
| Depth | Near | Recessed |
| Wet | Dry | Present |
| Tone | Dusk | Air |

## Installation

### RootlessJamesDSP (Android)

1. Copy `stillroom.eel` to your RootlessJamesDSP Liveprog scripts directory.
2. Enable the Liveprog effect.
3. Select `stillroom.eel` from the script dropdown.

### JDSP4Linux (Linux Desktop)

```bash
jamesdsp --set liveprog_enable=true
jamesdsp --set 'liveprog_file=/path/to/stillroom.eel'
```

## Psychoacoustic Design Principles

- **Nearfield, not reverb:** early reflections establish spatial context before the ear perceives a discrete tail. The diffuse field supplies continuity, not a wash — keeping the processor distinct from conventional reverb and aligned with transparent, hours-long listening.
- **Decorrelated side energy:** spaciousness is generated primarily in the side channel, preserving the mid (center) path for vocal and bass clarity. This mirrors how real rooms add lateral reflections without smearing the phantom center.
- **Mono-safe by construction:** the opposed-polarity side injection ensures that mono summing cancels the spatial field rather than comb-filtering it. This prevents the level surprises and tonal coloration that plague naive stereo-widening processors.
- **Frequency-dependent distance:** real air absorption attenuates high frequencies over distance. Depth models this by progressively reducing upper-frequency reflection energy and shifting the direct/reflected balance — not by merely turning up wet gain.
- **Bounded feedback:** each allpass stage has an independent feedback cap. There is no global feedback loop, so the processor cannot self-oscillate or produce long washes at any setting or sample rate.

## Implementation Guardrails

- The mid/direct path is mathematically untouched apart from input sanitation.
- Short smoothing on all controls, particularly Space, to prevent zippering from retuned delays.
- Each allpass feedback cap is independent; no global feedback loop.
- Diffuse output is kept beneath the early field at all settings (~25–40% of generated spatial energy, never dominant).
- Wet is internally capped to a ~0.0–0.35 spatial-send range.

## Validation

```bash
python tools/audit_stillroom.py
```

A dependency-free Python harness (stdlib only) validating package identity, native EEL2 structure, slider contract, current/archive byte identity, mono-collapse cancellation, feedback boundedness, impulse decay behavior, and stereo correlation across sample rates (44.1k/48k/96k/192k).

## Known Limitations

- **Not yet auditioned.** Numerical tests prove mono-safety, boundedness, decay, and stereo independence. They cannot prove the processor sounds like "a real room" rather than "six short delays." That is the core sonic gate and requires on-device listening.
- **Not host-validated.** No EEL2 parser/runtime was available in this environment; loadability on RootlessJamesDSP is static-inspection only.
- The allpass diffuser is a mobile-conscious compromise between diffusion quality and CPU cost.
- Style changes (Space retune) are smoothed but not crossfaded; rapid Space movement may produce minor transient artifacts.

## References

- *DAFX — Digital Audio Effects* (Udo Zölzer; ch. 3 reverberation, ch. 2 allpass/comb filters)
- *Designing Audio Effect Plug-Ins in C++* (Will Pirkle)
- Airwindows engineering spirit (compact perceptual DSP, small unusual state machines)
- Giorgio Sancristoforo / TOBOR Experiment (sound as space and material — conceptual influence)
- EEL2/EEL_VM, RootlessJamesDSP Liveprog Modern conventions
