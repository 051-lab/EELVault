# DRAGON — Reference Cassette Deck Emulator

**Version:** 1.0.0
**Status:** Experimental
**Type:** Reference cassette deck emulation (Nakamichi Dragon-class 3-head tape path)
**Target:** RootlessJamesDSP / JDSP4Linux
**File:** `dragon.eel`

## Description

DRAGON is a zero-look-ahead tape-path emulator modeled on the legendary **Nakamichi Dragon** — the reference 3-head, closed-loop dual-capstan cassette deck. It treats your audio as if it were recorded to and played back from compact cassette on the finest deck ever built: warm, rich, and musical, with gentle harmonic saturation and subtle mid-range glue rather than harsh distortion, near-inaudible wow & flutter (0.017% WRMS), a wide response with a slightly rounded top end, mild low-end warmth, and a whisper-quiet Dolby-C-shaped hiss floor.

Unlike generic lo-fi tape effects, DRAGON reproduces the *electrical and mechanical* behavior of the hardware: a record pre-emphasis / replay de-emphasis pair straddling the saturator (the physical reason tape distortion sounds smooth), a linked tape-compression detector, a shared modulated delay line for wow & flutter (one transport, one pitch wobble), and measured inter-channel tape bleed. The effect is transparent at its defaults and can be pushed toward character via its eight sliders.

The calibration was cross-referenced against primary sources: the Nakamichi Dragon service manual and brochure, the Craig Stark *Stereo Review* and Howard Roberson *Audio* magazine lab measurements, IASA TC-04 cassette replay equalization standards, and Ray Dolby's AES 1850 paper on Dolby C.

## Signal Flow

```text
Input L/R
  -> S1   DC blocker 7 Hz
  -> S2   Record emphasis shelf +3.5 dB @ 3183 Hz (fixed; Dolby C anti-sat proxy)
  -> S3   Anti-alias 2-pole LP @ 18 kHz
  -> S4   Tape compression gain (LINKED detector: att 4 ms / rel 90 ms)
  -> S5   Tape saturator: v = tanh(s); out = (v + asym*v^2)*makeup
  -> S6   Dynamic HF damping 1-pole (min 7 kHz, level-driven)
  -> S7   Wow & flutter delay: 1 Hz / 4 Hz / 8.5 Hz, SHARED offset, linear interp
  -> S7b  Inter-channel tape bleed -60 dB (measured separation)
  -> S8   Replay EQ: de-emph -3.5 dB @ 3183 Hz | IEC 70 us corner -4 dB @ 2273.6 Hz
  ->      | LF contour peak @ 50 Hz | 3180 us tilt +1 dB @ 50 Hz | HF rolloff @ 14 kHz
  -> S9   Tape hiss, uncorrelated TPDF L/R, Dolby-C-shaped
  -> S10  Output trim
  -> S11  DC blocker 7 Hz (removes shaper DC before limiter)
  -> S12  Soft limiter, threshold 0.891
  -> S13  Hard safety clamp +/-0.99999
Output L/R
```

Latency is 12 samples (~0.27 ms @ 44.1 kHz) — the W&F delay base. Zero block latency, zero look-ahead.

## Key Parameters

| Slider | Default | Range | What it does |
|--------|---------|-------|--------------|
| Record Drive | 3 dB | 0–10 | Input gain into the saturator. Low = transparent, high = grit. Feeds the compression detector too. |
| Tape Bias | 3 | 0–10 | Even-harmonic recipe: `asym = 0.004 + bias*0.010`. High bias = sweeter 2nd-harmonic warmth, and slightly quieter hiss. |
| Tape Compression | 2 dB | 0–6 | Linked-envelope glue, attack 4 ms / release 90 ms. Max gain reduction = slider value. |
| Wow & Flutter Depth | 1.0 | 0–2 | Scales the 1/4/8.5 Hz transport wobble. 1.0 = 0.017% WRMS (Dragon spec). |
| LF Contour | 1 dB | 0–4 | Peaking filter at 50 Hz (Q 0.95) on top of the fixed +1 dB 3180 µs tilt. |
| HF Rolloff | 3.5 dB | 0–9 | Shelf at 14 kHz; default produces −6 dB @ 18 kHz per the Stark measurement. |
| Tape Hiss | −82 dBFS | −90…−42 | TPDF noise level, Dolby-C-shaped (HP 90 Hz / LP 3.8 kHz / LP 9 kHz). |
| Output Trim | 0 dB | −12…+12 | Level match for honest A/B listening. |

### Sweet-spot presets

- **Taming harsh modern masters (pop / EDM / bright synths):** Rolloff 5–7, Bias 5–7, Drive 2–4.
- **Bus glue (rock / acoustic / jazz):** Comp 3.5–5, Drive 4–6, Bump 2.
- **Intentional lo-fi / nostalgia (beats / ambient):** W&Flutter 1.5–2, Hiss −55…−45, Drive 8+.

## Installation

### RootlessJamesDSP (Android)

1. Copy `dragon.eel` to your RootlessJamesDSP Liveprog scripts directory.
2. Enable the Liveprog effect.
3. Select `dragon.eel` from the script dropdown.

### JDSP4Linux (Linux Desktop)

```bash
jamesdsp --set liveprog_enable=true
jamesdsp --set 'liveprog_file=/path/to/dragon.eel'
```

## Psychoacoustic Design Principles

- **Pre/de-emphasis sandwich (S2 + BQ1):** boosting highs before saturation and cutting them after means the distortion products are de-emphasized on replay — the physical reason tape sounds smooth, not harsh. The 3183 Hz pair mirrors the Dolby C anti-saturation turnover region.
- **Even-harmonic warmth:** `v + asym·v²` after `tanh` injects the 2nd harmonic that gives tape its consonant warmth, balanced against the 3rd at the default bias (H2 ≈ H3, ~0.4% at −10 dBFS — matching the measured Dragon/ZX distortion).
- **Uncorrelated hiss:** independent L/R TPDF generators stay diffuse and never disturb localization (*Principles and Applications of Spatial Hearing*). The saturation harmonics partially mask the hiss so it integrates into the music.
- **Linked wow & flutter:** both channels share one modulated read offset — one tape, one transport. The 4 Hz component is emphasized because IEC 60386 weighting says the ear is most sensitive there. ITD/ILD cues survive intact.
- **Fletcher-Munson-aware LF contour:** the 50 Hz contour is especially satisfying at low listening volumes (walks, earbuds), where human hearing loses bass sensitivity first.

## Calibration Sources

| Target | Value | Source |
|--------|-------|--------|
| W&F | 0.017% WRMS forward | Stereo Review (Craig Stark) / Audio (Roberson) measurements; IEC 60386 weighting |
| Replay EQ | Type I 3180/120 µs, Type II/IV 3180/70 µs | IASA TC-04 `[STD]` |
| 70 µs corner | 2273.6 Hz fixed −4 dB shelf | IEC Type IV playback standard |
| Dolby C anti-sat | 50 µs = 3183 Hz; −2.8 dB @ 15 kHz | Ray Dolby, AES 1850 |
| Channel separation | >37 dB spec; 61 dB measured | Service manual; Audio magazine |
| HF rolloff | −6 dB @ 18 kHz (ZX @ 0 dB) | Stereo Review measurement |
| Noise | 77.5 dB S/N CCIR-ARM (ZX + Dolby C) | Stereo Review measurement → −82 dBFS default |
| THD | H3 ≈ 0.40% @ 315 Hz/0 dB; total < 0.8% | Both research files |
| Bias oscillator | 105 kHz (carrier above Nyquist, effects only) | Service manual |
| Head bump | Suppressed by PA-1L head geometry → subtle LF contour | Service manual `[SPEC]` |

## Version History

| Version | Name | File | Key Addition |
|---------|------|------|-------------|
| v1.0.0 | Absolute Lab Calibration | `versions/v1.0.0-absolute-lab-calibration.eel` | IEC 70 µs corner, Dolby C 3183 Hz pair, 60 dB bleed, 14 kHz rolloff, −82 dBFS hiss |

The definitive version is always available as `dragon.eel` in this directory.

## Known Limitations

- **No true Dolby C dynamics.** The hiss floor is static-shaped; modeling two cascaded sliding-band companders exceeds the mobile CPU budget. Named tradeoff.
- **Record stage is empirical.** The exact Dragon record-amp transfer function was never published (tape-dependent switched networks); the 3183 Hz emphasis pair is the best defensible proxy.
- **NAAC servo not modeled.** With azimuth corrected, its only residue is a barely-measurable HF stability benefit; omitting it is the faithful choice.
- **No oversampling.** The 2-pole 18 kHz anti-alias filter guards aliasing from the saturator; at Drive > 8 with bright material, foldback may become audible.
- **Not instrument-validated.** Loadability and sonics were confirmed on-device in RootlessJamesDSP, but no lab measurement (sweep, THD, demodulated W&F) has been run against this build yet.

## References

- Nakamichi Dragon Service Manual / Owner's Manual / Brochure (hifiengine.com)
- *Stereo Review* (Craig Stark), April 1983 — Dragon lab measurements
- *Audio* magazine (Howard A. Roberson), May 1983 — Dragon lab measurements
- IASA TC-04 — cassette replay equalization time constants
- Ray Dolby, "A 20 dB Audio Noise Reduction System for Consumer Recording," AES preprint 1850
- IEC 60094 / IEC 60386 — cassette standards and wow & flutter weighting
- *Designing Audio Effect Plug-Ins in C++* — Will Pirkle (envelope followers, waveshaping, filter stability)
- *The Audio Programming Book* — Richard Boulanger & Victor Lazzarini (delay lines, circular buffers)
- *Principles and Applications of Spatial Hearing* — Masayuki Morimoto (uncorrelated noise, ITD/ILD)
