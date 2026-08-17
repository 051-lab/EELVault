# Changelog

All notable changes to Material Memory Engine.

## [0.0.1] — 2026-08-14
### Added
- P0.1 "Matter" laboratory prototype: stereo six-mode damped two-state virtual material core.
- Four native EEL2 sliders (Excite 42, Material 48, Mix 65, Output 0 dB) with sequential declarations.
- Body/Edge excitation decomposition via a one-pole low-pass (700 + 500*M Hz), per channel.
- Material-dependent modal frequencies (logarithmic morph between soft/hard anchors, clamped at 0.22*Fs) and T60 (M^2 morph, r = exp(-6.9078/(T60*Fs))).
- Energy-preserving alternating Givens coupling lattice (A: M1↔M2 M3↔M4 M5↔M6 / B: M2↔M3 M4↔M5; multipliers [+0.70, -1.00, +1.25, -0.90, +1.15] at 1.5+10*M^2 Hz).
- Weighted modal emission (renormalized weights, materialGain 2.2), wet = input + gain*modal, Mix, Output dB, emergency +/-0.999 containment.
- Parameter smoothing: 15 ms one-poles for Excite/Mix/Output; 60 ms Material pole with bounded 32-sample coefficient re-derive.
- Sample-path slider fallback bridge (hosts whose VM never fires `@slider`).
- Denormal dither, non-finite input sanitizer, NaN guard, 1024-sample corruption/denormal scrub, clamp instrumentation.
- Dependency-free audit harness `tools/audit_materialmemory.py`.
- README, metadata.json, CHANGELOG, archived byte-identical `versions/v0.0.1-p0.1-matter.eel`.

### Deviations from the supplied design draft
- D1 drive normalization: retained `(1-r)` after testing and rejecting `sqrt(1-r*r)` (its resonant gain grows without bound at low damping — 18 dB spread, max 95.8). `(1-r)` normalizes each mode's resonant amplitude to ~0.5 (0.01 dB spread across the full grid); this is a resonant-gain, not DC-gain, claim.
- D9 (new) per-mode emission trim `owc[]` (log-frequency taper): Material level sweep is 0.3 dB for mid/high/impulse/multitone probes; low-frequency and noise probes show 0.4–3.0 dB (D9 shapes the low region most). Constants provisional pending listening.
- D2 base emission weights are the draft ratios scaled ~1.3 (sum 1.49, **not** 1.0 — the earlier "unit sum" wording was corrected; there is no sum=1 invariant).
- D3 defensive coupling-angle cap `±0.045 rad` (never active in the grid; max raw ~0.002 rad).
- D4 coefficient re-derive cadence changed to a bounded every-32-samples always-on refresh (~32x fewer recalcs, estimated).
- D5 frequency morph via `exp(log(ratio)*m)` with the six invariant `log(hf/sf)` ratios precomputed once at init.
- D6 slider fallback recomputes targets only on change.
- D7 denormal hygiene via signed input dither instead of per-state scrubs.
- D8 NaN→0 guard and clamp-activity instrumentation added.
- **D10 (critical, parser-verified):** removed all user-defined `function` helpers and inlined their bodies into `@init`/`@slider`/`@sample`. A local ysfx/WDL-eel2 runtime (the EEL2 engine family RootlessJamesDSP uses) rejects any `function` with `'name' undefined`; the draft and the pre-D10 implementation would not have loaded. This was found by actually running the parser — static inspection alone missed it. The same D10 constraint may apply to other EELVault scripts.

### Not included (deliberate)
- Memory, modal imprint, Charge, Life, Fatigue, Recovery, Fracture, Disintegrate, Space, stereo cross-coupling, FFT/STFT, FIR, oversampling, large delay buffers, LFO animation, randomization.
