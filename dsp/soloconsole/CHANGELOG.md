# Changelog

All notable changes to SoloConsole.

## [0.2.1] — 2026-08-07
### Fixed
- Restored the post-drive treble shelf to the audible signal path at both 1x and 2x rates;
  v0.2.0 updated the treble filter state but accidentally fed the pre-treble signal into
  the transformer rolloff.
- Restored causal odd-phase decimation: the FIR now begins on the newest odd oversample
  instead of stepping back to the even sample. The corrected 2x path matches the explicit
  reference convolution to floating-point precision and restores the 15-sample base-rate
  dry-path latency.
- Corrected OS-mode state flushing by resetting the loop index before clearing the decimator
  rings, and now also clears DC-blocker state, dry-delay history, and the dry-delay position.
### Preserved
- Native `slider1`–`slider8` controls and `@init` / `@slider` / `@block` / `@sample` sections.
- v0.2.0 fused 16-tap polyphase interpolation and rate-corrected 2x DC blocker.

## [0.2.0] — 2026-08-06
### Changed
- Interpolation now uses a fused 16-tap polyphase structure: the halfband even/odd tap
  sets each run one 16-tap convolution over the same 16-sample ring (instead of two
  full 32-tap convolutions over zero-stuffed slots). Bit-identical output (verified in
  `tools/audit_full.py`: max diff 0.0 end-to-end), half the interpolator loop cost.
- DC blocker now rate-corrected in the 2x path (`dcbR2 = 1 - (1 - dcbR) * 0.5`) so its
  pole frequency in Hz matches the 1x path.
- Drive slider default aligned to 6 dB (matches curated fallback).
- Smoothed params start at target at init (no startup ramp).
- OS-mode switch now flushes interp + decim ring buffers too, not just filter state.
### Added
- `tools/audit_full.py`: full-chain numpy parity harness proving v0.2 interp is
  bit-identical to v0.1 end-to-end.
### Removed
- Dead re-assignments (`sat = xin; xin = sat`) left in the v0.1 2x drive chain.

## [0.1.0] — 2026-08-06
### Added
- Experimental console drive entry for the vault.
- Polynomial soft-clip saturation with tube-style even-harmonic bias.
- 2x oversampling via windowed-sinc halfband FIR (32 taps), computed at init.
- Pre-drive bass shelf and post-drive treble shelf (RBJ-derived one-pole).
- Transformer rolloff, soft-knee ceiling, dry/wet mix.
- User controls (Input, Drive, Even, Bass, Treble, Output, Oversampling, Mix).
- Parameter smoothing, DC blocker, denormal protection, non-finite input sanitizer.
- UI-fallback defaults if the parameter syntax is unsupported on a given VM.
- Full measurement and documentation of the saturation curve's harmonics and aliasing
  behavior (see README "Why this saturation curve").
