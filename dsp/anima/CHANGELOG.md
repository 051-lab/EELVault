# ANIMA Changelog

All notable changes to ANIMA will be documented in this file.

## [1.0.0] - 2025-01-01

### Added
- Initial stable release
- Core analog emulation chain: HP → Shelf → Saturation → Tape → Tilt → DC → Flutter → M/S → Limiter
- Auto makeup gain with +2.4 dB base and +3.0 dB maximum
- 4-point Hermite cubic interpolation for micro-flutter delay
- Fixed-parameter design (no user sliders)
- Safety limiter at -0.3 dBFS
- Program-dependent tape compression
- Dynamic tilt EQ with Fletcher-Munson compensation
- Mid/Side width lift at +0.7 dB

### Fixed
- Replaced `while()` buffer clearing with `loop()` for EEL2 VM compatibility
- Fixed negative bitwise AND in Hermite interpolation using positive-modulo offset
- Fixed double-compression limiter collapse
- Removed ISP estimator and denormal guard for initial stable release (to be re-added in future updates)