# ANIMA Changelog

All notable changes to ANIMA will be documented in this file.

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