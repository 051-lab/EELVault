# EELWizard — Audio-DSP Research Engineer Agent Design

**Status:** Design specification for review  
**Date:** 2026-08-19  
**Working repository name:** `051-lab/EELWizard`  
**Integration repository:** `051-lab/EELVault`

## 1. Mission

EELWizard is a specialized AI audio-DSP research engineer for designing, implementing, validating, optimizing, reviewing, and documenting EEL2 LiveProg processors, with RootlessJamesDSP as the primary host family.

EELWizard is not primarily a code generator. Its product is a DSP implementation whose claims are supported by source-aware engineering decisions, deterministic validation, numerical/audio measurements, host compatibility evidence, and human listening approval where subjective judgment is required.

The intended lifecycle is:

```text
idea / problem statement
        ↓
requirements and target-host profile
        ↓
research when useful
        ↓
DSP hypothesis + signal-flow design
        ↓
reference behavior + acceptance tests
        ↓
EEL2 implementation
        ↓
static / VM / numerical validation
        ↓
performance + robustness review
        ↓
target RootlessJamesDSP device test
        ↓
human listening evaluation
        ↓
EELVault candidate
```

Code generation deliberately occurs in the middle of the workflow, not at the beginning.

---

## 2. Source Basis and Corpus Provenance

This design is grounded in the sources supplied for this project and the repositories inspected during design.

### 2.1 Supplied LiveProg ZIP

The supplied `live-prog-scripts.zip` contains **41 `.eel` files**.

Direct inspection shows:

- all 41 contain `@init` and `@sample`;
- exactly one supplied file, `soloconsole.eel`, also contains `@slider` and `@block`;
- the archive includes examples using IIR band splitting, FFT/STFT processing, FIR filtering, FFT convolution, fractional delay, polyphase filterbanks, reverb, stereo processing, companding, distortion, and utility processing.

### 2.2 Upstream factory corpus

The current upstream RootlessJamesDSP `app/src/main/assets/Liveprog/` tree and the supplied RootlessJamesDSP source digest contain **40 factory LiveProg files**. `soloconsole.eel` is not present in that upstream factory directory.

Therefore EELWizard must **not** classify all 41 supplied files as upstream factory scripts.

The ingestion policy is:

- the 40 files matching current upstream RootlessJamesDSP are classed `SHIPPED_UPSTREAM` after filename/content verification;
- `soloconsole.eel` is classed as a supplemental EELVault-lineage example, not upstream host truth;
- every future corpus import is reconciled by source path and content hash rather than trusting the folder label supplied to the agent.

This distinction is important because the supplemental SoloConsole example exercises sections that the 40 upstream factory examples do not demonstrate.

### 2.3 Other source material

The design also uses:

1. RootlessJamesDSP source/reference material, including LiveProg assets, parser/property classes, editor/parameter UI, engine integration, and EEL VM wrapper behavior.
2. JamesDSP `eel_vm` source/reference material, including EEL2 language rules and DSP primitives such as FFT, STFT, FIR, convolution, fractional delay, IIR band splitting, and polyphase filterbank operations.
3. `051-lab/EELVault`, including finished processors, metadata/readme patterns, and existing per-processor Python audit tools.
4. Ai2 `agent-baselines`, especially the Asta-v0 pattern of routing work to specialized solvers and the use of objective benchmarks.
5. Ai2 `asta-plugins`, which exposes literature review, local paper-library management, data analysis, hypothesis generation, workflows, and an Asta CLI usable by local coding agents.
6. Airwindows/Airwindopedia as algorithmic inspiration and implementation-study material, never as RootlessJamesDSP host or EEL2 language authority.

Primary external references:

- https://github.com/timschneeb/RootlessJamesDSP
- https://github.com/051-lab/RootlessJamesDSP
- https://github.com/051-lab/EELVault
- https://github.com/allenai/agent-baselines
- https://github.com/allenai/asta-plugins
- https://allenai.org/asta/agents

---

## 3. Core Design Principles

### 3.1 Target-host truth beats model memory

EELWizard must identify the target host/profile before making compatibility claims. The source code and verified behavior of that target profile outrank generic memories about REAPER JSFX, other EEL2 hosts, C, C++, or JavaScript.

### 3.2 VM truth beats guessed syntax

EEL_VM source/documentation is authoritative for core EEL2 behavior and exposed VM functions unless a selected host profile demonstrably constrains, removes, or extends that behavior.

### 3.3 Generated code is untrusted until tested

No `.eel` file is considered complete because an LLM produced it or because it looks plausible.

### 3.4 Measurements beat adjectives

Claims such as `transparent`, `sample-rate independent`, `mono compatible`, `alias resistant`, `zero latency`, or `DC safe` must map to explicit measurements or tests when they are objectively testable.

### 3.5 Research claims retain provenance

Measured hardware values, paper-derived constants, standards, engineering estimates, and perceptual tuning choices must never be silently merged into one class of “facts.”

### 3.6 Local-first and provider-agnostic

The core DSP toolchain runs locally and is not tied to one model provider. Provider adapters remain replaceable.

### 3.7 One orchestrator first

Version 0 uses one primary reasoning agent with explicit specialist modes and deterministic tools. Separate long-running sub-agents are introduced only if EELBench demonstrates a measurable reliability, quality, or cost benefit.

### 3.8 Fail closed on verification claims

If a gate was not run, the agent must say it was not run. Missing evidence can never be translated into “verified.”

---

## 4. Host Profiles

EELWizard must treat host compatibility as a profile, not as a single universal EEL2 environment.

Initial profiles:

### `rootless-upstream`

Authority comes from the selected upstream RootlessJamesDSP commit/release plus the matching factory LiveProg corpus.

### `rootless-051`

Authority comes from the selected `051-lab/RootlessJamesDSP` commit/branch and its verified extensions. A feature present only in this profile must not be taught or emitted as universal upstream behavior.

### `eel-vm-core`

Represents the underlying JamesDSP EEL_VM language/runtime capabilities independent of Android host UI behavior.

### `jdsp-linux`

Secondary compatibility profile for JDSP4Linux/related JamesDSP environments when explicitly selected and verified.

Every project workspace records:

```yaml
host_profile: rootless-051
host_revision: <resolved git revision>
sample_rates:
  - 44100
  - 48000
channels: 2
```

The implementation must resolve an actual revision before using profile-specific extensions in a compatibility claim.

---

## 5. Source Authority Hierarchy

Every retrieved artifact receives both a **domain** and an **authority class**. Authority is evaluated only inside the domain in which the source is competent.

| Class | Typical source | Valid authority domain |
|---|---|---|
| `TARGET_HOST` | selected RootlessJamesDSP fork/revision | host lifecycle, exposed sections, parameters, integration |
| `VM` | JamesDSP EEL_VM source/docs | core EEL2 syntax, VM memory, DSP primitives |
| `SHIPPED_UPSTREAM` | verified 40-file upstream LiveProg corpus | known-good upstream idioms |
| `VAULT` | verified EELVault processors/audits | project-local proven patterns |
| `SPEC` | standards, manufacturer/service docs | external technical facts covered by that source |
| `RESEARCH` | peer-reviewed papers / strong measurements | scientific models and measured findings |
| `REFERENCE` | textbooks / respected technical references | general DSP design guidance |
| `INSPIRATION` | Airwindows / experimental DSP | algorithmic ideas and implementation study |
| `ESTIMATE` | derived or perceptually tuned value | explicitly non-authoritative design choice |

Examples of correct conflict handling:

- A paper cannot override what syntax the selected RootlessJamesDSP host accepts.
- An upstream factory script cannot prove that a feature exists in a different fork revision.
- Airwindows C++ can inspire a topology but cannot prove EEL2 syntax.
- A perceptually tuned constant cannot be presented as a manufacturer measurement.

Unresolved conflicts are surfaced explicitly.

---

## 6. Supported Task Classes

EELWizard v1 supports:

### Build
- design a new LiveProg processor from a sonic/functional brief;
- port a suitable DSP algorithm into the selected host profile;
- produce an EELVault candidate package.

### Repair
- diagnose syntax errors;
- correct host incompatibilities;
- repair instability, DC buildup, bad initialization, discontinuities, stereo defects, sample-rate mistakes, and invalid memory behavior.

### Review
- audit code and architecture;
- compare revisions;
- detect regressions;
- identify unsupported claims and mobile hot paths.

### Optimize
- move invariant work out of per-sample execution;
- reduce expensive transcendental operations when behavior can be preserved;
- reduce memory traffic and unnecessary state;
- measure before/after behavior.

### Research
- search literature;
- extract models/measurements;
- distinguish evidence from estimates;
- convert relevant findings into testable DSP hypotheses.

### Explain
- produce technical and plain-language explanations;
- explain controls, signal flow, assumptions, limitations, and validation evidence.

---

## 7. Non-Goals for v1

Version 1 does not attempt to:

- fine-tune or train a foundation model;
- autonomously publish releases without human approval;
- replace physical-device listening tests with synthetic metrics;
- guarantee identical behavior across all EEL2 hosts;
- model hardware from invented or unsourced values;
- run a multi-agent swarm for every request;
- build a graphical plugin framework;
- become a generic DAW coding assistant.

---

## 8. System Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│                         EELWizard                            │
│                                                              │
│  Task Orchestrator                                           │
│        │                                                     │
│        ├── DSP Researcher                                    │
│        ├── DSP Architect                                     │
│        ├── EEL Engineer                                      │
│        └── DSP Reviewer                                      │
│        │                                                     │
│        ▼                                                     │
│  Deterministic Tool Layer                                    │
│        │                                                     │
│        ├── source-aware retrieval                            │
│        ├── EEL structural validator                          │
│        ├── EEL_VM runner                                     │
│        ├── Python DSP laboratory                             │
│        ├── EELBench                                          │
│        └── EELVault packager                                 │
└────────┬─────────────────────────────────────────────────────┘
         │
         ├── selected RootlessJamesDSP host/device
         └── EELVault candidate/release workflow
```

The specialist labels are operating modes in v0, not necessarily separate processes.

---

## 9. Specialist Responsibilities

### Orchestrator

- classify the request;
- resolve target host profile/revision;
- identify required evidence;
- select specialist modes and tools;
- maintain project state and claim ledger;
- enforce validation/release gates.

### DSP Researcher

- decide when research materially improves the design;
- formulate search questions;
- invoke Asta tooling;
- extract relevant findings with provenance;
- create testable hypotheses rather than dumping literature summaries into code.

### DSP Architect

- translate the brief into signal flow;
- define controls, state, latency, channel behavior, sample-rate behavior, and expected transfer characteristics;
- choose mobile-appropriate algorithms;
- specify acceptance tests before implementation.

### EEL Engineer

- retrieve host/VM rules and known-good examples;
- implement valid EEL2 for the selected profile;
- preserve stereo/state correctness;
- avoid unsupported JSFX/C syntax;
- annotate non-obvious algorithmic choices.

### DSP Reviewer

- independently challenge the implementation;
- inspect initialization, stability, sample-rate scaling, smoothing, channel symmetry, memory indexing, latency, and CPU risk;
- compare measurements with design claims;
- reject unsupported release status.

---

## 10. Knowledge Engine

Repository corpus layout:

```text
corpus/
├── host_profiles/
│   ├── rootless-upstream/
│   ├── rootless-051/
│   └── jdsp-linux/
├── eel_vm/
│   ├── language/
│   └── dsp_primitives/
├── liveprog/
│   ├── upstream_factory/
│   ├── supplemental/
│   └── manifests/
├── eelvault/
│   ├── normalized/
│   └── manifests/
└── references/
    └── manifests/
```

### Normalized records

Each `.eel` script receives a machine-readable record such as:

```yaml
name: delayChorus
source_class: SHIPPED_UPSTREAM
source_revision: <resolved git revision>
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
vm_primitives: []
state_variables: []
memory_regions: []
controls: []
source_path: corpus/liveprog/upstream_factory/delayChorus.eel
content_hash: <sha256>
```

The first ingester prioritizes facts that can be extracted deterministically. Semantic annotations may be added later without changing the canonical raw source.

### Retrieval

Retrieval is hybrid:

1. exact/token search for primitives and syntax;
2. structured filtering by host profile, authority class, technique, section, and VM primitive;
3. semantic retrieval for similar processors;
4. reranking that favors competent high-authority sources.

A normal authoring request should retrieve host/VM truth before lower-authority inspiration material.

---

## 11. Asta Integration

Asta is EELWizard's **research subsystem**, not its central brain.

Preferred integration is `asta-plugins` / the `asta` CLI because it is designed for use by local coding agents.

### Research triggers

Research is invoked when at least one condition applies:

- a processor models a real physical device/process;
- psychoacoustics or perception materially affects the design;
- measured constants or standards matter;
- the user explicitly asks for evidence;
- competing approaches need evidence-based selection;
- adjacent scientific methods may improve the algorithm.

Research is skipped for tasks such as straightforward syntax repair unless it adds clear value.

### Research output contract

```yaml
question: <research question>
claims:
  - claim: <supported statement>
    source_type: paper
    source: <identifier or URL>
    confidence: high
    implementation_relevance: <why this matters to DSP>
open_questions: []
testable_hypotheses: []
```

No research-derived numeric value may enter a release implementation without source metadata or explicit `ESTIMATE` status.

---

## 12. Claim Ledger

Every DSP project receives `claims.yaml`.

A claim record contains:

```yaml
id: example_parameter
value: 0.5
unit: normalized
provenance: measurement
source: <source identifier>
implementation: <where/how used>
verification: <test that checks the claim>
```

Perceptual choices use `provenance: estimate` and include a rationale. The ledger exists specifically to prevent model memory, measurements, and tuning choices from becoming indistinguishable.

---

## 13. DSP Laboratory

The Python laboratory provides deterministic signal generation and measurement.

### Required signal fixtures

- silence;
- DC;
- impulse;
- sine;
- stepped sine;
- logarithmic sweep;
- white noise;
- pink noise;
- multitone;
- two-tone IMD fixture;
- transient bursts;
- amplitude ramps;
- near-zero values;
- overload/extreme-amplitude vectors;
- stereo correlated/anti-correlated fixtures.

### Required measurements

- frequency response;
- impulse response;
- phase response when observable;
- latency;
- peak/RMS;
- crest factor;
- DC offset/drift;
- harmonic spectrum;
- THD;
- IMD test metrics;
- static transfer curve;
- dynamic gain behavior;
- attack/release behavior;
- channel mismatch;
- stereo correlation;
- mono fold-down behavior;
- NaN/Inf detection;
- runaway-state detection.

Where a Python reference implementation exists, the EEL candidate is compared using task-specific tolerances rather than a universal sample-identical requirement.

---

## 14. Validation Pipeline

### Gate 1 — Structural/static validation

Checks include:

- required sections for the selected profile;
- balanced delimiters;
- unsupported C/JSFX syntax patterns;
- suspicious conditional/assignment constructs;
- parameter declarations;
- memory/indexing hazards that can be inferred statically;
- forbidden unfinished implementation markers;
- profile-specific section usage.

### Gate 2 — EEL_VM compile/execution

The candidate is compiled/executed through the closest available VM harness. Diagnostics are returned as structured data.

### Gate 3 — Deterministic fixtures

The processor is exercised using DSP-lab signals.

### Gate 4 — Objective measurements

Measured output is checked against project acceptance criteria and the claim ledger.

### Gate 5 — Performance review

Review covers:

- per-sample expensive functions;
- avoidable recalculation;
- unbounded loops;
- memory size/traffic;
- excessive FFT/STFT choices;
- duplicated state;
- likely mobile real-time cost.

### Gate 6 — Target-host/device validation

The script must load and run in the selected RootlessJamesDSP profile before that profile may receive `DEVICE_PASS`.

The first implementation may use a human-operated device handoff. Automated ADB deployment/capture is a later extension.

### Gate 7 — Listening evaluation

Human listening approval remains mandatory for subjective release claims.

---

## 15. Compatibility Policy

Default design target when the brief does not require otherwise:

- stereo;
- 44.1 kHz and 48 kHz;
- Android/mobile-conscious CPU use;
- no undocumented host dependency.

Every candidate states:

- target host profile and revision;
- supported sample rates;
- channel assumptions;
- expected latency;
- control smoothing behavior;
- bypass/reset click behavior where relevant;
- CPU class: `light`, `moderate`, or `heavy`;
- material memory requirements;
- host-specific VM extensions used.

Generic JSFX UI syntax must never be assumed simply because the runtime is EEL-derived.

---

## 16. EELBench

EELBench objectively evaluates the agent itself.

### Benchmark families

**Language**
- repair invalid EEL2;
- identify imported C/JSFX mistakes;
- reason about scope/control flow;
- use EEL memory/functions correctly.

**Host**
- select the correct profile;
- use sections and host variables correctly;
- preserve stereo behavior;
- avoid cross-profile feature leakage.

**DSP construction**
- filter;
- compressor/envelope follower;
- fractional delay;
- M/S processing;
- saturation;
- FIR/FFT/STFT tasks where justified.

**Diagnostics**
- initialization defects;
- sample-rate dependencies;
- DC accumulation;
- zipper-noise risk;
- stereo asymmetry;
- NaN/Inf paths;
- memory/indexing defects.

**Optimization**
- remove unnecessary per-sample expensive operations;
- precompute invariants;
- reduce memory traffic;
- preserve behavior within defined tolerances.

**Research-to-DSP**
- formulate a research question;
- retrieve relevant evidence;
- retain provenance;
- create a testable model;
- implement and verify it.

**Repository engineering**
- build a complete EELVault candidate;
- produce metadata/docs/claims;
- execute generic and effect-specific validation;
- report release readiness accurately.

### Scoring

Tasks can score syntax/compile success, host correctness, objective DSP behavior, robustness, provenance, CPU constraints, documentation, and unnecessary-complexity penalties.

Critical failures such as non-loading code, normal-input NaN/Inf generation, or invented source claims fail the task regardless of prose quality.

Development and held-out benchmark sets are versioned separately to reduce benchmark overfitting.

---

## 17. EELVault Boundary

EELWizard and EELVault remain separate repositories.

### `051-lab/EELWizard`

Contains:

- orchestration;
- host-profile corpus;
- EEL_VM corpus/integration;
- source-aware retrieval;
- validators;
- VM runner;
- DSP lab;
- Asta adapter;
- EELBench;
- project workspaces;
- candidate packaging.

### `051-lab/EELVault`

Contains:

- curated processors;
- processor documentation;
- metadata/changelogs;
- validation/audit artifacts appropriate for the collection;
- release history.

Existing EELVault audit scripts are design evidence for extracting common reusable checks into EELWizard while retaining processor-specific tests where needed.

### Candidate logical contract

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

EELWizard may adapt packaging to the existing EELVault directory conventions rather than forcing unrelated repository restructuring.

---

## 18. CLI Surface

The first product is CLI-first so that it can be driven from normal shells and coding agents.

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

A later interactive entry point may expose `eelwizard agent` without changing the deterministic tool contracts.

---

## 19. Logical Tool Contracts

```text
resolve_host_profile(profile, revision)
search_host_docs(query, profile)
search_vm_docs(query)
search_liveprog_examples(query, profile, technique, primitive)
search_eelvault(query)
research_with_asta(question)

lint_eel(path_or_text, profile)
compile_eel(path_or_text, profile)
run_eel(test_fixture, controls, profile)

make_test_signal(spec)
measure_response(result)
measure_harmonics(result)
measure_dynamics(result)
measure_stereo(result)
compare_reference(reference, candidate)

run_eelbench(selection)
create_vault_candidate(project)
```

Tools return structured diagnostics/provenance rather than only prose.

---

## 20. Project State Model

Each development run uses a durable project workspace:

```text
workspaces/<project>/
├── brief.md
├── project.yaml
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

`project.yaml` stores the target host profile/revision and gate status so a later run can resume without reconstructing critical facts from chat history.

Allowed lifecycle states:

- `DESIGN_ONLY`
- `CODE_GENERATED`
- `STATIC_PASS`
- `VM_PASS`
- `MEASUREMENT_PASS`
- `DEVICE_PASS`
- `LISTENING_APPROVED`
- `EELVAULT_CANDIDATE`
- `RELEASED`

The state can advance only when the corresponding gate has evidence.

---

## 21. Security and Execution Boundaries

- generated EEL is untrusted until validated;
- VM execution receives time and memory limits;
- downloaded research/code is never executed automatically;
- provider/API credentials stay in environment-managed secrets;
- no final EELVault release/push occurs without explicit human authorization;
- research evidence is stored separately from executable code.

---

## 22. Technology Choices

Primary implementation language: **Python 3.11+**.

Recommended foundation:

- `uv` for environments/lockfiles;
- `pydantic` for typed schemas;
- `typer` for the CLI;
- NumPy/SciPy for DSP reference code and measurements;
- pytest for deterministic testing;
- SQLite/FTS for the first local structured/text index;
- a lightweight vector layer only where semantic retrieval measurably helps;
- provider adapters behind one interface.

The project intentionally avoids making an agent framework the architectural center. The lasting value should live in the corpus, host profiles, validators, VM harness, DSP lab, and evaluations.

---

## 23. Proposed EELWizard Repository Structure

```text
EELWizard/
├── README.md
├── pyproject.toml
├── uv.lock
├── src/eelwizard/
│   ├── agent/
│   │   ├── orchestrator.py
│   │   ├── roles.py
│   │   ├── state.py
│   │   └── providers/
│   ├── corpus/
│   │   ├── ingest.py
│   │   ├── schema.py
│   │   ├── index.py
│   │   └── retrieve.py
│   ├── hosts/
│   │   ├── profiles.py
│   │   └── resolve.py
│   ├── eel/
│   │   ├── parser.py
│   │   ├── lint.py
│   │   ├── runner.py
│   │   └── diagnostics.py
│   ├── lab/
│   │   ├── signals.py
│   │   ├── measurements.py
│   │   ├── dynamics.py
│   │   ├── harmonics.py
│   │   └── stereo.py
│   ├── research/
│   │   ├── asta.py
│   │   └── claims.py
│   ├── vault/
│   │   ├── package.py
│   │   └── report.py
│   └── cli.py
├── corpus/
│   ├── host_profiles/
│   ├── eel_vm/
│   ├── liveprog/
│   └── eelvault/
├── evals/eelbench/
│   ├── tasks/
│   ├── fixtures/
│   └── scorers/
├── tests/
├── docs/
└── workspaces/
    └── .gitkeep
```

Generated indexes/workspace outputs are ignored or selectively versioned. Canonical source manifests and benchmark fixtures remain version controlled.

---

## 24. Development Milestones

### M0 — Repository and contracts

Deliver:

- `051-lab/EELWizard` repository;
- uv/Python skeleton;
- CLI shell;
- architecture docs;
- typed schemas for source records, host profiles, claims, diagnostics, and project state;
- baseline CI/tests.

Exit when install, CLI startup, tests, and schema round-trips are deterministic.

### M1 — Knowledge engine

Deliver:

- reconcile and ingest the **40 verified upstream factory scripts**;
- ingest the supplemental SoloConsole snapshot separately;
- ingest EEL_VM language/DSP references;
- ingest target-host source manifests;
- ingest verified EELVault processors/audit metadata;
- source authority labels;
- searchable manifests/retrieval CLI.

Exit when every imported artifact has provenance/hash metadata and retrieval does not confuse upstream factory, fork-specific, Vault, research, or inspiration sources.

### M2 — EEL engineer + static validator

Deliver:

- rule-aware linter;
- host-profile-aware diagnostics;
- repair workflow;
- first EEL authoring mode;
- language/host EELBench tasks.

Exit when the 40 upstream factory scripts pass appropriate checks, deliberately broken fixtures fail usefully, and held-out repairs achieve a defined benchmark baseline.

### M3 — EEL_VM runner + DSP lab

Deliver:

- executable VM harness;
- deterministic signals;
- measurement modules;
- robustness stress tests;
- reference-vs-EEL comparison.

Exit when representative gain/filter/delay algorithms execute and produce expected measurements, with NaN/Inf/runaway checks automated.

### M4 — Asta research subsystem

Deliver:

- Asta adapter;
- evidence schema;
- claim ledger;
- research-to-design flow;
- provenance-aware reports.

Exit when research can be invoked selectively and no research-derived release constant loses its provenance.

### M5 — EELBench

Deliver:

- benchmark families from this spec;
- development + held-out fixtures;
- deterministic scorers where possible;
- benchmark report;
- regression policy for deterministic components.

Exit when agent revisions can be compared quantitatively.

### M6 — EELVault candidate workflow

Deliver:

- durable project orchestration;
- candidate packaging;
- validation reports;
- reusable checks extracted from existing EELVault audits;
- device/listening handoff format;
- documentation generation.

Exit when a new effect can move from brief to EELVault candidate without losing design, source, or measurement provenance.

---

## 25. First Vertical Slice

The first implementation proves one narrow loop before building the full research agent:

```text
40-file upstream factory corpus
        ↓
normalize + hash + index
        ↓
retrieve known-good examples
        ↓
repair a deliberately broken simple upstream-compatible LiveProg script
        ↓
static validation
        ↓
EEL_VM execution of a small deterministic fixture
        ↓
Python measurement report
```

A gain/filter/delay-class fixture is preferred because expected behavior is easy to measure and failures are easy to localize.

This slice proves the key engineering loop before Asta integration, complex autonomous workflows, or EELVault packaging are added.

---

## 26. v1 Acceptance Criteria

EELWizard v1 is successful when:

1. The 40 current upstream factory scripts are indexed as `SHIPPED_UPSTREAM` with provenance and hashes.
2. The supplied supplemental SoloConsole snapshot is indexed separately and cannot accidentally define upstream host behavior.
3. Host profiles prevent fork-specific features from leaking into incompatible targets.
4. The system distinguishes target-host rules, VM rules, upstream examples, Vault patterns, research evidence, inspiration, and estimates.
5. A generated script cannot become `verified` without the configured deterministic gates.
6. A useful subset of EEL algorithms can execute through the VM harness.
7. The DSP lab objectively measures common filter, dynamics, harmonic, latency, robustness, and stereo behaviors.
8. EELBench produces repeatable scores for agent revisions.
9. Asta research can be invoked selectively and retains provenance.
10. Project workspaces resume without relying on chat-memory reconstruction.
11. EELVault candidates include code, documentation, claims, and validation evidence.
12. Human approval remains required for final device/listening/release claims.

---

## 27. Explicit Post-v1 Possibilities

The following are intentionally outside v1 scope rather than unresolved requirements:

- model fine-tuning using EELBench/repair traces;
- persistent multi-agent workers;
- automated ADB deployment/audio capture;
- hardware-in-the-loop measurement;
- GUI/web front end;
- formats beyond EEL2 LiveProg;
- autonomous long-horizon DSP invention campaigns;
- distributed benchmark runners.

They should be reconsidered only when v1 measurements show a real limitation that they solve.

---

## 28. Design Summary

EELWizard is a local-first, provider-agnostic audio-DSP engineering system built from:

```text
DSP reasoning
+ target-host profiles
+ EEL_VM language/runtime truth
+ 40 verified upstream factory LiveProg programs
+ separately classified supplemental/Vault programs
+ verified EELVault engineering patterns
+ optional Asta scientific research
+ deterministic EEL execution
+ Python audio measurement
+ EELBench evaluation
+ human device/listening approval
```

Its defining rule is:

> **Never confuse plausible EEL2 with proven DSP, and never confuse one host profile with another.**

The project advances only when research, design, implementation, execution, measurement, and host validation support the specific claim being made.