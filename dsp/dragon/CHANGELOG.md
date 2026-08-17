# Changelog

All notable changes to DRAGON.

## [1.0.0] — 2026-08-16
### Added
- v1.0.0 "Absolute Lab Calibration" — Nakamichi Dragon reference 3-head deck tape-path emulator for RootlessJamesDSP / JDSP4Linux.
- Eight native EEL2 sliders with sequential declarations: Record Drive (3 dB), Tape Bias (3), Tape Compression (2 dB), Wow & Flutter Depth (1.0), LF Contour (1 dB), HF Rolloff (3.5 dB), Tape Hiss (−82 dBFS), Output Trim (0 dB).
- Record pre-emphasis / replay de-emphasis pair at 3183 Hz (+3.5/−3.5 dB, Dolby C anti-saturation proxy) straddling the saturator.
- Fixed IEC 70 µs Type IV playback corner (−4 dB high shelf @ 2273.6 Hz, Q 0.707).
- Linked tape compression (max(|L|,|R|) detector, attack 4 ms / release 90 ms, `gr = comp·envN²/(1+envN²)`).
- Asymmetric tanh saturator with 2nd-harmonic bias (`v = tanh(s); out = (v + asym·v²)·makeup`, `asym = 0.004 + bias·0.010`).
- Dynamic HF damping (1-pole, cutoff drops with envelope, floor 7 kHz).
- Three-component wow & flutter (1 Hz / 4 Hz / 8.5 Hz recursive quadrature oscillators, shared read offset, 12-sample base delay, 64-sample buffers L/R), combined 0.017% WRMS at depth 1.0, AGC renormalization every 512 samples.
- Inter-channel tape bleed at −60 dB (measured Dragon separation).
- Uncorrelated TPDF hiss, Dolby-C-shaped (HP 90 Hz / LP 3.8 kHz / LP 9 kHz) with slow level wander, default −82 dBFS.
- Two-pole 18 kHz anti-alias filter, 50 Hz LF contour peaking (Q 0.95), fixed 3180 µs tilt shelf (+1 dB @ 50 Hz), 14 kHz HF rolloff shelf.
- Output protection: 7 Hz DC blockers (input + output), soft limiter at 0.891, hard clamp ±0.99999.
- Parameter smoothing (12 ms per-sample gain-type, 25 ms per-block EQ), sample-rate-change coefficient re-derive in `@block`.
- README, metadata.json, CHANGELOG, archived byte-identical `versions/v1.0.0-absolute-lab-calibration.eel`.
- Dependency-free audit harness `tools/audit_dragon.py`.

### Calibration basis
- Cross-referenced against the Nakamichi Dragon service manual/brochure, Stereo Review (Craig Stark) and Audio (Howard Roberson) lab measurements, IASA TC-04 replay EQ standards (Type II/IV 3180/70 µs), and Ray Dolby's AES 1850 Dolby C paper.

### Deviations / notes
- RJDSP EEL dialect: function **definitions** use space-separated argument lists (`function rbj_hishelf(f dB S)`); **calls** use comma-separated arguments. Comma-separated definitions silently drop parameters on the RJDSP VM (NaN coefficients → silence). Documented in the script header.
- No true Dolby C dynamics (static-shaped hiss), no NAAC servo, no oversampling — deliberate mobile-CPU tradeoffs, detailed in README.
- On-device auditioned in RootlessJamesDSP (confirmed musical and stable); not yet instrument-validated.
