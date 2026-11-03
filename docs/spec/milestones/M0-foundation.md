# M0: Foundation

> **Size:** M · **Version at end:** `0.0.1` · **Depends on:** nothing · **Unblocks:** every other milestone
> **Spikes in this milestone:** S-00 (phase 1), S-10 (phase 3), S-04 (phase 4, report only)
> **Read first:** [00-overview](../00-overview.md), [01-decisions](../01-decisions.md), [02-architecture](../02-architecture.md), [03-cli-config-output](../03-cli-config-output.md), [04-documentation-standard](../04-documentation-standard.md), [05-engineering-standards](../05-engineering-standards.md)

---

## 1. Summary

M0 builds the **empty house that every later milestone moves into**. By the end there is an installable Python package called `cartographer-py` with two working commands: `cartographer --version` and `cartographer explain CODE`. There is also a small diagnostic command, `cartographer scan`. It finds every Python file in a project, decodes it, parses it, and reports files it can't read. Underneath sit the **core data model** (diagnostics, locations, results, configuration, projects, source files), the **output renderers** (text, JSON, SARIF), the **CLI shell** (global flags, exit codes, colour), the **test infrastructure** (pytest, Hypothesis, golden files), the **documentation checks** that enforce spec 04, and a **hardened CI workflow** that runs the whole lot on Windows and Ubuntu across Python 3.13, 3.14, 3.15 and 3.15t.

M0 has no real-world incident of its own. Its job is to make the later incident-driven milestones cheap to build and impossible to build sloppily.

## 2. Why this matters

Every analysis Cartographer will ever run has the same plumbing. It finds files, decodes them correctly, parses them, records findings with accurate positions, and prints them in a format a human or a machine can use. If that plumbing is wrong, every feature built on it is wrong in the same way. Two examples:

- **The column bug.** Python's `ast` module reports column positions as **UTF-8 byte offsets**, not character positions (D-018). Get this wrong once in the core, and every finding on a line containing `é` or `→` points to the wrong place: in the terminal, in the editor, and in GitHub code scanning.
- **The encoding bug.** A file that declares `# -*- coding: latin-1 -*-` must be decoded as Latin-1 (PEP 263). If you read it as UTF-8, the tool either crashes or silently sees garbage. On Windows with Python 3.13 or 3.14, the default encoding isn't even UTF-8 (PEP 686 only changes this in 3.15), so "works on my machine" bugs are easy to write.

M0 also sets up the **learning machinery**: the concept notes for all Stage 0 foundations, and the automated checks that stop any later PR from skipping documentation. Since you are learning from what gets written (D-001), these checks protect your learning as much as they protect code quality.

## 3. Read before starting

### 3.1 Concept notes
M0 **writes** all of Stage 0 (see §12). There's nothing earlier to read. Before starting, read:
- [`docs/learn/README.md`](../../learn/README.md): the curriculum map.
- [`docs/learn/faq.md`](../../learn/faq.md): the seeded beginner questions.
- [`docs/spec/06-environment-setup.md`](../06-environment-setup.md) steps 1–5: install uv and the four Pythons now.

### 3.2 Prediction questions
Write your answers in `docs/learn/predictions/M0.md` ([template](../../templates/prediction.md)) **before phase 1 starts**. Guesses are fine.

1. When you type `python -m cartographer --version`, which file in the package do you think Python runs first?
2. Does `ast.parse("print('hi')")` print `hi`? What do you think it returns?
3. On the line `name = "café"; x = 1`, at which column does `x` start if you count characters from 1? Do you think Python's `ast` will report the same number?
4. Name one way a test could pass on your Windows machine but fail on Linux CI.
5. What do you think happens if you try to change a field on a "frozen" dataclass?
6. A config file says `fail-on = 3` instead of `fail-on = "error"`. What should the tool do: guess, ignore it, or stop?
7. Should log messages ("parsing 12 files…") go to stdout or stderr? Why might it matter?
8. A linter finds problems. What exit code do you expect it to return, and why would a CI system care?
9. CI tests 2 operating systems × 4 Python versions. How many test jobs is that? Roughly how long do you think each takes?
10. Hypothesis "generates test inputs". How many inputs do you think it tries per test by default?
11. Why would a tool want both a human output format and a JSON one?

## 4. Scope

### 4.1 In scope
- Repository skeleton exactly as in [02 §2](../02-architecture.md#2-repository-layout), minus the feature packages (they arrive with their milestones).
- `pyproject.toml` with hatchling (D-033), ruff, mypy and pytest configuration, dependency groups and entry points.
- `core/`: `errors`, `diagnostics`, `codes`, `selection`, `result`, `log`, `versions`, `files`, `modnames` (basic rules), `source`, `project`, `config`.
- `output/`: registry + `text`, `json`, `sarif` renderers.
- `cli/`: root parser, global options, dispatch, exit codes, Windows colour, and the commands `explain` and `scan`. `--version` is a global flag.
- The full code registry from [03 §6](../03-cli-config-output.md#6-diagnostic-code-registry), with complete explanations for CRT001–CRT003.
- Scripts: `scripts/dev.py`, `scripts/check_concepts.py`, `scripts/check_links.py`, `scripts/gen_synthetic_project.py`.
- Tests: unit, property, integration, golden, and the documentation checks from [04 §8](../04-documentation-standard.md#8-doc-checks-that-run-in-ci-built-in-m0).
- `.github/workflows/ci.yml`, hardened per [05 §4](../05-engineering-standards.md#4-continuous-integration-githubworkflowsciyml-built-in-m0).
- All 18 Stage 0 concept notes, the M0 walkthrough and the M0 write-up.

### 4.2 Out of scope (and why)
| Not in M0 | Why | Where instead |
|---|---|---|
| Full source-root detection and import resolution | That *is* C1's subject. M0 only needs "which dotted name does this file have" | C1 §Source roots |
| Suppression comments (`# cartographer: ignore[...]`) | They belong with the rule engine. CRT004/CRT005 are registered but unimplemented | C3 |
| `cartographer.api` functions | No features exist yet. M0 creates `api.py` with only a docstring and `__all__ = []` | Each milestone |
| Runtime dependencies (LibCST, PyYAML) | Not needed until C5/C7 (D-006). S-04 checks them with a throwaway `uv run --with` | C5, C7 |
| Release workflow, TestPyPI | | C8 |
| Reference comparison | M0 rebuilds nothing that has a reference tool | — |

## 5. User-facing behaviour

All examples assume PowerShell in the repo root, after `uv sync`.

### 5.1 `--version`
```text
PS> uv run cartographer --version
cartographer 0.0.1 (Python 3.15.2, win32)
```
- Format: `cartographer {version} (Python {major}.{minor}.{micro}{build}, {sys.platform})`. `{build}` is empty for normal builds and `, free-threaded` for free-threaded builds (`sysconfig.get_config_var("Py_GIL_DISABLED") == 1`). Example: `cartographer 0.0.1 (Python 3.15.2, free-threaded, linux)`.
- Exit code 0. The output goes to **stdout**.
- `carto --version` and `python -m cartographer --version` print the same string.

### 5.2 `explain`
```text
PS> uv run cartographer explain CRT001
CRT001 syntax-error (default: warning)

What it means
  Cartographer could not parse this file as Python, so every analysis skips it.

Why it matters
  A file Cartographer can't parse is a blind spot: no imports, rules or
  injection checks are run on it. It is usually a genuine syntax error, but it can
  also mean the file uses syntax newer than the Python running Cartographer...

Example
  def broken(:
      pass

How to fix it
  ...

When it is OK to ignore
  ...

Learn more
  docs/learn/concepts/ast-basics.md, https://docs.python.org/3/library/ast.html
```
- Accepts a code (`CRT001`), a name (`syntax-error`), case-insensitively.
- For a code that is **registered but not implemented yet** (status "planned"):
  ```text
  PS> uv run cartographer explain CRT101
  CRT101 import-cycle (default: warning). Planned for milestone C1, not implemented yet.

  Modules form a cycle (an SCC with more than one module, or a self-loop).
  ```
  The second paragraph is the one-line summary from the registry. Exit code 0.
- Unknown code → stderr `cartographer: error: unknown diagnostic code "CRT99"; did you mean "CRT001"?` (suggestion from `difflib.get_close_matches` over all codes and names, cutoff 0.6. The suggestion clause is omitted if there's no match), exit code **2**.
- `cartographer explain --list` prints one line per registered code, sorted by code:
  ```text
  CRT001  syntax-error                  warning  M0  implemented
  CRT002  decode-error                  warning  M0  implemented
  CRT003  file-too-large                info     M0  implemented
  CRT004  invalid-suppression           warning  C3  planned
  ...
  ```
  Columns: code, name padded to 30, default severity padded to 8, milestone, status. A default-off code shows `info (off)` in the severity column, e.g. CRT005.

### 5.3 `scan`
`scan` is the M0 smoke-test command, and stays useful forever as a "what does Cartographer see?" debugging aid. It discovers files, decodes and parses each one, and reports CRT001–CRT003.

```text
PS> uv run cartographer scan tests/fixtures/projects/m0_errors
src/demo/bad_encoding.py:1:1: CRT002 [warning] cannot decode file: 'utf-8' codec can't decode byte 0xff in position 27: invalid start byte
  help: save the file as UTF-8, or correct its "# -*- coding: ... -*-" declaration (PEP 263)
src/demo/broken.py:2:12: CRT001 [warning] cannot parse: invalid syntax
  help: fix the syntax error; every Cartographer analysis skips this file until then
src/demo/nulls.py:1:1: CRT001 [warning] cannot parse: source code cannot contain null bytes
  help: fix the syntax error; every Cartographer analysis skips this file until then

Found 0 errors, 3 warnings, 0 info in 6 files (0.01 s).
```
(The positions and Python's own error text above are illustrative. The golden files in `tests/golden/scan/` are authoritative, §10.)

Options (on top of the global options in [03 §1.1](../03-cli-config-output.md#11-global-options-valid-before-or-after-the-command-name)):

| Option | Meaning |
|---|---|
| `--list-files` | After diagnostics, print every discovered file as `relpath  module-name` (module `-` if none), sorted by relpath |

Payload (`--format json`, field `payload`):
```json
{
  "files": [
    {"path": "src/demo/__init__.py", "module": "demo", "parsed": true},
    {"path": "src/demo/bad_encoding.py", "module": "demo.bad_encoding", "parsed": false},
    {"path": "src/my-script.py", "module": null, "parsed": true}
  ],
  "source_roots": ["src"]
}
```
`stats` for `m0_errors` on 3.15: `{"files_discovered": 6, "files_parsed": 3, "files_failed": 3, "files_skipped": 0}`. (The `payload` example above is illustrative and mixes files from `m0_errors` and `m0_golden`.) Definitions:
- **discovered**: files returned by the walker (§6.10).
- **parsed**: files whose `tree` is not `None`.
- **failed**: files that were read but produced CRT001 (unparseable) or CRT002 (undecodable).
- **skipped**: files never read because of CRT003 (too large).
- Invariant (tested in T-M0-13): `parsed + failed + skipped == discovered`. On 3.13/3.14, `future_syntax.py` also fails, so the counts there are 2 parsed / 4 failed.

### 5.4 Text-format summary line (normative, refines 03 §2.1)
`Found {E} {error|errors}, {W} {warning|warnings}, {I} info in {N} {file|files} ({seconds:.2f} s).`
- Singular when the count is exactly 1. `info` is invariant.
- It is printed even when there are no diagnostics: `Found 0 errors, 0 warnings, 0 info in 4 files (0.01 s).`
- `N` = number of files the command analysed (for `scan`: discovered files).

### 5.5 Exit codes
As in [03 §3](../03-cli-config-output.md#3-exit-codes). M0 implements all of them: 0, 1, 2, 3, 4 (no M0 code path raises `ToolEnvironmentError`, but the mapping and its test exist) and 130.

### 5.6 Errors as the user sees them
| Situation | Output (stderr) | Exit |
|---|---|---|
| Unknown flag | argparse usage + `cartographer: error: unrecognized arguments: --frobnicate` | 2 |
| No command | usage + `cartographer: error: the following arguments are required: command` | 2 |
| `PATH` doesn't exist | `cartographer: error: project root does not exist: C:\nope` | 2 |
| Bad config value | `cartographer: error: pyproject.toml: tool.cartographer.fail-on: expected one of "info", "warning", "error", "never", got 3` | 2 |
| Unknown config key | `cartographer: error: pyproject.toml: tool.cartographer: unknown key "fail_on"; did you mean "fail-on"?` | 2 |
| Bug (any other exception) | `cartographer: internal error: ZeroDivisionError: division by zero` + `This is a bug in Cartographer. Re-run with --debug for a full traceback.` | 3 |
| Ctrl+C | `Interrupted.` | 130 |

## 6. Design

### 6.1 Files created in M0
```
pyproject.toml  uv.lock  .python-version  .gitattributes  .gitignore  LICENSE  CHANGELOG.md
src/cartographer/__init__.py  __about__.py  __main__.py  api.py  py.typed
src/cartographer/core/__init__.py errors.py diagnostics.py codes.py selection.py result.py
                      log.py versions.py files.py modnames.py source.py project.py config.py
src/cartographer/output/__init__.py registry.py text.py json.py sarif.py
src/cartographer/cli/__init__.py main.py sections.py colour.py
src/cartographer/cli/commands/__init__.py explain.py scan.py
scripts/dev.py check_concepts.py check_links.py gen_synthetic_project.py
tests/conftest.py  src/conftest.py                       # src/conftest.py: doctest collection rules (D-055)
tests/unit/core/… tests/unit/output/… tests/unit/cli/…
tests/property/test_core_properties.py
tests/integration/test_cli_basics.py test_cli_scan.py
tests/docs/test_docstrings.py test_concept_examples.py test_fixture_readmes.py test_links.py test_concepts.py
tests/golden/scan/… tests/golden/explain/…
tests/fixtures/projects/m0_golden/… m0_errors/… m0_flat/…
benchmarks/bench_discover_parse.py
.github/workflows/ci.yml
docs/learn/concepts/<18 notes>.md
docs/learn/walkthroughs/M0.md  docs/learn/writeups/M0.md  docs/learn/spikes/S-00-*.md S-04-*.md S-10-*.md
```
`core/selection.py` (select/ignore/per-file-ignores logic) and `cli/sections.py` (the config-section registry, §6.9) refine the layout in 02 §2. `cli/colour.py` holds the Windows virtual-terminal code.

### 6.2 `pyproject.toml` (normative content; the implementer bumps lower bounds to current releases)
```toml
[build-system]
requires = ["hatchling>=1.27"]          # 1.27+ understands PEP 639 `license = "MIT"`; verify at implementation time
build-backend = "hatchling.build"

[project]
name = "cartographer-py"                # D-003
dynamic = ["version"]
description = "Maps unfamiliar Python codebases: imports, startup cost, rules, typing, injection risks, dependency and CI changes."
readme = "README.md"
requires-python = ">=3.13"              # D-004
license = "MIT"                         # D-012
license-files = ["LICENSE"]
authors = [{ name = "<owner name: confirm in the phase-1 PR>" }]
classifiers = [
  "Development Status :: 2 - Pre-Alpha",
  "Environment :: Console",
  "Programming Language :: Python :: 3.13",
  "Programming Language :: Python :: 3.14",
  "Programming Language :: Python :: 3.15",
  "Programming Language :: Python :: Free Threading :: 2 - Beta",
  "Topic :: Software Development :: Quality Assurance",
  "Typing :: Typed",
]
dependencies = []                       # libcst arrives in C5, PyYAML in C7 (D-006)

[project.scripts]
cartographer = "cartographer.cli.main:main"      # D-054: main(argv=None) -> int; the wrapper calls sys.exit(main())
carto = "cartographer.cli.main:main"

[project.urls]
Repository = "https://github.com/Kar6677thik/Cartographer"
Documentation = "https://github.com/Kar6677thik/Cartographer/tree/main/docs"

[dependency-groups]
dev = ["pytest>=8.3", "pytest-cov>=6", "hypothesis>=6.120", "ruff>=0.8", "mypy>=1.13", "networkx>=3.4",
       "jsonschema>=4.23"]                # jsonschema: SARIF schema validation in tests (D-006)

[tool.hatch.version]
path = "src/cartographer/__about__.py"

[tool.hatch.build.targets.wheel]
packages = ["src/cartographer"]

[tool.cartographer]                     # settings for analysing THIS repo (dogfooding, D-048)
exclude = ["tests/fixtures/**", ".corpus/**", "benchmarks/generated/**"]   # fixtures contain deliberate errors

[tool.ruff]
line-length = 100
target-version = "py313"
src = ["src", "tests", "scripts"]
extend-exclude = ["tests/fixtures"]     # fixtures are DATA, often deliberately broken
[tool.ruff.per-file-target-version]     # D-055: tests that contain 3.14+/3.15+ syntax
"tests/**/test_*_py314.py" = "py314"
"tests/**/test_*_py315.py" = "py315"     # if the installed ruff doesn't know "py315" yet, use the newest it knows
                                         # and record that in S-10 (verify the setting name at implementation time)

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "SIM", "RUF", "PL", "PT", "D"]
ignore = [
  "D105",     # magic-method docstrings: dunder methods are self-explanatory (04 §3.2 exempts them)
  "D107",     # __init__ docstrings: documented on the class instead
  "PLR0913",  # too many arguments: dataclass-style constructors legitimately have many
  "PLC0415",  # import-outside-top-level: deliberate lazy imports (§6.17 import discipline); added in phase 1
]
# Added in phase 1: ruff >= 0.17 also formats Python blocks inside Markdown; our docs align
# comments by hand and contain deliberately broken examples, so Markdown is excluded:
# [tool.ruff.format] exclude = ["*.md"]
[tool.ruff.lint.pydocstyle]
convention = "google"
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["D", "PLR2004"]           # tests: docstrings are checked by tests/docs instead; magic numbers are fine
"scripts/**" = ["T201"]                 # scripts print

[tool.mypy]
python_version = "3.15"                 # 05 §2: checks the 3.14+-gated modules too.
                                        # A second pass, `mypy --python-version 3.13 --exclude src/cartographer/adapters/`,
                                        # checks the 3.13 floor (scripts/dev.py types runs both; CI `types` job too)
strict = true
warn_unreachable = true
files = ["src", "scripts"]

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests", "src"]
addopts = [
  "-ra", "--strict-markers", "--strict-config",
  "--import-mode=importlib",
  "--doctest-modules",
  "-m", "not network and not docker and not corpus",
]
xfail_strict = true
filterwarnings = ["error"]              # a warning in our code is a bug; whitelist third-party ones explicitly
markers = [
  "slow: takes more than 2 s",
  "network: needs internet (opt in with -m network)",
  "docker: needs a Docker daemon (opt in with -m docker)",
  "corpus: needs .corpus/ cloned (opt in with -m corpus)",
  "execute: runs fixture code in a subprocess",
  "requires_py314: skipped on Python < 3.14",
  "requires_py315: skipped on Python < 3.15",
]

[tool.coverage.run]
branch = true
source = ["cartographer"]
[tool.coverage.report]
show_missing = true
exclude_also = ["if TYPE_CHECKING:", "raise NotImplementedError", "@overload"]
```
> **Doctests over `src/` (D-055):** `--doctest-modules` makes pytest import every module under `src/`. `src/conftest.py` therefore sets `collect_ignore_glob` so that `cartographer/adapters/*` is skipped on Python < 3.14 (those modules need `string.templatelib`) and `cartographer/depdiff/sandbox/*` is **always** skipped (container-only scripts, never imported on the host). In M0 neither package exists yet; the file and a test for it (T-M0-34) are created now so later milestones only add entries.

> **Gotcha to document in the walkthrough:** a later `-m` on the command line (`pytest -m docker`) **replaces** the `-m` in `addopts`, because argparse keeps the last value. That's how opt-in markers work.

Other root files:
- `.python-version`: `3.15`
- `.gitattributes`:
  ```
  * text=auto eol=lf
  *.png binary
  # Fixtures that MUST keep their exact bytes (encodings, BOMs, invalid bytes):
  tests/fixtures/projects/m0_errors/src/demo/bad_encoding.py -text
  tests/fixtures/projects/m0_golden/src/demo/latin.py -text
  tests/fixtures/projects/m0_golden/src/demo/bom.py -text
  ```
- `.gitignore`: patterns **anchored to the repo root** (`/build/`, `/dist/`, `/.venv/`, `/.corpus/`, `/.cartographer-cache/`) plus unanchored `__pycache__/`, `*.py[cod]`, `.coverage`, `htmlcov/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `.hypothesis/`. Anchoring matters: fixture projects deliberately contain `build/` directories to test default excludes, and an unanchored `build/` would stop git tracking them.
- `LICENSE`: MIT text, `Copyright (c) 2026 <owner name>`.
- `CHANGELOG.md`: Keep a Changelog header, an `## [Unreleased]` section, and `## [0.0.1]` at the end of M0.

### 6.3 Package entry files
- `__about__.py`: `__version__ = "0.0.1"` and nothing else, because hatch reads it as text.
- `__init__.py`: the module docstring, `from cartographer.__about__ import __version__`, and `__all__ = ["__version__"]`. Later milestones add lazy re-exports using a **module-level `__getattr__` (PEP 562)**, which works on 3.13 too. M0 documents that pattern in the docstring but doesn't use it yet.
- `__main__.py`: `from cartographer.cli.main import main` then `raise SystemExit(main())` (D-054). Its docstring explains what `python -m` does.
- `api.py`: docstring explaining D-031 and D-046, `__all__ = ["scan"]`, and the **single filtering point**:
  ```python
  SCOPES: Mapping[str, Scope] = {"scan": ("CRT001", "CRT002", "CRT003")}   # each milestone adds its commands (D-047)

  def scan(root: Path | str, *, config: Config | None = None,
           request: SelectionRequest | None = None) -> Result[ScanPayload]:
      """Discover and parse every file; report CRT001-CRT003 (the `scan` command)."""
      # load config/project if not given; sel = selection.resolve(request or request_from(config.core), scope=SCOPES["scan"])
      # collect file.parse_diagnostics for every file; build ScanPayload + stats
      return _finish(raw_result, sel)

  def _finish(result: Result[P], sel: Selection) -> Result[P]:
      """Filter diagnostics exactly once (D-046). From C3 on this calls core.filtering.apply_filters."""
      return dataclasses.replace(result, diagnostics=selection.apply(sel, result.diagnostics))
  ```
  **Rule:** every public `api` function resolves its selection (after any registration it depends on, such as C3 plugin loading) and calls `_finish` **exactly once**. Analyzers below `api` return raw diagnostics. `cli/main.py` never filters. `ScanPayload` (files + source roots, §5.3) is a small frozen dataclass defined in `api.py` itself, which keeps `core` free of command logic.

### 6.4 `core/errors.py`
Exactly the hierarchy in [02 §6](../02-architecture.md#6-exceptions). Every class has a docstring with an example message. Extra rules:
- `CartographerError.__init__(self, message: str, *, hint: str | None = None)`. The CLI prints `hint` on a second line as `  hint: …`.
- `ConfigError` carries `source: str` (file name) and `key_path: str` (`tool.cartographer.fail-on`), and its `str()` renders as in §5.6.
- `EXIT_CODES: Mapping[type[CartographerError], int]` lives here, so the mapping sits next to the classes and is tested in one place.

### 6.5 `core/diagnostics.py`
`Severity`, `Location`, `Edit`, `Fix`, `Diagnostic` exactly as in [02 §4.1–4.4](../02-architecture.md#4-core-data-model), plus:
```python
type JSONValue = None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]

def sort_key(d: Diagnostic) -> tuple[str, int, int, str]:
    """(path, line, column, code): the one ordering used everywhere (D-017)."""

def severity_from_str(text: str) -> Severity   # "warning" -> Severity.WARNING; ValueError otherwise
def to_json(d: Diagnostic) -> dict[str, JSONValue]  # the per-diagnostic object of 02 §4.8
```
- `Severity.__str__` returns the lowercase name (`"warning"`).
- `Diagnostic.__post_init__` validates cheaply: `code` matches `^CRT\d{3}$`, `line >= 1`, `column >= 1`, and `message` contains no newline and doesn't end with `.`. A violation raises `ValueError`, which is a programming error and therefore exit 3. That last rule enforces the 02 §4.4 message style.
- **`display_text(s: str) -> str`** (D-050): makes untrusted text safe for a message, help line or `Location.path`. It replaces every C0/C1 control character (including `\n`, `\r`, `\t`, `\x1b` escape sequences) and lone surrogates with `\xNN` / `\uNNNN` escapes, and escapes a trailing `.` or space as `\x2e` / `\x20` (so the message-style rule below can't be tripped by hostile input). It's idempotent on already-safe text, and `display_text(s) == s` for ordinary printable text. Every milestone that puts text from target files, archives, YAML or index JSON into a message must call it, and keep the raw value in `data`. Tested by T-M0-29.
- `data` is wrapped in `types.MappingProxyType` in `__post_init__` (using `object.__setattr__`, because the dataclass is frozen) so nobody can mutate it after creation. A CONCEPT comment explains both tricks.

### 6.6 `core/codes.py` (the registry)
```python
class CodeStatus(enum.Enum):
    IMPLEMENTED = "implemented"
    PLANNED = "planned"

@dataclass(frozen=True, slots=True)
class CodeInfo:
    code: str                  # "CRT001"
    name: str                  # "syntax-error"
    default_severity: Severity
    milestone: str             # "M0", "C1", ...
    summary: str               # the one-line "Meaning" text from 03 §6
    status: CodeStatus
    enabled_by_default: bool = True    # False only for CRT005 in the current table
    per_finding_severity: bool = False # True when the rule may choose severity per finding (D-041), e.g. CRT701
    explanation: str | None = None     # required when status is IMPLEMENTED (04 §5, D-044)

REGISTRY: Mapping[str, CodeInfo]       # every row of 03 §6, keyed by code (built-in codes only)
def get(code_or_name: str) -> CodeInfo | None   # case-insensitive, by code or name; includes external codes
def all_codes() -> tuple[CodeInfo, ...]          # built-in + external, sorted by code
def set_explanation(code: str, text: str) -> None
def register_external(info: CodeInfo) -> None    # third-party plugin codes (D-047), called by C3's rules/plugins.py
def _reset_external() -> None                    # tests only
```
- **Every** row of 03 §6 is registered in M0 with `status=PLANNED`, except CRT001–CRT003, which are `IMPLEMENTED` and carry full explanations. Each later milestone flips its codes to `IMPLEMENTED` and adds explanations.
- CRT701 has the default `"error/warning"` in 03 §6. Register it as `ERROR` with `per_finding_severity=True` (D-041); C7 downgrades it per occurrence.
- **`register_external(info)`** accepts only codes matching `^CRT9\d{2}$`, with `status=IMPLEMENTED` and a non-empty explanation. A code or name that already exists (built-in or external) → `ValueError` (C3 turns that into a plugin-load error, not a crash). External codes are stored in a separate dict, so `REGISTRY` stays exactly the 03 §6 table, but `get()` and `all_codes()` see both, which makes them selectable (`--select CRT901`) and gives SARIF its rule metadata.
- Explanations are module-level string constants (`_EXPLAIN_CRT001 = """…"""`) with the six headings from [04 §5](../04-documentation-standard.md#5-cartographer-explain-texts). Feature milestones may put explanations on rule classes instead and register them at import time through `codes.set_explanation(code, text)`. M0 provides that function.
- **Tests (T-M0-08):** (a) the registry matches the 03 §6 tables, parsed from the Markdown file itself, comparing code, name, default severity and milestone. Parsing rule for the **Default** cell: split on the first `,`. The part before it is the severity text; if that contains `/` (`error/warning`), the registered default is the part before `/` and `per_finding_severity` must be `True`. If the remainder contains `off by default` (`info, off by default`), `enabled_by_default` must be `False`. Any other cell shape fails the test with a message naming the row; (b) every `IMPLEMENTED` code has an explanation containing the six headings in order; (c) names are unique, kebab-case, and match `^[a-z][a-z0-9-]*$`.

### 6.7 `core/selection.py`
Turns `select`/`ignore`/`severity`/`per-file-ignores` into decisions. Resolution is split from application so that a command can resolve **after** registering extra codes (C3 plugins) but still filter **exactly once** (D-046, D-047).
```python
@dataclass(frozen=True, slots=True)
class Selector:
    text: str
    origin: Literal["cli", "config"]          # unknown selector -> UsageError (cli) or ConfigError (config)

@dataclass(frozen=True, slots=True)
class SelectionRequest:                      # UNRESOLVED; built by the CLI, carried by Invocation, passed to api
    select: tuple[Selector, ...]              # --select REPLACES config `select` (no merging)
    ignore: tuple[Selector, ...]              # --ignore REPLACES config `ignore`
    severity: Mapping[str, str]               # [tool.cartographer.severity]
    per_file: Mapping[str, tuple[str, ...]]   # [tool.cartographer.per-file-ignores]

type Scope = tuple[str, ...]                 # code selectors naming every code a command can produce

@dataclass(frozen=True, slots=True)
class Selection:                             # RESOLVED
    enabled: frozenset[str]                   # codes
    severity_overrides: Mapping[str, Severity]
    per_file_ignores: tuple[tuple[str, frozenset[str]], ...]   # (glob, codes), in config order

def request_from(core: CoreConfig, *, cli_select: Sequence[str] | None = None,
                 cli_ignore: Sequence[str] | None = None) -> SelectionRequest
def resolve(request: SelectionRequest, *, scope: Scope) -> Selection
def apply(selection: Selection, diagnostics: Iterable[Diagnostic]) -> tuple[Diagnostic, ...]
    # drop disabled codes and per-file-ignored ones, apply severity overrides, return sorted
```
**Effective selection (D-047):** `enabled = (match(select) ∩ match(scope)) − match(ignore)`, where `match` uses the selector semantics below against `codes.all_codes()` (built-in **and** external). `select` defaults to `("CRT",)`, so by default a command reports everything in its scope. Scopes are constants owned by `api` (`api.SCOPES`, one per command and sub-command); a scope selector that matches nothing is a programming error (assertion, caught by T-M0-30). M0 defines `scan = ("CRT001", "CRT002", "CRT003")`; every later milestone adds its commands' scopes as given in D-047 and its own spec.
**Selector semantics** (a selector is one string from `select`/`ignore`):
1. Matching is case-insensitive.
2. A selector equal to a code (`CRT303`) or a name (`mutable-default-argument`) matches that code **exactly**.
3. Otherwise a selector that is a prefix of codes (`CRT`, `CRT3`, `CRT30`) matches every code starting with it.
4. A selector matching nothing **in the whole registry** (built-in + external codes registered so far) raises `UsageError` (origin `cli`) or `ConfigError` (origin `config`), with a "did you mean" suggestion. It is *not* checked against the scope: `graph --select CRT301` is valid and simply reports nothing.
5. `enabled = (codes matched by select) − (codes matched by ignore)`. **Default-off codes** (`enabled_by_default=False`) are included only when selected **exactly** (rule 2), never by a prefix.
6. `planned` codes may be selected. They simply never fire.
7. `per-file-ignores` globs are matched against `Location.path` with `PurePosixPath.full_match` (3.13+). Ignore wins.
8. Severity overrides are applied **before** the exit-code calculation.

### 6.8 `core/result.py` and the exit code
`Result` as in [02 §4.7](../02-architecture.md#47-result). Plus:
```python
class SupportsJSON(Protocol):
    def to_json(self) -> JSONValue: ...

def exit_code_for(diagnostics: Sequence[Diagnostic], fail_on: str) -> int:
    """0 or 1 (03 §3). fail_on="never" -> always 0."""
```

### 6.9 `core/config.py` and `cli/sections.py`
**Core section dataclass** (TOML kebab-case keys ↔ snake_case fields, 03 §4.2):
```python
@dataclass(frozen=True, slots=True)
class CoreConfig:
    source_roots: tuple[str, ...] = ()
    include: tuple[str, ...] = ("**/*.py", "**/*.pyi")
    exclude: tuple[str, ...] = ()
    default_exclude: bool = True
    target_version: str = "auto"          # validated: "auto" or r"3\.\d+" with minor >= 13 (03 §4.3 clamps)
    select: tuple[str, ...] = ("CRT",)
    ignore: tuple[str, ...] = ()
    fail_on: Literal["info", "warning", "error", "never"] = "error"
    max_file_size_kb: int = 2048
    severity: Mapping[str, Literal["info", "warning", "error"]] = field(default_factory=dict)
    per_file_ignores: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

@dataclass(frozen=True)
class Config:
    core: CoreConfig
    sources: tuple[str, ...]              # files that contributed, for messages ("pyproject.toml")
    _sections: Mapping[str, object]       # validated feature-section instances, by table name
    def section[T](self, name: str, cls: type[T]) -> T   # returns the instance or cls() defaults
```
**Loading** (`load_config(root, *, explicit: Path | None, overrides: Mapping[str, object], section_types: Mapping[str, type]) -> Config`):
1. Pick the source per D-015: `--config FILE` (top-level keys) → `cartographer.toml` (top-level keys) → `pyproject.toml` `[tool.cartographer]` → defaults. `cartographer.toml` and `pyproject.toml` are **not merged** (03 §4.1). An INFO log names the file used.
2. Parse with `tomllib.load` (binary mode: `open(path, "rb")`, which `tomllib` requires). A TOML syntax error → `ConfigError` with the line/column from `tomllib.TOMLDecodeError` (fields `lineno`/`colno` exist on 3.14+; on 3.13, take them from the message text; S-10 doesn't cover this, so the implementer checks it and comments).
3. Split the table into core keys and **sub-tables**. A sub-table name must be in `section_types`, else `ConfigError: unknown section "grpah"; did you mean "graph"?`. The two core sub-tables `severity` and `per-file-ignores` are core fields, not sections.
4. Validate each table against its dataclass (`_validate(table, cls, key_path)`):
   - Use `typing.get_type_hints(cls)` with `get_origin`/`get_args`. Supported field types: `str`, `int`, `float`, `bool`, `Literal[...]`, `tuple[X, ...]` (from a TOML array), `Mapping[str, X]` (from a TOML table), and nested frozen dataclasses (from a table or an array of tables, used by C1 contracts).
   - **`bool` is not accepted where `int` is expected**, even though `True` is an `int` subclass in Python. **`int` is accepted where `float` is expected.** Both rules get CONCEPT comments.
   - Unknown keys → `ConfigError` with the `difflib` suggestion. The candidates are the kebab-case field names.
5. Apply CLI `overrides` (e.g. `fail_on` from `--fail-on`) last, with `dataclasses.replace`.
6. `target-version = "auto"` is resolved here (03 §4.3) into a concrete `"3.N"` string stored in `CoreConfig.target_version`. The `requires-python` mini-parser lives in `core/versions.py` (§6.12).

**Why `section_types` is a parameter:** `core` must not import feature packages (02 §3). The CLI owns the mapping (`cli/sections.py`):
```python
SECTION_TYPES: Mapping[str, str] = {
    # table name -> "module:Class"; each milestone adds its own line.
    # Feature config modules (<feature>/config.py) must stay import-light: dataclasses/typing only.
}
def resolve_section_types(names: Iterable[str]) -> Mapping[str, type]   # imports only what's needed
```
This is **dependency injection**: the caller hands `core` what it needs instead of `core` reaching upward. In M0 the mapping is empty. A concept-note section in `config-with-tomllib` explains the pattern.

### 6.10 `core/files.py`: discovery
```python
DEFAULT_EXCLUDED_DIR_NAMES: frozenset[str] = frozenset({
    ".git", ".hg", ".svn", ".venv", "venv", "env", ".tox", ".nox", "__pycache__",
    "build", "dist", "node_modules", ".mypy_cache", ".ruff_cache", ".pytest_cache",
    ".cartographer-cache", "site-packages", ".corpus",
})
DEFAULT_EXCLUDED_DIR_GLOBS: tuple[str, ...] = ("*.egg-info",)

@dataclass(frozen=True, slots=True)
class DiscoveredFile:
    path: Path          # absolute
    relpath: str        # posix, relative to root
    size: int           # bytes

def discover(root: Path, include: Sequence[str], exclude: Sequence[str],
             default_exclude: bool) -> tuple[DiscoveredFile, ...]
```
Algorithm (iterative, using an explicit stack of directories so deep trees can't hit the recursion limit):
```
stack = [root]
while stack:
    d = stack.pop()
    for entry in sorted(os.scandir(d), key=name):          # sorted => deterministic
        rel = posix relpath(entry, root)
        if entry.is_symlink() or entry.is_junction(): skip (DEBUG log)   # never follow links (D-020)
        if entry.is_dir(follow_symlinks=False):
            if default_exclude and (entry.name in DEFAULT_EXCLUDED_DIR_NAMES
                                    or fnmatch(entry.name, any DEFAULT_EXCLUDED_DIR_GLOBS)): continue
            if dir_excluded(rel, exclude): continue
            stack.append(entry.path)
        elif entry.is_file(follow_symlinks=False):
            if matches(rel, include) and not matches(rel, exclude): yield DiscoveredFile(...)
result sorted by relpath
```
- `matches(rel, patterns)` = any `PurePosixPath(rel).full_match(p)`. `PurePath.full_match` is new in 3.13 and supports `**` (zero or more directories), so `**/*.py` also matches the top-level `a.py`. The phase-3 tests pin this.
- `dir_excluded(rel, patterns)`: true if `full_match(rel, p)`, or if `p` ends with `/**` and `full_match(rel, p[:-3])`. So `generated/**` prunes the directory `generated` without walking it.
- A missing root → `ProjectError`. A root that is a file → `ProjectError("project root must be a directory: …")`.
- Permission errors on a subdirectory: WARNING log, skip it, continue.
- Case sensitivity: patterns are matched case-sensitively on every OS (documented). Windows paths are case-insensitive, but our relpaths come from the filesystem's own spelling, so matching stays predictable.

### 6.11 `core/modnames.py` (basic; C1 extends)
```python
def module_name(relpath: str, source_roots: Sequence[str]) -> str | None
def default_source_roots(root: Path) -> tuple[str, ...]   # M0 rule: ("src",) if root/"src" is a dir, else (".",)
```
Rules for `module_name`:
1. Find the **first** source root (in the given order) that is a prefix of `relpath`. `"."` matches everything. None found → `None`.
2. Strip the root prefix, then strip the `.py` or `.pyi` suffix.
3. If the last part is `__init__`, drop it (the package itself). An `__init__.py` directly in a source root has no package → `None`.
4. Every remaining part must satisfy `part.isidentifier() and not keyword.iskeyword(part)`. Otherwise → `None` (e.g. `my-script.py`, `2fast.py`, `class.py`).
5. Join with `.`.

Examples (doctests): `("src/demo/core.py", ["src"]) → "demo.core"`, `("src/demo/__init__.py", ["src"]) → "demo"`, `("src/my-script.py", ["src"]) → None`, `("tests/test_x.py", ["src"]) → None`, `("pkg/mod.pyi", ["."]) → "pkg.mod"`.

### 6.12 `core/versions.py`
```python
RUNNING: tuple[int, int] = sys.version_info[:2]
FREE_THREADED: bool = sysconfig.get_config_var("Py_GIL_DISABLED") == 1
HAS_TEMPLATELIB: bool = RUNNING >= (3, 14)

def python_description() -> str           # "3.15.2" or "3.15.2, free-threaded" (for --version)
def lowest_from_requires_python(spec: str) -> tuple[int, int] | None   # 03 §4.3 mini-parser
def resolve_target_version(value: str, requires_python: str | None) -> str
def syntax_hint(text: str) -> str | None  # D-004 hint; see below
```
**`lowest_from_requires_python`** handles comma-separated clauses with the operators `>=`, `>`, `==`, `~=`, `!=` and `<`/`<=`. Lower bounds come from `>=X.Y`, `~=X.Y` and `==X.Y.*`. `>X.Y` → `(X, Y+1)`, which is a simplification documented in the docstring. `!=`, `<` and `<=` don't contribute lower bounds. It returns the **largest** lower bound across clauses (`>=3.10,>=3.12` → 3.12). If there's no lower bound, or a clause it can't parse, it returns `None`. A concept-note section explains PEP 440 specifiers.

**`syntax_hint(text)`** is *Provisional (S-10)*. It is called only when `ast.parse` fails. It tokenizes the text with `tokenize.generate_tokens`, stopping at the first tokenize error, and looks for newer-syntax fingerprints that the **running** interpreter doesn't support:

| Fingerprint (token-level) | Feature | Min version |
|---|---|---|
| A `NAME` token among `t, T, tr, rt, Tr, tR, Rt, rT, TR, RT` immediately followed by a `STRING`/`FSTRING_START` token with no gap (`prev.end == next.start`) | t-string (PEP 750) | 3.14 |
| `NAME 'lazy'` as the first token of a logical line, followed by `NAME 'import'` or `NAME 'from'` | lazy import (PEP 810) | 3.15 |
| `NAME 'except'` followed by an expression containing a top-level `,` before `:`, with no `as` and no surrounding parentheses | unparenthesised `except A, B:` (PEP 758) | 3.14 |

On 3.14+, Python's own tokenizer already produces `TSTRING_START` tokens, so the first fingerprint only matters on 3.13. S-10 records the exact token streams on each version, and the table is adjusted to match. Return format: `"this file may use Python 3.15 syntax (lazy import); run Cartographer under Python 3.15 to analyse it"`. For several fingerprints, name the **highest** version and list the features comma-separated. Return `None` when nothing matches.

### 6.13 `core/source.py`: `SourceFile`
As in [02 §4.5](../02-architecture.md#45-sourcefile), with these precise rules:
- **Constructor:** `SourceFile(path: Path, relpath: str, module: str | None, size: int, max_size: int)`.
- **`text`** (`cached_property`): if `size > max_size` → `""`, and `parse_diagnostics` holds CRT003. Otherwise `with tokenize.open(path) as f: f.read()`. `tokenize.open` detects the PEP 263 cookie and a UTF-8 BOM, and its text wrapper uses **universal newlines**, so `\r\n` and `\r` become `\n`. `UnicodeDecodeError` or `SyntaxError` (raised by `tokenize.open` for an unknown or invalid cookie encoding) → `""` + CRT002.
- **`lines`**: `self.text.split("\n")`. **Not `splitlines()`**: `str.splitlines()` also splits on `\x0b`, `\x0c`, `\x1c`, `\x1d`, `\x1e`, `\x85`, `\u2028` and `\u2029`, but Python's parser counts only `\n`. Using `splitlines` shifts line numbers in files that contain a form feed (`\x0c`), which is common in old GNU-style code. This gets a CONCEPT(text-and-encodings) comment and a dedicated test (T-M0-12).
- **`tree`**: `ast.parse(text, filename=relpath, type_comments=True)` inside `try`. `except (SyntaxError, ValueError)` → `None` + CRT001. `ValueError` covers "source code string cannot contain null bytes" on versions that raise it. A `RecursionError` from absurdly nested code also → CRT001, with message `cannot parse: nesting too deep` (a test generates `"(" * 10_000`).
- **`parse_diagnostics`**: the tuple of CRT001/002/003 (at most one) for this file. Accessing it forces `tree`.
- **`location(node)`**: converts `(lineno, col_offset, end_lineno, end_col_offset)` to a 1-based character `Location`:
  ```python
  def _char_col(line: str, byte_offset: int) -> int:
      # CONCEPT(text-and-encodings): ast offsets count UTF-8 *bytes* of the line.
      return len(line.encode("utf-8")[:byte_offset].decode("utf-8", errors="replace"))
  column = _char_col(lines[lineno - 1], col_offset) + 1
  ```
  Nodes without positions (e.g. `ast.Module`) → `Location(relpath, 1, 1)`. If `end_*` is missing → `None`. Positions that fall outside the file's lines are clamped to the last line, and that's covered by a test.
- **`segment(node)`**: `ast.get_source_segment(self.text, node)` or `""`.
- **CRT001 location and message:** line = `SyntaxError.lineno or 1`, column = `SyntaxError.offset or 1`. On Python 3.10+ this is already 1-based and counted in characters for `str` input; S-10 confirms it on all four versions. The message is `cannot parse: {err.msg}`, with `; {hint}` appended when `syntax_hint` returns something. `data = {"python_message": err.msg, "hint_version": "3.15" | None}`.
- **CRT002**: location 1:1, message `cannot decode file: {exc}`, help as in §5.3, `data = {"error": type(exc).__name__}`.
- **CRT003**: location 1:1, message `file skipped: {size_kb} KB is larger than max-file-size-kb ({limit})`, `data = {"size_bytes": n, "limit_kb": k}`.

### 6.14 `core/project.py`
```python
def load_project(root: Path, config: Config) -> Project
```
1. `root = root.resolve()`. Must be a directory (`ProjectError`).
2. Source roots: `config.core.source_roots` if non-empty (each must exist under the root, else `ConfigError`), otherwise `modnames.default_source_roots(root)`. C1 replaces this default with full detection.
3. `files.discover(...)` → build a `SourceFile` per file, with `module_name(...)`.
4. If no files are found: return an empty project (not an error). `scan` prints `Found 0 errors, 0 warnings, 0 info in 0 files (…)`. **This is the rule for every command:** an empty project gives an empty result and exit 0, never `ProjectError` (C8's `report` included).
5. Duplicate module names (e.g. `pkg/mod.py` and `pkg/mod.pyi`): both files keep the name. `by_module` prefers `.py` over `.pyi`, then the earlier source root. Documented and tested.

### 6.15 `core/log.py`
`configure(verbosity: int, debug: bool) -> None`. It sets up the `cartographer` logger with a `StreamHandler(sys.stderr)` and the format `cartographer: {levelname.lower()}: {message}`. Verbosity mapping as in [02 §7](../02-architecture.md#7-logging). It's idempotent: calling it twice must not add two handlers, which is a classic bug that gets a test.

### 6.16 `output/`
```python
@dataclass(frozen=True, slots=True)
class RenderOptions:
    colour: bool
    root: Path
    tool_version: str

type Renderer = Callable[[Result[Any], RenderOptions], str]
def register(fmt: str, renderer: Renderer, *, commands: frozenset[str] | None = None) -> None
def render(fmt: str, result: Result[Any], options: RenderOptions) -> str   # UsageError if fmt not allowed for result.command
def formats_for(command: str) -> tuple[str, ...]                           # used by argparse `choices`
```
- **text**: layout per [03 §2.1](../03-cli-config-output.md#21-text-format-layout-normative) plus the summary line in §5.4. Colour (when `options.colour`): severity word red/yellow/cyan using SGR codes `31`/`33`/`36`, code bold (`1`), reset `0`. Commands may register **text hooks** with `output.text.register_hooks(command, *, before=None, after=None, footer=None)`; each hook is `Callable[[Result[Any], RenderOptions], str]`. The text layout is, in order: `before` block → diagnostics → `after` block → summary line → `footer` block. Empty blocks are omitted; non-empty blocks are separated by exactly one blank line. `scan --list-files` uses `after`. Later uses: C2 tables (`after`), C4 coverage table (`before`), C6 header (`before`) and `Note:` lines (`footer`). Tested by T-M0-33.
- **json**: the envelope in [02 §4.8](../02-architecture.md#48-json-envelope), `json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False)` + `"\n"`. Key order is the order in 02 §4.8 (insertion order, which is deterministic). `meta.duration_s` rounded to 3 decimals.
- **sarif**: SARIF 2.1.0:
  ```json
  {
    "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
    "version": "2.1.0",
    "runs": [{
      "tool": {"driver": {
        "name": "cartographer", "version": "0.0.1",
        "informationUri": "https://github.com/Kar6677thik/Cartographer",
        "rules": [{"id": "CRT001", "name": "syntax-error",
                   "shortDescription": {"text": "<summary>"},
                   "fullDescription": {"text": "<'What it means' paragraph>"},
                   "defaultConfiguration": {"level": "warning"},
                   "helpUri": "https://github.com/Kar6677thik/Cartographer/blob/main/docs/spec/03-cli-config-output.md#6-diagnostic-code-registry"}]
      }},
      "columnKind": "unicodeCodePoints",
      "originalUriBaseIds": {"SRCROOT": {"uri": "file:///C:/path/to/root/"}},
      "results": [{
        "ruleId": "CRT001", "ruleIndex": 0, "level": "warning",
        "message": {"text": "<message>"},
        "locations": [{"physicalLocation": {
          "artifactLocation": {"uri": "src/demo/broken.py", "uriBaseId": "SRCROOT"},
          "region": {"startLine": 2, "startColumn": 12, "endLine": 2, "endColumn": 13}}}],
        "relatedLocations": [],
        "properties": {"name": "syntax-error", "help": "<help>", "data": {}}
      }]
    }]
  }
  ```
  `rules` contains only codes that appear in `results`, sorted by code, and `ruleIndex` points into that array. `SRCROOT` comes from `Path.as_uri()` plus a trailing `/`. Paths are URI-escaped with `urllib.parse.quote` (spaces → `%20`, which matters because the owner's home folder contains a space). Fixes are omitted in M0 and added when the first `Fix` exists (C2). Rule metadata is looked up with `codes.get`, so external plugin codes (CRT9xx, D-047) get proper `rules` entries too.
  - **Schema validation test** (T-M0-17): a vendored copy of the SARIF 2.1.0 schema in `tests/fixtures/schemas/sarif-2.1.0.json`, validated with `jsonschema` (a dev-only dependency, already listed in D-006).

### 6.17 `cli/main.py`
```python
def main(argv: Sequence[str] | None = None) -> int     # never calls sys.exit: testable. Console-script target (D-054)
```
**Parser construction:**
- A `global_options` parent parser holds every option from 03 §1.1. Each subparser is created with `parents=[global_options_suppressed]`, a second copy whose defaults are all `argparse.SUPPRESS`. This is the standard trick that lets global options appear **before or after** the command name without the subparser's defaults overwriting values given before the command. It gets a CONCEPT(cli-with-argparse) comment and its own test (T-M0-20).
- `--version` uses `action="version"`, with the string built from `versions.python_description()`.
- Subcommands are registered from a table of `(name, module_path)` pairs. Each command module exposes `HELP: str`, `FORMATS: tuple[str, ...]`, `add_arguments(parser) -> None` and `run(inv: Invocation) -> Result[Any] | int`. **Command modules must be import-light at top level** (only `argparse`/`typing` and other import-light command helpers). Heavy imports happen inside `run()`, so `cartographer --version` stays fast (05 §6, dogfooded by C2).
- `--format` choices per command come from the command module's static `FORMATS` tuple, **not** from `output.formats_for()`, because importing the output registry while building the parser would defeat lazy loading. A test (T-M0-32) asserts `FORMATS == output.formats_for(name)` for every command after everything is imported.
- **Import discipline (item for C2 §6.12):** at module top level, `cli/main.py` imports only `argparse`, `sys`, `os`, `typing`, `collections.abc` and `cartographer.__about__`. `core.config`, `core.log`, `core.selection`, `core.result`, `output`, `cli.colour` and the chosen command's heavy code are imported **inside `main()` after `parse_args`**. `core/config.py` imports `tomllib` inside `load_config()`, not at module level. Result: `cartographer --version` (handled by argparse during `parse_args`) imports no config, TOML, logging-setup or output code (T-M0-32).

**`Invocation`** (frozen dataclass): `command`, `root: Path`, `config: Config`, `selection: SelectionRequest` (unresolved, §6.7), `format`, `output: Path | None`, `colour: bool`, `verbosity`, `debug`, `args: argparse.Namespace` (command-specific).

**Dispatch flow:**
```
try:
    ns = parser.parse_args(argv)           # argparse raises SystemExit(2) on errors -> return 2; --version exits here
    from cartographer.core import config as cfg, log, selection   # lazy: only after parse_args (import discipline)
    log.configure(...)
    config = cfg.load_config(root, explicit=ns.config, overrides=cli_overrides(ns),
                             section_types=resolve_section_types(...))
    request = selection.request_from(config.core, cli_select=ns.select, cli_ignore=ns.ignore)  # NOT resolved here
    result = command.run(invocation)       # run() calls cartographer.api.<fn>(..., request=inv.selection);
                                           # api resolves + filters exactly once (D-046). int return = commands
                                           # like `explain` that print themselves
    from cartographer import output        # lazy
    text = output.render(...)              # renders result.diagnostics AS GIVEN: no filtering in the CLI
    write to --output (utf-8, newline="\n") or stdout
    return exit_code_for(result.diagnostics, config.core.fail_on)
except CartographerError as e:  print to stderr; return EXIT_CODES[type(e)]
except KeyboardInterrupt:        print("Interrupted.", file=stderr); return 130
except Exception as e:           if debug: traceback; print internal-error text; return 3
```
- `argparse` exits through `SystemExit`. `main()` catches `SystemExit` around `parse_args` and returns its code, so `main(["--version"])` returns 0 in tests instead of killing pytest.
- Writing to stdout on Windows 3.13/3.14: `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` is called when stdout is **not** a TTY (redirected to a file or pipe). Otherwise piping JSON with non-ASCII paths can raise `UnicodeEncodeError` under a legacy code page (D-019). On a TTY the console's own encoding is kept. CONCEPT comment.

**`cli/colour.py`:**
```python
def should_colour(stream: TextIO, no_colour_flag: bool, environ: Mapping[str, str]) -> bool
    # False if flag, or "NO_COLOR" in environ (any value, per no-color.org), or not stream.isatty(),
    # or (Windows and enable_windows_vt() is False)
def enable_windows_vt() -> bool
    # ctypes: kernel32.GetStdHandle(-11); GetConsoleMode; SetConsoleMode(mode | 0x0004)
    # (ENABLE_VIRTUAL_TERMINAL_PROCESSING). Any failure -> False. Never raises.
```
`enable_windows_vt` is excluded from coverage on non-Windows runners with `# pragma: no cover` *only* on the `sys.platform != "win32"` early return, and is tested on the Windows CI runner.

### 6.18 Scripts
| Script | Behaviour |
|---|---|
| `scripts/dev.py` | `argparse` subcommands `lint` (`ruff check .`), `format` (`ruff format .`; `--check` flag), `types` (`mypy`), `test` (`pytest` + passthrough args), `docs` (`check_concepts.py`, `check_links.py`, `pytest tests/docs`), `bench` (runs `benchmarks/*.py`), `all` (`lint`, `format --check`, `types`, `docs`, `test` with coverage gates). Each step prints `==> step`, runs via `subprocess.run([sys.executable, "-m", ...])` (list args, no shell), and records pass/fail. `all` runs every step even after a failure, prints a summary table, and exits 1 if any step failed. Coverage gates: `pytest --cov --cov-fail-under=85`, then `coverage report --include="*/cartographer/core/*" --fail-under=90`. |
| `scripts/check_concepts.py` | Tokenizes every `.py` under `src/`, `tests/` (except `tests/fixtures/`) and `scripts/`. Finds `COMMENT` tokens matching `CONCEPT\(([a-z0-9][a-z0-9-]*)\)`. Each slug must have an existing file `docs/learn/concepts/<slug>.md`. Prints `path:line: CONCEPT(<slug>) has no docs/learn/concepts/<slug>.md` per failure and exits 1. Uses `tokenize`, never regex on raw lines, so a `"CONCEPT(x)"` inside a string isn't counted. |
| `scripts/check_links.py` | For every `*.md` in the repo (excluding `.venv`, `.corpus`, `tests/fixtures`), finds inline links `[text](target)` outside fenced code blocks and inline code. External targets (`http:`, `https:`, `mailto:`) are not checked, since that would need the network. A relative target must exist, resolved from the Markdown file's directory. A `#anchor` (same file or `file.md#anchor`) must match a heading slug computed GitHub-style: lowercase; drop every character except letters, digits, spaces, `-` and `_`; spaces → `-`; duplicates get `-1`, `-2`… Prints `file:line: broken link …` and exits 1 on failure. |
| `scripts/gen_synthetic_project.py` | `--out DIR --modules N --packages P --avg-imports K --cycles C --seed S`. Deterministic (`random.Random(seed)`; output sorted). Writes `pkgNN/modNNNN.py` files under `DIR/src/`, each with module-level imports of *lower-numbered* modules (a DAG), plus exactly `C` planted back-edges creating cycles, a function-level import in about 20 % of modules, and a `TYPE_CHECKING` block in about 10 %. **Shape rules (C1's runtime oracle T-C1-22 depends on them):** every `pkgNN/` directory has an **empty** `__init__.py`; every import is an absolute `import pkgAA.modBBBB` statement (no from-imports, no relative imports); the module level contains only imports, `VALUE = <n>` and one `def f(): ...`; imported modules are referenced **only inside function bodies** (`return pkgAA.modBBBB.VALUE`), so importing any module succeeds even with the planted cycles. The manifest lists **explicit** edges only; implicit parent-package edges are derived by the consumer (the empty `__init__.py` files import nothing). Writes `DIR/manifest.json` listing every module, every edge with its kind (`module`/`deferred`/`typing`) and the planted back-edges. That's the ground truth for C1's resolver tests. Also writes `DIR/pyproject.toml` and `DIR/README.md`. |

### 6.19 Tests infrastructure (`tests/conftest.py`)
- Registers Hypothesis profiles `dev` (100 examples), `ci` (500, `deadline=None`, `print_blob=True`) and `thorough` (5,000), and loads `os.environ.get("HYPOTHESIS_PROFILE", "dev")`.
- `collect_ignore_glob = ["fixtures/*"]`, so pytest never imports fixture code (05 §3.5). On interpreters older than 3.14 / 3.15 it also adds `**/test_*_py314.py` / `**/test_*_py315.py` (05 §3.1), because those files wouldn't even parse.
- **`src/conftest.py`** (D-055): `collect_ignore` for `cartographer/__main__.py` always (importing it runs the CLI), `collect_ignore_glob` for `cartographer/adapters/*` when `sys.version_info < (3, 14)` and for `cartographer/depdiff/sandbox/*` always. Its docstring explains why doctest collection imports modules.
- `pytest_collection_modifyitems`: skip `requires_py314`/`requires_py315` on older interpreters, with the reason `needs Python 3.15 (running 3.13)`.
- `pytest_addoption`: `--update-golden`.
- **`golden` fixture:** `golden.check(actual: str, path: str)`. It normalises both sides and compares; on mismatch it fails with a unified diff (`difflib.unified_diff`). With `--update-golden` it writes the file instead and marks the test as `xfail("golden updated")`, so an update run is never mistaken for a pass. Normalisations, in order:
  1. `\r\n` → `\n`.
  2. JSON: parse, delete the `meta` key, set `tool.version` to `"<version>"`, re-dump with `indent=2`.
  3. SARIF: set `runs[*].tool.driver.version` to `"<version>"` and `originalUriBaseIds.SRCROOT.uri` to `"file:///<root>/"`.
  4. Text: regex `\(\d+\.\d{2} s\)` → `(<time> s)`. `cartographer \S+ \(Python [^)]*\)` → `cartographer <version> (Python <python>)`.
- `fixture_project(name) -> Path` helper returns `tests/fixtures/projects/<name>`.

### 6.20 Fixture projects (each with a `README.md`, 04 §3.5)
| Fixture | Contents | Used for |
|---|---|---|
| `m0_golden/` | `pyproject.toml` (`requires-python = ">=3.12"`, `[tool.cartographer] exclude = ["generated/**"]`); `src/demo/__init__.py`; `src/demo/core.py` (a non-ASCII string before a node on the same line, e.g. `label = "naïve→"; value = 1`); `src/demo/latin.py` (PEP 263 `latin-1` cookie + a raw `0xE9` byte inside a string; committed with `-text`); `src/demo/bom.py` (UTF-8 BOM); `src/demo/formfeed.py` (a `\x0c` line before a function); `src/my-script.py`; `generated/skip_me.py`; `build/also_skipped.py` | Golden scan output on **all** interpreter versions: no diagnostics expected |
| `m0_errors/` | `src/demo/__init__.py`, `src/demo/ok.py`, `src/demo/broken.py` (syntax error), `src/demo/bad_encoding.py` (declares nothing, contains byte `0xFF`), `src/demo/nulls.py` (contains a NUL byte), `src/demo/future_syntax.py` (`# requires: 3.15` header + `lazy import json`) | Diagnostics. Golden output on **3.15 only** (`requires_py315`), because Python's error messages change between versions; structural asserts on every version |
| `m0_flat/` | No `src/`; `pkg/__init__.py`, `pkg/mod.py`, `pkg/mod.pyi`, `tool.py`; `cartographer.toml` **and** `pyproject.toml` with conflicting `fail-on` | Flat-layout module names; `cartographer.toml` wins (03 §4.1) |

The CRT003 test generates its large file in `tmp_path` at test time (a 2 MB+ file is not committed).

### 6.21 CI (`.github/workflows/ci.yml`)
```yaml
name: ci
on:
  push: { branches: [main] }
  pull_request:
permissions:
  contents: read
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
defaults:
  run:
    shell: bash            # bash exists on windows-latest too; one syntax everywhere
jobs:
  lint:   # ubuntu-latest, Python 3.15: ruff check + ruff format --check
  types:  # ubuntu-latest, Python 3.15: mypy (python_version 3.15), then mypy --python-version 3.13 --exclude src/cartographer/adapters/
  docs:   # ubuntu-latest, Python 3.15: scripts/dev.py docs
  test:
    strategy:
      fail-fast: false
      matrix:
        os: [windows-latest, ubuntu-latest]
        python: ["3.13", "3.14", "3.15", "3.15t"]
    runs-on: ${{ matrix.os }}
    env:
      PYTHON: ${{ matrix.python }}
      HYPOTHESIS_PROFILE: ci
    steps:
      - uses: actions/checkout@<40-char SHA>   # vX.Y.Z
        with: { persist-credentials: false }
      - uses: astral-sh/setup-uv@<40-char SHA> # vX.Y.Z
      - run: uv python install "$PYTHON"
      - run: uv sync --python "$PYTHON"
      - run: uv run --python "$PYTHON" python scripts/dev.py test --cov
```
- SHAs are looked up at implementation time (`gh api repos/actions/checkout/git/ref/tags/vX.Y.Z`) and **never guessed**. The tag goes in the trailing comment.
- Matrix values reach scripts only through `env:` (05 §4 hardening), even though `matrix.*` isn't attacker-controlled. Consistency makes the rule easy to check, and C7 will audit this file.
- The coverage gates run only in the `ubuntu-latest` × `3.15` cell (`if:` on a step), to avoid duplicate failures.

## 7. Diagnostics

| Code | Trigger | Location | Message example | `data` |
|---|---|---|---|---|
| CRT001 `syntax-error` | `ast.parse` raises `SyntaxError`/`ValueError`/`RecursionError` | error line/offset (§6.13) | `cannot parse: invalid syntax; this file may use Python 3.15 syntax (lazy import); run Cartographer under Python 3.15 to analyse it` | `python_message: str`, `hint_version: str \| null` |
| CRT002 `decode-error` | `tokenize.open`/`read` raises `UnicodeDecodeError` or `SyntaxError` (bad cookie) | 1:1 | `cannot decode file: unknown encoding: latin-42` | `error: str` (exception class name) |
| CRT003 `file-too-large` | `size > max-file-size-kb * 1024` | 1:1 | `file skipped: 2050 KB is larger than max-file-size-kb (2048)` | `size_bytes: int`, `limit_kb: int` |

All three carry a `help` line. CRT004–CRT7xx are registered as `planned` (§6.6).

## 8. Configuration

Only the core keys from [03 §4.2](../03-cli-config-output.md#42-core-keys-m0) are implemented, with the validation rules in §6.9. No feature sections exist yet, so any sub-table other than `severity`/`per-file-ignores` → `ConfigError: unknown section`.

## 9. Phases & tasks

Each phase is **one PR** (D-009). The whole of M0 is **MVP**: nothing here may slip.

### Phase 1: Skeleton, tooling, CI, doc checks (`m0/skeleton`)
- [ ] **S-00 spike**: install the four interpreters with uv locally; confirm `astral-sh/setup-uv` can provide `3.15t` on both runner OSes; write `docs/learn/spikes/S-00-interpreters.md`.
- [ ] `pyproject.toml` (including the repo's own `[tool.cartographer] exclude`, D-048), `.python-version`, `.gitattributes`, `.gitignore`, `LICENSE`, `CHANGELOG.md` (§6.2).
- [ ] `src/conftest.py` (D-055) + T-M0-34.
- [ ] `src/cartographer/{__init__,__about__,__main__,api}.py`, `py.typed` (§6.3).
- [ ] A minimal `cli/main.py` supporting only `--version` (full CLI comes in phase 4).
- [ ] `tests/conftest.py`: markers, Hypothesis profiles, `collect_ignore_glob` (golden helper comes in phase 4).
- [ ] 🖐 `scripts/dev.py` (§6.18). It's a small, self-contained script and good argparse/subprocess practice.
- [ ] `scripts/check_concepts.py`, `scripts/check_links.py` + `tests/docs/test_concepts.py`, `test_links.py` (they run the scripts against small fixture Markdown in `tmp_path`, plus against the real repo).
- [ ] `tests/docs/test_docstrings.py` (04 §3.1/3.2 rules: module docstring headings; public defs/classes have docstrings; private defs > 10 lines have docstrings; dunder methods exempt).
- [ ] `tests/docs/test_concept_examples.py` (04 §2.1: extract ```` ```pycon ```` blocks per note; one shared `globs` dict per note; skip a block whose first line is `# Python 3.N+` on older interpreters; `doctest` flags `ELLIPSIS | NORMALIZE_WHITESPACE`).
- [ ] `tests/docs/test_fixture_readmes.py`.
- [ ] `.github/workflows/ci.yml` (§6.21) with SHA-pinned actions.
- [ ] Concept notes: `how-python-runs-code`, `project-layout-and-pyproject`, `virtual-environments-and-uv`, `git-and-github-actions-basics`, `testing-with-pytest`.

### Phase 2: Core data model (`m0/core-model`)
- [ ] `core/errors.py` (§6.4), `core/diagnostics.py` (§6.5), `core/result.py` (§6.8), `core/log.py` (§6.15).
- [ ] `core/codes.py` with the full registry, `register_external`, and the CRT001–003 explanations (§6.6).
- [ ] `core/diagnostics.display_text` (§6.5, D-050) + T-M0-29.
- [ ] 🖐 `core/selection.py` (§6.7). The selector rules are a well-specified puzzle with clear tests.
- [ ] Unit tests + property tests (T-M0-01…T-M0-10, T-M0-29, T-M0-30).
- [ ] Concept notes: `type-hints-basics`, `dataclasses-and-enums`, `exceptions`, `logging`, `property-based-testing`.

### Phase 3: Files, sources, projects, config (`m0/sources`)
- [ ] **S-10 spike**: on 3.13, 3.14 and 3.15, record `ast.parse` errors and `tokenize` streams for a t-string, a `lazy import`, `except A, B:`, a NUL byte and a non-ASCII error column; write `docs/learn/spikes/S-10-new-syntax.md`; adjust §6.12's table.
- [ ] `core/files.py` (§6.10), `core/modnames.py` (§6.11), `core/versions.py` (§6.12).
- [ ] `core/source.py` (§6.13): byte→char columns, `split("\n")`, CRT001/002/003.
- [ ] `core/project.py` (§6.14), `core/config.py` (§6.9), `cli/sections.py` (empty mapping).
- [ ] Fixture projects `m0_golden`, `m0_errors`, `m0_flat` with READMEs (§6.20).
- [ ] 🖐 `scripts/gen_synthetic_project.py` (§6.18).
- [ ] `benchmarks/bench_discover_parse.py`: generate 2,000 modules (seed 1), time discovery + parsing (median of 5); compare with the 4 s budget (05 §6).
- [ ] Concept notes: `text-and-encodings`, `paths-and-files`, `config-with-tomllib`, `ast-basics`, `tokenize-and-comments`, `descriptors-and-cached-property`.

### Phase 4: Output and CLI (`m0/cli`)
- [ ] `output/registry.py`, `text.py`, `json.py`, `sarif.py` (§6.16); vendored SARIF schema + `jsonschema` dev dependency.
- [ ] `cli/main.py` full (§6.17, including the import discipline), `cli/colour.py`, `cli/commands/explain.py`, `cli/commands/scan.py`; `api.scan` + `api._finish` (§6.3); text hooks (§6.16).
- [ ] T-M0-31 (filter once), T-M0-32 (`--version` import set, `FORMATS` consistency), T-M0-33 (text hook order).
- [ ] `golden` fixture (§6.19) + golden files for `scan` (text/json/sarif on `m0_golden`; text/json on `m0_errors`, 3.15 only) and `explain` (`CRT001`, `CRT101`, `--list`).
- [ ] Integration tests for every row of §5.6 and every exit code.
- [ ] **S-04 spike (report only)**: `uv run --python 3.15t --with libcst --with pyyaml python -c "import sys, libcst, yaml; print(sys._is_gil_enabled())"`; write `docs/learn/spikes/S-04-free-threading.md`. No code change (D-029).
- [ ] Concept notes: `cli-with-argparse`, `sarif-and-machine-output`.

### Phase 5: Close the milestone (`m0/close`)
- [ ] Run every acceptance criterion (§11) and record the results.
- [ ] `docs/learn/walkthroughs/M0.md`, `docs/learn/writeups/M0.md`.
- [ ] Version `0.0.1`, `CHANGELOG.md`, tick the roadmap tracker and curriculum index.

## 10. Test plan

| ID | What | Kind |
|---|---|---|
| T-M0-01 | `Severity` ordering (`ERROR > WARNING > INFO`), `str()`, `severity_from_str` round trip | unit |
| T-M0-02 | `Diagnostic.__post_init__` rejects bad codes, line 0, column 0, multi-line messages, trailing `.` | unit |
| T-M0-03 | `Diagnostic.data` is read-only after construction | unit |
| T-M0-04 | `sort_key` gives a total, deterministic order: Hypothesis generates lists of diagnostics; sorting any permutation gives the same result | property |
| T-M0-05 | `to_json` output is accepted by `json.dumps` for any generated diagnostic (JSON-safe `data`) | property |
| T-M0-06 | Error classes map to exit codes 2/2/2/4/3; `ConfigError` string format | unit |
| T-M0-07 | `selection.resolve`: exact code, exact name, prefix, case-insensitivity, default-off CRT005 only by exact selection, ignore wins, CLI select replaces config select, unknown selector → error with suggestion | unit (parametrised) |
| T-M0-08 | Registry ⇔ 03 §6 tables (parsed from the Markdown, Default-cell rule in §6.6: `error/warning` → default ERROR + `per_finding_severity`; `info, off by default` → INFO + `enabled_by_default=False`); implemented codes have six-heading explanations; names unique and kebab-case | unit |
| T-M0-09 | `selection.apply`: per-file-ignores globs, severity overrides, output sorted | unit |
| T-M0-10 | `exit_code_for` for each `fail-on` value × diagnostic mixes | unit (parametrised) |
| T-M0-11 | `_char_col` matches a brute-force character count for any generated line + offset that lands on a character boundary (Hypothesis `text()` strategy including astral-plane characters) | property |
| T-M0-12 | Form-feed fixture: the line number of the function after `\x0c` matches `ast`'s line number (would fail with `splitlines()`) | unit |
| T-M0-13 | Decoding: latin-1 cookie, BOM, `\r\n` files, invalid byte → CRT002, unknown cookie → CRT002, NUL → CRT001, deep nesting → CRT001 | unit |
| T-M0-14 | `files.discover`: default excludes, user excludes (`generated/**` prunes), include patterns, top-level `a.py` matches `**/*.py`, symlinks skipped (test creates one; skipped on Windows without symlink privilege), deterministic order | unit |
| T-M0-15 | `module_name` rules (§6.11 examples + keywords + `__init__` at root) | unit (doctest + parametrised) |
| T-M0-16 | Config: precedence (CLI > `--config` > `cartographer.toml` > `pyproject.toml`), no merging, kebab↔snake, bool-not-int, int-as-float, unknown key/section suggestions, TOML syntax error position, `target-version = "auto"` from `requires-python` incl. clamping | unit |
| T-M0-17 | SARIF output validates against the vendored 2.1.0 schema; paths with spaces are URI-escaped; `ruleIndex` correct | unit |
| T-M0-18 | Golden: `scan` text/json/sarif on `m0_golden` (all versions); text/json on `m0_errors` (3.15) | golden |
| T-M0-19 | `--version` format (normal and free-threaded, via monkeypatched `versions`); same via `carto` and `python -m cartographer` (subprocess) | integration |
| T-M0-20 | Global options before and after the command give identical results (`--format json scan X` ≡ `scan X --format json`) | integration |
| T-M0-21 | Every row of §5.6 → expected stderr + exit code; internal error path via a monkeypatched command raising `ZeroDivisionError`; `--debug` shows the traceback; Ctrl+C path via a monkeypatched `KeyboardInterrupt` → 130 | integration |
| T-M0-22 | `explain`: code, name, case-insensitive, planned code, unknown code suggestion, `--list` golden | integration + golden |
| T-M0-23 | Colour: `NO_COLOR`, `--no-color`, non-TTY → no escape codes; forced TTY → escape codes present; `--output FILE` never coloured | unit |
| T-M0-24 | `log.configure` idempotent; logs go to stderr, never stdout | unit |
| T-M0-25 | `syntax_hint` per S-10 table (runs only on interpreters older than each feature) | unit |
| T-M0-26 | Doc checks: each check script fails on a crafted bad input and passes on a good one | unit (tests/docs) |
| T-M0-27 | `gen_synthetic_project` is deterministic (same seed → byte-identical tree) and its manifest's planted back-edges exist in the generated files | unit |
| T-M0-28 | JSON output with non-ASCII paths, redirected to a pipe, on Windows 3.13 doesn't raise (subprocess with `PYTHONIOENCODING` unset) | integration |
| T-M0-29 | `display_text`: newline, CR, tab, ESC/ANSI sequences, NUL, lone surrogate, trailing dot/space are escaped; printable text is unchanged; idempotent; a `Diagnostic` built from any Hypothesis-generated string passed through it never raises in `__post_init__` | unit + property |
| T-M0-30 | Effective selection: `select ∩ scope − ignore`; default `("CRT",)` reports the whole scope; an out-of-scope but registered selector is valid and yields nothing; an unknown selector errors with the right class per origin; `register_external` makes `CRT9xx` selectable and visible to `get`/`all_codes`; duplicate/invalid external codes raise `ValueError`; every `api.SCOPES` selector matches at least one code | unit |
| T-M0-31 | Filtering happens once (D-046): with a spy on `selection.apply`, `main(["scan", …])` calls it exactly once; `cli/main.py` contains no call to `selection.apply` (checked by an `ast` scan of the file) | integration + unit |
| T-M0-32 | `python -I -c "import sys; from cartographer.cli.main import main; main(['--version']); print(sorted(sys.modules))"` (subprocess) shows none of `tomllib`, `cartographer.core.config`, `cartographer.output`, `cartographer.cli.colour`; for every command, `FORMATS == output.formats_for(name)` | integration |
| T-M0-33 | Text hooks: `before` → diagnostics → `after` → summary → `footer`, empty blocks omitted, single blank-line separation | unit |
| T-M0-34 | `src/conftest.py`: on 3.13 the adapters glob is ignored; the sandbox glob is ignored on every version (checked with fake files in `tmp_path` via `pytester`) | unit |

## 11. Acceptance criteria

| ID | Criterion (objectively checkable) |
|---|---|
| A-M0-01 | On a fresh clone, `uv sync` then `uv run cartographer --version` prints `cartographer 0.0.1 (Python 3.15.x, win32)` on the owner's machine |
| A-M0-02 | `carto --version` and `uv run python -m cartographer --version` print the identical string |
| A-M0-03 | `uv run cartographer scan tests/fixtures/projects/m0_errors` exits **0** (all findings are warnings and `fail-on` defaults to `error`), and with `--fail-on warning` exits **1** |
| A-M0-04 | `scan` golden tests pass on all 8 CI cells (2 OS × 4 Pythons); the 3.15-only goldens pass on both 3.15 cells |
| A-M0-05 | SARIF output from `scan` validates against the SARIF 2.1.0 schema (T-M0-17) |
| A-M0-06 | `uv run python scripts/dev.py all` exits 0 locally; CI is green on every job |
| A-M0-07 | Coverage ≥ 90 % for `cartographer/core`, ≥ 85 % overall |
| A-M0-08 | `cartographer explain` works for all registered codes; CRT001–003 explanations have all six sections |
| A-M0-09 | All 18 Stage 0 concept notes exist, pass the example-execution test, and are ticked in `docs/learn/README.md` |
| A-M0-10 | Every `CONCEPT(...)` tag in the repo resolves; `check_links.py` reports zero broken links across `docs/` |
| A-M0-11 | Every third-party action in `ci.yml` is pinned to a 40-character SHA with a version comment; top-level `permissions: contents: read`; checkout uses `persist-credentials: false` |
| A-M0-12 | Spike notes S-00, S-04, S-10 exist and any spec changes they triggered are merged |
| A-M0-13 | `bench_discover_parse.py` result recorded in the write-up against the 4 s budget |
| A-M0-14 | Walkthrough and write-up exist, follow their templates, and the prediction table is filled in |

## 12. Documentation deliverables

### 12.1 Concept notes (all of Stage 0, slugs exactly as in the curriculum index)
| Slug | Phase | Must include (beyond the template) |
|---|---|---|
| `how-python-runs-code` | 1 | Source → bytecode → interpreter loop; `__pycache__` and `.pyc`; `python file.py` vs `python -m pkg` (what goes on `sys.path[0]` in each case); `__name__ == "__main__"`; how `__main__.py` makes `python -m cartographer` work |
| `project-layout-and-pyproject` | 1 | Module vs package; flat vs src layout (with the "tests import the wrong copy" demo); every table in our `pyproject.toml` explained line by line; console-script entry points (intro) |
| `virtual-environments-and-uv` | 1 | What a venv is on disk (`.venv\Scripts\python.exe`, `site-packages`); `uv sync`/`run`/`python install`/`lock`; why the lockfile is committed; dependency groups |
| `git-and-github-actions-basics` | 1 | Commits, branches, PRs, squash merges, Conventional Commits; what a workflow/job/step/runner is, using our `ci.yml` as the example; why actions are pinned to SHAs (forward-reference to C7) |
| `testing-with-pytest` | 1 | Test discovery, assertions and rewriting, fixtures, `tmp_path`, `parametrize`, markers (and our opt-in markers), coverage (line vs branch), doctests, golden files and `--update-golden` |
| `type-hints-basics` | 2 | Reading signatures; `X \| None`; `list[int]`; `Mapping` vs `dict`; `Literal`; `Protocol` (light intro); PEP 695 `def f[T]`; `type` aliases; what `mypy --strict` checks; annotations are not enforced at runtime |
| `dataclasses-and-enums` | 2 | `@dataclass` generated methods; `frozen`, `slots`, `field(default_factory=…)` and the mutable-default trap (forward-link to C3 `function-defaults`); `object.__setattr__` in `__post_init__`; `MappingProxyType`; `Enum` vs `IntEnum` and why `Severity` is an `IntEnum` |
| `exceptions` | 2 | `raise`, `try/except/else/finally`, hierarchies and catching the base class, `raise … from …`, why per-file problems are diagnostics not exceptions (D-032), how exit codes map |
| `logging` | 2 | Loggers, levels, handlers, formatters, why libraries never `print`, stderr vs stdout, the duplicate-handler bug |
| `property-based-testing` | 2 | Strategies (`integers`, `text`, `lists`, `builds`, `composite`); shrinking with a live demo; oracles vs invariants; reading a failure and pinning it with `@example`; our profiles |
| `text-and-encodings` | 3 | `str` vs `bytes`; Unicode code points; UTF-8 byte lengths (`len("é".encode())`); BOM; PEP 263 cookies; `tokenize.open`; universal newlines; `\r\n`; **byte vs character columns with the `ast` demo**; `splitlines()` vs `split("\n")` demo; PEP 686 and Windows code pages |
| `paths-and-files` | 3 | `pathlib` basics; absolute vs relative; posix vs Windows separators; `as_posix()`/`as_uri()`; `os.scandir` and why it's faster than `listdir` + `stat`; glob patterns and `full_match` (3.13+); symlinks and junctions |
| `config-with-tomllib` | 3 | TOML syntax (tables, arrays of tables, inline tables); `tomllib.load` needs binary mode; `[tool.*]` convention; precedence; validation with `get_type_hints`/`get_origin`/`get_args`; the bool-is-an-int trap; dependency injection (§6.9); PEP 440 `requires-python` specifiers |
| `ast-basics` | 3 | Tokens → parse tree → AST; `ast.parse`, `ast.dump(indent=2)`; node classes and `_fields`; positions (`lineno`, `col_offset` as bytes, `end_*`); `ast.walk` vs `NodeVisitor` vs `NodeTransformer`; `get_source_segment`; parsing never executes; `feature_version` can only lower the grammar (D-004) |
| `tokenize-and-comments` | 3 | What the tokenizer produces (`tokenize.generate_tokens`, token types); comments exist only in tokens, not in the AST; why `"# not a comment"` inside a string is safe with tokenize but not with regex; `FSTRING_START` and (3.14) `TSTRING_START` |
| `descriptors-and-cached-property` | 3 | Attribute lookup order; `__get__`/`__set__`; data vs non-data descriptors; how `property` and methods are descriptors; `cached_property` writes into the instance `__dict__`; why it doesn't combine with `__slots__` (and why `SourceFile` isn't slotted) |
| `cli-with-argparse` | 4 | `sys.argv`; positional vs optional arguments; sub-parsers; parent parsers and the `SUPPRESS` trick for global options; `action="version"`; how argparse exits (`SystemExit(2)`) and how `main()` returns instead; stdout vs stderr; exit codes; Windows VT colour |
| `sarif-and-machine-output` | 4 | Why machine formats exist; JSON envelopes and schema versioning; SARIF's structure (run/tool/rules/results/locations); `columnKind`; how GitHub code scanning displays it (forward-link to C8) |

### 12.2 Walkthrough (`docs/learn/walkthroughs/M0.md`)
- Reading order: `__main__.py` → `cli/main.py:main` → `core/config.py:load_config` → `core/project.py:load_project` → `core/files.py:discover` → `core/source.py:SourceFile` → `cli/commands/scan.py:run` → `api.py:scan` → `core/selection.py:resolve`/`apply` (via `api._finish`, the one filtering point) → `output/text.py`.
- End-to-end trace: `cartographer scan tests/fixtures/projects/m0_errors --format json`. Show the `Invocation` repr, the discovered-file list, the `SourceFile` for `broken.py` with its CRT001 `Diagnostic` repr, and the final JSON.
- A Mermaid diagram of the five-step pipeline as actually implemented.
- "If you want to change…": add a global flag; add an output format; add a core config key.

### 12.3 Write-up (`docs/learn/writeups/M0.md`)
Must cover: S-00/S-04/S-10 findings; the discover+parse benchmark vs the 4 s budget; CI matrix duration per cell; any interpreter-specific surprises (error messages, tokenizer differences); the prediction table.

### 12.4 Reference comparison
Not applicable to M0. Optionally, a short note comparing our SARIF output with ruff's `--output-format sarif` on the same broken file, written after acceptance.

## 13. Reference implementations to compare after

M0 has no single reference tool. After acceptance, it's worth reading (not copying) how **ruff** structures its CLI global options and exit codes, and how **pytest** registers markers. Answer in the write-up: *"Which of our M0 conventions would surprise a ruff user?"*

## 14. Risks & open items

| Item | Link | Mitigation |
|---|---|---|
| 3.15t unavailable on a runner | S-00, R-04 | Fallback in 08 §1 |
| `SyntaxError.offset` units or new-syntax token streams differ by version | S-10 | Hint table is Provisional; goldens for error fixtures are 3.15-only |
| `tomllib.TOMLDecodeError` position attributes differ between 3.13 and 3.14+ | — | Implementer verifies and comments in `config.py`; falls back to parsing the message |
| Symlink tests on Windows need Developer Mode or admin | R-04 | `pytest.skip` when `os.symlink` raises `OSError` |
| `jsonschema` is a new dev dependency | D-006 | Already recorded in D-006 during the spec pass |
| Scope creep into C1 (full source roots) | R-11 | §4.2 out-of-scope table |

## 15. Exercises for the learner

1. **See the column bug yourself.** In a Python 3.15 REPL, run `import ast; t = ast.parse('s = "café"; x = 1'); print(t.body[1].col_offset)`. Count the characters to `x` yourself. Why do the numbers differ?
   *Hint:* `len("é")` vs `len("é".encode("utf-8"))`.
2. **Break a lookup on purpose.** Write `class A: @functools.cached_property\n def v(self): print("computing"); return 1`. Access `A().v` twice on the same instance, then try adding `__slots__ = ()` to the class. What error do you get, and why? *(Answer in `descriptors-and-cached-property`.)*
3. **🖐 Add a global flag.** Add a `--quiet-summary` flag that suppresses the summary line in text output. Which files did you touch? Did the "options before or after the command" test still pass?
4. **Read our CI like an attacker.** Open `.github/workflows/ci.yml`. If someone opened a PR from a fork, which secrets could their code read? *(Trick question: name them, then check `permissions:`.)*
5. **Make Hypothesis find a bug.** Temporarily change `_char_col` to use `len(line[:byte_offset])`. Run T-M0-11 and read the shrunk failing example. What's the smallest string it found?
