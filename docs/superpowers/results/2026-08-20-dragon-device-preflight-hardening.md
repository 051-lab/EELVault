# DRAGON Device Finalist Preflight Hardening

## Scope

This record covers the final static hardening pass before the two experimental DRAGON finalists are loaded in RootlessJamesDSP on Android.

Finalists:

- `dsp/dragon/experiments/dragon-acceleration-body.eel`
- `dsp/dragon/experiments/dragon-totape-body.eel`

Production `dsp/dragon/dragon.eel` remains frozen.

## Parser-conservative slider label

The first finalist drafts used:

```eel
body:0<-1,1,0.05>Body (Lean < Reference > Full)
```

A bounded search of the RootlessJamesDSP-ViPER fork did not locate enough of the slider-line parser to prove that later angle brackets are always treated as opaque display text. Because the extra angle brackets provide no DSP or UI value, both experimental finalists now use the parser-conservative form:

```eel
body:0<-1,1,0.05>Body (Lean / Reference / Full)
```

The two GitHub hardening commit diffs confirm that the only content change in each finalist is this display label (plus end-of-file newline metadata). No DSP equation, constant, state, or signal-path statement changed.

## Strengthened static preflight audit

`tools/audit_dragon_device_candidates.py` was expanded to check:

- exactly one `@init`, `@slider`, `@block`, and `@sample`, in that order;
- absence of markdown-style section markers;
- RJDSP-safe function definitions with space-separated arguments and no commas in function-definition argument lists;
- exactly eight sliders in the order `drive, bias, comp, wflutter, body, rolloff, hiss, trim`;
- the parser-conservative Body display label;
- no exposed legacy `bump:` slider;
- fixed v1.0.0 `rbj_peak(50, 0.95, 1)` reference contour;
- refined Pear profile constants;
- W&F/Pear memory separation;
- Pear placement after replay HF shelf and before hiss;
- warm Pear-state update before the exact `Body=0` output bypass;
- absence of a Foundation implementation;
- Acceleration-specific limit, curvature detector, removal of the old broadband S6 map, and non-overlapping history rings;
- ToTape-specific crossover/gain/ballistics, residual detector, independence from the linked S4 envelope, and no extra array region beyond W&F + Pear.

Two false-positive assumptions in the first hardened audit draft were corrected before use: the actual warm-state variable is `body_wet`, and the source comments explicitly mention that Foundation is *not* included, so Foundation absence is now checked using implementation-token patterns rather than the word `foundation` anywhere in the source.

## Repository-integrity evidence

A fresh `main...dragon-adaptive-control-experiments` comparison after hardening shows:

- both finalists remain new files only under `dsp/dragon/experiments/`;
- production `dsp/dragon/dragon.eel` is absent from the diff;
- the v1.0.0 archive is absent from the diff;
- `dsp/dragon/metadata.json` is absent from the diff;
- `tools/audit_dragon.py` is absent from the diff;
- `.github/workflows/audit.yml` is absent from the final diff.

The experiment-selection file also remains deliberately unpromoted:

```json
{
  "lf": {"key": "none", "params": {}},
  "hf": {"key": "current-s6", "params": {}},
  "body": {"key": "body-none", "params": {}}
}
```

## CI verification attempt

A temporary experiment-branch-only GitHub Actions trigger was added to run the production Dragon audit plus the new device-candidate preflight. No Actions/check run attached to the API/app-authored commit, so this produced **no test evidence** and must not be counted as a passing CI run.

The workflow file was immediately restored byte-for-byte to its original content. It therefore leaves no workflow diff against `main`.

## Verification boundary

The ChatGPT execution container cannot resolve GitHub over normal network access and does not contain the RootlessJamesDSP EEL host. Consequently, the strengthened repository audit could not be executed from this environment against a local checkout, and an API-authored commit did not trigger GitHub Actions.

What *is* established before device testing:

1. the previously validated Acceleration and ToTape numerical algorithms remain unchanged by this hardening pass;
2. both hardening diffs are display-only;
3. the persisted finalist headers now use conservative slider display syntax;
4. production DRAGON and safe-selection state remain untouched;
5. the static audit contract is stricter and ready to run in a real checkout.

What is **not** yet established:

- actual RootlessJamesDSP EEL parse success;
- audio output from either finalist in the host;
- Android real-time CPU/underrun behavior;
- subjective A/B result.

Those are now the authoritative remaining device gates. Do not promote or merge either finalist before they are observed on the real host.
