# EEL2 Quick Reference for JamesDSP

This is a condensed reference for writing EEL2 scripts that run in RootlessJamesDSP and JDSP4Linux.

## Script Structure

```eel
desc: Script Name

// UI parameter declarations (optional)
varName:default<min,max,step>Label

[init](init)
// Runs once on load. Initialize all variables, coefficients, and memory here.

[sample](sample)
// Runs for every audio sample.
// spl0 = left channel input/output
// spl1 = right channel input/output

[serialize](serialize)
// Optional: persist state across sessions
```

## Critical Rules

1. The first line MUST be `desc: Script Name`.
2. UI parameter declarations go BEFORE `@init`.
3. `spl0` and `spl1` are both input AND output. Modify them in place.
4. All heavy computation (filter design, coefficient calculation, memory allocation) goes in `@init`, NOT in `@sample`.
5. Use `loop(count, ...)` for iteration. Do NOT use `while()` unless you have confirmed your VM supports it.
6. Use ternary operators for conditionals: `result = (x > 0) ? x : -x;`
7. dB to linear conversion: `gainLin = exp(dB * 0.11512925464970228);`

## Memory Allocation

EEL2 uses a flat memory array. Allocate by assigning a pointer index:

```eel
// Allocate two buffers of 4096 samples each
DELAY_SIZE = 4096;
dL = 0;
dR = DELAY_SIZE;

// Clear both buffers
i = 0;
loop(DELAY_SIZE * 2,
    dL[i] = 0;
    i += 1;
);
```

## Common Math Functions

| Function | Description |
|----------|-------------|
| `abs(x)` | Absolute value |
| `min(a, b)` | Minimum of two values |
| `max(a, b)` | Maximum of two values |
| `exp(x)` | e raised to the power x |
| `sin(x)` | Sine of x (radians) |
| `cos(x)` | Cosine of x (radians) |
| `$pi` | Pi constant (3.14159...) |
| `srate` | Current sample rate |

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Using `while()` loops | Use `loop(count, ...)` instead |
| Negative bitwise AND | Use positive offset: `(i + MASK) & MASK` instead of `(i - 1) & MASK` |
| Uninitialized delay buffers | Always zero buffers in `@init` before first use |
| Double-compression limiter | Use a single gain computer, not two cascaded gain reductions |
| Forgetting `: 0` on ternaries | Always write `condition ? true_val : false_val;` |