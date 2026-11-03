# C8: Ship (packaging, publishing, combined report, final acceptance)

> **Status:** Approved spec, revision 1 (2026-11-03). Parts marked **Provisional** depend on a spike in [08](../08-spikes-and-risks.md) or on facts to confirm while writing the concept notes.
> **Size:** M · **Version at end:** 1.0.0 (if [Final acceptance](#final-acceptance) passes; otherwise 0.8.0, §6.3) · **Depends on:** all earlier milestones · **Research:** §2.11 (Trusted Publishing, attestations), §5 C8 row ("uv, pytest + Hypothesis, wheels for 3.13–3.15t, Trusted Publishing with attestations, Cartographer running on its own CI") and §5 "Done when".
> **Packages/files:** `pyproject.toml`, `src/cartographer/report/`, `src/cartographer/cli/commands/report.py`, `.github/workflows/{dogfood,release}.yml`, `scripts/{check_dist,check_release_version,verify_provenance,final_acceptance}.py` (`final_acceptance.py` only collects evidence; corpus code runs only through `scripts/corpus_startup.py`, D-052), `acceptance/`

---

## 1. Summary

C8 turns Cartographer from "code in a repo" into **a released tool**, and checks that it meets the project's goal. It has four parts:
1. **Packaging:** a correct `pyproject.toml`, a pure-Python wheel and an sdist (D-030) whose contents are checked by tests, and a reproducible build.
2. **A combined report:** `cartographer report` runs every static analysis once and writes one deterministic Markdown document with an executive summary.
3. **Publishing like the research recommends:** a tag-triggered GitHub Actions release workflow that builds without secrets, smoke-tests the wheel on Windows and Ubuntu across 3.13–3.15t, and publishes to **TestPyPI** with **Trusted Publishing** and **attestations**. Real PyPI needs your explicit approval (D-011). The workflow has to pass our own `cartographer ci` with zero findings.
4. **Final acceptance:** a scripted run against pinned real repositories proving goal **G2** (one real import cycle, one startup win, one injection sink with a working rewrite, one dependency or CI risk).

## 2. Why this matters

- **The research's lesson about publishing (§2.11):** Ultralytics shipped malicious releases *through* its legitimate publishing workflow. Attestations prove *where* a release was built, so the workflow itself has to be locked down: no secrets in build jobs, no caches in release jobs, pinned actions, an approval gate. Our release workflow is built to that standard, and C7 checks it.
- **PyPI in 2025:** over 50,000 projects use Trusted Publishing, and only 17 % of uploads carry attestations. Publishing with them, and verifying them using our own C6 code, puts the project in the better group.
- **Packaging is where many Python bugs live:** a file missing from the wheel, a wrong `requires-python`, an entry point that points nowhere. Tests that open the built wheel catch these before users do.
- **"Done when" (research §5):** the whole project's success criterion is checked here, with evidence, not asserted.

## 3. Read before starting

### 3.1 Concept notes
Already written and needed here: `project-layout-and-pyproject` and `virtual-environments-and-uv` (M0), `git-and-github-actions-basics` (M0), `wheels-and-sdists`, `hashing-and-integrity` and `pypi-and-provenance` (C6), `github-actions-model` and `ci-attack-patterns` (C7), `sarif-and-machine-output` (M0).

Written in this milestone (owner C8, curriculum Stage 8): `packaging-and-build-backends`, `versioning-and-releases`, `trusted-publishing` (builds on `pypi-and-provenance`).

### 3.2 Prediction questions (`docs/learn/predictions/C8.md`)
1. What do you expect to find inside our wheel? Should `tests/` be in it? Should `docs/`?
2. What's the difference between a *build frontend* (`uv build`) and a *build backend* (`hatchling`)?
3. If you build the wheel twice from the same commit, will the two files be byte-identical? What could make them differ?
4. Trusted Publishing has no API token. How does PyPI know the upload really came from our workflow?
5. Why build in one job and publish in another, rather than doing both in one job?
6. Why does TestPyPI exist, and why can't we re-upload `1.0.0` after a mistake?
7. When installing our package from TestPyPI, why is it dangerous to let *all* packages come from TestPyPI? (Hint: anyone can upload anything there.)
8. What should the executive summary of a code-analysis report contain so that a busy reader acts on it?
9. Of the four "Done when" criteria, which do you expect to be hardest to show on a *real* repository, and why?
10. Do you expect the free-threaded build (3.15t) to need any change in Cartographer? Why or why not?

## 4. Scope

### 4.1 In scope
- Final `pyproject.toml` metadata, entry points, `py.typed`, wheel/sdist content rules and their tests, reproducible builds.
- `cartographer report` (Markdown + JSON).
- `.github/workflows/dogfood.yml` (Cartographer on itself, with SARIF upload to GitHub code scanning).
- `.github/workflows/release.yml` (build → smoke → TestPyPI → verify).
- Owner instructions for TestPyPI Trusted Publisher and GitHub environment setup.
- Final acceptance on the corpus, with recorded evidence. Version 1.0.0 (or 0.8.0) and the changelog.

### 4.2 Out of scope (and why)
| Out | Why |
|---|---|
| Publishing to real PyPI without explicit approval | D-011: it's public and effectively permanent. It's a gated optional phase (P6) |
| Compiled (mypyc) wheels | D-030: pure wheel only. Stretch S8-1 |
| Conda / Homebrew / standalone binaries | Not part of the Python packaging lesson |
| Docs website (Sphinx/MkDocs) | Docs are Markdown on GitHub, which renders them well. Stretch S8-3 |
| SBOM generation, signed git tags | Good practice, not essential to the lesson. Stretch S8-2 |

## 5. User-facing behaviour

### 5.1 Installing (README section written in P1, finalised in P5)
```powershell
# from TestPyPI (pre-release testing). Dependencies come from the real PyPI, see §6.6 for why
uv venv; uv pip install libcst pyyaml
uv pip install --no-deps --index-url https://test.pypi.org/simple/ cartographer-py==1.0.0
uv run cartographer --version
# cartographer 1.0.0 (Python 3.15.2, win32)
```
As a tool (once on real PyPI, if approved): `uv tool install cartographer-py` puts `cartographer` and `carto` on `PATH`.

### 5.2 `cartographer report`
```
cartographer report [PATH] [--sections LIST] [--startup-measurements FILE]
                    [--depdiff PKG OLD NEW] [--timestamp] [--format markdown|json] [-o FILE]
```
- `--format` defaults to `markdown` for this command. `text` and `sarif` → `UsageError` (use the individual commands for those).
- `--sections`: comma-separated subset of `graph,startup,check,typecov,tstring,ci,depdiff`. The default is all **static** sections: `graph,startup,check,typecov,tstring,ci`. `depdiff` is included only when `--depdiff` is given.
- `startup` in the report is **static only** (`startup analyze`), because the report never executes code (D-013). Measured numbers can be merged in with `--startup-measurements FILE`, where `FILE` is the JSON output of a `startup compare` run you did separately (for example inside a container, §Final acceptance).
- `--timestamp` adds a generated-at line. Without it the report is byte-for-byte deterministic.

Example skeleton (normative layout; golden test `tests/golden/report/report_demo.md` on fixture `tests/fixtures/projects/report_demo/`):
```markdown
# Cartographer report: report-demo

| | |
|---|---|
| Root | `.` |
| Cartographer | 1.0.0 |
| Analysed with Python | 3.15 |
| Target version | 3.15 |
| Python files | 9 |
| Workflow files | 1 |

## Executive summary

| Area | Errors | Warnings | Info | Headline |
|---|---|---|---|---|
| Import graph | 0 | 1 | 1 | 1 cycle (3 modules); suggested cut: demo.c → demo.a |
| Startup | 0 | 0 | 2 | 1 lazy-import candidate; 1 import-time side effect |
| Rules | 0 | 1 | 0 | 1 blocking call inside async def |
| Typing | 0 | 0 | 2 | 61 % of functions fully annotated |
| Injection (t-strings) | 0 | 1 | 0 | 1 SQL sink; 1 automatic rewrite available |
| CI workflows | 0 | 1 | 1 | 1 unpinned action |

### Top findings

1. **CRT101** import cycle of 3 modules: demo.a → demo.b → demo.c → demo.a (`demo/a.py:1:1`)
2. **CRT301** blocking call time.sleep() inside async def fetch (`demo/net.py:7:9`)
…

## 1. Import graph
…per-section content (§6.9.3)…

## Appendix A: all findings
| Location | Code | Severity | Message |
|---|---|---|---|
| `demo/a.py:1:1` | CRT101 | warning | import cycle of 3 modules: demo.a → demo.b → demo.c → demo.a |

## Appendix B: how to read this report
- Every code has a full explanation: run `cartographer explain CRT101`.
- …

<!-- generated by cartographer 1.0.0 -->
```

### 5.3 Exit codes for `report`
The usual rules (03 §3) apply to the **union** of all section diagnostics. A section that fails gets a "⚠ This section failed: <message>" paragraph, and the report is still written in full. The exit code then follows the failure's class, the same as for the individual command: a `ToolEnvironmentError` (network unreachable, Docker missing) → **4**, any other unexpected exception (a bug) → **3**. If several sections fail, the highest of those codes wins (4 over 3).

## 6. Design

### 6.1 `pyproject.toml` (normative content; M0 created a minimal version, and C8 finalises it)
```toml
[build-system]
requires = ["hatchling>=1.27"]          # PEP 639 licence metadata (Provisional: confirm min version in P1)
build-backend = "hatchling.build"       # D-033

[project]
name = "cartographer-py"                # D-003
dynamic = ["version"]
description = "Maps unfamiliar Python codebases: import cycles, startup cost, risky patterns, typing health, injection sinks, dependency and CI risks."
readme = "README.md"
requires-python = ">=3.13"              # D-004
license = "MIT"                         # SPDX expression (PEP 639), D-012
license-files = ["LICENSE"]
authors = [{ name = "Kar6677thik" }]
keywords = ["static-analysis", "imports", "lazy-imports", "t-strings", "supply-chain", "github-actions", "learning"]
classifiers = [
  "Development Status :: 4 - Beta",
  "Environment :: Console",
  "Intended Audience :: Developers",
  "Operating System :: OS Independent",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3 :: Only",
  "Programming Language :: Python :: 3.13",
  "Programming Language :: Python :: 3.14",
  "Programming Language :: Python :: 3.15",
  "Programming Language :: Python :: Free Threading :: 2 - Beta",   # Provisional: validated by T-C8-02
  "Topic :: Security",
  "Topic :: Software Development :: Quality Assurance",
  "Typing :: Typed",
]
dependencies = [
  "libcst>=<min version from S-03>",
  "PyYAML>=6.0",
]

[project.optional-dependencies]
verify = ["hypothesis>=<current at P1>"]     # D-035: only `tstring verify` needs it

[dependency-groups]                     # PEP 735; dev-only, never in the wheel's metadata (D-006)
dev = [
  "pytest>=…", "pytest-cov>=…", "hypothesis>=…",
  "ruff>=…", "mypy>=…",
  "networkx>=…",                        # test oracle only (D-007)
  "jsonschema>=…",                      # SARIF schema validation
  "trove-classifiers>=…",               # T-C8-02
]

[project.scripts]
cartographer = "cartographer.cli.main:main"
carto = "cartographer.cli.main:main"

[project.urls]
Homepage = "https://github.com/Kar6677thik/Cartographer"
Documentation = "https://github.com/Kar6677thik/Cartographer/tree/main/docs"
Source = "https://github.com/Kar6677thik/Cartographer"
Issues = "https://github.com/Kar6677thik/Cartographer/issues"
Changelog = "https://github.com/Kar6677thik/Cartographer/blob/main/CHANGELOG.md"

[tool.hatch.version]
path = "src/cartographer/__about__.py"

[tool.hatch.build.targets.wheel]
packages = ["src/cartographer"]

[tool.hatch.build.targets.sdist]
include = ["src/", "tests/", "docs/", "scripts/", "corpus/", "README.md", "LICENSE", "CHANGELOG.md", "pyproject.toml", "uv.lock"]
exclude = [".corpus/", "**/__pycache__/", "acceptance/"]
```
Why each choice is made is explained in the concept note `packaging-and-build-backends`. For example: why the sdist includes tests (downstream packagers such as Linux distributions run them) while the wheel doesn't.

### 6.2 Artefact content rules (`scripts/check_dist.py` + `tests/packaging/test_artifacts.py`)
`check_dist.py DIST_DIR` opens the built files with **C6's `ArchiveReader`** (API in C6 §6.6.2: `ArchiveReader.open(...)`, `.members`, `.anomalies`, `.iter_files()`) (dogfooding: our own hostile-archive checks run on our own release, and any CRT606 fails the check) and asserts:

**Wheel** (`cartographer_py-<v>-py3-none-any.whl`; exactly one wheel, and the tag must be `py3-none-any`):
| Rule | Check |
|---|---|
| W1 | contains `cartographer/__init__.py`, `cartographer/__about__.py`, `cartographer/__main__.py`, `cartographer/py.typed`, `cartographer/api.py` |
| W2 | contains the package data: `cartographer/depdiff/sandbox/Dockerfile`, `runner.py`, `probe.py` |
| W3 | contains no `tests/`, `docs/`, `scripts/`, `.corpus/`, `__pycache__/`, `*.pyc` |
| W4 | `METADATA`: `Name: cartographer-py`, `Version` = `__about__.__version__`, `Requires-Python: >=3.13`, `License-Expression: MIT`, `Provides-Extra: verify`, and `Requires-Dist` lines that are **exactly**: the unconditional `libcst>=…` and `PyYAML>=6.0`, plus `hypothesis>=…; extra == "verify"`. No dev-group package (pytest, networkx, …) may appear (**Provisional:** `Metadata-Version` 2.4 and `License-Expression`, confirmed against the hatchling version in P1) |
| W5 | `entry_points.txt` has `[console_scripts]` with `cartographer` and `carto`, both = `cartographer.cli.main:main` |
| W6 | `RECORD` is complete and every hash matches (ArchiveReader's `record-mismatch` check) |
| W7 | every `.py` file in the wheel parses with `ast.parse` under the **running** interpreter. CI runs this under 3.13, which enforces D-005 on the shipped code |
| W8 | `LICENSE` is present under `*.dist-info/licenses/` (PEP 639 location; Provisional with W4) |

**sdist** (`cartographer_py-<v>.tar.gz`; exactly one):
| Rule | Check |
|---|---|
| S1 | contains `pyproject.toml`, `README.md`, `LICENSE`, `CHANGELOG.md`, `src/cartographer/__init__.py`, `tests/conftest.py` |
| S2 | contains no `.corpus/`, `acceptance/`, `.venv/`, `__pycache__/`, `.git/` |
| S3 | `PKG-INFO` version matches the wheel's |
| S4 | **C6 CRT609 check against our own wheel reports nothing** (every wheel `.py` has a matching sdist file) |

**Reproducibility:** with `SOURCE_DATE_EPOCH` set to the last commit's timestamp (`git log -1 --format=%ct`), two consecutive `uv build` runs produce **byte-identical** wheels (compare SHA-256). **Provisional:** hatchling's reproducible-build support is confirmed in P1. If sdists aren't reproducible, only the wheel is required to be.

### 6.3 Version, changelog, and the 1.0.0 decision
- Release candidates for rehearsal: `1.0.0rc1`, `1.0.0rc2`, … (PEP 440 pre-release; tags `v1.0.0rc1`). *Why:* TestPyPI, like PyPI, never accepts the same filename twice, so every rehearsal needs a fresh version. The concept note `versioning-and-releases` explains this.
- **1.0.0 is released only if all of these are true:** every row of the 07 §3 progress tracker is ticked for C1–C7; all four [Final acceptance](#final-acceptance) criteria pass; CI is green on the full matrix; the dogfood workflow has zero `error`-severity findings. **Otherwise** release `0.8.0`, list the gaps in the changelog and the write-up, and leave 1.0.0 for later. This avoids a "1.0" that isn't true.
- `CHANGELOG.md`: Keep a Changelog format. Each version has `Added`/`Changed`/`Fixed`/`Security` subsections, and the 1.0.0 entry lists every command. Compare-links at the bottom (`[1.0.0]: https://github.com/Kar6677thik/Cartographer/compare/v0.7.0...v1.0.0`).
- `scripts/check_release_version.py TAG`: strips a leading `v` and requires an exact string match with `__about__.__version__`. Mismatch → exit 1 with both values shown.

### 6.4 Dogfood workflow (`.github/workflows/dogfood.yml`)
From C8 on, this workflow **replaces** the `dogfood` job in `ci.yml` (05 §4), which is removed in the same PR. It runs on `push` to `main` and on `pull_request` (**never** `pull_request_target`).
```yaml
name: dogfood
on:
  push:
    branches: [main]
  pull_request:
permissions:
  contents: read
jobs:
  dogfood:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write        # SARIF upload to code scanning
    steps:
      - uses: actions/checkout@<sha> # v4.x.y
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@<sha> # vX.Y.Z
        with:
          enable-cache: false
      - run: uv sync --frozen
      # Root is always "." (D-048): our pyproject.toml (layer contracts, typecov.fail-under,
      # exclude = ["tests/fixtures/**", …]) is only read when the root is the repo root.
      - run: uv run cartographer graph . --fail-on warning
      - run: uv run cartographer check . --fail-on warning --format sarif -o check.sarif
      - run: uv run cartographer typecov . --format sarif -o typecov.sarif   # fail-under from config ⇒ --fail-on warning (D-053)
      - run: uv run cartographer tstring find . --fail-on warning --format sarif -o tstring.sarif
      - run: uv run cartographer ci . --fail-on warning --format sarif -o ci.sarif
      - if: always() && github.event_name == 'push'
        uses: github/codeql-action/upload-sarif@<sha> # v3.x.y
        with:
          sarif_file: .
          category: cartographer
```
- `<sha>` placeholders are **never committed**. The implementer resolves each one to a full commit SHA (`git ls-remote https://github.com/<owner>/<repo> refs/tags/<tag>`, plus the peeled `^{}` line for annotated tags) and writes the tag in the trailing comment. The concept note `trusted-publishing` shows how.
- The SARIF upload only runs on `push`, because pull requests from forks don't get `security-events: write`. **Provisional:** confirm the exact `upload-sarif` inputs for a directory of several SARIF files, and adjust (one upload step per file is the fallback).
- The `--fail-on` gates encode project policy. Our own code must be clean of warnings for graph, check, tstring and ci. Typing coverage is gated by C4's `typecov.fail-under` in our `pyproject.toml`: because that threshold is set and the step passes no `--fail-on`, `typecov` uses `--fail-on warning` (D-053), so a CRT405 below the threshold fails the job.
- **Never pass `src` or `.github/` as the root** (D-048). With `src`, our `pyproject.toml` isn't read, and with `.github/`, `ci` finds no workflows and exits 2 (C7 §5.1).

### 6.5 Release workflow (`.github/workflows/release.yml`)
```yaml
name: release
on:
  push:
    tags: ["v*"]
permissions:
  contents: read
jobs:
  build:                                   # no secrets, no id-token, no cache
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<sha> # v4.x.y
        with:
          persist-credentials: false       # the default shallow clone still has HEAD's timestamp
      - uses: astral-sh/setup-uv@<sha> # vX.Y.Z
        with:
          enable-cache: false
      - name: Tag matches version
        env:
          TAG: ${{ github.ref_name }}      # via env, never pasted into the script (C7 CRT702)
        run: uv run --no-project python scripts/check_release_version.py "$TAG"
      - name: Build
        run: |
          export SOURCE_DATE_EPOCH="$(git log -1 --format=%ct)"
          uv build
      - run: uv run python scripts/check_dist.py dist/
      - uses: actions/upload-artifact@<sha> # v4.x.y
        with:
          name: dist
          path: dist/
          if-no-files-found: error

  smoke:
    needs: build
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest]
        python: ["3.13", "3.14", "3.15", "3.15t"]
    runs-on: ${{ matrix.os }}
    defaults:
      run:
        shell: bash
    steps:
      - uses: actions/download-artifact@<sha> # v4.x.y
        with:
          name: dist
          path: dist/
      - uses: astral-sh/setup-uv@<sha> # vX.Y.Z
        with:
          enable-cache: false
      - env:
          PY: ${{ matrix.python }}
        run: |
          uv venv --python "$PY" .smoke
          uv pip install --python .smoke dist/*.whl
          uv run --python .smoke --no-project cartographer --version
          uv run --python .smoke --no-project cartographer explain CRT101
          uv run --python .smoke --no-project python -c "import cartographer.api"

  publish-testpypi:
    needs: [build, smoke]
    runs-on: ubuntu-latest
    environment:
      name: testpypi
      url: https://test.pypi.org/p/cartographer-py
    permissions:
      id-token: write                      # the ONLY job with OIDC
    steps:
      - uses: actions/download-artifact@<sha> # v4.x.y
        with:
          name: dist
          path: dist/
      - uses: pypa/gh-action-pypi-publish@<sha> # v1.x.y
        with:
          repository-url: https://test.pypi.org/legacy/
          # Attestations are generated by default when using Trusted Publishing
          # (Provisional: confirm in the action's README for the pinned version; if not, set attestations: true)

  verify-testpypi:
    needs: publish-testpypi
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    defaults:
      run:
        shell: bash
    steps:
      - uses: astral-sh/setup-uv@<sha> # vX.Y.Z
        with:
          enable-cache: false
      - env:
          TAG: ${{ github.ref_name }}
        run: |
          VERSION="${TAG#v}"
          uv venv --python 3.15 .verify
          uv pip install --python .verify libcst pyyaml          # deps from REAL PyPI
          for i in 1 2 3 4 5; do                                 # TestPyPI's index can lag a little
            uv pip install --python .verify --no-deps --index-url https://test.pypi.org/simple/ \
              "cartographer-py==$VERSION" && break
            sleep 30
          done
          test "$(uv run --python .verify --no-project cartographer --version | cut -d' ' -f2)" = "$VERSION"
```
Rules for this file:
- **It must pass `cartographer ci . --fail-on info` with zero findings in `release.yml`** (and in `dogfood.yml` and `ci.yml`; A-C8-05). By construction: everything is pinned, there's a top-level `permissions: contents: read`, the checkout doesn't persist credentials, the release job has an environment, no job uses a cache (setup-uv `enable-cache: false`), and every `${{ }}` that reaches a script goes through `env:`.
- **Separation of duties:** `build` has no OIDC permission, so a compromised build step can't publish. `publish-testpypi` runs no project code at all: it only downloads the artefact and uploads it.
- The `smoke` job installs the **exact artefact** that will be published, not a rebuild.

### 6.6 Installing from TestPyPI safely (dependency confusion)
Anyone can upload any name to TestPyPI, including a fake `libcst`. If you install with TestPyPI as an index for *all* packages, a fake dependency could win. So:
1. Install dependencies from real PyPI first (`uv pip install libcst pyyaml`).
2. Install our package from TestPyPI with **`--no-deps`**.

The concept note `trusted-publishing` explains this "dependency confusion" class of attack, and the README install section (§5.1) follows the same pattern.

### 6.7 Verifying our own provenance (dogfood C6)
After a TestPyPI release, `scripts/verify_provenance.py VERSION` uses C6's `pypi.py` + `provenance.py` with `index-url = https://test.pypi.org` to fetch the Integrity API record for our wheel and sdist, and checks that:
- the status is `attested` for both files;
- the publisher is `repository = Kar6677thik/Cartographer`, `workflow = release.yml`, `environment = testpypi`.

It's run manually by the implementer after each rehearsal (it needs the network) and recorded in the write-up. **Provisional (S-08):** if TestPyPI doesn't serve the Integrity API, verify on the TestPyPI web page instead (each file's details show its provenance), record a screenshot path in the write-up, and note the limitation.

### 6.8 One-time setup the owner does by hand (web UI). Implementer: walk the owner through it, don't do it for them
These steps create **accounts and trust relationships**, so only you can do them. Labels in the web UIs may differ slightly. PyPI's "Trusted Publishers" documentation, including the page on creating a project with a pending publisher, is the authority.

**A. TestPyPI account**
1. Register at `https://test.pypi.org/account/register/`. TestPyPI is a **separate** site with separate accounts from pypi.org.
2. Verify your email and turn on two-factor authentication (Account settings).

**B. Pending Trusted Publisher** (lets the project be created on the first upload, with no token ever existing)
1. TestPyPI → your account menu → **Publishing**.
2. Under "Add a new pending publisher", choose **GitHub** and fill in:
   | Field | Value |
   |---|---|
   | PyPI project name | `cartographer-py` |
   | Owner | `Kar6677thik` |
   | Repository name | `Cartographer` |
   | Workflow name | `release.yml` |
   | Environment name | `testpypi` |
3. Save. The publisher shows as *pending* until the first successful upload.

**C. GitHub environment** (the approval gate CRT704 asks for)
1. GitHub → `Kar6677thik/Cartographer` → **Settings → Environments → New environment** → name `testpypi`.
2. **Required reviewers:** add yourself. Every publish then waits for your click.
3. **Deployment branches and tags:** "Selected branches and tags" → add a **tag** rule `v*`.

**D. The first rehearsal**
1. Tell the implementer that A–C are done. The implementer prepares `1.0.0rc1` and asks for your go-ahead before pushing the tag (D-009/D-011).
2. In GitHub → Actions → the `release` run → **Review deployments** → approve `testpypi`.
3. Open `https://test.pypi.org/project/cartographer-py/` → **Download files** → a file → check that the provenance/attestation details name `Kar6677thik/Cartographer` and `release.yml`.

### 6.9 `cartographer report` (`src/cartographer/report/`)

#### 6.9.1 Modules
| Module | Responsibility |
|---|---|
| `report/__init__.py` | `build_report(project, config, options) -> ReportResult` |
| `report/sections.py` | the `ReportSection` protocol and one adapter per feature, each calling that **feature package's public exports** (for example `cartographer.graph.build_import_graph`), **never `cartographer.api`** (D-049: `cli → api → report → features`; `api.build_report` imports `report` lazily) |
| `report/summary.py` | executive summary table, top-findings ranking |
| `report/markdown.py` | rendering + escaping (a renderer registered with `output` for format `markdown`) |
| `cli/commands/report.py` | wiring only |

#### 6.9.2 Contract between `report` and the features
```python
@dataclass(frozen=True, slots=True)
class SectionSummary:
    headline: str                         # one line, no trailing period, ≤ 100 chars
    rows: tuple[tuple[str, str], ...]     # key facts for the section body, e.g. ("Modules", "214")
    body_markdown: str                    # feature-specific details (tables), already escaped

class ReportSection(Protocol):
    key: str                              # "graph"
    title: str                            # "Import graph"
    def run(self, project: Project, config: Config) -> tuple[Result, SectionSummary]: ...
```
Each feature package exposes a `summarize(result) -> SectionSummary` function in its public `__init__`. If a milestone didn't provide one, C8 adds it to that feature package (allowed by the layering rule: `report` → every feature package, never `api`; 02 §3, D-049). The adapters build the `Project` **once** and pass it to every section, so each file is parsed once per report run (D-021).

**Filtering (D-046, D-047).** Because `report` bypasses `api`, it must do what `api` does, exactly once per section. Each adapter takes the feature's **raw** diagnostics and calls `core.filtering.apply_filters` once, with that section's command scope (D-047: the `graph` section uses `graph`'s scope, and so on) and the matching suppression provider (Python, or YAML for the CI section). The adapters never filter twice, and the features never filter at all. A test asserts that the report's per-section counts equal those of the individual commands on `report_demo`.

#### 6.9.3 Rendering rules
- **Section order** is fixed: graph, startup, check, typecov, tstring, ci, depdiff. Numbered headings `## 1. Import graph`, …, numbered only among the included sections.
- **Executive summary:** one row per included section, with counts per severity *after* `select`/`ignore`/suppressions, and the section's headline. A failed section shows `—` in the counts and `failed: <message>` as its headline.
- **Top findings:** all diagnostics sorted by `(-severity, section order, path, line, column, code)`, truncated to `report.top-findings` (default 10). Info-severity findings appear only if `report.include-info-in-top = true`.
- **Appendix A:** every diagnostic, in the standard sort order (02 §4.4).
- **Escaping:** in table cells, `|` → `\|`, newlines → a space, and backticks inside code spans are handled by choosing a longer backtick fence. Paths and code always appear in code spans. A Hypothesis test feeds random messages through the escaper and checks that the table keeps the same number of columns.
- **Determinism:** no timestamps (unless `--timestamp`), no durations, no absolute paths, sorted everything, and `\n` line endings. Running twice gives identical bytes, which a test checks across three different `PYTHONHASHSEED` values in subprocesses.
- **JSON format:** the standard envelope (02 §4.8). `payload = {"sections": [{"key", "title", "status": "ok"|"failed", "headline", "counts": {"error", "warning", "info"}, "rows"}]}`, and `diagnostics` = all of them.

#### 6.9.4 Edge cases
| # | Case | Behaviour |
|---|---|---|
| E1 | Project has no `.github/workflows` | CI section present: "No workflows found", zero counts. Unlike `cartographer ci` (exit 2, C7 §5.1), this is not an error in a report |
| E2 | Project has 0 Python files | Not an error. M0's `load_project` returns an empty project, and the report is written with every Python section present and showing "No Python files found" with zero counts. The CI section still runs if workflows exist. Exit 0 |
| E3 | A section raises | its block says "⚠ This section failed: …", the report is written, and the exit code follows §5.3 (4 for `ToolEnvironmentError`, else 3) |
| E4 | `--startup-measurements` file is invalid or from another project | `UsageError` → exit 2, before any analysis |
| E5 | `--depdiff` without network | that section fails per E3 with a `ToolEnvironmentError`, so the exit code is **4** (the same as `depdiff` itself, C6 §5.4), with a message suggesting `--offline` or dropping the section |
| E6 | Message contains `|` or a newline | escaped per §6.9.3 |

## 7. Diagnostics
C8 introduces **no new codes**. `report` aggregates the codes of the commands it runs. The `release.yml` and `dogfood.yml` files must produce **no** CRT7xx findings, and our code must produce no warnings for the gated commands (§6.4).

## 8. Configuration (`[tool.cartographer.report]`)
| Key | Type | Default | Meaning |
|---|---|---|---|
| `sections` | list[str] | `["graph", "startup", "check", "typecov", "tstring", "ci"]` | Default sections |
| `top-findings` | int 0–100 | 10 | Length of the Top findings list |
| `include-info-in-top` | bool | false | Allow info findings in Top findings |
| `title` | str \| null | null | Report title; default `[project] name` from `pyproject.toml`, else the directory name |

## 9. Phases & tasks

### P1: Packaging · branch `c8/packaging`
- [ ] Concept note `packaging-and-build-backends` (frontends vs. backends, PEP 517/621/639, hatchling vs. uv_build vs. setuptools compared on our project, what goes in wheels vs. sdists).
- [ ] Finalise `pyproject.toml` (§6.1). Confirm hatchling's PEP 639 and reproducibility support, and update the Provisional notes.
- [ ] `scripts/check_dist.py` (§6.2) using C6's `ArchiveReader`. `tests/packaging/test_artifacts.py` builds into a temp dir with `uv build` and runs the checks (marked `slow`).
- [ ] Reproducible-build test. Classifier validation (T-C8-02).
- [ ] README: install section, command table, links. 🖐 *Hands-on: run `uv build`, open the wheel with `python -m zipfile -l`, and compare what you see against rules W1–W8.*

### P2: `cartographer report` · branch `c8/report`
- [ ] `report/` modules (§6.9), `summarize()` functions for any feature missing one, the fixture `tests/fixtures/projects/report_demo/` (+ `README.md`), and the golden Markdown.
- [ ] Determinism and escaping tests.

### P3: Dogfood workflow · branch `c8/dogfood`
- [ ] `dogfood.yml` (§6.4) with real pinned SHAs. Remove the dogfood job from `ci.yml`. Update 05 §4 in the same PR.
- [ ] Fix any findings Cartographer reports on itself (each fix is part of this PR, or a separate PR if it's large).

### P4: Release workflow + TestPyPI rehearsal · branch `c8/release`
- [ ] Concept notes `versioning-and-releases` and `trusted-publishing` (OIDC in plain words, the build/publish split, attestations, dependency confusion).
- [ ] `release.yml` (§6.5), `scripts/check_release_version.py`, `scripts/verify_provenance.py`.
- [ ] `cartographer ci` on the new workflow gives zero findings (A-C8-05).
- [ ] **Owner:** §6.8 steps A–C. **Implementer, after the owner's go-ahead:** tag `v1.0.0rc1` → owner approves the deployment → run `verify_provenance.py` → record the results in the write-up.

### P5: Final acceptance and 1.0.0 · branch `c8/final`
- [ ] `scripts/final_acceptance.py` (evidence collection for F1–F4; F2 delegates to `scripts/corpus_startup.py`, the single harness of D-052, and contains no Docker code of its own), with evidence under `acceptance/final/`.
- [ ] `docs/learn/writeups/final-acceptance.md`.
- [ ] The 1.0.0 decision (§6.3), CHANGELOG, then the tag `v1.0.0` (owner go-ahead) → TestPyPI.
- [ ] C8 walkthrough, write-up and comparison. A **project retrospective** section in the write-up (what the whole journey taught).

### P6 (gated, optional): Real PyPI. Only with explicit owner approval in that session (D-011)
- [ ] Owner creates the pypi.org account + pending publisher (same fields as §6.8 B, environment `pypi`) and the GitHub environment `pypi` with required reviewers.
- [ ] Add a `publish-pypi` job to `release.yml`: `needs: verify-testpypi`, `if: vars.PUBLISH_TO_PYPI == 'true'`, `environment: pypi`, `id-token: write`, same downloaded artefacts, `pypa/gh-action-pypi-publish@<sha>` with the default repository. Re-run `cartographer ci` (zero findings).
- [ ] The owner sets the repository variable `PUBLISH_TO_PYPI=true` themselves.

### Stretch list
- S8-1 mypyc-compiled wheels for the C4 hot modules (needs `cibuildwheel` and a decision record, D-030).
- S8-2 SBOM (CycloneDX) as a release asset, and signed git tags.
- S8-3 Rendered docs site.

## 10. Test plan
| ID | What | Kind |
|---|---|---|
| T-C8-01 | Wheel rules W1–W8 and sdist rules S1–S4 on a fresh `uv build` | packaging (`slow`) |
| T-C8-02 | Every classifier is valid (against the `trove-classifiers` package, a dev-only dependency) | unit |
| T-C8-03 | Two builds with the same `SOURCE_DATE_EPOCH` give the same wheel SHA-256 | packaging (`slow`) |
| T-C8-04 | `check_release_version.py`: `v1.0.0` vs 1.0.0 ok; `v1.0.1` vs 1.0.0 fails; `1.0.0rc1` ok | unit |
| T-C8-05 | `report` on `report_demo` equals the golden Markdown | golden |
| T-C8-06 | `report` is byte-identical across three `PYTHONHASHSEED` values | integration (subprocess) |
| T-C8-07 | Markdown table escaping keeps the column count for random messages | Hypothesis |
| T-C8-08 | A failing section → report written + exit 3 (E3); invalid `--startup-measurements` → exit 2 (E4) | integration |
| T-C8-09 | `report --format text` → exit 2 | integration |
| T-C8-10 | `report` parses each file once (instrumented `SourceFile.tree` counter = number of files) | integration |
| T-C8-11 | `cartographer ci .` (root `.`, D-048) → zero findings at `--fail-on info` for `release.yml`, `dogfood.yml` and `ci.yml` | integration (dogfood) |
| T-C8-12 | The installed-wheel smoke test (the `smoke` job's commands) also runs locally against a temp venv | packaging (`slow`) |
| T-C8-13 | `report` on a directory with zero Python files writes a report with empty sections and exits 0 (E2) | integration |
| T-C8-14 | `report --depdiff …` with a transport that raises `ToolEnvironmentError` writes the report and exits 4 (E5); a section raising `RuntimeError` exits 3 (E3) | integration |
| T-C8-15 | Per-section counts in `report` equal the counts of the individual commands on `report_demo`, including a suppressed finding (filtering happens exactly once, D-046) | integration |
| T-C8-16 | Layering: `src/cartographer/report/**` contains no import of `cartographer.api` (checked by the C1 layer contract in the dogfood run and by a direct `ast` scan in this test) | unit |

## 11. Acceptance criteria
| ID | Criterion |
|---|---|
| A-C8-01 | `uv build` produces exactly one `py3-none-any` wheel and one sdist, and both pass `check_dist.py` (T-C8-01). |
| A-C8-02 | The wheel is reproducible (T-C8-03). |
| A-C8-03 | The `smoke` job is green on {ubuntu, windows} × {3.13, 3.14, 3.15, 3.15t}. Any 3.15t-on-Windows unavailability is handled per S-00 and documented. |
| A-C8-04 | A release candidate is on TestPyPI, published by `release.yml` through Trusted Publishing, with attestations whose publisher is `Kar6677thik/Cartographer` / `release.yml` / `testpypi` (§6.7 evidence in the write-up). |
| A-C8-05 | `cartographer ci .` reports **zero** findings (any severity) for `release.yml` and `dogfood.yml` (T-C8-11). |
| A-C8-06 | `verify-testpypi` passes: the TestPyPI-installed `cartographer --version` matches the tag. |
| A-C8-07 | `cartographer report` meets T-C8-05 … T-C8-10. |
| A-C8-08 | The dogfood workflow is green on `main`, with SARIF uploaded (findings visible in the repository's Security tab, or none). |
| A-C8-09 | [Final acceptance](#final-acceptance) passes all four criteria. Then the version is 1.0.0; otherwise 0.8.0 per §6.3. |
| A-C8-10 | Docs: the three Stage-8 concept notes ✅, README final, walkthrough, write-up (with the project retrospective), comparison. Every row in 07 §3 ticked. |
| A-C8-11 | Report correctness on edge cases and layering: T-C8-13 … T-C8-16 pass. |

### Final acceptance

This is the run that proves goal **G2** (00 §4): *"Pointed at a real mid-size repo, it surfaces at least one real cycle, one startup win, one injection-risky sink with a working rewrite, and one dependency or CI risk."*

**Inputs:** the repositories pinned in `corpus/corpus.toml` (selected in spike S-07, using the criteria in 08 §3), cloned into `.corpus/` by `scripts/fetch_corpus.py`. Each criterion may use a different repo. The *same* Cartographer build (the 1.0.0 candidate wheel, installed in a clean venv) is used for all of them.

**Safety:** corpus code is **never executed on the host** (D-013, 05 §7). Criteria 1, 3 and 4 are static. Criterion 2 executes imports, so it runs **only through `scripts/corpus_startup.py`**, the single corpus-execution harness defined in D-052 (also used by C2's acceptance). There is no second harness and no other set of Docker flags. In short, the harness:
1. builds an image `FROM python:3.15-slim` (S-06 Part A) containing **our** candidate wheel (trusted, our own code) and the corpus repo's **dependencies only**, installed as binary wheels (`pip install --only-binary=:all: --no-deps -r <pinned list>`). The corpus project itself is never installed or built, so none of its build code runs, not even during the image build when the network is on;
2. copies the pinned corpus checkout into a created container (`docker create` + `docker cp`, no bind mounts);
3. runs `cartographer startup compare --execute …` with exactly D-052's flags: `--network none --read-only --tmpfs /tmp:rw,size=256m --cap-drop ALL --security-opt no-new-privileges --pids-limit 256 --memory 1g --cpus 2 --user 65534:65534`. `startup compare` puts the corpus source roots on `sys.path` itself;
4. copies the JSON result out, then removes the container.
`scripts/final_acceptance.py` only calls the harness and stores its JSON under `acceptance/final/F2-startup/`.

**Choosing the F2 repo:** because only binary-wheel dependencies are installed, the F2 candidate must be importable from source with wheel-only dependencies (a pure-Python CLI is ideal). S-07 records this as a selection constraint.

| # | Criterion | Command(s) | Pass condition | Verification of "real" |
|---|---|---|---|---|
| F1 | **A real import cycle** | `cartographer graph .corpus/<repo> --format json` | ≥ 1 CRT101 | For one reported cycle, the evidence file lists every edge as `file:line` of the import statement, quoted from the repo at the pinned SHA. Implementer and owner both confirm each import exists and is executed when the module is imported (or document which edges are function-level/`TYPE_CHECKING` and that C1's default classification was respected). |
| F2 | **A startup win** | in the container: `cartographer startup compare --execute …` (C2's interface) | C2's comparison reports an improvement whose 95 % confidence interval for the time saved excludes zero, **and** the median saving is ≥ 5 % of the baseline | The evidence lists the lazy-import changes applied (as a diff), the interpreter (3.15.x), the run count, the median, the CI, and confirms the program still works: `<tool> --help` exits 0 with identical output in both variants, inside the container. |
| F3 | **An injection-risky sink with a working rewrite** | `cartographer tstring find .corpus/<repo>`; `cartographer tstring fix … --diff` (applied to a temp copy) | ≥ 1 CRT501/502/503 with an offered fix, and the rewrite passes the four checks below | `tests/acceptance/test_final_injection.py` (marker `corpus`): **(a)** the rewritten file parses with `ast.parse` on 3.15; **(b)** `tstring find` on the rewritten copy no longer reports that sink; **(c)** a *behavioural harness written in our test code* (it does **not** import corpus code) reproduces the original string-building expression and the rewritten t-string call with the same adapter, runs both against `sqlite3.connect(":memory:")` (or `shlex`/`html.parser` for shell/HTML sinks) with a seeded table and the payload `x' OR '1'='1`, and shows the original returns injected rows while the rewrite doesn't; **(d)** `cartographer tstring verify <adapter>` passes. |
| F4 | **A dependency or CI risk** | `cartographer ci .corpus/<repo>` and/or `cartographer depdiff <pkg> <old> <new>` on a real upgrade of a corpus dependency | ≥ 1 CRT70x or CRT60x finding judged a true positive | The evidence quotes the workflow lines (or the manifest evidence), explains the concrete risk in 2–4 sentences, and, for CI, records whether zizmor agrees (C7 A-C7-06). |

**Plus:** `cartographer report .corpus/<repo>` runs without a failed section on every corpus repo, and is byte-identical across two runs.

**Evidence format** (committed, deterministic: `meta` stripped, paths relative):
```
acceptance/final/
├── corpus.lock.toml                 # copy of corpus/corpus.toml with SHAs, as used
├── environment.md                   # OS, Docker version, Python versions, Cartographer wheel SHA-256
├── F1-cycle/
│   ├── command.txt                  # exact command(s)
│   ├── output.json                  # Cartographer JSON output (meta stripped)
│   └── verdict.md                   # PASS/FAIL, the verification table, quotes with file:line
├── F2-startup/ …                    # + compare.json, applied-changes.diff
├── F3-injection/ …                  # + rewrite.diff, pytest output
├── F4-risk/ …
└── reports/<repo>.md                # cartographer report per corpus repo
```
`docs/learn/writeups/final-acceptance.md` summarises it:
| Criterion | Repo @ SHA | Finding | Verdict | Evidence |
|---|---|---|---|---|
| F1 | … | CRT101 a → b → a | PASS | `acceptance/final/F1-cycle/verdict.md` |

If a criterion fails on every corpus candidate, do **not** quietly swap in a replica. Record FAIL, explain why, and apply the 0.8.0 rule (§6.3). A replica may be shown *in addition*, labelled as such (08 S-07 fallback).

## 12. Documentation deliverables
- **Concept notes** (owner C8): `packaging-and-build-backends`, `versioning-and-releases`, `trusted-publishing`. Musts:
  - `packaging-and-build-backends`: build our own project with `uv build` in a `pycon`-free walkthrough (shell blocks), then open the wheel in a `pycon` session with `zipfile`; a table of what each PEP (517, 518, 621, 639, 660) contributes.
  - `versioning-and-releases`: PEP 440 ordering examples (`1.0.0rc1 < 1.0.0 < 1.0.0.post1`) as a runnable `pycon` block using a tiny hand-written comparator (no `packaging` dependency); yanking vs. deleting.
  - `trusted-publishing`: a sequence diagram (Mermaid) of GitHub OIDC token → PyPI token exchange → upload → attestation; dependency confusion; why build and publish are separate jobs.
- **README** final: what it is, install, a quick start with three commands, links to docs/learn, the safety model in three bullets, and the name-clash note (D-003).
- **Walkthrough** `docs/learn/walkthroughs/C8.md`: the report pipeline end to end on `report_demo`; then the release pipeline as a diagram from tag push to TestPyPI, naming each job's permissions.
- **Write-up** `docs/learn/writeups/C8.md`: rehearsal log (what failed on rc1/rc2 and why); provenance verification output; final acceptance summary; **project retrospective** (for each milestone, one paragraph: what you understand now that you didn't before).
- **Comparison** `docs/learn/comparisons/C8.md`: compare our packaging and release setup with one well-run PyPA project that publishes with Trusted Publishing (candidates `pypa/pip-audit`, `pypa/twine`; confirm it uses Trusted Publishing before choosing). Questions: How do they structure release jobs? Do they pin actions? Do they test the built artefact before publishing? Run `cartographer ci` on their workflows and discuss the findings.

## 13. Reference implementations to compare after
| Reference | What to compare |
|---|---|
| A PyPA project's `release.yml` (chosen per §12) | job split, permissions, environment gates, pinning |
| `pypa/gh-action-pypi-publish` README | attestation defaults, recommended workflow shape |
| `pypa/sampleproject` | `pyproject.toml` conventions |
| PyPI's Trusted Publishers documentation | our §6.8 steps vs. the official ones |

## 14. Risks & open items
- **Provisional facts:** hatchling PEP 639/reproducibility specifics (P1); the attestation default in `gh-action-pypi-publish` (P4); TestPyPI Integrity API (S-08); `upload-sarif` multi-file input (P3); the free-threading classifier's validity (T-C8-02).
- **S-00:** 3.15t availability on Windows runners affects A-C8-03.
- **S-07:** corpus suitability drives Final acceptance. The FAIL path is defined, not hidden.
- **Owner availability:** P4/P5 need the owner for web-UI setup and deployment approvals, so plan those sessions together.
- **TestPyPI resets:** TestPyPI may occasionally be cleaned. If the project disappears, re-create the pending publisher (§6.8 B) and use a new rc number.

## 15. Exercises for the learner
1. Run `uv build` and list the wheel with `python -m zipfile -l dist/*.whl`. Find our two console scripts in `entry_points.txt`. *Hint:* it's in `cartographer_py-<v>.dist-info/`.
2. Change one docstring and rebuild. Does the wheel's SHA-256 change? Undo it and rebuild with the same `SOURCE_DATE_EPOCH`. Does the hash return to the original? *Hint:* `certutil -hashfile file SHA256` on Windows, or `hashlib`.
3. Read `release.yml` and, for each job, write down which permissions it has and why. Which job could a compromised `uv build` affect?
4. Run `cartographer ci` on `release.yml`, then deliberately add `cache: pip` to a publish step and run it again. Which code appears, and why does it matter for Ultralytics?
5. Open our package on TestPyPI and find the attestation. Which fields tell you the repository and workflow? What *doesn't* it tell you about the code?
6. Run `cartographer report` on a project of your own and read only the executive summary. Would you know what to fix first? Suggest one improvement to the report (and add it to the FAQ or open an issue).
