# C5 ★: f-string → t-string migration with a processor verifier

> **Status:** Approved spec, revision 1 (2026-11-03) · **Size:** XL · **Version at end:** 0.5.0
> **Depends on:** C3 (rule engine, `core/qualnames.py`, filtering and suppressions). M0 core.
> **Research:** §2.12 (PEP 750 t-strings), §00 "Where my searches found nothing" (no f→t codemod exists; no t-string taint rule in ruff or Bandit; Semgrep can't parse t-strings; ruff `S608` only *flags* SQL built from strings), §3 "Strings, grammar, t-strings" and "Packaging & security" rows.
> **Codes owned:** CRT501–CRT506.
> **Spikes:** S-03 (LibCST) and S-10 (`ast`/`tokenize`/`templatelib` shapes) in phase 1; S-05 (third-party processors) in phase 4.
> **★ Novel:** as far as the research could find, no existing tool rewrites injection-prone strings to t-strings, or property-tests a t-string processor. Expect to discover things nobody has written down. Record them in the write-up.

---

## 1. Summary

**The problem.** Python code often builds SQL queries, shell commands and HTML by gluing strings together:

```python
cur.execute(f"SELECT * FROM users WHERE name = '{name}'")
```
If `name` is `x' OR '1'='1`, the *structure* of the query changes: the attacker's text becomes SQL code. This is **injection**, one of the oldest and most damaging classes of security bug.

**The new tool in the language.** Python 3.14 added **template strings** (PEP 750). `t"…"` looks like an f-string but does **not** produce a `str`. It produces a `string.templatelib.Template` object that keeps the *fixed text* and the *interpolated values* **separate**. A **processor** (a function that consumes a `Template`) can then send the values as query parameters, escape them for HTML, or keep them as separate command-line arguments. The values never get a chance to become code.

**What C5 builds:**
1. **A finder** (`cartographer tstring find`) that locates dynamic strings (f-strings, `%`-formatting, `.format()`, `+` concatenation, `str.join`) **flowing into** SQL, shell or HTML **sinks** (the functions where injection does harm). It uses an **intra-procedural taint analysis**: it follows strings through variables, `if` branches and loops *within one function*. Findings are CRT501/CRT502/CRT503.
2. **A codemod** (`cartographer tstring fix`) that **rewrites** those strings into t-strings and wraps the sink call with the right **adapter**:
   ```python
   cur.execute(*sql(t"SELECT * FROM users WHERE name = {name}"))
   ```
   It refuses (CRT505) whenever a rewrite would not be safe, for example a dynamic table name, which parameters can't replace.
3. **Reference adapters** (`cartographer.adapters`): small, readable processors for DB-API SQL (all five parameter styles), HTML escaping and shell argument lists.
4. **A processor verifier** (`cartographer tstring verify`) that uses **property-based testing** (Hypothesis) to check that a processor, ours or someone else's, **never lets interpolated data change the parsed structure** of the output. A deliberately broken processor must be caught (CRT506).

## 2. Why this matters

- **PEP 750's stated goal is preventing injection.** Tools haven't caught up yet (research §00). Ruff's `S608` *flags* SQL built from strings but can't fix it. No codemod exists (only the reverse, `t2string`). There's no t-string taint rule in ruff or Bandit, and Semgrep can't even parse t-strings (issue #12030). The PEP lists linters only as future work.
- **Migrations are where mistakes happen.** Swapping `f` for `t` alone *breaks* code: `cur.execute(t"…")` passes a `Template` where a `str` is expected. Worse, a careless processor that flattens the template back into a string (`"".join(str(x) for x in t)`) brings the injection right back (CRT504). Doing this migration correctly needs exactly the knowledge this milestone teaches: string grammar, tokenizing, dataflow, CSTs, DB-API parameter styles, HTML contexts, shell word splitting.
- **"Is my processor actually safe?"** is a question nobody can answer by reading code alone. The verifier turns the security property into an executable test: *for any values, the structure of the output is the same as with harmless values*.

## 3. Read before starting

**Existing concept notes:** `ast-basics`, `tokenize-and-comments`, `text-and-encodings`, `visitor-pattern`, `class-registries`, `property-based-testing`, `type-hints-basics`, `subprocess` (C2).

**Written in this milestone:** `string-formatting`, `template-strings`, `injection-attacks`, `dbapi-and-paramstyles`, `literal-string`, `dataflow-and-taint`, `cst-and-codemods`, `structure-preservation`.

**Prediction questions** (`docs/learn/predictions/C5.md`):
1. With `name = "x' OR '1'='1"`, what SQL does `f"SELECT * FROM users WHERE name = '{name}'"` produce, and what rows would it return?
2. What is the *type* of `f"Hello {x}"`? Of `t"Hello {x}"`? What do you get if you `print()` each?
3. Why are query **parameters** safer than "escaping the quotes yourself"?
4. Can a query parameter replace a **table name** (`SELECT * FROM ?`)? Why or why not?
5. `q = "SELECT * FROM t"`, then `if admin: q += f" WHERE owner = {user}"`, then `cur.execute(q)`. Should a tool flag `cur.execute(q)`? Is that a real risk?
6. Our analysis only follows strings *within one function*. Name a common pattern it will miss.
7. `"%s" % x` and `f"{x}"`: when do these produce different results? (Hint: what if `x` is a tuple?)
8. `subprocess.run(["ls", d])` needs no escaping, but `subprocess.run(f"ls {d}", shell=True)` is dangerous. Why?
9. Is `html.escape(value)` enough when the value goes into an attribute **without quotes**, like `<a href={url}>`?
10. "Interpolated data never changes the structure of the output." How could you test that *automatically* for a processor you didn't write?
11. Why can't Cartographer's own source files under `src/` contain `t"…"` literals (D-005)?
12. Guess: in a typical web application, what fraction of f-strings reach a SQL/shell/HTML sink? 1 %? 10 %? 50 %?

## 4. Scope

### In scope
- Sink catalogue (§6.3), user-extensible via config.
- Dynamic-string recognition for f-strings, `%`, `.format()`, `+`, `str.join`, `+=`.
- Intra-procedural, flow-sensitive "may" taint analysis (§6.5) for function bodies, the module body, class bodies and lambdas.
- CRT501–CRT505 via C3 rules (so `cartographer check` runs them too), and CRT506 from the verifier.
- Rewrite planner (§6.8) for f-strings, `%`, `.format()`, concatenation, and single-assignment variables. Adapter import insertion. Text-edit backend + LibCST backend (§6.9).
- `tstring find`, `tstring fix --diff|--write [--unsafe-fixes]`, `tstring verify`.
- `cartographer.adapters` reference processors (§6.10).
- Hypothesis-based verifier with SQL/HTML/shell properties (§6.11).

### Out of scope (and why)
| Not doing | Why |
|---|---|
| Inter-procedural taint (following strings into other functions or through `return`) | NG4. It needs call graphs and summaries, which is a research project of its own. Documented as the main false-negative source |
| Proving a processor *correct* | The verifier is property-based testing: strong evidence, not proof. The concept note explains the difference |
| Rewriting for targets below 3.14 (classic `cur.execute("… = ?", (x,))`) | **Stretch.** v1 gives that advice as `help` text |
| Rewriting dynamic identifiers (table/column names) | Impossible with parameters. CRT505 with allow-list advice |
| `string.Template` (`$name`) sources | Stretch |
| Flask views returning f-string HTML (`return f"<h1>{name}</h1>"`) | Needs "return of a route function" sinks. Stretch |
| SQL dialect-perfect parsing | We use a small lexer (§6.8.2) and refuse when unsure |

## 5. User-facing behaviour

### 5.1 `cartographer tstring find`

```
cartographer tstring find [PATH] [--min-confidence low|medium|high] [--format text|json|sarif] [-o FILE]
```
**Scope (D-047):** `tstring find` can report CRT0xx and CRT501–CRT505, and nothing else. Internally it runs the C3 engine (the injection findings *are* C3 rules, D-038) with that scope: `effective = resolve(select) ∩ {CRT0xx, CRT501–CRT505} − resolve(ignore)`. With the default `select = ["CRT"]` you get every injection finding. `--select CRT3` gives an empty result, which is valid and not an error. Filtering happens once, in `api.py` (D-046). The JSON output adds the `tstring` payload.

**Fixture `tests/fixtures/projects/tstring_basic/`** (an empty `app/__init__.py`, `app/db.py`, and a `pyproject.toml` containing only `[project]`, `name = "tstring-basic"`, `requires-python = ">=3.14"`. That makes `target-version` resolve to 3.14 on every interpreter (03 §4.3), so the golden output is the same on 3.13 CI runners):
```python
# app/db.py
import sqlite3                                                              # 1
                                                                            # 2
                                                                            # 3
def get_user(conn: sqlite3.Connection, uid: int):                          # 4
    cur = conn.cursor()                                                     # 5
    cur.execute(f"SELECT * FROM users WHERE id = {uid}")                    # 6
    return cur.fetchone()                                                   # 7
                                                                            # 8
                                                                            # 9
def find_by_name(conn, name):                                               # 10
    q = "SELECT * FROM users WHERE name = '%s'" % name                     # 11
    return conn.execute(q).fetchall()                                       # 12
                                                                            # 13
                                                                            # 14
def sort_users(conn, column):                                               # 15
    return conn.execute(f"SELECT * FROM users ORDER BY {column}").fetchall()   # 16
```
```
$ cartographer tstring find tests/fixtures/projects/tstring_basic
app/db.py:6:17: CRT501 [warning] f-string reaches SQL sink `execute` (confidence: high; value from parameter `uid`)
  help: use a t-string with a SQL adapter so values become query parameters; preview with `cartographer tstring fix --diff`
app/db.py:12:25: CRT501 [warning] %-formatted string reaches SQL sink `execute` via variable `q` (confidence: high; value from parameter `name`)
  help: use a t-string with a SQL adapter so values become query parameters; preview with `cartographer tstring fix --diff`
  related: app/db.py:11:9 (string built here)
app/db.py:16:25: CRT501 [warning] f-string reaches SQL sink `execute` (confidence: high; value from parameter `column`)
  help: use a t-string with a SQL adapter so values become query parameters; preview with `cartographer tstring fix --diff`
app/db.py:16:25: CRT505 [info] no safe automatic rewrite: `{column}` is in an identifier position (after ORDER BY); parameters can only replace values
  help: check `column` against an allow-list of known column names before building the query, e.g. `if column not in {"id", "name"}: raise ValueError(column)`

Found 0 errors, 3 warnings, 1 info in 2 files (0.03 s).
```
- The location is the **sink argument** expression. `related` points to where the string was built, when that's elsewhere.
- `uid: int` is annotated, but **annotations are not enforced at runtime**, so it is still `high`. The `dataflow-and-taint` note explains why.

### 5.2 `cartographer tstring fix`

```
cartographer tstring fix [PATH] [--diff | --write] [--unsafe-fixes] [--backend auto|text|libcst]
                         [--adapter-mode import|vendor] [--min-confidence LEVEL] [--select CODES]
```
- `--diff` (the default) prints unified diffs to **stdout** and a fix summary to **stderr**. Exit code: 1 if the diff is non-empty, else 0. That makes it useful in CI as "unapplied fixes exist".
- `--write` applies **safe** fixes in place. With `--unsafe-fixes`, it also applies fixes marked `review`. Exit code follows the normal rule (03 §3) on the diagnostics that remain *after* fixing.
- `--backend`: `auto` = LibCST if spike S-03 enabled it (§6.9), else `text`.
- `--adapter-mode` (config `tstring.adapter-mode`, default `import`). **Important: rewritten code needs an adapter at runtime.**
  - `import` (default): the rewrite adds `from cartographer.adapters.sql import qmark as sql`, so **the target project must install `cartographer-py` as a runtime dependency, on Python 3.14+**. The `--help` text, the fix summary (stderr) and the `cartographer explain CRT501` text all say this. Remember the D-003 name-clash caveat too.
  - `vendor`: the rewrite copies Cartographer's small reference adapters *into the target project* (§6.8.8) and imports them from there. The project then needs only Python 3.14+, not Cartographer. That's the right choice for a library you don't want to give a new dependency.
  - Third-party adapters (`tstring.adapters.*`, S-05) are just imports, so the project needs whichever package they come from.
- **Requires** `target-version ≥ 3.14`. Otherwise it's a `UsageError` (exit 2): "t-strings need Python 3.14+; this project targets 3.12 (set `target-version` or `--target-version`)". It also requires the **running interpreter ≥ 3.14**, because rewritten files are validated by parsing them. Otherwise it's a `ToolEnvironmentError` (exit 4).

```
$ cartographer tstring fix --diff tests/fixtures/projects/tstring_basic
```
stderr:
```
2 fixes available (1 safe, 1 needs review):
  app/db.py:6:17   safe    f-string → t-string with cartographer.adapters.sql:qmark (paramstyle detected from `import sqlite3`)
  app/db.py:12:25  review  %-format → t-string; quotes around %s removed (the value is now bound with its own type, not as text); `% name` assumes `name` is not a tuple
1 finding has no safe rewrite (CRT505); see `cartographer tstring find`.
note: the rewritten code imports `cartographer.adapters`, so this project needs `cartographer-py` installed at runtime (Python 3.14+).
      To avoid the dependency, use `--adapter-mode vendor`, which copies the adapters into the project.
```
stdout:
```diff
--- a/app/db.py
+++ b/app/db.py
@@ -1,15 +1,16 @@
 import sqlite3
+from cartographer.adapters.sql import qmark as sql
 
 
 def get_user(conn: sqlite3.Connection, uid: int):
     cur = conn.cursor()
-    cur.execute(f"SELECT * FROM users WHERE id = {uid}")
+    cur.execute(*sql(t"SELECT * FROM users WHERE id = {uid}"))
     return cur.fetchone()
 
 
 def find_by_name(conn, name):
-    q = "SELECT * FROM users WHERE name = '%s'" % name
-    return conn.execute(q).fetchall()
+    q = t"SELECT * FROM users WHERE name = {name}"
+    return conn.execute(*sql(q)).fetchall()
 
 
 def sort_users(conn, column):
```
Running `tstring fix --write --unsafe-fixes` and then `tstring find` again reports only the two `sort_users` diagnostics. Running `fix` a second time produces an **empty** diff (idempotency).

**What the rewritten code does at runtime** (this is the whole point):
```pycon
>>> from cartographer.adapters.sql import qmark as sql     # Python 3.14+
>>> name = "x' OR '1'='1"
>>> sql(t"SELECT * FROM users WHERE name = {name}")
('SELECT * FROM users WHERE name = ?', ("x' OR '1'='1",))
```
The attacker's text travels as a **parameter**, and the database compares it as data.

### 5.3 `cartographer tstring verify`

```
cartographer tstring verify PROCESSOR --kind sql|html|shell [PATH] [--examples N] [--seed S]
                            [--paramstyle auto|qmark|numeric|named|format|pyformat] [--execute]
```
- `PROCESSOR` is `module:function`.
- **Executes code** (the third opt-in execution path, D-013, D-036): it imports and calls the processor.
  - **`cartographer.adapters.*`** need no flag, and **`sys.path` is never modified** for them. `PATH` is then only used to make the CRT506 location relative.
  - **Any other processor** requires `--execute` (exit 2 without it), with a warning, like C2's measure. The import is done in this exact order, to defeat the planted-module hijack from 00 §6.4:
    1. Import everything the verifier itself needs **before** touching `sys.path`: `hypothesis`, `hypothesis.strategies`, `sqlite3`, `html`, `html.parser`, `shlex`, `string.templatelib`, `inspect`, `json` and `re` (the list lives in one constant, `verifier/_preload.py:PRELOAD`).
    2. **Append** `PATH` (resolved to an absolute path) to the **end** of `sys.path`, never the front. A module in `PATH` can therefore never shadow a stdlib or installed module, even one that is imported later.
    3. `importlib.import_module(module)`. Then check that `module.__file__` lies inside `PATH`. If it doesn't (for example `PROCESSOR = "html:escape"` resolved to the stdlib), it's a `UsageError`: `` `html` resolved to <file>, outside PATH; rename your module ``.
  - The verifier runs in-process (no subprocess). Hypothesis uses `database=None` (below).
- Requires Python ≥ 3.14 and the optional extra `cartographer-py[verify]`, which provides Hypothesis (D-035). Otherwise exit 4 with an install hint.
- Defaults: `--examples 500`, `--seed 0`. Runs are deterministic, and Hypothesis's example database is disabled (`database=None`), so no `.hypothesis/` folder appears in your directory.

```
$ cartographer tstring verify cartographer.adapters.sql:qmark --kind sql
Verifying cartographer.adapters.sql:qmark (kind: sql, paramstyle: qmark, 500 examples, seed 0)
  P-SQL-1  query text does not depend on values ........ passed
  P-SQL-2  parameters are exactly the values ............ passed
  P-SQL-3  placeholder count equals interpolation count . passed
  P-SQL-4  executes in sqlite3 and data round-trips ..... passed
All 4 properties passed.
```
```
$ cartographer tstring verify broken:naive_sql --kind sql --execute tests/fixtures/processors
warning: --execute: importing and running `broken:naive_sql` from tests/fixtures/processors
Verifying broken:naive_sql (kind: sql, paramstyle: auto, 500 examples, seed 0)
  P-SQL-1  query text does not depend on values ........ FAILED
  P-SQL-2  parameters are exactly the values ............ FAILED
  P-SQL-3  placeholder count equals interpolation count . FAILED
  P-SQL-4  executes in sqlite3 and data round-trips ..... skipped (paramstyle could not be detected)

tests/fixtures/processors/broken.py:14:1: CRT506 [error] processor `broken:naive_sql` failed P-SQL-1: query text depends on interpolated values
  help: smallest failing input found by Hypothesis:
    template parts: ('SELECT a FROM t WHERE a = ', {v0}, '')
    benign query:   SELECT a FROM t WHERE a = 'x'
    with v0 = "'":  SELECT a FROM t WHERE a = '''
…(one CRT506 per failed property)…

Found 3 errors, 0 warnings, 0 info in 1 file (1.84 s).
```
The exact shrunk example depends on Hypothesis's search, so golden tests pin the **code, property ID and status**, not the counterexample text.

## 6. Design

### 6.1 Files

| File | Phase | Contents |
|---|---|---|
| `tstrings/__init__.py` | 1 | public exports |
| `tstrings/model.py` | 1 | `StrValue`, `Origin`, `Construction`, `SinkSpec`, `SinkMatch`, `Finding`, `RewriteReason` |
| `tstrings/sinks.py` | 1 | default catalogue, config-driven extension, call matching |
| `tstrings/strings.py` | 1 | recognising string constructions; f-string internals via `tokenize` |
| `tstrings/dataflow.py` | 2 | the analysis (§6.5) |
| `tstrings/confidence.py` | 2 | §6.6 |
| `tstrings/rules.py` | 1–2 | C3 `Rule` subclasses CRT501–CRT505 sharing one per-file analysis |
| `adapters/__init__.py`, `adapters/sql.py`, `adapters/html.py`, `adapters/shell.py` | 3 | §6.10 (Python 3.14+ only) |
| `tstrings/sqllex.py` | 4 | tiny SQL lexer (planner + verifier) |
| `adapters/_htmlctx.py` | 3 | HTML context state machine (adapter + planner) |
| `tstrings/plan.py` | 4–5 | rewrite planner → `Fix` objects |
| `tstrings/convert.py` | 5 | `%` / `.format()` / `+` → t-string text |
| `tstrings/apply_text.py` | 4 | text-edit backend, import insertion, encoding/newline preservation, atomic write |
| `tstrings/apply_libcst.py` | 6 | LibCST backend |
| `tstrings/validate.py` | 4 | post-rewrite validation |
| `tstrings/vendor.py` | 5 | vendor step of `fix --adapter-mode vendor` (§6.8.8) |
| `tstrings/verifier/{__init__,strategies,properties,runner,_preload}.py` | 7 | §6.11 (imports Hypothesis lazily); `_preload.py` holds the import-order defence of §5.3 |
| `cli/commands/tstring.py` | 1, 4, 7 | `find`, `fix`, `verify` |
| `api.py` | 1, 4, 7 | `find_tstring_candidates`, `plan_tstring_fixes`, `verify_processor` |

### 6.2 Data model

```python
@dataclass(frozen=True, slots=True)
class Origin:
    kind: Literal["parameter", "untrusted", "call", "attribute", "subscript", "name",
                  "loop", "numeric", "constant"]
    detail: str                  # "uid", "request.args.get", "filters.items()", …

@dataclass(frozen=True, slots=True)
class Construction:
    kind: Literal["f-string", "percent", "format", "concat", "join", "augmented-concat"]
    location: Location           # where the dynamic string was built
    node_id: int                 # id() of the AST node (for the planner; never serialised)

@dataclass(frozen=True, slots=True)
class StrValue:
    """Abstract value of an expression: what *might* it be at runtime?"""
    kinds: frozenset[Literal["static", "template", "dynamic", "unknown"]]
    constructions: frozenset[Construction] = frozenset()
    origins: frozenset[Origin] = frozenset()
    def join(self, other: StrValue) -> StrValue:      # union of all three sets
        ...
BOTTOM = StrValue(frozenset())
```
- `static`: built only from literals. This is the same idea as PEP 675's `LiteralString`: "only literals in the source". The `literal-string` note links the two.
- `template`: a t-string (`Template`) value.
- `dynamic`: a `str` built at runtime from at least one non-static part. **This is what we report.**
- `unknown`: anything else (a parameter, a call result). Not reported by itself, because we only report when we *saw* a dynamic construction (precision first, R-05).

The value domain is the **powerset** of the four kinds, plus sets of constructions and origins. That's a finite lattice ordered by ⊆, and join is union, which guarantees termination in §6.5.

```python
@dataclass(frozen=True, slots=True)
class SinkSpec:
    id: str                                  # "dbapi.execute"
    kind: Literal["sql", "shell", "html"]
    match: Literal["qualname", "method"]
    target: str                              # "os.system" or method name "execute"
    arg: int | None = 0                      # positional index of the string argument
    keywords: tuple[str, ...] = ()           # keyword names that may carry it instead
    require_kwargs: Mapping[str, bool] = field(default_factory=dict)   # {"shell": True}
    receiver_hint: tuple[str, ...] = ()      # regexes on the receiver's last name (method matches)
    rewrite: Literal["sql-params", "shell-argv", "html-escape", "none"] = "none"
    no_rewrite_reason: str | None = None     # e.g. "no-parameter-support"
    mvp: bool = True

@dataclass(frozen=True, slots=True)
class SinkMatch:
    spec: SinkSpec
    call: ast.Call
    arg_node: ast.expr
    strength: Literal["strong", "weak"]      # weak = receiver hint not matched / condition not constant
```

### 6.3 Sink catalogue

**Matching rules.**
- `qualname`: `ctx.qualified_name(call.func) == target` (C3 resolver, §6.3 there).
- `method`: `call.func` is `Attribute(attr=target)`. **Strength** is `strong` if any of these hold: the receiver's last identifier matches a `receiver_hint` regex (case-insensitive, full match); the receiver is a call ending in `.cursor()`; or the receiver is a local variable whose StrValue-independent *binding* (a separate tiny pass) is `X.cursor()`, `X.connect(...)` or `sqlite3.connect(...)`. Otherwise `weak`.
- The string argument is `call.args[arg]` if present and not `Starred`, else the first matching keyword in `keywords`. If neither is present, it's not a sink match.
- `require_kwargs`: each listed keyword must be present. If its value is a constant equal to the required value, the match stays strong. If it's a non-constant expression, the match becomes `weak` ("may be `shell=True`"). If it's a constant with a different value, or absent, there's no match.

| ID | Kind | Match | Target | Arg / keywords | Condition | Rewrite | MVP |
|---|---|---|---|---|---|---|---|
| `dbapi.execute` | sql | method | `execute` | 0 / `sql`, `query`, `operation` | hint `cur\w*\|cursor\|conn\w*\|connection\|db\|session\|engine` | sql-params | ✅ |
| `dbapi.executemany` | sql | method | `executemany` | 0 / same | same hint | none (`executemany`) | ✅ |
| `sqlite3.executescript` | sql | method | `executescript` | 0 / `sql_script` | same hint | none (`no-parameter-support`) | ✅ |
| `sqlalchemy.text` | sql | qualname | `sqlalchemy.text` (also `sqlalchemy.sql.text`, `sqlalchemy.sql.expression.text`) | 0 / `text` | — | none (stretch: `bindparams`) | — |
| `django.raw` | sql | method | `raw` | 0 / `raw_query` | receiver ends with `objects` or a name matching `\w*(objects\|manager)` (strong only; weak = no match) | none (stretch) | — |
| `django.RawSQL` | sql | qualname | `django.db.models.expressions.RawSQL` (also `django.db.models.RawSQL`) | 0 / `sql` | — | none (stretch) | — |
| `pandas.read_sql` | sql | qualname | `pandas.read_sql`, `pandas.read_sql_query` | 0 / `sql` | — | none | — |
| `os.system` | shell | qualname | `os.system` | 0 / `command` | — | shell-argv (§6.8.4) | ✅ |
| `os.popen` | shell | qualname | `os.popen` | 0 / `cmd` | — | none (`return-value-semantics`) | ✅ |
| `subprocess.shell` | shell | qualname | `subprocess.run`, `.call`, `.check_call`, `.check_output`, `.Popen` | 0 / `args` | `shell=True` | shell-argv | ✅ |
| `subprocess.getoutput` | shell | qualname | `subprocess.getoutput`, `subprocess.getstatusoutput` | 0 / `cmd` | — | none (`always-shell`) | — |
| `asyncio.shell` | shell | qualname | `asyncio.create_subprocess_shell` | 0 / `cmd` | — | none in MVP (stretch: `create_subprocess_exec(*argv(...))`) | ✅ (detect) |
| `markupsafe.Markup` | html | qualname | `markupsafe.Markup` | 0 / `object` | — | html-escape | ✅ |
| `django.mark_safe` | html | qualname | `django.utils.safestring.mark_safe` | 0 / `s` | — | html-escape | ✅ |
| `django.HttpResponse` | html | qualname | `django.http.HttpResponse` (also `django.http.response.HttpResponse`) | 0 / `content` | no `content_type` kw, or its constant value starts with `text/html` | html-escape | ✅ |
| `flask.render_template_string` | html | qualname | `flask.render_template_string` | 0 / `source` | — | none (`template-source`) | ✅ |
| `jinja2.Template` | html | qualname | `jinja2.Template` | 0 / `source` | — | none (`template-source`) | — |
| `flask.Response` | html | qualname | `flask.Response`, `flask.make_response` | 0 / `response` | no `mimetype`/`content_type` kw, or text/html | html-escape | — |

Notes:
- For `render_template_string` and `jinja2.Template`, the dynamic string is the **template source**. Injecting there is server-side template injection (SSTI): it can run code, not just inject markup. Values passed to `.render(**context)` are *not* a sink. The explanation text and the `injection-attacks` note cover SSTI.
- Keyword names above come from each API's documented signature. **The implementer must check each against the library's current docs in phase 1** and record any correction in the PR.
- Non-MVP rows are implemented in phase 8 (stretch). The catalogue code carries `mvp=False` and they're **disabled by default until implemented and tested**.

### 6.4 Recognising string constructions (`tstrings/strings.py`)

`eval_expr(expr, env, ctx) -> StrValue`:

| Expression | Result |
|---|---|
| `Constant(str)` | `{static}` |
| `Constant` int/float/bool/None | `{static}`, origin `numeric` (for confidence when interpolated) |
| `JoinedStr` (f-string) with **no** `FormattedValue` | `{static}` |
| `JoinedStr` with ≥ 1 `FormattedValue` | if every interpolated expression's value is `{static}` → `{static}`; else `{dynamic}`, construction `f-string`, origins = ∪ origins of interpolated values (and their constructions) |
| `TemplateStr` (3.14+; node name **Provisional, S-10**, looked up with `getattr(ast, "TemplateStr", None)`) | `{template}` |
| `BinOp(Mod)` whose left is `{static}` str | as for f-strings, construction `percent`, over the RHS (tuple elements, dict display values, or the single expression) |
| `Call(Attribute(value=V, attr="format"))` where V's value is exactly `{static}` | construction `format`, over args and keyword values |
| `BinOp(Add)` | flatten the `+` chain. If any operand has `dynamic`, or (at least one operand is `{static}` **and** at least one is not `{static}`) → `{dynamic}` (`concat`). If all are static → `{static}`. Otherwise the join of the operands |
| `Call(Attribute(value=V, attr="join"), args=[X])` with V `{static}` | if X is a list/tuple display of static values → `{static}`; else `{dynamic}` (`join`), origins from X |
| `Call(Attribute(value=V, attr=m))` with `m` in `strip`, `lstrip`, `rstrip`, `upper`, `lower`, `casefold`, `title`, `replace`, `removeprefix`, `removesuffix`, `format_map`(→ dynamic) | V's value (string-preserving methods) |
| `Name(id)` | `env[id]` if bound in the unit; else module-level UPPER_CASE name → `{unknown}` origin `constant`; else `{unknown}` origin `name` |
| `IfExp` | join of both branches |
| `Starred`, `Await`, `Lambda`, comprehensions | `{unknown}` |
| `Call` to `int`, `float`, `len`, `bool`, `round`, `abs` (builtins via qualnames) | `{unknown}` origin `numeric` |
| `Call` to `input`, or `Attribute`/`Subscript`/`Call` rooted at `sys.argv`, `os.environ`, or a name matching `untrusted-names` | `{unknown}` origin `untrusted` |
| other `Call` | `{unknown}` origin `call` (detail = dotted text of func) |
| other `Attribute` / `Subscript` | `{unknown}` origin `attribute` / `subscript`, inheriting the base's origins |
| bytes constants and `bytes` formatting | ignored (`{unknown}`, never reported; sinks take `str`) |

**f-string internals.** The planner needs the exact positions of `{`, `}`, conversions and format specs. On 3.12+ the tokenizer emits `FSTRING_START`, `FSTRING_MIDDLE` and `FSTRING_END` tokens, with `OP` tokens for the braces (PEP 701). `strings.fstring_fields(source, node)` re-tokenizes the node's source segment and returns, for each replacement field: brace positions, expression span, conversion char, format-spec span, and whether `=` (self-documenting) is used. **Provisional (S-10):** S-10 must confirm the token positions around escaped braces `{{`/`}}`, because those are known to be fiddly, and the tests include them.

### 6.5 Intra-procedural taint analysis (`tstrings/dataflow.py`)

**Analysis units.** Each `FunctionDef`/`AsyncFunctionDef`/`Lambda` body, the module body, and each class body is analysed separately, with a fresh environment. A nested function is its own unit, and any outer variable it reads is `{unknown}` with origin `name`.

**Environment.** `Env = Mapping[str, StrValue]` for **local simple names only**. Attributes (`self.q`) and subscripts aren't tracked: storing to them does nothing, and reading them gives `{unknown}`. Initial environment: each parameter → `{unknown}` with origin `parameter` (or `untrusted` if its name matches `untrusted-names`).

**Transfer functions** (`analyze(stmts, env) -> env'`), with sink checks run on every expression **before** the statement's own assignment takes effect:

| Statement | Effect |
|---|---|
| `x = e` / `x: T = e` | `env[x] = eval(e)` |
| `a, b = e1, e2` (tuple/list display of the same length, no starred) | pairwise |
| other destructuring (`a, b = f()`, starred) | each target `{unknown}`, origins = origins of `e` |
| `x += e` | `env[x] = concat(env[x], eval(e))`, construction `augmented-concat` if the result is dynamic |
| `(x := e)` inside any expression | `env[x] = eval(e)`, applied in left-to-right evaluation order within the statement |
| `del x` | remove `x` (BOTTOM) |
| `global x` / `nonlocal x` | `x` becomes `{unknown}` for the rest of the unit; stores ignored |
| `if`/`elif`/`else` | analyse each branch from `env`, then join the results |
| `match` | analyse each case from `env` (capture names → `{unknown}`, origins of subject), then join; plus `env` itself if there's no irrefutable case |
| `for t in it: body else: orelse` | loop fixpoint (below); `t` → `{unknown}` with origins of `it` (origin kind `loop` wrapping them) |
| `while c: body else: orelse` | loop fixpoint |
| `try: B except H: … else: E finally: F` | `env_B = analyze(B, env)`; each handler starts from `join(env, env_B)` (an exception may come at any point); `else` from `env_B`; `finally` from the join of all exits |
| `with e as x` | `x` → `{unknown}`, origins of `e`; then the body |
| `return` / `raise` | the path ends: result env is BOTTOM (neutral for join). **Returned values aren't followed** (NG4) |
| `break` / `continue` | treated as falling through: a sound over-approximation for a "may" analysis. It can only add facts, so it costs precision in odd code, never misses. Documented |
| nested `def` / `class` / `lambda` | bind the name to `{unknown}`; analysed as their own units |

**Loop fixpoint:**
```
def analyze_loop(body, orelse, env):
    head = env
    for i in range(MAX_LOOP_ITER := 50):
        after_body = analyze(body, head)
        new_head = head.join(after_body)        # join per variable
        if new_head == head: break
        head = new_head
    else:
        log.warning(...)  # never expected: lattice is finite; this is a bug guard
    return analyze(orelse, head).join(head)     # loop may run zero times
```
**Why it terminates:** each variable's value only grows (join is union) inside finite sets: 4 kinds, plus constructions and origins drawn from the finitely many nodes in the unit. So `head` can change only finitely often.

**Sink check.** For each `Call` reached during analysis, run the sink matcher (§6.3). On a match, evaluate the argument with the current env:
- `"dynamic" ∈ kinds` → a **finding** of the sink's kind (CRT501/502/503).
- `"template" ∈ kinds` and the argument is not wrapped by a recognised adapter call → **CRT504** ("Template passed to a `str` sink").
- The argument is `Starred(Call(f, [X]))` or `Call(f, [X])` where `f` resolves to a configured adapter (§8 `adapters`, or anything in `cartographer.adapters`) → safe. Nothing is reported (this is how idempotency works).

**CRT504 also triggers** on *flattening* a template value anywhere: `str(T)`, `format(T)`, `f"{T}"`, `"%s" % T`, `"…" + T`, `"".join(T)`, where `T`'s value has `template` (even with no sink).

**Worked example** (the walkthrough must show the env after each step):
```python
def search(conn, filters):                          # env: filters={unknown|param filters}
    q = "SELECT * FROM t WHERE 1=1"                 # q={static}
    for k, v in filters.items():                    # k,v={unknown|loop(param filters)}
        q += f" AND {k} = '{v}'"                    # q={dynamic|augcat,f-string}
    return conn.execute(q).fetchall()               # head after fixpoint: q={static,dynamic} → CRT501
```
Iteration 1: head q={static} → body gives {dynamic} → new head {static, dynamic}. Iteration 2: body from {static, dynamic} gives {dynamic} → head unchanged, so stop. At the sink, `dynamic ∈ kinds` gives CRT501 with confidence high (origin derives from parameter `filters`). The rewrite is refused with CRT505 `loop-concat`, and also `dynamic-identifier`, since `{k}` is a column name.

**Complexity:** O(S × L) per unit, where S is the number of statements and L the number of loop iterations until stable (small in practice, bounded by the lattice).

### 6.6 Confidence (`tstrings/confidence.py`)

Base level, from the origins of the interpolated values feeding the dynamic construction(s):
- **high**: any origin of kind `parameter` or `untrusted`, or a `loop` origin wrapping one of those.
- **medium**: otherwise, any origin of kind `call`, `attribute`, `subscript`, `name`, or `loop` (over those).
- **low**: only `numeric` and/or `constant` origins.

Then **downgrade one level** (high→medium→low; low stays low) if the sink match is `weak`. Findings below `min-confidence` (default `medium`) are dropped *before* filtering. The confidence and the reason for any downgrade go in `data`.

### 6.7 Diagnostics through the C3 engine (`tstrings/rules.py`)

```python
class _TStringRule(Rule, abstract=True):
    def end_file(self, ctx: RuleContext) -> None:
        analysis = ctx.shared.get("tstrings.analysis")
        if analysis is None:
            analysis = ctx.shared["tstrings.analysis"] = analyze_file(ctx)   # once per file
        for finding in analysis.findings_for(self.code):
            ctx.report(self, finding.node, finding.message, help=finding.help,
                       data=finding.data, related=finding.related)
            # (the Fix is attached by the planner via finding.fix)

class SqlInjectionRisk(_TStringRule, code="CRT501", name="sql-injection-risk"): ...
class ShellInjectionRisk(_TStringRule, code="CRT502", name="shell-injection-risk"): ...
class HtmlInjectionRisk(_TStringRule, code="CRT503", name="html-injection-risk"): ...
class TemplateFlattened(_TStringRule, code="CRT504", name="template-flattened"): ...
class NoSafeRewrite(_TStringRule, code="CRT505", name="no-safe-rewrite", severity=Severity.INFO): ...
```
Because these are C3 rules, `cartographer check` runs them too, and suppression comments, per-file ignores and severity overrides all apply. C3's `RuleContext.report` must accept an optional `fix: Fix | None` keyword. That is part of C3's API: if C3 shipped without it, adding it is a task in phase 4 here.

**Messages:**
- CRT501/502/503: ``{construction} reaches {SQL|shell|HTML} sink `{target}`[ via variable `{name}`] (confidence: {level}; value from {origin description})``. `construction` ∈ "f-string", "%-formatted string", "`.format()` string", "concatenated string", "joined string", "string built with `+=`". If there are several constructions, use the first by location and add "and N other places" to `related`. Origin description: ``parameter `uid` ``, `` `request.args.get(...)` ``, ``loop over `filters.items()` ``, and so on.
- CRT504: ``t-string `Template` is converted to `str` here, which removes its protection`` / ``t-string `Template` passed to `{target}`, which expects a `str`; wrap it with an adapter``.
- CRT505: ``no safe automatic rewrite: {reason text}`` (reasons in §6.8.6).

**`data` for CRT501–503:** `{"sink": "dbapi.execute", "kind": "sql", "construction": "f-string", "constructions": [{"kind", "path", "line", "column"}], "origins": [{"kind", "detail"}], "confidence": "high", "downgraded": null | "weak-sink-match" | "conditional-shell", "via_variable": "q" | null, "rewrite": "available" | "unavailable", "rewrite_safety": "safe" | "review" | null}`.
**CRT504:** `{"how": "str-call" | "format" | "f-string" | "percent" | "concat" | "join" | "sink", "sink": str | null}`.
**CRT505:** `{"reason": <reason id>, "sink": str, "detail": str}`.

**Help text for findings when `target-version < 3.14`:** ``t-strings need Python 3.14+ (target: {v}); use a parameterized query instead: `cur.execute("… = ?", (value,))` `` (SQL), `pass a list of arguments without shell=True` (shell), or `escape values with html.escape()` (HTML).

### 6.8 Rewrite planner (`tstrings/plan.py`, `tstrings/convert.py`)

The planner turns a finding into a `Fix` (02 §4.3): a list of `Edit`s plus `safety`. **Position edits are minimal**: we change only the characters that must change, which keeps comments and formatting intact.

#### 6.8.1 General rules
1. **Only when `target-version ≥ 3.14`.** Otherwise there are no fixes and no CRT505 for that reason (see §6.7 help).
2. **Prefix swap** for f-strings: in the literal's prefix, replace `f`→`t` and `F`→`T`, keeping `r`/`R` (`rf"…"` → `rt"…"`). That's one `Edit` per string part.
3. **Implicitly concatenated parts** (`f"a{x}" "b"`): every part becomes a t-string. Plain parts get the prefix `t` (`u` is replaced by `t`), and their `{`/`}` are doubled. Each part is edited separately, so comments between parts on different lines survive.
4. **Wrapping the sink argument:** insert `*{alias}(` before the argument and `)` after it (SQL), or `{alias}(` … `)` (HTML/shell).
5. **Adapter import:** `from {module} import {func}`, plus ` as {alias}` if the alias differs. Defaults: SQL `from cartographer.adapters.sql import {qmark|numeric|named|format_style|pyformat} as sql`, HTML `from cartographer.adapters.html import escape_html`, shell `from cartographer.adapters.shell import argv`. **Alias collision:** if the alias is bound or used anywhere in the file (as any `Name` id, or any binding in the qualnames pre-pass) and isn't already this exact import, try `{alias}_t`, then `{alias}_t2`, `{alias}_t3`, … The choice is computed **once per file** and shared by all its fixes.
6. **Import position:** after the last statement of the leading top-level import block (`import`, `from … import`, `lazy import`). The block starts after any module docstring and `from __future__` imports, and may contain blank lines and comments. If there's no import block: after the docstring, or after the shebang/encoding-cookie lines, or at line 1. The new line uses the file's newline style. If an identical import already exists at top level (outside `if TYPE_CHECKING:`), no edit is made.
7. **Expression text** inserted into generated t-strings (from `%`/`.format()`/`+` conversions) is the exact source segment. It's wrapped in parentheses unless the node is a `Name`, `Attribute`, `Constant`, `Subscript` or `Call`. A segment containing a newline or a comment token gives CRT505 `multi-line-source`.
8. **Every fix's edits are deduplicated per file** (identical `Edit`s merge, such as the shared import). If two fixes have **overlapping, non-identical** edits, the later one (by location) is skipped with an INFO log ("conflicting fix skipped; run again"). Running `fix` again picks it up.

#### 6.8.2 SQL: value positions, quotes, paramstyle
**Probe string.** Join the static parts, replacing interpolation *i* with the private-use character `U+E000 + i`. Lex it with `tstrings/sqllex.py`, which produces tokens `WS`, `LINE_COMMENT` (`--`…EOL), `BLOCK_COMMENT` (`/*…*/`), `STRING` (`'…'` with `''` escape), `QIDENT` (`"…"` with `""` escape, and `` `…` ``), `NUMBER`, `WORD` (`[A-Za-z_][A-Za-z0-9_$]*`), `PLACEHOLDER` (`?`, `?NNN`, `:name`, `$N`, `%s`, `%(name)s`), `SLOT` (private-use char) and `OP` (multi-char `<=`, `>=`, `<>`, `!=`, `||`, `::`; else one char).

**Slot context** for each interpolation:
| Context | Meaning | Outcome |
|---|---|---|
| `SLOT` token in normal context | bare | check value position |
| inside a `STRING` token whose text is exactly `'` + SLOT + `'` | whole quoted literal | **strip the quotes** (fix becomes `review`), then check value position |
| inside a `STRING` with other text (`'%{q}%'`) | quoted fragment | CRT505 `quoted-fragment` |
| inside `QIDENT` | quoted identifier | CRT505 `dynamic-identifier` |
| inside a comment | — | CRT505 `in-comment` |
| touching a `WORD`/`NUMBER` with no space (`tbl_{suffix}`) | identifier fragment | CRT505 `dynamic-identifier` |

**Value-position predicate.** Let `P` be the previous significant token (skipping `WS` and comments). The slot is in a **value position** iff:
- `P` is `OP` in `= < > <= >= <> != + - * / % ||`, or
- `P` is `WORD` (case-insensitive) in `LIKE ILIKE LIMIT OFFSET`, or
- `P` is `(` or `,` and the innermost open parenthesis is a **value list**: a `(` whose previous significant token is `VALUES` or `IN`, or a `(` preceded by `,` directly after a closed value-list group (multi-row `VALUES (…), (…)`).

Otherwise: if `P` is `WORD` in `FROM JOIN INTO UPDATE TABLE BY AS SELECT ON` → CRT505 `dynamic-identifier`, and the message names the keyword. For `BY`, it includes the previous word: "after ORDER BY". Anything else → CRT505 `not-value-position`.

**Other SQL refusals:** the static text already contains `PLACEHOLDER` tokens outside strings/comments → `existing-placeholders`. The sink call already passes a parameters argument (a second positional argument or a `parameters`/`params`/`vars` keyword) → `existing-parameters` (merging is a stretch). Any interpolation with a conversion (`!r`/`!s`/`!a`), a format spec, or `=` → `conversion-or-format-spec`.

**Paramstyle.** Config `tstring.paramstyle` (default `auto`). With `auto`, look at the file's top-level imported module names:
| Imported | Paramstyle | Adapter function |
|---|---|---|
| `sqlite3` | qmark | `qmark` |
| `psycopg`, `psycopg2`, `pymysql`, `MySQLdb`, `mysql.connector` | format (`%s`, positional) | `format_style` |
| `oracledb`, `cx_Oracle` | named | `named` |
| none of these, or more than one family | config fallback `qmark`, fix safety → `review`, summary note "paramstyle assumed" | — |

(The implementer verifies each driver's documented `paramstyle` and `%s` support in phase 4 and records the sources in the PR. Django's `raw()` uses `%s`, which matters for the stretch rewrite.)

**Before → after examples (each is a test):**
| Before | After | Safety |
|---|---|---|
| `cur.execute(f"SELECT * FROM t WHERE id = {uid}")` | `cur.execute(*sql(t"SELECT * FROM t WHERE id = {uid}"))` | safe |
| `cur.execute(f"… WHERE name = '{name}'")` | `cur.execute(*sql(t"… WHERE name = {name}"))` | review (quotes stripped) |
| `cur.execute(f"INSERT INTO t (a, b) VALUES ({a}, {b})")` | `cur.execute(*sql(t"INSERT INTO t (a, b) VALUES ({a}, {b})"))` | safe |
| `cur.execute(f"… WHERE id IN ({x})")` | rewrite: a single value in an `IN` list | safe |
| `cur.execute(f"SELECT * FROM {table}")` | CRT505 `dynamic-identifier` | — |
| `cur.execute(f"… LIKE '%{q}%'")` | CRT505 `quoted-fragment` (help: build `pattern = f"%{q}%"` in Python and interpolate `{pattern}`) | — |
| `cur.execute(f"… = {x!r}")` | CRT505 `conversion-or-format-spec` | — |
| `cur.executescript(f"…{x}")` | CRT505 `no-parameter-support` | — |

#### 6.8.3 HTML
- Check the slot contexts with `adapters/_htmlctx.py` (the same state machine as the adapter, §6.10.2). Interpolations are allowed only in `DATA`, `ATTR_DQ` and `ATTR_SQ`. Anything else → CRT505 `html-context`, with the context named (for example "unquoted attribute value").
- Conversions and format specs are allowed (the adapter applies them before escaping).
- Rewrite: `Markup(f"<b>{name}</b>")` → `Markup(escape_html(t"<b>{name}</b>"))`. The same applies to `mark_safe(...)` and `HttpResponse(...)`.
- Safety is always `review`: escaping changes output whenever a value was *intentionally* HTML (a pre-rendered fragment held in a plain `str`). Values with `__html__` (markupsafe's `Markup`) are passed through unescaped by the adapter, so already-safe markup stays intact.

#### 6.8.4 Shell
- Static text (outside quotes) containing any of `| & ; < > ( ) $ `` ` `` * ? [ ] { } ~`, a newline, or a leading `VAR=value` word → CRT505 `shell-operators`. An argument list can't express pipes, redirection, globbing or variables.
- `subprocess.run(f"tar -czf {dest} {src}", shell=True, check=True)` → `subprocess.run(argv(t"tar -czf {dest} {src}"), check=True)`. The `shell=True` keyword is removed by deleting the span from the end of the previous argument to the end of the keyword node (so `, shell=True` goes). If that span contains a comment → CRT505 `multi-line-source`.
- `os.system(f"rm -rf {path}")` **as an expression statement** → `subprocess.run(argv(t"rm -rf {path}"))`, adding `import subprocess` if `subprocess` isn't already bound to the module (if it's bound to something else → CRT505 `name-conflict`). If the return value is used (assigned, compared, returned) → CRT505 `return-value-used`, because `os.system` returns an exit status and `subprocess.run` returns a `CompletedProcess`.
- Safety is always `review` (argv execution differs subtly from a shell: empty arguments are kept, and there's no quote processing of values).

#### 6.8.5 Converting `%`, `.format()` and `+` (`tstrings/convert.py`): MVP, phase 5
These **generate** a new t-string literal that replaces the whole expression. The literal keeps the original's quote character, triple-quoting and raw-ness. If the source spans several lines with comments → CRT505 `multi-line-source`.

**`%` formatting** (`"…" % rhs`; the left side must be a str literal or an implicit concatenation of str literals, else CRT505 `unsupported-format-source`):
- Supported conversion specs: `%s`, `%r`, `%a`, `%d`, `%i`, each optionally with a mapping key `%(key)s`, plus `%%` → `%`. Flags, width, precision and length modifiers → CRT505 `unsupported-percent-code`.
- RHS: a **tuple display** maps elements in order (wrong count → CRT505 `percent-arity`). A **dict display** with constant string keys is needed for `%(key)` specs (`%(key)` with a non-display RHS → CRT505 `percent-dict-variable`). A **single non-tuple expression** is allowed for exactly one positional spec, and adds the review note "`% x` assumes `x` is not a tuple".
- `%s` → `{e}`, `%r` → `{e!r}`, `%a` → `{e!a}`. `%d`/`%i` → `{e}` for SQL with review note "integer formatting dropped; the value is bound as-is". For HTML/shell → CRT505 `unsupported-percent-code`. SQL then applies §6.8.2 (so `!r`/`!a` → CRT505 `conversion-or-format-spec`).
- Static text: `%%` → `%`. `{` → `{{` and `}` → `}}`.
- **Evaluation order:** a dict display evaluates its values once, left to right. The t-string evaluates them in *textual* order and once per use. If any value is used more than once, or in a different order, all of those values must be **simple** (`Name`, an `Attribute` chain on a `Name`, `Constant`, or a `Subscript` with constant index on a simple base). Otherwise → CRT505 `reordered-complex-argument`.

**`.format()`** (the receiver must be a str literal or an implicit concatenation of literals):
- Parse with `string.Formatter().parse()` (stdlib). For each field: `""` = automatic numbering, digits = index, an identifier = keyword argument; `.attr` chains are allowed (`{0.name}` → `{a.name}`); `[key]` → CRT505 `format-index-access`; mixing automatic and manual numbering → CRT505 `malformed`.
- `*args`/`**kwargs` in the call → CRT505 `star-args`. Nested fields in a format spec (`{0:{1}}`) → CRT505 `nested-format-spec`.
- Arguments referenced more than once, out of order, or unreferenced must be simple. Otherwise → CRT505 `reordered-complex-argument` / `unused-argument`.
- Conversion and format spec are preserved for HTML/shell. For SQL → CRT505 `conversion-or-format-spec`.

**`+` concatenation:**
- Flatten the `+` chain. String literals become static text (braces doubled). f-string operands are merged part by part. Every other operand becomes `{expr}`.
- An operand whose StrValue is `{static}` but which **isn't a literal** (for example `base = "SELECT …"; q = base + uid`) → CRT505 `static-fragment-variable`. Turning `base` into a parameter would break the query.

**Single-assignment forwarding** (all kinds; this is how `find_by_name` in §5.2 is fixed). When the sink argument is a `Name` `q`, rewrite via the variable iff, within the unit:
1. `q` has **exactly one** binding, a plain `Assign` (`q = <construction>`). An `AnnAssign` → CRT505 `annotated-variable` (its annotation would become wrong).
2. There are no other stores, `+=`, `del`, `global`/`nonlocal`, or walrus to `q`.
3. The assignment statement precedes the sink statement in the same statement list, or in a statement list that encloses it.
4. `q` is loaded **exactly once** (at the sink).

Then: rewrite the assignment's right-hand side into a t-string, and the sink argument `q` into `*sql(q)` / `escape_html(q)` / `argv(q)`. Violations → CRT505 `multi-assignment` / `variable-reused` / `loop-concat` (if any store is an `AugAssign` inside a loop).

**Always refused:** `str.join` constructions (`join`); constructions in a loop (`loop-concat`); `executemany` (`executemany`).

#### 6.8.6 CRT505 reasons (`data.reason` and message text)
| Reason id | Message text after "no safe automatic rewrite: " |
|---|---|
| `dynamic-identifier` | `` `{x}` is in an identifier position (after {KW}); parameters can only replace values `` |
| `not-value-position` | `` `{x}` is not in a position where a SQL value is expected `` |
| `quoted-fragment` | `` `{x}` is part of a larger quoted SQL string `` |
| `in-comment` | `` `{x}` is inside a SQL comment `` |
| `existing-placeholders` | `the query already contains parameter placeholders` |
| `existing-parameters` | `the call already passes query parameters` |
| `conversion-or-format-spec` | `` `{x}` uses a conversion or format spec, which a parameter cannot carry `` |
| `no-parameter-support` | `` `{sink}` cannot take parameters `` |
| `executemany` | `` `executemany` runs one query for many parameter rows; build the query from literals `` |
| `template-source` | `the string is a template *source*; pass values as template context instead` |
| `return-value-semantics` | `` `{sink}` returns a pipe; rewrite by hand with `subprocess.run(..., capture_output=True)` `` |
| `always-shell` | `` `{sink}` always uses a shell `` |
| `return-value-used` | `` the return value of `os.system` is used, and `subprocess.run` returns a different type `` |
| `shell-operators` | `the command uses shell features ({chars}) that an argument list cannot express` |
| `html-context` | `` `{x}` is in an HTML context escaping cannot protect ({context}) `` |
| `unsupported-format-source` / `unsupported-percent-code` / `percent-arity` / `percent-dict-variable` / `format-index-access` / `star-args` / `nested-format-spec` / `malformed` | `this formatting form cannot be converted automatically ({detail})` |
| `reordered-complex-argument` / `unused-argument` | `converting would change how many times or in what order {expr} is evaluated` |
| `static-fragment-variable` | `` part of the SQL text comes from variable `{name}`; it must stay text, not become a parameter `` |
| `multi-assignment` / `variable-reused` / `annotated-variable` / `loop-concat` / `join` | `the string is assembled in several steps ({detail})` |
| `multi-line-source` | `the expression spans lines with comments that a rewrite would lose` |
| `name-conflict` | `` the name `{name}` needed by the rewrite is already used for something else `` |

#### 6.8.7 Fix safety summary
| Situation | Safety |
|---|---|
| SQL, paramstyle detected, no quotes stripped, no review notes | `safe` |
| SQL with stripped quotes, assumed paramstyle, `%d` dropped, or `% x` single RHS | `review` |
| HTML, shell | `review` |
| Forwarded variable | the underlying fix's safety |

#### 6.8.8 Adapter modes: `import` vs `vendor` (MVP, phase 5)
**`import` (default).** The planner emits the import line from §6.8.1 rule 5. The fix summary prints the runtime-dependency note (§5.2).

**`vendor`.** The goal: rewritten code works in a project that does *not* have Cartographer installed.
1. **Constraint on our adapters** (enforced by T-C5-55): `cartographer/adapters/*.py` import **only** the stdlib and each other through *relative* imports (`from ._htmlctx import …`). So the whole directory can be copied anywhere and still work.
2. **Where it goes:** for a file with module name `top.sub.mod` (C1 module index), the vendored package is `<source root>/top/_cartographer_adapters/`, and the import becomes `from top._cartographer_adapters.sql import qmark as sql`. For a file without a module name (a loose script), the package goes next to the file and the import is `from _cartographer_adapters.sql import qmark as sql`. Config `tstring.vendor-package` (default `"auto"`) can name a dotted package instead (it must be inside the project).
3. **What is copied:** every `*.py` file of `cartographer.adapters`, read with `importlib.resources.files("cartographer.adapters")` (so it works from a wheel). Each copy gets a header:
   ```python
   # Vendored from cartographer-py X.Y.Z (MIT licence) by `cartographer tstring fix --adapter-mode vendor`.
   # Do not edit: re-run the command to update. Original: cartographer/adapters/<name>.py
   ```
4. **New files aren't `Edit`s.** `Edit` only changes existing files (02 §4.3), so vendoring is a separate **vendor step** of the `fix` command, which runs before the edits. With `--diff`, each new or changed vendored file is shown as a unified diff from `/dev/null` (or the old copy). With `--write`, the files are written atomically (§6.9 step 5).
5. **Existing copy:** identical bytes → nothing to do. Different (an older Cartographer version, or hand-edited) → the diff shows the update, and the fix becomes `review`.
6. **Idempotency:** a second run finds the imports and identical vendored files, so the diff is empty (T-C5-53).
7. **Licence note:** the vendored header keeps the MIT notice, which is what the licence requires. The FAQ entry "Can I vendor the adapters?" explains this.

### 6.9 Applying fixes

**Text backend (`tstrings/apply_text.py`), MVP, phase 4.**
1. Read **bytes**. Detect the encoding with `tokenize.detect_encoding` (keeping a BOM as `utf-8-sig`). Decode **without** newline translation. Detect the newline style (`\r\n` if the first line ending is `\r\n`, else `\n`).
2. Convert `Edit` positions (1-based line, 1-based character column; D-018) to string offsets using a line-start table.
3. Apply edits in **descending** offset order. Overlaps are impossible after §6.8.1 rule 8. If one occurs anyway, it's a bug → `AnalysisError`.
4. Validate (below). If validation fails, nothing is written for that file.
5. For `--write`: encode with the original encoding, write `<name>.cartographer-tmp` in the same directory, copy the mode bits (`shutil.copymode`), then `os.replace` (atomic on Windows and POSIX).

**LibCST backend (`tstrings/apply_libcst.py`), phase 6. Provisional (S-03).** If S-03 confirms LibCST can parse and emit t-strings on the running interpreter, implement the same transformations as a `libcst.CSTTransformer`: locate nodes by position metadata (`PositionProvider`; **S-03 must record whether its columns are 0- or 1-based and in what units**), replace the string node, wrap the argument, and insert the import as a CST statement. **Differential test (T-C5-41):** for every fixture, the text backend and the LibCST backend must produce **byte-identical** output. If S-03 is negative, `--backend libcst` is a `UsageError` ("LibCST X.Y cannot emit t-strings; see docs/learn/spikes/S-03…"), and the `cst-and-codemods` note still teaches LibCST using an f-string-only codemod example.

**Validation (`tstrings/validate.py`):**
1. `ast.parse(new_text)` succeeds (needs ≥ 3.14).
2. **Untouched statements are unchanged:** for top-level statements whose source span contains no edit, `ast.dump(stmt, include_attributes=False)` is equal between old and new, in order. The inserted import statements are excluded.
3. **Idempotency:** re-running the finder on the new text yields no CRT501–503 at any rewritten sink, and `plan()` on the new text yields no fixes for those locations.
If any check fails, log an ERROR with details, skip the file, and continue. At the end, exit **3** with "internal error: rewrite validation failed for N file(s); they were not modified". That's a bug, by definition.

**Diff output (`--diff`).** `difflib.unified_diff(n=3)` per changed file, sorted by path, with headers `--- a/<relpath>` and `+++ b/<relpath>`. Lines are compared with line endings stripped and printed with `\n`.

### 6.10 Reference adapters (`cartographer.adapters`, Python 3.14+)

All three modules start with this, which keeps `src/` valid 3.13 syntax (D-005) and keeps mypy checking the code below when run with `python_version ≥ 3.14`:
```python
import sys
if sys.version_info < (3, 14):
    raise ImportError("cartographer.adapters needs Python 3.14+ (PEP 750 template strings)")
from string.templatelib import Interpolation, Template
```
Adapters take a `Template` and iterate over it. Iterating yields the static `str` parts and the `Interpolation` objects in order, skipping empty strings. **Provisional (S-10):** confirm the iteration behaviour and the attribute names `value`, `expression`, `conversion`, `format_spec`. Adapters never contain t-string *literals*. Tests (in `*_py314.py` files, §10) do.

#### 6.10.1 `adapters/sql.py`
```python
type Paramstyle = Literal["qmark", "numeric", "named", "format", "pyformat"]
def dbapi(template: Template, paramstyle: Paramstyle = "qmark") -> tuple[str, tuple[object, ...] | dict[str, object]]
def qmark(template: Template) -> tuple[str, tuple[object, ...]]          # ?          (sqlite3)
def numeric(template: Template) -> tuple[str, tuple[object, ...]]        # :1, :2
def named(template: Template) -> tuple[str, dict[str, object]]           # :p1, :p2
def format_style(template: Template) -> tuple[str, tuple[object, ...]]   # %s         (named format_style: `format` would shadow the builtin)
def pyformat(template: Template) -> tuple[str, dict[str, object]]        # %(p1)s
```
Semantics:
1. Walk the parts in order. **Static text is copied verbatim.** It's developer-written literal text, so it's trusted. For `format` and `pyformat`, every `%` in static text becomes `%%` (those drivers treat `%` specially anywhere in the query).
2. For each `Interpolation`: if `conversion is not None` or `format_spec != ""`, raise `ValueError(f"SQL interpolation {{{expression}}} cannot use a conversion or format spec; pass the raw value")`. If `value` is itself a `Template`, **inline it recursively** (its static text is trusted too; depth ≤ 32, else `ValueError`). This allows composing `t"SELECT … WHERE {cond}"` with `cond = t"a = {x}"`. Otherwise emit the placeholder and append the value to the parameters: n-th parameter → `?` / `:n` / `:pn` / `%s` / `%(pn)s` (n is 1-based).
3. Return `(query, params)`: a tuple for positional styles, a dict for named styles.

```pycon
>>> uid, name = 7, "O'Brien"                                   # Python 3.14+
>>> qmark(t"SELECT * FROM users WHERE id = {uid} AND name = {name}")
('SELECT * FROM users WHERE id = ? AND name = ?', (7, "O'Brien"))
>>> named(t"SELECT * FROM users WHERE id = {uid}")
('SELECT * FROM users WHERE id = :p1', {'p1': 7})
>>> format_style(t"SELECT '100%' AS pct, {uid} AS id")
("SELECT '100%%' AS pct, %s AS id", (7,))
```

#### 6.10.2 `adapters/html.py`
```python
def escape_html(template: Template) -> str
```
1. Track the HTML **context** across static text with `adapters/_htmlctx.py`'s state machine: `DATA`, `TAG` (inside `<name …` before `>`), `ATTR_DQ`/`ATTR_SQ` (inside a double/single-quoted attribute value), `ATTR_UNQUOTED` (after `=` inside a tag with no quote), `COMMENT` (`<!-- … -->`), `RAWTEXT` (inside `<script>`/`<style>`, case-insensitive). Interpolated values don't change the context: they're escaped, so they can't contain `<`, `"` or `'`.
2. For an interpolation in `DATA`, `ATTR_DQ` or `ATTR_SQ`: let `v = value`. If `conversion is None`, `format_spec == ""`, and `v` has a callable `__html__`, emit `v.__html__()` unescaped (markupsafe's protocol for already-safe markup). Otherwise apply the conversion (`!r` → `repr`, `!s` → `str`, `!a` → `ascii`), then `format(v, format_spec)`, then `html.escape(text, quote=True)`, which escapes `& < > " '`.
3. In any other context, raise `ValueError` naming the expression and the context, e.g. ``"{url}" is in an unquoted attribute value; add quotes around it``. `href`/`src` URL schemes such as `javascript:` are **not** checked: documented as a limitation (escaping can't make a URL safe).

```pycon
>>> name, tip = "<script>", "it's"                           # Python 3.14+
>>> escape_html(t"<p title='{tip}'>{name}</p>")
"<p title='it&#x27;s'>&lt;script&gt;</p>"
```

#### 6.10.3 `adapters/shell.py`
```python
def argv(template: Template) -> list[str]
```
1. Build a probe string from the static text, with each interpolation *i* replaced by the private-use character `U+E000 + i`. If the static text already contains a character in `U+E000–U+F8FF`, raise `ValueError`.
2. Reject unquoted shell syntax in static text: scan with quote tracking. Unquoted `| & ; < > ( ) $ `` ` `` * ? [ ] { } ~` or a newline raise ``ValueError("shell syntax '|' is not supported by argv(); use subprocess pipes or Python instead")``.
3. `shlex.split(probe, posix=True)` splits the *static* structure into words. This uses POSIX rules on every OS, which is documented (on Windows, `subprocess` re-joins the list with `list2cmdline`, so the list is still the right structure).
4. In each word, replace each private-use char with `format(convert(value), format_spec)`. **Because values are substituted after splitting, their spaces, quotes and metacharacters can never change the number or boundaries of arguments.** A `list`/`tuple`/`set` value raises `ValueError` ("pass each argument as its own interpolation").

```pycon
>>> dest, src = "my archive.tgz", "a; rm -rf /"              # Python 3.14+
>>> argv(t"tar -czf {dest} {src}")
['tar', '-czf', 'my archive.tgz', 'a; rm -rf /']
>>> d = "x y"
>>> argv(t"cp --target={d} file")
['cp', '--target=x y', 'file']
```

### 6.11 Processor verifier (`tstrings/verifier/`), phase 7: MVP (★)

**Building templates without literals.** Strategies build `Template` objects with the constructor `Template(*parts)`, where parts are `str` and `Interpolation(value, expression, conversion, format_spec)`. **Provisional (S-10):** confirm the constructor signatures on 3.14/3.15. This is what keeps `src/` free of t-string literals.

**Skeleton strategies (`strategies.py`)**, one grammar per kind. A *skeleton* is the list of static parts plus slot markers; values are drawn separately.

- **SQL.** The fixed schema matches the execution database: `t(a TEXT, b INTEGER, c REAL)` plus `canary(x TEXT)` with one row.
  ```
  query := "SELECT a FROM t" [" WHERE " cond (" AND " cond)*] [" LIMIT " SLOT]
         | "INSERT INTO t (" cols ") VALUES (" SLOT ("," SLOT)* ")"       # #slots == #cols
         | "UPDATE t SET " col " = " SLOT [" WHERE " cond]
  cond  := col op SLOT | col " LIKE " SLOT | col " IN (" SLOT ("," SLOT)* ")"
  op    := "=" | "<" | ">" | "<=" | ">=" | "<>"
  ```
  Values: `text()` biased with an adversarial list (`'`, `''`, `'; DROP TABLE t; --`, `" OR 1=1 --`, `%s`, `?`, `:p1`, `\x00`-free control characters, long strings, emoji), plus integers, finite floats and `None`. `LIMIT` slots get non-negative integers.
- **HTML.** Depth ≤ 3: elements from `{p, b, i, a, div, span, ul, li}` with optional double- or single-quoted attributes from `{title, class, id, href}`, and slots only in text content and **quoted** attribute values. No `<script>`/`<style>`. Values: text including `<`, `>`, `&`, `"`, `'`, `</b>`, `<!--`, `<script>alert(1)</script>`, `" onmouseover="x`, entities like `&amp;`, plus integers.
- **Shell.** 1–6 words. Each word is a static word from `[a-z0-9_./=-]+`, a whole `SLOT`, `--opt=` + `SLOT`, or `'` + `SLOT` + `'`. Values: text including spaces, quotes, `$(id)`, `` `id` ``, `;`, `|`, `&&`, newlines, `*`, `~`, `-rf`, the empty string and unicode (no NUL).

**Benign assignment:** for slot *i*, the benign value is `"x"` for HTML/SQL text slots (`0` for integer-only slots), and `f"x{i}"` for shell (unique, so positions can be identified).

**Properties (`properties.py`)**: each raises `PropertyViolation(property_id, skeleton, values, expected, actual)` on failure.

| ID | Kind | Property (for all skeletons S and value assignments V) |
|---|---|---|
| P-SQL-1 | sql | `proc(S(V)).query == proc(S(V_benign)).query`: the query text doesn't depend on values |
| P-SQL-2 | sql | the parameters, in placeholder order (tuple order, or dict values ordered by placeholder occurrence), are exactly `V` (compared with `==` and the same type) |
| P-SQL-3 | sql | the number of `PLACEHOLDER` tokens (via `sqllex`, outside strings/comments) equals the number of slots |
| P-SQL-4 | sql | for paramstyles sqlite3 supports (**qmark, named**): executing against a fresh in-memory database raises no `sqlite3.Error`; the `canary` table still has exactly one row and table `t` still exists; for `INSERT` skeletons, reading the row back returns exactly the inserted values. Other paramstyles → `skipped` |
| P-HTML-1 | html | the **skeleton event sequence** of `proc(S(V))` equals that of `proc(S(V_benign))`. Events come from an `html.parser.HTMLParser` subclass (`convert_charrefs=True`): `("start", tag, sorted attribute names)`, `("end", tag)`, `("startend", …)`, `("data",)` (consecutive data merged), `("comment",)`, `("decl",)`, `("pi",)` |
| P-HTML-2 | html | for each slot in text content, the parser's (unescaped) data at that position equals `format(value)`: the value survives as data |
| P-SH-1 | shell | `len(argv(S(V))) == len(argv(S(V_benign)))`, where a `str` result is first split with `shlex.split` (and a `ValueError` from splitting is a failure) |
| P-SH-2 | shell | for each slot *i*, the element containing `x{i}` in the benign run, with `x{i}` replaced by `format(V[i])`, equals the element at the same index in the real run |

**Paramstyle detection** (when `--paramstyle auto`): run the processor once on a fixed one-slot skeleton with a benign value and look at the query: `?` → qmark, `:1` → numeric, `:<name>` + dict → named, `%s` + tuple → format, `%(<name>)s` + dict → pyformat. Otherwise `unknown`, and P-SQL-4 is skipped.

**Result-type checks:** SQL processors must return a 2-tuple `(str, tuple|list|dict)`, HTML processors a `str`, shell processors a `list[str]` or `str`. A mismatch on the first call is a `UsageError` (exit 2): "processor returned `X`; for --kind sql it must return `(query, params)`". S-05 documents small wrapper functions for third-party processors with other shapes.

**Runner (`runner.py`).** For each property: `@given(skeleton_and_values())` + `@settings(max_examples=N, database=None, deadline=None, derandomize=False, verbosity=Verbosity.quiet, suppress_health_check=[HealthCheck.too_slow])` + `@seed(S)`. Call it, and catch `PropertyViolation`: Hypothesis re-raises the **shrunk** (minimal) failing example's exception. Each property runs independently, so one failure doesn't hide others. An exception other than `PropertyViolation` raised *by the processor* also counts as a failure of the property being checked, with `actual = "raised ValueError: …"`.

**CRT506** (error): one per failed property. Location: the processor's definition (`inspect.getsourcefile` + `inspect.getsourcelines`). The path is relative to `PATH` if the file is inside it, else its absolute posix path. Message: ``processor `{spec}` failed {P-ID}: {property description}``. Help: the counterexample (template parts as a tuple, with slots shown as `{v0}`, the values reprs truncated to 200 characters, expected vs actual). `data`: `{"processor", "property", "skeleton", "values", "expected", "actual", "seed", "examples"}`.

**Payload** (`cartographer.tstring.verify/1`): `{"processor", "kind", "paramstyle", "examples", "seed", "properties": [{"id", "description", "status": "passed" | "failed" | "skipped", "reason": str | null, "counterexample": {...} | null}]}`.

**Broken fixtures** (`tests/fixtures/processors/broken.py`, our own code, runnable only on 3.14+):
- `naive_sql(t)`: concatenates static text with `'` + `str(value)` + `'` and returns `(query, ())`. It must fail P-SQL-1, 2 and 3.
- `naive_html(t)`: concatenates without escaping. It must fail P-HTML-1.
- `naive_shell(t)`: `" ".join(...)` of static text and `str(value)`, returning a `str`. It must fail P-SH-1.
- `almost_html(t)`: escapes `<` and `>` but not quotes. It must fail P-HTML-1 for quoted-attribute slots. This is the subtle one, proving the verifier finds non-obvious bugs.

### 6.12 Version gating summary
| Feature | 3.13 | 3.14+ |
|---|---|---|
| `tstring find` | ✅ (files containing t-strings → CRT001 with a hint) | ✅ |
| fixes computed (shown in JSON) | ✅ (unvalidated) | ✅ |
| `tstring fix` | exit 4 (needs a 3.14 parser to validate) | ✅ (needs target ≥ 3.14) |
| `import cartographer.adapters.*` | `ImportError` with a clear message | ✅ |
| `tstring verify` | exit 4 | ✅ with `[verify]` extra |
| Tests containing t-string literals | **not collected**: files named `test_*_py314.py`, excluded by `conftest.py` with `collect_ignore_glob` when `sys.version_info < (3, 14)`. A marker can't help, because the file wouldn't even parse | ✅ |

## 7. Diagnostics

| Code | Name | Default | Trigger | `data` |
|---|---|---|---|---|
| CRT501 | `sql-injection-risk` | warning | §6.5 sink check, kind sql | §6.7 |
| CRT502 | `shell-injection-risk` | warning | kind shell | §6.7 |
| CRT503 | `html-injection-risk` | warning | kind html | §6.7 |
| CRT504 | `template-flattened` | warning | §6.5 | `how`, `sink` |
| CRT505 | `no-safe-rewrite` | info | §6.8 refusals (at the sink argument) | `reason`, `sink`, `detail` |
| CRT506 | `processor-verification-failed` | error | §6.11 | §6.11 |

## 8. Configuration

```toml
[tool.cartographer.tstring]
min-confidence  = "medium"            # "low" | "medium" | "high"
adapter-mode    = "import"            # "import" | "vendor" (§6.8.8)
vendor-package  = "auto"              # "auto" | dotted package inside the project (vendor mode only)
untrusted-names = ["request", "req", "args", "form", "params", "query", "body", "payload", "user_input"]
paramstyle      = "auto"              # "auto" | "qmark" | "numeric" | "named" | "format" | "pyformat"
disable-sinks   = []                  # sink ids from §6.3
fallback-paramstyle = "qmark"         # used when auto-detection fails (fix becomes "review")

[tool.cartographer.tstring.adapters]  # "module:function"; "auto" = the cartographer.adapters default for that kind
sql   = "auto"                        # auto → cartographer.adapters.sql:<paramstyle function>
html  = "auto"                        # auto → cartographer.adapters.html:escape_html
shell = "auto"                        # auto → cartographer.adapters.shell:argv

[tool.cartographer.tstring.alias]     # preferred local names (collisions handled per §6.8.1)
sql = "sql"
html = "escape_html"
shell = "argv"

[[tool.cartographer.tstring.extend-sinks]]   # zero or more
id = "myorm.raw"
kind = "sql"                          # "sql" | "shell" | "html"
match = "qualname"                    # "qualname" | "method"
target = "myorm.db.raw"
arg = 0                               # int or omitted
keywords = ["query"]
require-kwargs = {}                   # e.g. { shell = true }
receiver-hint = []                    # regexes (method matches only)
rewrite = "none"                      # "sql-params" | "shell-argv" | "html-escape" | "none"
```
Validation: unknown sink ids in `disable-sinks` → `ConfigError` with suggestions. An `extend-sinks` entry with `rewrite = "sql-params"` but `kind = "html"` → `ConfigError`. Duplicate ids → `ConfigError`. A configured adapter `"module:function"` is *not* imported during `find`/`fix` (it's just text in the generated import). Only `verify` imports anything.

## 9. Phases & tasks

**MVP:** phases 1–7 and 9. Phase 8 is the stretch list (R-02).

### Phase 1: Finder: sinks and direct constructions (`c5/finder`)
- [ ] **Spike S-03** (LibCST: version, wheels for 3.13–3.15t on Windows, t-string and `lazy import` parse/emit, position units) → `docs/learn/spikes/S-03-libcst.md`.
- [ ] **Spike S-10** (`ast.TemplateStr`/`Interpolation` node names and fields; `tokenize` f-string/t-string token positions incl. `{{`/`}}`; `Template`/`Interpolation` constructors and iteration; 3.13 `SyntaxError` text for t-strings) → `docs/learn/spikes/S-10-ast-shapes.md`. Update §6.4/§6.10/§6.11 if needed.
- [ ] Concept notes `string-formatting` and `injection-attacks` (demos use in-memory `sqlite3`, `shlex` and `html.parser` only; nothing is ever executed in a real shell).
- [ ] `tstrings/model.py`, `sinks.py` (MVP rows; verify keyword names against docs), `strings.py`.
- [ ] `tstrings/rules.py` (CRT501–503 for *direct* sink arguments, without variables yet), `tstring find`, fixture `tstring_basic` (line 6 only at this stage).
- [ ] 🖐 Write `sinks.match_call()` for the `qualname` case yourself.
- [ ] Tests T-C5-01…08.

### Phase 2: Dataflow and confidence (`c5/dataflow`)
- [ ] Concept notes `dataflow-and-taint` (with the env-table walkthrough of §6.5's example) and `literal-string`.
- [ ] `tstrings/dataflow.py`, `confidence.py`. CRT504; CRT505 for refusals known without planning (`no-parameter-support`, `template-source`, `executemany`, `always-shell`, `return-value-semantics`).
- [ ] `tstring_basic` golden for `find`, without the line-16 CRT505 (that needs the planner; the golden is completed in phase 4).
- [ ] Tests T-C5-09…17, T-C5-56.

### Phase 3: Reference adapters (`c5/adapters`)
- [ ] Concept notes `template-strings` (writing a processor from scratch) and `dbapi-and-paramstyles` (all five styles, demonstrated with `sqlite3` where possible).
- [ ] `adapters/sql.py`, `adapters/html.py`, `adapters/shell.py`, `adapters/_htmlctx.py`.
- [ ] `conftest.py` collection gating for `*_py314.py` files.
- [ ] 🖐 Implement `argv()` from the §6.10.3 description before reading the implementer's tests.
- [ ] Tests T-C5-19…25.

### Phase 4: Planner and text backend for f-strings (`c5/fix`)
- [ ] **Spike S-05** (sql-tstring, tdom, tstr: existence, APIs, `Template` support) → `docs/learn/spikes/S-05-tstring-processors.md`. Add configuration examples for any that exist to the `template-strings` note. (Integration is phase 8.)
- [ ] Concept note `cst-and-codemods` (first part: AST vs CST, why minimal text edits preserve formatting).
- [ ] `tstrings/sqllex.py`, `plan.py` (§6.8.1–6.8.4, §6.8.6 refusals, forwarding), `apply_text.py`, `validate.py`.
- [ ] Add `fix` to C3's `ctx.report` if missing (§6.7).
- [ ] `tstring fix --diff/--write/--unsafe-fixes`. Goldens for `tstring_basic` (the f-string parts), `tstring_shell`, `tstring_html`. Complete the `find` golden for `tstring_basic` (T-C5-18) now that the planner emits CRT505.
- [ ] Tests T-C5-18, T-C5-26…34.

### Phase 5: Converting `%`, `.format()` and `+` (`c5/convert`)
- [ ] `tstrings/convert.py` (§6.8.5). Fixture `tstring_convert` covering every row of §6.8.5 and every refusal reason.
- [ ] Full `tstring_basic` fix golden (§5.2), including the runtime-dependency note in the stderr summary.
- [ ] Adapter modes (§6.8.8): `--adapter-mode`, the vendor step, the relative-imports constraint test. Golden `tstring_basic` with `--adapter-mode vendor`.
- [ ] Extend `string-formatting` with "converting between styles".
- [ ] Tests T-C5-35…40, T-C5-53, T-C5-55.

### Phase 6: LibCST backend (`c5/libcst`)
- [ ] If S-03 is positive: `apply_libcst.py` and the differential test T-C5-41. If negative: the `UsageError` path, plus a written explanation in the S-03 note and the `cst-and-codemods` note.
- [ ] Finish `cst-and-codemods` (LibCST transformer walk-through).
- [ ] Tests T-C5-41…42.

### Phase 7: Processor verifier ★ (`c5/verifier`)
- [ ] Concept note `structure-preservation` (properties as security specifications; testing vs proof; shrinking a counterexample).
- [ ] `tstrings/verifier/*` (including `_preload.py` and the import order of §5.3); the `verify` command; optional extra `[verify]` in `pyproject.toml` (D-035).
- [ ] `tests/fixtures/processors/broken.py` with the four broken processors and a README.
- [ ] Run the verifier on our three adapters with `--examples 5000` once, and record the run time in the write-up.
- [ ] Tests T-C5-43…50, T-C5-54.

### Phase 8: Stretch (`c5/stretch-*`, each its own PR, all optional)
- [ ] Non-MVP sinks in §6.3 (detection + tests).
- [ ] Third-party adapters from S-05 (`tstring.adapters.sql = "sql_tstring:…"`) with verifier runs against them.
- [ ] `asyncio.create_subprocess_shell` → `create_subprocess_exec(*argv(...))`.
- [ ] Classic parameterised rewrite for targets < 3.14.
- [ ] `IN`-list expansion helper (`{ids:in}`-style or an adapter function).
- [ ] Merging with existing parameters (`existing-parameters`).
- [ ] Flask view-return HTML sinks; `string.Template` sources.
- [ ] ~~Vendor mode~~: promoted to the MVP (phase 5, §6.8.8) after the cross-spec review.

### Phase 9: Acceptance and docs (`c5/acceptance`)
- [ ] Corpus (S-07: PyGoat or DVPWA, plus at least one real non-training repo): run `find`, triage, run `fix --diff`, review the diffs.
- [ ] Performance: `tstring find` on 2,000 files < 10 s (05 §6).
- [ ] Walkthrough, write-up, comparison. Version 0.5.0, changelog.

## 10. Test plan

| ID | Test |
|---|---|
| T-C5-01 | Every MVP sink row matches its positive example and rejects its near-miss (e.g. `subprocess.run(f"…")` without `shell=True`, `subprocess.run([…], shell=True)` with a list, `logging.info(f"…")`) |
| T-C5-02 | Method-sink strength: receiver-hint match, `.cursor()` receiver, local cursor binding → strong; unrelated receiver → weak (downgraded) |
| T-C5-03 | `shell=flag` (non-constant) → weak/conditional; `shell=False` → no match |
| T-C5-04 | Keyword-argument sinks (`execute(sql=f"…")`, `HttpResponse(content=f"…")`) |
| T-C5-05 | `HttpResponse(..., content_type="application/json")` is not a sink |
| T-C5-06 | Construction recognition: every row of the §6.4 table |
| T-C5-07 | f-string internals via tokenize: brace positions, conversions, specs, `=`, nested f-strings, escaped braces `{{ }}`, triple-quoted, raw (`rf`), multi-line |
| T-C5-08 | Static f-strings (`f"SELECT 1"`) and f-strings interpolating only static locals are not dynamic |
| T-C5-09 | Flow-sensitivity: reassignment from static to dynamic and back |
| T-C5-10 | Branch join (`if/else`, `match`), `try/except/finally` env rules |
| T-C5-11 | Loop fixpoint: the §6.5 worked example gives the stated env per iteration |
| T-C5-12 | Destructuring, walrus, `del`, `global`/`nonlocal`, `with … as` |
| T-C5-13 | Nested functions/lambdas/classes are separate units; closure reads are unknown |
| T-C5-14 | Property: analysis terminates and is deterministic on randomly generated straight-line/branch/loop programs over a small grammar (Hypothesis), with ≤ 50 iterations per loop |
| T-C5-15 | Property (monotonicity): adding a dynamic assignment anywhere before a sink never removes a finding |
| T-C5-16 | Confidence levels and downgrades for every origin kind; `min-confidence` filtering |
| T-C5-17 | CRT504: each flattening form; a Template passed directly to a sink; an adapter-wrapped argument is not flagged |
| T-C5-18 | Golden: `find` on `tstring_basic` (text/json/sarif), exactly §5.1 |
| T-C5-19 | `sql` adapters: all five paramstyles; `%` doubling for format/pyformat; nested Template inlining; depth limit; conversion/spec `ValueError` (`_py314`) |
| T-C5-20 | Property: for random skeletons/values, `qmark` output executes in sqlite3 and returns injected payloads as data (`_py314`) |
| T-C5-21 | `escape_html`: contexts (every state), `__html__` passthrough, conversions/specs, `ValueError` messages (`_py314`) |
| T-C5-22 | `htmlctx` state machine on edge inputs: `<a title="x>y">`, `<!-- <b> -->`, `<SCRIPT>`, self-closing tags, `>` inside quotes |
| T-C5-23 | `argv`: word gluing (`--x={v}`), quoted slots, empty values, unicode, private-use chars in static text, list values, every rejected shell character (`_py314`) |
| T-C5-24 | On 3.13: importing `cartographer.adapters.sql` raises `ImportError` with the documented message |
| T-C5-25 | `conftest` gating: on 3.13, `*_py314.py` files aren't collected (meta-test checking pytest's collected node ids) |
| T-C5-26 | `sqllex`: tokens for strings with `''`, quoted identifiers, comments, placeholders, slots |
| T-C5-27 | Value-position predicate: each row of §6.8.2, incl. multi-row `VALUES`, `IN`, `LIMIT`, `ORDER BY`, `FROM`, `tbl_{x}` |
| T-C5-28 | SQL before → after table (§6.8.2), each row exactly |
| T-C5-29 | Paramstyle detection per driver import; ambiguous → review with the assumed style |
| T-C5-30 | Import insertion: after docstring/`__future__`/import block/shebang/encoding cookie; no-import files; existing identical import reused; alias collision → `sql_t`, `sql_t2` |
| T-C5-31 | Shell rewrites: `shell=True` removal span (first/middle/last keyword), `os.system` statement vs used return value, `import subprocess` insertion/conflict |
| T-C5-32 | HTML rewrites for `Markup`, `mark_safe`, `HttpResponse`; unsupported context → CRT505 |
| T-C5-33 | Text backend: CRLF and LF preserved, BOM preserved, latin-1 cookie file preserved, atomic write (temp file not left behind), mode preserved |
| T-C5-34 | Validation failure (monkeypatched planner emitting a bad edit) → file untouched, exit 3 |
| T-C5-35 | `%` conversion: every supported spec, `%%`, tuple/dict/single RHS, every refusal reason |
| T-C5-36 | `.format()` conversion: auto/manual/keyword fields, attribute fields, conversions/specs (HTML/shell), every refusal reason |
| T-C5-37 | `+` conversion: literal/f-string/expression operands; parenthesisation rule; `static-fragment-variable` |
| T-C5-38 | Single-assignment forwarding: each of the four conditions, positive and negative |
| T-C5-39 | Golden: full `fix --diff` on `tstring_basic` (stdout diff + stderr summary), exactly §5.2 |
| T-C5-40 | Idempotency: `fix --write --unsafe-fixes` twice on copies of every fix fixture; the second run's diff is empty, and the `find` results are exactly the expected leftovers |
| T-C5-41 | Differential: text vs LibCST backend byte-identical on all fix fixtures (skipped with the reason if S-03 is negative) |
| T-C5-42 | `--backend libcst` when unavailable → `UsageError` |
| T-C5-43 | Verifier passes all properties for `qmark`, `named`, `format_style`, `pyformat`, `numeric` (P-SQL-4 skipped where documented), `escape_html` and `argv` at 500 examples, seed 0 (`_py314`) |
| T-C5-44 | Verifier catches `naive_sql` (P-SQL-1/2/3), `naive_html` (P-HTML-1), `naive_shell` (P-SH-1) and `almost_html` (P-HTML-1) within 500 examples at seed 0, as CRT506 with the right property id |
| T-C5-45 | Paramstyle auto-detection in the verifier for all five styles; `unknown` → P-SQL-4 skipped |
| T-C5-46 | Result-type mismatch → exit 2 with the documented message |
| T-C5-47 | `--execute` required for non-`cartographer.adapters` processors (exit 2 without it); warning printed with it |
| T-C5-48 | Missing Hypothesis (simulated by blocking the import) → exit 4 with the install hint; running on 3.13 → exit 4 |
| T-C5-49 | No `.hypothesis/` directory is created in the working directory |
| T-C5-50 | A processor raising an exception counts as a property failure with `actual = "raised …"` |
| T-C5-51 | Acceptance fixture: the rewritten `tstring_basic` functions (written to a temp dir, imported, our own code) run against an in-memory sqlite3 `users` table. The payload `x' OR '1'='1` returns no rows, and the table is intact (`_py314`, `execute`) |
| T-C5-52 | `check` (C3) also reports CRT501–505, and suppression comments work on them |
| T-C5-53 | Vendor mode: `fix --diff --adapter-mode vendor` on `tstring_basic` matches its golden (new-file diffs + import lines); after `--write`, a second run's diff is empty; an outdated vendored copy is shown as an update and marked `review` |
| T-C5-54 | **Planted-module defence (§5.3):** `PATH` contains `hypothesis.py`, `sqlite3.py` and `shlex.py` that write a marker file when imported. `tstring verify cartographer.adapters.sql:qmark --kind sql PATH` and `tstring verify good:proc --kind sql --execute PATH` both pass, and **no marker file is created**. `sys.path` is unchanged after an adapter run, and `PATH` is the *last* entry after an `--execute` run. `PROCESSOR = "html:escape"` with `--execute` → `UsageError` (resolved outside PATH) |
| T-C5-55 | `cartographer/adapters/*.py` import only stdlib modules and each other via relative imports (an `ast` scan of the package) |
| T-C5-56 | Scope (D-047): `tstring find --select CRT3` reports nothing and exits 0; `tstring find` never reports CRT3xx even when they'd fire; `tstring verify` reports only CRT506 |

## 11. Acceptance criteria

| ID | Criterion |
|---|---|
| A-C5-01 | `tstring find` on `tstring_basic` prints exactly the §5.1 output (timing excluded) |
| A-C5-02 | `tstring fix --diff` on `tstring_basic` prints exactly the §5.2 diff and summary. After `--write --unsafe-fixes`, `find` reports only the two line-16 diagnostics, and a second `fix` produces an empty diff |
| A-C5-03 | The rewritten fixture code is **behaviourally safe**: T-C5-51 passes |
| A-C5-04 | `tstring verify` passes for every reference adapter and fails each of the four broken processors on the specified properties, with CRT506 (T-C5-43/44) |
| A-C5-05 | Every CRT505 reason id in §6.8.6 is produced by at least one test fixture, and every before → after row in §6.8 is a passing test |
| A-C5-06 | The LibCST differential test passes, **or** S-03's negative result is documented and the `UsageError` path is tested |
| A-C5-07 | On 3.13: `find` works, `fix`/`verify` exit 4 with their messages, and the test suite is green with the `_py314` files not collected |
| A-C5-08 | Corpus: on the intentionally vulnerable app from S-07 (PyGoat or DVPWA), `find` reports at least one true-positive injection-risky sink, and `fix --diff` produces a rewrite for it that passes validation (§6.9). The rewritten function is reproduced as a fixture and exercised like T-C5-51. **The corpus code itself is never executed** (D-013) |
| A-C5-09 | Corpus triage: every CRT501–503 on the corpus repos is labelled true or false positive in the write-up, with precision per kind |
| A-C5-10 | `tstring find` on the 2,000-file synthetic project < 10 s on the dev machine |
| A-C5-11 | `cartographer check .` (dogfood, root `.`, D-048) reports no CRT50x on Cartographer itself (our own `subprocess` calls follow 05 §2) |
| A-C5-12 | Documentation: eight Stage 5 concept notes ✅; walkthrough, write-up, comparison; glossary/FAQ updated; S-03, S-05 and S-10 notes exist |
| A-C5-13 | Vendor mode works without Cartographer: after `fix --write --unsafe-fixes --adapter-mode vendor` on a temp copy of `tstring_basic`, the T-C5-51 checks pass in a subprocess started with `python -I -S` (no site-packages, so `cartographer` is not importable) with only the temp dir on `sys.path` (`_py314`, `execute`) |
| A-C5-14 | `tstring verify` never lets a module in `PATH` shadow the stdlib or Hypothesis (T-C5-54) |

## 12. Documentation deliverables

**Concept notes (exact slugs):** `string-formatting`, `template-strings`, `injection-attacks`, `dbapi-and-paramstyles`, `literal-string`, `dataflow-and-taint`, `cst-and-codemods`, `structure-preservation`. Musts:
- `string-formatting`: `%`, `.format()`, f-strings incl. PEP 701 (3.12) grammar changes and the `=` specifier; `string.Formatter().parse()`; converting between styles and the traps (tuple RHS, evaluation order).
- `template-strings`: `Template`/`Interpolation`, iterating, writing a 10-line processor, why `str(template)` is not the rendered text, composition of templates. `pycon` examples marked `# Python 3.14+`.
- `injection-attacks`: SQL with in-memory sqlite3 (show the attack working on an f-string query and failing on a parameterised one), shell (with `shlex.split` showing how words change; **never run a real shell**), HTML (with `html.parser` events), SSTI explained in prose.
- `dataflow-and-taint`: sources/sinks/propagation; may vs must; flow-sensitive vs flow-insensitive; intra- vs inter-procedural; the env-table walkthrough; why annotations aren't trusted.
- `cst-and-codemods`: AST vs CST, a byte-identical round-trip demo, minimal text edits, LibCST transformers, idempotency.
- `structure-preservation`: the property formulations from §6.11, why "benign vs adversarial" comparison works, shrinking, testing ≠ proof.

**Walkthrough** `docs/learn/walkthroughs/C5.md`: trace `find_by_name` from tokens → AST → env table → sink match → finding → plan (show the `Edit` list) → diff → rewritten code → `qmark()` output → sqlite3 execution.

**Write-up** `docs/learn/writeups/C5.md`: predictions; corpus precision per kind; how often fixes were `safe` vs `review` vs refused (with the reason distribution); the verifier's run times; anything ★-novel discovered (what was harder than expected about f→t migration).

**FAQ seeds:** "Does the rewritten code need Cartographer installed?" (yes in `import` mode; no in `vendor` mode, §6.8.8), "Can I vendor the adapters?" (yes, the header keeps the MIT notice), "Why does the fix add `*` before `sql(...)`?", "Why is my rewrite marked review?", "Can I use the adapters in production?" (yes, but they're intentionally minimal: see S-05 alternatives), "Why can't the tool rewrite table names?".

## 13. Reference implementations to compare after

| Reference | Look at | Questions |
|---|---|---|
| **ruff `S608`** (hardcoded SQL expression), **`S602`/`S605`** (shell) | How they detect SQL-looking strings (keyword heuristics?) without dataflow | What do they catch that our sink-based approach doesn't, and vice versa? Run both on `tstring_basic`, `tstring_convert` and the corpus |
| **Bandit `B608`, `B602`** | Same | Same, plus their confidence/severity model vs ours |
| **Semgrep** Python injection rules | Taint mode (sources/sinks/sanitizers) | How does a generic taint engine express what we hard-coded? (Note: it can't parse t-strings yet, per research §00) |
| **sql-tstring**, **tdom** (if S-05 confirms them) | Their processors | Run our verifier on them. Where do their designs differ (identifier handling, HTML contexts)? |
| **t2string** | The reverse transformation | What edge cases did they have to handle going t→f? |
| **LibCST codemods** (`libcst.codemod`) | The framework for multi-file codemods | Should our planner have been a `VisitorBasedCodemodCommand`? |

## 14. Risks & open items

- **Resolved (D-036, D-013 amended):** `tstring verify` is the third opt-in execution path. No flag is needed for `cartographer.adapters.*`; any other processor needs `--execute` (§5.3).
- **Resolved (D-035):** an optional extra `verify = ["hypothesis>=…"]` makes Hypothesis an optional runtime dependency for `tstring verify` only (D-006 requires a decision record).
- **S-10** (08) covers `Template`/`Interpolation` constructor signatures and iteration semantics, and `tokenize` positions for f-/t-string tokens around escaped braces.
- **S-03** may come back negative. Then the text backend is the only backend (D-023 fallback), and phase 6 shrinks to documentation.
- **R-02 (size):** XL. The MVP line is explicit (phases 1–7, 9). Phase 8 is optional.
- **R-05:** method-name sinks (`execute`) can match unrelated APIs. Mitigated by receiver strength + confidence + `disable-sinks` + corpus triage.
- **mypy coverage of adapters:** the main mypy run uses `python_version = "3.15"` (05 §2), so `adapters/` is fully checked. The extra `--python-version 3.13` pass must exclude `adapters/`, or the version guard makes their bodies unreachable.
- **Runtime dependency of rewrites (review item):** with the default `import` mode, rewritten projects depend on `cartographer-py`. That's why vendor mode is part of the MVP (§6.8.8) and the fix summary always prints the note in §5.2.

## 15. Exercises for the learner

1. **Attack and defend.** In a Python 3.15 REPL with `sqlite3.connect(":memory:")`, create a `users` table, then run an f-string query with `name = "x' OR '1'='1"`. Then do the same with `qmark(t"…")`. Explain the difference in one paragraph.
2. **Write a processor.** Implement `def csv_row(t: Template) -> str` that quotes values per RFC 4180. Then verify it with a property of your own design: "the number of fields after `csv.reader` parsing is the same as with benign values".
   *Hint:* that's P-SH-1 in disguise.
3. **Beat the analysis.** Write three snippets where a dynamic string reaches `cur.execute` but CRT501 stays silent. For each, name the design limit (inter-procedural, attribute storage, aliasing).
4. **Convert by hand.** Rewrite `"UPDATE t SET a = %s WHERE id = %d" % (a, i)` and `"{0} and {0}".format(f())` as t-strings, or explain why you can't safely.
5. **Find the subtle bug.** Before reading the tests, look at `almost_html` in `tests/fixtures/processors/broken.py` and write down an input that breaks it. Then run `tstring verify` and compare your input with the shrunk counterexample.
