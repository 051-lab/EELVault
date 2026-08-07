# SoloConsole v0.2.2 Validation & Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship SoloConsole v0.2.2 as a validation-and-hardening release that preserves the v0.2.1 sonic topology while making its core DSP invariants reproducible and correcting the known DC-block, initial-OS-state, and decimator-allocation inaccuracies.

**Architecture:** Keep `dsp/soloconsole/soloconsole.eel` structurally identical to v0.2.1 except for three production hardening edits: sample-rate-derived 5 Hz DC-block coefficients, `prev_os` initialized to the actual initial oversampling state, and a 32-slot decimator history allocation. Add a dependency-free Python audit harness that parses the EEL source and numerically reconstructs the halfband/polyphase/decimation path so correctness can be checked from a clean checkout.

**Tech Stack:** EEL2/JSFX for RootlessJamesDSP/JDSP4Linux; Python 3 standard library only for validation; Git/GitHub for release/version tracking.

## Global Constraints

- Preserve native `slider1` through `slider8` declarations and `@init`, `@slider`, `@block`, `@sample` sections.
- Preserve the v0.2.1 saturation curve, tone-filter topology, transformer rolloff, 2x fused-polyphase interpolation, causal odd-phase decimation, 15-sample latency, output gain, and pre-drive blend routing.
- No NumPy or third-party dependency in validation tooling.
- No 4x oversampling, final safety limiter redesign, Mix-routing redesign, tone-smoothing redesign, auto makeup gain, or console-glue dynamics.
- Current and archived v0.2.2 `.eel` files must be byte-identical.
- The audit command is `python tools/audit_soloconsole.py` and must exit non-zero on any failed invariant.

---

### Task 1: Add the reproducible SoloConsole audit harness

**Files:**
- Create: `tools/audit_soloconsole.py`
- Test target: `dsp/soloconsole/soloconsole.eel`
- Test target: `dsp/soloconsole/metadata.json`

**Interfaces:**
- Consumes: repository-relative paths resolved from `Path(__file__).resolve().parents[1]`.
- Produces: `main() -> int`, printing one `[PASS]`/`[FAIL]` line per invariant and returning `0` only when every check passes.

- [ ] **Step 1: Write the audit harness before production changes**

Implement these concrete helpers using only the standard library:

```python
def load_text(path: Path) -> str: ...
def require(name: str, condition: bool, detail: str = "") -> bool: ...
def design_halfband(taps: int = 32, fc: float = 0.25) -> list[float]: ...
def polyphase_interpolate(samples: list[float], h: list[float]) -> list[float]: ...
def explicit_zero_stuff_interpolate(samples: list[float], h: list[float]) -> list[float]: ...
def causal_decimate(samples_2x: list[float], h: list[float]) -> list[float]: ...
def explicit_decimate(samples_2x: list[float], h: list[float]) -> list[float]: ...
def max_abs_diff(a: list[float], b: list[float]) -> float: ...
def dc_cutoff_hz(r: float, fs: float) -> float: ...
```

`main()` must check:

```python
checks = [
    native_sections_and_sliders,
    no_legacy_slider_names,
    version_is_0_2_2,
    archive_exists_and_matches_current,
    interpolation_reference_error_below_1e_12,
    decimation_reference_error_below_1e_12,
    impulse_peak_is_sample_15,
    dc_block_is_5_hz_at_44100_48000_96000,
    six_treble_to_transformer_handoffs_present,
    complete_os_switch_state_clear_present,
    decimator_allocation_matches_32_slot_mask,
    metadata_version_and_latency_match,
]
```

The DC-block check must parse coefficients expressed as:

```eel
dcbR = exp(-2 * $pi * 5 / srate);
dcbR2 = exp(-2 * $pi * 5 / (srate * 2));
```

and numerically verify the corresponding pole cutoff is within `0.02 Hz` of 5 Hz at each requested sample rate.

- [ ] **Step 2: Run the audit against the untouched v0.2.1 production file and verify RED**

Run:

```bash
python tools/audit_soloconsole.py
```

Expected result: non-zero exit. At minimum the audit must report failures for version/archive v0.2.2, fixed-vs-derived DC blocker, `prev_os` initialization, and 64-slot decimator allocation. Existing v0.2.1 invariants such as native sliders, causal decimation, treble handoffs, and 15-sample latency should pass.

- [ ] **Step 3: Commit the red audit harness**

```bash
git add tools/audit_soloconsole.py
git commit -m "test: add SoloConsole validation harness"
```

---

### Task 2: Apply the minimal v0.2.2 production hardening changes

**Files:**
- Modify: `dsp/soloconsole/soloconsole.eel`

**Interfaces:**
- Consumes: v0.2.1 topology and audit expectations from Task 1.
- Produces: SoloConsole v0.2.2 with no intentional sonic-topology change other than the DC-block pole being exactly sample-rate-derived at 5 Hz.

- [ ] **Step 1: Change only the version, decimator allocation, OS initialization, and DC coefficients**

Apply these exact semantic edits:

```eel
desc: SoloConsole Drive v0.2.2
```

```eel
OS_BUF = 32;
```

Replace:

```eel
prev_os = -1;
os_active = 1;

p_sm = 1 - exp(-1 / (srate * 0.01));
dcbR = 0.9995;
dcbR2 = 1 - (1 - dcbR) * 0.5;
```

with:

```eel
os_active = 1;
prev_os = os_active;

p_sm = 1 - exp(-1 / (srate * 0.01));
dcbR = exp(-2 * $pi * 5 / srate);
dcbR2 = exp(-2 * $pi * 5 / (srate * 2));
```

Do not alter any saturation, shelf, transformer, limiter, interpolation, decimation, dry-delay, output-gain, or Mix equations.

- [ ] **Step 2: Run the audit and verify the production hardening checks move GREEN while release/archive checks remain RED**

Run:

```bash
python tools/audit_soloconsole.py
```

Expected: DC-block accuracy, OS initialization, and allocation checks pass. Version may pass if the source version is already changed, but archive/metadata release checks must still fail until Task 3.

- [ ] **Step 3: Commit the production hardening change**

```bash
git add dsp/soloconsole/soloconsole.eel
git commit -m "fix: harden SoloConsole rate and state handling"
```

---

### Task 3: Package v0.2.2 and align metadata/docs with actual behavior

**Files:**
- Create: `dsp/soloconsole/versions/v0.2.2-validation-hardening.eel`
- Modify: `dsp/soloconsole/metadata.json`
- Modify: `dsp/soloconsole/README.md`
- Modify: `dsp/soloconsole/CHANGELOG.md`

**Interfaces:**
- Consumes: final `soloconsole.eel` from Task 2.
- Produces: exact archived copy, metadata version `0.2.2`, and documentation matching the implemented DSP.

- [ ] **Step 1: Archive the current EEL file byte-for-byte**

Create `dsp/soloconsole/versions/v0.2.2-validation-hardening.eel` with content exactly equal to `dsp/soloconsole/soloconsole.eel`.

- [ ] **Step 2: Update metadata**

Set:

```json
"version": "0.2.2"
```

add:

```json
"v0.2.2": "versions/v0.2.2-validation-hardening.eel"
```

preserve:

```json
"dcBlockHz": 5.0,
"latencySamples2x": 15
```

and replace the fixed approximate `latencyMs` field with sample-rate-neutral metadata:

```json
"latencySamples2x": 15
```

only; do not retain a single fixed `latencyMs` value.

- [ ] **Step 3: Correct README terminology and semantics**

Make these exact conceptual corrections:

- Version becomes `0.2.2`.
- Bass and Treble are described as **RBJ biquad shelves**, not one-pole shelves.
- DC blocker is described as a **sample-rate-derived 5 Hz pole at both 1x and 2x**.
- Mix is described as a **pre-drive blend**: the blend's dry side includes Input gain + Bass shelf rather than raw input.
- 2x latency is documented as **15 samples**; optionally show 0.340 ms at 44.1 kHz and 0.3125 ms at 48 kHz as examples, clearly sample-rate-dependent.
- `tools/audit_soloconsole.py` replaces historical references to unavailable validation scripts for current verification.
- Keep final limiter and 4x oversampling as future design topics, not v0.2.2 features.

- [ ] **Step 4: Add the v0.2.2 changelog entry and correct misleading historical wording**

Add a top entry summarizing:

```text
[0.2.2] — Validation & Hardening
- Added dependency-free repository audit harness.
- Made the DC-block pole sample-rate-derived at 5 Hz at 1x/2x.
- Prevented the first unrelated slider change from forcing an OS-state flush.
- Reduced decimator history allocation from 64 to 32 addressed positions per channel.
- Corrected README/metadata terminology and latency semantics.
```

For v0.2.0 historical text, remove any claim that the complete end-to-end v0.2.0 output was proven bit-identical if that claim conflicts with the later v0.2.1 corrective release. Narrow the claim to fused **interpolator** parity only.

- [ ] **Step 5: Run the full audit and verify GREEN**

Run:

```bash
python tools/audit_soloconsole.py
```

Expected: exit code `0`, all checks `[PASS]`.

- [ ] **Step 6: Commit release packaging/docs**

```bash
git add dsp/soloconsole/versions/v0.2.2-validation-hardening.eel dsp/soloconsole/metadata.json dsp/soloconsole/README.md dsp/soloconsole/CHANGELOG.md
git commit -m "docs: package SoloConsole v0.2.2 hardening release"
```

---

### Task 4: Final regression and branch verification

**Files:**
- Verify: all files changed on `hardening/soloconsole-v0.2.2`

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: merge-ready branch with reproducible evidence.

- [ ] **Step 1: Run the clean-checkout audit**

From the repository root on the branch:

```bash
python tools/audit_soloconsole.py
```

Expected: exit `0`, every invariant `[PASS]`.

- [ ] **Step 2: Verify current/archive identity**

Run:

```bash
python -c "from pathlib import Path; a=Path('dsp/soloconsole/soloconsole.eel').read_bytes(); b=Path('dsp/soloconsole/versions/v0.2.2-validation-hardening.eel').read_bytes(); assert a == b; print('v0.2.2 archive identity: PASS')"
```

Expected: `v0.2.2 archive identity: PASS`.

- [ ] **Step 3: Verify branch scope**

Run:

```bash
git diff --stat main...HEAD
git diff --name-status main...HEAD
```

Expected changed paths only:

```text
docs/superpowers/specs/2026-08-07-soloconsole-v0.2.2-hardening-design.md
docs/superpowers/plans/2026-08-07-soloconsole-v0.2.2-hardening.md
tools/audit_soloconsole.py
dsp/soloconsole/soloconsole.eel
dsp/soloconsole/versions/v0.2.2-validation-hardening.eel
dsp/soloconsole/metadata.json
dsp/soloconsole/README.md
dsp/soloconsole/CHANGELOG.md
```

No ANIMA or unrelated repository files may change.

- [ ] **Step 4: Review the production diff for topology drift**

Confirm that relative to v0.2.1 the only DSP-source semantic changes are:

```text
version 0.2.1 -> 0.2.2
OS_BUF 64 -> 32
prev_os -1 -> initialized os_active
fixed dcbR/dcbR2 -> sample-rate-derived 5 Hz coefficients
```

If any saturation, tone, transformer, limiter, interpolation, decimation, latency, output, or Mix equation differs, fail the release review.

- [ ] **Step 5: Open a pull request only after all verification is green**

Use title:

```text
Harden SoloConsole v0.2.2 validation and rate handling
```

The PR body must include the audit results, numerical parity tolerance, exact 15-sample latency, DC-block verification at 44.1/48/96 kHz, current/archive identity, and branch-scope verification.
