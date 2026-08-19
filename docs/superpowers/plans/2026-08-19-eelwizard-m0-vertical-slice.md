# EELWizard M0 + First Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `051-lab/EELWizard`, establish its typed/source-aware LiveProg foundation, and prove one real end-to-end path that retrieves upstream `gainControl.eel`, introduces and repairs one controlled syntax defect, executes the repaired processor through upstream EEL_VM, and measures its expected -8 dB gain.

**Architecture:** Python owns host/source metadata, LiveProg parsing, corpus indexing/retrieval, conservative lint/repair, orchestration, and audio measurement. Upstream EEL_VM remains a separately built GPL-2.0 executable invoked through subprocess; the Python package does not vendor, modify, or link EEL_VM in this slice. No LLM provider or Asta dependency is added until this deterministic path is proven.

**Tech Stack:** Python 3.11+, uv, Pydantic v2, Typer, NumPy, pytest, SQLite/FTS5, Git, GitHub Actions, PowerShell/MSBuild for EEL_VM.

**Spec:** `docs/superpowers/specs/2026-08-19-eelwizard-design.md`

## Global Constraints

- Python version floor: **3.11**.
- Upstream RootlessJamesDSP pin: `60d25ae8a53c6f4691c090673df290a73c6b6357`.
- Upstream EEL_VM pin: `284b3da00af91efc3aff6bfc1acefb4e801a8ad6`.
- Canonical gain source: `app/src/main/assets/Liveprog/gainControl.eel`, blob `b0df21b571311cfb7eebdff269b6d78dfdfdcd86`.
- Upstream factory corpus count at that RootlessJamesDSP pin: **40 `.eel` scripts**.
- `soloconsole.eel` is supplemental EELVault/project material and must never be classified as upstream `SHIPPED` content.
- Authority order: `HOST > VM > SHIPPED > VAULT > SPEC > RESEARCH > REFERENCE > INSPIRATION > ESTIMATE`.
- Initial host profiles: `rootless-upstream`, `rootless-051`, `eel-vm-core`, `jdsp-linux`.
- `VM_PASS` requires a successful execution by the real upstream EEL_VM executable.
- `MEASUREMENT_PASS` requires an objective measurement meeting its stated tolerance.
- Do not add model-provider SDKs, Asta, semantic embeddings, device automation, or EELVault release automation in this plan.
- Do not add a repository license in M0. The EELWizard distribution license is an explicit post-M0 decision after reviewing the external GPL-2.0 EEL_VM boundary.
- TDD is mandatory; each task ends in a commit only after its tests pass.

---

## File Map

```text
EELWizard/
├── .github/workflows/ci.yml
├── .gitignore
├── README.md
├── pyproject.toml
├── uv.lock
├── corpus/
│   ├── sources/
│   │   ├── rootless-upstream.json
│   │   └── eel-vm-core.json
│   └── generated/.gitkeep
├── docs/superpowers/
│   ├── specs/2026-08-19-eelwizard-design.md
│   └── plans/2026-08-19-eelwizard-m0-vertical-slice.md
├── scripts/bootstrap_eel_vm.ps1
├── src/eelwizard/
│   ├── __init__.py
│   ├── cli.py
│   ├── models.py
│   ├── corpus/
│   │   ├── __init__.py
│   │   ├── ingest.py
│   │   ├── liveprog.py
│   │   └── store.py
│   ├── eel/
│   │   ├── __init__.py
│   │   ├── lint.py
│   │   ├── repair.py
│   │   ├── standalone.py
│   │   └── runner.py
│   ├── lab/
│   │   ├── __init__.py
│   │   ├── measurements.py
│   │   └── signals.py
│   └── vertical_slice.py
└── tests/
    ├── fixtures/
    │   └── upstream_gainControl.eel
    ├── integration/test_eel_vm_gain.py
    ├── test_cli.py
    ├── test_models.py
    ├── test_liveprog.py
    ├── test_corpus.py
    ├── test_lint_repair.py
    ├── test_standalone.py
    ├── test_measurements.py
    └── test_vertical_slice.py
```

`corpus/generated/`, `.cache/`, and `reports/` are local/generated and ignored by Git. Source descriptors, tests, spec, and plan are version controlled.

---

### Task 1: Bootstrap the repository, package, and CI

**Files:**
- Create: `README.md`
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `src/eelwizard/__init__.py`
- Create: `src/eelwizard/cli.py`
- Create: `tests/test_cli.py`
- Create: `.github/workflows/ci.yml`
- Copy: approved spec and this plan into `docs/superpowers/`

**Interfaces:**
- Produces command `eelwizard` and package version `0.1.0`.

- [ ] **Step 1: Create and clone the repository**

```bash
gh repo create 051-lab/EELWizard --public --description "AI audio-DSP research engineer for RootlessJamesDSP LiveProg/EEL2" --clone
cd EELWizard
```

- [ ] **Step 2: Create the failing CLI test**

`tests/test_cli.py`:

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

Expected: FAIL because the package has not been created.

- [ ] **Step 3: Create `pyproject.toml`**

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
dev = ["pytest>=8.2"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
addopts = "-ra"
testpaths = ["tests"]
markers = ["integration: requires the real upstream EEL_VM executable"]
```

- [ ] **Step 4: Implement the minimum package**

`src/eelwizard/__init__.py`:

```python
__version__ = "0.1.0"
```

`src/eelwizard/cli.py`:

```python
import typer
from eelwizard import __version__

app = typer.Typer(no_args_is_help=True)


@app.command()
def version() -> None:
    typer.echo(f"EELWizard {__version__}")
```

- [ ] **Step 5: Create `.gitignore`**

```gitignore
.venv/
__pycache__/
.pytest_cache/
.cache/
reports/
corpus/generated/*
!corpus/generated/.gitkeep
*.pyc
```

- [ ] **Step 6: Create baseline CI**

`.github/workflows/ci.yml`:

```yaml
name: CI
on: [push, pull_request]

jobs:
  unit:
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

- [ ] **Step 7: Copy the approved spec and plan into the new repo**

Copy exactly:

```text
docs/superpowers/specs/2026-08-19-eelwizard-design.md
docs/superpowers/plans/2026-08-19-eelwizard-m0-vertical-slice.md
```

README must state that M0 is deterministic infrastructure and does not yet claim autonomous DSP design.

- [ ] **Step 8: Lock, test, and commit**

```bash
uv lock
uv sync --frozen --dev
uv run pytest tests/test_cli.py -v
uv run eelwizard version
git diff --check
git add .
git commit -m "chore: bootstrap EELWizard"
```

Expected: CLI prints `EELWizard 0.1.0` and test passes.

---

### Task 2: Define typed authority, host, claim, diagnostic, and state contracts

**Files:**
- Create: `src/eelwizard/models.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Produces: `SourceClass`, `HostProfile`, `ProjectStatus`, `DiagnosticSeverity`, `Diagnostic`, `Claim`, `LiveProgRecord`, `ProjectState`.

- [ ] **Step 1: Write failing model tests**

`tests/test_models.py`:

```python
from eelwizard.models import HostProfile, ProjectState, ProjectStatus, SourceClass


def test_authority_and_profiles_are_stable() -> None:
    assert SourceClass.HOST.rank == 1
    assert SourceClass.SHIPPED.rank == 3
    assert SourceClass.ESTIMATE.rank == 9
    assert HostProfile.ROOTLESS_UPSTREAM.value == "rootless-upstream"
    assert HostProfile.ROOTLESS_051.value == "rootless-051"


def test_project_state_round_trips() -> None:
    state = ProjectState(name="gain-slice", status=ProjectStatus.STATIC_PASS)
    assert ProjectState.model_validate_json(state.model_dump_json()) == state
```

Run and expect FAIL:

```bash
uv run pytest tests/test_models.py -v
```

- [ ] **Step 2: Implement `models.py`**

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
        return list(type(self)).index(self) + 1


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
    controls: list[str] = Field(default_factory=list)
    text: str = ""


class ProjectState(BaseModel):
    name: str
    status: ProjectStatus = ProjectStatus.DESIGN_ONLY
    claims: list[Claim] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
```

- [ ] **Step 3: Test and commit**

```bash
uv run pytest tests/test_models.py -v
git add src/eelwizard/models.py tests/test_models.py
git commit -m "feat: add EELWizard core contracts"
```

---

### Task 3: Parse and normalize RootlessJamesDSP LiveProg deterministically

**Files:**
- Create: `src/eelwizard/corpus/__init__.py`
- Create: `src/eelwizard/corpus/liveprog.py`
- Create: `tests/fixtures/upstream_gainControl.eel`
- Create: `tests/test_liveprog.py`

**Interfaces:**
- Produces: `ControlDefinition`, `LiveProgDocument`, `parse_liveprog(text)`, `normalize_liveprog(...)`.

- [ ] **Step 1: Add exact pinned gain fixture**

`tests/fixtures/upstream_gainControl.eel`:

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

```python
from pathlib import Path
from eelwizard.corpus.liveprog import normalize_liveprog, parse_liveprog
from eelwizard.models import HostProfile, SourceClass

FIXTURE = Path("tests/fixtures/upstream_gainControl.eel")


def test_parse_gain_control() -> None:
    doc = parse_liveprog(FIXTURE.read_text(encoding="utf-8"))
    assert doc.description == "Gain control"
    assert doc.tags == ["gain"]
    assert list(doc.sections) == ["init", "sample"]
    assert [c.name for c in doc.controls] == ["dB"]
    assert "gainLin = exp" in doc.sections["init"]


def test_normalize_gain_control() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    record = normalize_liveprog(
        name="gainControl",
        text=text,
        source_path="app/src/main/assets/Liveprog/gainControl.eel",
        source_class=SourceClass.SHIPPED,
        host_profile=HostProfile.ROOTLESS_UPSTREAM,
    )
    assert record.sections == ["init", "sample"]
    assert record.controls == ["dB"]
    assert record.host_variables == ["spl0", "spl1"]
    assert len(record.content_hash) == 64
```

- [ ] **Step 3: Implement complete parser and normalizer**

`src/eelwizard/corpus/liveprog.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re

from eelwizard.models import HostProfile, LiveProgRecord, SourceClass

SECTION_RE = re.compile(r"^@([A-Za-z_][A-Za-z0-9_]*)$")
CONTROL_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):([^<]+)<([^>]*)>(.*)$")
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
    description: str | None = None
    tags: list[str] = []
    controls: list[ControlDefinition] = []
    sections: dict[str, str] = {}
    current: str | None = None
    body: list[str] = []

    def flush() -> None:
        nonlocal body
        if current is not None:
            sections[current] = "\n".join(body).strip("\n")
        body = []

    for raw in text.splitlines():
        stripped = raw.strip()
        section_match = SECTION_RE.fullmatch(stripped)
        if section_match:
            flush()
            current = section_match.group(1)
            continue
        if current is not None:
            body.append(raw)
            continue
        if stripped.startswith("desc:"):
            description = stripped[5:].strip()
            continue
        if stripped.startswith("//tags:"):
            tags = [item for item in stripped[7:].strip().split() if item]
            continue
        control_match = CONTROL_RE.fullmatch(stripped)
        if control_match:
            controls.append(
                ControlDefinition(
                    name=control_match.group(1),
                    default=control_match.group(2).strip(),
                    range_spec=control_match.group(3).strip(),
                    description=control_match.group(4).strip(),
                )
            )
    flush()
    return LiveProgDocument(description=description, tags=tags, controls=controls, sections=sections)


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
        host_variables=[v for v in HOST_VARIABLES if re.search(rf"\b{re.escape(v)}\b", text)],
        controls=[c.name for c in doc.controls],
        text=text,
    )
```

- [ ] **Step 4: Test and commit**

```bash
uv run pytest tests/test_liveprog.py -v
git add src/eelwizard/corpus tests/fixtures/upstream_gainControl.eel tests/test_liveprog.py
git commit -m "feat: parse LiveProg structure"
```

---

### Task 4: Build and search the pinned upstream corpus

**Files:**
- Create: `corpus/sources/rootless-upstream.json`
- Create: `corpus/sources/eel-vm-core.json`
- Create: `corpus/generated/.gitkeep`
- Create: `src/eelwizard/corpus/ingest.py`
- Create: `src/eelwizard/corpus/store.py`
- Modify: `src/eelwizard/cli.py`
- Create: `tests/test_corpus.py`

**Interfaces:**
- Produces: `build_rootless_manifest`, `CorpusStore.rebuild`, `CorpusStore.search_liveprog`, CLI `corpus build-rootless`, `corpus index`, `corpus inspect`.

- [ ] **Step 1: Add pinned source descriptors**

`corpus/sources/rootless-upstream.json`:

```json
{"name":"RootlessJamesDSP upstream LiveProg","repository":"https://github.com/timschneeb/RootlessJamesDSP.git","commit":"60d25ae8a53c6f4691c090673df290a73c6b6357","path":"app/src/main/assets/Liveprog","source_class":"SHIPPED","host_profile":"rootless-upstream","expected_eel_count":40}
```

`corpus/sources/eel-vm-core.json`:

```json
{"name":"JamesDSP EEL_VM","repository":"https://github.com/james34602/EEL_VM.git","commit":"284b3da00af91efc3aff6bfc1acefb4e801a8ad6","source_class":"VM","host_profile":"eel-vm-core"}
```

- [ ] **Step 2: Write failing corpus tests**

```python
from pathlib import Path
import pytest
from eelwizard.corpus.ingest import CorpusCountError, build_rootless_manifest
from eelwizard.corpus.store import CorpusStore

FIXTURE = Path("tests/fixtures/upstream_gainControl.eel")


def test_wrong_upstream_count_fails(tmp_path: Path) -> None:
    src = tmp_path / "Liveprog"
    src.mkdir()
    (src / "gainControl.eel").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(CorpusCountError):
        build_rootless_manifest(src, tmp_path / "m.jsonl", expected_count=40)


def test_soloconsole_is_never_upstream_factory(tmp_path: Path) -> None:
    src = tmp_path / "Liveprog"
    src.mkdir()
    (src / "soloconsole.eel").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(CorpusCountError):
        build_rootless_manifest(src, tmp_path / "m.jsonl", expected_count=1)


def test_store_finds_shipped_gain(tmp_path: Path) -> None:
    src = tmp_path / "Liveprog"
    src.mkdir()
    (src / "gainControl.eel").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    records = build_rootless_manifest(src, tmp_path / "m.jsonl", expected_count=1)
    store = CorpusStore(tmp_path / "corpus.sqlite3")
    store.rebuild(records)
    hits = store.search_liveprog("gain spl0", limit=5)
    assert hits[0].record.name == "gainControl"
    assert hits[0].record.source_class.value == "SHIPPED"
```

- [ ] **Step 3: Implement `ingest.py`**

```python
from pathlib import Path
from eelwizard.corpus.liveprog import normalize_liveprog
from eelwizard.models import HostProfile, LiveProgRecord, SourceClass


class CorpusCountError(RuntimeError):
    pass


def build_rootless_manifest(source_dir: Path, output: Path, expected_count: int = 40) -> list[LiveProgRecord]:
    paths = sorted(source_dir.glob("*.eel"), key=lambda p: p.name.casefold())
    if any(p.name.casefold() == "soloconsole.eel" for p in paths):
        raise CorpusCountError("soloconsole.eel is supplemental project material, not upstream factory content")
    if len(paths) != expected_count:
        raise CorpusCountError(f"expected {expected_count} upstream .eel files, found {len(paths)}")
    records = [
        normalize_liveprog(
            name=p.stem,
            text=p.read_text(encoding="utf-8"),
            source_path=p.name,
            source_class=SourceClass.SHIPPED,
            host_profile=HostProfile.ROOTLESS_UPSTREAM,
        )
        for p in paths
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(r.model_dump_json() + "\n" for r in records), encoding="utf-8")
    return records
```

- [ ] **Step 4: Implement `store.py`**

```python
from dataclasses import dataclass
from pathlib import Path
import sqlite3
from eelwizard.models import LiveProgRecord


@dataclass(frozen=True)
class SearchHit:
    record: LiveProgRecord
    text_score: float
    authority_rank: int


class CorpusStore:
    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.path)

    def rebuild(self, records: list[LiveProgRecord]) -> None:
        with self._connect() as db:
            db.executescript("""
                DROP TABLE IF EXISTS records;
                DROP TABLE IF EXISTS records_fts;
                CREATE TABLE records (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE VIRTUAL TABLE records_fts USING fts5(name, text);
            """)
            for record in records:
                cur = db.execute(
                    "INSERT INTO records(name, payload_json) VALUES (?, ?)",
                    (record.name, record.model_dump_json()),
                )
                db.execute(
                    "INSERT INTO records_fts(rowid, name, text) VALUES (?, ?, ?)",
                    (cur.lastrowid, record.name, record.text),
                )

    def search_liveprog(self, query: str, limit: int = 5) -> list[SearchHit]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT r.payload_json, bm25(records_fts)
                FROM records_fts
                JOIN records r ON r.id = records_fts.rowid
                WHERE records_fts MATCH ?
                ORDER BY bm25(records_fts) ASC
                LIMIT ?
                """,
                (query, limit),
            ).fetchall()
        hits = [
            SearchHit(
                record=LiveProgRecord.model_validate_json(payload),
                text_score=float(score),
                authority_rank=LiveProgRecord.model_validate_json(payload).source_class.rank,
            )
            for payload, score in rows
        ]
        return sorted(hits, key=lambda h: (h.text_score, h.authority_rank))
```

- [ ] **Step 5: Add corpus CLI commands**

Extend `cli.py` with a `corpus` Typer group. `build-rootless SOURCE_DIR` writes `corpus/generated/rootless-upstream.jsonl`; `index` reads each JSON line into `LiveProgRecord` and rebuilds `corpus/generated/corpus.sqlite3`; `inspect QUERY` prints:

```text
[SHIPPED/rootless-upstream] gainControl — gainControl.eel
```

The command implementation must use `LiveProgRecord.model_validate_json(line)` and `CorpusStore` directly; no network access occurs inside these commands.

- [ ] **Step 6: Test locally and import the real 40-script pin**

```bash
uv run pytest tests/test_corpus.py -v
git clone https://github.com/timschneeb/RootlessJamesDSP.git .cache/rootless-upstream
git -C .cache/rootless-upstream checkout 60d25ae8a53c6f4691c090673df290a73c6b6357
uv run eelwizard corpus build-rootless .cache/rootless-upstream/app/src/main/assets/Liveprog
uv run eelwizard corpus index
uv run eelwizard corpus inspect "gain spl0"
```

Acceptance: import prints `Indexed 40 upstream LiveProg scripts`; inspection returns `gainControl` as `SHIPPED/rootless-upstream`.

- [ ] **Step 7: Commit**

```bash
git add corpus/sources corpus/generated/.gitkeep src/eelwizard/corpus src/eelwizard/cli.py tests/test_corpus.py
git commit -m "feat: index pinned Rootless LiveProg corpus"
```

---

### Task 5: Add conservative static lint and one safe repair

**Files:**
- Create: `src/eelwizard/eel/__init__.py`
- Create: `src/eelwizard/eel/lint.py`
- Create: `src/eelwizard/eel/repair.py`
- Create: `tests/test_lint_repair.py`

**Interfaces:**
- Produces: `lint_liveprog(text, profile)` and `apply_safe_repairs(text, diagnostics)`.

- [ ] **Step 1: Write failing lint/repair tests**

```python
from pathlib import Path
from eelwizard.eel.lint import lint_liveprog
from eelwizard.eel.repair import apply_safe_repairs
from eelwizard.models import HostProfile

GOOD = Path("tests/fixtures/upstream_gainControl.eel").read_text(encoding="utf-8")
BROKEN = GOOD.replace("spl0 = spl0 * gainLin;", "spl0 = spl0 * gainLin", 1)


def test_missing_semicolon_is_line_12() -> None:
    errors = [d for d in lint_liveprog(BROKEN, HostProfile.ROOTLESS_UPSTREAM) if d.severity.value == "error"]
    assert [(d.code, d.line) for d in errors] == [("EEL001", 12)]


def test_safe_repair_only_fixes_eel001() -> None:
    diagnostics = lint_liveprog(BROKEN, HostProfile.ROOTLESS_UPSTREAM)
    repaired = apply_safe_repairs(BROKEN, diagnostics)
    assert "spl0 = spl0 * gainLin;" in repaired
    assert len(repaired.splitlines()) == len(BROKEN.splitlines())
    assert not [d for d in lint_liveprog(repaired, HostProfile.ROOTLESS_UPSTREAM) if d.severity.value == "error"]
```

- [ ] **Step 2: Implement `lint.py`**

```python
import re
from eelwizard.corpus.liveprog import CONTROL_RE, parse_liveprog
from eelwizard.models import Diagnostic, DiagnosticSeverity, HostProfile

_STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"')


def _code_without_comment_or_string(line: str) -> str:
    code = line.split("//", 1)[0]
    return _STRING_RE.sub("", code)


def _looks_like_unterminated_assignment(stripped: str) -> bool:
    if not stripped or stripped.startswith(("//", "/*", "*", "@")):
        return False
    if CONTROL_RE.fullmatch(stripped):
        return False
    if any(op in stripped for op in ("==", "!=", "<=", ">=")):
        return False
    if "=" not in stripped or "?" in stripped:
        return False
    return not stripped.endswith((";", "(", ")", ":"))


def lint_liveprog(text: str, profile: HostProfile) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    doc = parse_liveprog(text)
    if "init" not in doc.sections:
        diagnostics.append(Diagnostic(code="HOST001", severity=DiagnosticSeverity.ERROR, message="missing @init"))
    if "sample" not in doc.sections:
        diagnostics.append(Diagnostic(code="HOST002", severity=DiagnosticSeverity.ERROR, message="missing @sample"))
    if profile is HostProfile.ROOTLESS_UPSTREAM:
        for section in ("slider", "block"):
            if section in doc.sections:
                diagnostics.append(Diagnostic(code="HOST003", severity=DiagnosticSeverity.WARNING, message=f"@{section} is not established as upstream-host truth in M0"))
    in_section = False
    for line_no, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith("@"):
            in_section = True
            continue
        code = _code_without_comment_or_string(raw)
        if "{" in code or "}" in code:
            diagnostics.append(Diagnostic(code="EEL010", severity=DiagnosticSeverity.ERROR, message="C-style braces are invalid for core EEL control blocks", line=line_no))
        if in_section and _looks_like_unterminated_assignment(stripped):
            diagnostics.append(Diagnostic(code="EEL001", severity=DiagnosticSeverity.ERROR, message="assignment-like statement is missing semicolon", line=line_no))
    return diagnostics
```

- [ ] **Step 3: Implement `repair.py`**

```python
from eelwizard.models import Diagnostic


def apply_safe_repairs(text: str, diagnostics: list[Diagnostic]) -> str:
    targets = {d.line for d in diagnostics if d.code == "EEL001" and d.line is not None}
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines, start=1):
        if index not in targets:
            continue
        ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        body = line[:-len(ending)] if ending else line
        lines[index - 1] = body + ";" + ending
    return "".join(lines)
```

- [ ] **Step 4: Test and commit**

```bash
uv run pytest tests/test_lint_repair.py -v
git add src/eelwizard/eel tests/test_lint_repair.py
git commit -m "feat: add conservative EEL lint and repair"
```

---

### Task 6: Generate standalone EEL and execute it through real upstream EEL_VM

**Files:**
- Create: `src/eelwizard/eel/standalone.py`
- Create: `src/eelwizard/eel/runner.py`
- Create: `scripts/bootstrap_eel_vm.ps1`
- Create: `tests/test_standalone.py`
- Create: `tests/integration/test_eel_vm_gain.py`
- Modify: `src/eelwizard/cli.py`

**Interfaces:**
- Produces: `build_standalone_program`, `EelVmRunner`, `EelVmRunResult`, CLI `doctor`.

- [ ] **Step 1: Write failing standalone test**

```python
from pathlib import Path
import numpy as np
from eelwizard.corpus.liveprog import parse_liveprog
from eelwizard.eel.standalone import build_standalone_program


def test_standalone_contains_only_vm_code() -> None:
    doc = parse_liveprog(Path("tests/fixtures/upstream_gainControl.eel").read_text(encoding="utf-8"))
    program = build_standalone_program(doc, np.array([0.25, -0.5, 1.0]), np.array([-0.25, 0.5, -1.0]), 48000.0)
    assert "desc:" not in program
    assert "@init" not in program
    assert "@sample" not in program
    assert program.count("gainLin = exp") == 1
    assert "loop(3," in program
    assert "__EELWIZARD__" in program
```

- [ ] **Step 2: Implement complete standalone generator**

`src/eelwizard/eel/standalone.py`:

```python
import math
import numpy as np
from eelwizard.corpus.liveprog import LiveProgDocument


def _aligned_region(length: int) -> int:
    base = max(16, length)
    return 1 << (base - 1).bit_length()


def build_standalone_program(document: LiveProgDocument, left: np.ndarray, right: np.ndarray, sample_rate: float) -> str:
    left = np.asarray(left, dtype=np.float64)
    right = np.asarray(right, dtype=np.float64)
    if left.ndim != 1 or right.ndim != 1 or len(left) != len(right):
        raise ValueError("left/right fixtures must be equal-length 1-D arrays")
    if len(left) > 8192:
        raise ValueError("CLI-backed M0 fixtures are limited to 8192 frames")
    if not math.isfinite(sample_rate) or sample_rate <= 0:
        raise ValueError("sample_rate must be finite and positive")
    if not np.all(np.isfinite(left)) or not np.all(np.isfinite(right)):
        raise ValueError("fixtures must contain only finite values")
    if "init" not in document.sections or "sample" not in document.sections:
        raise ValueError("LiveProg requires init and sample sections")

    right_base = _aligned_region(len(left))
    lines = [f"srate = {repr(float(sample_rate))};", "inL = 0;", f"inR = {right_base};"]
    for i, value in enumerate(left):
        lines.append(f"inL[{i}] = {repr(float(value))};")
    for i, value in enumerate(right):
        lines.append(f"inR[{i}] = {repr(float(value))};")
    lines.extend(["", document.sections["init"], "", "i = 0;", f"loop({len(left)},", "  spl0 = inL[i];", "  spl1 = inR[i];"])
    lines.extend("  " + line for line in document.sections["sample"].splitlines())
    lines.extend(['  printf("__EELWIZARD__ %.17g %.17g\\n", spl0, spl1);', "  i += 1;", ");", ""])
    return "\n".join(lines)
```

- [ ] **Step 3: Write integration test that only passes with a real executable**

`tests/integration/test_eel_vm_gain.py`:

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
    program = build_standalone_program(doc, left, -left, 48000.0)
    result = EelVmRunner(Path(exe)).run(program)
    expected = left * (10 ** (-8.0 / 20.0))
    np.testing.assert_allclose(result.left, expected, rtol=2e-6, atol=2e-7)
    np.testing.assert_allclose(result.right, -expected, rtol=2e-6, atol=2e-7)
    assert result.returncode == 0
```

- [ ] **Step 4: Implement the external runner**

`src/eelwizard/eel/runner.py`:

```python
from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
import numpy as np


class EelVmExecutionError(RuntimeError):
    pass


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
        if not self.executable.is_file():
            raise FileNotFoundError(self.executable)
        with tempfile.TemporaryDirectory(prefix="eelwizard-") as tmp:
            script = Path(tmp) / "fixture.eel"
            script.write_text(program, encoding="utf-8")
            completed = subprocess.run(
                [str(self.executable), str(script)],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        if completed.returncode != 0:
            raise EelVmExecutionError(f"EEL_VM exited {completed.returncode}: {completed.stderr or completed.stdout}")
        left: list[float] = []
        right: list[float] = []
        for raw in completed.stdout.splitlines():
            if not raw.startswith("__EELWIZARD__ "):
                continue
            parts = raw.split()
            if len(parts) != 3:
                raise EelVmExecutionError(f"malformed EELWizard output: {raw}")
            left.append(float(parts[1]))
            right.append(float(parts[2]))
        return EelVmRunResult(
            returncode=completed.returncode,
            left=np.asarray(left, dtype=np.float64),
            right=np.asarray(right, dtype=np.float64),
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
```

- [ ] **Step 5: Add reproducible Windows EEL_VM bootstrap**

`scripts/bootstrap_eel_vm.ps1`:

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

- [ ] **Step 6: Add `doctor` command and run real VM test**

`doctor --eel-cli PATH` must instantiate `EelVmRunner`, execute this exact core EEL program, and report success only if it returns two numeric values of `1`:

```eel
printf("__EELWIZARD__ 1 1\n");
```

Run from Visual Studio Developer PowerShell:

```powershell
$exe = ./scripts/bootstrap_eel_vm.ps1 | Select-Object -Last 1
$env:EELWIZARD_EEL_CLI = $exe
uv run eelwizard doctor --eel-cli $exe
uv run pytest tests/test_standalone.py tests/integration/test_eel_vm_gain.py -v
```

Task acceptance requires the integration test to PASS, not SKIP. If MSBuild fails, preserve the exact failure and fix only the bootstrap/toolchain invocation; do not patch EEL_VM source and do not use a mock to satisfy this gate.

- [ ] **Step 7: Commit**

```bash
git add src/eelwizard/eel src/eelwizard/cli.py scripts/bootstrap_eel_vm.ps1 tests/test_standalone.py tests/integration/test_eel_vm_gain.py
git commit -m "feat: execute LiveProg through upstream EEL_VM"
```

---

### Task 7: Add deterministic signal generation and gain measurement

**Files:**
- Create: `src/eelwizard/lab/__init__.py`
- Create: `src/eelwizard/lab/signals.py`
- Create: `src/eelwizard/lab/measurements.py`
- Create: `tests/test_measurements.py`

**Interfaces:**
- Produces: `stereo_sine` and `measure_gain_db`.

- [ ] **Step 1: Write failing tests**

```python
import numpy as np
from eelwizard.lab.measurements import measure_gain_db
from eelwizard.lab.signals import stereo_sine


def test_minus_8_db_measurement() -> None:
    left, right = stereo_sine(997.0, 48000.0, 0.1, 0.5)
    assert np.array_equal(left, right)
    processed = left * (10 ** (-8.0 / 20.0))
    assert abs(measure_gain_db(left, processed) + 8.0) < 1e-9


def test_silent_reference_is_rejected() -> None:
    with np.testing.assert_raises(ValueError):
        measure_gain_db(np.zeros(8), np.zeros(8))
```

- [ ] **Step 2: Implement exact functions**

`signals.py`:

```python
import math
import numpy as np


def stereo_sine(frequency: float, sample_rate: float, duration_seconds: float, amplitude: float) -> tuple[np.ndarray, np.ndarray]:
    frame_count = round(sample_rate * duration_seconds)
    time = np.arange(frame_count, dtype=np.float64) / sample_rate
    mono = amplitude * np.sin(2.0 * math.pi * frequency * time)
    return mono.copy(), mono.copy()
```

`measurements.py`:

```python
import math
import numpy as np


def measure_gain_db(reference: np.ndarray, processed: np.ndarray) -> float:
    reference = np.asarray(reference, dtype=np.float64)
    processed = np.asarray(processed, dtype=np.float64)
    if reference.shape != processed.shape:
        raise ValueError("reference and processed arrays must have equal shape")
    ref_rms = float(np.sqrt(np.mean(np.square(reference))))
    out_rms = float(np.sqrt(np.mean(np.square(processed))))
    if ref_rms == 0.0:
        raise ValueError("reference signal is silent")
    if out_rms == 0.0:
        return float("-inf")
    return 20.0 * math.log10(out_rms / ref_rms)
```

- [ ] **Step 3: Test and commit**

```bash
uv run pytest tests/test_measurements.py -v
git add src/eelwizard/lab tests/test_measurements.py
git commit -m "feat: add deterministic DSP measurements"
```

---

### Task 8: Prove the complete gain vertical slice and emit evidence

**Files:**
- Create: `src/eelwizard/vertical_slice.py`
- Create: `tests/test_vertical_slice.py`
- Modify: `src/eelwizard/cli.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`

**Interfaces:**
- Produces: `VerticalSliceReport`, `run_gain_vertical_slice(store, runner)`, CLI `demo gain-slice`.

- [ ] **Step 1: Write orchestration test with a fake runner only for unit state logic**

The fake runner is allowed only in this unit test; the final M0 gate still runs real EEL_VM.

```python
import numpy as np
from eelwizard.corpus.ingest import build_rootless_manifest
from eelwizard.corpus.store import CorpusStore
from eelwizard.eel.runner import EelVmRunResult
from eelwizard.models import ProjectStatus, SourceClass
from eelwizard.vertical_slice import run_gain_vertical_slice


class FakeRunner:
    def __init__(self, frame_count: int = 4800):
        time = np.arange(frame_count, dtype=np.float64) / 48000.0
        source = 0.5 * np.sin(2.0 * np.pi * 997.0 * time)
        self.output = source * (10 ** (-8.0 / 20.0))

    def run(self, program: str) -> EelVmRunResult:
        return EelVmRunResult(0, self.output, self.output, "", "")


def test_vertical_slice_reaches_measurement_pass(tmp_path) -> None:
    source = tmp_path / "Liveprog"
    source.mkdir()
    fixture = open("tests/fixtures/upstream_gainControl.eel", encoding="utf-8").read()
    (source / "gainControl.eel").write_text(fixture, encoding="utf-8")
    records = build_rootless_manifest(source, tmp_path / "m.jsonl", expected_count=1)
    store = CorpusStore(tmp_path / "corpus.sqlite3")
    store.rebuild(records)
    report = run_gain_vertical_slice(store, FakeRunner())
    assert report.source_name == "gainControl"
    assert report.retrieved_source_class is SourceClass.SHIPPED
    assert report.status is ProjectStatus.MEASUREMENT_PASS
    assert any(d.code == "EEL001" for d in report.diagnostics_before)
    assert not [d for d in report.diagnostics_after if d.severity.value == "error"]
    assert abs(report.measured_gain_db + 8.0) < 0.02
```

- [ ] **Step 2: Implement report and fail-closed orchestration**

`vertical_slice.py` must define:

```python
from pydantic import BaseModel
from eelwizard.corpus.liveprog import parse_liveprog
from eelwizard.corpus.store import CorpusStore
from eelwizard.eel.lint import lint_liveprog
from eelwizard.eel.repair import apply_safe_repairs
from eelwizard.eel.standalone import build_standalone_program
from eelwizard.lab.measurements import measure_gain_db
from eelwizard.lab.signals import stereo_sine
from eelwizard.models import Diagnostic, HostProfile, ProjectStatus, SourceClass


class VerticalSliceError(RuntimeError):
    pass


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


def run_gain_vertical_slice(store: CorpusStore, runner: object) -> VerticalSliceReport:
    hits = store.search_liveprog("gain spl0", limit=5)
    if not hits:
        raise VerticalSliceError("gainControl was not retrieved")
    hit = next((item for item in hits if item.record.name == "gainControl"), None)
    if hit is None or hit.record.source_class is not SourceClass.SHIPPED:
        raise VerticalSliceError("gainControl must come from SHIPPED upstream corpus")

    broken = hit.record.text.replace("spl0 = spl0 * gainLin;", "spl0 = spl0 * gainLin", 1)
    if broken == hit.record.text:
        raise VerticalSliceError("controlled defect could not be introduced")
    before = lint_liveprog(broken, HostProfile.ROOTLESS_UPSTREAM)
    repaired = apply_safe_repairs(broken, before)
    after = lint_liveprog(repaired, HostProfile.ROOTLESS_UPSTREAM)
    if [d for d in after if d.severity.value == "error"]:
        raise VerticalSliceError("static validation failed after safe repair")

    left, right = stereo_sine(997.0, 48000.0, 0.1, 0.5)
    program = build_standalone_program(parse_liveprog(repaired), left, right, 48000.0)
    result = runner.run(program)
    if result.returncode != 0:
        raise VerticalSliceError("EEL_VM execution failed")
    measured = measure_gain_db(left, result.left)
    expected = -8.0
    error = measured - expected
    if abs(error) > 0.02:
        raise VerticalSliceError(f"gain error {error:.6f} dB exceeds 0.02 dB")
    return VerticalSliceReport(
        source_name=hit.record.name,
        retrieved_source_class=hit.record.source_class,
        diagnostics_before=before,
        diagnostics_after=after,
        status=ProjectStatus.MEASUREMENT_PASS,
        measured_gain_db=measured,
        expected_gain_db=expected,
        gain_error_db=error,
        eel_vm_returncode=result.returncode,
    )
```

- [ ] **Step 3: Add real CLI command**

`eelwizard demo gain-slice --eel-cli PATH --report reports/gain-slice.json` must open `corpus/generated/corpus.sqlite3`, instantiate the real `EelVmRunner`, call `run_gain_vertical_slice`, write `report.model_dump_json(indent=2)`, and print:

```text
Source: gainControl [SHIPPED/rootless-upstream]
Static validation: PASS
EEL_VM execution: PASS
Measured gain: -8.00 dB
Expected gain: -8.00 dB
Final status: MEASUREMENT_PASS
```

- [ ] **Step 4: Add real Windows integration CI**

Append this job to `.github/workflows/ci.yml`:

```yaml
  eel-vm-integration:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          python-version: "3.11"
      - uses: microsoft/setup-msbuild@v2
      - run: uv sync --frozen --dev
      - shell: pwsh
        run: |
          $exe = ./scripts/bootstrap_eel_vm.ps1 | Select-Object -Last 1
          "EELWIZARD_EEL_CLI=$exe" | Out-File -FilePath $env:GITHUB_ENV -Encoding utf8 -Append
      - run: uv run pytest tests/integration/test_eel_vm_gain.py -v
```

This job must fail rather than silently skip if bootstrap succeeds but the environment variable or executable is invalid.

- [ ] **Step 5: Run all local gates with the real EEL_VM binary**

```powershell
$exe = ./scripts/bootstrap_eel_vm.ps1 | Select-Object -Last 1
$env:EELWIZARD_EEL_CLI = $exe
uv run eelwizard corpus build-rootless .cache/rootless-upstream/app/src/main/assets/Liveprog
uv run eelwizard corpus index
uv run pytest -m "not integration" -v
uv run pytest tests/integration/test_eel_vm_gain.py -v
uv run eelwizard demo gain-slice --eel-cli $exe --report reports/gain-slice.json
git diff --check
```

Acceptance: 40 upstream records; `gainControl` retrieval is `SHIPPED/rootless-upstream`; controlled defect yields `EEL001`; repair leaves zero static errors; real EEL_VM exits 0; measured gain is `-8.00 dB ± 0.02 dB`; report final status is `MEASUREMENT_PASS`.

- [ ] **Step 6: Update README with only demonstrated claims and commit**

README may claim only:

```text
EELWizard can index the pinned upstream LiveProg corpus, retrieve a known-good gain implementation, diagnose and safely repair one conservative syntax defect, execute the repaired processor through upstream EEL_VM, and verify the measured default gain against the expected -8 dB behavior.
```

It must not claim Asta integration, autonomous DSP invention, broad EEL repair, Android device validation, or EELVault release readiness.

```bash
git add .github/workflows/ci.yml README.md src/eelwizard/vertical_slice.py src/eelwizard/cli.py tests/test_vertical_slice.py
git commit -m "feat: prove EELWizard gain vertical slice"
```

---

## M0 Completion Gate

Do not begin M1/Asta/LLM work until all twelve checks are true:

1. Fresh clone: `uv sync --frozen --dev` succeeds.
2. Python 3.11 unit suite passes.
3. Pinned RootlessJamesDSP import yields exactly 40 upstream `.eel` records.
4. `soloconsole.eel` is rejected from the upstream corpus path.
5. `gain spl0` retrieves `gainControl` as `SHIPPED/rootless-upstream`.
6. Controlled missing-semicolon defect is reported as `EEL001` on line 12.
7. Safe repair removes that static error without changing line count.
8. Standalone EEL excludes LiveProg metadata/section markers and executes init once/sample per frame.
9. Pinned upstream EEL_VM actually executes the fixture.
10. Measured gain is `-8.00 dB ± 0.02 dB`.
11. Final report status is exactly `MEASUREMENT_PASS`.
12. Final working tree is clean.

## Next Plan

After M0 is green, create a separate M1 implementation plan for host/VM reference ingestion, host-profile feature matrices, all 40 upstream script technique manifests, supplemental EELVault indexing, and retrieval benchmarks. Asta remains an M4 research subsystem; do not pull it into M0/M1 merely because it is available.
