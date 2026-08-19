# DRAGON Adaptive Control Experiments — Design

## Goal

Evaluate a small set of Airwindows-informed mechanisms that may improve DRAGON's low-frequency/low-mid controllability and high-frequency dynamic behavior without bloating the UI, breaking the v1.0.0 reference calibration, or committing unproven processing to the production `dragon.eel` signal path.

The immediate engineering question is not "which Airwindows plugin should DRAGON include?" It is:

> Which minimal mechanisms, if any, measurably and audibly improve DRAGON's behavior across demanding playback systems while preserving a true reference state?

This design authorizes isolated experiments and audit-harness work. It does **not** authorize permanent production changes to `dsp/dragon/dragon.eel`.

## Baseline

The frozen comparison baseline is DRAGON v1.0.0 on `main`:

`Input -> 7 Hz DC block -> record emphasis -> 18 kHz anti-alias LP -> linked tape compression -> asymmetric tanh saturation -> broadband-envelope-driven dynamic HF damping -> wow/flutter -> crosstalk -> replay EQ -> hiss -> output trim -> 7 Hz DC block -> soft limiter -> hard clamp`

The present architectural concern is the S4/S6 coupling:

- the linked record-level envelope is computed from `max(abs(L), abs(R)) * driveLin`;
- the same envelope drives tape compression gain reduction;
- the same envelope also lowers S6's one-pole damping cutoff;
- therefore strong LF energy can indirectly increase HF attenuation even when HF energy itself has not increased.

The usability concern is independent but related: the current `LF Contour` control is unipolar `0..+4 dB`, while the replay path also has a fixed +1 dB low shelf. The current UI can add warmth but cannot intentionally lean out the upper-bass/low-mid body region that became difficult to control on a high-output automotive playback system.

## Design principles

1. **Reference first.** v1.0.0 remains immutable as the baseline during experiments.
2. **NONE may win.** Each experimental category must allow the baseline/no-new-mechanism result to win.
3. **No control creep.** The target production UI remains eight user controls. A ninth control requires separate design approval.
4. **Neutral means neutral.** Any future `Body = 0` or equivalent reference position must bypass adaptive coloration and reproduce the calibrated reference behavior within numerical tolerance.
5. **Mechanisms, not plugin ports.** Airwindows code is research material and an algorithmic reference. DRAGON should adopt only the minimum mechanism needed for its own signal path.
6. **Mobile-first CPU discipline.** RootlessJamesDSP Android stability and CPU cost are first-class acceptance criteria.
7. **Measurement before taste.** Candidate promotion requires numerical evidence before on-device listening decides among finalists.
8. **No hidden calibration stacking.** A candidate that adds permanent linear LF/HF tilt must justify that change against the existing replay calibration.
9. **Stereo behavior must be intentional.** Low-frequency control should be linked or otherwise proven not to shift the stereo image unpredictably.
10. **Production `dragon.eel` remains untouched until a combined candidate passes the full gate.**

## Research basis

The experiment pool is based on source-level review of Airwindows implementations and the existing DRAGON source.

Primary Airwindows mechanisms retained for experimentation:

- `Highpass`: level-dependent high-pass coefficient modulation using its Tight behavior.
- `StoneFireComp`: low-frequency `Stone` extraction and independent dynamics as a conceptual alternative for LF headroom control.
- `Sinew` / Air4's `DarkF`+`Ratio`: conditional slew limiting that can leave small-signal response unchanged until slew exceeds a threshold.
- `Acceleration2`: waveform-curvature detector that crossfades toward a smoothed signal in proportion to high-frequency/rapid-change activity.
- `ToTape9`: explicit high-frequency residual extraction and frequency-aware tape behavior.
- `PearLiteEQ`: Pear-derived four-region decomposition, with particular interest in the `LMid`/`Bass` relationship for playback body adaptation.

Secondary references kept out of the first production-oriented matrix unless a primary candidate fails:

- `SubTight` for deep-sub containment;
- `Hull2` and `SmoothEQ3` as lighter spectral-decomposition fallbacks;
- `Stonefire` as a broader Bass/Mid/Treble decomposition reference;
- `FatEQ`/`Density3` only if static body reduction proves perceptually thin and a density-oriented correction is justified.

## Experimental branch and file boundaries

All work for this design lives on branch:

`dragon-adaptive-control-experiments`

Production baseline files must not be modified during isolated-candidate work:

- `dsp/dragon/dragon.eel`
- `dsp/dragon/versions/v1.0.0-absolute-lab-calibration.eel`
- `dsp/dragon/metadata.json`

The existing dependency-free `tools/audit_dragon.py` remains the authoritative v1.0.0 audit. Experimental numerical models should be added in a separate focused module so baseline assertions do not become conditional on candidate code.

Planned experiment-owned files:

- `tools/dragon_experiments.py` — stdlib-only candidate DSP/reference models and reusable measurement helpers.
- `tools/audit_dragon_experiments.py` — deterministic experiment matrix, regression checks, reports, and pass/fail policy.
- `docs/superpowers/plans/2026-08-19-dragon-adaptive-control-experiments.md` — implementation plan after this design is approved.

No `.eel` candidate file is required for the first numerical gate. On-device `.eel` candidates are created only for mechanisms that survive the Python audit.

## Experiment 0 — baseline characterization

Before evaluating new mechanisms, reproduce and lock measurements of current DRAGON behavior at 44.1 and 48 kHz.

Required baseline measurements:

1. small-signal frequency response from 20 Hz to 20 kHz;
2. current S6 damping cutoff as a function of the linked envelope;
3. the bass-to-HF coupling test defined below;
4. 50/60/80/100/150/200/300 Hz output behavior at multiple signal levels;
5. limiter engagement rate on deterministic stress fixtures;
6. peak/RMS headroom through S4/S5/S6;
7. left/right parity with matched input;
8. deterministic confirmation that v1.0.0's reference model remains unchanged.

The experiment audit must report baseline results before candidate results so later comparisons are always anchored to the same reference.

## Canonical Challenger regression fixture

The key architectural regression test is a two-tone fixture:

- LF carrier: 60 Hz;
- HF probe: 10 kHz at fixed amplitude;
- LF amplitude swept through at least `-30, -20, -12, -6, -3, 0 dBFS` input levels;
- HF probe remains fixed for the entire sweep;
- run at 44.1 and 48 kHz.

Primary metric:

`delta_hf_db = measured 10 kHz output level at each LF amplitude - measured 10 kHz output level at the -30 dBFS LF reference condition`

Interpretation:

- current S6 is expected to show increasing negative `delta_hf_db` as LF level raises the broadband envelope;
- a successful HF replacement should keep `delta_hf_db` materially flatter when HF amplitude is unchanged;
- the same candidate must still react when the 10 kHz probe itself is swept upward.

No fixed pass threshold is declared before the baseline is measured. Candidate ranking is relative to v1.0.0, but a candidate must demonstrate a clear reduction in LF-caused HF attenuation without introducing a larger unrelated tonal error.

## LF experiment family

### LF-A — v1.0.0 baseline

No new LF processing.

Purpose: control condition.

### LF-B — literal Airwindows Highpass/Tight model

Implement the source mechanism faithfully in Python:

- source-derived `iirAmount = A^3 / overallscale`;
- `tight = B*2 - 1` with positive Tight behavior;
- per-sample offset derived from instantaneous `abs(sample)`;
- alternating A/B one-pole state topology;
- no dither contribution in the numerical model.

Purpose:

- quantify the exact LF restraint and nonlinear side effects of the original mechanism;
- establish whether its audio-rate coefficient modulation creates unacceptable harmonic/intermodulation products for a reference cassette emulator.

This literal version is an experimental reference, not the preferred production architecture.

### LF-C — DRAGON Foundation Guard

Create a DRAGON-specific derivative of the Highpass idea with the following structural requirements:

- stereo-linked detector;
- detector responds to low-frequency energy rather than full-band instantaneous magnitude;
- detector probe uses a low-pass region whose initial search space is 80–150 Hz;
- attack/release smoothing occurs before cutoff modulation;
- cutoff movement is bounded to a low-sub/upper-sub operating region and must not become a 100–300 Hz corrective EQ;
- the processing path remains zero-lookahead;
- at guard amount `0`, the candidate is a numerical bypass;
- no new user-facing threshold/ratio/attack/release controls.

The first implementation searches fixed internal detector/cutoff combinations numerically. These values are experiment constants, not production controls.

Promotion criteria:

- materially reduces excess LF peak/headroom pressure versus baseline stress fixtures;
- lower THD/IMD than literal Highpass at equivalent LF restraint;
- no meaningful stereo image shift on asymmetric stereo fixtures;
- no audible-band static high-pass signature when the detector is inactive or minimally active;
- cheaper or clearly better sounding than LF-D.

### LF-D — lightweight StoneFire-inspired guard

Do not port full StoneFireComp.

Build the smallest defensible alternative that captures its design lesson:

- derive a low-frequency/foundation component;
- derive a complementary remainder;
- apply a very shallow linked gain-control action only to the foundation component;
- cap maximum gain reduction at a small experiment-controlled value;
- recombine exactly enough to preserve unity behavior when no gain reduction occurs.

The first numerical version may use a simpler complementary low-pass split rather than the full Airwindows Kalman structure. A literal Kalman port is authorized only if the lightweight model cannot reproduce the relevant behavior.

Promotion criteria:

- must outperform LF-C in at least one meaningful category (LF transparency, distortion, dynamic control, or on-device sound) enough to justify its higher state/CPU complexity;
- otherwise LF-C wins by simplicity.

### LF outcome policy

Allowed outcomes:

- LF-C wins;
- LF-D wins;
- LF-B wins only if its nonlinear character proves uniquely appropriate and acceptably transparent;
- NONE wins and production DRAGON receives no LF guard.

`SubTight` is not part of this first matrix. It returns only if all LF finalists leave a clearly identified deep-sub looseness problem.

## HF experiment family

### HF-A — current S6 baseline

Current behavior:

- S4 linked broadband envelope;
- `envN = min(1.6, env*2)`;
- `dfc = max(7000, 30000/(1 + 3*envN))`;
- one-pole low-pass at the resulting cutoff.

This is the control condition.

### HF-B — exact Sinew model

Implement the standalone Airwindows Sinew mechanism faithfully, excluding dither:

- maintain previous output sample per channel;
- derive an allowed per-sample slew threshold;
- modulate threshold with `cos(last^2)` as in the source;
- constrain only samples whose slew exceeds the threshold;
- preserve unchanged samples when they remain below threshold.

Purpose:

- test whether conditional slew limiting can replace S6's permanently active one-pole loss;
- measure how much small-signal FR is preserved;
- quantify harmonic/IMD changes and waveform peak behavior.

The first audit must use exact `cos()`. Polynomial or table approximations are explicitly deferred until Sinew proves worthy sonically and numerically.

### HF-C — Acceleration-DRAGON

Do not port the complete Acceleration2 response.

Retain the source-derived detector concept:

- spaced first differences;
- signed-square terms `d * abs(d)`;
- activity from the difference between successive signed-square terms;
- sample-rate-aware spacing;
- activity normalized/clamped to a `0..1` blend factor.

Replace Acceleration2's full fixed/output filtering with a DRAGON-compatible dynamic smoothing target that does not introduce an additional unconditional HF rolloff.

Purpose:

- test whether waveform curvature is a better trigger for tape-like HF softening than amplitude or an explicit frequency split.

### HF-D — ToTape-DRAGON

Implement an explicit HF residual detector:

- low-pass the signal at a fixed experiment-controlled crossover;
- `hf_residual = signal - lowpassed_signal`;
- rectify/smooth HF residual activity;
- use the HF-only envelope to control a bounded softening mechanism;
- keep the detector independent of the S4 broadband compression envelope.

The action stage should initially use the existing Dragon one-pole S6 topology so the experiment isolates the **detector** difference before testing a different softening curve.

Purpose:

- determine whether a simple frequency-specific detector fixes the coupling with lower complexity and more intuitive tuning than HF-B/HF-C.

### HF-E — Slew4 detector fallback

Do not implement unless HF-B through HF-D fail to produce a clear winner.

If activated, use only Slew4's second-difference/acceleration-style activity detector. Do not port its variable moving-average bank.

### HF required measurements

For HF-A through HF-D:

1. canonical 60 Hz + 10 kHz Challenger regression fixture;
2. inverse fixture: fixed LF, swept 10 kHz amplitude;
3. pure-tone small-signal FR 20 Hz–20 kHz;
4. 1/5/10/15 kHz tone bursts for transient behavior;
5. 1 kHz + 10 kHz IMD fixture;
6. 60 Hz + 10 kHz IMD fixture;
7. impulse and square-wave edge behavior;
8. maximum sample-to-sample slew before/after;
9. CPU proxy operation/state counts documented alongside numerical results.

### HF outcome policy

Allowed outcomes:

- Sinew wins;
- Acceleration-DRAGON wins;
- ToTape-DRAGON wins;
- current S6 wins;
- NONE/current S6 with a smaller calibration correction wins.

No two HF mechanisms may be stacked merely because both sound interesting. A combined HF design requires evidence that each solves a distinct measurable problem.

## Body experiment family

Body adaptation is evaluated only after the baseline and at least one HF candidate are characterized. It is intentionally separated from LF dynamic headroom control.

### BODY-A — current LF Contour

Current v1.0.0 control:

- 50 Hz peak;
- Q 0.95;
- slider range `0..+4 dB`;
- fixed +1 dB 50 Hz low shelf remains in the replay chain.

### BODY-B — Pear-derived Body macro

The production intent, if Pear wins, is to **repurpose** `LF Contour` rather than add a ninth control.

Target UI semantics:

`Lean <- 0 / Reference -> Full`

Structural requirements:

- `Body = 0` reproduces reference Dragon playback behavior;
- negative range emphasizes reduction of low-mid body more than deep bass;
- positive range may retain the existing LF warmth concept but must be less aggressive than the negative corrective authority;
- no independent Bass/LMid/HMid/High controls are exposed;
- the first candidate must manipulate primarily Pear's LMid/Bass relationship;
- Pear processing should initially sit after replay EQ and before hiss so record-stage drive/saturation calibration is not changed by the Body macro;
- full PearLite stage count is benchmarked before any reduction;
- reduced-stage Pear is allowed only if its response/subjective behavior remains acceptably close;
- SmoothEQ3/Hull2 fallback work begins only if Pear is rejected on CPU or response grounds.

Initial tuning targets are intentionally asymmetric:

- negative Body should have enough authority to reduce the 100–300 Hz sense of thickness on bass-heavy playback systems;
- positive Body should preserve the current ability to add tasteful warmth without turning the macro into a generic bass boost.

Exact gain equivalents are determined by the audit and listening gates, not hard-coded by this design.

### Body required measurements

1. static FR at minimum, reference, and maximum positions;
2. reference null/bypass test at `Body = 0`;
3. detailed response sampling at 50/80/100/150/200/300/500/1000 Hz;
4. phase/group-delay comparison around the manipulated region;
5. peak/headroom change before the output limiter;
6. CPU/state cost at 44.1 and 48 kHz;
7. interaction test with the winning HF candidate;
8. interaction test with the winning LF guard, if any.

## Combination gate

Candidates are not promoted individually straight into production. After category winners are selected, test the following combinations in order:

1. winning HF mechanism only;
2. Pear Body only, if BODY-B wins;
3. winning LF mechanism only, if any;
4. HF + Body;
5. HF + LF;
6. Body + LF;
7. HF + Body + LF.

The smallest combination that solves the identified problems wins.

If `HF + Body` performs as well as `HF + Body + LF`, the LF mechanism is rejected.

If a candidate is redundant after combination, remove it even if it performed well in isolation.

## Numerical acceptance gates

A combined candidate may proceed to an on-device `.eel` build only when all of the following are true:

1. baseline `tools/audit_dragon.py` still passes unchanged;
2. experiment audit is deterministic and dependency-free;
3. candidate produces finite output for all fixtures;
4. no safety clamp is hit under fixtures where v1.0.0 did not hit it unless the difference is explicitly explained and approved;
5. no DC offset regression exceeds the v1.0.0 reference by a meaningful amount;
6. left/right matched-input parity remains within floating-point noise except for intentionally uncorrelated hiss fixtures where hiss is disabled for parity tests;
7. candidate does not add undocumented latency;
8. candidate reduces the specific metric it was designed to improve;
9. candidate does not introduce a larger unrelated regression in FR, THD, IMD, or headroom;
10. reference/bypass state is numerically verified where the mechanism is user-directed.

## On-device gate

Only numerical finalists receive `.eel` candidate builds.

Required targets:

- RootlessJamesDSP Normal variant;
- RootlessJamesDSP Debug four-slot variant where useful for controlled serial A/B;
- RootlessJamesDSP ViPER4Android Edition where useful for future deployment;
- OnePlus Nord N200 as the minimum-performance R&D device;
- Samsung S24 Ultra as a high-performance/reference listening target when available.

Required listening contexts:

1. headphones/earbuds with known tonal balance;
2. phone or small-speaker playback for translation;
3. a capable stereo/full-range system;
4. a strong automotive system when access is available, because the motivating issue appeared in that environment.

Listening notes must explicitly distinguish:

- deep-sub tightness;
- upper-bass weight;
- 100–300 Hz body;
- vocal/midrange preservation;
- cymbal/air preservation;
- transient softness;
- perceived loudness;
- pumping/modulation;
- stereo image stability;
- whether the effect still reads as a premium cassette deck rather than a generic mastering processor.

## CPU gate

No candidate is promoted based only on desktop/Python behavior.

For EEL2 finalists:

- measure stable playback with the candidate loaded alone;
- compare against v1.0.0 under the same device/app/audio conditions;
- test at 44.1 and 48 kHz where the host permits;
- test the Normal one-slot variant first;
- then test multi-slot variants to identify whether the candidate leaves reasonable headroom for serial DSP use;
- any stutter, underrun, or instability is a hard failure until explained.

When two candidates are sonically equivalent, choose the one with fewer states, transcendental operations, branches, buffer accesses, and per-sample arithmetic.

## UI policy

The target production UI remains eight controls:

1. Record Drive
2. Tape Bias
3. Tape Compression
4. Wow & Flutter Depth
5. Body
6. HF Rolloff
7. Tape Hiss
8. Output Trim

`Body` is a proposed replacement semantic for `LF Contour`, not an approved production rename yet.

Hidden internal controls are preferred for:

- LF detector crossover;
- LF attack/release;
- LF maximum guard action;
- HF detector spacing/crossover;
- HF threshold/softening mapping;
- Pear band relationships.

A parameter becomes user-facing only if fixed calibration cannot serve materially different playback contexts without unacceptable compromise.

## Production promotion policy

Production work begins only after a written experiment report identifies the winners and the user explicitly approves promotion.

A production release must then receive its own implementation/release plan and version decision. It must not overwrite the archived v1.0.0 file.

Possible production outcomes include:

- HF redesign only;
- Body redesign only;
- HF + Body;
- LF + HF;
- LF + Body;
- LF + HF + Body;
- no production change.

## Explicitly out of scope

- true Dolby C compander implementation;
- NAAC azimuth servo modeling;
- oversampling redesign;
- replacing the existing saturation model;
- changing wow/flutter calibration;
- changing hiss topology;
- changing crosstalk calibration;
- tape type/profile systems;
- age/wear controls;
- adding a Mix control;
- adding multiband-compressor UI;
- direct full-plugin ports of StoneFireComp, Air4, Acceleration2, ToTape9, or GuitarConditioner;
- SubTight unless the first LF matrix demonstrates a remaining deep-sub-specific problem;
- production metadata/version changes before candidate promotion.

## Source attribution and licensing

Airwindows source is MIT-licensed. Any production code that materially ports or derives from an Airwindows implementation must retain appropriate attribution in repository documentation/source comments consistent with the MIT license and EELVault licensing practice.

Research source paths include:

- `airwindows/airwindows/plugins/LinuxVST/src/Highpass/HighpassProc.cpp`
- `airwindows/airwindows/plugins/LinuxVST/src/StoneFireComp/StoneFireCompProc.cpp`
- `airwindows/airwindows/plugins/LinuxVST/src/Sinew/SinewProc.cpp`
- `airwindows/airwindows/plugins/LinuxVST/src/Air4/Air4Proc.cpp`
- `airwindows/airwindows/plugins/LinuxVST/src/Acceleration2/Acceleration2Proc.cpp`
- `airwindows/airwindows/plugins/LinuxVST/src/ToTape9/ToTape9Proc.cpp`
- `airwindows/airwindows/plugins/LinuxVST/src/PearLiteEQ/PearLiteEQProc.cpp`
- `airwindows/airwindows/plugins/LinuxVST/src/GuitarConditioner/GuitarConditionerProc.cpp`

## Design acceptance criteria

This experiment phase is complete when:

1. current DRAGON v1.0.0 baseline behavior is locked numerically;
2. LF-B/LF-C/LF-D have comparable reports or the matrix is stopped early by a clearly documented failure;
3. HF-B/HF-C/HF-D have comparable reports against current S6;
4. Pear Body is measured against current LF Contour if it reaches its scheduled gate;
5. every category records a winner or `NONE`;
6. combined candidates are tested from smallest to largest topology;
7. numerical finalists are tested on-device;
8. CPU/stability and listening results are documented;
9. a final recommendation states exactly which mechanisms, if any, should enter a production DRAGON release;
10. `dsp/dragon/dragon.eel` and the archived v1.0.0 file remain unchanged throughout the experiment phase.
