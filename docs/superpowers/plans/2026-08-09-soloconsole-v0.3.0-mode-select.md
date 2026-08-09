# SoloConsole v0.3.0 — Style-select saturation (plan)

- **Date:** 2026-08-09
- **Status:** Implemented
- **Files:** `dsp/soloconsole/soloconsole.eel`, `dsp/soloconsole/metadata.json`, `tools/audit_soloconsole.py`, `dsp/soloconsole/versions/v0.3.0-mode-select.eel`

## Goal

Add a per-sample distortion-style selector (`Style`) to SoloConsole without forking the signal chain, adding allocation, or changing mode 0 behavior. The Style value comes from a ninth host control (`slider9`); hosts without one keep `0` and hear exactly the v0.2.2 curve.

## Design constraints

- EEL2 grammar only: chained ternaries, no `if/else if`, no functions, static heap only.
- The saturation block is byte-identical at all six chain sites (L/R x even/odd at 2x, L/R at 1x); the dispatch therefore lives at every site and is validated by a site-count check in the audit.
- Mode 0 must remain bit-identical to v0.2.2: it is the original `u - u^3/3` polysoft with the unchanged bias-cancel step.
- All modes share the downstream DC block, treble shelf, transformer rolloff, and soft-knee ceiling. The bias-cancel `sat - b + b^3/3` runs after every mode to keep the even-harmonic staging consistent.

## Styles

| # | Name | Curve (after `u = t + b`) | Properties |
|---|------|---------------------------|------------|
| 0 | Polysoft | `au>1 ? ±2/3 : u - u^3/3` | v0.2.2 behavior, bit-identical |
| 1 | Foldback | `au<=1 ? u : sign(u) * (1 - abs((au%2)-1))` | continuous across ±1, transparent below, triangle wrap, bounded ±1 |
| 2 | Asymmetric | `u>0 ? u/(1+0.3u) : u/(1-0.6u)` | monotonic, bounded +3.33 / -1.67, even-rich |
| 3 | Bitcrush | `floor(u*2^bits + 0.5)/2^bits`, `bits = 3 + floor(even*8)` | uniform quantization, 3..11 bits via the Even slider |

## EEL2 notes

- `%` is float fmod: `au % 2.0` gives the fold cycle used by mode 1.
- `pow(2, cb)` replaces any shift idiom; `floor` is used for both bit mapping and mid-tread rounding.
- No new heap allocation; variables `fw`, `cb`, `csc` are plain globals.

## Verification

`tools/audit_soloconsole.py` now runs 20 checks:

- v0.3.0 version marker, `slider1..slider9` ordering, current/archive byte identity.
- All v0.2.2 invariants preserved (polyphase parity, causal decimation, 15-sample latency, 5 Hz DC pole at 44.1/48/96 kHz, six treble handoffs, OS-switch flush, 32-slot ring, initial-OS hardening).
- Dispatch present at all six saturator sites; fallback `sat_mode = 0` at init; `slider9` clamped to 0..3.
- Numeric invariants: all four modes finite and bounded pre-limiter; foldback transparent/continuous at ±1; asymmetric monotonic and asymmetric through zero; bitcrush lands on the exact `2^bits` grid for Even = 0/25/50/100 %.
- Metadata: version, archive path, `satMode: 0`, feature flags.

## Risks / follow-ups

- Mode switches are not smoothed: a Style change is a step in the nonlinear curve (downstream filters see a continuous input, but a step can excite the treble shelf briefly). Acceptable for v0.3.0; a short crossfade is future work.
- `slider9` exposure depends on host UI support; documented in README.
