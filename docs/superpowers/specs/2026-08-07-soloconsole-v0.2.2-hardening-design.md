# SoloConsole v0.2.2 Validation & Hardening Design

## Goal

Harden SoloConsole v0.2.1 without changing its core sonic architecture. v0.2.2 must make the current implementation reproducibly testable, correct known sample-rate/state-handling inaccuracies, and align documentation/metadata with the actual DSP behavior.

## Scope

### In scope

1. Add repository-owned numerical audit tooling for SoloConsole.
2. Verify native EEL2 structure and sequential `slider1`–`slider8` declarations.
3. Verify fused-polyphase interpolation against an explicit zero-stuffed FIR reference.
4. Verify causal odd-phase decimation against an explicit FIR reference.
5. Verify 15-sample 2x base-rate latency by impulse analysis.
6. Verify Treble affects the audible 1x and 2x paths.
7. Verify 1x/2x state switching clears all rate-dependent state.
8. Replace fixed DC-block feedback with sample-rate-derived 5 Hz coefficients at both 1x and 2x rates.
9. Initialize `prev_os` to the actual initial oversampling state so the first unrelated slider change cannot trigger an unnecessary flush.
10. Reduce the decimator history allocation from 64 to the 32 positions actually addressed.
11. Correct SoloConsole metadata and README terminology: RBJ biquad shelves, 15-sample latency, sample-rate-derived 5 Hz DC blocker, and pre-drive blend semantics for Mix.
12. Add a v0.2.2 archived version file and changelog entry.

### Explicitly out of scope

- No 4x oversampling.
- No final safety limiter/ceiling redesign.
- No change to Mix routing semantics; document the existing pre-drive blend instead.
- No tone-control smoothing redesign.
- No saturation-curve, transformer-rolloff, or harmonic-tuning changes.
- No auto makeup gain or console-glue dynamics.

## Architecture

Keep the v0.2.1 signal path unchanged:

`Input -> input gain -> bass shelf -> optional 2x oversampling -> saturation/bias -> DC blocker -> treble shelf -> transformer rolloff -> soft-knee wet-path ceiling -> downsample -> output gain -> pre-drive blend -> stereo output`

Only three production-code hardening changes are allowed:

1. `dcbR` and `dcbR2` become sample-rate-derived 5 Hz pole coefficients.
2. `prev_os` starts equal to the initialized oversampling mode.
3. `OS_BUF` is reduced to 32 because the decimator ring is masked by `OS_MASK = 31`.

Everything else in v0.2.1's DSP topology and tuning must remain unchanged.

## Validation tooling

Create a self-contained Python audit tool under `tools/` using only the Python standard library. It must run without NumPy or third-party packages so validation is easy on Windows, WSL, Linux, and CI.

The audit must fail non-zero when a required invariant is violated and print a concise per-check result. Required checks:

- native section markers and eight sequential sliders;
- no legacy named slider declarations;
- v0.2.2 current/archive text identity;
- polyphase interpolation parity against explicit zero-stuffed reference;
- causal decimation parity against explicit reference;
- 15-sample impulse latency;
- sample-rate-derived DC blocker accuracy at 44.1, 48, and 96 kHz;
- Treble-to-transformer handoff present in all six processing paths;
- complete OS-switch state clearing;
- decimator allocation/mask consistency;
- metadata version and latency consistency.

## Compatibility

Targets remain RootlessJamesDSP and JDSP4Linux. Preserve native `@init`, `@slider`, `@block`, and `@sample` sections and `slider1` through `slider8` declarations. No new dependencies may be introduced into the EEL2 script.

## Release acceptance criteria

v0.2.2 is ready for merge only when:

1. the audit tool passes from a clean checkout using standard Python;
2. numerical FIR parity error is at floating-point noise level;
3. measured oversampling latency is exactly 15 base-rate samples;
4. the DC blocker measures approximately 5 Hz at 44.1/48/96 kHz;
5. current and archived v0.2.2 `.eel` files are identical;
6. the branch diff contains only SoloConsole hardening, validation tooling, and related documentation;
7. no automated or manual verification reports a regression in the v0.2.1 saturation/tone/oversampling topology.
