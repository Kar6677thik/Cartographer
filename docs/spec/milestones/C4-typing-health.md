# C4: Typing health

> **Status:** Approved spec, revision 1 (2026-11-03) · **Size:** M · **Version at end:** 0.4.0
> **Depends on:** C1 (import graph: module index, import resolution, SCCs, dependencies-first order). It uses only C1's **public exports** from `cartographer.graph` (`condensation_order`, `fan_in`, the module index and resolver; 02 §3) and reuses `core/qualnames.py` from C3 (D-037). Filtering happens once in `api.py` (D-046). C3 is merged before C4 in the planned order.
> **Research:** §2.3 (Dropbox: type-checking 4 million lines), §2.4 (Meta: Pyre → Pyrefly 1.0; tooling moving to Rust), §3 "Typing" row, §00 table (Pytifex, typing conformance suite, PEP 649 breakage).
> **Codes owned:** CRT401–CRT406.
> **Spikes:** S-14 (annotation evaluation at runtime) in phase 3, S-09 (type-checker CLIs) in phase 4, S-12 (mypyc on 3.15/Windows) and S-15 (does mypyc on 3.15 also need `setuptools`?) in phase 5. All four are in 08 §1.

---

## 1. Summary

C4 answers three questions about a project's **type annotations**. An annotation is the `: int` / `-> str` part of a signature, which tools called **type checkers** use to find bugs without running code.

1. **How much of the code is annotated?** `cartographer typecov` measures **annotation coverage** per function, module and package, with precise, documented formulas. It also measures how much of that coverage is "fake", i.e. annotated as `Any`, which turns checking off.
2. **Where does `Any` leak into otherwise-typed code?** If a well-typed module exports a value that comes from an unannotated function, every consumer silently loses type checking. C4 follows values across modules (using C1's import graph) and lists the leaks, ranked by **how many modules they affect**. This is Dropbox's lesson: *type the core libraries first*.
3. **Where will annotations break at runtime?** Names imported only under `if TYPE_CHECKING:` work for type checkers but are missing at runtime. Frameworks that read annotations at runtime (pydantic, `functools.singledispatch`, sometimes dataclasses) then fail. Python 3.14's **deferred annotations** (PEP 649/749) change *when* that failure happens. CRT406 finds these.

C4 also includes two **learning studies** that produce write-ups rather than product features:
- **Checker disagreement study.** Run mypy, pyright, pyrefly and ty on a curated "typing zoo" of tricky snippets and on Cartographer itself, and explain where and *why* they disagree.
- **mypyc experiment.** Compile two hot Cartographer modules to C with mypyc and measure the speedup (Dropbox got about 4x on mypy itself).

## 2. Why this matters

**Dropbox (research §2.3).** Dropbox went from about 420,000 annotated lines (end of 2016) to almost 4 million in about three years. Their lessons:
- **Type core libraries first, or `Any` leaks everywhere.** If `utils.load_config()` is unannotated, every caller gets `Any`, and the type checker silently stops checking all code that touches the result. Coverage numbers look fine while real checking is low. C4's "precise coverage" and "Any-leak" reports expose exactly that.
- **Coverage reports drove owner-led annotation.** Per-team (per-package) reports, not automated annotation tools, got the code annotated. That's why `typecov` offers `--by package` and Markdown output suitable for a PR comment or a team dashboard.
- Clean runs took over 15 minutes. They fixed that with a daemon and with **mypyc**, which compiled mypy itself to C for about a 4x speedup. That's our mypyc experiment.

**Meta and the Rust wave (research §2.4).** Pyrefly 1.0 (12 May 2026) checks about 1.8 million lines per second and is Instagram's default checker. Astral's ty is in beta. pyright powers VS Code's Pylance. **These checkers disagree on the same code**, because the typing spec leaves room for choices: how to infer `x = []`, whether to check the bodies of unannotated functions, how to narrow. Understanding *why* they disagree is the best way to understand how type checkers work.

**PEP 649/749 (research §2.12, 3.14).** Annotations are now evaluated **lazily**, only when something asks for them. Code that "worked" because nothing read its annotations can break when a library starts reading them, or start working on 3.14 when it failed on 3.13. Ruff's `flake8-type-checking` rules handle part of this with a configurable list of "runtime-evaluated base classes" (research §00). We build our own version and compare.

## 3. Read before starting

**Existing concept notes:** `type-hints-basics`, `ast-basics`, `import-system`, `type-checking-guard`, `graphs-and-scc` (C1), `class-registries`, `decorators` (C3), `measuring-performance` (C2).

**Written in this milestone:** `gradual-typing`, `generics-and-variance`, `protocols-and-structural-typing`, `typeddict-overloads-paramspec`, `narrowing`, `annotations-at-runtime`, `how-type-checkers-work`, `mypyc`.

**Prediction questions** (`docs/learn/predictions/C4.md`):
1. A function `def f(x: int, y) -> str` has how many "annotation slots", and how many are filled?
2. Should `self` count as a missing annotation? What about `__init__`'s return type?
3. Module A is 100 % annotated, but its public constant `CONFIG = load()` comes from an unannotated function in module B. What type does a checker give `CONFIG`, and what happens to the checking of code that uses it?
4. If `from typing import Any` appears in 30 places, is the code "less typed" than code with no annotations at all? Why might coverage be misleading?
5. You import `Decimal` only under `if TYPE_CHECKING:` and use it in a `@dataclass` field annotation. On Python 3.13 without `from __future__ import annotations`, what happens at import time? On 3.14?
6. mypy and pyright see `def f(): return 1` (no annotations). What does each think `f()` returns? Will they report errors *inside* unannotated functions?
7. Which will mypyc speed up more: Tarjan's SCC algorithm (pure-Python loops over dicts and lists) or `SourceFile` creation (mostly calls into `ast.parse`, which is C)? By roughly how much?
8. Is `list[int]` a subtype of `list[float]`? Is `Sequence[int]` a subtype of `Sequence[float]`? Why the difference?
9. Do you expect the four checkers to agree on most of the "typing zoo" snippets? Name a feature you think they'll disagree on.
10. If we parse 2,000 files with 4 threads on the free-threaded 3.15t build, how much faster than 1 thread do you expect? What could stop it from scaling?

## 4. Scope

### In scope
- Coverage metrics (§6.2) for `.py` and `.pyi` files, rolled up per function, module, package and project.
- Public-API detection (§6.3).
- Diagnostics CRT401–CRT406.
- Any-leak propagation using C1's graph, with confidence levels and a "fix these first" ranking.
- `typecov` output in text, json, markdown and sarif.
- Scripts: `scripts/checker_matrix.py` (disagreement study), `scripts/mypyc_experiment.py`, `scripts/annotation_runtime_matrix.py` (S-14), plus benchmarks.
- Making Cartographer clean under pyright (strict), pyrefly and ty where reasonable, and documenting the remaining disagreements. Cartographer is already required to pass `mypy --strict` from M0 (05 §2).

### Out of scope (and why)
| Not doing | Why |
|---|---|
| Real type inference | That's a type checker's job. We measure *annotations* and follow *simple* value flows (§6.4) |
| Class attribute / instance attribute coverage | v1 measures function signatures and module-level variables only. Attributes need class-body and `__init__` analysis (stretch) |
| Inferring return types of unannotated functions | We follow **mypy's convention**: an unannotated function returns `Any`. Pyright infers instead, which is documented as a known difference |
| Parsing annotations inside docstrings / Sphinx types | Not annotations |
| Shipping mypyc-compiled wheels | D-030 (stretch in C8) |
| Running type checkers as part of `typecov` | The checker study is a script for learning, not a product feature |

## 5. User-facing behaviour

### 5.1 `cartographer typecov`

```
cartographer typecov [PATH] [--by module|package] [--public-only] [--fail-under PCT]
                     [--top N] [--format text|json|markdown|sarif] [-o FILE]
```
- `--by`: rollup level of the table (default `module`). `package` groups by the dotted name up to `typecov.package-depth` components (default 2, e.g. `pkg.sub`).
- `--public-only`: the table counts only public functions (§6.3). Diagnostics are unaffected.
- `--fail-under PCT`: same as config `fail-under` (per module, §7 CRT405). **When a threshold is set (flag or config) and you did not pass `--fail-on` explicitly, `typecov` uses `--fail-on warning`** (D-053). CRT405 is a warning, so under the default `--fail-on error` the gate would never fail. An explicit `--fail-on` always wins.
- `--top N`: length of the "fix these first" list (default 10).

**Fixture `tests/fixtures/projects/typecov_basic/`:**
```python
# pkg/__init__.py        (empty)

# pkg/core.py
def add(a: int, b: int) -> int:                 # 1
    return a + b                                # 2
                                                # 3
                                                # 4
class Box:                                      # 5
    def __init__(self, v: int) -> None:         # 6
        self.v = v                              # 7
                                                # 8
    def get(self) -> int:                       # 9
        return self.v                           # 10

# pkg/api.py
from typing import Any                          # 1
from pkg.core import add                        # 2
                                                # 3
def fetch(url):                                 # 4
    return url                                  # 5
                                                # 6
def parse(data: Any) -> dict[str, int]:         # 7
    return {}                                   # 8
                                                # 9
def _helper(x: int, y):                         # 10
    return add(x, y)                            # 11
```
Slot counting (§6.2):
- `core.py`: `add` has 3 slots (a, b, return), 3 annotated. `Box.__init__`: `self` is excluded, and the return slot is excluded because a parameter is annotated, leaving 1 slot (`v`), 1 annotated. `Box.get`: `self` excluded, 1 slot (return), 1 annotated. **Total 5/5, 100.0 %.**
- `api.py`: `fetch` 0/2. `parse` 2/2 (1 `Any` slot). `_helper` 1/3. **Total 3/7 = 42.9 %. Precise (3 − 1)/7 = 28.6 %.**
- Project: 8/12 = 66.7 %. Precise 7/12 = 58.3 %.

Expected output (golden `tests/golden/typecov/typecov_basic.text`):
```
$ cartographer typecov tests/fixtures/projects/typecov_basic
Module     Funcs  Full  Partial  None  Slots  Annotated  Any  Coverage  Precise
pkg            0     0        0     0      0          0    0         –        –
pkg.api        3     1        1     1      7          3    1     42.9%    28.6%
pkg.core       3     3        0     0      5          5    0    100.0%   100.0%
TOTAL          6     4        1     1     12          8    1     66.7%    58.3%

pkg/api.py:4:1: CRT401 [info] public function `pkg.api.fetch` is missing annotations: parameter `url`, return
  help: annotate it, starting with the return type: callers of an unannotated function get `Any`
pkg/api.py:7:17: CRT402 [info] explicit `Any` in annotation of parameter `data` of `pkg.api.parse`
  help: use a precise type, or `object` if any value is accepted but must be checked before use

Found 0 errors, 0 warnings, 2 info in 3 files (0.03 s).
```
Notes, each pinned by a test:
- Rows are sorted by module name. Numbers are right-aligned. Percentages have one decimal. `–` means "no slots".
- `_helper` is private, so it gets no CRT401.
- `pkg.api` is below the typed threshold (80 %), so its leaks are *not* CRT403 (§6.4). It's simply untyped, and CRT401 describes it.
- `Any` columns: `Any` = number of slots whose annotation contains `Any` anywhere. Precise = (Annotated − Any)/Slots.

**Leak fixture `tests/fixtures/projects/typecov_leaks/`:**
```python
# pkg/__init__.py        (empty)

# pkg/loader.py
import json                                     # 1
                                                # 2
                                                # 3
def load_config(path):                          # 4
    with open(path, encoding="utf-8") as f:     # 5
        return json.load(f)                     # 6

# pkg/settings.py
from pkg.loader import load_config              # 1
                                                # 2
CONFIG = load_config("settings.json")           # 3
                                                # 4
                                                # 5
def get_timeout(default: int = 30) -> int:      # 6
    return int(CONFIG.get("timeout", default))  # 7
                                                # 8
                                                # 9
def get_name() -> str:                          # 10
    return str(CONFIG["name"])                  # 11
```
```
$ cartographer typecov tests/fixtures/projects/typecov_leaks
Module         Funcs  Full  Partial  None  Slots  Annotated  Any  Coverage  Precise
pkg                0     0        0     0      0          0    0         –        –
pkg.loader         1     0        0     1      2          0    0      0.0%     0.0%
pkg.settings       2     2        0     0      3          3    0    100.0%   100.0%
TOTAL              3     2        0     1      5          3    0     60.0%    60.0%

Fix these first (unannotated or Any symbols, by number of modules affected):
  1. pkg.loader.load_config  (pkg/loader.py:4)  affects 1 module, 1 leak

pkg/loader.py:4:1: CRT401 [info] public function `pkg.loader.load_config` is missing annotations: parameter `path`, return
  help: annotate it, starting with the return type: callers of an unannotated function get `Any`
pkg/settings.py:3:1: CRT403 [warning] public `pkg.settings.CONFIG` is implicitly `Any`: assigned from unannotated `pkg.loader.load_config()` (pkg/loader.py:4)
  help: annotate `load_config`'s return type, or annotate `CONFIG` explicitly (e.g. `CONFIG: dict[str, object] = ...`)
  related: pkg/loader.py:4:1 (origin: unannotated function)

Found 0 errors, 1 warning, 1 info in 3 files (0.03 s).
```

### 5.2 JSON payload (`--format json`, inside the 02 §4.8 envelope)

```json
"payload": {
  "schema": "cartographer.typecov/1",
  "totals": {"functions": 6, "full": 4, "partial": 1, "none": 1, "slots": 12,
             "annotated": 8, "any": 1, "coverage": 0.6667, "precise_coverage": 0.5833},
  "modules": [
    {"module": "pkg.api", "path": "pkg/api.py", "kind": "source", "shadowed_by_stub": false,
     "typed": false, "functions": 3, "full": 1, "partial": 1, "none": 1, "slots": 7,
     "annotated": 3, "any": 1, "coverage": 0.4286, "precise_coverage": 0.2857,
     "type_ignores": 0, "bare_type_ignores": 0,
     "public": {"functions": 2, "slots": 4, "annotated": 2, "any": 1, "coverage": 0.5, "precise_coverage": 0.25}}
  ],
  "functions": [
    {"qualname": "pkg.api.fetch", "path": "pkg/api.py", "line": 4, "public": true,
     "slots": 2, "annotated": 0, "any": 0, "status": "none", "missing": ["url", "return"], "via": "annotations"}
  ],
  "leaks": [],
  "fix_first": []
}
```
Ratios are floats rounded to 4 decimals, or `null` when there are no slots. Lists are sorted (modules by name, functions by `(path, line)`).

### 5.3 Markdown (`--format markdown`), for PR comments and team dashboards
```markdown
## Type coverage: 66.7 % (precise 58.3 %)

| Module | Functions | Coverage | Precise | `Any` slots | Status |
|---|---:|---:|---:|---:|---|
| `pkg.api` | 3 | 42.9 % | 28.6 % | 1 | partial |
| `pkg.core` | 3 | 100.0 % | 100.0 % | 0 | typed |

### Fix these first
_None._

<sub>Generated by Cartographer 0.4.0 · thresholds: typed ≥ 80 %</sub>
```
Status values: `typed` (coverage ≥ typed-threshold), `partial` (0 < coverage < threshold), `untyped` (0 %), `–` (no slots).

### 5.4 Scripts (not CLI commands)

| Script | Purpose | Output |
|---|---|---|
| `scripts/checker_matrix.py [--zoo] [--self] [--tools mypy,pyright,pyrefly,ty]` | Run checkers and compare (§6.7) | `docs/learn/writeups/data/C4-checker-matrix.json` + generated table `docs/learn/writeups/C4-checker-matrix.md` |
| `scripts/annotation_runtime_matrix.py` | S-14 experiment (§6.6) | `docs/learn/spikes/S-14-annotations-at-runtime.md` data table |
| `scripts/mypyc_experiment.py` | Compile + benchmark (§6.8) | numbers for the write-up |
| `benchmarks/bench_parallel_parse.py` | 3.15t stretch (§6.9) | numbers for the write-up |

## 6. Design

### 6.1 Files

| File | Phase | Contents |
|---|---|---|
| `typecov/__init__.py` | 1 | exports `type_coverage`, models |
| `typecov/model.py` | 1 | `Slot`, `FunctionCoverage`, `ModuleCoverage`, `Totals`, `Leak`, `TypecovPayload` |
| `typecov/collect.py` | 1 | AST walk: find functions, classify slots, detect `Any`, type comments |
| `typecov/public_api.py` | 1 | public names, `__all__` evaluation, re-exports |
| `typecov/metrics.py` | 1 | aggregation, rollups, rounding |
| `typecov/ignores.py` | 1 | `# type: ignore` scanning via `tokenize` (CRT404) |
| `typecov/leaks.py` | 2 | symbol table, lattice, fixpoint propagation over C1 SCCs, fan-in ranking (CRT403) |
| `typecov/_walk.py` | 1 | `ScopedVisitor`: `ast.NodeVisitor` with scope and annotation tracking (no dependency on C3's dispatcher) |
| `typecov/runtime_annotations.py` | 3 | CRT406 |
| `typecov/render.py` | 1 | text table + markdown renderer (registered with `output`) |
| `cli/commands/typecov.py` | 1 | subcommand |
| `api.py` | 1 | `type_coverage(project, config) -> Result[TypecovPayload]` |
| `scripts/checker_matrix.py` | 4 | §6.7 |
| `tests/fixtures/typing_zoo/*.py` | 4 | §6.7 |
| `scripts/annotation_runtime_matrix.py`, `tests/fixtures/annotations_runtime/*.py` | 3 | §6.6 |
| `scripts/mypyc_experiment.py`, `benchmarks/bench_scc.py`, `benchmarks/bench_source.py` | 5 | §6.8 |
| `benchmarks/bench_parallel_parse.py` | 5 (stretch) | §6.9 |

### 6.2 Coverage metrics: exact definitions

**Annotation slot.** One position where an annotation can be written: each parameter (positional-only, positional-or-keyword, `*args`, keyword-only, `**kwargs`) and the return of each function. A slot is **annotated** if the AST has an annotation there (`arg.annotation is not None` / `returns is not None`), or if the function has a **type comment** (`# type: (int, str) -> bool`, parsed via `ast.parse(..., type_comments=True)`; then every slot of that function is annotated and `via = "type_comment"`). Dropbox started on type comments, so they must count.

**Which functions are counted:** every `FunctionDef` and `AsyncFunctionDef` in the file, including nested functions and methods, and including those inside `if TYPE_CHECKING:` blocks. **Lambdas are not counted**, since they can't be annotated (`stats.lambdas_skipped` reports how many).

**Excluded slots** (they don't count towards either total):

| Rule | Why |
|---|---|
| The **first parameter** of a function defined *directly* in a class body, unless decorated `@staticmethod` (resolved via qualnames, so `@builtins.staticmethod` works too). This covers `self`, `cls` in `@classmethod`, `cls` in `__new__` and `mcs` in metaclass methods, whatever the parameter is named | Checkers infer it |
| The return slot of `__init__` **if at least one other parameter is annotated** | mypy treats such `__init__` as typed with implicit `-> None`. With no annotated parameters, mypy needs `-> None` to check it at all, so the slot counts |
| The return slot of a `@<prop>.setter` / `@<prop>.deleter` method | Always `None`, never consumed |
| **Overload implementation:** a function with the same name, in the same scope, immediately following one or more `@overload`-decorated definitions (`typing.overload` / `typing_extensions.overload`), *excluding* any decorated with `@overload`. The `@overload` variants are counted normally | Implementations are deliberately loose. Checkers check them against the overloads |

**Per function:** `S_f` = counted slots, `A_f` = annotated slots, `Y_f` = annotated slots whose annotation contains `Any` (§6.2.1).
- `status` = `"full"` if `A_f == S_f`, `"none"` if `A_f == 0`, else `"partial"`. If `S_f == 0`, then `status = "trivial"` and the function is excluded from the function counts. Example: a property deleter `@x.deleter def x(self): ...`, where `self` and the return are both excluded.
- `missing`: the names of unannotated slots in signature order, with `"return"` last.

**Per module `m`:** `S_m = Σ S_f`, `A_m = Σ A_f`, `Y_m = Σ Y_f` over counted functions.
- `coverage_m = A_m / S_m`, and `precise_coverage_m = (A_m − Y_m) / S_m`. Both are `None` if `S_m = 0`.
- `functions/full/partial/none` = counts of functions by status (excluding trivial).
- `typed_m` = `coverage_m is not None and coverage_m ≥ typed_threshold / 100`.

**Stubs.** `.pyi` files are counted with `kind = "stub"`. If `mod.py` and `mod.pyi` both exist for the same module, the `.py` is reported with `shadowed_by_stub = true` and **excluded from totals and rollups**, because checkers use the stub. Its diagnostics are still reported.

**Rollups.** For a package `p` (`--by package`): sum `S`, `A`, `Y` and the counts over all modules whose name equals `p` or starts with `p.`, then compute the ratios from the sums. **Project totals** are slot-weighted sums over all non-shadowed modules (not an average of module percentages, so big modules weigh more).

**Public variants:** the same formulas restricted to public functions (§6.3).

#### 6.2.1 Detecting `Any`
An annotation *contains `Any`* if any `Name`/`Attribute` node in it resolves (via `core/qualnames.py`) to `typing.Any` or `typing_extensions.Any`. **String annotations** (`"Any"`, `"dict[str, Any]"`) are parsed with `ast.parse(s, mode="eval")` and checked the same way. A string that fails to parse counts as annotated with `data.unparseable_annotation = true` and no `Any`. With `from __future__ import annotations`, annotations are still AST nodes (only *runtime* evaluation changes), so nothing special is needed. `object` is **not** `Any`.

**Worked example.** `def parse(data: Any) -> dict[str, int]` has S=2, A=2, Y=1, status `full`. It contributes 2/2 to coverage but only 1/2 to precise coverage.

### 6.3 Public API

1. **Public module:** no component of its dotted name starts with `_`, except that the module `__init__` is ignored. `__main__` is private. Modules matched by `typecov.exclude` globs (default `["tests/**", "test/**", "**/conftest.py"]`) are excluded from all metrics.
2. **Public name in a public module:**
   - If the module defines `__all__` *statically*, public names = exactly that set. Static forms are `__all__ = [...]`/`(...)` of string literals, `__all__ += [...]`, `__all__.extend([...])` and `__all__.append("x")`, all at module level, evaluated in order. If any other assignment to `__all__` exists, or a non-literal element appears, `__all__` is **dynamic**: fall back to rule (b) and set `data.dynamic_all = true` on that module.
   - (b) otherwise: names **defined** in the module (`def`, `class`, assignment targets) not starting with `_`. Dunder names (`__x__`) are public. **Imported names are not public under (b)**: they only become public through rule 5.
3. **Public method:** the class is public (by rule 2 in its module) and the method name is public by rule 2(b). Dunder methods like `__eq__` are public.
4. **Nested functions** are never public.
5. **Re-exports (explicit only).** An imported name in public module `m` is a **re-export** only if (a) it's listed in `m`'s static `__all__`, or (b) it's imported with the redundant-alias form `import X as X` / `from d import f as f`. This is the convention mypy uses with `implicit_reexport = False` and the one PEP 484 sets for stubs. A plain `from pkg.loader import load_config` is **not** a re-export, which is why `typecov_leaks` reports only `CONFIG`. A function defined in module `d` that is re-exported by a public module is public too. Imports are resolved through C1's resolver. Re-exports are reported in `data.reexported_by`. With a *dynamic* `__all__`, only form (b) counts.

### 6.4 Any-leaks (CRT403)

**Definition.** A **leak** is a *public symbol of a typed module* whose type, as a checker following mypy's conventions sees it, is `Any`. "Typed module" means coverage ≥ `typed-threshold`: the module's author tried, and consumers expect checking. Symbols considered:
- public function **parameter or return slots** (unannotated, or containing `Any`);
- public **module-level variables** (`NAME = expr`, `NAME: T = expr`);
- public **re-exported names** (imports that a typed module makes public).

**Status lattice** (for each symbol):
```
BOTTOM  <  TYPED  <  UNKNOWN  <  ANY
```
`ANY` carries an `origin` chain: a list of `(symbol, location, reason)` hops, where reason ∈ {`explicit-any`, `unannotated-function`, `unannotated-parameter`, `attribute-of-any`, `untyped-external`}. Join is the max. When joining two `ANY` values, keep the **shorter chain**, with ties broken by lexicographic order of the origin's qualified name (determinism).

**Evaluation of one symbol:**
| Symbol / expression | Status |
|---|---|
| function return annotated, no `Any` | TYPED |
| function return annotated with `Any` | ANY (`explicit-any`, 0 hops) |
| function return unannotated (mypy convention) | ANY (`unannotated-function`, 0 hops) |
| variable with annotation | as its annotation (TYPED, or ANY `explicit-any`) |
| `NAME = <literal / display of literals / f-string>` | TYPED |
| `NAME = f(...)`, `f` resolves (qualnames + C1 module index) to a **project function** | status of `f`'s return, with chain `+1 hop` |
| `NAME = C(...)`, `C` resolves to a **project class** | TYPED |
| `NAME = other_name` | status of `other_name` (same module or imported), `+1 hop` |
| `NAME = x.attr` / `x[i]` / `x.method()` where `x` is ANY | ANY (`attribute-of-any`, `+1 hop`) |
| anything resolving outside the project, in `typecov.untyped-modules` | ANY (`untyped-external`, 0 hops) |
| anything else (external calls, comprehensions, arithmetic, …) | UNKNOWN (we can't tell, so it isn't reported) |
| imported name `from m import X` | status of `m.X` |

**Propagation algorithm** (dependencies first, using C1):
```
from cartographer.graph import EdgeKind, condensation_order   # C1 public exports (02 §3)

RUNTIME_KINDS = frozenset({EdgeKind.MODULE, EdgeKind.OPTIONAL, EdgeKind.DEFERRED})
# TYPE_CHECKING (`typing`) edges create no runtime values; `dynamic` edges have no names to follow.

order = condensation_order(graph, kinds=RUNTIME_KINDS)   # SCCs, dependencies first
status = defaultdict(lambda: BOTTOM)
for scc in order:
    symbols = [s for m in sorted(scc) for s in m.symbols]  # deterministic order
    bound = 3 * len(symbols) + 2 * total_chain_shortenings_bound(symbols) + 1   # see below
    iterations = 0
    while True:                                            # run to the fixpoint
        iterations += 1
        changed = False
        for sym in symbols:
            new = join(status[sym], evaluate(sym, status))
            if new != status[sym]: status[sym] = new; changed = True
        if not changed: break
        if iterations > bound:                             # bug guard, never expected
            raise AnalysisError(f"typecov: no fixpoint in {scc} after {bound} iterations")
```
**Why it terminates, and where the bound comes from:** the status lattice has height 4, so each symbol's *status* can rise at most 3 times. Once a symbol is ANY, its chain can only get **shorter**, and a chain is never longer than the number of symbols in the SCC plus the longest chain entering it from earlier SCCs (`total_chain_shortenings_bound`). Every iteration that doesn't reach the fixpoint changes at least one symbol, so the loop ends within `3·n + 2·L + 1` iterations, where `n` is the symbol count and `L` the chain bound. The loop runs **until nothing changes**: there is no fixed iteration cap like 20, which an SCC with a chain of 21 modules could exceed. Exceeding the derived bound raises `AnalysisError` (exit 3), because it can only mean a bug in `join` or `evaluate`. T-C4-31 builds a 50-module cyclic chain to prove the loop isn't artificially capped.

**Reporting.** For each typed module `M`, and each public symbol of `M` with status ANY whose confidence ≥ `min-leak-confidence`, emit one **CRT403**:
| Confidence | Condition |
|---|---|
| `high` | 0 hops: an unannotated slot or explicit `Any` directly in a public signature/variable of `M` |
| `medium` | exactly 1 hop (e.g. `CONFIG = load_config()`, `load_config` unannotated) |
| `low` | ≥ 2 hops, or any `attribute-of-any` hop |

**Dedup with CRT401/CRT402.** If CRT403 is reported for a function slot, CRT401 (same function) and CRT402 (same annotation) are **not** reported. The more specific warning wins.

**"Fix these first" ranking** (`payload.fix_first`, and the text section): group leaks by their chain's **root origin** symbol. Rank roots by **fan-in count** descending. With `S = {root module} ∪ {modules re-exporting the root}`, it is `len(frozenset().union(*(fan_in(graph, m, kinds=RUNTIME_KINDS) for m in S)) - S)`: the number of distinct project modules outside `S` that import any module in `S`. (`fan_in` is the C1 export `fan_in(graph, module, *, kinds, implicit=False, include_scripts=False) -> frozenset[str]`, C1 §6.12.) Then then leaks caused descending, then name. This is Dropbox's "core libraries first", made concrete.

**Complexity:** O(Σ symbols × iterations), effectively linear in project size.

**Edge cases (tests):**
- An untyped module (below threshold) never gets CRT403. Its public functions get CRT401.
- A variable assigned twice at module level is the join of both.
- `CONFIG: dict[str, object] = load_config(...)` (explicitly annotated) is TYPED. No leak (the annotation is a promise the checker enforces at the assignment).
- Cyclic imports: `a.X = b.f()` and `b.f` returns `a.Y`, all unannotated. They converge within the SCC.
- A star import (`from m import *`) makes the importing module's names derived from it UNKNOWN (precision).
- `typing.TYPE_CHECKING`-only imports don't create runtime values. They're ignored for leak propagation.
- Dynamic `__all__`: public set from underscore rules, `data.dynamic_all = true`.

### 6.5 Other diagnostics: triggers

**CRT401 `unannotated-public-function`** (info): a public function (§6.3) with `A_f < S_f`, in **any** module (typed or not), unless superseded by CRT403. Location: the `def` keyword (`FunctionDef.lineno`/`col_offset`, which is the `def` line even with decorators). Message: ``public function `{qualname}` is missing annotations: {missing list}``, e.g. ``parameter `url`, return``. `data`: `{"qualname", "missing": [...], "slots", "annotated"}`.

**CRT402 `explicit-any`** (info): every annotation that contains `Any` (§6.2.1), in any function slot or annotated variable, public or not, unless superseded by CRT403. Location: the `Any` node (inside a string annotation: the string's location, with `data.in_string = true`). Message: ``explicit `Any` in annotation of {parameter `x` | return | variable `NAME`} of `{qualname}` ``. `data`: `{"qualname", "slot", "in_string"}`.

**CRT403 `any-leak`** (warning): §6.4. Message forms:
- 0 hops, unannotated: ``public `{qualname}` in typed module `{M}` has an unannotated {return | parameter `x`}: callers get `Any` ``
- 0 hops, explicit: ``public `{qualname}` in typed module `{M}` exposes explicit `Any` in {slot}``
- ≥ 1 hop: ``public `{qualname}` is implicitly `Any`: {first hop description} ({origin location})``, where the first-hop description is e.g. ``assigned from unannotated `pkg.loader.load_config()` ``.
`data`: `{"symbol", "kind": "function-slot" | "variable" | "reexport", "slot": str | null, "confidence", "chain": [{"symbol", "path", "line", "reason"}], "root": "<qualname>"}`. Related: one entry per chain hop.

**CRT404 `bare-type-ignore`** (info): a `COMMENT` token (via `tokenize`) matching `#\s*type:\s*ignore(?!\[)`. Location: the comment. Also counted: total `type: ignore` comments per module in `type_ignores`, bare ones in `bare_type_ignores`. Message: ``bare `# type: ignore` hides every error on this line; add the error code, e.g. `# type: ignore[attr-defined]` ``. `data`: `{"comment"}`.

**CRT405 `coverage-below-threshold`** (warning): only when `fail-under` is set (config or `--fail-under`). One per non-shadowed module with `coverage_m < fail_under / 100` (modules with no slots are skipped). **Units:** `coverage_m` is a fraction in [0, 1] (§6.2), while `fail-under` is a percent in [0, 100], so the comparison divides by 100. The message prints both as percents. Location: `path:1:1`. Message: ``module `{m}` annotation coverage is {cov:.1f} %, below the threshold of {t:.1f} %``. Also **one project-level CRT405** if the project total coverage (a fraction) is below `fail_under / 100`, located at `pyproject.toml:1:1` if that file exists, otherwise at line 1 of the first analysed file in sort order, with `data.scope = "project"`. `data`: `{"scope": "module" | "project", "coverage", "threshold"}`.

### 6.6 CRT406 `type-checking-import-at-runtime`

**Background (concept note `annotations-at-runtime`).**
- Python ≤ 3.13 without `from __future__ import annotations`: function and class annotations are evaluated **at definition time**. A `TYPE_CHECKING`-only name in an annotation is an immediate `NameError` at import, which the author would notice quickly.
- With `from __future__ import annotations` (any version): annotations are stored as **strings**, never evaluated unless something asks (for example `typing.get_type_hints`).
- Python ≥ 3.14 (PEP 649/749): annotations are evaluated **lazily**, on first access of `__annotations__`. `annotationlib.get_annotations(obj, format=…)` offers formats that tolerate undefined names, such as `FORWARDREF` and `STRING`.

So a `TYPE_CHECKING`-only name breaks **when something evaluates the annotation**. Whether a given library does that, and in which format, is exactly what spike S-14 measures.

**TYPE_CHECKING-only names.** Names bound by imports inside the body of `if <cond>:` at module level, where `<cond>` resolves (qualnames) to `typing.TYPE_CHECKING` or `typing_extensions.TYPE_CHECKING`, and that are **not** bound anywhere else at module level (including the `else:` branch). Imports inside `if TYPE_CHECKING:` blocks in functions follow the same rule, scoped to the function.

**Use classification.** For each `Name` (Load) whose id is a TC-only name, walking with C4's own small `ast.NodeVisitor` subclass, `typecov/_walk.py:ScopedVisitor`. It tracks the scope stack and whether it's inside an annotation. C4 does **not** import C3's dispatcher, because 02 §3 allows no `typecov → rules` import. The concept note `visitor-pattern` compares the two walkers:
| Context of the use | Result |
|---|---|
| inside another `if TYPE_CHECKING:` block | fine |
| inside a string literal that is *not* an annotation | fine (it's just text) |
| a **non-annotation runtime expression**: `isinstance(x, Foo)`, `cast(Foo, x)` (the first argument *is evaluated*), a default value, a base class, a decorator, a module-level expression | **CRT406, confidence high, reason `runtime-use`** |
| an annotation (including string annotations, parsed as in §6.2.1) of a class whose bases or decorators include a **runtime-evaluated consumer** (catalogue below), or of a function decorated by one | **CRT406, reason `runtime-evaluated-class` / `runtime-evaluated-decorator`, confidence from the catalogue** |
| the first-parameter annotation of a function decorated with `@<f>.register` where `<f>` is bound in the same module to a function decorated with `functools.singledispatch` (or a `singledispatchmethod`) | **CRT406, reason `runtime-evaluated-decorator`, high** (registration reads the annotation) |
| any other annotation | fine |

**Runtime-evaluated consumer catalogue** (config: `runtime-evaluated-bases`, `runtime-evaluated-decorators`, each entry `"qualname"`; defaults below). Project-local subclasses are followed: `class Base(BaseModel)` in `a.py`, then `class Child(Base)` in `b.py`, is still a consumer (resolved via C1, depth ≤ 10, cycles guarded).

| Consumer | Kind | Default confidence | Status |
|---|---|---|---|
| `pydantic.BaseModel` | base | high | pydantic builds validators from annotations, so they must resolve |
| `functools.singledispatch` `.register` | decorator (special form above) | high | registration inspects the annotation |
| `dataclasses.dataclass` | decorator | medium | **Provisional (S-14)**: depends on version and future import |
| `typing.NamedTuple`, `typing.TypedDict`, `typing_extensions.TypedDict`, `typing_extensions.NamedTuple` | base | medium | **Provisional (S-14)** |
| `attrs.define`, `attrs.frozen`, `attr.s`, `attr.define` | decorator | medium | **Provisional (S-14)** |
| `pydantic.validate_call` | decorator | high | evaluates parameter annotations |

**S-14 adjusts the confidences.** For each stdlib consumer, `scripts/annotation_runtime_matrix.py` runs a small fixture (our own code, in a subprocess, `execute`-marked) on 3.13, 3.14 and 3.15, with and without `from __future__ import annotations`. It records whether class/function creation succeeds and whether *instantiation/use* succeeds. For example, a dataclass with field `x: Decimal` where `Decimal` is TC-only: create the class, instantiate it, call `dataclasses.fields()`. The result table goes into the spike note and the concept note. The catalogue defaults are then updated: **a consumer that fails on the project's `target-version` → high; fails only on older versions → low with a version note; never fails → removed from defaults**. Third-party consumers (pydantic, attrs) are not run automatically (they'd need network installs). Their confidence comes from their documented behaviour and is recorded with a source link.

**Message:** ``name `{name}` is imported only under `TYPE_CHECKING` but is needed at runtime by {reason text}``, where the reason text is e.g. ```isinstance()` `` / ``pydantic `BaseModel` field annotations`` / ```functools.singledispatch` registration``. **Help:** "move the import out of the `if TYPE_CHECKING:` block". Add "(on Python {target} annotations are evaluated lazily; it fails when `{consumer}` reads them)" when relevant.
**`data`:** `{"name", "imported_from", "reason": "runtime-use" | "runtime-evaluated-class" | "runtime-evaluated-decorator", "consumer": str | null, "confidence", "target_version"}`. Diagnostics below `typecov.min-runtime-confidence` (default `"medium"`) are dropped.

**Edge cases:** `if typing.TYPE_CHECKING:` vs `from typing import TYPE_CHECKING`; `if not TYPE_CHECKING:` (the else-side is the runtime side, so names imported there are normal); a name imported both under TYPE_CHECKING and in a `try` at module level (not TC-only); a string annotation `"Foo"` in a pydantic model (still flagged, because pydantic resolves strings); `cast("Foo", x)` (fine, it's a string); `Foo` used in a `match` class pattern (runtime use, flagged).

### 6.7 Checker disagreement study (`scripts/checker_matrix.py`)

**Tools and versions.** A constant at the top of the script pins exact versions, filled in during spike S-09. Each tool runs via `uvx --from <pkg>==<version> <cmd> …`, so nothing is added to the project's dependencies. The machine-readable output flags are **Provisional (S-09)**: the script has one adapter class per tool with `command(files) -> list[str]` and `parse(stdout, stderr) -> list[CheckerFinding]`. If a tool has no JSON mode, its adapter parses text with a documented regex.

```python
@dataclass(frozen=True, slots=True)
class CheckerFinding:
    tool: str            # "mypy"
    tool_version: str
    file: str            # posix, relative to repo root
    line: int            # 1-based
    column: int | None   # 1-based if the tool provides it
    code: str | None     # tool's own error code / rule name
    severity: Literal["error", "warning", "note", "info"]
    message: str
```
Each tool runs in its **default** mode and in a documented **strict** mode, targeting Python 3.15 where the tool supports a version flag. Tools that can't target 3.15 are recorded as such.

**The typing zoo** (`tests/fixtures/typing_zoo/`). Each file is 10–40 lines. It starts with a docstring explaining what it tests, what the **typing specification** says (with a link to the spec section or conformance-suite file), and why checkers might differ. Expected-error markers:
- `# E: <reason>`: the spec requires an error on this line
- `# E?: <reason>`: the spec allows but doesn't require one
- no marker: no error expected

| File | Topic |
|---|---|
| `01_pep695_generics.py` | `def first[T](xs: list[T]) -> T`, `class Box[T]`, `type Alias[T] = …`, bounds and constraints |
| `02_variance.py` | `list` invariance vs `Sequence` covariance vs `Callable` parameter contravariance; PEP 695 inferred variance |
| `03_protocols.py` | structural subtyping, protocol with property, `@runtime_checkable` + `isinstance` |
| `04_typeddict_required.py` | `total=False`, `Required`/`NotRequired`, `ReadOnly` |
| `05_typeddict_extra_items.py` | PEP 728 `extra_items` / `closed` (3.15 typing) |
| `06_typeform.py` | PEP 747 `TypeForm` |
| `07_overloads.py` | overlapping overloads, implementation consistency |
| `08_narrowing_isinstance.py` | `isinstance`, `in`, `is None`, `match` narrowing |
| `09_typeis_typeguard.py` | `TypeIs` vs `TypeGuard` |
| `10_exhaustiveness.py` | `assert_never` on enums and unions |
| `11_paramspec_decorator.py` | a decorator preserving signature with `ParamSpec`; `Concatenate` |
| `12_self_type.py` | `Self` in fluent builders and classmethods |
| `13_literal_and_literalstring.py` | `Literal`, `LiteralString` (PEP 675) |
| `14_optional_access.py` | attribute access on `X \| None` |
| `15_untyped_defs.py` | errors **inside** an unannotated function (mypy skips by default; others may check) |
| `16_empty_container_inference.py` | `x = []` then `x.append(1)` |
| `17_dataclass_transform.py` | `@dataclass_transform` |
| `18_override.py` | `@override` with a misspelt method |
| `19_frozendict.py` | builtin `frozendict` (3.15, PEP 814): do the checkers' typeshed copies know it yet? |
| `20_deferred_annotations.py` | forward references without quotes under 3.14 semantics |

**The zoo's facts about the spec must be cited, not invented.** Each file's docstring links the spec or conformance-suite source it is based on. If the spec is ambiguous, the marker is `# E?`.

**Analysis.** For every `(file, line)` that has a marker or at least one finding, compute per tool `reported: bool`. Classify each line:
- `agree-correct`: every tool matches the spec expectation
- `disagree`: tools differ
- `all-wrong`: every tool differs from the spec

The script writes the JSON and a generated Markdown table:
```markdown
| Snippet:line | Spec | mypy | pyright | pyrefly | ty | Class |
|---|---|---|---|---|---|---|
| 15_untyped_defs.py:9 | E? | – | E | E | E | disagree |
```
**Self-run (`--self`)**: run all tools in strict mode on `src/`. Produce a count table by tool and code, and a triage list (each finding: real bug → fixed in this milestone; checker difference → documented; false positive → documented with a minimal reproduction). mypy `--strict` must stay at **zero** errors (05 §2). Pyright/pyrefly/ty findings don't fail CI. They are recorded.

**Write-up requirement:** explain at least **five** disagreements with their root cause (binding rules, inference strategy, unannotated-function policy, narrowing algorithm, typeshed version), linked to the `how-type-checkers-work` concept note.

### 6.8 mypyc experiment (`scripts/mypyc_experiment.py`, spike S-12)

1. Copy `src/` to a temporary directory. Never compile in place: compiled `.pyd`/`.so` files next to the sources would shadow them for every later run.
2. Run `mypyc cartographer/graph/scc.py cartographer/core/source.py` there (from the dev env's `mypy` package). On Windows this needs MSVC Build Tools. **Provisional (S-15):** on 3.12+ the `distutils` module is gone, so mypyc may also need `setuptools` installed in the environment that runs it. The experiment script installs it with `uv run --with setuptools` if S-15 confirms that, and records the versions. If S-12 finds it impractical, the experiment runs on ubuntu (CI job `workflow_dispatch` only, or WSL2) and the write-up says so.
3. Benchmarks (`benchmarks/bench_scc.py`, `benchmarks/bench_source.py`) run in subprocesses: once with the interpreted package, once with the compiled copy first on `sys.path`. Each benchmark **asserts which version it imported** (`cartographer.graph.scc.__file__` ends with `.pyd`/`.so` for compiled).
   - `bench_scc`: SCCs of a seeded synthetic graph (10,000 nodes, 50,000 edges).
   - `bench_source`: build `SourceFile`s and compute 100,000 node locations over the 2,000-file synthetic project (stresses byte→char conversion).
4. 20 runs each, after 3 warm-ups. Report median and bootstrap 95 % CI using C2's statistics helper (see the C2 spec for its module), plus the speedup ratio with its CI.
5. Record behavioural differences that mypyc introduces (it enforces annotations at runtime and binds early; see the concept note `mypyc`), and whether all unit tests for those modules pass against the compiled copy (`pytest tests/unit/graph/test_scc.py` with the compiled path first).

No compiled artefact is committed or shipped (D-030).

### 6.9 Stretch: parallel parsing on 3.15t (D-022)

`benchmarks/bench_parallel_parse.py`: parse the 2,000-file synthetic project with `concurrent.futures.ThreadPoolExecutor` at 1, 2, 4 and 8 workers, on 3.15 and on 3.15t. Record `sys._is_gil_enabled()` *after importing Cartographer's dependencies* (links to S-04). Report the speedup with CIs. This is a measurement only. Product code stays single-threaded (D-022) unless a new decision says otherwise.

## 7. Diagnostics

| Code | Name | Default | Trigger | `data` |
|---|---|---|---|---|
| CRT401 | `unannotated-public-function` | info | §6.5 | `qualname`, `missing`, `slots`, `annotated` |
| CRT402 | `explicit-any` | info | §6.5 | `qualname`, `slot`, `in_string` |
| CRT403 | `any-leak` | warning | §6.4 | `symbol`, `kind`, `slot`, `confidence`, `chain`, `root` |
| CRT404 | `bare-type-ignore` | info | §6.5 | `comment` |
| CRT405 | `coverage-below-threshold` | warning | §6.5 | `scope`, `coverage`, `threshold` |
| CRT406 | `type-checking-import-at-runtime` | warning | §6.6 | `name`, `imported_from`, `reason`, `consumer`, `confidence`, `target_version` |

All diagnostics pass through the filtering pipeline (`core.filtering.apply_filters`) **once**, in `api.py` (D-046). `typecov`'s scope is CRT0xx + CRT401–CRT406 (D-047).

## 8. Configuration

```toml
[tool.cartographer.typecov]
typed-threshold        = 80.0      # float percent; module is "typed" at or above this
fail-under             = 0.0       # float percent; 0 = disabled (no CRT405)
package-depth          = 2         # int ≥ 1, for --by package
exclude                = ["tests/**", "test/**", "**/conftest.py"]   # globs excluded from metrics
untyped-modules        = []        # list[str]: external top-level modules to treat as Any (e.g. ["requests"])
min-leak-confidence    = "medium"  # "low" | "medium" | "high"
min-runtime-confidence = "medium"  # for CRT406
runtime-evaluated-bases      = ["pydantic.BaseModel", "typing.NamedTuple", "typing.TypedDict",
                                "typing_extensions.TypedDict", "typing_extensions.NamedTuple"]
runtime-evaluated-decorators = ["dataclasses.dataclass", "attrs.define", "attrs.frozen",
                                "attr.s", "attr.define", "pydantic.validate_call"]
```
`runtime-evaluated-*` lists **replace** the defaults. `extend-runtime-evaluated-bases` / `extend-runtime-evaluated-decorators` (default `[]`) add to them. Thresholds outside 0–100 are a `ConfigError`.

## 9. Phases & tasks

### Phase 1: Coverage core (`c4/coverage`): **MVP**
- [ ] Concept note `gradual-typing` (`Any`, how it spreads, coverage vs precision, Dropbox lessons).
- [ ] `typecov/model.py`, `collect.py`, `public_api.py`, `metrics.py`, `ignores.py`, `render.py`.
- [ ] CRT401, CRT402, CRT404, CRT405 + explanations.
- [ ] `typecov` command, text/json/markdown/sarif; fixture `typecov_basic` + goldens.
- [ ] 🖐 Implement `public_api.static_all()`: evaluate `__all__` from the AST (a nice small interpreter exercise).
- [ ] Tests T-C4-01…12, T-C4-32, T-C4-33.

### Phase 2: Any-leaks (`c4/leaks`): **MVP**
- [ ] `typecov/leaks.py`: symbol extraction, lattice, fixpoint over C1 SCCs, fan-in ranking.
- [ ] CRT403 + dedup with CRT401/402; fixture `typecov_leaks` (+ a cyclic variant `typecov_leaks_cycle`).
- [ ] Extend `graphs-and-scc` with a "fixpoints over SCCs" section.
- [ ] Tests T-C4-13…19, T-C4-31.

### Phase 3: Annotations at runtime (`c4/runtime-annotations`): **MVP**
- [ ] **Spike S-14** (08 §1): write `scripts/annotation_runtime_matrix.py` and fixtures, run on 3.13/3.14/3.15, write `docs/learn/spikes/S-14-annotations-at-runtime.md`, update the catalogue defaults in §6.6 and §8 in the same PR.
- [ ] Concept note `annotations-at-runtime` (PEP 563 vs 649/749, `annotationlib` formats, the matrix table).
- [ ] `typecov/runtime_annotations.py` (CRT406); fixtures `typecov_runtime/` (pydantic-style base defined *locally* as a stand-in named `BaseModel` in a fake `pydantic` package inside the fixture, so no install is needed; singledispatch; isinstance/cast uses).
- [ ] Tests T-C4-20…25.

### Phase 4: Checker study (`c4/checker-matrix`)
- [ ] **Spike S-09**: versions and output flags for mypy, pyright, pyrefly, ty. Record in `docs/learn/spikes/S-09-type-checkers.md` and pin the versions in the script.
- [ ] Concept notes `how-type-checkers-work`, `generics-and-variance`, `protocols-and-structural-typing`, `typeddict-overloads-paramspec`, `narrowing`. Each uses zoo snippets as examples.
- [ ] Typing zoo (20 files, §6.7), each with spec citations.
- [ ] `scripts/checker_matrix.py` with per-tool adapters; `--zoo`, `--self`.
- [ ] Run on the zoo and on `src/`; fix real bugs found in `src/`; generate the matrix files.
- [ ] 🖐 Pick three disagreement rows and write their root-cause explanations yourself, before reading the implementer's.
- [ ] Tests T-C4-26…28 (adapters parse recorded outputs; no network in tests).

### Phase 5: mypyc + stretch (`c4/mypyc`)
- [ ] **Spike S-12**: mypyc on Windows/3.15 feasibility. **Spike S-15** (mypyc part): is `setuptools` required?
- [ ] Concept note `mypyc`.
- [ ] `scripts/mypyc_experiment.py`, `benchmarks/bench_scc.py`, `benchmarks/bench_source.py`; run; record.
- [ ] *(Stretch)* `benchmarks/bench_parallel_parse.py` on 3.15 vs 3.15t.
- [ ] Tests T-C4-29…30.

### Phase 6: Acceptance & docs (`c4/acceptance`)
- [ ] Dogfood: add `cartographer typecov . --fail-under 100` to the CI `dogfood` job (root `.`, D-048; this implies `--fail-on warning`, D-053). Set `[tool.cartographer.typecov] exclude = ["tests/**", "scripts/**", "benchmarks/**"]` in the repo's `pyproject.toml`, so the 100 % gate covers `src/` only. Also add and a check that every CRT402 in `src/` has a justification comment (05 §2) on the same or the previous line, matching `# Any:` (script `scripts/check_any_justified.py`).
- [ ] Corpus run (S-07 repos) with triage of CRT403/CRT406.
- [ ] Walkthrough, write-up, comparison. Version 0.4.0, changelog.

**MVP line:** phases 1–3 + 6. Phases 4–5 are core learning deliverables and are expected, but if they slip (R-02) the milestone can close with them moved to a "C4 stretch" list in the write-up, **as long as the owner agrees**.

## 10. Test plan

| ID | Test |
|---|---|
| T-C4-01 | Slot counting for every parameter kind (posonly, regular, `*args`, kwonly, `**kwargs`) and the return |
| T-C4-02 | First-param exclusion: instance methods, `@classmethod`, `__new__`, metaclass methods, `@staticmethod` (not excluded), nested functions in methods (not excluded), oddly named `self` |
| T-C4-03 | `__init__` return rule: excluded when any param is annotated, counted otherwise |
| T-C4-04 | Property setter/deleter return excluded; getter return counted |
| T-C4-05 | Overloads: variants counted, implementation excluded, also with `typing_extensions.overload` and aliased imports |
| T-C4-06 | Type comments count all slots with `via = "type_comment"` |
| T-C4-07 | `Any` detection: aliased `from typing import Any as A`, `typing.Any`, nested `dict[str, Any]`, string annotations, unparseable string |
| T-C4-08 | Stub shadowing: `.py` excluded from totals when a `.pyi` exists |
| T-C4-09 | Public API: static `__all__` forms, dynamic `__all__` fallback, underscore rules, dunders, private modules, re-exports via C1 resolver |
| T-C4-10 | Golden: `typecov_basic` text/json/markdown, exactly as §5 |
| T-C4-11 | CRT404 via tokenize: `# type: ignore` inside a string isn't counted; `# type: ignore[code]` isn't bare |
| T-C4-12 | CRT405 per module and project, location rule, disabled when `fail-under = 0` |
| T-C4-13 | Lattice join: properties (commutative, associative, idempotent; chain tie-break deterministic), Hypothesis over random statuses |
| T-C4-14 | Golden: `typecov_leaks`, including the fix-first ranking |
| T-C4-15 | Cyclic leak fixture converges; result independent of module iteration order (Hypothesis permutes order) |
| T-C4-16 | Confidence levels: 0/1/2 hops and attribute-of-any |
| T-C4-17 | Dedup: CRT403 suppresses the matching CRT401/CRT402 only |
| T-C4-18 | Untyped module never yields CRT403; threshold boundary (exactly 80.0 % is typed) |
| T-C4-19 | `untyped-modules` config makes `requests.get()` results ANY |
| T-C4-20 | TC-only name detection: `typing.TYPE_CHECKING`, aliased import, `else` branch, also-imported-elsewhere |
| T-C4-21 | Runtime uses: `isinstance`, `cast(Foo, …)` vs `cast("Foo", …)`, default value, base class, decorator, match class pattern |
| T-C4-22 | Runtime-evaluated classes: direct base, project-local subclass chain, cycle guard |
| T-C4-23 | singledispatch `.register` detection |
| T-C4-24 | `from __future__ import annotations` handling matches the S-14 matrix for the target version |
| T-C4-25 | `scripts/annotation_runtime_matrix.py` runs (marked `execute`, our fixtures only) and its output matches the committed spike table on the CI interpreter |
| T-C4-26 | Checker adapters parse recorded outputs (`tests/fixtures/checker_outputs/<tool>-<version>.txt/json`) into the normalised schema |
| T-C4-27 | Disagreement classification on a synthetic set of findings |
| T-C4-28 | Every zoo file has a docstring with a spec link and at least one marker or a "no errors expected" statement |
| T-C4-29 | `mypyc_experiment.py --dry-run` builds the command lines and temp layout without compiling |
| T-C4-30 | Benchmarks assert which implementation they imported |
| T-C4-31 | Fixpoint: a 50-module cyclic chain of unannotated assignments converges (no cap of 20); the derived bound is computed and never exceeded; a deliberately non-monotone `join` (monkeypatched) raises `AnalysisError` |
| T-C4-32 | `--fail-under` implies `--fail-on warning` (exit 1 on CRT405); an explicit `--fail-on error` keeps exit 0; CRT405 compares `coverage < fail_under / 100` (79.95 % vs threshold 80 → CRT405; 80.0 % → none) |
| T-C4-33 | Re-export rules: `__all__` listing, `import X as X`, `from m import f as f` are re-exports; a plain `from m import f` is not (the `typecov_leaks` golden shows exactly one CRT403) |

## 11. Acceptance criteria

| ID | Criterion |
|---|---|
| A-C4-01 | `cartographer typecov` on `typecov_basic` and `typecov_leaks` matches the §5 goldens exactly (timing excluded) |
| A-C4-02 | Every rule in §6.2 is covered by at least one named test (T-C4-01…09) |
| A-C4-03 | `cartographer typecov . --fail-under 100` on Cartographer (root `.`, D-048) reports 100.0 % coverage and exits 0, while the same command on a copy with one unannotated function exits 1 (D-053), and every CRT402 in `src/` has an `# Any:` justification (CI dogfood) |
| A-C4-04 | S-14 note exists, and the §6.6 catalogue defaults match its results |
| A-C4-05 | Checker matrix generated for all four tools on all 20 zoo files (or a tool marked "could not run", with the reason). The write-up explains ≥ 5 disagreements with root causes |
| A-C4-06 | Self-run results of pyright/pyrefly/ty on `src/` are recorded and triaged. mypy `--strict` has 0 errors |
| A-C4-07 | mypyc experiment numbers (median + 95 % CI, speedup) for both benchmarks are recorded, with the platform and the S-12 outcome |
| A-C4-08 | On at least one corpus repo, `typecov` runs without crashing. Every CRT403 and CRT406 finding is triaged, with precision stated |
| A-C4-09 | All T-C4 tests pass on the CI matrix (except `execute`/version-specific ones, which run where applicable) |
| A-C4-10 | Documentation: eight Stage 4 concept notes ✅; walkthrough, write-up, comparison; glossary/FAQ updated |

## 12. Documentation deliverables

**Concept notes (exact slugs):** `gradual-typing`, `generics-and-variance`, `protocols-and-structural-typing`, `typeddict-overloads-paramspec`, `narrowing`, `annotations-at-runtime`, `how-type-checkers-work`, `mypyc`. Musts:
- `gradual-typing`: show with mypy (`reveal_type`) how one unannotated function turns a whole call chain into `Any`, and how `precise_coverage` captures it.
- `generics-and-variance`: PEP 695 syntax first, old `TypeVar` second; the `list[int]`/`list[float]` example with the actual checker error message.
- `how-type-checkers-work`: binding → inference → narrowing → checking, with a diagram; the incremental-checking idea (mypy daemon, Dropbox) as concept only (NG3); why the four tools disagree, linked to matrix rows.
- `annotations-at-runtime`: the S-14 table; PEP 563 vs 649/749; `annotationlib` formats with runnable `pycon` examples marked `# Python 3.14+`.
- `mypyc`: what it compiles, what it enforces at runtime, our measured numbers.

**Walkthrough** `docs/learn/walkthroughs/C4.md`: trace `typecov_leaks` from slots → module metrics → symbol table → SCC order → fixpoint iterations (show the status table after each iteration) → CRT403.

**Write-up** `docs/learn/writeups/C4.md`: predictions; coverage of Cartographer itself; corpus numbers; matrix highlights; mypyc numbers; 3.15t numbers (if done).

**Generated artefacts:** `docs/learn/writeups/C4-checker-matrix.md` (header: "Generated by `scripts/checker_matrix.py` — do not edit by hand") and `docs/learn/writeups/data/C4-checker-matrix.json`.

## 13. Reference implementations to compare after

| Reference | Look at | Questions |
|---|---|---|
| **mypy reports** (`--txt-report`, `--html-report`, `--linecount-report`, `--any-exprs-report`, `--lineprecision-report`) | How mypy measures "precision" per line and counts `Any` expressions | Their metric is per *expression*, ours per *slot*. Which better predicts real checking? Run both on `typecov_basic` and the corpus repo |
| **pyright `--verifytypes`** | "Type completeness" of a package's public API | How does it define public symbols and "unknown" types? Compare with our §6.3/§6.4 on the same package |
| **ruff `ANN` (flake8-annotations) and `TC` (flake8-type-checking) rules**, incl. `runtime-evaluated-base-classes` / `runtime-evaluated-decorators` settings | CRT401/CRT406 equivalents | What does ruff's default list contain? Does it handle singledispatch or `cast`? |
| **Pytifex** and the **typing conformance suite** | How they compare checkers | How do their results compare with our zoo for overlapping features? What did they test that we didn't? |

## 14. Risks & open items

- **Spike S-14 (in 08 §1):** *"How do `dataclasses`, `typing.NamedTuple`, `typing.TypedDict`, `functools.singledispatch`, `typing.get_type_hints` and `annotationlib.get_annotations` behave with a `TYPE_CHECKING`-only name in an annotation, on 3.13/3.14/3.15, with and without `from __future__ import annotations`?"* Needed by C4 phase 3. Fallback: keep those consumers at `medium` with a "version-dependent" note.
- **S-09** (checker CLIs): output formats and version flags are Provisional. Adapters isolate the impact.
- **S-12** (mypyc on Windows): may need ubuntu/WSL.
- **R-10:** ty is beta and will change. Versions are pinned and recorded.
- **R-05:** leak heuristics may be noisy, so default `min-leak-confidence = "medium"` and corpus triage.
- **Disagreement with checkers' conventions:** pyright infers unannotated return types, but we follow mypy (Any). Explained in the `gradual-typing` note and in CRT401's explanation.

## 15. Exercises for the learner

1. **Hand-count slots.** For a 10-line snippet the implementer gives you in the walkthrough, compute S, A, Y and the status per function, then run `typecov --format json` and compare.
   *Hint:* watch for `self`, `__init__`'s return and overload implementations.
2. **Make a leak, then fix it.** In `typecov_leaks`, add `-> dict[str, object]` to `load_config`. Predict the new report, then run it. Then annotate `CONFIG` instead (and revert the first change). Is the result the same? Why?
3. **Variance by experiment.** Write `def total(xs: list[float]) -> float` and call it with a `list[int]`. Run mypy and pyright. Change the parameter to `Sequence[float]`. Explain the difference in your own words.
   *Hint:* could `total` append a `float` to your `list[int]`?
4. **TYPE_CHECKING trap.** Write a dataclass using a `TYPE_CHECKING`-only `Decimal` and run it on 3.13 and 3.15, with and without `from __future__ import annotations`. Does your result match the S-14 table?
5. **Disagreement hunt.** Find one snippet *not* in the zoo where mypy and pyright disagree. Add it as `21_<topic>.py` with a spec citation.
   *Hint:* look at the `15_untyped_defs.py` pattern, or at `TypedDict` + `**kwargs` (`Unpack`).
