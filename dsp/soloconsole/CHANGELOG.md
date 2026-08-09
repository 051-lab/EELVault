# Changelog

All notable changes to SoloConsole.

## [0.3.2] — 2026-08-09
### Added
- Live parameter bridge at the top of `@sample`: the nine `slider*` variables are read every sample and compared against a snapshot cache; on any change the same target/coefficient recompute and OS-mode flush as `@slider` runs once. This follows the direct-read pattern of device-proven JamesDSP effects (e.g. PrismSoundSphere), whose VM never exhibits an active `@slider` section; hosts that do fire `@slider` are unaffected (the cache is already aligned and the bridge stays silent).
- Cache snapshot initializes from the declared slider defaults, so a virgin startup runs the bridge as a no-op.

### Preserved
- All v0.3.1 behavior; the four style cores, dropdown declaration, and bit-identical Mode 0 / Polysoft path.

## [0.3.1] — 2026-08-09
### Changed
- `Style` (`slider9`) now declares a native option-list dropdown — `{Polysoft,Foldback,Asymmetric,Bitcrush}` — instead of a bare fader. Hosts that ignore the option list still see a 0..3 slider and keep identical behavior; the value, clamping, and DSP are unchanged.
- Audit harness now also verifies the dropdown declaration (21 checks).

### Preserved
- All v0.3.0 behavior: dispatch coverage, style invariants, and the bit-identical Mode 0 / Polysoft path.

## [0.3.0] — 2026-08-09
### Added
- `Style` selector (`slider9`): 0 = Polysoft, 1 = Foldback, 2 = Asymmetric, 3 = Bitcrush, implemented as chained EEL2 ternaries at all six saturator sites.
- Foldback style: triangle-wave wrapping at ±1 through float `%` fmod, continuous and transparent below the threshold.
- Asymmetric style: monotonic rational soft clip (`u/(1+0.3u)` positive, `u/(1-0.6u)` negative, bounded +3.33/−1.67).
- Bitcrush style: mid-tread quantization at `2^bits`, bits 3..11 mapped from the Even slider.
- Audit harness extended to 20 checks: slider1..9 ordering, v0.3.0 archive identity, dispatch coverage at all six sites, style fallback/clamping, numeric invariants per style (finiteness/boundedness, foldback linearity/continuity, asymmetric monotonicity, bitcrush grid), and metadata feature flags.

### Preserved
- Mode 0 is bit-identical to v0.2.2 (same curve, bias staging, and full downstream chain at both rates).
- v0.2.2 fused polyphase interpolation, causal odd-phase decimation, 15-sample latency, sample-rate-derived DC blocker, and OS-switch state flushing.

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
