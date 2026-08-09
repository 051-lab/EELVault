# Changelog

All notable changes to SoloConsole.

## [0.2.2] — 2026-08-07
### Added
- `tools/audit_soloconsole.py`: dependency-free repository audit covering native EEL2 structure, slider mapping, current/archive identity, polyphase interpolation parity, causal decimation parity, 15-sample impulse latency, Treble routing, OS-state clearing, DC-block tuning, allocation consistency, and release metadata.

### Changed
- DC-block feedback is now derived directly from sample rate for a 5 Hz pole at both 1x and 2x processing rates.
- Initial oversampling state now sets `prev_os = os_active`, preventing the first unrelated slider change from forcing a redundant rate-state flush.
- Decimator history allocation reduced from 64 to the 32 positions actually addressed by the `OS_MASK = 31` ring.
- README and metadata now describe the tone filters as RBJ biquad shelves and `Mix` as a pre-drive blend rather than a raw-input dry/wet control.
- Latency documentation now uses the exact 15-sample 2x invariant rather than one fixed millisecond value.

### Preserved
- v0.2.1 saturation curve, tone topology, transformer rolloff, fused polyphase interpolation, causal odd-phase decimation, 15-sample latency, wet-path ceiling, output gain, and blend routing.

## [0.2.1] — 2026-08-07
### Fixed
- Restored the post-drive treble shelf to the audible signal path at both 1x and 2x rates; v0.2.0 updated the treble filter state but accidentally fed the pre-treble signal into the transformer rolloff.
- Restored causal odd-phase decimation: the FIR now begins on the newest odd oversample instead of stepping back to the even sample. The corrected 2x path matches the explicit reference convolution to floating-point precision and restores the 15-sample base-rate dry-path latency.
- Corrected OS-mode state flushing by resetting the loop index before clearing the decimator rings, and now also clears DC-blocker state, dry-delay history, and the dry-delay position.

### Preserved
- Native `slider1`–`slider8` controls and `@init` / `@slider` / `@block` / `@sample` sections.
- v0.2.0 fused 16-tap polyphase interpolation and rate-adjusted 2x DC blocker concept.

## [0.2.0] — 2026-08-06
### Changed
- Interpolation now uses a fused 16-tap polyphase structure: the halfband even/odd tap sets each run one 16-tap convolution over the same 16-sample ring instead of two full 32-tap convolutions over zero-stuffed slots.
- The fused interpolator was validated against the explicit zero-stuffed interpolation reference, reducing interpolator loop cost while preserving that interpolation result to floating-point precision.
- DC blocker received a rate-adjusted 2x feedback coefficient so its pole stayed approximately aligned between the 1x and 2x paths.
- Drive slider default aligned to 6 dB, matching the curated fallback.
- Smoothed parameters start at target at initialization to avoid a startup ramp.
- OS-mode switching began flushing interpolation and decimation ring buffers in addition to filter state.

### Note
- Earlier wording that described the complete v0.2.0 end-to-end chain as bit-identical was too broad. v0.2.1 later corrected Treble routing and decimator phase/alignment regressions. The validated parity claim for v0.2.0 is therefore limited to the fused interpolation stage itself.

## [0.1.0] — 2026-08-06
### Added
- Experimental console drive entry for the vault.
- Polynomial soft-clip saturation with tube-style even-harmonic bias.
- 2x oversampling via windowed-sinc halfband FIR (32 taps), computed at init.
- Pre-drive bass shelf and post-drive treble shelf.
- Transformer rolloff, soft-knee wet-path ceiling, and pre-drive blend.
- User controls (Input, Drive, Even, Bass, Treble, Output, Oversampling, Mix).
- Parameter smoothing, DC blocker, denormal protection, non-finite input sanitizer.
- UI-fallback defaults if the parameter syntax is unsupported on a given VM.
