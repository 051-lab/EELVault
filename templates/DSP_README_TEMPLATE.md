# [DSP_NAME] — [Subtitle]

**Version:** [X.Y.Z]
**Status:** [Stable / Beta / Experimental]
**Type:** [Description of DSP type]
**Target:** RootlessJamesDSP / JDSP4Linux
**File:** `[filename].eel`

## Description

[Describe what this DSP does, its sonic character, and its intended use case.]

## Signal Flow

```text
Input stereo
-> [Stage 1]
-> [Stage 2]
-> ...
-> Output stereo
```

## Key Parameters

| Parameter | Value |
|-----------|-------|
| [Parameter 1] | [Value] |
| [Parameter 2] | [Value] |

## Installation

### RootlessJamesDSP (Android)

1. Copy `[filename].eel` to your RootlessJamesDSP Liveprog scripts directory.
2. Enable the Liveprog effect.
3. Select `[filename].eel` from the script dropdown.

### JDSP4Linux (Linux Desktop)

```bash
jamesdsp --set liveprog_enable=true
jamesdsp --set 'liveprog_file=/path/to/[filename].eel'
```

## Psychoacoustic Design Principles

[Describe the psychoacoustic principles used in this DSP.]

## Known Limitations

[List any known limitations or tradeoffs.]

## References

[List reference books, papers, or documentation used in the design.]