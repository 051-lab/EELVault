# DRAGON On-Device Finalist Verification & Listening Protocol

## Status

Two experiment-only device finalists now exist on branch `dragon-adaptive-control-experiments`:

- `dsp/dragon/experiments/dragon-acceleration-body.eel`
- `dsp/dragon/experiments/dragon-totape-body.eel`

Production `dsp/dragon/dragon.eel` is unchanged. The experiment selection file also remains at the safe v1.0.0 baseline (`LF=none`, `HF=current-s6`, `Body=body-none`).

## Fresh verification evidence

### Static candidate contract

The exact candidate source strings used for the repository writes were checked against the device-candidate audit contract.

- Acceleration finalist: 13/13 static contract checks satisfied.
- ToTape finalist: 13/13 static contract checks satisfied.
- Both have balanced parentheses in the generated EEL source.
- Both contain exactly eight sliders.
- Both use native `@init`, `@slider`, `@block`, `@sample` sections.
- Neither exposes the old `bump:` / LF Contour slider.
- Both retain the fixed v1.0.0 `rbj_peak(50, 0.95, 1)` reference contour.
- Both place Pear after the S8 HF shelf and before S9 hiss.
- Both keep Pear state warm continuously while discarding Pear output at `Body≈0`, preventing a cold-state transient when the Body control is moved.

### Acceleration EEL algorithm equivalence

The EEL finalist uses a 64-sample ring per channel instead of physically shifting the Airwindows history array. The ring implementation was directly compared against the already validated Python `AccelerationStage` using the fixed 48 kHz source-derived vector.

Result:

- maximum output error: `0.0`
- detector sense vector error: `0.0`

The ring therefore preserves the validated Acceleration detector semantics exactly for the test vector.

### ToTape EEL algorithm equivalence

The EEL ToTape residual/envelope/damping equations were compared sample-by-sample with the already validated Python `ToTapeHFStage` on a 48 kHz / 10 kHz test stream.

Result:

- maximum sample error: `0.0`

### Combination evidence

Formal numerical combination evidence remains recorded in:

`docs/superpowers/reports/2026-08-20-dragon-lf-none-combination-evidence.md`

The primary result remains:

- current S6 bass-to-HF coupling span: roughly `9.70-9.76 dB`
- Acceleration 0.32: roughly `5.93-5.94 dB`
- ToTape 2500/2: roughly `5.95-5.96 dB`

Body position changes those values by only a few thousandths of a dB.

### Branch integrity

A fresh `main...dragon-adaptive-control-experiments` comparison shows the two device candidates only as new files under `dsp/dragon/experiments/`; production Dragon, the v1.0.0 archive, metadata, and `tools/audit_dragon.py` are not changed in the branch diff.

## Important verification limitation

This ChatGPT execution environment does not contain a RootlessJamesDSP/EEL VM host capable of compiling and running the `.eel` scripts directly. The source structure and candidate algorithms have been checked, but **actual EEL parse/runtime validity and Android real-time CPU behavior must be confirmed on-device before either candidate can be considered promotable**.

That host test is the purpose of this round.

---

# Controlled On-Device A/B Protocol

## Files

A — control:

`dsp/dragon/dragon.eel`

B — primary candidate:

`dsp/dragon/experiments/dragon-acceleration-body.eel`

C — conservative alternate:

`dsp/dragon/experiments/dragon-totape-body.eel`

## Keep the playback chain controlled

For the first comparison:

- use one LiveProg script at a time;
- disable unrelated EQ/bass enhancement/spatial effects if practical;
- use identical playback volume;
- disable loudness normalization if it changes between trials;
- use the same source files and the same listening position;
- do not compensate a candidate by changing Drive, Bias, Compression, HF Rolloff, or Output Trim during the first pass.

## Phase 0 — load/runtime gate

Load B, then C.

For each candidate verify:

1. script parses and produces audio;
2. all eight controls appear;
3. no silence, NaN behavior, runaway level, clicks, or obvious instability;
4. playback remains smooth for at least several complete tracks;
5. moving Body slowly from 0 to -0.5 and back does not produce a cold-filter thump or discontinuity.

If either candidate causes stutter, record which one and at what sample rate/device/load. Do not tune sound until runtime stability is known.

## Phase 1 — Reference comparison (`Body=0`)

Start B and C at their defaults with `Body=0`.

Compare each against A on material with:

- strong kick/sub-bass plus cymbals/hi-hats;
- bass guitar/808 plus bright vocals;
- dense full-range mixes;
- sparse transient-heavy material.

Primary question:

> When the bass becomes large, do the highs remain naturally present instead of the entire presentation becoming darker/heavier?

Listen for:

- cymbal/hat presence during kick hits;
- vocal consonants during bass peaks;
- stereo image stability;
- transient attack;
- whether B sounds unnaturally open or sharp;
- whether C still sounds too much like the old dark S6.

## Phase 2 — Challenger correction (`Body=-0.5`)

This is the most important practical setting.

Set Body to `-0.5` on B and C.

Expected numerical intent is approximately half of the full Lean correction: roughly 2-2.5 dB less energy through the troublesome low-mid/body region while true 50 Hz bass remains nearly unchanged.

Listen specifically for:

- 100-300 Hz congestion;
- kick/bass separation;
- male/lower vocal chestiness;
- whether sub-bass still feels physically present;
- whether the mix becomes thinner rather than cleaner.

The desired result is **less body congestion without losing foundation**.

## Phase 3 — range/extreme check

Briefly test:

- `Body=-1.0`
- `Body=+0.5`
- `Body=+1.0`

This is not a search for the best everyday setting. It checks whether the control range is useful and well-behaved.

At Full Lean, watch for excessive thinning above 500 Hz. At Full, watch for the old low-mid control problem returning too aggressively.

## Phase 4 — CPU/stability comparison

This matters heavily on Android.

### Acceleration candidate

Acceleration uses fixed-rate biquad coefficients and arithmetic/lookup history in the sample loop. It removes the old S6 dynamic coefficient `exp()` from that stage.

### ToTape candidate

ToTape has the simpler conceptual detector, but its dynamic damping coefficient is recomputed from independent channel envelopes and therefore performs more per-sample transcendental work.

For both candidates monitor:

- stuttering;
- underruns/glitches;
- heat/battery behavior if noticeable;
- stability while the screen is off;
- behavior while changing Body;
- behavior at 44.1 versus 48 kHz if the host exposes both.

If eight-stage Pear proves too expensive, do **not** immediately abandon the Body architecture. The numerical research already found a retuned four-stage Pear approximation capable of following the eight-stage magnitude curve within roughly 0.04 dB RMS / <0.10 dB maximum error. That optimization is intentionally deferred until the full Pear version proves sonically worthwhile.

## Recommended scoring sheet

Score each candidate from 1-5 for:

| Criterion | Control A | Acceleration B | ToTape C |
|---|---:|---:|---:|
| Bass no longer darkens highs | | | |
| 100-300 Hz controllability at Body -0.5 | | | |
| True sub-bass preserved | | | |
| Treble naturalness | | | |
| Transient naturalness | | | |
| Stereo stability | | | |
| No pumping/modulation artifacts | | | |
| CPU/playback smoothness | | | |
| Overall Dragon identity | | | |

Also write one sentence for each candidate answering:

> What did this version do that the other two did not?

## Decision rule after listening

Acceleration remains the numerical primary finalist, but listening can overturn it.

- Promote Acceleration if its openness/transients sound natural and CPU is stable.
- Promote ToTape if Acceleration sounds unnaturally open/edgy and ToTape retains the desired tape character without returning the bass-driven darkness.
- Promote neither if the new HF behavior sounds less Dragon-like than v1.0.0.
- Add Foundation only if the device round exposes a remaining real LF-headroom problem that Body cannot solve; do not add it preemptively.

No production merge should occur before these observations are recorded.
