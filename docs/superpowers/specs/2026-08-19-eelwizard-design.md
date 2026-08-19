# EELWizard — Audio-DSP Research Engineer Agent Design

**Status:** Design specification for review  
**Date:** 2026-08-19  
**Working repository name:** `051-lab/EELWizard`  
**Integration repository:** `051-lab/EELVault`

## 1. Mission

EELWizard is a specialized AI audio-DSP research engineer focused on designing, implementing, validating, and documenting high-quality EEL2 LiveProg processors for RootlessJamesDSP, with secondary compatibility goals for the closely related JamesDSP/JDSP4Linux EEL environment where practical.

EELWizard is not primarily a code generator. Its core product is a verified DSP implementation backed by explicit engineering reasoning, source-aware research, deterministic checks, numerical/audio measurements, and a release package suitable for EELVault.

The preferred workflow is:

```text
idea / problem statement
        ↓
requirements and constraints
        ↓
research when useful
        ↓
DSP hypothesis and signal-flow design
        ↓
reference behavior / testable claims
        ↓
EEL2 implementation
        ↓
static + VM + numerical validation
        ↓
performance and robustness review
        ↓
RootlessJamesDSP device test
        ↓
human listening evaluation
        ↓
EELVault candidate
```

The design deliberately places code generation in the middle of the process rather than at the beginning.

---

## 2. Source Basis

This design is grounded in the following supplied and inspected sources:

1. The factory RootlessJamesDSP LiveProg script corpus supplied as `live-prog-scripts.zip`.
   - 41 `.eel` scripts were verified in the archive.
   - All 41 contain `@init` and `@sample` sections.
   - One contains `@slider` and one contains `@block`.
   - The corpus contains examples of IIR band splitting, FFT/STFT processing, FIR filtering, FFT convolution, fractional delay, polyphase filterbanks, reverb, stereo processing, companding, distortion, and utility processing.
2. RootlessJamesDSP source/reference material, including its LiveProg assets, parser/property classes, editor/parameter UI, engine integration, and EEL VM wrapper.
3. The JamesDSP `eel_vm` source/reference material, including EEL2 language rules and DSP primitives such as FFT, STFT, FIR, convolution, fractional delay, IIR band splitting, and polyphase filterbank operations.
4. `051-lab/EELVault`, including its finished DSP layout, metadata/readme templates, and existing per-processor Python audit tools.
5. Ai2 `agent-baselines`, especially the Asta-v0 pattern of routing tasks to specialized solvers and the benchmark-oriented development philosophy.
6. Ai2 `asta-plugins`, which exposes literature review, local paper-library management, data analysis, hypothesis generation, multi-step workflows, and an Asta CLI usable by local coding agents.
7. Airwindows/Airwindopedia material as an algorithmic inspiration library, not as a RootlessJamesDSP language or host specification.

Primary external references:

- https://github.com/allenai/agent-baselines
- https://github.com/allenai/asta-plugins
- https://allenai.org/asta/agents
- https://github.com/051-lab/EELVault

---

## 3. Core Design Principles

### 3.1 Host truth beats model memory

When EELWizard must decide what RootlessJamesDSP accepts, the RootlessJamesDSP host implementation and the verified factory LiveProg corpus outrank generic memories about REAPER JSFX, EEL2 variants, C, C++, or JavaScript.

### 3.2 VM truth beats guessed syntax

EEL_VM documentation/source is authoritative for core EEL2 language behavior and exposed VM functions unless the RootlessJamesDSP host demonstrably constrains or overrides that behavior.

### 3.3 Generated code is untrusted until tested

No `.eel` file is considered complete merely because an LLM produced it or because it looks syntactically plausible.

### 3.4 Measurements beat adjectives

Claims such as “transparent,” “sample-rate independent,” “mono compatible,” “alias resistant,” “zero latency,” or “DC safe” must map to explicit tests wherever objectively testable.

### 3.5 Research claims retain provenance

Measured hardware values, paper-derived constants, standard values, engineering estimates, and perceptual tuning choices must not be silently mixed together.

### 3.6 Local-first and provider-agnostic

The core system should run locally and must not depend on one model provider. Provider adapters may use OpenAI, Anthropic, Google, local/OpenAI-compatible endpoints, or other models without changing the DSP toolchain.

### 3.7 Start as one orchestrator with specialist modes

Version 0 uses one main reasoning agent with explicit specialist modes and deterministic tools. Separate sub-agents are introduced only when EELBench demonstrates a measurable quality, reliability, or cost advantage.

---

## 4. Source Authority Hierarchy

EELWizard assigns every retrieved artifact an authority class.

| Rank | Class | Examples | Authority |
|---|---|---|---|
| 1 | `HOST` | RootlessJamesDSP LiveProg/parser/engine source | Final authority for RootlessJamesDSP host behavior |
| 2 | `VM` | JamesDSP EEL_VM source/docs | Final authority for core EEL2/VM behavior when not overridden by host |
| 3 | `SHIPPED` | Factory RootlessJamesDSP `.eel` scripts | Canonical known-good idioms and compatibility examples |
| 4 | `VAULT` | Verified EELVault processors/audits | Proven project-local engineering patterns |
| 5 | `SPEC` | Standards, manufacturer/service data, formal technical docs | Authoritative for the specific external fact claimed |
| 6 | `RESEARCH` | Peer-reviewed papers, high-quality measurements | Evidence for DSP theory, models, and parameter choices |
| 7 | `REFERENCE` | Textbooks, respected technical articles | General DSP guidance |
| 8 | `INSPIRATION` | Airwindows, experimental/open-source processors | Algorithmic inspiration; never host/language authority |
| 9 | `ESTIMATE` | Derived or perceptually tuned values | Allowed only when labeled and justified |

Conflict resolution follows the table from highest applicable authority to lowest.

The agent must explicitly surface unresolved conflicts rather than merging incompatible claims.

---

## 5. Supported Task Classes

EELWizard v1 is designed to support these task classes:

### 5.1 Build
- Design a new LiveProg DSP from a functional or sonic brief.
- Port an algorithm into RootlessJamesDSP-compatible EEL2.
- Create an EELVault-ready processor package.

### 5.2 Repair
- Diagnose and fix EEL2 syntax errors.
- Correct RootlessJamesDSP host incompatibilities.
- Repair numerical instability, NaN/Inf behavior, DC buildup, stereo defects, bad state initialization, parameter discontinuities, or sample-rate dependencies.

### 5.3 Review
- Conduct code audits.
- Compare two revisions.
- Detect behavioral regressions.
- Identify CPU/mobile hot paths.

### 5.4 Optimize
- Reduce per-sample expensive math.
- Move invariant work to initialization/control-rate paths.
- Reduce memory traffic.
- Replace avoidable transcendental operations with stable recurrences/approximations where justified.
- Preserve measured behavior during optimization.

### 5.5 Research
- Find literature relevant to a DSP problem.
- Extract models, measurements, or psychoacoustic findings.
- Generate testable DSP hypotheses from evidence.
- Maintain a provenance ledger for research-derived implementation choices.

### 5.6 Explain
- Explain a processor's signal flow and controls.
- Produce technical and plain-language documentation.
- Explain why a design was chosen and how it was validated.

---

## 6. Non-Goals for v1

EELWizard v1 does not attempt to:

- train or fine-tune a foundation model;
- autonomously publish releases without human approval;
- replace physical-device listening tests with synthetic metrics;
- guarantee bit-identical behavior between all EEL2 hosts;
- emulate proprietary hardware from invented or unsourced values;
- run an expensive multi-agent swarm for every task;
- create a graphical plugin framework;
- become a generic DAW coding assistant.

These exclusions keep the first system centered on verified RootlessJamesDSP LiveProg engineering.

---

## 7. System Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│                         EELWizard                            │
│                                                              │
│  ┌───────────────────────┐                                   │
│  │ Task Orchestrator     │                                   │
│  └───────────┬───────────┘                                   │
│              │                                               │
│   ┌──────────┼───────────┬──────────────┐                    │
│   ▼          ▼           ▼              ▼                    │
│ Research   Architect   EEL Engineer   Reviewer               │
│   │          │           │              │                    │
│   └──────────┴───────────┴──────────────┘                    │
│              │                                               │
│              ▼                                               │
│      Deterministic Tool Layer                                │
│              │                                               │
│  ┌───────────┼──────────┬───────────┬────────────┐           │
│  ▼           ▼          ▼           ▼            ▼           │
│ Retrieval  EEL Lint   EEL_VM     DSP Lab      EELBench       │
│                         Runner                                │
└──────────────┬───────────────────────────────────────────────┘
               │
       ┌───────┴─────────┐
       ▼                 ▼
 RootlessJamesDSP      EELVault
 device validation    candidate/release
```

The specialist labels are roles/modes in v0, not necessarily separate model processes.

---

## 8. Specialist Modes

### 8.1 Orchestrator

Responsibilities:
- classify the task;
- establish constraints and required evidence;
- choose specialist mode(s);
- sequence tool calls;
- maintain the engineering state/claim ledger;
- enforce release gates;
- prevent “code first” behavior when research/design is required.

### 8.2 DSP Researcher

Responsibilities:
- decide whether outside research is useful;
- formulate paper-search questions;
- invoke Asta tools/CLI when available;
- summarize relevant evidence without silently upgrading weak evidence to fact;
- extract numeric values with provenance;
- generate hypotheses that can be tested by the DSP lab.

### 8.3 DSP Architect

Responsibilities:
- translate the sonic/functional brief into a signal-flow design;
- define state, controls, latency, sample-rate behavior, channel topology, and expected transfer behavior;
- choose algorithms appropriate to mobile real-time execution;
- identify likely failure modes before implementation;
- define acceptance tests before code generation.

### 8.4 EEL Engineer

Responsibilities:
- retrieve known-good language/host idioms;
- implement valid EEL2 using RootlessJamesDSP conventions;
- preserve stereo/state correctness;
- avoid importing unsupported JSFX syntax or host assumptions;
- keep real-time work bounded and mobile-aware;
- annotate non-obvious implementation choices.

### 8.5 DSP Reviewer

Responsibilities:
- challenge the implementation independently from the authoring pass;
- inspect numerical stability, state initialization, sample-rate scaling, parameter smoothing, channel symmetry, memory indexing, latency, and CPU hazards;
- compare implementation against design claims and measurement results;
- reject unsupported release claims.

---

## 9. Knowledge Engine

### 9.1 Corpus layout

The agent repository stores normalized source material under `corpus/`.

```text
corpus/
├── rootless/
│   ├── host/
│   └── manifests/
├── eel_vm/
│   ├── language/
│   ├── dsp_primitives/
│   └── manifests/
├── shipped_liveprog/
│   ├── raw/
│   ├── normalized/
│   └── manifest.jsonl
├── eelvault/
│   ├── normalized/
│   └── manifest.jsonl
└── references/
    └── manifests/
```

### 9.2 Normalized LiveProg records

Each factory or EELVault script is parsed into a record containing at least:

```yaml
name: delayChorus
source_class: SHIPPED
sections:
  - init
  - sample
host_variables:
  - spl0
  - spl1
  - srate
techniques:
  - delay-line
  - modulation
  - feedback
  - wet-dry
vm_primitives: []
state_variables: []
memory_regions: []
controls: []
notes: []
source_path: corpus/shipped_liveprog/raw/delayChorus.eel
content_hash: ...
```

The schema is extensible, but the initial index must prioritize high-confidence facts that can be extracted deterministically.

### 9.3 Retrieval

Retrieval is hybrid:

1. exact/token search for language primitives, host variables, and known API names;
2. structured filtering by source authority, task type, technique, section, and primitive;
3. semantic retrieval for conceptually similar processors;
4. reranking that favors higher-authority and known-good examples.

The agent should normally retrieve:
- one or more host/VM rules relevant to the task;
- the closest factory example(s);
- relevant verified EELVault pattern(s), when available;
- research/inspiration only after compatibility truth is established.

---

## 10. Asta Integration

Asta is a research subsystem, not the central reasoning engine.

### 10.1 Preferred integration

The preferred local integration is `asta-plugins` / the `asta` CLI because it is designed for local coding agents and exposes literature review and related research skills.

### 10.2 Research trigger

The orchestrator invokes research when at least one of these is true:
- the effect models a real physical device or process;
- a design choice depends on psychoacoustics or perception;
- the user requests evidence/research;
- competing algorithms need evidence-based selection;
- measured constants or standards matter;
- novelty would benefit from adjacent scientific methods.

Research is not mandatory for trivial syntax repair or obvious host-language questions.

### 10.3 Research output contract

Research must return a structured evidence bundle:

```yaml
question: ...
claims:
  - claim: ...
    source_type: paper | standard | manufacturer | measurement | estimate
    source: ...
    confidence: high | medium | low
    implementation_relevance: ...
open_questions: []
testable_hypotheses: []
```

No research-derived numeric constant may enter a release implementation without source metadata or an explicit `ESTIMATE` designation.

---

## 11. Claim Ledger

Every project gets a machine-readable claim ledger.

Example:

```yaml
claims:
  - id: head_bump_frequency
    value: 64
    unit: Hz
    provenance: measurement
    source: ...
    implementation: low_frequency_resonance
    verification: measured_response_test

  - id: saturation_curve
    value: perceptual_tune_v2
    provenance: estimate
    rationale: ...
    verification: harmonic_sweep_and_listening
```

The ledger prevents model guesses, measurements, and perceptual tuning from collapsing into one undifferentiated notion of “truth.”

---

## 12. DSP Laboratory

The DSP laboratory is a Python subsystem used to create deterministic input signals and analyze outputs.

### 12.1 Signal generators

Minimum v1 set:
- impulse;
- DC;
- silence;
- sine;
- stepped sine;
- logarithmic sweep;
- white noise;
- pink noise;
- multitone;
- two-tone IMD signal;
- transient bursts;
- amplitude ramps;
- near-zero/denormal-scale values;
- overload/extreme-amplitude vectors;
- stereo correlation/anti-correlation fixtures.

### 12.2 Measurements

Minimum v1 set:
- frequency response;
- phase response when observable;
- impulse response;
- latency;
- peak and RMS level;
- crest factor;
- DC offset/drift;
- harmonic spectrum;
- THD;
- IMD proxy/tests;
- static transfer curve;
- dynamic gain curve;
- attack/release behavior;
- stereo channel mismatch;
- stereo correlation;
- mono fold-down error;
- NaN/Inf detection;
- runaway-state detection.

### 12.3 Reference comparison

Where a Python/reference model exists, the lab compares the EEL output to the reference using task-appropriate tolerances rather than requiring universal sample-identical behavior.

---

## 13. EEL Validation Pipeline

Validation is staged.

### Gate 1 — Structural/static validation

Checks include:
- required sections;
- balanced delimiters;
- unsupported syntax patterns known to come from C/JSFX hallucination;
- suspicious assignments/conditionals;
- memory-range declarations/indexing where inferable;
- duplicate or conflicting controls;
- undefined required host assumptions;
- forbidden placeholders/TODO implementation fragments.

### Gate 2 — EEL_VM compile/execution

The candidate is compiled/executed in the closest available EEL_VM harness.

Failures are returned as structured diagnostics and routed back to the EEL Engineer.

### Gate 3 — Deterministic test vectors

The compiled processor is exercised with DSP-lab fixtures.

### Gate 4 — Numerical/audio measurements

Results are checked against the design acceptance criteria and claim ledger.

### Gate 5 — Performance review

The reviewer checks:
- per-sample expensive functions;
- avoidable recalculation;
- unbounded loops;
- oversized memory use;
- unnecessary FFT/STFT size or overlap;
- state duplication;
- mobile-real-time risk.

### Gate 6 — RootlessJamesDSP host/device validation

The script must load and run in RootlessJamesDSP. Host validation eventually supports an ADB-assisted test path, but v1 may use a human-operated device handoff where automation is unavailable.

### Gate 7 — Listening evaluation

Human listening remains required for subjective qualities that numerical tests cannot prove.

---

## 14. RootlessJamesDSP Compatibility Policy

The default target is stereo mobile playback at 44.1 kHz and 48 kHz unless a processor explicitly declares narrower support.

Every new processor must state:
- supported sample rates;
- channel assumptions;
- expected latency;
- whether controls are smoothed;
- whether bypass/state resets are click-safe;
- expected CPU class (`light`, `moderate`, `heavy`);
- memory requirements when material;
- any dependence on host-specific VM extensions.

The agent must not assume that generic REAPER JSFX UI syntax or behavior is available simply because EEL2 is historically related.

---

## 15. EELBench

EELBench is the evaluation system for the agent itself.

The purpose is to measure whether EELWizard is improving rather than relying on subjective impressions of model intelligence.

### 15.1 Benchmark families

#### Language
- repair invalid EEL2 syntax;
- identify unsupported C/JSFX constructs;
- explain scope and control flow;
- reason about EEL memory indexing;
- use functions/local/instance semantics correctly.

#### Host
- implement valid RootlessJamesDSP sections;
- use host variables correctly;
- create valid parameter/control patterns;
- handle `srate` correctly;
- preserve `spl0`/`spl1` and stereo semantics.

#### DSP construction
- stable one-pole/biquad designs;
- compressor/envelope follower;
- fractional delay;
- M/S processing;
- saturation/waveshaping;
- FIR/FFT/STFT tasks when justified.

#### Diagnostics
- find state-initialization bugs;
- find sample-rate dependencies;
- find DC accumulation;
- find zipper noise risk;
- find stereo asymmetry;
- find NaN/Inf paths;
- find memory-boundary/indexing defects.

#### Optimization
- remove unnecessary per-sample transcendental calls;
- precompute invariants;
- reduce memory traffic;
- preserve output behavior within a specified tolerance.

#### Research-to-DSP
- formulate a research question;
- retrieve relevant evidence;
- distinguish fact from estimate;
- convert evidence into a testable DSP model;
- implement and verify it.

#### Repository engineering
- create a complete EELVault candidate;
- generate metadata/docs;
- run generic and DSP-specific audits;
- report evidence for release readiness.

### 15.2 Scoring

Each task can award points for:
- syntax/compile success;
- host compatibility;
- objective DSP behavior;
- robustness;
- source/provenance correctness;
- CPU constraints;
- documentation correctness;
- unnecessary-complexity penalties.

Critical failures such as non-loading code, NaN/Inf generation under normal fixtures, or invented source claims cause task failure regardless of prose quality.

### 15.3 Benchmark discipline

EELBench fixtures are versioned. The agent is evaluated on a stable public/development set, with a held-out set reserved for avoiding benchmark overfitting.

---

## 16. EELVault Integration

EELVault remains the curated output collection. EELWizard is developed separately.

### 16.1 Boundary

`051-lab/EELWizard` contains:
- the agent;
- corpus/indexing;
- EEL validators;
- EEL_VM runner integration;
- DSP lab;
- EELBench;
- workflow logic.

`051-lab/EELVault` contains:
- finished/candidate processors;
- processor documentation;
- metadata/changelogs;
- effect-specific tests/audits where useful;
- release history.

### 16.2 Candidate contract

A candidate produced for EELVault contains at least:

```text
dsp/<name>/
├── <name>.eel
├── README.md
├── metadata.json
├── CHANGELOG.md
├── claims.yaml
└── validation/
    └── report.json
```

The exact EELVault repository structure can preserve existing conventions; the contract represents the logical artifacts required from EELWizard.

### 16.3 Generic verifier

Existing processor-specific Python audits in EELVault are treated as valuable training/design evidence. Common checks should be extracted over time into a generic command such as:

```text
eelwizard verify path/to/effect.eel
```

DSP-specific audits remain supported for behavior that cannot be generalized.

---

## 17. CLI Surface

The initial product is CLI-first.

Proposed stable command family:

```text
eelwizard corpus build
eelwizard corpus inspect <query>
eelwizard design <brief>
eelwizard repair <file>
eelwizard review <file>
eelwizard verify <file>
eelwizard measure <file>
eelwizard benchmark
eelwizard vault package <project>
```

An interactive agent command may later provide:

```text
eelwizard agent
```

The CLI-first approach keeps the system automatable from Codex, Claude Code, OpenCode, T3 Code, shell scripts, CI, and future front ends.

---

## 18. Tool Contracts

The model should interact with deterministic capabilities through narrow typed tools rather than raw shell whenever practical.

Minimum logical tool set:

```text
search_host_docs(query)
search_vm_docs(query)
search_liveprog_examples(query, technique, primitive)
search_eelvault(query)
research_with_asta(question)

lint_eel(path_or_text)
compile_eel(path_or_text)
run_eel(test_fixture, controls)

make_test_signal(spec)
measure_response(result)
measure_harmonics(result)
measure_dynamics(result)
measure_stereo(result)
compare_reference(reference, candidate)

run_eelbench(selection)
create_vault_candidate(project)
```

Tools return structured data with diagnostics and provenance, not only prose.

---

## 19. Project State Model

Each DSP development run uses a project workspace.

```text
workspaces/<project>/
├── brief.md
├── design.yaml
├── claims.yaml
├── research/
├── reference/
├── src/
├── tests/
├── measurements/
├── reviews/
└── release/
```

The orchestrator records state transitions. A later run can resume from the workspace without reconstructing important decisions from chat history.

---

## 20. Failure Policy

EELWizard must fail closed on technical claims.

It must not label a candidate “verified,” “release ready,” or “RootlessJamesDSP compatible” when the corresponding gate was not run.

Allowed states include:

- `DESIGN_ONLY`
- `CODE_GENERATED`
- `STATIC_PASS`
- `VM_PASS`
- `MEASUREMENT_PASS`
- `DEVICE_PASS`
- `LISTENING_APPROVED`
- `EELVAULT_CANDIDATE`
- `RELEASED`

If a gate cannot be run, the status remains at the previous successfully demonstrated state and the missing gate is reported.

---

## 21. Security and Execution Boundaries

Generated EEL and downloaded research/code are treated as untrusted inputs.

- EEL_VM execution should occur in a controlled process/container when practical.
- Test execution receives time and memory limits.
- The agent does not push or release to EELVault without explicit human authorization.
- Research retrieval does not automatically execute downloaded code.
- Provider/API credentials remain environment-managed and are never written into project artifacts.

---

## 22. Technology Choices

### Core language

Python 3.11+ is the primary implementation language because it supports:
- agent orchestration;
- scientific audio analysis;
- test tooling;
- corpus processing;
- CLI development;
- easy integration with Asta tooling and model-provider SDKs.

### Recommended foundation

- `uv` for reproducible Python environments and lockfiles;
- `pydantic` for typed tool/project schemas;
- `typer` or equivalent for CLI commands;
- NumPy/SciPy for reference DSP and analysis;
- pytest for deterministic tests;
- optional provider adapters isolated behind one model interface;
- local SQLite/FTS plus lightweight vector retrieval for corpus indexing before introducing heavier infrastructure.

### Why not start with a large framework

The critical engineering value lies in the corpus, validators, runner, measurements, and evaluations. Agent frameworks should remain replaceable. The first version should not couple the project to one proprietary orchestration stack.

---

## 23. Proposed Repository Structure

```text
EELWizard/
├── README.md
├── pyproject.toml
├── uv.lock
├── src/
│   └── eelwizard/
│       ├── agent/
│       │   ├── orchestrator.py
│       │   ├── roles.py
│       │   ├── state.py
│       │   └── providers/
│       ├── corpus/
│       │   ├── ingest.py
│       │   ├── schema.py
│       │   ├── index.py
│       │   └── retrieve.py
│       ├── eel/
│       │   ├── parser.py
│       │   ├── lint.py
│       │   ├── runner.py
│       │   └── diagnostics.py
│       ├── lab/
│       │   ├── signals.py
│       │   ├── measurements.py
│       │   ├── dynamics.py
│       │   ├── harmonics.py
│       │   └── stereo.py
│       ├── research/
│       │   ├── asta.py
│       │   └── claims.py
│       ├── vault/
│       │   ├── package.py
│       │   └── report.py
│       └── cli.py
├── corpus/
│   ├── rootless/
│   ├── eel_vm/
│   ├── shipped_liveprog/
│   └── eelvault/
├── evals/
│   └── eelbench/
│       ├── tasks/
│       ├── fixtures/
│       └── scorers/
├── tests/
├── docs/
│   ├── architecture/
│   ├── host-contract/
│   └── research/
└── workspaces/
    └── .gitkeep
```

Large/generated corpus indexes and workspace outputs should be ignored or versioned selectively; canonical source manifests and benchmark fixtures remain version controlled.

---

## 24. Development Milestones

### M0 — Repository and contracts

Deliverables:
- new `051-lab/EELWizard` repository;
- Python/uv skeleton;
- architecture docs;
- typed schemas for corpus records, claims, diagnostics, and project state;
- CI baseline;
- fixture copy of a very small known-good EEL subset.

Exit criteria:
- clean install;
- CLI starts;
- tests run in CI;
- schemas round-trip deterministically.

### M1 — Knowledge engine

Deliverables:
- ingest all 41 supplied factory LiveProg scripts;
- ingest EEL_VM language/DSP reference material;
- ingest RootlessJamesDSP host reference material;
- ingest EELVault verified processors/audit metadata;
- source authority labels;
- searchable manifests;
- retrieval CLI.

Exit criteria:
- every factory script has a normalized record and content hash;
- queries for key primitives return the correct known-good examples;
- host/VM facts can be retrieved separately from inspiration/reference material.

### M2 — EEL engineer and static validator

Deliverables:
- rule-aware EEL linter;
- diagnostics schema;
- repair workflow;
- first EEL authoring agent mode;
- initial language/host EELBench tasks.

Exit criteria:
- all 41 shipped scripts pass compatibility checks or have documented parser exceptions;
- intentionally broken fixtures fail with useful diagnostics;
- the agent can repair held-out syntax defects at a defined benchmark score.

### M3 — EEL_VM runner + DSP lab

Deliverables:
- executable EEL test harness;
- signal fixtures;
- measurement modules;
- robustness stress tests;
- reference-vs-EEL comparison framework.

Exit criteria:
- known factory scripts can be executed where their host dependencies allow;
- basic filter/gain/delay processors produce expected measured behavior;
- NaN/Inf/runaway tests are automated.

### M4 — Research subsystem

Deliverables:
- Asta adapter;
- structured research evidence bundle;
- claim ledger;
- research-to-design workflow;
- provenance-aware reports.

Exit criteria:
- a research task can produce evidence with traceable source metadata;
- no unsourced numeric claim silently enters a candidate;
- research can be skipped for tasks where it adds no value.

### M5 — EELBench

Deliverables:
- benchmark families defined in this spec;
- development and held-out task sets;
- deterministic scorers where possible;
- benchmark report artifact;
- regression threshold in CI for deterministic components.

Exit criteria:
- agent changes can be compared quantitatively;
- benchmark failures identify the responsible capability class.

### M6 — EELVault candidate workflow

Deliverables:
- project workspace orchestration;
- candidate packaging;
- validation reports;
- generic audit extraction from existing EELVault audits;
- device-test handoff/report format;
- documentation generation.

Exit criteria:
- a new effect can move from brief to EELVault candidate while preserving research/design/measurement provenance;
- candidate status accurately reflects which gates were actually run.

---

## 25. First Vertical Slice

The first implementation should prove the architecture with one narrow end-to-end slice instead of immediately implementing every subsystem.

The slice is:

```text
factory corpus
   ↓
normalize/index
   ↓
retrieve known-good examples
   ↓
repair a deliberately broken simple LiveProg script
   ↓
static validation
   ↓
run a small deterministic DSP fixture
   ↓
measurement report
```

A gain/filter/delay-class processor is preferable for this slice because expected behavior is easy to measure and failures are easy to localize.

This proves the crucial loop before adding Asta research or autonomous EELVault packaging.

---

## 26. Acceptance Criteria for v1

EELWizard v1 is successful when all of the following are true:

1. The 41 supplied factory scripts are indexed as first-class known-good examples.
2. The system can distinguish RootlessJamesDSP host rules, EEL_VM rules, factory idioms, EELVault patterns, research evidence, and inspiration sources.
3. A generated script cannot become “verified” without passing the configured deterministic gates.
4. The system can compile/execute a useful subset of LiveProg scripts or isolated algorithms through an EEL_VM harness.
5. The DSP lab can objectively measure common filter, dynamics, harmonic, latency, robustness, and stereo behaviors.
6. EELBench provides repeatable scores for agent revisions.
7. Asta research can be invoked selectively and its results retain provenance.
8. A project workspace can resume without relying on chat-memory reconstruction.
9. EELVault candidates contain code, documentation, claims, and validation evidence.
10. Human approval remains required for final EELVault release/device-listening claims.

---

## 27. Decisions Intentionally Deferred Beyond v1

These are not unresolved requirements for v1; they are explicit post-v1 possibilities:

- model fine-tuning using EELBench/repair traces;
- separate persistent sub-agent processes;
- automated ADB deployment and audio capture on Android;
- real-time hardware-in-the-loop measurements;
- GUI/web front end;
- plugin formats beyond EEL2 LiveProg;
- self-directed long-horizon DSP invention campaigns;
- distributed benchmark runners.

They should be reconsidered only after the v1 benchmark and workflow provide evidence that they solve a real limitation.

---

## 28. Design Summary

EELWizard should be built as a local-first, provider-agnostic audio-DSP engineering system whose intelligence comes from the combination of:

```text
strong DSP reasoning
+ RootlessJamesDSP host truth
+ EEL_VM language truth
+ 41 known-good factory LiveProg programs
+ verified EELVault patterns
+ optional Asta scientific research
+ deterministic EEL execution
+ Python audio measurement
+ objective EELBench evaluation
+ human listening/device approval
```

The agent's defining rule is simple:

> **Never confuse plausible EEL2 with proven DSP.**

The project advances only when each layer—research, design, implementation, execution, measurement, and host validation—supports the claim being made.