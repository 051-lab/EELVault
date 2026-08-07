# Changelog

All notable changes to SoloConsole.

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