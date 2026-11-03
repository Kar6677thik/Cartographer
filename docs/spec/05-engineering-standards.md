# 05 — Engineering standards

> How code is written, tested, checked and merged. These apply to every milestone. Documentation rules are in [04](04-documentation-standard.md).

---

## 1. Tooling (all run through `uv`)

| Purpose | Tool | Command |
|---|---|---|
| Environment + deps | `uv` (lockfile `uv.lock` committed) | `uv sync` |
| Run anything in the env | `uv run` | `uv run cartographer --version` |
| Lint + format | `ruff` | `uv run ruff check .` / `uv run ruff format .` |
| Type-check | `mypy --strict` on `src/` (tests: non-strict) | `uv run mypy` |
| Tests | `pytest` + `hypothesis` + `pytest-cov` | `uv run pytest` |
| Docs checks | scripts in `scripts/` (04 §8) | `uv run python scripts/dev.py docs` |
| Everything CI runs | `scripts/dev.py` | `uv run python scripts/dev.py all` |

`scripts/dev.py` is a small cross-platform task runner (argparse + `subprocess.run`). It exists so the same commands work in PowerShell, bash and CI, with no Makefile, which Windows lacks by default. Subcommands: `lint`, `format`, `types`, `test`, `docs`, `bench`, `all`.

## 2. Code style

- **Formatting:** `ruff format`, line length **100**.
- **Lint rules** (`[tool.ruff.lint]`): `select = ["E", "F", "W", "I", "N", "UP", "B", "SIM", "RUF", "PL", "PT", "D"]`, Google docstring convention (`[tool.ruff.lint.pydocstyle] convention = "google"`), `target-version = "py313"` (D-005). The few justified ignores are listed in `pyproject.toml`, each with a comment.
- **Typing:** every function signature fully annotated. `mypy --strict` passes on `src/`. mypy runs with `python_version = "3.15"`, so version-gated 3.14+ modules (`cartographer.adapters`) are checked, plus a second CI pass with `--python-version 3.13` to check the floor. Use modern syntax available in 3.13: `list[int]`, `X | None`, PEP 695 generics (`def first[T](xs: list[T]) -> T`), `type` aliases (`type JSONValue = …`). **`Any` is allowed only with a comment explaining why** (C4 measures our own `Any` usage, so it's dogfooding).
- **Naming:** modules `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE`. Private helpers start with `_`.
- **Imports:** absolute (`from cartographer.core.source import SourceFile`). Relative imports only inside a feature package's own modules. No wildcard imports. Heavy optional imports (LibCST, PyYAML) are listed in the module's `__lazy_modules__` (D-005) so `cartographer --version` stays fast. C2 measures exactly that. `__lazy_modules__` does nothing before 3.15, so **CLI command modules also import heavy feature code inside their `run()` function**, which keeps 3.13/3.14 startup fast too (C2 §6.12).
- **Data:** prefer `@dataclass(frozen=True, slots=True)` and `enum` to dicts and strings. Dicts are for JSON boundaries only.
- **Functions** do one thing. Pure functions (no I/O) wherever possible, with I/O pushed to the edges (CLI, fetchers).
- **No global mutable state** apart from the registries (rules, renderers, config sections), which are populated at import time and documented as such.
- **Paths:** `pathlib.Path` everywhere internally, converted to posix strings only for output (D-020). Never build paths by string concatenation.
- **Subprocesses:** always pass a **list** of arguments (never `shell=True`), always set `timeout=`, always `check=False` with explicit handling, always capture with `text=True, encoding="utf-8", errors="replace"`. Tests in C5 actually flag `shell=True`, so we'd be caught by our own tool.

## 3. Testing

### 3.1 Layout and markers
```
tests/unit/<pkg>/test_<module>.py     # fast, pure, no subprocess
tests/integration/test_cli_<cmd>.py   # runs cli.main(argv) in-process; a few via subprocess
tests/property/test_<topic>.py        # Hypothesis (may also live next to unit tests)
tests/docs/                           # documentation checks (04 §8)
tests/acceptance/                     # corpus runs (marked)
```
**Test files containing t-string literals** (or other 3.14+/3.15+ syntax) are named `test_*_py314.py` / `test_*_py315.py`, and `conftest.py` excludes them from collection on older interpreters with `collect_ignore_glob`. A skip marker can't help here, because the file wouldn't even parse.

Markers (registered in `pyproject.toml`; `--strict-markers`):

| Marker | Meaning | Runs by default? |
|---|---|---|
| `slow` | > 2 s | yes locally, yes in CI |
| `network` | needs internet (C6 live PyPI) | **no** (`-m network` to opt in) |
| `docker` | needs Docker daemon (C6 sandbox) | **no** (`-m docker`) |
| `corpus` | needs `.corpus/` cloned (acceptance) | **no** (`-m corpus`) |
| `execute` | runs target code via subprocess (C2 measure) | yes, but only on our own fixtures |
| `requires_py314` / `requires_py315` | auto-skip on older interpreters (D-005) | — |

### 3.2 Coverage
- Line + branch coverage via `pytest-cov`. **Gate: ≥ 90 % for `core/`, ≥ 85 % overall.** CI fails below that.
- Coverage isn't the goal. Every spec acceptance criterion must map to at least one named test. Milestone specs list "Test plan" items with IDs (`T-C1-07`), and the test's docstring cites the ID.

### 3.3 Property-based testing (Hypothesis)
- Every hand-built algorithm (D-007) has at least one property test against an oracle or an invariant.
- Profiles in `tests/conftest.py`: `dev` (100 examples), `ci` (500 examples, `deadline=None`), `thorough` (5,000 examples, run manually or nightly). Select with `--hypothesis-profile`.
- Failing examples are reproduced with the `@example(...)` decorator and kept as regression tests.
- A concept note (`property-based-testing`, M0) explains strategies, shrinking and how to read a failure.

### 3.4 Golden-file tests (CLI output)
- `tests/golden/<command>/<case>.<fmt>` holds the expected output. The `golden` fixture (hand-written in `conftest.py`) compares actual and expected output, after stripping `meta`, normalising `\r\n` to `\n`, and normalising paths to posix.
- In text output, the duration in the summary line `(N.NN s)` is normalised to `(X s)`.
- `uv run pytest --update-golden` rewrites the files. The diff must then be reviewed in the PR, because that review *is* the test.

### 3.5 Fixture projects
- `tests/fixtures/projects/<name>/` are miniature repos. **They are data. They are never imported or executed** (except C2 `execute` fixtures, which are clearly named `exec_*`).
- `conftest.py` excludes `tests/fixtures` from collection (`collect_ignore_glob`), so pytest never imports fixture code.
- **Exception:** `tests/fixtures/plugins/` (C3), `tests/fixtures/processors/` (C5) and `tests/fixtures/annotations_runtime/` (C4, run in a subprocess by S-14/T-C4-25) are *our own* code. Tests import, install or run them deliberately. They are still excluded from collection.
- Every fixture has a `README.md` (04 §3.5).

### 3.6 Determinism
- Outputs are sorted (D-017). Tests that depend on dict ordering or set iteration are bugs.
- Hypothesis runs record their seed in CI logs. Tests never depend on the current time or locale. Time comes from an injectable clock where needed (C2 measurements, C6 timeouts).

## 4. Continuous integration (`.github/workflows/ci.yml`, built in M0)

| Job | Matrix | Steps |
|---|---|---|
| `lint` | ubuntu, 3.15 | `ruff check`, `ruff format --check` |
| `types` | ubuntu, 3.15 | `mypy` |
| `docs` | ubuntu, 3.15 | doc checks (04 §8) |
| `test` | {windows-latest, ubuntu-latest} × {3.13, 3.14, 3.15, 3.15t} | `pytest --hypothesis-profile=ci --cov` |
| `dogfood` (C1+) | ubuntu, 3.15 | Always on root `.` (D-048): `cartographer graph .` must show 0 cycles and 0 layer violations. From C3: `check .`. From C4: `typecov . --fail-under <N>`. From C7: `ci .`. Moves to its own `dogfood.yml` with SARIF upload in C8 |

CI hardening (we practise what C7 preaches, and C7 will audit this very file):
- All third-party actions pinned to a **full commit SHA** with a `# vX.Y.Z` comment.
- Top-level `permissions: contents: read`.
- `actions/checkout` with `persist-credentials: false`.
- No `pull_request_target`. No `${{ github.event.* }}` inside `run:`. Values pass through `env:` instead.

## 5. Dependencies and supply chain (for *our* project)

- Runtime deps are pinned with a **lower bound only** in `pyproject.toml` (libraries should not pin exactly). Exact versions are locked in `uv.lock` for development and CI.
- Adding a runtime dependency requires a decision record (D-006).
- `uv lock --upgrade` happens deliberately in its own PR, never mixed with feature work. C6 is then run on the changed packages (dogfooding).

## 6. Performance budgets

Measured on the dev machine with Python 3.15, using synthetic projects from `scripts/gen_synthetic_project.py` (deterministic, seeded). Benchmarks live in `benchmarks/` and run with `scripts/dev.py bench`. They are **not** part of CI pass/fail, because CI machines are too noisy, but the results are recorded in milestone write-ups.

| Operation | Project size | Budget |
|---|---|---|
| `cartographer --version` | — | < 150 ms wall time (lazy imports keep it fast) |
| Discover + parse all files | 2,000 files | < 4 s |
| `graph` | 2,000 modules / 10,000 edges | < 6 s total, < 500 MB peak RSS |
| `check` (all C3 rules) | 2,000 files | < 8 s |
| `tstring find` | 2,000 files | < 10 s |

Missing a budget isn't a failure in itself. It must be written up (why, and what would fix it). The C4 mypyc experiment uses these benchmarks.

## 7. Security practices while developing

- Never run code from `.corpus/` or downloaded packages on the host (D-013). Acceptance runs that must execute corpus code (C2 startup win, C8 Final acceptance F2) use `scripts/corpus_startup.py`, which runs them only inside a `--network none` Docker container.
- Cartographer's own scripts are never placed in, or run from, directories containing untrusted files. Subprocesses touching such files use `python -I`.
- No secrets in the repo. TestPyPI publishing uses Trusted Publishing, so no API tokens exist at all (C8).
- `tarfile` extraction always uses `filter="data"` *and* our own checks (C6), because defence in depth means not trusting a single layer.

## 8. Definition of Done (applies to every phase and milestone)

A phase or milestone is done only when **all** of these are true:

- [ ] All acceptance criteria in its spec pass, each mapped to a named test (`T-…` IDs).
- [ ] `scripts/dev.py all` passes locally. CI is green on the full matrix.
- [ ] Coverage gates met.
- [ ] Documentation layers 1–3 done for a phase. Layers 1–5 done for a milestone (04 §1).
- [ ] Glossary and FAQ updated, and curriculum index ticked.
- [ ] `cartographer explain` text written for every new code.
- [ ] `CHANGELOG.md` updated. Version bumped at milestone end (D-010).
- [ ] Any new decision recorded in `01-decisions.md`. Any spec deviation fixed in the spec itself.
- [ ] Owner has reviewed the PR's "What you'll learn" section.
