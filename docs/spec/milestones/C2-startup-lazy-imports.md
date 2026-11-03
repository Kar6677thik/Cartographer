# C2: Startup profiler and lazy-import advisor

> **Size:** L · **Version at end:** `0.2.0` · **Depends on:** C1 (module index, resolver, graph, usage analysis) · **Unblocks:** C8
> **Incident:** PEP 810 lazy imports, shipped in Python 3.15 (research §2.5)
> **Spikes in this milestone:** S-01, S-02 (phase 1), S-15 C2 part (phase 2), S-11 (phase 6), S-06 Part A (phase 7)
> **Command:** `cartographer startup {analyze,measure,compare,pth}` · **Codes:** CRT201–CRT206 · **Config:** `[tool.cartographer.startup]`

---

## 1. Summary

C2 answers **"why does this program take so long to start, and what can be made lazy?"** in four parts:

1. **`startup analyze`** (static and safe) reads the project and reports **import-time side effects**: code that does real work merely because a module was imported (network calls, file reads, plugin registration, monkey-patching). It also reports **lazy-import candidates**: imports whose names are only used inside functions, so the import could be postponed until it is actually needed. On Python 3.15+ targets it suggests the new `lazy import` syntax (PEP 810). On older targets it suggests the backwards-compatible `__lazy_modules__` list. It also catches mistakes in code that *already* uses lazy imports.
2. **`startup measure --execute`** runs `python -X importtime` repeatedly in a subprocess and turns the output into an import tree with medians and **confidence intervals**, so you can see where the time really goes.
3. **`startup compare --execute`** makes a **copy** of the project, applies the advisor's lazy imports to the copy, measures original and copy alternately on Python 3.15, and reports the saving with a confidence interval. This is "measure the real win" from the research.
4. **`startup pth`** inspects an interpreter's `site-packages` for `.pth` files that run code at every startup.

Measuring executes code, so it only happens with `--execute`, and only on code you trust (D-013).

## 2. Why this matters

### The incident (research §2.5)
Command-line tools and services often spend most of their startup time **importing modules they won't use in this run**. `mytool --help` might import a database driver, a plotting library and an HTTP client just because some command *might* need them. PEP 810 reports **50–70 % faster startup** and **30–40 % memory savings** from lazy imports, citing Meta, Hudson River Trading and PySide. Python 3.15 ships the syntax:

```python
lazy import json                 # json is bound to a proxy; the real import happens on first use
lazy from json import dumps
```
plus a backwards-compatible form, `__lazy_modules__ = ["json"]`, and global controls (`-X lazy_imports`, `PYTHON_LAZY_IMPORTS`, `sys.set_lazy_imports_filter()`). The exact forms are *Provisional until spike S-01*.

### The gotchas (why an *advisor* is needed, not "make everything lazy")
- **Errors move.** A broken import fails at *first use*, possibly deep inside a request handler, not at startup.
- **Registration breaks.** Many libraries register plugins, handlers or signal hooks *when imported*. If nothing ever uses the module's names, a lazy import of it **never runs**, and the registration silently never happens.
- **Laziness can be defeated.** If a lazily imported name is used at module level (in a decorator, a default argument, a base class), it is imported immediately anyway. You get the complexity and none of the win.
- **`lazy from m import X` still runs all of `m`** when `X` is first used.
- **Startup measurements are noisy.** One run tells you almost nothing. You need repeated runs, a robust statistic (the median) and an honest uncertainty (a confidence interval).

### What you will learn
That **a module is a script that runs once**; what counts as a side effect; how `-X importtime` works and how to read it; how lazy imports work and where they break; how `site.py` and `.pth` files run code before yours does; how to run subprocesses safely; and how to measure performance honestly (warm-up, interleaving, medians, bootstrap confidence intervals).

## 3. Read before starting

### 3.1 Concept notes
- From earlier milestones: `import-system`, `circular-imports`, `type-checking-guard` (C1); `ast-basics`, `text-and-encodings` (M0).
- Written in this milestone: `module-execution-and-side-effects`, `lazy-imports`, `importtime`, `site-and-pth-files`, `subprocess`, `measuring-performance`.

### 3.2 Prediction questions
Answer in `docs/learn/predictions/C2.md` before phase 1.

1. When you `import json`, does Python run code inside `json/__init__.py`? If you import it a second time in the same program, does that code run again?
2. Guess what fraction of `cartographer --version`'s run time is spent importing modules: 10 %, 50 % or 90 %?
3. You write `lazy import json` and never use `json`. Is the json module ever imported?
4. A module `plugins.py` registers itself into a dictionary when imported. You change `import plugins` to `lazy import plugins` in your app and never mention `plugins` again. What happens to the registration?
5. You run the same startup measurement 20 times. Will all 20 numbers be the same? Will the first run be faster or slower than the others, and why?
6. How many runs do you think you need before a median startup time is trustworthy: 3, 20 or 1,000?
7. `lazy from big_module import tiny_function`. When `tiny_function` is first called, does Python run *all* of `big_module` or only the part that defines `tiny_function`?
8. Can a file in `site-packages` make Python run code every time *any* Python program starts, even one that never imports anything?
9. Your measurement says "saved 5 ms, 95 % CI [−2, 12] ms". Did lazy imports help?
10. Why would we copy the project before trying lazy imports, instead of editing it in place?

## 4. Scope

### 4.1 In scope
- An `-X importtime` parser for every format observed by S-02 (3.13, 3.14, 3.15, and `-X importtime=2` if it exists).
- A static import-time side-effect classifier with a precise taxonomy (§6.3), giving CRT201.
- A lazy-import advisor (§6.5), giving CRT202, with fixes that depend on target version. Detection of existing lazy imports (§6.6), giving CRT203/CRT204.
- A measurement runner with warm-up, interleaving, an injectable clock, median and bootstrap CIs (§6.7, §6.8), giving CRT206.
- `startup compare` on a copy, with keyword-lazy edits on 3.15 (§6.9).
- `.pth` / `.start` scanning (§6.10), giving CRT205.
- Text, JSON, SARIF (now including **fixes**) and Markdown outputs.
- A shared `core/edits.py` (`apply_edits`), which C5 reuses.
- Dogfooding: Cartographer's own startup path (§6.12).

### 4.2 Out of scope (and why)
| Not in C2 | Why |
|---|---|
| Rewriting the user's project in place | Compare works on a **temporary copy** only. `analyze` emits fixes, but never applies them (NG8) |
| Memory measurement (the "30–40 % memory" claim) | Startup *time* is enough for one milestone. Peak RSS could be a stretch item (it needs `psutil` or platform APIs) |
| Profiling beyond imports (Tachyon, cProfile) | That's Kiln territory (K6). We only parse `-X importtime` |
| Detecting `__init_subclass__` / metaclass registries statically | Not visible without type inference. Documented limitation, worked around via `registration-modules` config |
| Measuring corpus repos on the host | D-013: corpus code runs only inside the Docker harness (§9 phase 7) |
| Auto-detecting the entry module of an arbitrary project | Too heuristic. `--module`/`--entry` are explicit |

## 5. User-facing behaviour

### 5.1 Commands
```
cartographer startup analyze [PATH] [--entry MODULE] [--importtime FILE]
                                    [--format {text,json,sarif,markdown}]
cartographer startup measure [PATH] --python EXE --module MODULE --execute
                                    [--runs N] [--warmup N] [--depth N] [--min-ms X] [--include-startup]
                                    [--format {text,json,markdown}]
cartographer startup compare [PATH] --python EXE --module MODULE --execute
                                    [--runs N] [--warmup N] [--all-lazy] [--include-low-confidence]
                                    [--format {text,json,markdown}]
cartographer startup pth [--python EXE] [--format {text,json,sarif}]
```
- `--module` must match `^[A-Za-z_]\w*(\.[A-Za-z_]\w*)*$`, else `UsageError`. It's interpolated into a `-c` program, so it is **validated, never trusted** (§6.7).
- `--python` must point to a runnable interpreter, else `ToolEnvironmentError` (exit 4). For `pth`, the default is `sys.executable`.
- **Without `--execute`**, `measure` and `compare` exit **2** without running anything:
  ```text
  cartographer: error: "startup measure" runs the import-time code of "slowcli.cli" in a subprocess.
    hint: only do this for code you trust, then re-run with --execute
  ```
- **With `--execute`**, a warning goes to stderr before anything runs: `cartographer: warning: running the import-time code of "slowcli.cli" with C:\…\python.exe`.
- `compare` requires the interpreter to be **≥ 3.15**, otherwise exit 4: `startup compare needs Python 3.15 or newer for lazy imports (got 3.14 from C:\…\python.exe)`.
- `--entry MODULE` (analyze): the program's main module, used to check whether a candidate stays eagerly imported through other paths (§6.5 criterion C5).
- `--importtime FILE` (analyze): a JSON file written by `startup measure --format json`. It adds measured savings to candidates and enables `min-saving-ms` filtering.
- `--all-lazy` (compare): also measure the original with the global lazy-imports switch (`-X lazy_imports=all` or whatever S-01 confirms) as an **upper bound**. If S-01 shows no such switch, the flag is removed from the spec.
- Result `command` names: `"startup analyze"`, `"startup measure"`, `"startup compare"`, `"startup pth"`.

### 5.2 Worked example fixture: `exec_c2_slowcli`
The `exec_` prefix means the tests **execute** this fixture (05 §3.5). It contains only harmless code, written by us.
```
tests/fixtures/projects/exec_c2_slowcli/
├── README.md                 # what it simulates, why executing it is safe, expected findings
├── pyproject.toml            # requires-python = ">=3.15"
└── src/slowcli/
    ├── __init__.py           # (empty)
    ├── cli.py                # import slowcli.plugins          ← imported only for its side effects
    │                         # from slowcli import report       ← used only inside main()
    │                         # def main(): return report.render()
    ├── report.py             # import slowcli._heavy             ← used only inside render()
    │                         # def render(): return slowcli._heavy.table()
    ├── _heavy.py             # import time
    │                         # time.sleep(0.06)                  ← simulates a 60 ms import
    │                         # def table(): return "…"
    ├── plugins.py            # from slowcli.registry import register
    │                         # @register
    │                         # def export_csv(): ...
    └── registry.py           # REGISTRY = {}
                              # def register(f): REGISTRY[f.__name__] = f; return f
```

### 5.3 `startup analyze`
```text
PS> uv run cartographer startup analyze tests/fixtures/projects/exec_c2_slowcli
src/slowcli/_heavy.py:2:1: CRT201 [info] import-time side effect (call): time.sleep(...) runs when slowcli._heavy is imported
src/slowcli/cli.py:2:1: CRT202 [info] import of "slowcli.report" could be lazy: only used inside functions
  help: change it to `lazy from slowcli import report` (Python 3.15+, PEP 810)
src/slowcli/plugins.py:2:1: CRT201 [info] import-time side effect (registration): @register on "export_csv" runs when slowcli.plugins is imported
src/slowcli/report.py:1:1: CRT202 [info] import of "slowcli._heavy" could be lazy: only used inside functions
  help: change it to `lazy import slowcli._heavy` (Python 3.15+, PEP 810)

Startup analysis: 6 modules, 5 module-level imports, 2 lazy-import candidates (2 high confidence), 2 side effects, 0 lazy-import problems

Found 0 errors, 0 warnings, 4 info in 6 files (0.03 s).
```
- `target-version` is `3.15` here (from `requires-python`). With `--target-version 3.13` the help changes to the `__lazy_modules__` advice (§6.5.4).
- `cli.py`'s `import slowcli.plugins` is **not** a candidate: its bound name `slowcli` is never used, so it's a side-effect import, and its target registers handlers.

### 5.4 `startup measure`
```text
PS> uv run cartographer startup measure tests/fixtures/projects/exec_c2_slowcli --python $py315 --module slowcli.cli --execute --runs 10
cartographer: warning: running the import-time code of "slowcli.cli" with C:\…\python.exe
src/slowcli/cli.py:2:1: CRT206 [info] slow import: slowcli.report takes 60.62 ms cumulative (median of 10 runs, 95% CI [60.50, 60.83])
  help: if it is only needed inside functions, make the import lazy (see `cartographer startup analyze`)
src/slowcli/report.py:1:1: CRT206 [info] slow import: slowcli._heavy takes 60.21 ms cumulative (median of 10 runs, 95% CI [60.12, 60.40])
  help: if it is only needed inside functions, make the import lazy (see `cartographer startup analyze`)

Import-time profile of slowcli.cli (Python 3.15.2, 10 runs after 2 warm-up runs)

  cumulative ms [95% CI]      self ms   module
   61.40 [61.02, 61.95]          0.21   slowcli.cli
   60.62 [60.50, 60.83]          0.30   ├─ slowcli.report
   60.21 [60.12, 60.40]         60.21   │  └─ slowcli._heavy
    0.48 [0.44, 0.55]            0.20   └─ slowcli.plugins

Target import total: 61.40 ms [61.02, 61.95] · process wall time: 83.10 ms [82.40, 84.70]

Found 0 errors, 0 warnings, 2 info in 6 files (1.42 s).
```
(Numbers illustrative.)
- The tree shows **only the target's imports** (roots not present in the baseline run, §6.7), to `--depth` levels (default 3). Nodes with median cumulative < `--min-ms` (default 1.0) are hidden, except that a hidden node's parent line still shows the total. `--include-startup` also shows the interpreter's own startup imports.
- Children are sorted by descending median cumulative time.
- **Box-drawing fallback:** if `sys.stdout.encoding` can't encode `├─│└`, ASCII is used instead (`|-`, `` `- ``, `|`). This matters on legacy Windows code pages under 3.13/3.14 (D-019).
- Diagnostics are sorted by location (D-017), so `cli.py` comes before `report.py`. The golden file is authoritative for exact output.

### 5.5 `startup compare`
```text
PS> uv run cartographer startup compare tests/fixtures/projects/exec_c2_slowcli --python $py315 --module slowcli.cli --execute --runs 20 --all-lazy
cartographer: warning: running the import-time code of "slowcli.cli" with C:\…\python.exe
Startup comparison for slowcli.cli (Python 3.15.2, 20 interleaved runs per variant after 2 warm-up runs each)

  variant    lazy imports     process wall ms [95% CI]    target import ms [95% CI]
  eager      0                83.10 [82.40, 84.70]        61.40 [61.02, 61.95]
  advisor    2                23.40 [22.90, 23.95]         0.95 [0.90, 1.02]
  all-lazy   (global switch)  22.80 [22.40, 23.30]         0.61 [0.58, 0.66]

Advisor saving: 59.70 ms (71.8 %) process wall time, 95% CI [58.85, 60.62] ms (significant: the interval excludes 0).

Applied to a temporary copy (the original project was not modified):
  src/slowcli/cli.py:2     from slowcli import report  →  lazy from slowcli import report
  src/slowcli/report.py:1  import slowcli._heavy       →  lazy import slowcli._heavy

Found 0 errors, 0 warnings, 0 info in 6 files (6.85 s).
```
- If the advisor finds no candidates: `Nothing to compare: the advisor found no lazy-import candidates (use --include-low-confidence to try low-confidence ones).` Exit 0.
- If the **lazy copy fails to import** while the original succeeds: WARNING `the lazy copy failed to import (…last stderr line…); the advisor's suggestions changed behaviour here`, payload `variants.advisor.failed = true`, and the comparison table marks it `FAILED`. That's a genuine and valuable finding. The write-up must investigate any occurrence.

### 5.6 `startup pth`
```text
PS> uv run cartographer startup pth --python .venv\Scripts\python.exe
C:/…/.venv/Lib/site-packages/distutils-precedence.pth:1:1: CRT205 [warning] .pth file runs code at every interpreter startup: import os; var = 'SETUPTOOLS_USE_DISTUTILS'; enabled = os.environ.get(var, 'local') == 'local'; …
  help: executable .pth lines run before any of your code; they are deprecated in Python 3.15 (PEP 829). Check that the owning distribution (setuptools) is one you trust

Site directories scanned: 1 · .pth files: 3 (2 path-only, 1 executable) · .start files: 0

Found 0 errors, 1 warning, 0 info in 3 files (0.15 s).
```
- **The deprecation clause of the CRT205 help text is *Provisional (S-11)*.** Phase 6 rewrites it, and the golden file, to state exactly what Python 3.15 does with executable `.pth` lines (warning, deprecation, or nothing yet), citing PEP 829 only as far as S-11 confirms.
- **Paths in `startup pth` are absolute posix paths** (D-045). This is a documented exception to 02 §4.2, because these files are outside any project. The SARIF output uses absolute `file:///` URIs with no `uriBaseId`.
- Executable lines longer than 100 characters are truncated with `…` in the message. `data.line_text` holds the full line.

### 5.7 Markdown (`--format markdown`), used by C8's report
````markdown
# Startup report: slowcli.cli

| Item | Value |
|---|---|
| Python | 3.15.2 |
| Runs | 20 (+2 warm-up) |
| Target import total | 61.40 ms (95 % CI 61.02–61.95) |

## Slowest imports
| Module | Cumulative ms (median, 95 % CI) | Self ms | Imported by |
|---|---|---|---|
| slowcli.report | 60.62 (60.50–60.83) | 0.30 | slowcli.cli |

## Lazy-import candidates
| Location | Import | Confidence | Estimated saving |
|---|---|---|---|
| `src/slowcli/report.py:1` | `import slowcli._heavy` | high | 60.21 ms |

## Import-time side effects
| Kind | Count | Example |
|---|---|---|
| registration | 1 | `src/slowcli/plugins.py:2`: `@register` on `export_csv` |

## Comparison
(only for `startup compare`: the variant table as a Markdown table, plus the saving sentence)
````
Sections that would be empty are omitted. Each renderer emits only the sections it has data for.

## 6. Design

### Package layout
```
src/cartographer/startup/
  __init__.py      # public: analyze_startup, measure_startup, compare_startup, scan_pth + data classes
  config.py        # StartupConfig (import-light)
  importtime.py    # -X importtime parser → ImportTimeNode trees (S-02)
  names.py         # alias map + qualified names of expressions
  side_effects.py  # CRT201 classifier
  lazy.py          # detection of existing lazy imports: `lazy` keyword (3.15) and __lazy_modules__ (S-01)
  advisor.py       # CRT202/203/204 + fixes
  runner.py        # ProcessRunner/Clock protocols, SubprocessRunner, command construction
  stats.py         # median, bootstrap CI, difference CI
  measure.py       # orchestrates runs, aggregates trees, CRT206
  compare.py       # temp copy, edits, validation, interleaved variants
  pth.py           # site-dir discovery + .pth/.start scanning, CRT205
  render.py        # text tree, comparison table, markdown; registered with output.registry
src/cartographer/graph/usage.py      # EXTENDED: fine-grained UseKind (C1 tests must stay green)
src/cartographer/core/edits.py       # NEW: apply_edits (shared with C5)
src/cartographer/output/sarif.py     # EXTENDED: SARIF `fixes`
src/cartographer/cli/commands/startup.py
src/cartographer/api.py              # + analyze_startup, measure_startup, compare_startup, scan_pth
benchmarks/bench_startup.py
scripts/corpus_startup.py            # phase 7 Docker harness
```
`cli/sections.py` gains `"startup": "cartographer.startup.config:StartupConfig"`. The `startup` command has **nested sub-commands**. The M0 global-options trick (`parents=[…SUPPRESS…]`) must be applied at the nested level too, so that `startup measure … --format json` works.

### 6.1 `-X importtime` format and parser (`importtime.py`)
*Provisional (S-02).* The long-standing format (since Python 3.7) is a header followed by one line per completed import, written to **stderr**:
```text
import time: self [us] | cumulative | imported package
import time:       105 |        105 |   _io
import time:       224 |        224 |   posix
import time:       317 |        675 | _frozen_importlib_external
```
- Times are **microseconds**. `self` excludes children. `cumulative` includes them.
- Nesting is shown by **indentation of the name**: the third field is one space plus two spaces per nesting level.
- **Lines are printed when an import *finishes***, so children come **before** their parent, one level deeper.

S-02 records real outputs from 3.13, 3.14 and 3.15 (including `-X importtime=2`, if it exists, and what it adds, for example markers for already-loaded modules). The recordings are committed as `tests/fixtures/importtime/<python>-<case>.txt`, and the parser supports exactly the observed formats.

```python
@dataclass(frozen=True, slots=True)
class ImportTimeNode:
    name: str
    self_us: int
    cumulative_us: int
    depth: int
    children: tuple["ImportTimeNode", ...]
    cached: bool = False             # only if S-02 finds an importtime=2 marker for already-loaded modules

@dataclass(frozen=True, slots=True)
class ImportTimeRun:
    roots: tuple[ImportTimeNode, ...]   # in output order
    ignored_lines: int                  # non-importtime stderr lines (the target may print to stderr!)
    warnings: tuple[str, ...]           # e.g. "truncated output: 2 orphan nodes"

LINE = re.compile(r"^import time:\s*(?P<self>\d+)\s*\|\s*(?P<cum>\d+)\s*\|(?P<rest> .*)$")

def parse_importtime(stderr: str) -> ImportTimeRun
```
**Tree-building algorithm** (children-before-parent):
```
pending: dict[int, list[ImportTimeNode]] = {}
for line in stderr.splitlines():          # splitlines is fine here: this is program output, not source code
    m = LINE.match(line)
    if not m or line is the header:  ignored += (not header); continue
    rest  = m["rest"]                      # " " + "  " * depth + name
    depth = (len(rest) - len(rest.lstrip(" ")) - 1) // 2
    name  = rest.strip()
    node  = ImportTimeNode(name, int(m["self"]), int(m["cum"]), depth,
                           children=tuple(pending.pop(depth + 1, [])))
    pending.setdefault(depth, []).append(node)
roots = pending.pop(0, [])
if pending:  # deeper nodes never claimed by a parent => truncated output
    warnings.append(...); roots.extend(orphans in order)
```
- Complexity O(lines).
- **Validation, which warns but doesn't fail:** `cumulative_us < self_us`; a depth jump of more than one level.
- The **regex is anchored**, and anything that doesn't match is ignored and counted. That's essential, because the target program's own stderr output interleaves with importtime lines.

### 6.2 Names and qualified names (`names.py`)
```python
class AliasMap:
    """Maps names bound at module level by imports to absolute dotted names."""
    @classmethod
    def from_module(cls, file: SourceFile, resolver: Resolver, node: ModuleNode) -> "AliasMap"
    def qualify(self, expr: ast.expr) -> str | None
```
- `import numpy as np` → `np ↦ numpy`. `import os.path` → `os ↦ os`. `from os import path as p` → `p ↦ os.path`. `from subprocess import run` → `run ↦ subprocess.run`. Relative from-imports are resolved through C1's `Resolver`.
- Only **module-level** imports (context `MODULE`, any guard except `TYPE_CHECKING`) contribute.
- Builtins: a `Name` not bound at module level by an import, `def`, `class` or assignment, and present in `dir(builtins)` → `builtins.<name>`. A module-level rebinding of a builtin name (`open = my_open`) → unknown (`None`).
- `qualify(Name)` → map lookup. `qualify(Attribute)` → `qualify(value) + "." + attr`. Anything else → `None`.

### 6.3 Side-effect classifier (`side_effects.py`)
**What runs at import time:** every module-level statement, recursively including the bodies of module-level `if`/`else`, `for`/`while`, `with`, `try`/`except`/`else`/`finally` and `match` cases, plus **class bodies** (recursively). For `def` statements, the decorators, default values and (when not deferred) annotations also run. **Excluded:** function and lambda bodies; `if TYPE_CHECKING:` bodies; `if __name__ == "__main__":` bodies.

For each statement the classifier finds every `ast.Call` (and the special assignments below) that executes at import time. It classifies each one and emits **at most one CRT201 per statement**, choosing the highest-priority kind found:

| Priority | Kind | Detected when the qualified name (§6.2) is… |
|---|---|---|
| 1 | `network` | starts with `socket.`, `ssl.`, `urllib.request.`, `http.client.`, `requests.`, `httpx.`, `aiohttp.`, `urllib3.`, `smtplib.`, `ftplib.` |
| 2 | `subprocess` | starts with `subprocess.`; or is `os.system`, `os.popen`, `os.fork`, `os.exec*`, `os.spawn*`, `os.posix_spawn*` |
| 3 | `io` | `builtins.open`, `builtins.print`, `builtins.input`, `io.open`, `os.listdir`, `os.scandir`, `os.walk`, `os.makedirs`, `os.mkdir`, `os.remove`, `os.unlink`, `os.rename`, `os.path.exists`/`isfile`/`isdir`/`getsize`/`getmtime`, `shutil.*`, `glob.*`, `json.load`, `pickle.load`, `tomllib.load`, `sqlite3.connect`, `tempfile.*`; **or** a method call named `read_text`, `read_bytes`, `write_text`, `write_bytes`, `open`, `mkdir`, `touch`, `unlink`, `iterdir`, `glob`, `rglob`, `exists`, `is_file`, `is_dir` whose receiver expression contains a call to `pathlib.Path`/`pathlib.PurePath` or the name `__file__` |
| 4 | `env` | `os.getenv`, `os.putenv`, `os.unsetenv`, `os.environ.get`/`setdefault`/`pop`/`update`; subscript load/store on `os.environ` |
| 5 | `registration` | a **decorator** that is not in the pure list (§6.3.1); `atexit.register`, `signal.signal`, `codecs.register`, `copyreg.pickle`, `sys.addaudithook`, `warnings.filterwarnings`, `warnings.simplefilter`, `logging.basicConfig`, `logging.config.*`, `mimetypes.add_type`, `faulthandler.enable`; any call whose last name segment matches `register`, `register_*`, `*_register`, `add_*handler*`, `subscribe`, `connect`; `startup.registration-calls`; assignment `sys.excepthook = …` / `sys.displayhook = …`; subscript assignment into an attribute of an imported module (`registry.HANDLERS["x"] = f`) |
| 6 | `global-state` | assignment to an attribute of an imported module (`json.dumps = …`); `sys.path.*(…)` or assignment to `sys.path`; `sys.modules[…] = …`; `sys.setrecursionlimit`, `sys.set_int_max_str_digits`; `gc.*` (e.g. `gc.disable()`, `gc.freeze()`, the Instagram trick from Kiln); `os.chdir`, `os.umask`, `locale.setlocale`, `random.seed`, `socket.setdefaulttimeout`, `asyncio.set_event_loop_policy` |
| 7 | `call` | any other call that isn't pure (including unresolvable method calls such as `logger.addHandler(h)`) |

#### 6.3.1 Pure calls and decorators (no diagnostic)
Builtins `dict list set frozenset tuple str int float bool bytes bytearray object range len isinstance issubclass getattr hasattr setattr property staticmethod classmethod super type min max sorted enumerate zip map filter repr hash id iter next any all abs round divmod pow chr ord format vars`; `typing.*`, `typing_extensions.*`; `collections.namedtuple`, `collections.defaultdict`, `collections.OrderedDict`, `collections.deque`, `collections.Counter`, `collections.ChainMap`; `enum.*`; `dataclasses.dataclass`, `dataclasses.field`, `dataclasses.make_dataclass`; `functools.partial`, `wraps`, `lru_cache`, `cache`, `cached_property`, `total_ordering`, `singledispatch`, `singledispatchmethod`, `reduce`; `re.compile` (pure, though it can be slow. `data.note` doesn't flag it); `logging.getLogger`; `contextvars.ContextVar`; `threading.Lock`, `RLock`, `Event`, `local`, `Condition`, `Semaphore`; `weakref.*`; `abc.abstractmethod`, `abc.ABCMeta`; `contextlib.contextmanager`, `asynccontextmanager`; `struct.Struct`; `decimal.Decimal`; `fractions.Fraction`; `pathlib.Path`/`PurePath`/`PurePosixPath`/`PureWindowsPath` constructors and attribute access (`Path(__file__).parent`); `os.path.join`, `dirname`, `basename`, `abspath`, `splitext`, `normpath` (pure string operations); `os.fspath`; `sys.intern`; `builtins.sentinel` and `builtins.frozendict` (*Provisional, S-15*: PEP 661/814 builtins, listed only if S-15 confirms they exist as builtins in 3.15 under these names; otherwise removed in phase 2); `importlib.metadata.version` (not pure: it reads files, so it's `io`. Listed here as a trap, and the concept note explains why); plus `startup.pure-calls` from config.

A **class decorator or function decorator** from the pure list (`@dataclass`, `@functools.cache`, `@staticmethod`, `@property`, `@typing.overload`, `@typing.final`, `@typing.override`, `@typing.runtime_checkable`, `@enum.unique`, `@contextlib.contextmanager`, `@abc.abstractmethod`) is not a side effect.

**CRT201** (info):
- messages: `import-time side effect ({kind}): {qualname}(...) runs when {module} is imported` · decorators: `import-time side effect (registration): @{decorator} on "{name}" runs when {module} is imported` · assignments: `import-time side effect ({kind}): assigns to {target} when {module} is imported` · unresolvable: `import-time side effect (call): a call to {segment} runs when {module} is imported` (segment truncated to 60 chars).
- location: the statement. For a decorator, it's the decorator's line at the column of `@`, so `ast`'s decorator expression column minus one.
- `data`: `kind`, `call: str | null`, `target: str | null`, `in_class: bool`, `module: str`.
- Only for internal modules with a module name. Scripts aren't imported, so they're skipped.
- **Documented limitations** (in `explain CRT201`): `__init_subclass__` and metaclass registries are invisible; calls through local variables are generic `call`; effects inside functions called at module level aren't followed (intra-module, single level only).

### 6.4 Use-site classification (extends `graph/usage.py`)
C1 classified uses into `annotations` / `functions` / `module`. C2 needs finer detail, so `graph/usage.py` gains:
```python
class UseKind(enum.StrEnum):
    FUNCTION_BODY = "function-body"            # body of def / async def / lambda (incl. methods)
    ANNOTATION_DEFERRED = "annotation-deferred"
    ANNOTATION_EAGER = "annotation-eager"
    DECORATOR = "decorator"                    # incl. method decorators (run at class creation)
    DEFAULT = "default"                        # default argument values
    BASE_CLASS = "base-class"                  # bases and class keywords (metaclass=…)
    CLASS_BODY = "class-body"
    MODULE_LEVEL = "module-level"              # incl. comprehensions and `del` at module level

EAGER_USES = frozenset(UseKind) - {UseKind.FUNCTION_BODY, UseKind.ANNOTATION_DEFERRED}

@dataclass(frozen=True, slots=True)
class Use:
    name: str
    location: Location
    kind: UseKind

def classify_uses(file: SourceFile, names: frozenset[str], *, annotations_deferred: bool) -> tuple[Use, ...]
```
- **Annotations are deferred** (`ANNOTATION_DEFERRED`) when `target-version >= 3.14` (PEP 649/749) or the module has `from __future__ import annotations`. **Exception:** annotations in the body of a class that has any class decorator (e.g. `@dataclass`), or that inherits from a name qualifying to `typing.NamedTuple`, `typing.TypedDict`, `pydantic.BaseModel` or `msgspec.Struct`, are `ANNOTATION_EAGER`. Those tools read annotations when the class is created. The concept note `lazy-imports` explains this with the dataclass example.
- C1's three-way `where` is re-derived from `UseKind` (annotations = all uses `ANNOTATION_*`; functions = all `FUNCTION_BODY`; otherwise module), and **all C1 tests must pass unchanged**.

### 6.5 Lazy-import advisor (`advisor.py`)
#### 6.5.1 Candidates
For every **internal** module (not scripts, no CRT001/CRT002), consider each `RawImport` (C1) with `kind == MODULE` (context `MODULE`, guard `NONE`) and mechanism `IMPORT` or `FROM`. A candidate must pass all of these checks:

| # | Criterion | Rejected example |
|---|---|---|
| C1 | **Placement is allowed for `lazy`** (*Provisional S-01*): a direct top-level statement of the module, or inside a module-level `with` block. Not inside a class body, `try`, `if` (until S-01 confirms whether module-level `if` is allowed), or loop | `try: import ujson` |
| C2 | **No eager use:** every use of every bound name is `FUNCTION_BODY` or `ANNOTATION_DEFERRED` (§6.4). If the bound names are **never used**: a candidate only if the module is a package `__init__` and the target is a submodule (the re-export pattern, confidence `medium`); otherwise it's a side-effect import → rejected | `@app.route` where `app` comes from the import; `def f(x=json.dumps)` |
| C3 | **Not a registration import:** the target is not an internal module with a CRT201 of kind `registration`, and doesn't match a `startup.registration-modules` prefix | `import myapp.plugins` |
| C4 | **Not pointless:** the target isn't `__future__`, isn't in `sys.builtin_module_names`, and isn't in the always-loaded set (`sys`, `builtins`, `os`, `io`, `abc`, `codecs`, `encodings`, `stat`, `posixpath`, `ntpath`, `genericpath`, `_collections_abc`, `site`, `types`, `warnings`; when `--importtime` is given, the set of modules already imported in the baseline run is used instead) | `import os` |
| C5 | **Unique binding:** no bound name is bound by another import, assignment or `def` at module level (`import a.b` + `import a.c` both bind `a`) | `import a.b` / `import a.c` |
| C6 | **No star import**, and the name isn't rebound or deleted later at module level | `from m import *` |

**Confidence:**
- `high`: passes everything; target is internal or third-party; all uses are `FUNCTION_BODY`.
- `medium`: the re-export case; or some uses are `ANNOTATION_DEFERRED`; or the name is listed in `__all__`; or the module defines a module-level `__getattr__` (PEP 562), which may reach names dynamically.
- `low`: the target is stdlib (often already loaded by something else); or, with `--entry`, the target **stays eagerly reachable** (below).

**Still-eager check (only with `--entry M`):** take C1's graph, keep edges whose kind is `module`/`optional`/`dynamic`, and remove every edge whose sites are **all** candidates (as if every candidate were already lazy). For each candidate target `t` still reachable from `M` (BFS over the remaining edges, with external targets counted by their top-level name), set confidence `low` and `data.still_eager_via` to the BFS path from `M` to `t`. Message suffix: `; but it is still imported eagerly via a → b → t`.

**Measured savings (only with `--importtime FILE`):** `data.estimated_saving_ms` = the median cumulative time of the target's node in the profile (if present). Candidates with a measured saving below `min-saving-ms` are dropped (INFO log with the count). Candidates are then **ranked by estimated saving** in Markdown output. Text and JSON keep location order (D-017).

Candidates with confidence `low` are emitted only if `startup.include-low-confidence = true`. They are always counted in the payload.

#### 6.5.2 CRT202 (info)
- message: `import of "{module}" could be lazy: {reason}` with reason `only used inside functions` / `only used in deferred annotations and functions` / `re-exported by the package and unused here` + optional ` (est. saving {ms:.2f} ms)` + optional still-eager suffix.
- location: the import statement.
- `data`: `module`, `statement`, `confidence`, `reason` (`functions`/`annotations`/`re-export`), `advice` (`lazy-keyword`/`lazy-modules`), `estimated_saving_ms: float | null`, `still_eager_via: list[str] | null`.

#### 6.5.3 Fix for `target-version >= 3.15`: the `lazy` keyword
`Fix(description="Make the import lazy (PEP 810)", edits=(Edit(path, start=pos, end=pos, replacement="lazy "),), safety="review")`, where `pos` is the statement's start (line, column). Help: ``change it to `lazy import x` `` or ``change it to `lazy from m import x` `` (Python 3.15+, PEP 810).

#### 6.5.4 Fix for `target-version < 3.15`: `__lazy_modules__`
*Provisional S-01* (exact semantics: which name to list for `from a.b import c`, and exact vs prefix matching). Default assumption: list the imported module (`"a.b"` for `from a.b import c`, `"a.b"` for `import a.b`).
- If the module already assigns `__lazy_modules__` at top level to a literal list or tuple of strings: insert `"{name}", ` right after the opening bracket. An empty tuple `()` becomes `("{name}",)`.
- Otherwise: insert a new line `__lazy_modules__ = ["{name}"]\n` before the first statement that is not the module docstring or a `from __future__` import.
- Help: ``add "{name}" to `__lazy_modules__`: Python 3.15+ then imports it lazily, older versions ignore it. Or move the import into the function(s) that use it, which works on every version``.
- Fix description warns: `if several imports in this file qualify, list them all in one __lazy_modules__`. Each fix is independent and safety is `review`. Only keyword fixes are ever *applied* (by `compare`, which always targets 3.15).

### 6.6 Existing lazy imports (`lazy.py`)
- **`lazy` keyword:** only parseable when Cartographer runs on 3.15+ (D-004). Detected via `core.versions.is_lazy_import(node: ast.Import | ast.ImportFrom) -> bool`, whose exact AST attribute is fixed by S-10/S-01. On 3.13/3.14, such files already produce CRT001 with the 3.15 hint.
- **`__lazy_modules__`:** a top-level assignment of a literal list/tuple of strings. A non-literal value → DEBUG log, ignored. Imports whose module matches an entry (S-01 semantics) are treated as lazy, on **every** Cartographer version.

**CRT203 `lazy-import-defeated`** (warning): a lazy import (either form) whose bound name has an **eager use** (§6.4).
- message: `lazy import of "{module}" is reified at import time by its use on line {n} ({use_kind})`
- location: the **first eager use**; related: the lazy import statement.
- `data`: `module`, `use_line`, `use_kind`, `mechanism` (`lazy-keyword`/`lazy-modules`).

**CRT204 `lazy-import-registration-risk`** (warning): a lazy import whose target is a registration module (C3 of §6.5.1), **or** whose bound names are never used (so the import never happens at all).
- messages: `lazy import of "{module}" may never run its registration: the module registers handlers when imported ({call} on line {n} of {path})` / `lazy import of "{module}" is never used, so it will never be imported; if it was imported for its side effects, they are now skipped`
- location: the lazy import statement; related: the registration site, if known.
- `data`: `module`, `reason` (`registration`/`unused`), `evidence: {path, line} | null`.

### 6.7 Runner (`runner.py`)
```python
class Clock(Protocol):
    def now_ns(self) -> int: ...                     # default: time.perf_counter_ns

@dataclass(frozen=True, slots=True)
class RunSpec:
    argv: tuple[str, ...]
    cwd: Path
    timeout_s: float

@dataclass(frozen=True, slots=True)
class RunOutcome:
    returncode: int
    stdout: str
    stderr: str
    wall_ns: int
    timed_out: bool

class ProcessRunner(Protocol):
    def run(self, spec: RunSpec) -> RunOutcome: ...

class SubprocessRunner:                              # the only class that actually spawns processes
    def __init__(self, clock: Clock = PerfCounterClock()) -> None
```
**Command construction** (`import_argv(python, roots, module, pycache_dir, *, extra_x=())`):
```
[python, "-I", "-X", "importtime", "-X", "utf8", "-X", f"pycache_prefix={pycache_dir}", *extra_x,
 "-c", f"import sys; sys.path[0:0] = {roots!r}; import {module}"]
```
- `-I` (isolated mode): ignores `PYTHON*` env vars, the user site directory and the script directory. That gives reproducible runs and no planted-module surprises. The project's source roots are added explicitly via the `-c` program.
- `roots` is a `list[str]` of **absolute** source-root paths. `repr()` makes it a safe Python literal. `module` was validated by regex (§5.1). **Nothing else is ever interpolated into code.**
- `-X utf8`: UTF-8 mode, regardless of the Windows code page (PEP 540). It's needed because `-I` disables `PYTHONUTF8`.
- `-X pycache_prefix=…`: `.pyc` files go into a temp directory, **never into the user's project** (we must not write into a repo we're inspecting). Each variant gets its own prefix directory.
- `cwd` = a fresh empty temp directory.
- **Baseline argv:** the same, but the program is only `import sys; sys.path[0:0] = {roots!r}`. Its importtime roots are the **interpreter-startup imports**. In a target run, roots whose names appear in the baseline's root set are startup, and the rest belong to the target. (This is version-independent, so we don't need to know which modules `site` loads.)
- `subprocess.run(list(argv), cwd=…, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=…, check=False)`. Wall time = `clock.now_ns()` immediately before and after.
- Timeout → `ToolEnvironmentError("importing slowcli.cli timed out after 60 s")`. A non-zero exit → `ToolEnvironmentError` including the last 5 stderr lines that aren't importtime lines.

### 6.8 Statistics (`stats.py`)
```python
@dataclass(frozen=True, slots=True)
class Summary:
    n: int
    median: float
    ci_low: float | None          # None when n < 5
    ci_high: float | None
    minimum: float
    maximum: float

def summarize(xs: Sequence[float], *, confidence: float, resamples: int, rng: random.Random) -> Summary
def bootstrap_ci(xs, stat, *, confidence, resamples, rng) -> tuple[float, float]
def bootstrap_diff_ci(a, b, *, confidence, resamples, rng) -> tuple[float, float]   # CI of median(a) - median(b)
```
**Bootstrap (percentile method):** repeat `resamples` times: draw `len(xs)` values from `xs` **with replacement** (`rng.choices`), compute the median. Sort the resampled medians `m`. With `alpha = 1 - confidence`, `lo = m[floor(alpha/2 * B)]` and `hi = m[ceil((1 - alpha/2) * B) - 1]`. For the difference, resample `a` and `b` independently each round and record `median(a*) - median(b*)`.
- **Why the median, not the mean:** startup times have a long right tail (an antivirus scan, a cache miss), and the median ignores that tail.
- **Why bootstrap:** it makes no assumption about the shape of the distribution. Startup times aren't normally distributed.
- **Determinism:** `rng = random.Random(startup.seed)`. The same data and seed give an identical CI.
- `n < 5` → CI `None`, and a WARNING `too few runs (3) for a confidence interval; use --runs 5 or more`.
- **Significance (compare):** the saving is *significant* iff the difference CI's lower bound > 0.

### 6.9 Measure and compare (`measure.py`, `compare.py`)
**Measure:**
```
check interpreter (python -I -c "import sys; print(sys.version_info[:3], sys._is_gil_enabled() if hasattr(sys, '_is_gil_enabled') else True)")
for i in range(warmup): run target (discard)            # warms the OS file cache and compiles .pyc
baseline = run baseline once; startup_roots = names of its roots
runs = [run target for _ in range(runs)]                # each parsed with parse_importtime
per module name: collect self_us and cumulative_us across runs (a name is unique within one run)
tree = structure of the FIRST measured run, restricted to target roots; values = per-name medians
target_total = sum of cumulative of target roots, per run → Summary
wall = per-run wall time → Summary
CRT206 (below)
```
**CRT206 `slow-import`** (info): for every edge `parent → child` in the target tree where the **parent is an internal module** and `median(child.cumulative) >= slow-threshold-ms` (default 50): find, in the parent's file, the `RawImport` that C1 resolves to `child` (or to `child`'s top-level name for external modules). If one is found, emit at that location.
- message: `slow import: {child} takes {ms:.2f} ms cumulative (median of {n} runs, 95% CI [{lo:.2f}, {hi:.2f}])`
- `data`: `module`, `cumulative_ms`, `self_ms`, `ci: [lo, hi] | null`, `runs`, `imported_by`.
- A chain like `cli → report → _heavy` intentionally gives two findings (`report` slow from `cli`'s import, `_heavy` slow from `report`'s import). Each points at a place you could change.

**Compare:**
1. Validate the interpreter (≥ 3.15, else exit 4).
2. Run `analyze` with `target_version="3.15"` and keep CRT202 diagnostics with `advice == "lazy-keyword"` and a fix (plus `low` ones only with `--include-low-confidence`).
3. **Copy** the project root to `tempfile.mkdtemp(prefix="cartographer-compare-")/lazy` with `shutil.copytree(…, symlinks=False, ignore=…)`. The ignore function skips default-excluded directories **and every symlink**, because `copytree` with `symlinks=False` would otherwise *follow* links and copy their targets, possibly from outside the project.
4. Apply the fixes with `core.edits.apply_edits` to the copied files. A file whose source declares a **non-UTF-8 PEP 263 cookie** is skipped (logged), because we write UTF-8. Written with `encoding="utf-8", newline="\n"`.
5. **Validate** the edited copy with the 3.15 interpreter: `[python, "-I", "-c", "import ast, sys\nfor p in sys.argv[1:]: ast.parse(open(p, encoding='utf-8').read(), p)", *edited_files]`. A failure means **our** bug → `AnalysisError` (exit 3).
6. **Smoke import** of each variant once. If the original fails → exit 4 (the environment is missing dependencies). If only the lazy copy fails → mark it `failed` (§5.5) and continue without it.
7. **Measure interleaved:** after `warmup` runs per variant, do `runs` rounds. In round `i`, run the variants in rotated order (`variants[i % k:] + variants[:i % k]`), which cancels drift such as CPU frequency changes and background load. Variants: `eager` (original), `advisor` (copy), and `all-lazy` (original + `extra_x=("-X", "lazy_imports=all")`, *Provisional S-01*, only with `--all-lazy`).
8. Report per-variant wall-time and target-import Summaries, plus the saving `eager − advisor` (wall time) with `bootstrap_diff_ci`, the percentage, and significance.
9. Delete the temp directory (`shutil.rmtree`) in a `finally`, unless `--debug` is set (then print its path for inspection).

### 6.10 `.pth` and `.start` files (`pth.py`)
**Finding the site directories without running `.pth` files:**
```
[python, "-I", "-S", "-c", "import json, site, sys, sysconfig; print(json.dumps({...}))"]
```
`-S` means "don't import `site` at startup", so no `.pth` file is processed and no `sitecustomize`/`usercustomize` runs. The program prints `sysconfig.get_paths()["purelib"]` and `["platlib"]`, `site.getsitepackages()`, `site.getusersitepackages()`, `sys.prefix` and `sys.version`. The directories are de-duplicated and non-existent ones are dropped. This interrogation is injectable (`SiteQuery` protocol) so tests can use a fabricated site directory.

**Scanning:** for each directory, sorted `*.pth` files, read as `utf-8-sig` with `errors="replace"`. Per line (1-based):
- blank or starting with `#` → skip.
- `line.startswith(("import ", "import\t"))` → **executable**. That's exactly `site.py`'s rule → CRT205.
- otherwise → a path entry (payload records it and whether it exists).

**Owner distribution:** for each `*.dist-info/RECORD` in the same directory, if it lists the `.pth` file's name → `data.distribution = "<name>"` (from the dist-info directory name).

**`.start` files** (*Provisional S-11*): if S-11 confirms PEP 829's `.start` file format, list them in the payload (`start_files`) with their entries. No diagnostic, because they're the sanctioned replacement. If S-11 shows something different, this section is rewritten in the same PR as the spike note.

**CRT205** (warning):
- message: `.pth file runs code at every interpreter startup: {line_text truncated to 100 chars}`
- location: absolute posix path, the line, column 1 (§5.6 exception).
- help: as in §5.6 (owner name included when known).
- `data`: `line_text`, `site_dir`, `file`, `distribution: str | null`.

### 6.11 `core/edits.py`
```python
def apply_edits(text: str, edits: Sequence[Edit]) -> str
```
- Converts `(line, column)` (1-based, characters, D-018) to string offsets using the line starts of `text.split("\n")`.
- Sorts edits by start offset, **descending**, and applies them back to front so earlier offsets stay valid.
- **Overlapping** edits → `ValueError` (two zero-width insertions at the same point are allowed, and applied in input order).
- An edit position outside the text → `ValueError`.
- All edits must have the same `path`, else `ValueError` (the caller groups by file).

### 6.12 Dogfooding Cartographer's own startup
- **Import-set test** (`tests/integration/test_startup_dogfood.py`, marker `execute`, every Python version): run `python -I -X importtime -m cartographer --version` (our own code), parse it with **our** parser, and assert that none of these modules were imported: `cartographer.graph`, `cartographer.startup`, `cartographer.rules`, `cartographer.typecov`, `cartographer.tstrings`, `cartographer.depdiff`, `cartographer.ci`, `cartographer.report`, `cartographer.adapters`, `libcst`, `yaml`, `asyncio`, `ssl`, `urllib.request`, `http.client`, `email`, `tomllib`. (`--version` is handled by argparse before any config is loaded, so even `tomllib` isn't needed.) This holds on every version thanks to the M0 import discipline (M0 §6.17): command modules import heavy things inside `run()`, `cli/main.py` imports config/output only after `parse_args`, and `core/config.py` imports `tomllib` inside `load_config()`.
- **`__lazy_modules__` dogfooding** (D-005): run `cartographer startup analyze .` on the repo root (D-048). Every `high`-confidence CRT202 in `src/cartographer/cli/` and `src/cartographer/core/` is resolved, either by adding the module to that file's `__lazy_modules__` or by moving the import into a function. The dogfood test asserts **zero high-confidence CRT202** in those two packages. Findings elsewhere are listed in the write-up.
- **Budget benchmark** (`benchmarks/bench_startup.py`): 20 runs of `python -I -m cartographer --version` on 3.15 (and 3.13 for comparison) using `runner.py` + `stats.py` → median + CI vs the **150 ms** budget (05 §6). Recorded in the write-up, not gated in CI.
- `startup compare` on Cartographer itself (`--module cartographer.cli.main`), recorded in the write-up.

## 7. Diagnostics

| Code | Severity | Emitted by | Section |
|---|---|---|---|
| CRT201 `import-time-side-effect` | info | analyze | §6.3 |
| CRT202 `lazy-import-candidate` | info | analyze (+ compare internally) | §6.5 |
| CRT203 `lazy-import-defeated` | warning | analyze | §6.6 |
| CRT204 `lazy-import-registration-risk` | warning | analyze | §6.6 |
| CRT205 `pth-executable-line` | warning | pth | §6.10 |
| CRT206 `slow-import` | info | measure | §6.9 |

**Scopes (D-047, M0 §6.7).** Each sub-command reports only codes in its scope, and the effective selection is `select ∩ scope − ignore`. With the default `select = ["CRT"]` that means "everything this sub-command can report". The scopes, added to `api.SCOPES`:
| Sub-command | Scope | Notes |
|---|---|---|
| `startup analyze` | `CRT0`, CRT201–CRT204 | C1's resolution diagnostics (CRT103/CRT104) are **not** in scope, even with `--select CRT1`, because a user asking about startup doesn't want import-graph reports. Use `cartographer graph` for those. (D-047's list also names CRT205, but `analyze` never emits it; the parent should align D-047's example.) |
| `startup measure` | `CRT0`, CRT206 | |
| `startup compare` | `CRT0` | It prints a comparison table, not findings |
| `startup pth` | CRT205 | No project files are parsed |

There is no per-command "replace the selection" behaviour any more. Filtering happens once, in `api._finish` (D-046). All six codes flip to `IMPLEMENTED` with explanations. CRT201's explanation lists the limitations in §6.3. CRT202's includes the four gotchas from §2.

## 8. Configuration

```toml
[tool.cartographer.startup]
slow-threshold-ms      = 50.0     # CRT206 threshold (float > 0)
runs                   = 20       # measured runs per variant (int >= 1; CI needs >= 5)
warmup                 = 2        # discarded runs per variant (int >= 0)
timeout-s              = 60.0     # per subprocess
confidence             = 0.95     # 0 < x < 1
bootstrap-resamples    = 2000     # int >= 100
seed                   = 0        # RNG seed for the bootstrap (determinism)
min-saving-ms          = 1.0      # with --importtime: drop candidates saving less than this
include-low-confidence = false
pure-calls             = []       # extra qualified names treated as pure, e.g. ["myapp.config.load_defaults"]
registration-calls     = []       # extra qualified names treated as registration
registration-modules   = []       # module prefixes whose import must never be made lazy
```
CLI `--runs`/`--warmup` override `runs`/`warmup`. Validation errors follow M0 §6.9.

## 9. Phases & tasks

**MVP line:** phases 1–5 (they deliver the research's "find a startup win and measure it"). Phase 6 (pth + dogfood) is required for acceptance. Phase 7 holds the corpus evidence.

### Phase 1: Spikes and the importtime parser (`c2/importtime`): MVP
- [ ] **S-01 spike** on 3.15: `lazy import` / `lazy from` placement rules (module-level `if`? `with`? class body?), `__lazy_modules__` semantics (exact module names vs prefixes; which name for `from a.b import c`), the `-X lazy_imports` values and `PYTHON_LAZY_IMPORTS`, `sys.set_lazy_imports_filter` signature, the proxy's type name and what reifies it (attribute access from another module? `globals()`? `dir()`?), and the AST attribute marking lazy imports (shared with S-10). Write `docs/learn/spikes/S-01-lazy-imports.md`; update §5.1, §6.5.1 (C1), §6.5.4, §6.6, §6.9 step 7.
- [ ] **S-02 spike**: record `-X importtime` (and `=2`, if it exists) output on 3.13, 3.14, 3.15 for: `import json`; a package with a submodule (does the parent get its own line?); an import that prints to stderr; and a failing import. Save as `tests/fixtures/importtime/*.txt` with a README. Write `docs/learn/spikes/S-02-importtime.md`.
- [ ] `startup/importtime.py` (§6.1).
- [ ] 🖐 Hypothesis round-trip test: generate a random tree → render it in importtime format → parse → equal tree (T-C2-02). Writing the *renderer* for the test is a good exercise.
- [ ] Concept notes: `importtime`, `lazy-imports` (written from the S-01 findings, with every gotcha demonstrated).

### Phase 2: Side-effect classifier (`c2/side-effects`): MVP
- [ ] **S-15 spike (C2 part)**: on 3.15, check whether `sentinel` (PEP 661) and `frozendict` (PEP 814) exist as builtins and under which names. Write or extend `docs/learn/spikes/S-15-misc-facts.md`; update the pure list in §6.3.1.
- [ ] `startup/names.py` (§6.2), `startup/side_effects.py` (§6.3), `startup/config.py`; `cli/sections.py` entry.
- [ ] CRT201 + explanation.
- [ ] Fixture `c2_side_effects/`: one module per kind; pure examples (no findings); a class body; a `__main__` block and a `TYPE_CHECKING` block (excluded); decorators pure and non-pure; unresolvable method call; builtin shadowing; `Path(__file__).read_text()`.
- [ ] Concept note: `module-execution-and-side-effects`.

### Phase 3: Advisor and `startup analyze` (`c2/advisor`): MVP
- [ ] Extend `graph/usage.py` with `UseKind`/`classify_uses` (§6.4); keep C1 green.
- [ ] `core/edits.py` (§6.11) + property tests.
- [ ] `startup/lazy.py` (§6.6), `startup/advisor.py` (§6.5); CRT202/203/204 + explanations.
- [ ] `output/sarif.py`: emit `fixes` (`artifactChanges` → `replacements` with `deletedRegion` + `insertedContent`).
- [ ] `cli/commands/startup.py` with the nested sub-commands; `analyze` text/json/sarif/markdown; `api.analyze_startup`.
- [ ] Fixtures `c2_lazy_candidates/` (every criterion in §6.5.1, accepted and rejected, incl. annotations with/without `from __future__ import annotations`, dataclass annotation, `__all__`, module `__getattr__`, shared binding, `with` block) and `c2_existing_lazy/` (`__lazy_modules__` cases on all versions; `# requires: 3.15` file with `lazy` keyword cases).
- [ ] Golden: `startup analyze` on `exec_c2_slowcli` (text/json/sarif) for target versions 3.15 and 3.13.

### Phase 4: `startup measure` (`c2/measure`): MVP
- [ ] `startup/runner.py` (§6.7), `startup/stats.py` (§6.8), `startup/measure.py` (§6.9), `startup/render.py` (tree + ASCII fallback + markdown); CRT206 + explanation; `api.measure_startup`.
- [ ] 🖐 `stats.py` test-first: write T-C2-10…T-C2-13 before the implementation.
- [ ] `FakeRunner` + `FakeClock` test doubles in `tests/unit/startup/fakes.py` (they replay recorded importtime outputs and fixed wall times), so measure logic is unit-tested without subprocesses.
- [ ] Integration test (`execute`) on `exec_c2_slowcli`.
- [ ] Concept notes: `subprocess`, `measuring-performance`.

### Phase 5: `startup compare` (`c2/compare`): MVP
- [ ] `startup/compare.py` (§6.9 compare); `api.compare_startup`; text/json/markdown rendering.
- [ ] Integration test (`execute`, `requires_py315`) on `exec_c2_slowcli`: significant saving (A-C2-05).
- [ ] Tests for: no candidates; lazy copy fails (fixture variant `exec_c2_lazybreak/`, where a lazy import is reified through a path the static analysis can't see, e.g. `globals()["report"]`); symlink in project not followed; non-UTF-8 cookie file skipped; temp dir removed.

### Phase 6: `.pth` scanning and dogfooding (`c2/pth-dogfood`)
- [ ] **S-11 spike**: PEP 829 on 3.15. What exactly is deprecated (warning text and category), the `.start` file format, and how `site.py` processes both. Write `docs/learn/spikes/S-11-pth-start.md`; update §6.10.
- [ ] `startup/pth.py` (§6.10); CRT205 + explanation; `api.scan_pth`.
- [ ] Tests with a fabricated site directory in `tmp_path` (executable lines, path lines, comments, BOM, a RECORD-owned file, `.start` file if applicable) + one real-venv smoke test (no assertions on content).
- [ ] Dogfooding (§6.12): import-set test; resolve our high-confidence CRT202s with `__lazy_modules__`; `benchmarks/bench_startup.py`.
- [ ] Concept note: `site-and-pth-files`.

### Phase 7: Acceptance and reflection (`c2/close`)
- [ ] **S-06 Part A spike**: confirm `python:3.15-slim` exists and that the exact D-052 flag set works on Docker Desktop for Windows (`docker run --rm --network none --read-only --tmpfs /tmp:rw,size=256m --cap-drop ALL --security-opt no-new-privileges --pids-limit 256 --memory 1g --cpus 2 --user 65534:65534 python:3.15-slim python -c "print('ok')"`), plus `docker create` + `docker cp` into a created container. Write `docs/learn/spikes/S-06-sandbox.md` (Part A). C6 adds Part B.
- [ ] 🖐 `scripts/corpus_startup.py`: the **only** corpus-execution harness (D-052). Corpus code never runs on the host. Steps, exactly as D-052:
  1. Build an image `FROM python:3.15-slim` containing the Cartographer wheel and the corpus repo's **dependencies only**, installed as binary wheels: `pip install --only-binary=:all: --no-deps -r <pinned list>` (the pinned list is recorded per corpus repo in `corpus/corpus.toml` as `startup_requirements`). **The corpus project itself is never installed or built**, so none of its build code runs, even during the image build when the network is on.
  2. `docker create` the container with exactly the D-052 flags: `--network none --read-only --tmpfs /tmp:rw,size=256m --cap-drop ALL --security-opt no-new-privileges --pids-limit 256 --memory 1g --cpus 2 --user 65534:65534`, and the command `cartographer startup compare /work/<repo> --python /usr/local/bin/python --module <mod> --execute --format json --output /tmp/result.json`.
  3. `docker cp` the pinned corpus checkout into `/work/<repo>` of the created (not yet started) container. No bind mounts. `/work` is created in the image and owned by user 65534, so the read-only root filesystem still accepts the copy before start (S-06 Part A confirms).
  4. `docker start -a`, then `docker cp` the result out (if `/tmp` is a tmpfs and can't be copied after exit, the command prints the JSON to stdout instead; S-06 Part A decides) and `docker rm`.
  5. `startup compare` adds the corpus source roots to `sys.path` itself, so no install of the project is needed.
  Every `docker` call uses an argument list (no shell). Tests for the harness use the `docker` marker. C8's Final acceptance F2 reuses this script unchanged.
- [ ] Run it on at least one `startup`-purpose corpus repo (S-07). Record the results.
- [ ] Walkthrough, write-up, reference comparison (§12); version `0.2.0`; changelog.

## 10. Test plan

| ID | What | Kind |
|---|---|---|
| T-C2-01 | Parser: every recorded fixture (3.13/3.14/3.15, `=2` if any) → hand-verified expected trees (stored as JSON next to each fixture) | unit |
| T-C2-02 | Render→parse round trip for random trees (depth ≤ 6, ≤ 60 nodes, times ≤ 10⁷ µs, names from module-name strategy) | property |
| T-C2-03 | Parser robustness: interleaved non-importtime stderr lines counted in `ignored_lines`; truncated output produces orphans + warning; `cumulative < self` warns; never raises on arbitrary text (Hypothesis `text()`) | unit + property |
| T-C2-04 | `AliasMap.qualify`: every alias form, relative from-imports, builtins, shadowed builtins, function-level imports ignored | unit |
| T-C2-05 | Side-effect classifier: each row of the §6.3 table, priority selection within one statement, pure list, class bodies, excluded blocks, decorators, assignments | unit (parametrised over `c2_side_effects`) |
| T-C2-06 | `classify_uses`: every `UseKind`, annotations deferred by target version / `__future__` / dataclass exception; C1 `where` derivation unchanged (C1 tests still pass) | unit |
| T-C2-07 | Advisor: every criterion C1–C6 accepted/rejected; confidence levels; still-eager path with `--entry`; `--importtime` savings and `min-saving-ms` drop | unit (parametrised over `c2_lazy_candidates`) |
| T-C2-08 | Fixes: keyword edit for ≥ 3.15; `__lazy_modules__` new-line and existing-list/tuple edits, incl. empty `()`; applying a fix yields source that `ast.parse`s on 3.15 (`requires_py315`) | unit |
| T-C2-09 | CRT203/CRT204 on `c2_existing_lazy` (`__lazy_modules__` on every version; keyword cases `requires_py315`) | unit |
| T-C2-10 | `summarize`: constant data → CI `(c, c)`; `lo <= median-of-resamples-range <= hi` ordering; `min(xs) <= lo <= hi <= max(xs)` | property |
| T-C2-11 | Shift/scale equivariance: `CI(xs + k) == CI(xs) + k` and `CI(xs * s) == CI(xs) * s` (s > 0) with the same seed (within 1e-9) | property |
| T-C2-12 | Determinism: same data + seed → identical CI; different seed → generally different | property |
| T-C2-13 | `n < 5` → CI `None` + warning; diff CI sign: `a` strictly greater than `b` everywhere → `lo > 0` | unit |
| T-C2-14 | Runner argv construction exactly as §6.7 (incl. `repr` of a path with a space and a quote, e.g. `C:\Users\Karthik Reddy\it's`); `--module` validation rejects `os; import shutil` | unit |
| T-C2-15 | Measure with `FakeRunner`: baseline subtraction, per-name medians, tree from first run, CRT206 locations via resolver, chain gives two findings, timeout and non-zero exit → exit 4 | unit |
| T-C2-16 | `--execute` gate: without it exit 2 and `FakeRunner.run` never called; with it the warning is printed to stderr first | integration |
| T-C2-17 | Measure on `exec_c2_slowcli` (real subprocess): `_heavy` median cumulative ≥ 55 ms | integration (`execute`) |
| T-C2-18 | Compare on `exec_c2_slowcli` (3.15): advisor variant significant; temp dir deleted; original files byte-identical before/after (hash check) | integration (`execute`, `requires_py315`) |
| T-C2-19 | Compare edge cases: no candidates; lazy copy fails (`exec_c2_lazybreak`); symlink skipped; non-UTF-8 cookie file skipped; interleaving order rotates (FakeRunner records call order) | unit + integration |
| T-C2-20 | `apply_edits`: overlapping → `ValueError`; same-point insertions in order; out-of-range → `ValueError`; random non-overlapping edit sets give the same result in any input order | property |
| T-C2-21 | pth scanning on fabricated site dirs: exact CRT205 set, path entries, comments, BOM, RECORD owner; `-S` present in the site-query argv | unit |
| T-C2-22 | Dogfood import-set test (§6.12) on every interpreter | integration (`execute`) |
| T-C2-23 | Dogfood: zero high-confidence CRT202 in `src/cartographer/cli` and `src/cartographer/core` | integration |
| T-C2-24 | Goldens: `analyze` text/json/sarif/markdown (3.15 and 3.13 targets); `measure`/`compare` text and markdown via FakeRunner (deterministic numbers) | golden |
| T-C2-25 | SARIF `fixes` validate against the vendored SARIF schema | unit |

## 11. Acceptance criteria

| ID | Criterion |
|---|---|
| A-C2-01 | The parser reproduces the expected trees for every recorded importtime fixture from 3.13, 3.14 and 3.15 (T-C2-01) |
| A-C2-02 | `startup analyze` on `exec_c2_slowcli` matches its golden output, giving exactly 2 CRT202 and 2 CRT201, on all CI cells |
| A-C2-03 | `startup measure` and `startup compare` refuse to run without `--execute` (exit 2, nothing spawned) |
| A-C2-04 | `startup measure` on `exec_c2_slowcli` reports `slowcli._heavy` with a median cumulative ≥ 55 ms, plus two CRT206 findings |
| A-C2-05 | On Python 3.15, `startup compare` on `exec_c2_slowcli` reports a **significant** advisor saving with a 95 % CI lower bound ≥ 40 ms, leaves the original project byte-identical, and removes its temp directory |
| A-C2-06 | All statistics property tests (T-C2-10…T-C2-13) pass with the `ci` profile |
| A-C2-07 | `startup pth` reports the exact expected CRT205 set on the fabricated site-dir fixture and runs without error against the project's own `.venv` |
| A-C2-08 | The dogfood import-set test passes on all CI cells; `cartographer --version` median on 3.15 is recorded against the 150 ms budget |
| A-C2-09 | On at least one pinned corpus CLI, run through the Docker harness (`--network none`), `startup compare` reports a significant saving; the numbers, command and image digest are recorded in the write-up. If no corpus repo shows a significant win, the write-up explains why, with the measured data (that is still a valid result, but A-C2-09 is then marked "not met" and the owner decides) |
| A-C2-10 | CRT201–CRT206 `IMPLEMENTED` with complete explanations; SARIF fixes validate |
| A-C2-11 | Spike notes S-01, S-02, S-11, S-15 (C2 part) and S-06 Part A exist; any spec changes they forced are merged |
| A-C2-12 | Six concept notes written and ticked; walkthrough, write-up and comparison exist |

## 12. Documentation deliverables

### 12.1 Concept notes (Stage 2)
| Slug | Must include |
|---|---|
| `module-execution-and-side-effects` | "A module is a script that runs once" demo with a `print` at the top of a module imported twice; `sys.modules` caching; what runs when `def`/`class` statements execute (decorators, defaults, class bodies); the side-effect taxonomy with one example each; registration patterns (decorator registries, `atexit`, signals, entry points), with a forward link to C3's `__init_subclass__`; why side effects make code slower to start and harder to test |
| `lazy-imports` | PEP 810 syntax and placement rules (from S-01, with exact error messages for invalid placements); `__lazy_modules__`; global switches; proxies and reification, with a demo that prints when a module is actually imported; all four gotchas, each with a runnable 3.15 demo (`# Python 3.15+` blocks); the dataclass-annotation trap; how lazy imports compare with "import inside the function" and with `importlib.util.LazyLoader` |
| `importtime` | How to run it; reading the output (self vs cumulative, microseconds, indentation, children-before-parent); why the first run differs (`.pyc` compilation, OS file cache); `-X importtime=2` (if S-02 confirms); `pycache_prefix` |
| `site-and-pth-files` | What `site.py` does at startup; `site-packages`, user site; `.pth` path lines vs `import` lines; why executable lines are a stealth/persistence risk (forward link to C6); `-S`, `-s`, `-I`; PEP 829 and `.start` files (from S-11); editable installs and their `.pth` files |
| `subprocess` | `subprocess.run` with list arguments vs `shell=True` (with an injection demo); `capture_output`, `text`, `encoding`, `errors`; timeouts; return codes; environment and `-I`; never interpolating untrusted text into `-c` code; how our `FakeRunner` makes subprocess code testable (dependency injection again) |
| `measuring-performance` | Noise sources; warm-up; why medians; percentiles; the bootstrap explained with a 10-number example done by hand, then in code; confidence intervals and what "95 %" means (and doesn't); interleaving/rotation; significance as "CI excludes zero"; why one run proves nothing |

### 12.2 Walkthrough (`docs/learn/walkthroughs/C2.md`)
Reading order: `cli/commands/startup.py` → `startup/advisor.py` (driven by `analyze_startup`) → `startup/side_effects.py` → `startup/names.py` → `graph/usage.py` → `startup/lazy.py` → `startup/importtime.py` → `startup/runner.py` → `startup/stats.py` → `startup/measure.py` → `startup/compare.py` → `startup/pth.py`. End-to-end trace of `exec_c2_slowcli`: the alias map of `cli.py`; the `Use` list for `report`; the candidate decision table (C1–C6 per import); the `Edit`s; the copied tree; the argv of one run; one raw importtime stderr and its parsed tree; the bootstrap resamples (first 5) and the final CI. Mermaid diagrams: the analyze data flow and the compare sequence (copy → edit → validate → smoke → interleave → report).

### 12.3 Write-up (`docs/learn/writeups/C2.md`)
Must include: S-01/S-02/S-11 findings ("the docs said X, reality was Y"); `exec_c2_slowcli` numbers on 3.15 and on 3.13 (measure only); the corpus harness results (repo@SHA, module, image digest, variant table, saving + CI); precision of CRT201 and CRT202 on two corpus repos (sample 20 each, classify TP/FP, and list false-positive patterns); Cartographer's own `--version` time vs the budget, before and after `__lazy_modules__`; noise analysis (CI width vs number of runs: 5, 10, 20, 50); the prediction table.

### 12.4 Reference comparison (`docs/learn/comparisons/C2.md`)
Against **importcost** and **lazysafe** (primary), and briefly **flake8-lazy**, **Lifeguard** and **lazy-fix** where their docs/code are available. Questions:
1. How do they measure import cost? Is it `-X importtime`, their own timing, or static estimates? How do they handle noise?
2. How does lazysafe decide an import is safe to make lazy? Which of our criteria C1–C6 does it have, and which does it have that we lack?
3. Do any of them detect registration side effects or "defeated" lazy imports?
4. Run them (where possible, on our own fixtures only) and compare findings on `exec_c2_slowcli` and `c2_lazy_candidates` in a table.
5. What would we change in our taxonomy after reading theirs?

## 13. Reference implementations to compare after
importcost, lazysafe (primary); flake8-lazy, Lifeguard, lazy-fix (secondary). See §12.4. Don't read their source before acceptance (D-008).

## 14. Risks & open items
| Item | Link | Mitigation |
|---|---|---|
| PEP 810 details differ from the research summary (placement, `__lazy_modules__`, switches, AST shape) | S-01, S-10, R-01 | Everything dependent is marked Provisional and changed in the spike PR |
| importtime format differs across versions, or parents lack their own lines | S-02 | Baseline-subtraction design doesn't depend on parent lines. Parser driven by recorded fixtures |
| Noisy CI machines make timing tests flaky | R-04 | Only robust lower bounds are asserted (sleep-based fixture). Everything else uses FakeRunner/FakeClock |
| Side-effect heuristics are noisy on real code | R-05 | CRT201 is `info`. Precision is measured in the write-up. `pure-calls` config exists |
| Corpus measurement needs code execution | D-013, D-052 | Docker harness only (phase 7). Never on the host. Recorded as D-013's corpus rule and D-052 |
| Lazy copy behaves differently (hidden reification paths) | — | Smoke import + `failed` reporting (§5.5); `exec_c2_lazybreak` fixture |
| `copytree` following symlinks out of the project | R-06 | Ignore function skips symlinks (§6.9 step 3); test T-C2-19 |

## 15. Exercises for the learner

1. **Watch a module run.** Create `noisy.py` with `print("noisy is running!")` at the top. In a REPL, `import noisy` twice. How many prints? Now check `"noisy" in sys.modules` and try `importlib.reload(noisy)`. *Hint:* `module-execution-and-side-effects`.
2. **Read importtime by hand.** Run `python -X importtime -c "import json" 2> out.txt`. Find `json` in the output. Which line is its parent? What's json's self time vs cumulative time? Now run it again: are the numbers the same?
3. **Defeat a lazy import (3.15).** Write `lazy import json` and then `@functools.cache` on a function whose *default argument* is `json.dumps`. Use the demo from `lazy-imports` to show json gets imported immediately. Run `cartographer startup analyze` to see CRT203.
4. **🖐 Bootstrap by hand.** Take the numbers `[10, 11, 11, 12, 30]`. Do 5 bootstrap resamples with dice (or `random.choices`), compute each median, and estimate a rough interval. Why doesn't the 30 move the median much?
5. **Break a plugin.** In `exec_c2_slowcli`, change `import slowcli.plugins` to `lazy import slowcli.plugins` (3.15). Call `registry.REGISTRY` after importing `slowcli.cli`. What's in it? What does CRT204 say?
6. **Inspect your own interpreter.** Run `cartographer startup pth --python .venv\Scripts\python.exe`. For each executable line, find which package installed it and why it needs to run code at startup.
