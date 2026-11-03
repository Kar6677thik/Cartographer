# C3: Rule engine with a plugin API

> **Status:** Approved spec, revision 1 (2026-11-03) · **Size:** M · **Version at end:** 0.3.0
> **Depends on:** M0 (core types, `SourceFile`, config, CLI, output, `explain`). C1 and C2 are *not* required, but once they exist, C3's filtering pipeline (§6.7) also applies to their diagnostics.
> **Research:** §2.6 (blocking calls on the event loop), §2.12 (PEP 765, control flow leaving `finally`), §3 "Data model" row (decorators, descriptors, `__init_subclass__` registries, entry points).
> **Codes owned:** CRT301, CRT302, CRT303 (rules); CRT004, CRT005 (suppressions, core range but implemented here); CRT9xx (reserved for plugins).

---

## 1. Summary

C3 builds a small **linter engine**. A linter is a program that reads code and reports patterns that are probably mistakes. The engine:

1. Reads each Python file once (through `SourceFile`) and walks its AST (abstract syntax tree) **once**, handing each node to every rule that asked for that kind of node.
2. Tracks **context** as it walks: which function you are in, whether that function is `async def`, and what each imported name really refers to (so `from time import sleep as nap; nap(1)` is understood as `time.sleep(1)`).
3. Lets rules be written as small classes that **register themselves** when defined, using `__init_subclass__`. It also lets *other installed packages* add rules through an **entry point** (a plugin system), without Cartographer knowing about them in advance.
4. Applies the user's choices: `select`/`ignore`, `per-file-ignores`, severity overrides, and **suppression comments** like `# cartographer: ignore[CRT301]`.
5. Ships three real rules, each tied to a real incident:
   - **CRT301 `blocking-call-in-async`**: `time.sleep`, `requests.get` and the like inside `async def` (research §2.6).
   - **CRT302 `finally-control-flow`**: `return`/`break`/`continue` that leaves a `finally` block and silently swallows exceptions (PEP 765, research §2.12).
   - **CRT303 `mutable-default-argument`**: `def f(x=[])`, the most famous Python trap.

New commands: `cartographer check` (run the rules) and `cartographer rules` (list/describe rules). `cartographer explain` (from M0) learns to explain rule codes.

## 2. Why this matters

**The incident (research §2.6).** A PDF-ingestion service ran ordinary blocking code (`boto3`, `requests`, ORM queries, big JSON parses) inside `async def` functions. asyncio runs all coroutines on **one thread**, using an **event loop** (a scheduler that switches between tasks whenever one of them `await`s). A blocking call never `await`s, so while `requests.get()` waits 300 ms for a server, *every other request on that process waits too*. Moving those calls to `asyncio.to_thread()` gave about **31–36 % more throughput and 24–27 % lower p99 latency**. (p99 is the latency that 99 % of requests beat.) The bug is invisible in code review unless you know to look. A tool that knows the list of blocking calls finds it in milliseconds.

**The language change (research §2.12).** Python 3.14 added a `SyntaxWarning` for `return`, `break` or `continue` that leaves a `finally` block (PEP 765). These statements silently **discard an exception that is in flight**:

```python
def load():
    try:
        raise ValueError("corrupt file")
    finally:
        return None      # the ValueError vanishes. load() returns None, no error.
```

Code written for 3.13 and earlier gets no warning at all. A rule catches it on every version and explains *why*.

**The design lesson (research §3).** Real linters (flake8, ruff, pylint) are built from the same parts you will build here: a visitor that walks the tree, a registry that collects rules, a configuration layer, suppression comments, and a plugin API. Building them teaches **decorators**, **`__init_subclass__`**, **class attributes**, **descriptors** (how methods become bound methods), and **entry points**. Those are the "data model" topics the research says you must be able to explain cold.

## 3. Read before starting

**Concept notes that already exist (from M0):** `ast-basics`, `tokenize-and-comments`, `descriptors-and-cached-property`, `dataclasses-and-enums`, `config-with-tomllib`, `testing-with-pytest`, `property-based-testing`.

**Concept notes written in this milestone** (read them as they land): `visitor-pattern`, `decorators`, `class-registries`, `entry-points-and-plugins`, `asyncio-basics`, `try-finally-semantics`, `function-defaults`.

**Prediction questions.** Answer these in `docs/learn/predictions/C3.md` *before* Stage B (07 §2). Guesses are fine.

1. `def f(x=[]): x.append(1); return x`. What do `f()`, `f()`, `f()` return, and why?
2. What does this function return or raise? `def g():` / `try: raise ValueError` / `finally: return 1`
3. While `time.sleep(1)` runs inside one coroutine, what happens to the other coroutines on the same event loop?
4. Should `time.sleep(1)` be flagged if it is inside a normal `def helper():` that is *nested inside* an `async def`? Why or why not?
5. How could a tool know that `nap(1)` means `time.sleep(1)` after `from time import sleep as nap`? What could fool it?
6. Is `await asyncio.to_thread(time.sleep, 1)` a blocking call on the event loop? Why?
7. Walking the tree once for all three rules vs. once per rule: roughly how much faster do you expect one pass to be? What else besides speed changes?
8. How can a package that Cartographer has never heard of add a rule to it, without Cartographer importing that package by name?
9. If a third-party rule crashes on one file, what should Cartographer do: crash, skip the file, or skip the rule?
10. Why find `# cartographer: ignore[...]` comments with the `tokenize` module instead of searching each line for `#`?
11. In `class MyRule(Rule, code="CRT901")`, where does `code="CRT901"` go? (Hint: not to `__init__`.)

## 4. Scope

### In scope
- Rule base class, registry via `__init_subclass__`, `@handles` decorator for node-type dispatch, per-rule options dataclasses.
- Single-pass, iterative (non-recursive) dispatcher with scope tracking and an ancestor stack.
- Qualified-name resolution of imported names and aliases (`core/qualnames.py`, reused later by C4 and C5).
- The diagnostic **filtering pipeline** for *all* Python-source commands: select/ignore, per-file-ignores, suppression comments (CRT004/CRT005), severity overrides (`core/filtering.py`, `core/suppressions.py`).
- Plugin loading from entry-point group `cartographer.rules`, with failure isolation.
- Rules CRT301, CRT302, CRT303.
- Commands `check` and `rules`. `explain` extended to rule codes.
- A fixture plugin package (and broken plugins) used by tests.

### Out of scope (and why)
| Not doing | Why |
|---|---|
| Auto-fixes for C3 rules | NG8: only C5 and C2 rewrite code. Rules give `help` text instead |
| Type inference for receivers (`Path(...).read_text()` in async) | Needs a type checker. We resolve *names*, not *types*. Listed as a known false negative |
| Following aliases through assignments (`s = time.sleep; s(1)`) | Needs dataflow. C5 builds dataflow for strings. Out of scope here (documented limitation) |
| Comprehension scoping for name resolution | Rare in practice. Documented limitation (§6.3) |
| Dataclass field defaults (`x: list = []` in a `@dataclass`) | `dataclasses` already raises `ValueError` for `list`/`dict`/`set` defaults at class creation, so the bug can't ship silently. Noted in the CRT303 explanation |
| Rule-level parallelism or caching | D-021, D-022 |
| A `--fix` flag | NG8 |

## 5. User-facing behaviour

### 5.1 `cartographer check`

```
cartographer check [PATH] [--select CODES] [--ignore CODES] [--no-plugins] [--statistics]
                   [--format text|json|sarif] [--fail-on LEVEL] [-o FILE]
```
- `PATH`: project root (default: current directory), as in 03 §1.
- `--no-plugins`: don't load entry-point plugins (same as config `rules.load-plugins = false`).
- **Scope (D-047):** `check` can report CRT0xx, CRT3xx, CRT501–CRT505 (C5's injection rules are C3 rules, D-038, once C5 is merged) and **every registered plugin code** (CRT9xx). `effective = resolve(select) ∩ scope − resolve(ignore)`. With the default `select = ["CRT"]` that means "every rule this command knows about", plugins included.
- `--statistics`: print a count per code instead of individual diagnostics (text format only. With json, the counts are always present in `stats`).
- All global options from 03 §1.1 apply.

**Fixture `tests/fixtures/projects/rules_basic/`** (two files: an empty `app/__init__.py` and `app/handlers.py`):

```python
# app/handlers.py
import asyncio                                        # 1
import time                                           # 2
from time import sleep as nap                         # 3
                                                      # 4
import requests                                       # 5
                                                      # 6
                                                      # 7
async def fetch_all(urls):                            # 8
    time.sleep(0.1)                                   # 9
    nap(1)                                            # 10
    await asyncio.sleep(0)                            # 11
    data = await asyncio.to_thread(requests.get, urls[0])   # 12
                                                      # 13
    def helper():                                     # 14
        time.sleep(1)                                 # 15
                                                      # 16
    return [requests.get(u) for u in urls], data, helper    # 17
                                                      # 18
                                                      # 19
def cleanup(path, cache={}):                          # 20
    try:                                              # 21
        return open(path).read()                      # 22
    finally:                                          # 23
        return None                                   # 24
```
(The `# N` comments show line numbers here only. They are not in the real fixture file.)

Expected output (golden file `tests/golden/check/rules_basic.text`, with the timing excluded):

```
$ cartographer check tests/fixtures/projects/rules_basic
app/handlers.py:9:5: CRT301 [warning] blocking call `time.sleep` inside `async def fetch_all`
  help: use `await asyncio.sleep(...)` instead
app/handlers.py:10:5: CRT301 [warning] blocking call `time.sleep` (as `nap`) inside `async def fetch_all`
  help: use `await asyncio.sleep(...)` instead
app/handlers.py:17:13: CRT301 [warning] blocking call `requests.get` inside `async def fetch_all`
  help: use an async HTTP client, or run it in a thread: `await asyncio.to_thread(requests.get, ...)`
app/handlers.py:20:25: CRT303 [warning] mutable default `{}` for parameter `cache` is shared between calls
  help: use `cache=None` and create the value inside the function: `if cache is None: cache = {}`
app/handlers.py:24:9: CRT302 [warning] `return` in `finally` block discards any exception being raised (PEP 765)
  help: move the `return` after the `try` statement, or handle the exception explicitly with `except`
  related: app/handlers.py:21:5 (try statement)

Found 0 errors, 5 warnings, 0 info in 2 files (0.02 s).
```

What is **not** reported, and why (each of these is a test):
- Line 11: `await asyncio.sleep(0)` is the non-blocking version.
- Line 12: `requests.get` is only *referenced*, not called. `to_thread` calls it in a worker thread.
- Line 15: `time.sleep` is inside the nested **sync** `def helper`, which runs whenever someone calls it (maybe in a thread), not necessarily on the loop.
- Line 22: `open()` is inside a normal `def`, not `async def`.

`--statistics`:
```
$ cartographer check --statistics tests/fixtures/projects/rules_basic
3  CRT301  blocking-call-in-async
1  CRT302  finally-control-flow
1  CRT303  mutable-default-argument

Found 0 errors, 5 warnings, 0 info in 2 files (0.02 s).
```
Rows are sorted by count (descending), then code (ascending).

Exit code: 0, because the default `--fail-on error` and these are warnings. With `--fail-on warning` it's 1.

### 5.2 `cartographer rules`

```
$ cartographer rules
CODE    NAME                       DEFAULT  SOURCE   SUMMARY
CRT301  blocking-call-in-async     warning  builtin  Known blocking call inside `async def`
CRT302  finally-control-flow       warning  builtin  `return`/`break`/`continue` leaves a `finally` block
CRT303  mutable-default-argument   warning  builtin  Mutable default argument value
```
With the example plugin installed (§6.8), an extra row appears:
```
CRT901  print-call                 info     cartographer-example-plugin 0.1.0  `print()` call
```
- Columns are padded to the widest value. Rows are sorted by code.
- `--format json` prints `{"schema": "cartographer.rules/1", "rules": [{"code", "name", "default_severity", "enabled_by_default", "source", "summary", "options": {...defaults...}}]}`.

`cartographer rules CODE_OR_NAME` prints the rule's metadata, its options (with defaults and current values) and then its full explanation:
```
$ cartographer rules blocking-call-in-async
CRT301 blocking-call-in-async (default: warning, builtin)

Options ([tool.cartographer.rules.blocking-call-in-async]):
  blocking-calls         = (built-in list, 39 entries; see `explain`)
  extend-blocking-calls  = []
  allow-calls            = []

What it means
  …the six-section explanation (04 §5)…
```
An unknown code/name gives a `UsageError` (exit 2) with a "did you mean" suggestion, using `difflib.get_close_matches` over codes and names.

### 5.3 `cartographer explain`
Unchanged interface from M0. C3 makes it resolve rule codes: it looks first in the **rule registry** (`Rule.explanation`, including plugin rules if plugins are loaded), then in `core.codes` (for non-rule codes like CRT001, CRT004).

### 5.4 Suppression comments (honoured by every Python-source command)
Syntax is defined in 03 §5. C3 makes it precise:

```
comment    := "#" WS* "cartographer:" WS* directive WS* [ "#" anything ]
directive  := ("ignore" | "ignore-file") WS* "[" item ( WS* "," WS* item )* WS* ","? WS* "]"
item       := CODE | NAME            CODE = "CRT" 3 digits;  NAME = kebab-case rule/code name
```
- Matching is case-sensitive for `cartographer:` and the directive. Codes are upper-case and names lower-case.
- **Prefixes are not allowed** in suppressions (`ignore[CRT3]` is `CRT004`). Suppressions must be exact, so they don't hide future rules.
- **Line suppression** (`ignore[...]`): applies to diagnostics whose *start line* lies within the **logical line** that contains the comment. A logical line is one complete statement, possibly spanning several physical lines because of brackets. So both of these work:
  ```python
  cur.execute(
      f"SELECT {x}"   # cartographer: ignore[CRT501]
  )
  data = big_call(a,
                  b)   # cartographer: ignore[CRT301]   ← diagnostic on line 1 of the statement
  ```
- **(Python provider only, D-051.)** A line suppression on a comment-only line (no code on that logical line) is **`CRT004`**: *"suppression comment must be on a line of code; to suppress the whole file use `ignore-file`"*.
- **File suppression** (`ignore-file[...]`): must appear in a comment whose line is ≤ 20. Elsewhere it is `CRT004`. It applies to every diagnostic in the file with a listed code.
- A comment like `# cartographer: ignore` (no list), `# cartographer: ignore[]`, `# cartographer: ignor[CRT301]` (unknown directive), or one with an unknown code/name is `CRT004`, located at the comment.
- `CRT004` diagnostics can't themselves be suppressed by comments (that would allow loops). They can be disabled via config `ignore`.
- YAML files (C7) use their own provider, where a comment on the line *above* is allowed (03 §5). The comment-only rule above does not apply there.
- **`CRT005 unused-suppression`** (info, *off by default*) is reported for each listed item that suppressed nothing in this run, **but only if that item's code was selected in this run**. If CRT301 wasn't selected, nobody checked, so we can't say the suppression is unused.

## 6. Design

### 6.1 Files (all under `src/cartographer/`)

| File | Phase | Contents |
|---|---|---|
| `rules/__init__.py` | 1 | Public plugin API re-exports: `Rule`, `RuleOptions`, `NoOptions`, `RuleContext`, `handles`, `Scope`, `ScopeKind` |
| `rules/base.py` | 1 | `Rule`, `RuleOptions`, `NoOptions`, `handles`, `__init_subclass__` validation |
| `rules/registry.py` | 1 | The registry: register, lookup by code/name, selection resolution, `snapshot()` for tests |
| `rules/context.py` | 1 | `RuleContext`, `Scope`, `ScopeKind` |
| `rules/dispatch.py` | 1 | The iterative single-pass walker |
| `rules/engine.py` | 1 | `run_rules(project, config, *, selection) -> Result`: instantiates the selected rules, runs files, isolates plugin crashes. Returns **raw** diagnostics (D-046) |
| `rules/config.py` | 1 | `RulesConfig` (import-light: stdlib + `core` only), registered in `cli/sections.py` as `"rules": "cartographer.rules.config:RulesConfig"` (D-043) |
| `core/qualnames.py` | 2 | `QualNameResolver` (pre-pass over imports and bindings) |
| `rules/builtin/__init__.py` | 2 | Imports the builtin rule modules so they register |
| `rules/builtin/async_blocking.py` | 2 | CRT301 |
| `rules/builtin/finally_flow.py` | 3 | CRT302 |
| `rules/builtin/mutable_defaults.py` | 3 | CRT303 |
| `core/suppressions.py` | 4 | `SuppressionIndex`, the `SuppressionProvider` protocol, and `PythonSuppressionProvider` (tokenize-based) (D-051) |
| `core/filtering.py` | 4 | `apply_filters(diagnostics, config, *, selection, suppressions) -> tuple[Diagnostic, ...]` |
| `rules/plugins.py` | 5 | Entry-point discovery and loading, `PluginError` records, `core.codes.register_external(...)` for each plugin rule (D-047) |
| `cli/commands/check.py` | 1 (wired), 4 (filters), 5 (`--no-plugins`) | `check` subcommand |
| `cli/commands/rules.py` | 1 | `rules` subcommand |
| `api.py` | 1 | adds `run_rules(...)` (D-031). From phase 4 it is the **single place** where `apply_filters` runs (D-046) |

> **Layering note (02 §3):** `core/qualnames.py`, `core/suppressions.py` and `core/filtering.py` live in `core` because C1, C2, C4 and C5 need them too, and `core` may not import `rules`. `api.py` calls `core.filtering.apply_filters` **exactly once** on the raw diagnostics of *every* Python-source command (D-046). That's how C1/C2 diagnostics also honour suppressions. Nothing else filters: not `run_rules`, not the analyzers, not `cli/main.py` (which only renders and computes the exit code).

### 6.2 The `Rule` base class

```python
class RuleOptions:
    """Base for per-rule option dataclasses. Subclasses are frozen dataclasses."""

@dataclass(frozen=True, slots=True)
class NoOptions(RuleOptions):
    pass

class Rule:
    # Set from class keywords by __init_subclass__ (never assigned by hand):
    code: ClassVar[str]                  # "CRT301"
    name: ClassVar[str]                  # "blocking-call-in-async"
    default_severity: ClassVar[Severity]
    enabled_by_default: ClassVar[bool]
    # Written in the class body:
    summary: ClassVar[str]               # one line for `rules` listing
    explanation: ClassVar[str]           # six-section text (04 §5)
    options_class: ClassVar[type[RuleOptions]] = NoOptions
    # Built by __init_subclass__ from @handles-decorated methods:
    _handlers: ClassVar[Mapping[type[ast.AST], tuple[str, ...]]]

    def __init_subclass__(cls, *, code: str | None = None, name: str | None = None,
                          severity: Severity = Severity.WARNING,
                          enabled_by_default: bool = True,
                          abstract: bool = False, **kwargs: object) -> None: ...

    def __init__(self, options: RuleOptions) -> None:
        self.options = options

    def begin_file(self, ctx: RuleContext) -> None:   # optional hook
        pass
    def end_file(self, ctx: RuleContext) -> None:     # optional hook
        pass
```

Defining a rule looks like this:
```python
class MutableDefault(Rule, code="CRT303", name="mutable-default-argument"):
    summary = "Mutable default argument value"
    explanation = """…six sections…"""

    @handles(ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
    def check_defaults(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
                       ctx: RuleContext) -> None:
        ...
        ctx.report(self, default_node, "mutable default ...", help="...", data={...})
```

**`handles(*node_types)`** is a decorator. It stores the tuple on the function as the attribute `__cartographer_handles__` and returns **the same function** (it doesn't wrap it, so there's no call overhead). It's typed with a `TypeVar` bound to `Callable[..., None]` so type checkers keep the method's signature. It raises `TypeError` at decoration time if given no types, or a non-`ast.AST` subclass.

**`__init_subclass__` steps** (in this order; each failure raises `RuleRegistrationError`, a subclass of `CartographerError` defined in `rules/base.py`):
1. Call `super().__init_subclass__(**kwargs)` (cooperative inheritance).
2. If `abstract=True`: build `_handlers` (so subclasses inherit them) and **don't register**. Stop.
3. `code` and `name` must both be given. `code` must match `^CRT\d{3}$` and `name` must match `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`.
4. Determine `source`: if `cls.__module__` starts with `"cartographer."`, the rule is **builtin**. Builtin codes must exist in `core.codes` with the *same name and default severity* (a mismatch is a bug, which keeps 03 §6 honest). Otherwise the rule is a **plugin** rule: its code must match `^CRT9\d\d$` and must *not* already be in `core.codes` (neither built in nor registered externally by another plugin).
5. `summary` must be a non-empty one-line `str`. `explanation` must be a `str`. For builtins, a test (T-C3-05) enforces the six sections. For plugins, missing sections log a WARNING, because we can't fail someone else's package for doc style.
6. `options_class` must be a frozen dataclass subclass of `RuleOptions`.
7. Build `_handlers`: walk `cls.__mro__` in reverse, collecting every attribute with `__cartographer_handles__`. That gives `node type → tuple of method names` (subclass methods override parent methods of the same name). There must be at least one handler, or `begin_file`/`end_file` must be overridden. Otherwise the rule could never report anything, which is an error.
8. Register in the registry. A duplicate code or name is an error, and the message names both classes and their modules.
9. **Plugin rules only:** after the entry point has loaded successfully, `rules/plugins.py` (not `__init_subclass__`) calls `core.codes.register_external(CodeInfo(code, name, default_severity, milestone="plugin", status=IMPLEMENTED, explanation=cls.explanation, source=<distribution name and version>))`. From then on the code behaves like a built-in one: selectors can name it (`--select CRT901`, prefixes like `CRT9`), `explain` finds it, and the SARIF `tool.driver.rules` array includes its metadata. `registry.snapshot()` also snapshots and restores the external codes, so tests stay isolated.

> **CONCEPT(class-registries):** `__init_subclass__` runs when a *subclass is created* (when the `class` statement finishes), not when an instance is made. Keyword arguments in the class header (`class X(Rule, code="CRT303")`) are passed to it. That's how a class "registers itself" without a metaclass. The concept note compares this with metaclasses and with explicit `register()` calls.

### 6.3 Qualified-name resolution (`core/qualnames.py`)

**Goal:** given an expression like `nap` or `requests.get` or `os.path.join` at some point in a file, return the dotted name it refers to at runtime (`"time.sleep"`, `"requests.get"`, `"os.path.join"`), or `None` if we can't be sure. **Precision first** (R-05): returning `None` means "don't flag", which is always safe.

```python
@dataclass(frozen=True, slots=True)
class Binding:
    kind: Literal["import", "other"]
    target: str | None        # dotted target for imports, None for "other"
    node: ast.AST             # where it was bound (for debugging/docs)

class QualNameResolver:
    @classmethod
    def build(cls, tree: ast.Module, module: str | None, is_package: bool) -> QualNameResolver: ...
    def resolve(self, expr: ast.expr, scope_chain: Sequence[ast.AST]) -> str | None: ...
```

**Pre-pass (flow-insensitive).** For each *scope node* (`Module`, `FunctionDef`, `AsyncFunctionDef`, `Lambda`, `ClassDef`), collect every name binding in that scope (not in nested scopes):

| Statement | Binding |
|---|---|
| `import a.b.c` | `a` → import `"a"` |
| `import a.b.c as d` | `d` → import `"a.b.c"` |
| `from a.b import c` | `c` → import `"a.b.c"` |
| `from a.b import c as d` | `d` → import `"a.b.c"` |
| `from . import x` / `from ..p import y` | relative: resolved against the file's package (below). Unresolvable → `other` |
| `from a import *` | marks the scope as **star-polluted**: any name not otherwise bound resolves to `None` |
| assignment targets (`x = …`, `x: T = …`, `x += …`, `for x in`, `with … as x`, `except … as x`, `(x := …)`, `del x`, `match` capture patterns, `def x`, `class x`, `import` inside `try`) | `x` → `other` (except imports, above) |
| `global x` / `nonlocal x` | name lookups for `x` in this scope skip to module / enclosing function scope |

**Relative imports.** `base` = the file's package: `module` itself if `is_package` (an `__init__.py`), else `module` minus its last component. Then level 1 = `base`, level 2 = parent of `base`, and so on. If the level climbs above the top-level package, or `module` is `None` (file not under a source root), the binding is `other`. C1 reports CRT104 for that, not C3.

**Resolution of a `Name`** (`resolve(Name("nap"), scope_chain)`):
1. Find the binding scope. Start at the innermost scope. Skip `ClassDef` scopes **except** when the class body is itself the innermost scope (Python's rule: methods don't see class-level names). Honour `global`/`nonlocal`.
2. In that scope, collect *all* bindings of the name:
   - none → continue outward
   - only import bindings, all with the **same** target → that target
   - anything else (an `other` binding, or imports with different targets, such as `try: import simplejson as json` / `except ImportError: import json`) → `None`
3. If no scope binds it: if the module scope is star-polluted → `None`. Else, if the name is in `dir(builtins)` → `"builtins.<name>"`. Else `None`.

**Resolution of an `Attribute` chain** `a.b.c`: resolve the leftmost `Name`, then append `.b.c`. Any other base (a call, a subscript) → `None`.

**Worked example.** For `from time import sleep as nap` at module level and `nap(1)` inside `async def fetch_all`: the scope chain is `[Module, AsyncFunctionDef fetch_all]`. `fetch_all` has no binding for `nap`, so lookup moves out. `Module` has exactly one binding, `nap` → import `"time.sleep"`, which is the result.

**Complexity.** The pre-pass is O(N) in AST nodes. Each `resolve` is O(depth of scope chain + length of attribute chain).

**Documented limitations** (each has an `xfail`-free test asserting the *current* behaviour, so changes are deliberate):
- `s = time.sleep; s(1)` → `s` is `other`, so `None` (no flag).
- A name rebound only inside a comprehension, e.g. `[sleep for sleep in xs]`, isn't tracked. Comprehension targets are attributed to the enclosing scope.
- Flow-insensitivity: `import time` *after* its use in a function still resolves. That's correct for functions called later, and harmless otherwise.

### 6.4 `RuleContext`

```python
class ScopeKind(enum.Enum):
    MODULE = "module"; CLASS = "class"; FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"; LAMBDA = "lambda"

@dataclass(frozen=True, slots=True)
class Scope:
    kind: ScopeKind
    node: ast.AST
    name: str            # "<module>", class/function name, or "<lambda>"

class RuleContext:
    source: SourceFile
    config: Config
    shared: dict[str, object]        # per-file scratch space shared between rules (C5 uses it)
    @property scopes(self) -> tuple[Scope, ...]
    @property scope(self) -> Scope                     # innermost
    @property function_scope(self) -> Scope | None     # innermost FUNCTION/ASYNC_FUNCTION/LAMBDA
    @property in_async_function(self) -> bool          # function_scope.kind is ASYNC_FUNCTION
    @property parents(self) -> tuple[ast.AST, ...]     # ancestors of the current node, root first
    @property parent(self) -> ast.AST | None
    @property in_annotation(self) -> bool              # inside a parameter/return/variable annotation
    def qualified_name(self, expr: ast.expr) -> str | None
    def report(self, rule: Rule, node: ast.AST, message: str, *, help: str | None = None,
               data: Mapping[str, JSONValue] | None = None,
               related: Sequence[tuple[str, Location]] = ()) -> None
```
- `report` builds a `Diagnostic` using `rule.code`, `rule.name`, `rule.default_severity` (overrides come later, in filtering), and `source.location(node)`, so byte-to-character conversion happens in one place (D-018).
- `in_async_function` ignores `CLASS` scopes. A class body *inside* an `async def` executes immediately, during the coroutine, so a blocking call in it does block the loop.

### 6.5 The single-pass dispatcher (`rules/dispatch.py`)

**Why iterative:** a recursive walk can hit Python's recursion limit (about 1,000 frames) on deeply nested expressions, such as generated code with a 2,000-term `a + b + c + …`. An explicit stack has no such limit. **Why one pass:** parsing and walking dominate the cost, so k rules in one walk is close to k times cheaper than k walks. The concept note `visitor-pattern` shows the measurement.

**Dispatch table.** For the active rule instances, build `table: dict[type[ast.AST], list[BoundMethod]]` lazily: for a node type `T`, the list is every handler registered for any class in `T.__mro__`, ordered by (rule code, method name). That keeps it deterministic. Cache it per `T`.

**Events.** The walk processes a stack of events:
```
VISIT(node)        → call handlers for node; then schedule its children (below); push LEAVE(node) first
LEAVE(node)        → pop node from the ancestor stack
PUSH_SCOPE(node)   → push Scope for node
POP_SCOPE(node)    → pop it
SET_ANNOT(flag)    → set/restore ctx.in_annotation
```

**Which children are evaluated in which scope.** This matters for correctness. Python evaluates a function's *decorators and default values in the enclosing scope*, when the `def` statement runs:

| Node | Children visited in the **outer** scope | Then `PUSH_SCOPE` and visit **inside** |
|---|---|---|
| `FunctionDef` / `AsyncFunctionDef` | `decorator_list`, `args.defaults`, `args.kw_defaults` (non-`None`), `type_params` | the `arg` nodes (annotations under `SET_ANNOT(True)`), `returns` (under `SET_ANNOT(True)`), `body` |
| `Lambda` | `args.defaults`, `args.kw_defaults` | `arg` nodes, `body` |
| `ClassDef` | `decorator_list`, `bases`, `keywords`, `type_params` | `body` |
| `AnnAssign` | `target`, `value` | `annotation` under `SET_ANNOT(True)` (no new scope) |
| everything else | all children via `ast.iter_child_nodes`, in field order | — |

**Pseudocode:**
```
def walk(tree, ctx, table):
    ctx.push_scope(Scope(MODULE, tree, "<module>"))
    stack = [VISIT(tree)]
    while stack:
        ev = stack.pop()
        match ev:
            case VISIT(node):
                ctx.ancestors.append(node)
                for handler in table.for_type(type(node)):
                    run_guarded(handler, node, ctx)          # §6.9 isolation
                outer, inner = split_children(node)          # table above
                later = [*map(VISIT, outer)]
                if node introduces a scope:
                    later += [PUSH_SCOPE(node), *inner_events(node), POP_SCOPE(node)]
                stack.append(LEAVE(node))
                stack.extend(reversed(later))                # reversed: so they pop in order
            case LEAVE(node):   ctx.ancestors.pop()
            case PUSH_SCOPE(n): ctx.push_scope(scope_for(n))
            case POP_SCOPE(n):  ctx.pop_scope()
            case SET_ANNOT(f):  ctx.set_annotation(f)
```
`inner_events` produces the inner children in field order, with `SET_ANNOT(True)`/`SET_ANNOT(previous)` wrapped around annotation subtrees.

**Order guarantee:** nodes are visited in **pre-order** (parent before children), children in AST field order. The final diagnostics are sorted anyway (02 §4.4), but deterministic visiting makes debugging and the walkthrough trace reproducible.

**Worked example** (for the walkthrough and test T-C3-08). For
```python
async def f(x=time.sleep(1)):
    time.sleep(2)
```
the events are: `VISIT Module` → `VISIT AsyncFunctionDef f` → `VISIT Call time.sleep(1)` (outer scope: `function_scope` is `None`, so **not** async, no CRT301) → … → `PUSH_SCOPE f` → `VISIT arg x` → `VISIT Expr` → `VISIT Call time.sleep(2)` (`in_async_function` is True, so **CRT301**) → … → `POP_SCOPE f`. The default value `time.sleep(1)` runs when the module defines `f`, not on the event loop. That's exactly why the outer/inner split exists.

**Complexity:** O(N × h), where N is the number of nodes and h the average number of handlers per node type (≤ 2 for builtins). In practice that's O(N).

### 6.6 Built-in rules

#### CRT301 `blocking-call-in-async`

**Trigger.** On every `ast.Call` node where **all** of these hold:
1. `ctx.in_async_function` is True.
2. `name := ctx.qualified_name(node.func)` is not `None`, and `name` is in the effective blocking set: `(blocking_calls or DEFAULTS) ∪ extend_blocking_calls − allow_calls`.
3. The call is **not** the direct operand of `await` (`ctx.parent` is not an `ast.Await` whose `value is node`). If someone awaits it, it returns an awaitable, so it isn't the sync function we know.

**Default blocking set** (each entry has a category, used for the `help` text and `data`):

| Category | Qualified names | Help text |
|---|---|---|
| `sleep` | `time.sleep` | use `await asyncio.sleep(...)` instead |
| `network` | `requests.get/post/put/patch/delete/head/options/request`, `httpx.get/post/put/patch/delete/head/options/request/stream`, `urllib.request.urlopen`, `socket.create_connection`, `socket.getaddrinfo`, `socket.gethostbyname` | use an async HTTP client, or run it in a thread: `` `await asyncio.to_thread(<name>, ...)` `` |
| `subprocess` | `subprocess.run/call/check_call/check_output`, `os.system`, `os.popen`, `os.waitpid` | use `await asyncio.create_subprocess_exec(...)` |
| `file-io` | `builtins.open`, `io.open`, `shutil.copy/copy2/copyfile/copytree/move/rmtree` | run it in a thread: `` `await asyncio.to_thread(<name>, ...)` `` |
| `input` | `builtins.input` | read input outside the event loop, or in a thread |
| `database` | `sqlite3.connect` | use an async driver, or `asyncio.to_thread` |

That's **39 entries**: sleep 1, network 21 (8 `requests` + 9 `httpx` + `urlopen` + 3 `socket`), subprocess 7, file-io 8, input 1, database 1. `len(DEFAULT_BLOCKING_CALLS) == 39` is asserted, and so is the per-category count, so the `rules` output in §5.2 and this table stay honest. User-added names (`extend-blocking-calls`) get category `other` and the generic help: "run it in a thread: `await asyncio.to_thread(<name>, ...)`".

**Message.** ``blocking call `{name}` inside `async def {function}` ``. Let `spelled` be the source segment of `node.func` (for example `nap`, `t.sleep`, `time.sleep`). If `spelled` is an alias, meaning `name != spelled` and `name` does not end with `"." + spelled`, insert `` (as `{spelled}`) ``. For example: ``blocking call `time.sleep` (as `nap`) inside `async def fetch_all` ``. `time.sleep` spelled as `time.sleep` gets no alias note. Spelled as `t.sleep` (after `import time as t`), it does.

**Location:** the `Call` node.

**`data`:** `{"call": "time.sleep", "alias": "nap" | null, "function": "fetch_all", "category": "sleep"}`.

**Options** (`[tool.cartographer.rules.blocking-call-in-async]`):
```python
@dataclass(frozen=True, slots=True)
class BlockingCallOptions(RuleOptions):
    blocking_calls: tuple[str, ...] | None = None   # None = built-in list; a list REPLACES it
    extend_blocking_calls: tuple[str, ...] = ()
    allow_calls: tuple[str, ...] = ()
```
Each entry must be a dotted name (`^[A-Za-z_][\w]*(\.[A-Za-z_][\w]*)+$`, or `builtins.x`). Otherwise `ConfigError`.

**Edge cases** (each is a test):
| Case | Result |
|---|---|
| `time.sleep(1)` in `async def` | flag |
| `from time import sleep as nap; nap(1)` | flag, with alias |
| `import time as t; t.sleep(1)` | flag (`t` → `"time"`, so `"time.sleep"`); alias `t.sleep` |
| `await asyncio.sleep(1)` | no |
| `await asyncio.to_thread(time.sleep, 1)` | no (not a call of `time.sleep`) |
| `loop.run_in_executor(None, time.sleep, 1)` | no |
| sync `def` nested in `async def` calling `time.sleep` | no |
| `lambda: time.sleep(1)` inside `async def` | no (lambda is a function scope) |
| class body inside `async def` calling `time.sleep` | **flag** (class bodies execute immediately) |
| method of that class calling `time.sleep` | no |
| default value of a nested `def` inside `async def`: `def g(x=time.sleep(1))` | **flag** (defaults evaluate in the enclosing async scope) |
| decorator of a nested def inside `async def` calling a blocking function | **flag** |
| list comprehension / generator expression inside `async def` | flag (they run in the coroutine's frame) |
| `time = FakeTime(); time.sleep(1)` | no (`time` has an `other` binding, so ambiguous) |
| `try: import simplejson as json` / `except: import json` (irrelevant to the list, but tests ambiguity) | resolves to `None` |
| `from time import *` then `sleep(1)` | no (star-polluted) |
| `time.sleep` inside `async def` inside `if TYPE_CHECKING:` | flag (we don't special-case; it's silly code, but consistent) |
| `async with`/`async for` bodies | flag as usual (same async function) |
| `open()` in `async def` with `allow-calls = ["builtins.open"]` | no |
| `open` shadowed by a parameter `def f(open)` | no (parameters are `other` bindings) |

#### CRT302 `finally-control-flow`

**Semantics (PEP 765).** A `return`, `break` or `continue` that **transfers control out of** a `finally` block is reported:
- `return` anywhere inside the `finally` body, unless inside a nested function, lambda or class (which is a different scope).
- `break`/`continue` inside the `finally` body, unless they are inside a loop **body** that is itself inside the `finally` body. Then they target that inner loop and stay inside `finally`. **Careful:** the `else:` clause of an inner loop is *not* part of that loop for `break`/`continue` purposes. A `break` in `for …: … else: break` targets the *outer* loop, so it is reported.

**Trigger.** Handler on `ast.Try` and `ast.TryStar`. For each, walk `node.finalbody` with a small dedicated walker:
```
def scan(stmts, loop_depth):
    for s in stmts:
        visit(s, loop_depth)

def visit(n, loop_depth):
    match n:
        case FunctionDef | AsyncFunctionDef | Lambda | ClassDef: return        # new scope
        case Return:                         report(n)
        case Break | Continue if loop_depth == 0: report(n)
        case For | AsyncFor | While:
            scan(n.body, loop_depth + 1)     # body: break/continue are local
            scan(n.orelse, loop_depth)       # else: NOT local
            visit expression children (target/iter/test) with loop_depth   # e.g. walrus/lambda
        case _: for child in iter_child_nodes(n): visit(child, loop_depth)
```
**Nested `try/finally` inside a `finally`** would be scanned twice: by the outer `try`'s scan and by its own handler. To report each statement once, the rule keeps `self._reported: set[int]` of `id(stmt)`, reset in `begin_file`.

**Message:**
- `return`: ``` `return` in `finally` block discards any exception being raised (PEP 765) ```
- `break`: ``` `break` in `finally` block exits the loop and discards any exception being raised (PEP 765) ```
- `continue`: ``` `continue` in `finally` block skips to the next iteration and discards any exception being raised (PEP 765) ```

**Location:** the statement. **Related:** `("try statement", location of the Try node)`.
**`data`:** `{"statement": "return" | "break" | "continue", "try_line": <int>}`.
**Help:** ``move the `{stmt}` after the `try` statement, or handle the exception explicitly with `except` ``.

**Edge cases:**
| Case | Result |
|---|---|
| `return` in `try` body or `except` | no |
| `return` in `finally` | flag |
| `return` in `finally` in a nested `def` | no |
| `for` loop inside `finally` with `break` in its body | no |
| `break` in `finally` (loop outside the try) | flag |
| `break` in the `else:` of a loop inside `finally` | flag |
| `while` inside `finally`, `continue` in a nested `if` in its body | no |
| nested `try/finally` inside `finally` with `return` | flag **once** |
| `try/except*` (`TryStar`) with `finally` + `return` | flag |
| `return` inside `match` case inside `finally` | flag |
| `with` block inside `finally` containing `return` | flag |

#### CRT303 `mutable-default-argument`

**Trigger.** Handler on `FunctionDef`, `AsyncFunctionDef`, `Lambda`. Pair each default with its parameter: positional defaults align with the *last* `len(defaults)` of `posonlyargs + args`, and `kw_defaults[i]` belongs to `kwonlyargs[i]` (`None` means no default). A default is **mutable** if it is:

| Expression | `data.kind` |
|---|---|
| `[...]` list display | `list-display` |
| `{...: ...}` dict display (including `{}`) | `dict-display` |
| `{a, b}` set display | `set-display` |
| list/set/dict comprehension | `comprehension` |
| a call whose `ctx.qualified_name(func)` is in `builtins.list/dict/set/bytearray`, `collections.defaultdict/OrderedDict/deque/Counter/ChainMap`, or `extend-mutable-calls` | `call` (plus `data.call`) |

**Not mutable** (no flag): `None`, numbers, strings, bytes, tuples (even `(1, [2])`, since we don't look inside: documented), `frozenset()`, `frozendict(...)` (3.15, PEP 814; **Provisional, S-15**: if `frozendict` isn't a 3.15 builtin under that name, drop it from this list), names (`x=DEFAULTS`: could be mutable, but flagging every name would be noisy), attribute access, generator expressions (single-use, a different bug, out of scope).

**Message:** ``mutable default `{segment}` for parameter `{param}` is shared between calls``, where `segment` is the source text of the default, truncated to 30 characters with `…`.
**Location:** the default expression.
**`data`:** `{"parameter": "cache", "kind": "dict-display", "function": "cleanup", "call": null}` (function is `"<lambda>"` for lambdas).
**Help:** ``use `{param}=None` and create the value inside the function: `if {param} is None: {param} = {empty}` `` where `empty` is `[]`, `{}`, `set()` or the call text, by kind.

**Options:** `extend-mutable-calls: tuple[str, ...] = ()`.

**Edge cases:** positional-only defaults (`def f(a=[], /)`), keyword-only (`def f(*, a={})`), lambda defaults, an `async def` with a mutable default, `.pyi` stubs (defaults are `...`, so no flag), and `def f(x=list)` (the *type* `list`, not a call: no flag).

### 6.7 Filtering pipeline (`core/filtering.py`, used by every Python-source command)

Analyzers produce *raw* diagnostics with default severities. `api.py` then calls `apply_filters` **once** (D-046). It runs these steps **in this order** (the order is part of the contract, and each step is a test):

```python
def apply_filters(diagnostics: Iterable[Diagnostic], config: Config, *,
                  selection: Selection,                # resolved by api.py, AFTER plugin loading (D-047)
                  suppressions: SuppressionProvider,   # D-051
                  ) -> tuple[Diagnostic, ...]: ...
```

> **Relationship to M0 (D-037):** steps 1, 2 and 4 already exist in M0's `core/selection.py` (`resolve()` / `apply()`, M0 §6.7). C3 does **not** reimplement them. `core/filtering.apply_filters` *composes* `selection.resolve` + `selection.apply` with the new suppression steps 3, 5 and 6. Selector semantics (exact code or name, code prefix, default-off codes, unknown-selector errors) are defined once, in M0 §6.7, and the description below restates them for convenience. If the two ever disagree, M0 §6.7 wins, and this section gets fixed. The only change C3 makes to `selection.py` is splitting `apply()` so that suppressions can run between per-file-ignores (step 2) and severity overrides (step 4).

1. **Selection.** Resolve `select`/`ignore` selectors (config, overridden by CLI flags; flags *replace* config values, they don't merge). A selector is an exact code (`CRT301`), an exact name (`blocking-call-in-async`), or a **code prefix** (`CRT`, `CRT3`, `CRT30`). Name prefixes aren't allowed. An unknown selector (matching no registered code, name or prefix) is a `UsageError` for flags and a `ConfigError` for config, with suggestions. A code is **selected** if some `select` selector matches it and no `ignore` selector matches it (`ignore` wins). **Off-by-default codes** (`enabled_by_default=False`, such as CRT005) are selected only by an *exact* code or name, never by a prefix. **Selection is resolved before running, by `api.py`**, after plugins are loaded (so plugin codes exist) and intersected with the command's scope (D-047). The *same* `Selection` object is passed to `run_rules` (which instantiates only selected rules, saving time) and to `apply_filters` (which drops anything outside it, for example CRT001 when not selected, and tells CRT005 what was checked).
2. **Per-file ignores.** For each `glob → selectors` entry in `per-file-ignores` (matched against the posix `relpath` with the same glob semantics as `include`/`exclude` from M0), drop diagnostics in matching files whose code matches a selector.
3. **Suppression comments**, §5.4. For each diagnostic, `suppressions.index_for(diagnostic.location.path)` returns a `SuppressionIndex` or `None`. `None` means "no suppressions for this path": always the case for archive paths containing `!` (D-050). Record which suppression items were used.
4. **Severity overrides** from `[tool.cartographer.severity]` (keys are codes or names, values are `"info" | "warning" | "error"`). The result is a new frozen `Diagnostic` via `dataclasses.replace`.
5. **CRT005**, if selected: one diagnostic per unused suppression item whose code was selected.
6. **CRT004** diagnostics from suppression parsing are added here. They pass through steps 1 and 4 (they can be ignored or re-severitied by config), but never step 3.
7. Sort (02 §4.4).

`--fail-on` is applied by the CLI after this, on the final severities.

**Suppression types (D-051, `core/suppressions.py`):**
```python
@dataclass(frozen=True, slots=True)
class SuppressionItem:
    code: str                       # resolved code, e.g. "CRT301" (names are resolved to codes at parse time)
    directive: Literal["ignore", "ignore-file"]
    location: Location              # the comment, for CRT005

class SuppressionIndex:            # one per file; mutable only in its `used` set
    def match(self, diagnostic: Diagnostic) -> SuppressionItem | None   # marks the item used
    def unused(self) -> tuple[SuppressionItem, ...]
    invalid: tuple[Diagnostic, ...]  # CRT004 diagnostics found while parsing

class SuppressionProvider(Protocol):
    def index_for(self, path: str) -> SuppressionIndex | None: ...

class PythonSuppressionProvider:  # built from a Project; caches one index per .py/.pyi relpath
    def __init__(self, project: Project) -> None: ...
    def index_for(self, path: str) -> SuppressionIndex | None: ...   # None for unknown paths and '!' paths
```
Indexes are built lazily, on the first diagnostic for that path. CRT004 diagnostics are collected from every index that was built, **plus** every Python file in the project (so invalid suppressions in files without findings are still reported). C7 adds a `YamlSuppressionProvider` with the same protocol. A composite provider (`ChainProvider(python, yaml)`) dispatches by file extension.

**`PythonSuppressionProvider` index construction.** Use `tokenize.generate_tokens` over `SourceFile.text`. For each `COMMENT` token whose text matches `^#\s*cartographer:`, parse it with the grammar in §5.4. Map line suppressions to the logical line's span: track the first token line after each `NEWLINE`/`NL`, and assign the comment to the span `[first_line, newline_token_line]`. If tokenizing fails (`tokenize.TokenError`, `SyntaxError`, `IndentationError`), there are no suppressions for that file. The file already has CRT001 from parsing.

### 6.8 Plugins (`rules/plugins.py`)

**Discovery.** `importlib.metadata.entry_points(group="cartographer.rules")`, sorted by `(entry_point.name, entry_point.value)` for determinism. Each entry point's `load()` must return either:
- a `Rule` subclass (already registered as a side effect of importing its module), or
- a module, in which case every `Rule` subclass *defined in that module* (`cls.__module__ == module.__name__`) counts as provided.

Anything else is a plugin error (`phase="load"`, `"entry point must reference a Rule subclass or a module"`).

**Isolation.** Plugins are code the *user* installed into Cartographer's environment, not target-project code, so loading them doesn't violate D-013. They can still be buggy:

| Failure | Handling |
|---|---|
| `ep.load()` raises anything (including `RuleRegistrationError` from a bad code) | Record `PluginError(phase="load")`, log WARNING, skip the entry point, continue |
| A plugin rule's handler / `begin_file` / `end_file` raises during a file | Record `PluginError(phase="run", rule=…, path=…)`, log WARNING (traceback at DEBUG, or printed with `--debug`), **disable that rule for the rest of the run**, drop its diagnostics *for that file only* (partial results could mislead), continue with the other rules |
| A **builtin** rule raises | Not isolated: it's our bug, so propagate it. The CLI exits 3 (D-032) |

```python
@dataclass(frozen=True, slots=True)
class PluginError:
    entry_point: str           # entry point name
    distribution: str | None   # e.g. "cartographer-broken-plugins"
    version: str | None
    phase: Literal["load", "run"]
    rule: str | None           # code, for run errors
    path: str | None           # relpath, for run errors
    error: str                 # "RuntimeError: boom"
```
Plugin errors go into `Result.payload.plugin_errors` (JSON) and `Result.stats["plugin_errors"]`. The text renderer prints one line per error **after** the diagnostics and before the summary:
```
plugin error: `crash` (cartographer-broken-plugins 0.1.0) disabled after RuntimeError: boom (rule CRT902 on app/handlers.py)
```
Exit codes are unaffected (plugin errors aren't findings about the user's code).

**Options for rules (builtin and plugin).** At config-load time (M0 §6.9, eager), `RulesConfig` only checks that every `[tool.cartographer.rules.<key>]` sub-table is a table, and keeps it **raw** (`options: Mapping[str, Mapping[str, object]]`). Rule names aren't all known yet, because plugins load later. The engine validates the tables **after plugin loading**, in `rules.engine.resolve_options(config, registry, plugin_errors, plugins_loaded)`:

| Situation | Behaviour |
|---|---|
| Key is a registered rule name | Validate with that rule's `options_class` (unknown option keys or wrong types → `ConfigError`, exit 2, with a "did you mean") |
| Key is a code (`CRT301`) | `ConfigError`: ``use the rule name `blocking-call-in-async` instead of `CRT301` `` |
| Unknown name, plugins were loaded, **no** plugin failed to load | `ConfigError` with suggestions, plus the hint "if this table belongs to a plugin you uninstalled, remove it" |
| Unknown name, plugins were loaded, but **≥ 1 plugin failed to load** | WARNING and ignore (the table might belong to the broken plugin) |
| Unknown name, plugins **not** loaded (`--no-plugins` / `load-plugins = false`) | INFO log and ignore (it may belong to a plugin) |

**Why fail on unknown names?** It's the same rule as D-015: a typo like `[tool.cartographer.rules.blocking-calls-in-async]` should fail loudly, not be silently ignored.

**Fixture plugins** (`tests/fixtures/plugins/`, documented as the single exception to 05 §3.5 "fixtures are never imported"):

```
tests/fixtures/plugins/
├── README.md
├── example_plugin/
│   ├── pyproject.toml          # name="cartographer-example-plugin", version="0.1.0"
│   │                           # [project.entry-points."cartographer.rules"]
│   │                           # print-call = "cartographer_example_plugin:PrintCallRule"
│   └── src/cartographer_example_plugin/__init__.py   # CRT901 print-call (info): flags print(...)
└── broken_plugins/
    ├── pyproject.toml          # name="cartographer-broken-plugins", version="0.1.0", three entry points:
    │                           # crash   = "cartographer_broken_plugins.crash:CrashRule"      (CRT902, raises in handler)
    │                           # badcode = "cartographer_broken_plugins.badcode:BadCodeRule"  (code="CRT301" → registration error)
    │                           # notarule = "cartographer_broken_plugins.notarule:some_function"
    └── src/cartographer_broken_plugins/{__init__,crash,badcode,notarule}.py
```
**How tests "install" them without network or pip:** a pytest fixture `fake_distribution(tmp_path, name, version, entry_points, src_dir)` copies the package into `tmp_path`, writes `tmp_path/<name>-<version>.dist-info/METADATA` (`Metadata-Version: 2.1`, `Name`, `Version`) and `entry_points.txt` (INI format), then `monkeypatch.syspath_prepend(tmp_path)` and `importlib.invalidate_caches()`. `importlib.metadata` finds distributions by scanning `sys.path` for `*.dist-info` directories. That *is* the lesson: an entry point is just a line in a text file. Teardown removes the plugin modules from `sys.modules` and restores the registry with `registry.snapshot()` (a context manager that copies and restores the registry dicts).

One extra slow, network-marked integration test does a real `uv pip install` of `example_plugin` into a temporary venv and runs `cartographer rules` there.

### 6.9 Engine (`rules/engine.py`)

```
# api.py: the orchestration for `check` (the only place that filters, D-046)
def check(project, config, *, load_plugins=True) -> Result[RulesPayload]:
    plugins_loaded = load_plugins and config.section("rules").load_plugins
    plugin_errors = rules.plugins.load_into_registry() if plugins_loaded else []   # registers external codes
    selection = core.selection.resolve(config, scope=rules.check_scope())          # D-047, AFTER plugin load
    options = rules.engine.resolve_options(config, registry, plugin_errors, plugins_loaded)
    raw = rules.run_rules(project, config, selection=selection, options=options)
    diagnostics = core.filtering.apply_filters(
        raw.diagnostics, config, selection=selection,
        suppressions=PythonSuppressionProvider(project))
    return dataclasses.replace(raw, diagnostics=diagnostics,
                               payload=RulesPayload(plugin_errors + raw.payload.run_errors))

# rules/engine.py: returns RAW diagnostics
def run_rules(project, config, *, selection, options) -> Result[RulesRunPayload]:
    rules = [cls(options[cls.name]) for cls in registry.rule_classes() if cls.code in selection.enabled]
    diagnostics = []
    for source in project.files:                            # sorted by relpath (02 §4.6)
        diagnostics += source.parse_diagnostics             # CRT001/CRT002
        if source.tree is None: continue
        ctx = RuleContext(source, config, resolver=QualNameResolver.build(...))
        active = [r for r in rules if not disabled(r)]
        walk(source.tree, ctx, DispatchTable(active))       # with begin_file/end_file around it
        diagnostics += ctx.diagnostics
    return Result("check", tuple(sorted(diagnostics)), RulesRunPayload(run_errors), stats)   # raw: NOT filtered
```
`stats`: `files_analyzed`, `rules_run`, `plugin_errors`, `duration_s`, and per-code counts `count_CRT301`… (used by `--statistics`). Per-code counts are recomputed by `api.py` **after** filtering, so they match what the user sees.

**`rules.check_scope()`** returns `{CRT001–CRT005} ∪ {codes of all registered rules}`. That includes plugin codes and, once C5 is merged, CRT501–CRT505.

## 7. Diagnostics

| Code | Name | Default | Trigger (summary) | `data` fields |
|---|---|---|---|---|
| CRT301 | `blocking-call-in-async` | warning | §6.6 | `call`, `alias`, `function`, `category` |
| CRT302 | `finally-control-flow` | warning | §6.6 | `statement`, `try_line` |
| CRT303 | `mutable-default-argument` | warning | §6.6 | `parameter`, `kind`, `function`, `call` |
| CRT004 | `invalid-suppression` | warning | §5.4 | `comment` (raw text), `reason`: `"missing-codes"`, `"empty-list"`, `"unknown-directive"`, `"unknown-code"`, `"prefix-not-allowed"`, `"not-on-code-line"`, `"ignore-file-too-late"`, `"malformed"`; `item` (offending item, or null) |
| CRT005 | `unused-suppression` | info, off | §5.4 | `item`, `directive`: `"ignore"` or `"ignore-file"` |

CRT004 example messages:
- ``suppression comment needs a list of codes, e.g. `# cartographer: ignore[CRT301]` ``
- `` unknown code `CRT399` in suppression comment ``
- `` code prefixes are not allowed in suppressions: `CRT3` ``

CRT005 example: `` unused suppression for `CRT301` (nothing was reported on this line) ``

## 8. Configuration

```toml
[tool.cartographer.rules]
load-plugins = true            # bool; false = never load entry points (same as --no-plugins)

[tool.cartographer.rules.blocking-call-in-async]
blocking-calls        = []     # omit to use the built-in list; a list replaces it
extend-blocking-calls = []     # list[str] of dotted names
allow-calls           = []     # list[str] of dotted names

[tool.cartographer.rules.mutable-default-argument]
extend-mutable-calls  = []     # list[str] of dotted names

# Generic keys from 03 §4.2 used by C3: select, ignore, fail-on, per-file-ignores, severity
```
```python
# rules/config.py: import-light (stdlib + core only), registered in cli/sections.py (D-043)
@dataclass(frozen=True, slots=True)
class RulesConfig:
    load_plugins: bool = True
    options: Mapping[str, Mapping[str, object]] = field(default_factory=dict)   # raw per-rule tables
```
At load time, `RulesConfig` checks only that `load-plugins` is a bool and that every other key under `rules` is a table. Nested tables are keyed by **rule name** (not code) because names are readable. They are validated later, after plugin loading, with the exact behaviour in §6.8 ("Options for rules").

## 9. Phases & tasks

Each phase is one PR (D-009). 🖐 = a good hands-on task for the owner.

### Phase 1: Engine skeleton (`c3/engine`)
- [ ] Write concept notes `visitor-pattern`, `decorators`, `class-registries` (first drafts are enough to start; finish them before the PR merges).
- [ ] `rules/base.py`: `RuleOptions`, `NoOptions`, `handles`, `Rule.__init_subclass__` with all validation steps (§6.2), and `RuleRegistrationError`.
- [ ] `rules/registry.py`: register, `by_code`, `by_name`, `rule_classes()` (sorted), `snapshot()`.
- [ ] `rules/context.py`: `Scope`, `ScopeKind`, `RuleContext` (qualified-name method stubbed to `None` until phase 2).
- [ ] `rules/dispatch.py`: iterative walk with the outer/inner split table and `SET_ANNOT`.
- [ ] `rules/engine.py`: `run_rules` without plugins or filtering (raw diagnostics, sorted).
- [ ] `rules/config.py` (`RulesConfig`) and its `cli/sections.py` entry.
- [ ] `api.run_rules` (resolves the selection with `rules.check_scope()`; uses M0's `selection.apply` until phase 4), `cli/commands/check.py` (basic), `cli/commands/rules.py` (list + detail).
- [ ] 🖐 Write a throwaway test rule in `tests/unit/rules/test_dispatch.py` that records the event order for the §6.5 worked example.
- [ ] Tests T-C3-01…08.

### Phase 2: Qualified names + CRT301 (`c3/blocking-calls`)
- [ ] Concept note `asyncio-basics` (with a runnable demo of a blocked loop, measured with `time.perf_counter`).
- [ ] `core/qualnames.py` (§6.3), with tests for every binding kind and every limitation.
- [ ] `RuleContext.qualified_name` wired to the resolver.
- [ ] `rules/builtin/async_blocking.py` (CRT301) + options + explanation.
- [ ] Tests T-C3-09…14, T-C3-39.

### Phase 3: CRT302 + CRT303 (`c3/finally-defaults`)
- [ ] Concept notes `try-finally-semantics` (must show the 3.14 `SyntaxWarning` with `python -W error::SyntaxWarning`; mark the version) and `function-defaults` (including PEP 661 `sentinel` on 3.15 as an alternative to `None`; **Provisional, S-15**: check that the builtin exists and what it's called on the installed 3.15 before writing the example).
- [ ] `rules/builtin/finally_flow.py`, `rules/builtin/mutable_defaults.py`.
- [ ] 🖐 Implement the CRT303 "pair defaults with parameters" helper yourself. It's a nice exercise in list slicing.
- [ ] Fixture `rules_basic` + golden files (text, json, sarif).
- [ ] Tests T-C3-15…20.

### Phase 4: Filtering pipeline + suppressions (`c3/filtering`)
- [ ] `core/suppressions.py` (tokenize-based, §5.4), `core/filtering.py` (§6.7).
- [ ] Make `api.py` the **single filtering point** (D-046): replace its M0 `selection.apply` calls with `apply_filters(..., suppressions=PythonSuppressionProvider(project))` for **every** Python-source command that exists at this point (`scan`, `check`, plus `graph` and `startup analyze` if C1/C2 are merged). Confirm that no analyzer and nothing in `cli/main.py` filters.
- [ ] CRT004/CRT005 explanations in `core/codes.py`.
- [ ] Extend the `tokenize-and-comments` concept note with a "suppression comments" section.
- [ ] Tests T-C3-21…28, T-C3-36, T-C3-38.

### Phase 5: Plugins (`c3/plugins`)
- [ ] Concept note `entry-points-and-plugins` (show `entry_points.txt` contents and `importlib.metadata.entry_points()` live).
- [ ] `rules/plugins.py`, isolation in the engine, `--no-plugins`, `load-plugins` config.
- [ ] `core.codes.register_external` calls for plugin rules; selection resolved after plugin load (D-047); SARIF `rules` include plugin codes; `resolve_options` behaviour table (§6.8).
- [ ] Fixture plugins + `fake_distribution` pytest fixture + `registry.snapshot()`.
- [ ] `explain` and `rules` show plugin rules and their source distribution.
- [ ] 🖐 Write your own plugin rule (`CRT9xx`) in the example plugin. See Exercise 1.
- [ ] Tests T-C3-29…35, T-C3-37.

### Phase 6: Acceptance & docs (`c3/acceptance`)
- [ ] Benchmark `check` on the 2,000-file synthetic project (05 §6 budget: < 8 s).
- [ ] CI `dogfood` job: `cartographer check .` must report zero diagnostics (root `.`, D-048; fixtures are excluded by the repo's config).
- [ ] Walkthrough, write-up, comparison (§12).
- [ ] Version 0.3.0, `CHANGELOG.md`.

## 10. Test plan

| ID | Test | Kind |
|---|---|---|
| T-C3-01 | Defining a subclass with valid keywords registers it, and the registry finds it by code and by name | unit |
| T-C3-02 | Each `__init_subclass__` validation (bad code regex, bad name, missing summary, duplicate code, duplicate name, builtin code not in `core.codes`, plugin code outside CRT9xx, no handlers) raises `RuleRegistrationError` with a message naming the class | unit, parametrized |
| T-C3-03 | `abstract=True` classes don't register, and their `@handles` methods are inherited by concrete subclasses | unit |
| T-C3-04 | `@handles` returns the original function (identity), and rejects empty or non-AST arguments | unit |
| T-C3-05 | Every builtin rule's `explanation` has the six sections of 04 §5, and its code, name and severity match `core.codes` | unit |
| T-C3-06 | The dispatcher calls handlers for base-class registrations (`@handles(ast.stmt)`) | unit |
| T-C3-07 | The dispatcher survives a 5,000-deep nested `BinOp` expression without `RecursionError` | unit |
| T-C3-08 | The event order for the §6.5 worked example matches exactly (default evaluated outside the async scope) | unit |
| T-C3-09 | `QualNameResolver`: every row of the §6.3 binding table resolves as specified | unit, parametrized |
| T-C3-10 | Resolver limitations behave as documented (assignment alias → None; star import → None; conflicting imports → None; class-scope skipping) | unit |
| T-C3-11 | Relative imports resolve against the package, both for `__init__.py` and for plain modules; above-top → None | unit |
| T-C3-12 | CRT301: every edge-case row in §6.6 | unit, parametrized |
| T-C3-13 | CRT301 options: replace, extend and allow lists behave, and invalid names are a `ConfigError` | unit |
| T-C3-14 | Property: for random nesting of `async def`/`def`/`lambda`/`class` (Hypothesis builds the source text), CRT301 fires iff the innermost function-like scope is `async def` | property |
| T-C3-15 | CRT302: every edge-case row in §6.6, including the loop-`else` case and single reporting for nested try | unit, parametrized |
| T-C3-16 | Property: CRT302 fires on generated code iff `compile()` on Python ≥ 3.14 emits the PEP 765 `SyntaxWarning` for it (oracle = CPython itself, `requires_py314`) | property |
| T-C3-17 | CRT303: every kind in the table, the non-mutable list, and the positional/keyword-only pairing | unit, parametrized |
| T-C3-18 | CRT303 `data` and message truncation at 30 characters | unit |
| T-C3-19 | Golden: `check rules_basic` in text, json and sarif | golden |
| T-C3-20 | `--statistics` output and ordering | golden |
| T-C3-21 | Suppression grammar: valid forms parse, and each invalid form yields CRT004 with the right `reason` | unit, parametrized |
| T-C3-22 | Line suppression applies across a multi-line logical line, and `#` inside a string literal is not a comment | unit |
| T-C3-23 | `ignore-file` works on lines ≤ 20 and is CRT004 after that | unit |
| T-C3-24 | CRT005 only when selected by exact code, and only for selected codes | unit |
| T-C3-25 | Filter-order contract: per-file-ignore beats a severity override (the dropped diagnostic never gets re-severitied); `ignore` beats `select`; off-by-default codes aren't selected by prefix | unit |
| T-C3-26 | Unknown selectors: `UsageError` (flag) / `ConfigError` (config) with suggestions | unit |
| T-C3-27 | Severity overrides by code and by name change `--fail-on` behaviour (exit 0 → 1) | integration |
| T-C3-28 | Suppressions also apply to C1 `graph` diagnostics (skipped if C1 isn't merged) | integration |
| T-C3-29 | Example plugin via `fake_distribution`: CRT901 is listed by `rules`, runs in `check`, and is explained by `explain` | integration |
| T-C3-30 | Broken plugins: load failure, registration failure and "not a rule" each produce a `PluginError(phase="load")`, and the run still succeeds | integration |
| T-C3-31 | Crashing plugin rule: disabled after the first crash, its diagnostics for that file dropped, other rules unaffected, error printed, exit code unchanged | integration |
| T-C3-32 | A builtin rule crash (monkeypatched to raise) produces exit 3 | integration |
| T-C3-33 | `--no-plugins` and `load-plugins = false` skip discovery (entry-point function never called) | unit |
| T-C3-34 | Real install into a temp venv lists CRT901 (`slow`, `network`) | integration |
| T-C3-35 | Plugin rule options are validated by its `options_class`. Unknown rule names follow every row of the §6.8 "Options for rules" table (ConfigError / WARNING / INFO) | unit, parametrized |
| T-C3-36 | **Filter once (D-046):** a file with two used suppressions and one unused, run through the full CLI with `--select CRT,CRT005`, yields exactly one CRT005 and no duplicated CRT004. A spy asserts `apply_filters` is called exactly once per command and that `run_rules` returns unfiltered diagnostics | integration |
| T-C3-37 | **Plugin codes (D-047):** with the example plugin, `--select CRT901` works, `--select CRT9` and the default `CRT` include it, `explain CRT901` works, and SARIF `tool.driver.rules` contains CRT901 with its name and summary. With `--no-plugins`, `--select CRT901` is a `UsageError` | integration |
| T-C3-38 | **Suppression providers (D-051):** `PythonSuppressionProvider.index_for` returns `None` for paths containing `!` and for non-project paths. The comment-only-line CRT004 rule applies to Python indexes only. A `ChainProvider` dispatches by extension | unit |
| T-C3-39 | CRT301 default table: `len == 39` and the per-category counts match §6.6 | unit |

## 11. Acceptance criteria

| ID | Criterion |
|---|---|
| A-C3-01 | `cartographer check tests/fixtures/projects/rules_basic` prints exactly the golden output in §5.1 (timing excluded) and exits 0. With `--fail-on warning` it exits 1 |
| A-C3-02 | `cartographer rules` lists CRT301–CRT303. `cartographer rules CRT301` and `cartographer explain CRT301` print the six-section explanation |
| A-C3-03 | All T-C3 tests pass on the full CI matrix (Windows + Ubuntu × 3.13/3.14/3.15/3.15t). T-C3-16 runs on ≥ 3.14 |
| A-C3-04 | With the example plugin installed, `rules` lists CRT901 with its distribution name and version, and `check` reports it |
| A-C3-05 | With the broken plugins installed, `check` completes, reports exactly three load errors and one run error, and exits with the same code as without them |
| A-C3-06 | Every suppression example in §5.4 behaves as specified (covered by T-C3-21…24) |
| A-C3-07 | `cartographer check .` on Cartographer itself (root `.`, D-048) reports zero diagnostics (CI `dogfood` job) |
| A-C3-08 | Performance: `check` on the 2,000-file synthetic project completes in < 8 s on the dev machine (05 §6), recorded in the write-up |
| A-C3-09 | On at least one acceptance-corpus repository (S-07), the C3 rules run without crashing. Every reported CRT301/302/303 is manually triaged as true or false positive in the write-up, with precision stated |
| A-C3-10 | Documentation: all seven concept notes for Stage 3 written (✅ in `docs/learn/README.md`); walkthrough, write-up and comparison exist; glossary and FAQ updated |

## 12. Documentation deliverables

**Concept notes (owned by C3, exact slugs):** `visitor-pattern`, `decorators`, `class-registries`, `entry-points-and-plugins`, `asyncio-basics`, `try-finally-semantics`, `function-defaults`. Specific content each must include:
- `visitor-pattern`: `ast.NodeVisitor` vs our dispatcher. Why one pass, with a measurement: 1 walk × 3 rules vs 3 walks on the synthetic project. Why iterative, with the recursion-limit demo.
- `decorators`: functions as objects, closures, decorators with arguments, `functools.wraps`, `ParamSpec`. **Why `@handles` deliberately does not wrap** (it marks instead).
- `class-registries`: `__init_subclass__` with class keywords; the metaclass equivalent (and why we don't need one); how methods become bound methods (descriptor link to `descriptors-and-cached-property`).
- `entry-points-and-plugins`: what `entry_points.txt` looks like; `importlib.metadata`; isolation strategies; why plugins are trusted code but still fallible.
- `asyncio-basics`: event loop, coroutines, `await`, a measured demo of one blocking call delaying 10 tasks; `to_thread`; link to research §2.6.
- `try-finally-semantics`: what `finally` guarantees; the swallowing demo; PEP 765 and the 3.14 warning; loops inside `finally`.
- `function-defaults`: defaults are evaluated once (show `f.__defaults__`); the `None` idiom; `sentinel` (PEP 661, 3.15; Provisional, S-15).

**Walkthrough** `docs/learn/walkthroughs/C3.md`: trace `rules_basic/app/handlers.py` line 10 from tokens → AST → resolver binding table → dispatcher events → `ctx.report` → filtering → text output. Include a Mermaid diagram of engine → dispatcher → rules → filtering.

**Write-up** `docs/learn/writeups/C3.md`: predictions vs reality; the one-pass vs multi-pass measurement; corpus triage with a precision estimate; any false positives and what caused them.

**Comparison** `docs/learn/comparisons/C3.md`: see §13.

**FAQ seeds to add:** "Why doesn't Cartographer flag `Path.read_text()` in async code?" (no type inference) and "Why must suppressions list codes?"

## 13. Reference implementations to compare after

Read only *after* acceptance (D-008). Rule codes below are as named in those projects' docs at the time of writing. Verify them when writing the comparison.

| Reference | What to look at | Questions to answer |
|---|---|---|
| **ruff** (`ASYNC` rules, e.g. `ASYNC210`, `ASYNC230`, `ASYNC251`; `B006`; `B012`) | How ruff resolves qualified names (its "semantic model"); how it handles noqa comments | How does ruff know `nap` is `time.sleep`? Does it flag the class-body-in-async case? Does it flag defaults of nested defs? |
| **flake8-async** | The rule list and the reasoning per call | Which blocking calls do they list that we don't, and why? |
| **flake8's plugin API** (entry-point group `flake8.extension`) | How a plugin class is discovered, instantiated and run | Compare their plugin contract with ours: what does theirs make easy or hard? |
| **flake8-bugbear** `B006`, `B012` | Mutable defaults, jump statements in `finally` | Do they treat `frozenset()` or `dict()` calls differently? Loop-`else`? |
| **pylint** `W0150 lost-exception` | Same bug as CRT302 | How did pylint describe it before PEP 765 existed? |

Run all of them on `rules_basic` and on the corpus repo, and tabulate the differences (template §2).

## 14. Risks & open items

- **R-05 (false positives):** CRT301 relies on names only. Mitigation: precision-first resolution (ambiguous → no flag), the allow-list option, corpus triage in A-C3-09.
- **Plugin API stability:** the plugin API (`cartographer.rules` exports) is 0.x and may change before 1.0. Say so in the `entry-points-and-plugins` note and in `rules/__init__.py`'s docstring.
- **3.14+ `SyntaxWarning`:** T-C3-16 uses CPython as an oracle. If the warning's exact conditions differ from §6.6 (for example in the loop-`else` case), **CPython wins**: update §6.6 and record it in the write-up.
- **Spike S-15** (needed by C3 phase 3): do `frozendict` and `sentinel` exist as 3.15 builtins under those names? It affects only the CRT303 "not mutable" list and the `function-defaults` note.
- **Filtering contract (D-046, D-047, D-051):** C3 is where the single filtering point is built. Any later command that filters on its own is a bug, and T-C3-36 guards it.

## 15. Exercises for the learner

1. **Write a plugin rule.** In the example plugin, add `CRT902 assert-in-production` that flags `assert` statements outside files matching `tests/**`.
   *Hint:* `@handles(ast.Assert)`. Use `ctx.source.relpath` and `fnmatch` or the glob helper. Remember the code must be `CRT9xx`.
2. **Break the resolver.** Find three ways to call `time.sleep` inside `async def` that CRT301 misses. For each, explain which design decision (§6.3 limitations) causes the miss and whether fixing it would add false positives.
   *Hint:* aliases through assignment, `getattr(time, "sleep")`, `importlib.import_module`.
3. **Measure the event-loop cost.** Write a script with 10 tasks that each `await asyncio.sleep(0.1)`, then add one `time.sleep(0.5)` in one task. Predict the total runtime of each version, then measure.
   *Hint:* `asyncio.gather`, `time.perf_counter()`.
4. **PEP 765 by hand.** Without running it, predict what each of these returns or raises, then check on 3.15 with `-W error::SyntaxWarning`: (a) `return` in `finally` after `raise`, (b) `break` in `finally` inside a `for`, (c) `continue` in a loop *inside* `finally`.
5. **Mutable defaults in the wild.** Run `cartographer check --select CRT303` on a corpus repo. For each finding, decide: real bug, harmless (never mutated), or intentional cache? What would ruff's `B006` say?
