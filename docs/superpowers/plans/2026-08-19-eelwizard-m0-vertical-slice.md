# EELWizard M0 + First Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `051-lab/EELWizard` repository, establish its typed contracts and source-aware LiveProg corpus layer, and prove one end-to-end path that retrieves a known-good RootlessJamesDSP pattern, repairs a deliberately broken gain processor, validates it, executes it through upstream EEL_VM, and emits an objective gain measurement report.

**Architecture:** The first slice is deliberately infrastructure-first. Python owns parsing, source authority, host profiles, retrieval, lint/repair, orchestration, and measurement; upstream EEL_VM remains an external GPL-2.0 executable invoked by subprocess rather than being copied or linked into the Python package. The slice uses upstream `gainControl.eel` because its expected behavior is mathematically unambiguous and therefore suitable for proving the validation chain before adding model-provider orchestration or Asta.

**Tech Stack:** Python 3.11+, uv, Pydantic v2, Typer, NumPy, pytest, SQLite/FTS5 from the Python standard library, Git, GitHub Actions, PowerShell for the Windows EEL_VM bootstrap.

**Spec:** `docs/superpowers/specs/2026-08-19-eelwizard-design.md`

## Global Constraints

- Python version floor is **3.11**.
- EELWizard is local-first and provider-agnostic; no model-provider SDK is added in this plan.
- Asta integration is explicitly outside this plan; it begins after this deterministic vertical slice is green.
- Upstream RootlessJamesDSP source of truth is pinned to commit `60d25ae8a53c6f4691c090673df290a73c6b6357` for this slice.
- Upstream EEL_VM source of truth is pinned to commit `284b3da00af91efc3aff6bfc1acefb4e801a8ad6` for this slice.
- The canonical gain fixture is upstream `app/src/main/assets/Liveprog/gainControl.eel`, blob `b0df21b571311cfb7eebdff269b6d78dfdfdcd86`.
- The supplied corpus is classified as **40 upstream factory scripts plus supplemental project material**; `soloconsole.eel` must never be counted as an upstream factory script.
- Source authority ordering is `HOST > VM > SHIPPED > VAULT > SPEC > RESEARCH > REFERENCE > INSPIRATION > ESTIMATE`.
- Initial host profiles are `rootless-upstream`, `rootless-051`, `eel-vm-core`, and `jdsp-linux`.
- Generated code is untrusted until its corresponding gate runs successfully.
- No command may report `VM_PASS` unless upstream EEL_VM actually executed the generated standalone program successfully.
- No command may report `MEASUREMENT_PASS` unless an objective acceptance check actually passed.
- Do not vendor, modify, or link EEL_VM source into the Python package in this plan. Build the upstream CLI separately and invoke it as an external executable.
- Do not add a repository license during this slice. Licensing for EELWizard itself is deferred explicitly until the distribution boundary around GPL-2.0 EEL_VM has been reviewed; this does not block private/local development.
- TDD is mandatory: every behavior change begins with a failing test, then minimal implementation, then green tests.
- Commit after every independently reviewable task.

---

## File Map

The plan creates the following focused structure in the new `051-lab/EELWizard` repository:

```text
EELWizard/
├── .github/
│   └── workflows/
│       └── ci.yml
├── .gitignore
├── README.md
├── pyproject.toml
├── uv.lock
├── docs/
│   └── superpowers/
│       ├── specs/
│       │   └── 2026-08-19-eelwizard-design.md
│       └── plans/
│           └── 2026-08-19-eelwizard-m0-vertical-slice.md
├── corpus/
│   ├── sources/
│   │   ├── rootless-upstream.json
│   │   └── eel-vm-core.json
│   └── generated/
│       └── .gitkeep
├── scripts/
│   └── bootstrap_eel_vm.ps1
├── src/
│   └── eelwizard/
│       ├── __init__.py
│       ├── cli.py
│       ├── models.py
│       ├── corpus/
│       │   ├── __init__.py
│       │   ├── ingest.py
│       │   ├── liveprog.py
│       │   ├── retrieve.py
│       │   └── store.py
│       ├── eel/
│       │   ├── __init__.py
│       │   ├── diagnostics.py
│       │   ├── lint.py
│       │   ├── repair.py
│       │   ├── standalone.py
│       │   └── runner.py
│       ├── lab/
│       │   ├── __init__.py
│       │   ├── measurements.py
│       │   └── signals.py
│       └── vertical_slice.py
└── tests/
    ├── fixtures/
    │   ├── broken_gain.eel
    │   └── upstream_gainControl.eel
    ├── integration/
    │   └── test_eel_vm_gain.py
    ├── test_cli.py
    ├── test_models.py
    ├── test_corpus_ingest.py
    ├── test_liveprog.py
    ├── test_retrieve.py
    ├── test_lint_repair.py
    ├── test_standalone.py
    ├── test_measurements.py
    └── test_vertical_slice.py
```

`corpus/generated/` contains locally generated corpus/index artifacts and remains ignored except for `.gitkeep`. Canonical source descriptors and test fixtures remain version controlled.

---

### Task 1: Create the repository and reproducible Python skeleton

**Files:**
- Create: `README.md`
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `src/eelwizard/__init__.py`
- Create: `src/eelwizard/cli.py`
- Create: `tests/test_cli.py`
- Create: `.github/workflows/ci.yml`
- Copy: `docs/superpowers/specs/2026-08-19-eelwizard-design.md`
- Copy: `docs/superpowers/plans/2026-08-19-eelwizard-m0-vertical-slice.md`

**Interfaces:**
- Consumes: the approved design and this plan from EELVault.
- Produces: installable package `eelwizard`, console command `eelwizard`, and a green Python CI baseline.

- [ ] **Step 1: Create and clone the GitHub repository**

Run:

```bash
gh repo create 051-lab/EELWizard --public --description "AI audio-DSP research engineer for RootlessJamesDSP LiveProg/EEL2" --clone
cd EELWizard
```

Expected: repository exists locally with `origin` pointing to `051-lab/EELWizard`.

- [ ] **Step 2: Initialize the uv project and dependencies**

Create `pyproject.toml` with this minimum content:

```toml
[project]
name = "eelwizard"
version = "0.1.0"
description = "Audio-DSP research engineer tooling for RootlessJamesDSP LiveProg/EEL2"
requires-python = ">=3.11"
dependencies = [
  "numpy>=2.0",
  "pydantic>=2.8",
  "typer>=0.12",
]

[project.scripts]
eelwizard = "eelwizard.cli:app"

[dependency-groups]
dev = [
  "pytest>=8.2",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
addopts = "-ra"
testpaths = ["tests"]
markers = [
  "integration: requires an external EEL_VM executable",
]
```

Then run:

```bash
uv lock
uv sync --dev
```

Expected: `uv.lock` exists and `uv sync --frozen --dev` succeeds.

- [ ] **Step 3: Write the failing CLI smoke test**

Create `tests/test_cli.py`:

```python
from typer.testing import CliRunner

from eelwizard.cli import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "EELWizard 0.1.0"
```

Run:

```bash
uv run pytest tests/test_cli.py -v
```

Expected: FAIL because `eelwizard.cli` does not exist yet.

- [ ] **Step 4: Implement the minimum package and CLI**

Create `src/eelwizard/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `src/eelwizard/cli.py`:

```python
import typer

from eelwizard import __version__

app = typer.Typer(no_args_is_help=True)


@app.command()
def version() -> None:
    typer.echo(f"EELWizard {__version__}")
```

- [ ] **Step 5: Run the smoke test and command**

Run:

```bash
uv run pytest tests/test_cli.py -v
uv run eelwizard version
```

Expected: PASS and output `EELWizard 0.1.0`.

- [ ] **Step 6: Add baseline CI**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  python:
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          python-version: "3.11"
      - run: uv sync --frozen --dev
      - run: uv run pytest -m "not integration" -v
```

- [ ] **Step 7: Copy the approved design and plan into the new repository**

Copy the exact approved EELVault documents without editing their technical content:

```text
docs/superpowers/specs/2026-08-19-eelwizard-design.md
docs/superpowers/plans/2026-08-19-eelwizard-m0-vertical-slice.md
```

- [ ] **Step 8: Add `.gitignore` and README**

`.gitignore` must include:

```gitignore
.venv/
__pycache__/
.pytest_cache/
.cache/
corpus/generated/*
!corpus/generated/.gitkeep
reports/
*.pyc
```

README must state that the first milestone is deterministic tooling, not an autonomous LLM agent, and point to the spec and plan.

- [ ] **Step 9: Run the full non-integration suite and commit**

Run:

```bash
uv run pytest -m "not integration" -v
git diff --check
git add .
git commit -m "chore: bootstrap EELWizard"
```

Expected: all tests pass and working tree is clean after commit.

---

### Task 2: Define authority, host-profile, diagnostic, claim, and project-state contracts

**Files:**
- Create: `src/eelwizard/models.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Consumes: no runtime interface from Task 1 beyond the package.
- Produces: `SourceClass`, `HostProfile`, `ProjectStatus`, `DiagnosticSeverity`, `Diagnostic`, `Claim`, `LiveProgRecord`, and `ProjectState`.

- [ ] **Step 1: Write failing model tests**

Create `tests/test_models.py`:

```python
from eelwizard.models import (
    Claim,
    Diagnostic,
    DiagnosticSeverity,
    HostProfile,
    LiveProgRecord,
    ProjectState,
    ProjectStatus,
    SourceClass,
)


def test_source_authority_order_is_stable() -> None:
    assert SourceClass.HOST.rank == 1
    assert SourceClass.SHIPPED.rank == 3
    assert SourceClass.ESTIMATE.rank == 9


def test_host_profiles_are_explicit() -> None:
    assert HostProfile.ROOTLESS_UPSTREAM.value == "rootless-upstream"
    assert HostProfile.ROOTLESS_051.value == "rootless-051"


def test_project_state_round_trip() -> None:
    state = ProjectState(name="gain-slice", status=ProjectStatus.STATIC_PASS)
    restored = ProjectState.model_validate_json(state.model_dump_json())
    assert restored == state


def test_liveprog_record_requires_content_hash() -> None:
    record = LiveProgRecord(
        name="gainControl",
        source_class=SourceClass.SHIPPED,
        host_profile=HostProfile.ROOTLESS_UPSTREAM,
        source_path="gainControl.eel",
        content_hash="abc123",
        sections=["init", "sample"],
    )
    assert record.sections == ["init", "sample"]


def test_diagnostic_and_claim_are_typed() -> None:
    diag = Diagnostic(code="EEL001", severity=DiagnosticSeverity.ERROR, message="missing semicolon")
    claim = Claim(id="default_gain", value=-8.0, unit="dB", provenance="SHIPPED")
    assert diag.code == "EEL001"
    assert claim.value == -8.0
```

Run:

```bash
uv run pytest tests/test_models.py -v
```

Expected: FAIL because the models do not exist.

- [ ] **Step 2: Implement the exact enums and models**

`src/eelwizard/models.py` must expose:

```python
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SourceClass(str, Enum):
    HOST = "HOST"
    VM = "VM"
    SHIPPED = "SHIPPED"
    VAULT = "VAULT"
    SPEC = "SPEC"
    RESEARCH = "RESEARCH"
    REFERENCE = "REFERENCE"
    INSPIRATION = "INSPIRATION"
    ESTIMATE = "ESTIMATE"

    @property
    def rank(self) -> int:
        order = list(type(self))
        return order.index(self) + 1


class HostProfile(str, Enum):
    ROOTLESS_UPSTREAM = "rootless-upstream"
    ROOTLESS_051 = "rootless-051"
    EEL_VM_CORE = "eel-vm-core"
    JDSP_LINUX = "jdsp-linux"


class ProjectStatus(str, Enum):
    DESIGN_ONLY = "DESIGN_ONLY"
    CODE_GENERATED = "CODE_GENERATED"
    STATIC_PASS = "STATIC_PASS"
    VM_PASS = "VM_PASS"
    MEASUREMENT_PASS = "MEASUREMENT_PASS"
    DEVICE_PASS = "DEVICE_PASS"
    LISTENING_APPROVED = "LISTENING_APPROVED"
    EELVAULT_CANDIDATE = "EELVAULT_CANDIDATE"
    RELEASED = "RELEASED"


class DiagnosticSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Diagnostic(BaseModel):
    code: str
    severity: DiagnosticSeverity
    message: str
    line: int | None = None
    column: int | None = None


class Claim(BaseModel):
    id: str
    value: Any
    unit: str | None = None
    provenance: str
    source: str | None = None
    verification: str | None = None


class LiveProgRecord(BaseModel):
    name: str
    source_class: SourceClass
    host_profile: HostProfile
    source_path: str
    content_hash: str
    sections: list[str] = Field(default_factory=list)
    host_variables: list[str] = Field(default_factory=list)
    techniques: list[str] = Field(default_factory=list)
    vm_primitives: list[str] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)
    text: str = ""


class ProjectState(BaseModel):
    name: str
    status: ProjectStatus = ProjectStatus.DESIGN_ONLY
    claims: list[Claim] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
```

- [ ] **Step 3: Run tests and commit**

Run:

```bash
uv run pytest tests/test_models.py -v
git diff --check
git add src/eelwizard/models.py tests/test_models.py
git commit -m "feat: add EELWizard core contracts"
```

Expected: PASS.

---

### Task 3: Parse RootlessJamesDSP LiveProg sections and metadata deterministically

**Files:**
- Create: `src/eelwizard/corpus/__init__.py`
- Create: `src/eelwizard/corpus/liveprog.py`
- Create: `tests/fixtures/upstream_gainControl.eel`
- Create: `tests/test_liveprog.py`

**Interfaces:**
- Consumes: `HostProfile`, `LiveProgRecord`, `SourceClass`.
- Produces: `LiveProgDocument`, `parse_liveprog(text: str) -> LiveProgDocument`, `normalize_liveprog(...) -> LiveProgRecord`.

- [ ] **Step 1: Add the exact upstream gain fixture**

Create `tests/fixtures/upstream_gainControl.eel` with the pinned upstream content:

```eel
desc: Gain control
//tags: gain

dB:-8<-30,15,1>Volume gain (dB)

@init
dB = -8;
DB_2_LOG = 0.11512925464970228420089957273422;
gainLin = exp(dB * DB_2_LOG);

@sample
spl0 = spl0 * gainLin;
spl1 = spl1 * gainLin;
```

- [ ] **Step 2: Write failing parser tests**

Create `tests/test_liveprog.py`:

```python
from pathlib import Path

from eelwizard.corpus.liveprog import normalize_liveprog, parse_liveprog
from eelwizard.models import HostProfile, SourceClass

FIXTURE = Path("tests/fixtures/upstream_gainControl.eel")


def test_parse_gain_control_sections_and_preamble() -> None:
    doc = parse_liveprog(FIXTURE.read_text(encoding="utf-8"))
    assert doc.description == "Gain control"
    assert doc.tags == ["gain"]
    assert list(doc.sections) == ["init", "sample"]
    assert "gainLin = exp" in doc.sections["init"]
    assert "spl0 = spl0 * gainLin;" in doc.sections["sample"]
    assert [control.name for control in doc.controls] == ["dB"]


def test_normalize_gain_control_marks_upstream_authority() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    record = normalize_liveprog(
        name="gainControl",
        text=text,
        source_path="app/src/main/assets/Liveprog/gainControl.eel",
        source_class=SourceClass.SHIPPED,
        host_profile=HostProfile.ROOTLESS_UPSTREAM,
    )
    assert record.sections == ["init", "sample"]
    assert "spl0" in record.host_variables
    assert "spl1" in record.host_variables
    assert len(record.content_hash) == 64
```

Run:

```bash
uv run pytest tests/test_liveprog.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement the parser with section boundaries owned by the host layer**

`src/eelwizard/corpus/liveprog.py` must define:

```python
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re

from eelwizard.models import HostProfile, LiveProgRecord, SourceClass

SECTION_RE = re.compile(r"^@([A-Za-z_][A-Za-z0-9_]*)\s*$")
CONTROL_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):([^<\n]+)<([^>]*)>(.*)$")
HOST_VARIABLES = ("spl0", "spl1", "srate", "nSmps", "nCh")


@dataclass(frozen=True)
class ControlDefinition:
    name: str
    default: str
    range_spec: str
    description: str


@dataclass(frozen=True)
class LiveProgDocument:
    description: str | None
    tags: list[str]
    controls: list[ControlDefinition] = field(default_factory=list)
    sections: dict[str, str] = field(default_factory=dict)


def parse_liveprog(text: str) -> LiveProgDocument:
    # Parse preamble only until the first @section; collect section bodies verbatim.
    ...


def normalize_liveprog(
    *,
    name: str,
    text: str,
    source_path: str,
    source_class: SourceClass,
    host_profile: HostProfile,
) -> LiveProgRecord:
    doc = parse_liveprog(text)
    return LiveProgRecord(
        name=name,
        source_class=source_class,
        host_profile=host_profile,
        source_path=source_path,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        sections=list(doc.sections),
        host_variables=[name for name in HOST_VARIABLES if re.search(rf"\b{re.escape(name)}\b", text)],
        controls=[control.name for control in doc.controls],
        text=text,
    )
```

Replace the ellipsis in `parse_liveprog` with a single-pass implementation that:

1. reads `desc:` and `//tags:` only before the first section;
2. parses the Rootless numeric control syntax shown in the fixture;
3. starts a new section only when the entire trimmed line matches `@name`;
4. preserves section body lines and order;
5. does not reinterpret EEL expressions.

- [ ] **Step 4: Run tests and commit**

Run:

```bash
uv run pytest tests/test_liveprog.py -v
git diff --check
git add src/eelwizard/corpus tests/fixtures/upstream_gainControl.eel tests/test_liveprog.py
git commit -m "feat: parse LiveProg structure"
```

Expected: PASS.

---

### Task 4: Add pinned source descriptors and build the 40-script upstream manifest

**Files:**
- Create: `corpus/sources/rootless-upstream.json`
- Create: `corpus/sources/eel-vm-core.json`
- Create: `src/eelwizard/corpus/ingest.py`
- Modify: `src/eelwizard/cli.py`
- Create: `tests/test_corpus_ingest.py`

**Interfaces:**
- Consumes: `normalize_liveprog(...)`.
- Produces: `build_rootless_manifest(source_dir: Path, output: Path) -> list[LiveProgRecord]` and CLI `eelwizard corpus build-rootless SOURCE_DIR`.

- [ ] **Step 1: Create pinned source descriptors**

`corpus/sources/rootless-upstream.json`:

```json
{
  "name": "RootlessJamesDSP upstream LiveProg",
  "repository": "https://github.com/timschneeb/RootlessJamesDSP.git",
  "commit": "60d25ae8a53c6f4691c090673df290a73c6b6357",
  "path": "app/src/main/assets/Liveprog",
  "source_class": "SHIPPED",
  "host_profile": "rootless-upstream",
  "expected_eel_count": 40
}
```

`corpus/sources/eel-vm-core.json`:

```json
{
  "name": "JamesDSP EEL_VM",
  "repository": "https://github.com/james34602/EEL_VM.git",
  "commit": "284b3da00af91efc3aff6bfc1acefb4e801a8ad6",
  "source_class": "VM",
  "host_profile": "eel-vm-core"
}
```

- [ ] **Step 2: Write failing ingestion tests**

Use a temporary directory with two fixture copies plus one `soloconsole.eel` sentinel. The test must prove supplemental project material cannot silently become `SHIPPED`:

```python
from pathlib import Path

import pytest

from eelwizard.corpus.ingest import CorpusCountError, build_rootless_manifest


def test_upstream_import_rejects_wrong_factory_count(tmp_path: Path) -> None:
    source = tmp_path / "Liveprog"
    source.mkdir()
    text = Path("tests/fixtures/upstream_gainControl.eel").read_text(encoding="utf-8")
    (source / "gainControl.eel").write_text(text, encoding="utf-8")
    with pytest.raises(CorpusCountError):
        build_rootless_manifest(source, tmp_path / "manifest.jsonl", expected_count=40)


def test_upstream_import_never_accepts_soloconsole_as_factory(tmp_path: Path) -> None:
    source = tmp_path / "Liveprog"
    source.mkdir()
    text = Path("tests/fixtures/upstream_gainControl.eel").read_text(encoding="utf-8")
    for i in range(39):
        (source / f"factory_{i}.eel").write_text(text, encoding="utf-8")
    (source / "soloconsole.eel").write_text(text, encoding="utf-8")
    with pytest.raises(CorpusCountError):
        build_rootless_manifest(source, tmp_path / "manifest.jsonl", expected_count=40)
```

Run:

```bash
uv run pytest tests/test_corpus_ingest.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement deterministic manifest creation**

`build_rootless_manifest` must:

1. enumerate `*.eel` in filename order;
2. reject any file named `soloconsole.eel` case-insensitively for the upstream profile;
3. require exactly `expected_count` files;
4. normalize every script as `SourceClass.SHIPPED` + `HostProfile.ROOTLESS_UPSTREAM`;
5. write one Pydantic JSON object per line using UTF-8 and sorted filename order;
6. return the records.

Define:

```python
class CorpusCountError(RuntimeError):
    pass
```

- [ ] **Step 4: Add the corpus CLI group**

Extend `cli.py` with:

```python
corpus_app = typer.Typer(no_args_is_help=True)
app.add_typer(corpus_app, name="corpus")


@corpus_app.command("build-rootless")
def build_rootless(source_dir: Path, output: Path = Path("corpus/generated/rootless-upstream.jsonl")) -> None:
    records = build_rootless_manifest(source_dir, output, expected_count=40)
    typer.echo(f"Indexed {len(records)} upstream LiveProg scripts")
```

- [ ] **Step 5: Run unit tests**

Run:

```bash
uv run pytest tests/test_corpus_ingest.py tests/test_liveprog.py -v
```

Expected: PASS.

- [ ] **Step 6: Run the real pinned-corpus import**

Run:

```bash
git clone https://github.com/timschneeb/RootlessJamesDSP.git .cache/rootless-upstream
git -C .cache/rootless-upstream checkout 60d25ae8a53c6f4691c090673df290a73c6b6357
uv run eelwizard corpus build-rootless .cache/rootless-upstream/app/src/main/assets/Liveprog
```

Expected exact output:

```text
Indexed 40 upstream LiveProg scripts
```

Then verify:

```bash
python -c "from pathlib import Path; print(sum(1 for _ in Path('corpus/generated/rootless-upstream.jsonl').open(encoding='utf-8')))"
```

Expected: `40`.

- [ ] **Step 7: Commit**

```bash
git add corpus/sources src/eelwizard/corpus/ingest.py src/eelwizard/cli.py tests/test_corpus_ingest.py
git commit -m "feat: ingest pinned Rootless LiveProg corpus"
```

Do not commit `.cache/` or `corpus/generated/rootless-upstream.jsonl` in this task.

---

### Task 5: Add SQLite/FTS retrieval over normalized LiveProg records

**Files:**
- Create: `src/eelwizard/corpus/store.py`
- Create: `src/eelwizard/corpus/retrieve.py`
- Modify: `src/eelwizard/cli.py`
- Create: `tests/test_retrieve.py`

**Interfaces:**
- Consumes: iterable of `LiveProgRecord`.
- Produces: `CorpusStore`, `SearchHit`, `search_liveprog(query: str, limit: int = 5)`, CLI `eelwizard corpus inspect QUERY`.

- [ ] **Step 1: Write failing retrieval tests**

```python
from eelwizard.corpus.retrieve import SearchHit
from eelwizard.corpus.store import CorpusStore
from eelwizard.models import HostProfile, LiveProgRecord, SourceClass


def make_record(name: str, text: str, source_class: SourceClass) -> LiveProgRecord:
    return LiveProgRecord(
        name=name,
        source_class=source_class,
        host_profile=HostProfile.ROOTLESS_UPSTREAM,
        source_path=f"{name}.eel",
        content_hash=name,
        sections=["init", "sample"],
        text=text,
    )


def test_gain_query_returns_shipped_gain_first(tmp_path) -> None:
    store = CorpusStore(tmp_path / "corpus.sqlite3")
    store.rebuild([
        make_record("gainControl", "spl0 = spl0 * gainLin; spl1 = spl1 * gainLin;", SourceClass.SHIPPED),
        make_record("gainIdea", "gain concept", SourceClass.INSPIRATION),
    ])
    hits = store.search_liveprog("gain spl0", limit=5)
    assert isinstance(hits[0], SearchHit)
    assert hits[0].record.name == "gainControl"
    assert hits[0].record.source_class is SourceClass.SHIPPED
```

Run:

```bash
uv run pytest tests/test_retrieve.py -v
```

Expected: FAIL.

- [ ] **Step 2: Implement an FTS5 store with explicit authority reranking**

Use standard-library `sqlite3` and create:

```sql
CREATE TABLE records (
    name TEXT PRIMARY KEY,
    source_class TEXT NOT NULL,
    host_profile TEXT NOT NULL,
    source_path TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE VIRTUAL TABLE records_fts USING fts5(name, text, content='');
```

Define:

```python
@dataclass(frozen=True)
class SearchHit:
    record: LiveProgRecord
    text_score: float
    authority_rank: int
```

Search must combine FTS match relevance with a stable authority tie-break where smaller `SourceClass.rank` wins. Do not add embeddings in this slice.

- [ ] **Step 3: Add `corpus inspect` CLI**

The command must open `corpus/generated/corpus.sqlite3`, print each hit as:

```text
[SHIPPED/rootless-upstream] gainControl — app/src/main/assets/Liveprog/gainControl.eel
```

- [ ] **Step 4: Build the real local index and prove retrieval**

Load the 40-record JSONL created in Task 4, rebuild the SQLite database, then run:

```bash
uv run eelwizard corpus inspect "gain spl0"
```

Expected: `gainControl` appears in the returned hits and is labeled `SHIPPED/rootless-upstream`.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/test_retrieve.py -v
git diff --check
git add src/eelwizard/corpus src/eelwizard/cli.py tests/test_retrieve.py
git commit -m "feat: add authority-aware LiveProg retrieval"
```

---

### Task 6: Implement narrow static diagnostics and a safe deterministic repair

**Files:**
- Create: `src/eelwizard/eel/__init__.py`
- Create: `src/eelwizard/eel/diagnostics.py`
- Create: `src/eelwizard/eel/lint.py`
- Create: `src/eelwizard/eel/repair.py`
- Create: `tests/fixtures/broken_gain.eel`
- Create: `tests/test_lint_repair.py`

**Interfaces:**
- Consumes: `parse_liveprog(text)`.
- Produces: `lint_liveprog(text: str, profile: HostProfile) -> list[Diagnostic]` and `apply_safe_repairs(text: str, diagnostics: list[Diagnostic]) -> str`.

- [ ] **Step 1: Create one deliberately broken but unambiguous fixture**

Create `tests/fixtures/broken_gain.eel` identical to the upstream gain fixture except the first sample assignment is missing its semicolon:

```eel
@sample
spl0 = spl0 * gainLin
spl1 = spl1 * gainLin;
```

- [ ] **Step 2: Write failing lint/repair tests**

```python
from pathlib import Path

from eelwizard.eel.lint import lint_liveprog
from eelwizard.eel.repair import apply_safe_repairs
from eelwizard.models import HostProfile

BROKEN = Path("tests/fixtures/broken_gain.eel")


def test_missing_assignment_semicolon_is_reported() -> None:
    diagnostics = lint_liveprog(BROKEN.read_text(encoding="utf-8"), HostProfile.ROOTLESS_UPSTREAM)
    assert [(d.code, d.line) for d in diagnostics if d.severity.value == "error"] == [("EEL001", 12)]


def test_safe_repair_restores_missing_semicolon_only() -> None:
    text = BROKEN.read_text(encoding="utf-8")
    diagnostics = lint_liveprog(text, HostProfile.ROOTLESS_UPSTREAM)
    repaired = apply_safe_repairs(text, diagnostics)
    assert "spl0 = spl0 * gainLin;" in repaired
    assert len(repaired.splitlines()) == len(text.splitlines())
    assert not [d for d in lint_liveprog(repaired, HostProfile.ROOTLESS_UPSTREAM) if d.severity.value == "error"]
```

Run:

```bash
uv run pytest tests/test_lint_repair.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement conservative lint rules**

For this slice, `lint_liveprog` implements only rules that can be determined safely without pretending to be a complete EEL parser:

- `EEL001`: assignment-like statement inside a section is missing `;`;
- `HOST001`: required `@init` section missing;
- `HOST002`: required `@sample` section missing;
- `HOST003`: `@slider` or `@block` encountered under `rootless-upstream`; emit **warning**, not error, because this slice has not yet established those sections as upstream-host truth;
- `EEL010`: line contains a C-style brace `{` or `}` outside a comment/string; emit error.

The missing-semicolon matcher must be restricted to lines that contain `=` but not `==`, `!=`, `<=`, `>=`, terminate in neither `;` nor `(` nor `)`, and are not comments, control declarations, section labels, or continuation expressions.

- [ ] **Step 4: Implement only the `EEL001` auto-repair**

`apply_safe_repairs` may automatically append a semicolon only for diagnostics with code `EEL001`. It must leave all other diagnostics untouched and preserve line count.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/test_lint_repair.py -v
git diff --check
git add src/eelwizard/eel tests/fixtures/broken_gain.eel tests/test_lint_repair.py
git commit -m "feat: add conservative EEL lint and repair"
```

---

### Task 7: Generate a standalone EEL_VM program from LiveProg sections

**Files:**
- Create: `src/eelwizard/eel/standalone.py`
- Create: `tests/test_standalone.py`

**Interfaces:**
- Consumes: `LiveProgDocument`, stereo NumPy arrays, sample rate.
- Produces: `build_standalone_program(document, left, right, sample_rate) -> str`.

- [ ] **Step 1: Write the failing standalone-generation test**

```python
from pathlib import Path

import numpy as np

from eelwizard.corpus.liveprog import parse_liveprog
from eelwizard.eel.standalone import build_standalone_program


def test_standalone_program_runs_init_once_and_sample_per_frame() -> None:
    doc = parse_liveprog(Path("tests/fixtures/upstream_gainControl.eel").read_text(encoding="utf-8"))
    program = build_standalone_program(
        doc,
        np.array([0.25, -0.5, 1.0], dtype=np.float64),
        np.array([-0.25, 0.5, -1.0], dtype=np.float64),
        48000.0,
    )
    assert "srate = 48000" in program
    assert program.count("gainLin = exp") == 1
    assert "loop(3," in program
    assert "spl0 = inL[i];" in program
    assert 'printf("__EELWIZARD__' in program
```

Run:

```bash
uv run pytest tests/test_standalone.py -v
```

Expected: FAIL.

- [ ] **Step 2: Implement the wrapper generator**

The generated EEL source must have this shape:

```eel
srate = 48000;
inL = 0;
inR = 16;

inL[0] = 0.25;
inL[1] = -0.5;
inL[2] = 1.0;
inR[0] = -0.25;
inR[1] = 0.5;
inR[2] = -1.0;

// @init body copied here verbatim

i = 0;
loop(3,
  spl0 = inL[i];
  spl1 = inR[i];
  // @sample body copied here verbatim
  printf("__EELWIZARD__ %.17g %.17g\n", spl0, spl1);
  i += 1;
);
```

Requirements:

1. reject unequal left/right lengths;
2. reject input lengths greater than 4096 in this first CLI-backed runner to avoid enormous generated source;
3. allocate right input after a power-of-two-aligned left region with at least 16 words of separation;
4. include only the bodies of `init` and `sample`; never pass `desc:`, controls, or `@section` markers to core EEL_VM;
5. format finite values with `repr(float(value))` and reject NaN/Inf input fixtures.

- [ ] **Step 3: Run tests and commit**

```bash
uv run pytest tests/test_standalone.py -v
git diff --check
git add src/eelwizard/eel/standalone.py tests/test_standalone.py
git commit -m "feat: generate standalone EEL_VM programs"
```

---

### Task 8: Bootstrap and invoke the upstream EEL_VM CLI as an external executable

**Files:**
- Create: `scripts/bootstrap_eel_vm.ps1`
- Create: `src/eelwizard/eel/runner.py`
- Modify: `src/eelwizard/cli.py`
- Create: `tests/integration/test_eel_vm_gain.py`

**Interfaces:**
- Consumes: path to upstream `eel_CLI.exe`, standalone EEL text.
- Produces: `EelVmRunResult`, `EelVmRunner.run(program: str) -> EelVmRunResult`, CLI `eelwizard doctor --eel-cli PATH`.

- [ ] **Step 1: Write the integration test first**

Create `tests/integration/test_eel_vm_gain.py`:

```python
import os
from pathlib import Path

import numpy as np
import pytest

from eelwizard.corpus.liveprog import parse_liveprog
from eelwizard.eel.runner import EelVmRunner
from eelwizard.eel.standalone import build_standalone_program


@pytest.mark.integration
def test_upstream_eel_vm_executes_gain_fixture() -> None:
    exe = os.environ.get("EELWIZARD_EEL_CLI")
    if not exe:
        pytest.skip("EELWIZARD_EEL_CLI is not configured")

    doc = parse_liveprog(Path("tests/fixtures/upstream_gainControl.eel").read_text(encoding="utf-8"))
    left = np.array([0.25, -0.5, 1.0], dtype=np.float64)
    right = -left
    program = build_standalone_program(doc, left, right, 48000.0)
    result = EelVmRunner(Path(exe)).run(program)

    expected = left * (10 ** (-8.0 / 20.0))
    np.testing.assert_allclose(result.left, expected, rtol=2e-6, atol=2e-7)
    np.testing.assert_allclose(result.right, -expected, rtol=2e-6, atol=2e-7)
    assert result.returncode == 0
```

Run without EEL_VM configured:

```bash
uv run pytest tests/integration/test_eel_vm_gain.py -v
```

Expected: SKIP, not PASS. The task is not complete until the same test passes with a real executable.

- [ ] **Step 2: Implement the external runner**

Define:

```python
from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile

import numpy as np


@dataclass(frozen=True)
class EelVmRunResult:
    returncode: int
    left: np.ndarray
    right: np.ndarray
    stdout: str
    stderr: str


class EelVmRunner:
    def __init__(self, executable: Path):
        self.executable = executable

    def run(self, program: str, timeout_seconds: float = 10.0) -> EelVmRunResult:
        ...
```

Replace the ellipsis with code that:

1. fails immediately with `FileNotFoundError` when the executable is absent;
2. writes the program to a temporary `.eel` file;
3. invokes `[str(executable), str(script_path)]` with `capture_output=True`, `text=True`, and the supplied timeout;
4. raises a dedicated `EelVmExecutionError` on non-zero exit;
5. parses only stdout lines beginning `__EELWIZARD__ `;
6. converts exactly two following tokens per data line to float64 arrays;
7. returns all raw stdout/stderr for diagnostics.

- [ ] **Step 3: Create a reproducible Windows bootstrap script for upstream EEL_VM**

`scripts/bootstrap_eel_vm.ps1` must:

```powershell
$ErrorActionPreference = "Stop"
$Repo = ".cache/eel_vm"
$Commit = "284b3da00af91efc3aff6bfc1acefb4e801a8ad6"

if (-not (Test-Path $Repo)) {
    git clone https://github.com/james34602/EEL_VM.git $Repo
}

git -C $Repo fetch origin
git -C $Repo checkout $Commit

$Solution = Join-Path $Repo "CLI/eel_CLI.sln"
msbuild $Solution /m /p:Configuration=Release /p:Platform=x64

$Exe = Get-ChildItem $Repo -Recurse -Filter "eel_CLI.exe" |
    Where-Object { $_.FullName -match "Release" } |
    Select-Object -First 1

if (-not $Exe) {
    throw "eel_CLI.exe was not produced by the upstream build"
}

Write-Output $Exe.FullName
```

The script does not patch upstream source and does not copy EEL_VM code into EELWizard.

- [ ] **Step 4: Add `doctor` CLI**

Command contract:

```bash
uv run eelwizard doctor --eel-cli C:\path\to\eel_CLI.exe
```

Expected successful output:

```text
EEL_VM executable: OK
EEL_VM smoke execution: OK
```

The smoke execution must run the core EEL expression `printf("__EELWIZARD__ 1 1\n");` through the binary; file existence alone is insufficient.

- [ ] **Step 5: Build EEL_VM and run the real integration test**

From a Visual Studio Developer PowerShell where `msbuild` is available:

```powershell
$exe = ./scripts/bootstrap_eel_vm.ps1 | Select-Object -Last 1
$env:EELWIZARD_EEL_CLI = $exe
uv run eelwizard doctor --eel-cli $exe
uv run pytest tests/integration/test_eel_vm_gain.py -v
```

Expected: integration test PASS. If the upstream project does not build on the installed Visual Studio toolchain, stop this task and report the exact compiler/linker error; do not substitute a fake runner and do not mark `VM_PASS`.

- [ ] **Step 6: Commit only after real VM execution passes**

```bash
git add scripts/bootstrap_eel_vm.ps1 src/eelwizard/eel/runner.py src/eelwizard/cli.py tests/integration/test_eel_vm_gain.py
git commit -m "feat: execute LiveProg through upstream EEL_VM"
```

---

### Task 9: Add deterministic DSP signals and gain measurement

**Files:**
- Create: `src/eelwizard/lab/__init__.py`
- Create: `src/eelwizard/lab/signals.py`
- Create: `src/eelwizard/lab/measurements.py`
- Create: `tests/test_measurements.py`

**Interfaces:**
- Produces: `stereo_sine(...)`, `measure_gain_db(reference, processed) -> float`, `MeasurementResult`.

- [ ] **Step 1: Write failing measurement tests**

```python
import numpy as np

from eelwizard.lab.measurements import measure_gain_db
from eelwizard.lab.signals import stereo_sine


def test_measure_gain_db_reports_minus_8_db() -> None:
    left, _ = stereo_sine(frequency=997.0, sample_rate=48000.0, duration_seconds=0.1, amplitude=0.5)
    processed = left * (10 ** (-8.0 / 20.0))
    assert abs(measure_gain_db(left, processed) - (-8.0)) < 1e-9


def test_measure_gain_rejects_silent_reference() -> None:
    with np.testing.assert_raises(ValueError):
        measure_gain_db(np.zeros(8), np.zeros(8))
```

Run:

```bash
uv run pytest tests/test_measurements.py -v
```

Expected: FAIL.

- [ ] **Step 2: Implement the minimal signal and measurement functions**

`stereo_sine` returns two float64 arrays with identical sine content. `measure_gain_db` computes RMS ratio:

```python
def measure_gain_db(reference: np.ndarray, processed: np.ndarray) -> float:
    ref_rms = float(np.sqrt(np.mean(np.square(reference, dtype=np.float64))))
    out_rms = float(np.sqrt(np.mean(np.square(processed, dtype=np.float64))))
    if ref_rms == 0.0:
        raise ValueError("reference signal is silent")
    if out_rms == 0.0:
        return float("-inf")
    return 20.0 * math.log10(out_rms / ref_rms)
```

`stereo_sine` must calculate frame count as `round(sample_rate * duration_seconds)` and use `np.arange(frame_count, dtype=np.float64) / sample_rate`.

- [ ] **Step 3: Run tests and commit**

```bash
uv run pytest tests/test_measurements.py -v
git diff --check
git add src/eelwizard/lab tests/test_measurements.py
git commit -m "feat: add deterministic DSP measurements"
```

---

### Task 10: Prove the complete vertical slice and emit a validation report

**Files:**
- Create: `src/eelwizard/vertical_slice.py`
- Modify: `src/eelwizard/cli.py`
- Create: `tests/test_vertical_slice.py`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: corpus store, lint/repair, parser, standalone generator, real `EelVmRunner`, gain measurement.
- Produces: `VerticalSliceReport`, `run_gain_vertical_slice(...)`, CLI `eelwizard demo gain-slice`.

- [ ] **Step 1: Define the report contract and failing orchestration test**

In `vertical_slice.py`, the final Pydantic report must contain:

```python
class VerticalSliceReport(BaseModel):
    source_name: str
    retrieved_source_class: SourceClass
    diagnostics_before: list[Diagnostic]
    diagnostics_after: list[Diagnostic]
    status: ProjectStatus
    measured_gain_db: float
    expected_gain_db: float
    gain_error_db: float
    eel_vm_returncode: int
```

Create `tests/test_vertical_slice.py` using a fake runner only to test orchestration state transitions. The fake returns processed arrays multiplied by `10 ** (-8 / 20)`. Assert:

```python
assert report.source_name == "gainControl"
assert report.retrieved_source_class is SourceClass.SHIPPED
assert any(d.code == "EEL001" for d in report.diagnostics_before)
assert not [d for d in report.diagnostics_after if d.severity.value == "error"]
assert report.status is ProjectStatus.MEASUREMENT_PASS
assert abs(report.measured_gain_db + 8.0) < 0.02
assert abs(report.gain_error_db) < 0.02
```

Run:

```bash
uv run pytest tests/test_vertical_slice.py -v
```

Expected: FAIL.

- [ ] **Step 2: Implement `run_gain_vertical_slice` with fail-closed status transitions**

The orchestration order is fixed:

```text
retrieve SHIPPED gainControl
→ lint broken_gain.eel
→ apply EEL001 safe repair
→ lint repaired text
→ status STATIC_PASS only if zero errors remain
→ parse repaired LiveProg
→ generate a 997 Hz, 0.1 s, 48 kHz stereo sine at amplitude 0.5
→ build standalone EEL_VM program
→ execute real/fake injected runner
→ status VM_PASS only when runner succeeds
→ measure processed/reference gain
→ compare against -8.0 dB with tolerance ±0.02 dB
→ status MEASUREMENT_PASS only when tolerance passes
```

If retrieval returns anything other than `SourceClass.SHIPPED` for `gainControl`, raise `VerticalSliceError` rather than continuing.

- [ ] **Step 3: Add the real CLI command**

Command:

```bash
uv run eelwizard demo gain-slice --eel-cli C:\path\to\eel_CLI.exe --report reports/gain-slice.json
```

Successful console output must include:

```text
Source: gainControl [SHIPPED/rootless-upstream]
Static validation: PASS
EEL_VM execution: PASS
Measured gain: -8.00 dB
Expected gain: -8.00 dB
Final status: MEASUREMENT_PASS
```

The JSON report is `VerticalSliceReport.model_dump_json(indent=2)`.

- [ ] **Step 4: Run the fake-runner unit suite**

```bash
uv run pytest -m "not integration" -v
```

Expected: all unit tests PASS.

- [ ] **Step 5: Run the complete real vertical slice**

With `EELWIZARD_EEL_CLI` set from Task 8:

```powershell
uv run eelwizard demo gain-slice --eel-cli $env:EELWIZARD_EEL_CLI --report reports/gain-slice.json
uv run pytest tests/integration/test_eel_vm_gain.py -v
```

Acceptance criteria:

- retrieval source is `SHIPPED/rootless-upstream`;
- initial `EEL001` is observed;
- repair leaves zero static errors;
- EEL_VM exits 0;
- measured gain is within `0.02 dB` of `-8.00 dB`;
- final status is exactly `MEASUREMENT_PASS`;
- `reports/gain-slice.json` contains the evidence above.

- [ ] **Step 6: Extend CI without faking EEL_VM**

Keep the existing Ubuntu/Windows unit-test matrix. Add a separate Windows integration job that attempts the real upstream EEL_VM bootstrap and runs only `tests/integration/test_eel_vm_gain.py`. If upstream toolchain incompatibility prevents a reliable hosted-runner build, leave the integration job disabled with a documented reason in README and require the local Windows integration command as the M0 gate; never replace it with a mock and call it integration.

- [ ] **Step 7: Update README with demonstrated capability only**

README may now claim:

```text
EELWizard can index the pinned upstream LiveProg corpus, retrieve a known-good gain implementation, diagnose and safely repair one conservative syntax defect, execute the repaired processor through upstream EEL_VM, and verify the measured default gain against the expected -8 dB behavior.
```

It must not yet claim autonomous DSP design, Asta research integration, broad EEL repair, full RootlessJamesDSP device compatibility, or EELVault release automation.

- [ ] **Step 8: Final verification and commit**

Run:

```bash
uv sync --frozen --dev
uv run pytest -m "not integration" -v
uv run pytest tests/integration/test_eel_vm_gain.py -v
git diff --check
git status --short
```

Expected: all unit tests and the real VM integration test pass; `git diff --check` is clean.

Commit:

```bash
git add src/eelwizard/vertical_slice.py src/eelwizard/cli.py tests/test_vertical_slice.py .github/workflows/ci.yml README.md
git commit -m "feat: prove EELWizard gain vertical slice"
```

---

## M0 / Vertical-Slice Completion Gate

Do not start Asta integration, LLM provider adapters, semantic embeddings, general DSP authoring, or EELVault packaging until all of these are true:

1. `uv sync --frozen --dev` succeeds from a fresh clone.
2. Unit tests pass on Python 3.11.
3. Rootless upstream corpus import at commit `60d25ae8a53c6f4691c090673df290a73c6b6357` yields exactly **40** `.eel` records.
4. `soloconsole.eel` is rejected from the upstream `SHIPPED` corpus path.
5. `gain spl0` retrieval returns upstream `gainControl` as a `SHIPPED/rootless-upstream` result.
6. The deliberately broken gain fixture produces `EEL001` and the conservative repair removes that error without changing line count.
7. The generated standalone program excludes LiveProg metadata/section markers and includes init once plus sample code per frame.
8. The pinned upstream EEL_VM executable actually runs the generated program.
9. Real EEL_VM output measures `-8.00 dB ± 0.02 dB` for the gain fixture.
10. Final report status is exactly `MEASUREMENT_PASS`.
11. No device, listening, research, EELVault-candidate, or release claim is made by this slice.
12. Working tree is clean after the final commit.

## What Comes After This Plan

Once this completion gate is green, write the next plan for the **M1 knowledge engine expansion**: full host/VM reference ingestion, host-profile feature matrices, supplemental EELVault indexing, richer technique extraction, and retrieval benchmarks. Asta research integration remains M4 work and should not be pulled forward merely because the plugin is available.
