# 02 — Architecture

> How the code is organised, how data flows through it, and the core types every milestone shares.
> Decisions referenced as `D-###` are in [01-decisions.md](01-decisions.md).
> **Beginner tip:** if a word here is new to you (AST, dataclass, entry point…), look it up in the [glossary](../learn/glossary.md) first.

---

## 1. The big picture

Every command follows the same five-step pipeline:

```
 ┌──────────┐   ┌──────────┐   ┌────────────┐   ┌───────────────┐   ┌────────────┐
 │ 1. CLI   │──▶│2. Config │──▶│ 3. Project │──▶│ 4. Analyzer   │──▶│ 5. Output  │
 │ argparse │   │ load +   │   │ discover   │   │ (graph, rules,│   │ text/json/ │
 │          │   │ validate │   │ files      │   │  tstring, …)  │   │ sarif/dot  │
 └──────────┘   └──────────┘   └────────────┘   └───────────────┘   └────────────┘
                                     │                  │
                                     ▼                  ▼
                               SourceFile(s)       Result = diagnostics
                              (parsed once,          + feature payload
                               shared by all)        (e.g. the graph)
```

1. **CLI** (`cartographer.cli`) turns `sys.argv` into a typed `Invocation` object. It does no analysis (D-031).
2. **Config** (`cartographer.core.config`) merges defaults, config files and flags into one frozen `Config` (D-015).
3. **Project** (`cartographer.core.project`) finds the root, the source roots and the files, and maps files to module names.
4. **Analyzer**: a feature package (`graph`, `startup`, `rules`, …) exposed through `cartographer.api`. It takes `(Project, Config)` and returns a `Result`.
5. **Output** (`cartographer.output`) renders the `Result` in the chosen format. The exit code is computed from the diagnostics (03 §3).

**The key design rule:** steps 2–4 never print anything and never call `sys.exit`. They return data or raise exceptions from `cartographer.core.errors`. That keeps them testable as plain functions.

## 2. Repository layout

```
Cartographer/
├── README.md                    # What it is, quick start, links into docs/
├── CLAUDE.md                    # Rules for AI implementers (read every session)
├── CHANGELOG.md                 # Keep a Changelog
├── LICENSE                      # MIT (D-012)
├── pyproject.toml               # Metadata, deps, tool configs (ruff, mypy, pytest)
├── uv.lock                      # Locked dev environment (committed)
├── .python-version              # "3.15" (uv uses this)
├── .gitattributes               # "* text=auto eol=lf"
├── .gitignore
├── .github/workflows/
│   ├── ci.yml                   # lint + type-check + tests (Win/Ubuntu × 3.13/3.14/3.15/3.15t)
│   ├── dogfood.yml              # C8: Cartographer runs on itself
│   └── release.yml              # C8: build + TestPyPI Trusted Publishing
├── src/cartographer/
│   ├── __init__.py              # __version__ + tiny lazy re-exports
│   ├── __about__.py             # __version__ = "0.0.1" (single source, D-010)
│   ├── __main__.py              # enables `python -m cartographer`
│   ├── api.py                   # PUBLIC library API (D-031)
│   ├── py.typed                 # marks the package as typed (PEP 561)
│   ├── core/                    # shared by every feature (M0)
│   │   ├── errors.py            # exception hierarchy (§6)
│   │   ├── config.py            # Config dataclasses, loading, validation
│   │   ├── files.py             # directory walking + include/exclude globs
│   │   ├── project.py           # Project: root, source roots, module index
│   │   ├── modnames.py          # path ⇄ dotted module name rules
│   │   ├── source.py            # SourceFile: decode, parse once, positions
│   │   ├── diagnostics.py       # Diagnostic, Location, Severity, Fix, Edit
│   │   ├── codes.py             # registry of all CRT codes (03 §6)
│   │   ├── result.py            # Result envelope returned by analyzers
│   │   ├── versions.py          # interpreter feature detection (D-004/D-005)
│   │   ├── selection.py         # select/ignore/per-file-ignores/severity (M0)
│   │   ├── qualnames.py         # qualified-name resolution of imports/aliases (C3, D-037)
│   │   ├── suppressions.py      # `# cartographer: ignore[...]` parsing via tokenize (C3)
│   │   ├── filtering.py         # full filtering pipeline = selection + suppressions (C3)
│   │   ├── edits.py             # apply Edit/Fix objects to text safely (C2, reused by C5)
│   │   └── log.py               # logging setup (-v / -q)
│   ├── output/                  # renderers (M0, extended per milestone)
│   │   ├── text.py  json.py  sarif.py  markdown.py
│   ├── cli/
│   │   ├── main.py              # root parser, global flags, dispatch, exit codes
│   │   ├── sections.py          # config-section registry: name -> "module:Class" (D-043)
│   │   ├── colour.py            # ANSI colour + Windows virtual-terminal enabling
│   │   └── commands/            # one module per subcommand
│   │       ├── scan.py explain.py rules.py               # M0 / C3
│   │       ├── graph.py startup.py check.py typecov.py
│   │       ├── tstring.py depdiff.py ci.py report.py
│   ├── graph/                   # C1
│   ├── startup/                 # C2
│   ├── rules/                   # C3 (engine + builtin rules + plugin loading)
│   ├── typecov/                 # C4 (named "typecov", NOT "typing": see note below)
│   ├── tstrings/                # C5 (finder, taint, codemod, sqllex.py, verifier/)
│   ├── adapters/                # C5 reference t-string processors (D-024), incl. _htmlctx.py state machine
│   ├── depdiff/                 # C6 (pypi, fetch, safe extract, manifests, provenance, sandbox)
│   ├── ci/                      # C7 (workflow model, YAML loader, expression scanner, rules)
│   └── report/                  # C8 combined report
├── tests/
│   ├── conftest.py              # shared fixtures, markers, golden-file helper
│   ├── unit/<package>/…         # mirrors src/cartographer/<package>/
│   ├── integration/             # CLI end-to-end via subprocess / main(argv)
│   ├── property/                # Hypothesis tests (or alongside unit tests; see 05)
│   ├── golden/                  # expected CLI outputs (05 §3.4)
│   ├── packaging/               # wheel/sdist content checks (C8)
│   └── fixtures/
│       ├── projects/<name>/     # tiny fake repos, each with README.md explaining it
│       ├── plugins/             # sample third-party rule plugin (C3); OUR code, imported by tests
│       ├── processors/          # good + deliberately broken t-string processors (C5); imported by tests
│       ├── typing_zoo/          # tricky typing snippets for the checker study (C4)
│       ├── annotations_runtime/ # PEP 649/749 runtime-annotation cases (C4)
│       ├── pypi/                # recorded PyPI API responses (C6)
│       └── replicas/ultralytics/# attack replica (C6, C7)
├── corpus/corpus.toml           # pinned real repos for acceptance (D-027)
├── acceptance/final/            # committed evidence of the C8 Final acceptance run
├── scripts/                     # dev.py, check_concepts.py, check_links.py, gen_synthetic_project.py,
│                                # fetch_corpus.py, corpus_startup.py (Docker only), checker_matrix.py
├── benchmarks/                  # performance budget checks (05 §6)
└── docs/
    ├── README.md                # doc map
    ├── research/                # the original research notes
    ├── spec/                    # THESE specs (00–08 + milestones/)
    ├── learn/                   # concept notes, glossary, FAQ, walkthroughs, comparisons, write-ups
    └── templates/               # templates for every recurring doc
```

> **Why `typecov`, not `typing`?** `cartographer.typing` wouldn't actually shadow the stdlib `typing` for absolute imports. It *would* confuse readers, tools and tracebacks, so we avoid it. The same reasoning rules out naming anything `ast`, `json`, `types`, `test`, `string`, `tokenize`, `inspect`, `select`, `signal`, `code` or `token`. (`code` is a real stdlib module, which is why the registry file is `codes.py`.)

## 3. Module dependency rules (layering)

To keep the code understandable, imports may only point **downwards**:

```
cli  ──▶  api  ──▶  report  ──▶  feature packages (graph, startup, rules, typecov, tstrings, depdiff, ci)
                         │
                         ▼
                 adapters, output   ──▶   core
```

- `core` imports nothing from Cartographer outside `core`.
- Feature packages may import `core` and **each other only through their public `__init__` exports**, and only where a milestone spec says so. The complete allowed list: `startup` → `graph` (C2 needs the resolver and `graph/usage.py`), `typecov` → `graph` (module ordering), `tstrings` → `rules` (C5 findings are C3 rules, D-038), `tstrings` → `adapters` (shared HTML-context state machine), `report` → every feature package (never `api`, D-049). Shared helpers (`qualnames`, `suppressions`, `filtering`, `edits`) live in `core` so that no other cross-feature imports are needed (D-037).
- Adding a cross-feature import means updating this list **and** the dogfood layer contract in C1 §6.9 in the same PR.
- `output` imports `core` only. Feature-specific renderers (for example DOT for graphs) live in the feature package and are registered with `output`.
- **C1 enforces this on Cartographer itself**: a test runs `cartographer graph` on `src/` and asserts there are no layering violations and no cycles. That's dogfooding.

## 4. Core data model

All core types are `@dataclass(frozen=True, slots=True)` unless stated otherwise. Frozen means immutable, so it is safe to share. (Types with a mapping field, like `Diagnostic.data`, are still **not hashable**, so don't put them in sets or use them as dict keys.) `slots` saves memory and catches typos in attribute names. Concept note: `docs/learn/concepts/dataclasses-and-enums.md` (M0).

### 4.1 `Severity`
```python
class Severity(enum.IntEnum):    # IntEnum so severities compare: ERROR > WARNING
    INFO = 10
    WARNING = 20
    ERROR = 30
```
SARIF mapping: INFO → `note`, WARNING → `warning`, ERROR → `error`.

### 4.2 `Location`
```python
@dataclass(frozen=True, slots=True)
class Location:
    path: str                 # posix, relative to project root, e.g. "pkg/mod.py"
    line: int                 # 1-based
    column: int               # 1-based, Unicode code points (D-018)
    end_line: int | None = None
    end_column: int | None = None   # exclusive, same units
```
For non-Python files (YAML in C7, archives in C6), `path` may point into an archive using the `!` convention: `dist/pkg-1.5.whl!pkg/__init__.py`. **One exception:** `startup pth` reports absolute paths, because `.pth` files live outside the project (D-045).

### 4.3 `Edit` and `Fix`
```python
@dataclass(frozen=True, slots=True)
class Edit:                    # replace text in [start, end) with `replacement`
    path: str
    start: tuple[int, int]     # (line, column), same units as Location
    end: tuple[int, int]
    replacement: str

@dataclass(frozen=True, slots=True)
class Fix:
    description: str           # human sentence: "Rewrite as t-string using adapters.sql.dbapi"
    edits: tuple[Edit, ...]
    safety: Literal["safe", "review"]   # "review" = semantics may change; never auto-applied
```

### 4.4 `Diagnostic`
```python
@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str                  # "CRT101"
    name: str                  # "import-cycle"
    severity: Severity
    message: str               # one line, no trailing period, e.g. "import cycle of 3 modules: a → b → c → a"
    location: Location
    help: str | None = None    # what to do about it, one or two sentences
    fix: Fix | None = None
    related: tuple[tuple[str, Location], ...] = ()   # (label, location) pairs, e.g. other edges in a cycle
    data: Mapping[str, JSONValue] = field(default_factory=dict)  # machine-readable extras, documented per code
```
**Ordering:** diagnostics sort by `(location.path, location.line, location.column, code)`, which gives deterministic output (D-017). `data` must be JSON-serialisable, so no custom objects go in it.

### 4.5 `SourceFile`
The single gateway to a Python file's contents (D-019, D-021).
```python
class SourceFile:              # not frozen: it lazily caches
    path: Path                 # absolute
    relpath: str               # posix, relative to root
    module: str | None         # dotted name if under a source root, else None
    @cached_property text: str              # decoded via tokenize.open
    @cached_property lines: list[str]
    @cached_property tree: ast.Module | None   # None if it failed; diagnostics recorded
    @cached_property parse_diagnostics: tuple[Diagnostic, ...]
    def location(self, node: ast.AST) -> Location      # handles byte→char conversion
    def segment(self, node: ast.AST) -> str            # exact source text of a node
```
`tree` is parsed with `ast.parse(text, filename=relpath, type_comments=True)`. If it raises `SyntaxError`, `tree` is `None` and `parse_diagnostics` contains `CRT001` (with the version hint from D-004, computed by `core.versions.syntax_hint(text)`).

### 4.6 `Project`
```python
@dataclass(frozen=True)
class Project:
    root: Path
    source_roots: tuple[Path, ...]        # where top-level packages live (C1 defines detection)
    files: tuple[SourceFile, ...]         # every included *.py / *.pyi, sorted by relpath
    config: Config
    def by_module(self, dotted: str) -> SourceFile | None
    def by_relpath(self, relpath: str) -> SourceFile | None
```
M0 implements discovery and a *basic* path→module mapping (`modnames.py`). C1 extends it with the full import-resolution rules (namespace packages, `.pyi` stubs, multiple roots).

### 4.7 `Result`
```python
@dataclass(frozen=True)
class Result(Generic[PayloadT]):
    command: str                          # "graph", "check", …
    diagnostics: tuple[Diagnostic, ...]   # sorted
    payload: PayloadT | None              # feature data, e.g. ImportGraph; must offer .to_json()
    stats: Mapping[str, int | float]      # files_analyzed, duration_s, …
```

### 4.8 JSON envelope
Every `--format json` output has exactly this top-level shape (schema version bumps on breaking change):
```json
{
  "schema": "cartographer.result/1",
  "tool": {"name": "cartographer", "version": "0.1.0"},
  "command": "graph",
  "root": ".",
  "diagnostics": [
    {"code": "CRT101", "name": "import-cycle", "severity": "warning",
     "message": "...", "location": {"path": "pkg/a.py", "line": 3, "column": 1,
     "end_line": 3, "end_column": 14}, "help": "...", "fix": null,
     "related": [], "data": {}}
  ],
  "payload": { },
  "stats": {"files_analyzed": 12},
  "meta": {"python": "3.15.2", "platform": "win32", "duration_s": 0.41}
}
```
`meta` is the **only** non-deterministic part. Golden tests strip it.

## 5. Extension points

| Extension point | Mechanism | Defined in |
|---|---|---|
| New rule | subclass `Rule`; registered automatically via `__init_subclass__` | C3 |
| Third-party rules | entry-point group **`cartographer.rules`** | C3 |
| New output format | register a renderer function in `output.registry` | M0 |
| New t-string sink | config `tstring.sinks` or a `SinkSpec` in code | C5 |
| New adapter | config `tstring.adapters.<kind> = "module:function"` | C5 |
| New CI rule | subclass `WorkflowRule` (same registry pattern as C3). No third-party entry point for CI rules in v1 | C7 |

## 6. Exceptions

```
CartographerError                 # base; never raised directly
├── UsageError                    # bad CLI usage             → exit 2
├── ConfigError                   # invalid config file/keys  → exit 2
├── ProjectError                  # root missing, no files    → exit 2
├── ToolEnvironmentError          # Docker/network/interpreter missing → exit 4
└── AnalysisError                 # analyzer cannot continue at all     → exit 3
```
Per-file problems are **never** exceptions that escape an analyzer. They become diagnostics (D-032). `ToolEnvironmentError` is deliberately not called `EnvironmentError`, because that name is a built-in alias of `OSError`.

## 7. Logging

- Use the stdlib `logging`, logger names `cartographer.<package>`, output to **stderr** (stdout is reserved for results, so `--format json > out.json` stays clean).
- `-q` → WARNING, default → WARNING, `-v` → INFO, `-vv` → DEBUG. `--debug` also implies full tracebacks.
- Never log file *contents*, which could be secrets from a target repo. Logging paths and counts is fine.

## 8. Performance shape

- One pass to discover files, then each file is parsed once (lazy `cached_property`). Analyzers walk the trees they need.
- Budgets and benchmarks: [05 §6](05-engineering-standards.md#6-performance-budgets).
