# ANIMA — Vintage Harmonic Engine

**Version:** 1.0.0
**Status:** Stable
**Type:** Fixed-parameter analog emulation
**Target:** RootlessJamesDSP / JDSP4Linux
**File:** `anima.eel`

## Description

ANIMA is a fixed-parameter, program-dependent analog emulation processor. It transforms sterile digital audio into warm, dimensional, vintage-sounding output by emulating the behavior of transformer-coupled analog gear, tape machines, and optical compressors.

ANIMA has no user-adjustable parameters. It is a "magic box" — you load it, and it works. All parameters are hard-coded to their psychoacoustically optimal values.

## Signal Flow

```text
Input stereo
-> 30 Hz high-pass
-> 120 Hz transformer shelf (+1.5 dB)
-> +4.0 dB even-harmonic saturation
-> 14 kHz tape damping
-> Program-dependent tape compression
-> Auto makeup gain (+2.4 dB base, +3.0 dB max)
-> 1 kHz dynamic tilt EQ
-> DC removal
-> 2.0 ms micro-flutter (4-point Hermite interpolation)
-> Mid/Side +0.7 dB width lift
-> Output trim (-0.6 dB)
-> Safety limiter (-0.3 dBFS)
-> Output stereo
```

## Key Parameters

| Parameter | Value |
|-----------|-------|
| High-pass frequency | 30 Hz |
| Transformer shelf frequency | 120 Hz |
| Transformer shelf gain | +1.5 dB |
| Drive input gain | +4.0 dB |
| Even-harmonic warmth mix | 0.12 |
| Tape damping low-pass | 14000 Hz |
| Tape compression amount | 0.45 |
| Tilt EQ pivot frequency | 1000 Hz |
| Tilt EQ maximum depth | 0.06 |
| Micro-flutter base delay | 2.0 ms |
| Micro-flutter depth | ±0.35 ms |
| Mid/Side side gain | +0.7 dB |
| Auto makeup base gain | +2.4 dB |
| Auto makeup maximum gain | +3.0 dB |
| Output trim | -0.6 dB |
| Limiter ceiling | -0.3 dBFS |

## Version History

| Version | Name | File | Key Addition |
|---------|------|------|-------------|
| v0.1.0 | Base Analog Chain | `versions/v0.1.0-base-analog-chain.eel` | Core chain + fixed makeup gain |
| v0.2.0 | Auto Makeup Gain | `versions/v0.2.0-auto-makeup-gain.eel` | Program-dependent auto makeup |
| v0.3.0 | Hermite Interpolation | `versions/v0.3.0-hermite-interpolation.eel` | 4-point cubic interpolation |
| v0.4.0 | Thermal Hysteresis | `versions/v0.4.0-thermal-hysteresis.eel` | Program-dependent release |
| v0.5.0 | ISP Estimation | `versions/v0.5.0-isp-estimation.eel` | Inter-Sample Peak detection |
| v1.0.0 | Denormal Protection | `versions/v1.0.0-denormal-protection.eel` | CPU denormal guard (DEFINITIVE) |

The definitive version is always available as `anima.eel` in this directory.

## Installation

### RootlessJamesDSP (Android)

1. Copy `anima.eel` to your RootlessJamesDSP Liveprog scripts directory.
2. Enable the Liveprog effect.
3. Select `anima.eel` from the script dropdown.

### JDSP4Linux (Linux Desktop)

```bash
jamesdsp --set liveprog_enable=true
jamesdsp --set 'liveprog_file=/path/to/anima.eel'
```

## Psychoacoustic Design Principles

- **Even-harmonic saturation** generates musically consonant overtones (2nd, 4th harmonics) perceived as warmth and body, following the principles described in *Designing Audio Effect Plug-Ins in C++*.
- **Dynamic tilt EQ** applies Fletcher-Munson equal-loudness compensation: when the signal gets loud, highs are gently reduced and lows are gently boosted to maintain perceived balance.
- **Micro-flutter** uses the Haas effect: delays under 5 ms are perceived as thickness and motion rather than discrete echoes, following spatial hearing principles from *Principles and Applications of Spatial Hearing*.
- **Thermal hysteresis** emulates the "memory" behavior of analog optical compressors, where sustained loudness slows the release time.
- **4-point Hermite interpolation** preserves high-frequency content during delay modulation, following the fractional delay line techniques described in *The Audio Programming Book*.

## Known Limitations

- Saturation stage is not oversampled. The 14 kHz tape damping filter placed after the saturation stage attenuates high-frequency aliasing artifacts.
- Limiter uses a lightweight ISP estimator rather than a full ITU-R BS.1770 4x oversampled True Peak meter.
- Flutter delay uses linear interpolation in the stable build. Hermite interpolation is available in the enhanced build.

## References

- *Designing Audio Effect Plug-Ins in C++* — Will Pirkle
- *The Audio Programming Book* — Richard Boulanger & Victor Lazzarini
- *Principles and Applications of Spatial Hearing* — Masayuki Morimoto
- JDSP4Linux Knowledge Base — https://github.com/Audio4Linux/JDSP4Linux