# On-Device Verification Checklist

The numeric audits (`tools/audit_*.py`) prove that each DSP is stable, bounded,
latency-correct, and structurally sound. They **cannot** prove it sounds good.
That gate requires the real EEL2 VM on a device. This document is the standard
protocol for closing the "Release Readiness" items on hardware.

## Device reference (as verified 2026-08-18)

- **Device:** OnePlus N200 (DE2117), Android 16, Magisk root.
- **Audio engine:** spawned as a child process named `<package>.rjdsp.debug`
  **only while audio is playing**; it reads the liveprog file when it spawns.

### Three app variants (each has its own Liveprog dir and config)

| Variant | Package | Liveprog slots | Liveprog dir (under `/storage/emulated/0/Android/data/`) |
|---------|---------|----------------|---------------------------------------------------------|
| Normal | `me.timschneeberger.rootlessjamesdsp` | 1 | `me.timschneeberger.rootlessjamesdsp/files/Liveprog/` |
| Debug | `me.timschneeberger.rootlessjamesdsp.debug` | 4 | `me.timschneeberger.rootlessjamesdsp.debug/files/Liveprog/` |
| ViPER4Android | `me.timschneeberger.rootlessjamesdsp.v4a` | 4 | `me.timschneeberger.rootlessjamesdsp.v4a/files/Liveprog/` |

- **Liveprog config** (per variant, under `/data/data/<package>/shared_prefs/`):
  `dsp_liveprog.xml` holds `liveprog_file` (path relative to the app files
  dir, e.g. `Liveprog/vault-anima.eel`) and `liveprog_enable`. The V4A and
  Debug variants add `dsp_liveprog2/3/4.xml` for their extra slots.
- **Current on-device state:** the Normal app has `Dragon Cassette Emulator -
  RJDSP.eel` enabled; the V4A app has `soloconsole.eel` enabled in slot 1.
- **Four-slot chaining:** the V4A and Debug variants can run up to four
  liveprog scripts in series. Chain with care: ANIMA and DRAGON add an
  all-wet modulated delay (Haas-zone) and are meant for serial insertion, so
  stacking multiple delay-bearing effects compounds latency.

## Deploying a script

Pick the target variant's package first (Normal, Debug, or V4A), then:

```bash
adb push dsp/anima/anima.eel \
  /storage/emulated/0/Android/data/<package>/files/Liveprog/vault-anima.eel
```

Then either select the script in the RJDSP UI, or set it directly (root):

```bash
adb shell su -c 'sed -i "s|<string name=\"liveprog_file\">.*</string>|<string name=\"liveprog_file\">Liveprog/vault-anima.eel</string>|" \
  /data/data/me.timschneeberger.rootlessjamesdsp/shared_prefs/dsp_liveprog.xml'
```

**The engine reads the file when it spawns.** To force a reload: pause/resume
playback, or toggle the liveprog effect in the UI, so the processor restarts.
If the script fails to compile, RJDSP falls back to passthrough and shows an
error — that is the failure signal; silence in logcat while audio flows is the
success signal.

## Per-package checks

### 1. Load test (all packages)

- [ ] Script appears in the RJDSP liveprog dropdown.
- [ ] Selecting it does not error or fall back to passthrough.
- [ ] Audio keeps flowing (no silence, no crash).

### 2. Ear test (all packages)

| Package | What to listen for |
|---------|--------------------|
| **ANIMA** | Warmth/body without harshness; sustained notes "breathe" (program-dependent release); stereo width lifts but a centered vocal stays centered (mono-safe). |
| **DRAGON** | Cassette character: soft highs, gentle compression, faint slow wow/flutter on sustained tones, low hiss floor. No self-oscillation at high Drive. |
| **Material Memory** | A struck/transient source should ring like a material, not six separate filter pings. No runaway coupling. |
| **SoloConsole** | Console glue: quiet passages densify, loud passages ease back. Drive adds body, not harsh aliasing (2x oversampling on). |
| **STILLROOM** | A real room impression, not short discrete echoes. Verify the sliders now do something when moved (fixed 2026-08-17). |

### 3. SoloConsole — 1x vs 2x oversampling A/B

- [ ] Toggle Oversampling between 1x and 2x on a bright, transient-heavy source.
- [ ] At 2x, high-frequency drive should be cleaner (less "sparkly" aliasing).
- [ ] Note the 2x path latency (~0.34 ms) — should be inaudible on its own.

### 4. CPU budget (all packages)

With music playing and the effect active, from the host:

```bash
adb shell 'top -b -n 1 -p $(pidof me.timschneeberger.rootlessjamesdsp.rjdsp.debug)'
```

or read the engine's CPU time via `/proc/<pid>/stat` (fields `utime`/`stime`).
Record per-package CPU% — target is a few percent of one core at 48 kHz.

## Results log

Record each run below so the vault stays honest about what was ear-verified.

| Date | Package | Load OK | Ear verdict | CPU% | Notes |
|------|---------|---------|-------------|------|-------|
|      |         |         |             |      |       |
