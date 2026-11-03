# 03 — CLI, configuration, output and diagnostic codes

> The *user-facing contract*. Milestone specs add detail to their own subcommand and config section. They must not change anything defined here without updating this file in the same PR.

---

## 1. Invocation

```
cartographer [GLOBAL OPTIONS] <command> [COMMAND OPTIONS] [PATH]
carto        …same…                      # alias (D-003)
python -m cartographer …same…            # via __main__.py
```

`PATH` defaults to the current directory. It is the **project root**, the directory containing the target's `pyproject.toml`. If `PATH` points *inside* a project, Cartographer does **not** search upwards for the root in v1. It uses `PATH` as given, which avoids surprises.

### 1.1 Global options (valid before or after the command name)

| Option | Default | Meaning |
|---|---|---|
| `--config FILE` | none | Use this TOML file (top-level keys, same schema as `cartographer.toml`) |
| `--format {text,json,sarif,…}` | `text` | Output format. Commands may add formats (`dot`, `mermaid`, `markdown`) |
| `--output FILE`, `-o FILE` | stdout | Write the result to a file (UTF-8, `\n` line endings) |
| `--select CODES` | from config, else the command's default selection | Comma-separated codes, names or prefixes: `CRT1,mutable-default-argument`. **Default-off** codes (e.g. CRT005) are only enabled by their exact code or name, never by a prefix. A command only ever reports codes in its **scope** (D-047): `effective = select ∩ scope − ignore`. So `--select CRT` (the default) means "everything this command can report" |
| `--ignore CODES` | from config | Same syntax. `ignore` wins over `select` |
| `--fail-on {info,warning,error,never}` | `error` | Lowest severity that makes the exit code 1 |
| `--target-version X.Y` | auto (§4.3) | Python version the *target* project runs on (D-004) |
| `-v` / `-vv` / `-q` | warning level | Logging verbosity (to stderr) |
| `--debug` | off | DEBUG logging + full tracebacks on internal errors |
| `--no-color` | auto | Disable ANSI colour. Colour is also off when stdout is not a TTY or the `NO_COLOR` env var is set |
| `--version` | — | Print `cartographer 0.1.0 (Python 3.15.2, win32)` and exit 0 |

> **Windows colour note:** modern Windows Terminal understands ANSI escape codes, but the legacy console needs "virtual terminal processing" switched on. `cli/main.py` enables it through `ctypes` (`SetConsoleMode` with `ENABLE_VIRTUAL_TERMINAL_PROCESSING`). If that fails, colour is silently turned off. The code must comment this, because it is non-obvious.

### 1.2 Commands

Each command's full behaviour lives in its milestone spec. This table is the inventory.

| Command | Milestone | Summary |
|---|---|---|
| `graph` | C1 | Build the import graph; report cycles, tangles, cut suggestions, layer violations; export DOT/Mermaid |
| `startup analyze` | C2 | Static: import-time side effects + lazy-import candidates |
| `startup measure` | C2 | **Executes** (`--execute`): parse `-X importtime` over N runs; tree + statistics |
| `startup compare` | C2 | **Executes**: measure eager vs. lazy (copy with lazy imports applied) on 3.15; report the win with a confidence interval |
| `startup pth` | C2 | Scan an interpreter's `site-packages` for `.pth` files with executable lines |
| `check` | C3 | Run the rule engine |
| `rules [CODE_OR_NAME]` | C3 | List all rules, or show one rule's metadata, options and explanation |
| `scan` | M0 | Discover and parse all files and report CRT001–CRT003. A debugging aid: "what does Cartographer see?" |
| `explain CODE` / `explain --list` | M0 (content grows) | Print the long explanation of any diagnostic code, or list all codes with their status. This is a teaching feature |
| `typecov` | C4 | Annotation coverage + `Any` leaks |
| `tstring find` | C5 | Find dynamic strings reaching SQL/shell/HTML sinks |
| `tstring fix` | C5 | Rewrite to t-strings (`--diff` default, `--write` to apply) |
| `tstring verify` | C5 | Property-test a processor (ours or third-party) for structure preservation |
| `depdiff` | C6 | Compare two versions of a package: capabilities, provenance, archive anomalies (`--dynamic` = Docker sandbox) |
| `ci` | C7 | Audit `.github/workflows` and local composite actions |
| `report` | C8 | Run everything static and produce one Markdown report |

## 2. Output formats

| Format | Applies to | Spec |
|---|---|---|
| `text` | all | Human-readable, grouped by file, ends with the summary line defined in §2.1 |
| `json` | all | The envelope in [02 §4.8](02-architecture.md#48-json-envelope) |
| `sarif` | all commands that produce diagnostics | SARIF **2.1.0**: one `run`, `tool.driver.rules` built from the code registry, `columnKind: "unicodeCodePoints"`, `originalUriBaseIds.SRCROOT` = root |
| `dot` | `graph` | Graphviz DOT (C1) |
| `mermaid` | `graph` | Mermaid `flowchart` text, which renders directly in GitHub Markdown (C1) |
| `markdown` | `report`, `startup`, `typecov` | C8, C2, C4 |

### 2.1 Text format layout (normative)
```
pkg/a.py:3:1: CRT101 [warning] import cycle of 3 modules: pkg.a → pkg.b → pkg.c → pkg.a
  help: cut the edge pkg.c → pkg.a (1 name used, only inside functions)
  related: pkg/b.py:5:1 (pkg.b imports pkg.c)

Found 0 errors, 1 warning, 0 info in 12 files (0.41 s).
```
- **Summary line** (always printed, even with zero findings): `Found <E> error(s), <W> warning(s), <I> info in <N> <noun> (<secs> s).` Use the singular for exactly 1 (`1 error`). `info` never changes. The noun is `files` by default, and commands may use their own (`artifacts` for `depdiff`, `workflows` for `ci`). Normative details: M0 §5.4.
- First line: `path:line:col: CODE [severity] message`. Editors and terminals can click this form.
- `help:` and `related:` lines are indented two spaces.
- Colour (if enabled): severity word coloured (error red, warning yellow, info cyan). The code is bold.

## 3. Exit codes

| Code | Meaning |
|---|---|
| 0 | Ran successfully, and no diagnostic is at or above `--fail-on` |
| 1 | Ran successfully, and at least one diagnostic is at or above `--fail-on` |
| 2 | Usage or configuration problem (`UsageError`, `ConfigError`, `ProjectError`) |
| 3 | Internal error, which is a bug. The message says to rerun with `--debug` and file an issue |
| 4 | Environment problem (`ToolEnvironmentError`): Docker unavailable, network unreachable, interpreter not found |
| 130 | Interrupted with Ctrl+C (`KeyboardInterrupt`). Print `Interrupted.` and nothing else |

## 4. Configuration

### 4.1 Where it comes from
Precedence is in D-015. Locations:
- `<root>/pyproject.toml` → table `[tool.cartographer]`
- `<root>/cartographer.toml` → top-level keys. If both files exist, `cartographer.toml` wins **entirely**, with no merging, and an INFO log says so.
- `--config FILE` → top-level keys. Overrides both.

Keys use **kebab-case** in TOML (`fail-on`). Python attributes use snake_case (`fail_on`). The loader converts between them.

### 4.2 Core keys (M0)

```toml
[tool.cartographer]
source-roots   = []            # [] = auto-detect (C1 §Source roots). Paths relative to root.
include        = ["**/*.py", "**/*.pyi"]
exclude        = []            # ADDED to the default excludes (D-020)
default-exclude = true         # false = do not apply the built-in exclude list
target-version = "auto"        # "auto" | "3.13" | "3.14" | "3.15"
select         = ["CRT"]       # codes / names / prefixes
ignore         = []
fail-on        = "error"
max-file-size-kb = 2048        # bigger files are skipped with CRT003

[tool.cartographer.severity]   # override the default severity per code
CRT303 = "error"

[tool.cartographer.per-file-ignores]   # glob → codes
"tests/**" = ["CRT303"]
"**/migrations/**" = ["CRT1"]
```

### 4.3 `target-version = "auto"`
1. If `[project] requires-python` exists, take its **lowest** allowed version (`>=3.12` → 3.12, `~=3.11` → 3.11). Versions below 3.13 are clamped to "3.13" with an INFO log, because advice only exists for ≥3.13.
2. Otherwise use the running interpreter's `major.minor`.
Parsing `requires-python` uses a small hand-written parser for the common operators (`>=`, `>`, `==`, `~=`, `,`). Anything it cannot understand falls back to step 2 with a DEBUG log. A concept note explains PEP 440 specifiers.

### 4.4 Feature sections (each defined by its milestone)
| Table | Milestone |
|---|---|
| `[tool.cartographer.graph]` | C1 (layers, tangle threshold, edge kinds to include) |
| `[tool.cartographer.startup]` | C2 (thresholds, runs, known-side-effect modules) |
| `[tool.cartographer.rules]` | C3 (per-rule options, e.g. extra blocking calls) |
| `[tool.cartographer.typecov]` | C4 (fail-under, public-only) |
| `[tool.cartographer.tstring]` | C5 (sinks, adapters, paramstyle) |
| `[tool.cartographer.depdiff]` | C6 (cache dir, docker image, timeouts) |
| `[tool.cartographer.ci]` | C7 (trusted actions allow-list, release job patterns) |
| `[tool.cartographer.report]` | C8 |

### 4.5 Validation
- Config is loaded into frozen dataclasses (`core/config.py`). Each feature section is its own dataclass, registered by the feature package, so `core` doesn't need to know every feature.
- Type mismatches (`fail-on = 3`) → `ConfigError: tool.cartographer.fail-on: expected one of "info", "warning", "error", "never", got 3`.
- Unknown keys → `ConfigError` with a "did you mean" suggestion (D-015).

## 5. Suppression comments (implemented in C3, honoured by every Python-source command)

```python
import foo  # cartographer: ignore[CRT101]
x = f"..."  # cartographer: ignore[CRT501, CRT502]
# cartographer: ignore-file[CRT303]      ← anywhere in the first 20 lines: whole file
```
- A bare `# cartographer: ignore` without codes is **not allowed**. It produces `CRT004 invalid-suppression`, because blanket ignores hide problems.
- Unknown codes in a suppression → `CRT004`.
- `CRT005 unused-suppression` (info, off unless selected) reports suppressions that matched nothing.
- Comments are found with `tokenize` (not regex on raw lines) so that `# cartographer:` inside a string literal is never mistaken for a comment.
- For C7 (YAML), the same syntax works in YAML comments: `# cartographer: ignore[CRT705]` on the line itself or the line above. Lines inside block scalars (`run: |`) are shell script, not YAML comments, and are never treated as suppressions.

## 6. Diagnostic code registry

The single source of truth for codes. `core/codes.py` must match this table, and a test enforces that. Every code is registered in M0 with status `planned` and becomes `implemented` in its milestone (D-044). Where a milestone spec says so, a rule computes severity **per finding** (e.g. CRT701, CRT702), and the Default column is then the most common case (D-041). Each code has a name, a default severity, the milestone that implements it, and a long explanation (shown by `cartographer explain CODE`). The explanation is written as the code is implemented and must follow the "explain" template in [04 §5](04-documentation-standard.md#5-cartographer-explain-texts).

### CRT0xx: core
| Code | Name | Default | Meaning |
|---|---|---|---|
| CRT001 | `syntax-error` | warning | File could not be parsed (with a version hint, D-004) |
| CRT002 | `decode-error` | warning | File could not be decoded (bad PEP 263 encoding / bytes) |
| CRT003 | `file-too-large` | info | File skipped: larger than `max-file-size-kb` |
| CRT004 | `invalid-suppression` | warning | Malformed suppression comment or unknown code (C3) |
| CRT005 | `unused-suppression` | info, off by default | Suppression matched nothing (C3) |

### CRT1xx: import graph (C1)
| Code | Name | Default | Meaning |
|---|---|---|---|
| CRT101 | `import-cycle` | warning | Modules form a cycle (an SCC with more than one module, or a self-loop) |
| CRT102 | `import-tangle` | warning | An SCC with ≥ `graph.tangle-threshold` modules (default 10) |
| CRT103 | `unresolved-internal-import` | warning | An import that points *into* the project but matches no module |
| CRT104 | `relative-import-beyond-top` | error | `from ... import x` climbs above the top-level package |
| CRT105 | `suggested-cut` | info | An edge whose removal breaks a cycle, with reasoning |
| CRT106 | `layer-violation` | error | An import breaks a configured layer contract |

### CRT2xx: startup / lazy imports (C2)
| Code | Name | Default | Meaning |
|---|---|---|---|
| CRT201 | `import-time-side-effect` | info | Module-level code that does work when imported (calls, I/O, registration) |
| CRT202 | `lazy-import-candidate` | info | Import that could be lazy, with an estimated saving if measured |
| CRT203 | `lazy-import-defeated` | warning | A `lazy import`ed name is used at module level, so it is imported eagerly anyway |
| CRT204 | `lazy-import-registration-risk` | warning | Lazily importing a module whose import registers plugins or handlers |
| CRT205 | `pth-executable-line` | warning | A `.pth` file contains an executable `import` line (PEP 829 context; exact 3.15 deprecation status is Provisional, S-11) |
| CRT206 | `slow-import` | info | Measured import above `startup.slow-threshold-ms` |

### CRT3xx: rules (C3)
| Code | Name | Default | Meaning |
|---|---|---|---|
| CRT301 | `blocking-call-in-async` | warning | Known blocking call (e.g. `time.sleep`, `requests.get`) inside `async def` |
| CRT302 | `finally-control-flow` | warning | `return`/`break`/`continue` that leaves a `finally` block (PEP 765) |
| CRT303 | `mutable-default-argument` | warning | `def f(x=[])` and similar |

### CRT4xx: typing health (C4)
| Code | Name | Default | Meaning |
|---|---|---|---|
| CRT401 | `unannotated-public-function` | info | Public function missing parameter or return annotations |
| CRT402 | `explicit-any` | info | `Any` written explicitly in an annotation |
| CRT403 | `any-leak` | warning | A typed module's public API exposes `Any` or unannotated values |
| CRT404 | `bare-type-ignore` | info | `# type: ignore` without an error code |
| CRT405 | `coverage-below-threshold` | warning | Module annotation coverage below `typecov.fail-under` |
| CRT406 | `type-checking-import-at-runtime` | warning | A name imported only under `TYPE_CHECKING` is needed at runtime (PEP 649/749 context) |

### CRT5xx: t-strings / injection (C5)
| Code | Name | Default | Meaning |
|---|---|---|---|
| CRT501 | `sql-injection-risk` | warning | Dynamic string reaches a SQL sink |
| CRT502 | `shell-injection-risk` | warning | Dynamic string reaches a shell sink |
| CRT503 | `html-injection-risk` | warning | Dynamic string reaches an HTML sink |
| CRT504 | `template-flattened` | warning | A t-string `Template` is converted to plain `str` before reaching a sink |
| CRT505 | `no-safe-rewrite` | info | Risky sink found, but no automatic rewrite is safe (e.g. a dynamic table name) |
| CRT506 | `processor-verification-failed` | error | `tstring verify` found a structure-changing input |

### CRT6xx: dependency diff (C6)
| Code | Name | Default | Meaning |
|---|---|---|---|
| CRT601 | `new-capability` | warning | New version gains a capability (network, subprocess, exec, …) |
| CRT602 | `install-time-code` | error | Code that runs at install/build time gained capabilities |
| CRT603 | `pth-file-added` | error | New version ships a `.pth` file |
| CRT604 | `provenance-lost` | error | Old version had attestations; new one does not |
| CRT605 | `publisher-changed` | error | Trusted Publisher identity (repo / workflow) changed |
| CRT606 | `archive-anomaly` | error | Path traversal, symlink, bomb or duplicate entries in an archive |
| CRT607 | `obfuscation-signal` | warning | Encoded payload + `exec`/`eval`, high-entropy blobs |
| CRT608 | `new-runtime-behavior` | warning | Sandboxed import produced audit events the old version did not |
| CRT609 | `sdist-wheel-mismatch` | warning | Wheel contains code not present in the sdist |

### CRT7xx: CI workflows (C7)
| Code | Name | Default | Meaning |
|---|---|---|---|
| CRT701 | `dangerous-trigger` | error/warning | `pull_request_target` / `workflow_run` (error if it checks out PR code) |
| CRT702 | `template-injection` | error | Attacker-controlled `${{ … }}` expanded inside `run:` (incl. via composite actions) |
| CRT703 | `cache-in-release-job` | warning | Cache restored in a job that publishes artefacts |
| CRT704 | `missing-environment-gate` | warning | Publishing job without `environment:` |
| CRT705 | `unpinned-action` | warning | `uses:` not pinned to a full 40-character commit SHA |
| CRT706 | `excessive-permissions` | warning | No `permissions:` block, or `write-all` |
| CRT707 | `persisted-credentials` | info | `actions/checkout` without `persist-credentials: false` |
| CRT708 | `unparseable-workflow` | warning | Workflow file could not be parsed |

### CRT9xx: reserved for third-party plugins (C3)
