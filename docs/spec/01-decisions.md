# 01 — Decision log

> Every question that could cause confusion during implementation is answered here **once**, with its reasoning. If a milestone spec seems to contradict this file, this file wins. Fix the milestone spec in the same PR.
>
> **Format:** each decision has an ID (`D-###`), the decision, *why*, and *what you'd change if you disagreed*. New decisions made during implementation are appended using [`docs/templates/decision-record.md`](../templates/decision-record.md). Never renumber or delete a decision. To reverse one, mark it `Superseded by D-0xx`.
>
> **Status values:** `Accepted` (in force), `Superseded`, `Provisional` (in force, but must be confirmed by a spike in [`08-spikes-and-risks.md`](08-spikes-and-risks.md)).

---

## Project & process

### D-001: Roles
**Decision:** Claude implements the code, tests and documentation. You (the owner) are the **learner and reviewer**: you read the concept notes, answer the prediction questions before each milestone, review PRs, and ask questions. Tasks marked 🖐 in milestone specs are good candidates for you to write yourself if you want hands-on practice. They are optional.
**Why:** You said you are starting from zero and want the docs to answer your doubts. Teaching value therefore has to be built *into* the artefacts: concept notes, heavily explained code, walkthroughs and write-ups. It can't depend on you already knowing things.
**Consequence:** the documentation standard ([04](04-documentation-standard.md)) is mandatory and is part of every Definition of Done.

### D-002: Cartographer and Kiln share nothing
**Decision:** Cartographer lives in this repo only. No shared library with Kiln, and no shared monorepo.
**Why:** The research says so (§Summary), and it keeps each project's scope clear.

### D-003: Names
| Thing | Value | Why |
|---|---|---|
| Distribution name (PyPI) | `cartographer-py` | `cartographer` is already taken on PyPI (checked 2026-11-03). `cartographer-py` was free on that date. |
| Import name | `cartographer` | Short and natural. Risk: it clashes if someone also installs the unrelated `cartographer` PyPI package. That is acceptable for a learning project and noted in the README. |
| CLI commands | `cartographer` and the alias `carto` | Both are console-script entry points that run the same `main()`. |
| Python package layout | `src/cartographer/` ("src layout") | Stops tests from accidentally importing the un-installed source tree. The [FAQ](../learn/faq.md#why-src-layout) explains this. |
| GitHub repo | `github.com/Kar6677thik/Cartographer` (already exists, public, empty) | — |

### D-004: Supported Python versions: runtime vs. target
**Decision:**
- Cartographer **runs on** CPython **3.13, 3.14, 3.15 and 3.15t** (`requires-python = ">=3.13"`). Development uses **3.15**.
- Cartographer **analyses target code with the parser of the interpreter it is running on.** If a target file uses newer syntax than that interpreter knows (for example `lazy import` under 3.14, or a t-string under 3.13), Cartographer does **not** crash. It emits diagnostic **`CRT001 syntax-error`** with a hint such as *"this file may use Python 3.15 syntax (`lazy import`); run Cartographer under Python 3.15 to analyse it"* and continues with the other files.
- `--target-version` (config: `target-version`) tells *advice-giving* features which Python the target project runs on. For example, C2 only suggests `lazy import` syntax when the target is ≥ 3.15 and otherwise suggests `__lazy_modules__`. It does **not** change the parser.

**Why:** `ast.parse()` can only *lower* its grammar (`feature_version`), never raise it. That fact is easy to miss and causes confusing crashes, so we make it explicit.
**If you disagreed:** you could make 3.15 the floor. That removes the gating code but also removes the lesson about version compatibility.

### D-005: Cartographer's own source code must be valid 3.13 syntax
**Decision:** Code under `src/` must parse on 3.13. That means **no t-string literals and no `lazy import` statements in `src/`**. Newer *library* features are used behind `sys.version_info` checks, which type checkers understand.
- Lazy imports in our own code use the compatibility form `__lazy_modules__ = [...]` (PEP 810). Python 3.15 honours it and older versions ignore it. This is deliberate dogfooding for C2.
- Code that needs `string.templatelib` (3.14+) lives in modules imported only when available. Tests for it are skipped on 3.13 with `@pytest.mark.requires_py314`.
- **Test fixture files** (sample target code under `tests/fixtures/`) may use any syntax, because they are *data* that is parsed, never imported. Fixtures needing newer syntax carry a `# requires: 3.15` header comment, and tests skip accordingly.

### D-006: Dependency policy, mostly stdlib
**Decision:** Runtime dependencies are limited to:

| Package | Used by | Why not stdlib |
|---|---|---|
| `libcst` | C5 codemod (C2's lazy-apply uses plain text edits, see C2) | Rewriting code while **preserving formatting and comments** needs a *concrete* syntax tree. `ast` throws formatting away. |
| `PyYAML` | C7 | The stdlib has no YAML parser. We use its low-level `compose()` API to get line numbers. |

Everything else uses the stdlib: `ast`, `tokenize`, `symtable`, `argparse`, `tomllib`, `json`, `urllib.request`, `zipfile`, `tarfile`, `asyncio`, `subprocess`, `html.parser`, `shlex`, `sqlite3`, `statistics`, `logging`, `dataclasses` and `importlib.metadata`.

Dev-only dependencies: `pytest`, `hypothesis`, `pytest-cov`, `ruff`, `mypy`, `jsonschema` (validates our SARIF output against the official schema in tests), `trove-classifiers` (C8 metadata test), and `networkx` (**test oracle only**: we check our own graph algorithms against it, and it never appears in `src/`). Golden-file (snapshot) testing uses a small hand-written pytest fixture, not a plugin (see 05 §3.4). The C4 type checkers (`pyright`, `pyrefly`, `ty`) run via `uvx` and are not project dependencies.

**Optional extra:** `cartographer-py[verify]` adds `hypothesis` for `tstring verify` only (D-035).

**Why:** learning first. Hand-written argument parsing, graph algorithms, dataflow and HTTP fan-out teach far more than `click`, `networkx` and `httpx`. **Adding any new runtime dependency requires a new decision record.**

### D-007: Build core algorithms by hand, verify with oracles
**Decision:** SCC detection (Tarjan), the feedback-edge heuristic, dataflow, `-X importtime` parsing, statistics (bootstrap confidence intervals) and the Actions expression scanner are written by hand. Wherever a trusted implementation exists (networkx, `statistics`, `tokenize`), **property-based tests compare ours against it** on random inputs.
**Why:** you learn the algorithm and get confidence that it is correct.

### D-008: Read the reference implementation only *after* building ours
**Decision:** For each milestone, the implementer builds from the spec **without reading the reference tool's source code**, and must not copy code from it (licences, plus the learning goal). After acceptance, the implementer reads the reference and writes `docs/learn/comparisons/<milestone>.md` from [the template](../templates/reference-comparison.md). Reading the reference tool's *user docs* (what it does, not how) is allowed for calibration.

### D-009: Git workflow
**Decision:**
- `main` is always green (CI passes).
- Work happens on branches named `<milestone>/<short-topic>`, for example `c1/resolver`. Each **phase** of a milestone spec is one PR, and PRs are squash-merged.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat(graph): add Tarjan SCC`, `docs(learn): add import-system note`).
- Every PR description includes a "**What you'll learn from this PR**" section (see 04).
- The implementer only pushes or opens PRs when the owner has asked in the current session.

### D-010: Versioning
**Decision:** SemVer `0.y.z` until C8. Each completed milestone bumps the minor version: M0 → `0.0.1`, C1 → `0.1.0`, C2 → `0.2.0`, … C7 → `0.7.0`, and C8 → `1.0.0` if final acceptance passes. The version lives in a single place, `src/cartographer/__about__.py`. Every release has a changelog entry in `CHANGELOG.md` ([Keep a Changelog](https://keepachangelog.com/) format).

### D-011: Publishing needs explicit approval
**Decision:** C8 publishes to **TestPyPI** using Trusted Publishing with attestations. Publishing to the **real PyPI** happens only after the owner explicitly says yes in that session. Publishing is public and effectively permanent: PyPI never lets you reuse a version number.

### D-012: Licence
**Decision:** MIT, set up in M0. **If you disagreed:** Apache-2.0 is the other common choice (it adds a patent grant). Changing it before the first release costs nothing.

---

## Architecture & behaviour

### D-013: Static by default; three opt-in execution paths
See [00 §6](00-overview.md#6-safety-model-important-read-this). The three paths are `startup measure`/`startup compare` (`--execute`, C2), `depdiff --dynamic` (Docker, C6) and `tstring verify` (C5, D-036).
**Corpus rule (amended during the spec pass):** code from `.corpus/` (real third-party repos) **never runs on the host, not even with `--execute`**. When acceptance needs to execute corpus code (C2's startup win, C8 Final acceptance F2), it runs inside a Docker container started with `--network none`, via `scripts/corpus_startup.py`. `--execute` on the host is only for our own fixtures and code the owner explicitly trusts. The harness is specified in D-052. Tests never hit the network or Docker unless they are explicitly marked (`@pytest.mark.network`, `@pytest.mark.docker`), and marked tests are deselected by default.

### D-014: CLI is built on `argparse`
**Decision:** use the stdlib `argparse` with sub-parsers, one module per subcommand. See [03](03-cli-config-output.md).
**Why:** stdlib (D-006), and it teaches how CLIs actually parse arguments.

### D-015: Configuration lives in `pyproject.toml`
**Decision:** read `[tool.cartographer]` from the *target project's* `pyproject.toml`, or a standalone `cartographer.toml` (same keys, no `tool.cartographer` prefix), parsed with `tomllib`. Precedence, highest first: **CLI flags → `--config FILE` → `cartographer.toml` → `pyproject.toml [tool.cartographer]` → built-in defaults.** Unknown keys are an error (`ConfigError`, exit code 2) that suggests the closest valid key, found with `difflib.get_close_matches`. Full schema in [03](03-cli-config-output.md#4-configuration).

### D-016: One diagnostic model and one code scheme for all features
**Decision:** every finding from every milestone is a `Diagnostic` (see [02 §4](02-architecture.md#4-core-data-model)) with a code `CRT###`. The first digit is the milestone:

| Range | Owner |
|---|---|
| `CRT0xx` | Core / internal (parse errors, config) |
| `CRT1xx` | C1 import graph |
| `CRT2xx` | C2 startup / lazy imports |
| `CRT3xx` | C3 rules |
| `CRT4xx` | C4 typing |
| `CRT5xx` | C5 t-strings / injection |
| `CRT6xx` | C6 dependency diff |
| `CRT7xx` | C7 CI workflows |
| `CRT9xx` | Reserved for third-party plugins (C3 plugin API) |

Each code also has a kebab-case **name** (`CRT101 import-cycle`). Users can refer to a rule by code, by name, or by prefix (`--select CRT1`). The master registry is [03 §6](03-cli-config-output.md#6-diagnostic-code-registry).

### D-017: Output formats
**Decision:** `text` (default, human-readable), `json` (stable, versioned envelope), `sarif` (SARIF 2.1.0 for GitHub code scanning). Graph-shaped extras: `dot` and `mermaid` (C1). Report: `markdown` (C8). Output is **deterministic**: sorted, no timestamps except in `meta`, and posix-style relative paths, so golden tests are stable.

### D-018: Positions are 1-based lines and 1-based *character* columns
**Decision:** `Location.line` and `Location.column` are both 1-based. Columns count **Unicode code points**, not bytes.
**Why (a classic trap):** `ast` gives `col_offset` as a **0-based UTF-8 byte offset**. On a line like `name = "café"; x = 1`, byte and character offsets differ after the `é`. `core/source.py` converts them. SARIF output declares `"columnKind": "unicodeCodePoints"`.

### D-019: Reading source files
**Decision:** always read Python source through `tokenize.open()`, which honours PEP 263 encoding declarations and BOMs. Files that fail to decode produce `CRT002 decode-error` and are skipped. Cartographer's own file writes always use `encoding="utf-8"` and `newline="\n"`. We never rely on the platform default. Python 3.15 makes UTF-8 the default (PEP 686), but 3.13 and 3.14 on Windows do not.

### D-020: Discovering files
**Decision:** a project = a root directory. We walk it with `os.scandir` (recursively) and apply `include` and `exclude` glob patterns. Default excludes: `.git`, `.hg`, `.venv`, `venv`, `env`, `.tox`, `.nox`, `__pycache__`, `build`, `dist`, `node_modules`, `*.egg-info`, `.mypy_cache`, `.ruff_cache`, `.pytest_cache`, `.cartographer-cache`, `site-packages`. **We do not parse `.gitignore`** in v1 (that's a non-trivial spec; a note explains why). Symlinked directories are not followed, which prevents loops. Paths are reported relative to the root in posix form (`pkg/mod.py`).

### D-021: No caching between runs (v1)
**Decision:** each invocation re-parses. Within one run, each file is parsed **once** and shared by all analyses (`SourceFile` caches its AST). Performance budget: see 05 §6.

### D-022: Concurrency inside Cartographer
**Decision:** v1 analysis is **single-threaded**, which keeps it simple and deterministic. The *only* concurrency is C6's network fan-out (asyncio + `asyncio.to_thread`) and C2/C6 subprocesses. A stretch goal in C4 measures a thread-pool parse on 3.15t, which is a free-threading lesson.

### D-023: Codemods use LibCST; fallback is position-based text edits
**Decision (Provisional, spike S-03):** C5 rewrites code with LibCST. (C2's lazy-apply only inserts the `lazy` keyword or a `__lazy_modules__` line, so it uses plain position-based text edits via the shared `core/edits.py`.) If the installed LibCST cannot *emit* t-string syntax, the codemod uses LibCST only to *locate* nodes and then applies precise text edits. Changing `f"..."` to `t"..."` is a prefix swap plus wrapping the call site, so text edits are sufficient and safe when the positions are exact.

### D-024: t-string adapters
**Decision:** Cartographer ships small, readable **reference processors** in `cartographer.adapters` (`sql.dbapi`, `html.escape_html`, `shell.argv`). They are used (a) by the C5 verifier as known-good processors, and (b) as the default import target for C5 rewrites. Config `tstring.adapters.<sink-kind>` can point rewrites at third-party processors instead (for example sql-tstring or tdom) once spike S-05 has confirmed their APIs.

### D-025: Network access (C6 only)
**Decision:** use HTTPS via `urllib.request` against PyPI's JSON API and Integrity (provenance) API. Fan-out uses `asyncio.TaskGroup` + `asyncio.Semaphore(8)` + `asyncio.to_thread`. Downloads are cached in a user cache directory (`%LOCALAPPDATA%\cartographer\cache` on Windows, `~/.cache/cartographer` elsewhere, overridable with `CARTOGRAPHER_CACHE_DIR`) and verified against PyPI's published SHA-256 before use. Tests never use the network: they use recorded responses under `tests/fixtures/pypi/`.

### D-026: YAML parsing (C7)
**Decision:** PyYAML **`yaml.compose()` with `SafeLoader`**, never `yaml.load` with an unsafe loader. Composing gives a node tree with line and column marks for every value. We convert it to our own typed model.
**Gotcha this teaches:** YAML 1.1 parses the bare key `on:` as the boolean `True`. GitHub Actions' trigger key is literally `on`. Working at the node level and reading the raw scalar text avoids that trap.

### D-027: Acceptance corpus
**Decision:** final acceptance (G2) runs against **pinned real repositories** (exact commit SHA) and **replica fixtures** we build ourselves (an Ultralytics-style workflow and package pair). Real repos are cloned into `.corpus/` (gitignored) by `scripts/fetch_corpus.py` from `corpus/corpus.toml`. Candidate selection and pinning happen in M0 (spike S-07).

### D-028: Documentation is a Definition-of-Done item
See [04](04-documentation-standard.md). A PR that adds behaviour without the required docstrings, concept notes or walkthrough updates is not mergeable.

### D-029: Free-threaded build (3.15t)
**Decision:** Cartographer is pure Python, so it runs on 3.15t unchanged. CI runs the test suite on 3.15t. If a dependency (LibCST has a native parser, PyYAML has an optional C extension) **re-enables the GIL**, we record it with `sys._is_gil_enabled()` in a test that *reports* rather than fails. Spike S-04 checks this.

### D-030: Distribution artefacts
**Decision:** we ship one **pure-Python wheel** (`py3-none-any`) plus an sdist. The C4 mypyc compilation is a *measured experiment* and is not shipped. Shipping compiled wheels is a stretch goal in C8.

### D-031: Public Python API
**Decision:** the library API is the module `cartographer.api`. It contains one function per feature (`build_import_graph`, `profile_startup`, `run_rules`, `type_coverage`, `find_tstring_candidates`, `diff_dependency`, `audit_workflows`) plus the data classes they return. Everything else is internal (named with a leading `_`, or documented as internal). The CLI is a thin layer over `cartographer.api`. **Rule: the CLI never does analysis itself.**

### D-032: Error handling philosophy
**Decision:** *problems in the target project* (a bad file, an unresolvable import) become **diagnostics** and the run continues. *Problems with the invocation* (bad flag, bad config) raise `UsageError` or `ConfigError` → exit 2 with a friendly message. *Environment problems* (Docker missing, network down) → `ToolEnvironmentError` → exit 4. *Bugs* (any other exception) → exit 3 with a short message plus "rerun with `--debug` for a traceback". We never print a raw traceback to users unless `--debug` is set.

### D-033: Build backend is `hatchling`
**Decision:** `[build-system] requires = ["hatchling"]`. The version is read from `src/cartographer/__about__.py` (`[tool.hatch.version] path = …`).
**Why:** it's mature and widely documented, and it handles the src layout with no configuration. C8 compares it with `uv_build` and `setuptools` in a concept note. **If you disagreed:** `uv_build` is a fine alternative for pure-Python projects.

### D-034: Learning artefact locations
**Decision:** all learning material lives under `docs/learn/`:
`concepts/` (concept notes), `walkthroughs/`, `writeups/`, `comparisons/`, `predictions/`, `spikes/`, plus `glossary.md`, `faq.md` and the curriculum index `README.md`. File names are kebab-case slugs fixed by the curriculum index. A milestone never renames another milestone's note.

---

## Decisions added while writing the milestone specs (spec pass, 2026-11-03)

### D-035: Optional extra `[verify]` for `tstring verify`
**Decision:** `pyproject.toml` declares `[project.optional-dependencies] verify = ["hypothesis>=…"]`. `cartographer tstring verify` needs it. Without it, the command exits 4 with `install with: uv pip install "cartographer-py[verify]"`. Everything else works without Hypothesis.
**Why:** verifying a processor *is* property-based testing at runtime, and the extra keeps the default install small (D-006).

### D-036: `tstring verify` execution policy
**Decision:** `tstring verify` imports and calls a processor. For our own `cartographer.adapters.*` it needs no flag. For any other processor it needs `--execute`, the same opt-in as C2. See C5 §5.3.

### D-037: Shared analysis helpers live in `core`
**Decision:** `core/qualnames.py` (qualified-name resolution), `core/suppressions.py` (suppression comments) and `core/filtering.py` (the filtering pipeline) are built in C3 but live in `core`, because C1, C2, C4 and C5 use them and `core` must not import `rules`. `core/filtering.apply_filters` *composes* M0's `core/selection.py` with suppressions (C3 §6.7). `api.py` applies it to every Python-source command, **exactly once** (D-046). `core/edits.py` (applying `Edit`s to text, built in C2) is shared by C2 and C5.

### D-038: Injection findings are C3 rules
**Decision:** CRT501–CRT505 are implemented as C3 `Rule` subclasses, so `cartographer check` reports them too. `tstring find` is `check` with `--select CRT5` preset plus a C5-specific payload. `RuleContext.report()` accepts `fix: Fix | None`.

### D-039: `workflow_dispatch` inputs are trusted by default (C7)
**Decision:** only users with write access can trigger `workflow_dispatch`, so its inputs are not treated as attacker-controlled. `ci.untrusted-dispatch-inputs = true` flips that. `workflow_call` and composite-action inputs inherit taint from their caller (C7 §6.4.3).

### D-040: C6 never extracts archives to the host disk
**Decision:** C6 validates every archive entry and reads members **into memory** with hard size caps. The only exception is the `--extract-to DIR` debug option, which uses our checks plus `tarfile`'s `filter="data"`. The Docker sandbox receives the wheel on **stdin** and returns JSON-lines results on **stdout**, with no bind mounts. The fallback, if S-06 shows stdin transport is unreliable on Docker Desktop for Windows, is `docker create` + `docker cp` into a container before it starts.

### D-041: Per-finding severity
**Decision:** a rule may compute severity per finding when its spec says so (CRT701 and CRT702 do). The "Default" column in 03 §6 is then the most common case. `[tool.cartographer.severity]` overrides always win.

### D-042: The 1.0.0 gate
**Decision:** C8 releases `1.0.0` only if Final acceptance (C8 §Final acceptance) and the other C8 release conditions pass. Otherwise it releases `0.8.0` and records the gaps in the C8 write-up.

### D-043: Feature config sections are registered through `cli/sections.py`
**Decision:** `core.config.load_config(section_types=…)` validates every `[tool.cartographer.<section>]` table **eagerly**, so a typo in any section fails fast. `core` can't import feature packages, so the mapping (`"graph": "cartographer.graph.config:GraphConfig"`, …) is injected from `cli/sections.py`. Feature `config.py` modules must stay import-light (stdlib + `core` only). See M0 §6.9.

### D-044: Codes have a status
**Decision:** every code in 03 §6 is registered in M0 with `status = PLANNED`. A milestone flips its codes to `IMPLEMENTED` and must add their explanations. Only `IMPLEMENTED` codes require explanations (04 §8). Selecting a planned code is allowed, and it never fires.

### D-045: `startup pth` reports absolute paths
**Decision:** `.pth` files live in an interpreter's `site-packages`, outside the project root, so `startup pth` diagnostics use absolute posix paths (and absolute `file://` URIs in SARIF). It is the only exception to 02 §4.2.

---

## Decisions added after the cross-spec review (spec pass, 2026-11-03)

### D-046: Diagnostics are filtered exactly once, in `api.py`
**Decision:** analyzers, including `rules.run_rules`, return **raw** diagnostics (default severities, nothing dropped). `cartographer.api` applies the filtering pipeline **once** per command: `core.selection` in M0, which becomes `core.filtering.apply_filters` from C3 on. `cli/main.py` never filters; it only renders and computes the exit code from the already-filtered diagnostics.
**Why:** filtering twice makes every suppression consumed by the first pass look "unused" to the second (false CRT005), and duplicates CRT004.

### D-047: Selection = user selection ∩ command scope
**Decision:**
- Every command declares a **scope**: the set of codes it can produce. Examples: `scan` = CRT001–003; `graph` = CRT0xx + CRT1xx; `startup analyze` = CRT0xx + CRT201–204; `startup measure` = CRT0xx + CRT206; `startup compare` = CRT0xx; `startup pth` = CRT205; `check` = CRT0xx + CRT3xx + CRT501–505 + all registered plugin codes; `tstring find` = CRT0xx + CRT501–505; `tstring verify` = CRT506; `typecov` = CRT0xx + CRT4xx; `depdiff` = CRT001–003 + CRT6xx (unparseable files *inside artefacts* still get CRT001–003); `ci` = CRT7xx + CRT004/005; `report` runs each section with **that section's own** scope and filters each one once. Milestone specs hold the authoritative per-command lists (`api.SCOPES`, M0 §6.7).
- `effective = resolve(select) ∩ scope(command) − resolve(ignore)`. `select` defaults to `("CRT",)`. Default-off codes are only enabled by their exact code or name.
- **Plugin codes** (CRT9xx) are registered with `core.codes.register_external(CodeInfo)` by `rules/plugins.py`. Commands that load plugins resolve the selection **after** loading them, so `--select CRT901` works and SARIF gets plugin rule metadata. Until plugins exist (M0–C2), selection resolves immediately.
- An unknown selector is still an error (UsageError/ConfigError), but it's checked against the **whole** registry (including plugins once loaded), not against the scope. `graph --select CRT301` is valid and reports nothing.

### D-048: Dogfooding always analyses the repo root
**Decision:** every self-analysis run (CI dogfood jobs, acceptance criteria, tests) uses root `.`: `cartographer graph .`, `check .`, `typecov . --fail-under N`, `ci .`, `report .`. The repo's own `pyproject.toml` contains (from M0 phase 1):
```toml
[tool.cartographer]
exclude = ["tests/fixtures/**", ".corpus/**", "benchmarks/generated/**"]
```
**Why:** with root `src/`, our `pyproject.toml` (layer contracts, thresholds) isn't read. Without the exclude, fixture projects (which contain deliberate errors) would fail the dogfood jobs.

### D-049: `report` never imports `api`
**Decision:** the layering is `cli → api → report → feature packages → adapters/output → core`. `report` calls feature packages through their public `__init__` exports. `api.build_report` imports `report` lazily. C1's dogfood layer contract encodes this order.

### D-050: Untrusted text is escaped before display; artefacts can't suppress findings
**Decision:** `core.diagnostics.display_text(s: str) -> str` escapes control characters (including newlines and ANSI escape sequences), lone surrogates and trailing dots/spaces (`\n` becomes `\x0a`, and so on). Every string that comes from untrusted input (archive member names, index JSON, YAML values, target-file text) passes through it before going into `Diagnostic.message`, `help` or `Location.path`. The raw value goes into `data` (JSON-escaped by `json.dumps`). **Suppression comments inside downloaded artefacts (C6) are never honoured**, because a malicious package must not be able to hide its own findings.

### D-051: Suppressions come from per-path providers
**Decision:** `core.filtering.apply_filters(diagnostics, config, *, selection, suppressions: SuppressionProvider)`, where
```python
class SuppressionProvider(Protocol):
    def index_for(self, path: str) -> SuppressionIndex | None: ...
```
C3 builds `PythonSuppressionProvider` (tokenize-based, for `.py`/`.pyi` under the project). C7 builds `YamlSuppressionProvider`. Paths containing `!` (archive members, D-050) always get `None`. `SuppressionIndex` maps line numbers to suppressed codes and records which entries were used (for CRT005). Each provider documents its own line-matching rules: Python uses logical lines, and YAML uses "same line or the line directly above" (03 §5). C3's rule that a comment-only line is CRT004 applies to Python only.

### D-052: One corpus-execution harness
**Decision:** `scripts/corpus_startup.py` is the **only** way corpus code is executed (C2 acceptance, C8 Final acceptance F2). It:
1. builds an image `FROM python:3.15-slim` (spike S-06) that installs the corpus repo's **dependencies only**, as binary wheels (`pip install --only-binary=:all: --no-deps -r <pinned list>`). It never installs or builds the corpus project itself, so none of the project's build code runs, even at build time when the network is on;
2. copies the corpus checkout into the container (`docker create` + `docker cp`, no bind mounts);
3. runs `cartographer startup compare --execute` inside the container with exactly these flags: `--network none --read-only --tmpfs /tmp:rw,size=256m --cap-drop ALL --security-opt no-new-privileges --pids-limit 256 --memory 1g --cpus 2 --user 65534:65534`;
4. copies the JSON result out and removes the container.
The pinned dependency list comes from each corpus entry's `startup_requirements` field in `corpus/corpus.toml` (C2 phase 7).
`startup compare` adds the corpus source roots to `sys.path` itself, so no install is needed.

### D-053: `typecov --fail-under` implies `--fail-on warning`
**Decision:** CRT405 is a warning, so a threshold gate would never fail under the default `--fail-on error`. When `--fail-under` (or `typecov.fail-under`) is set and the user didn't pass `--fail-on` explicitly, `typecov` uses `--fail-on warning`.

### D-054: Console-script target
**Decision:** both `cartographer` and `carto` point to `cartographer.cli.main:main`, with signature `main(argv: Sequence[str] | None = None) -> int`. The console-script wrapper calls `sys.exit(main())`. Tests call `main([...])` directly.

### D-055: Doctest collection over `src/`
**Decision:** `src/conftest.py` sets `collect_ignore` / `collect_ignore_glob` so that `--doctest-modules` skips `cartographer/adapters/*` on Python < 3.14 and **always** skips `cartographer/depdiff/sandbox/*` (container-only scripts that must never be imported on the host). Sandbox scripts also guard all their work with `if __name__ == "__main__":`. Ruff uses `per-file-target-version` so test files named `test_*_py314.py` / `test_*_py315.py` are linted with the right grammar.
