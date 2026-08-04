# Signal Flow Conventions

All DSP scripts in EELVault document their signal flow using the following notation.

## Format

```text
Input stereo
-> [Stage Name]
-> [Stage Name]
-> Output stereo
```

## Example

```text
Input stereo
-> 30 Hz high-pass
-> 120 Hz transformer shelf
-> Even-harmonic saturation
-> 14 kHz tape damping
-> Program-dependent tape compression
-> Auto makeup gain
-> Dynamic tilt EQ
-> DC removal
-> Micro-flutter delay
-> Mid/Side width lift
-> Output trim
-> Safety limiter
-> Output stereo
```

## Stage Documentation

Each stage in the signal flow should document:

1. **What it does** — the processing operation
2. **Why it exists** — the psychoacoustic or engineering justification
3. **Key parameters** — the definitive values used
4. **Risks** — clipping, phase, aliasing, or artifact risks

## Parameter Documentation

All parameters are documented as definitive values, not ranges.

```text
Parameter name: value unit
```

Example:

```text
High-pass frequency: 30 Hz
Transformer shelf frequency: 120 Hz
Transformer shelf gain: +1.5 dB
Drive input gain: +4.0 dB
Even-harmonic warmth mix: 0.12
Tape damping low-pass: 14000 Hz
```