# ANIMA Changelog

All notable changes to ANIMA will be documented in this file.

## [1.0.1] - v1.0.1 Corrective Release (DEFINITIVE)

### Fixed
- Critical: LFO2 phase discontinuity eliminated. Frequency multiplication (1.7x) moved into the oscillator increment. Sine evaluation changed from sin(lfo2 * 1.7 + 1.3) to sin(lfo2 + 1.3). Removes audible glitch every ~4.3 seconds.
- Critical: LFO2 double phase offset removed. Initialization changed from 1.3 to 0. Phase offset is now applied only in the sine argument.
- Important: DC blocker separated from musical high-pass. Post-saturation DC removal now uses a dedicated 5 Hz coefficient instead of reusing the 30 Hz HPF coefficient. Eliminates the double 30 Hz high-pass that was attenuating sub-bass.

### Added
- Non-finite input protection (NaN and Infinity sanitizer) at the input stage.
- Precomputed LFO increments in [init](init) for improved clarity.
- Dedicated dcBlockHz parameter (5 Hz) in [init](init).

### Changed
- Redundant division (1 / tapeGain) replaced with direct expression (1 + tapeAmt * env) in auto makeup target calculation. Removes one per-sample division.
- Saturation stage comments updated to "Asymmetric Mixed-Harmonic Saturation" for technical accuracy.
- Limiter comments updated to "Transition-Aware Safety Limiter" for technical accuracy.
- Thermal Hysteresis comments updated to "Program-Dependent Release" for technical accuracy.

### Deferred to v1.1.0
- Recursive quadrature LFO oscillator (performance optimization).
- Low-rate LFO evaluation with interpolation (performance optimization).
- Sine lookup table (performance optimization).

## [1.0.0] - v1.0.0 Denormal Protection (DEFINITIVE)

### Added
- Denormal protection via alternating DC offset guard
- Prevents CPU spikes during digital silence

## [0.5.0] - v0.5.0 ISP Estimation

### Added
- Inter-Sample Peak estimation in the safety limiter
- Derivative-based ISP detector with 0.25 coefficient
- Protects DAC from inter-sample overshoots

## [0.4.0] - v0.4.0 Thermal Hysteresis

### Added
- Program-dependent release for tape compression
- Fast release: 150 ms for transients
- Slow release: 600 ms for sustained material
- Program memory detector: 200 ms

## [0.3.0] - v0.3.0 Hermite Interpolation

### Added
- 4-point Hermite cubic interpolation for micro-flutter delay
- Positive-modulo safety for backward buffer lookup
- Preserves high-frequency content during modulation

## [0.2.0] - v0.2.0 Auto Makeup Gain

### Added
- Program-dependent auto makeup gain
- Base gain: +2.4 dB
- Maximum gain: +3.0 dB
- Attack: 50 ms, Release: 400 ms

## [0.1.0] - v0.1.0 Base Analog Chain

### Added
- Initial working release
- Core analog emulation chain
- Fixed makeup gain: +2.4 dB
- Linear interpolation for micro-flutter delay
- Fixed 300 ms tape release
- Safety limiter at -0.3 dBFS