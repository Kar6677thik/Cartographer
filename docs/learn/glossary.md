# Glossary

> Every term used in Cartographer's docs and code, in plain English. **Rule (04 §1):** when a PR introduces a new term, it adds it here in the same PR. Entries link to the concept note that explains them in depth (→).
> Alphabetical. Code identifiers are in `backticks`.

---

**Abstract syntax tree (AST)**: A tree of objects that represents the *structure* of code: "a function call, whose function is `print`, with one argument". Comments and formatting are dropped. Python's `ast` module builds one. → `ast-basics`

**Acceptance criterion**: An objectively checkable statement that must be true for a milestone to be done (IDs like `A-C1-03`).

**Adapter / processor (t-strings)**: A function that takes a `Template` and turns it into something safe to use: a SQL query plus parameters, escaped HTML, or an argument list. → `template-strings`

**Annotation slot**: One place where a type annotation can go: a parameter or a return value. C4's coverage counts slots. → `gradual-typing`

**`Any`**: The type that switches type-checking off for a value. Anything can be assigned to it and it can be used as anything. It "leaks" when untyped values spread into typed code. → `gradual-typing`

**Any-leak**: A public symbol of a typed module whose type is effectively `Any`, so `Any` spreads into code that uses it (CRT403). → `gradual-typing`

**Artefact poisoning (CI)**: A privileged workflow consuming build artefacts produced by an untrusted run. → `ci-attack-patterns`

**Assertion rewriting (pytest)**: pytest rewrites `assert` statements in test files while importing them, so a failure shows the values involved (`assert 4 == 5`). → `testing-with-pytest`

**Atomic write**: Write to a temporary file, then `os.replace` it over the target, so nobody ever sees a half-written file.

**Attestation (PEP 740)**: A signed statement, published on PyPI next to a file, saying *which CI workflow in which repository built it*. It proves where a file came from, **not** that it's safe (the Ultralytics lesson). → `pypi-and-provenance`

**Audit hook (PEP 578)**: A callback registered with `sys.addaudithook` that CPython calls for sensitive events (`open`, `socket.connect`, `subprocess.Popen`, …). Useful for *observing* behaviour. It cannot reliably *sandbox* code. → `audit-hooks`

**Backpressure / semaphore**: Limiting how many tasks run at once. An `asyncio.Semaphore(8)` lets at most 8 tasks into a section of code at a time. → `asyncio-fan-out`

**Billion laughs**: A tiny YAML or XML document that explodes in size through nested aliases. → `yaml-and-its-traps`

**Bootstrap confidence interval**: A way to estimate the uncertainty of a measurement by resampling your data many times. "Median 412 ms, 95 % CI [398, 430]". → `measuring-performance`

**Bootstrap (percentile method)**: Estimate a confidence interval by resampling your data with replacement many times and taking percentiles of the recomputed statistic. → `measuring-performance`

**Build backend / frontend**: The *frontend* (`uv build`, `pip`) asks the *backend* (`hatchling`, `setuptools`) to turn source into a wheel or sdist. → `packaging-and-build-backends`

**Build matrix (CI)**: Running the same CI job once per combination of settings, for example 2 operating systems × 4 Pythons = 8 jobs. → `git-and-github-actions-basics`

**Byte offset vs. character offset**: `ast` reports columns as *UTF-8 byte* positions. `é` is 2 bytes but 1 character, so the two disagree on non-ASCII lines (D-018). → `text-and-encodings`

**Bytecode**: The low-level instructions CPython compiles your code into before running it. Visible with `dis`. → `how-python-runs-code`

**Cache poisoning (CI)**: Planting malicious content in a CI cache that a trusted job later restores. This was likely part of the Ultralytics attack. → `ci-attack-patterns`

**Capability manifest**: C6's list of security-relevant things a package version can do (network, subprocess, exec, …), with evidence locations.

**CLI (command-line interface)**: A program you drive by typing commands and options in a terminal.

**Code object**: What `compile()` produces: bytecode plus the names, constants and line numbers it needs. Running a module means executing its code object. → `how-python-runs-code`

**Codemod**: A program that rewrites source code automatically (for example, f-string → t-string). → `cst-and-codemods`

**Commit SHA**: The 40-character hexadecimal hash that identifies a git commit. It's computed from the content, so it can't be re-pointed like a tag. → `git-and-github-actions-basics`

**Composite action**: A reusable GitHub Actions step defined in an `action.yml` that bundles several steps. The Ultralytics injection lived in one. → `github-actions-model`

**Concrete syntax tree (CST)**: Like an AST, but it keeps *everything*: whitespace, comments, parentheses. That's what lets a codemod change one thing and leave the rest of the file byte-for-byte identical. LibCST provides one. → `cst-and-codemods`

**Condensation graph**: The graph you get by collapsing each SCC into one node. It is always acyclic. → `graphs-and-scc`

**Confidence (of a finding)**: How sure a heuristic is (`high` / `medium` / `low`), stored in `Diagnostic.data`.

**Content-addressed cache**: Files stored under their own hash, so a name always means the same bytes. → `hashing-and-integrity`

**Copy-on-write (CoW)**: After `fork()`, parent and child share memory pages until one writes. That's mostly a Kiln topic, mentioned for context.

**Counterexample (Hypothesis)**: The smallest failing input Hypothesis reports after shrinking. → `property-based-testing`

**CPython**: The standard Python interpreter, written in C. When people say "Python" they usually mean CPython.

**Cycle (import cycle)**: Module A imports B, which (directly or through others) imports A. → `circular-imports`

**Dataclass**: A class whose `__init__`, `__repr__` and `__eq__` are generated from annotated fields by `@dataclass`. → `dataclasses-and-enums`

**DB-API (PEP 249)**: The standard interface Python database drivers follow: `connect()`, `cursor()`, `execute(sql, params)`. → `dbapi-and-paramstyles`

**Dependency confusion**: An attacker publishes a package with the same name on another index, and it gets installed instead of the real one.

**Dependency injection**: Passing a component the things it needs (a clock, a runner, the config-section types) instead of letting it create or import them. It makes code testable.

**Depth-first search (DFS)**: Exploring a graph by going as deep as possible along each path before backtracking. → `graphs-and-scc`

**Descriptor**: An object that customises attribute access by defining `__get__` (and maybe `__set__`). `property`, methods and `cached_property` are all descriptors. → `descriptors-and-cached-property`

**Diagnostic**: One finding Cartographer reports: code, severity, message, location, help, optional fix. See spec 02 §4.4.

**Differential test**: Running two implementations on the same input and comparing their outputs.

**Docker container**: An isolated process with its own filesystem and (optionally) no network. We use it as a sandbox in C6. → `containers-and-sandboxing`

**Docstring**: A string literal that is the first statement of a module, class or function. It becomes `__doc__` and is our main in-code documentation (04 §3).

**Doctest**: An example in a docstring written as an interactive session (`>>> 1 + 1` / `2`) that the `doctest` module runs as a test.

**Dogfooding**: Using your own tool on yourself. Cartographer analyses its own source in CI.

**DOT**: Graphviz's text format for describing graphs. → `graph-visualisation`

**Dynamic analysis**: Learning about code by *running* it and observing (C2 measure, C6 sandbox). The opposite of static analysis.

**Edge (graph)**: A connection from one node to another. In C1, "module A imports module B".

**Edge kind (C1)**: How and when an import runs: `module` (at import time), `optional` (inside `try/except ImportError`), `dynamic` (`importlib.import_module`), `deferred` (inside a function), `typing` (under `TYPE_CHECKING`).

**Editable install**: Installing a project so the environment points at its source folder (`src/`), so edits take effect without reinstalling. `uv sync` does this for the project itself. → `project-layout-and-pyproject`

**Entry point**: A named hook declared in package metadata. *Console scripts* create commands (`cartographer`). *Plugin groups* (`cartographer.rules`) let other packages register extensions. → `entry-points-and-plugins`

**Environment (GitHub)**: A named deployment target (for example `testpypi`) that can require reviewer approval and hold its own secrets. → `github-actions-model`

**Event loop**: The asyncio scheduler that runs coroutines. One blocking call stops every task on it. → `asyncio-basics`

**ExceptionGroup / `except*`**: How Python reports several exceptions at once. asyncio's `TaskGroup` raises one when several tasks fail. → `asyncio-fan-out`

**Exit code**: The number a program returns to the shell when it ends. 0 means success. Cartographer's meanings are in spec 03 §3.

**Exponential backoff with jitter**: Retry delays that double each time, with random variation so clients don't all retry at the same moment. → `asyncio-fan-out`

**Feedback arc set**: A set of edges whose removal makes a graph acyclic. The smallest one is NP-hard to find, so we use a heuristic. → `breaking-cycles`

**Fixture (pytest)**: A function that provides test setup. Also used loosely for **fixture projects**, the tiny fake repos under `tests/fixtures/`. → `testing-with-pytest`

**Flow-sensitive analysis**: An analysis that follows statements in order, so `x = "safe"` after `x = user_input` makes `x` safe again. → `dataflow-and-taint`

**Free-threaded build (`3.15t`)**: A CPython build without the GIL, so threads can run Python code truly in parallel. Some C extensions turn the GIL back on when imported.

**Frozen (dataclass)**: Instances can't be modified after creation, which makes them safe to share and hashable.

**f-string**: `f"Hello {name}"`, which is evaluated immediately into a plain `str`. → `string-formatting`

**GIL (Global Interpreter Lock)**: A lock in standard CPython that lets only one thread run Python bytecode at a time.

**`GITHUB_TOKEN`**: The automatic short-lived token every workflow run gets. Its rights are set by `permissions:`. → `github-actions-model`

**Glob pattern**: A filename pattern such as `src/**/*.py`, where `**` means "any number of directories". → `paths-and-files`

**Golden file / snapshot test**: A test that compares output against a stored "known good" file (05 §3.4).

**Gradual typing**: Typing where annotated and unannotated code mix, with `Any` as the bridge. → `gradual-typing`

**Hatchling**: The build backend we use (D-033).

**Heuristic**: A rule of thumb that is usually right but not always. Most static analysis is heuristic.

**Hypothesis**: A library for *property-based testing*. You describe the inputs, and it generates hundreds of cases, then *shrinks* any failure to the smallest example. → `property-based-testing`

**`-I` (isolated mode)**: `python -I` ignores `PYTHON*` environment variables and the user's site-packages, and doesn't add the script's directory to `sys.path`. That protects against planted modules.

**Idempotent**: Doing it twice gives the same result as doing it once. Our codemods must be idempotent.

**Import-time side effect**: Work a module does merely by being imported: network calls, registering plugins, reading files. → `module-execution-and-side-effects`

**Impostor commit**: A commit SHA from a fork's network that GitHub serves as if it belonged to the upstream repo. → `ci-attack-patterns`

**`__init__.py`**: A file that marks a directory as a *regular package*. Its code runs the first time anything in the package is imported. → `import-system`

**Integrity API (PyPI)**: PyPI's endpoint serving attestations/provenance for each file (spike S-08). → `pypi-and-provenance`

**Interleaving (benchmarks)**: Alternating the variants run by run (A, B, A, B…) so that machine drift affects all of them equally. → `measuring-performance`

**Interpolation (t-strings)**: One `{…}` part of a t-string. It holds the evaluated `value`, the source `expression` text, `conversion` and `format_spec`. → `template-strings`

**Intra-procedural**: Within a single function. C5's taint analysis is intra-procedural (non-goal NG4).

**Lattice / join / fixpoint**: An ordered set of abstract values (for example `safe` < `maybe-tainted`). *Join* merges two of them at a branch. A *fixpoint* is reached when another pass of the analysis changes nothing. → `dataflow-and-taint`

**Lazy import (PEP 810)**: `lazy import json` binds `json` to a proxy. The real import happens on first use, which speeds up startup. → `lazy-imports`

**`__lazy_modules__`**: A module-level list of module names (PEP 810). On Python 3.15+ the imports of those modules in that file become lazy. Older Pythons ignore it, which makes it the backwards-compatible way to opt in. → `lazy-imports`

**LibCST**: A library from Meta/Instagram that parses Python into a CST and lets you modify it while preserving formatting (D-006, D-023).

**Linter**: A program that reports likely-mistake patterns in code (ruff, flake8, and Cartographer's `check`).

**`LiteralString` (PEP 675)**: A type meaning "a string built only from literals in the source", so it can't contain user input. → `literal-string`

**Lockfile**: A file (`uv.lock`) recording the exact versions of every dependency, so everyone gets identical environments.

**Logical line**: One complete statement, which may span several physical lines inside brackets. Suppression comments apply to the whole logical line. → `tokenize-and-comments`

**`__main__`**: The name Python gives the module you run directly (`python file.py` or `python -m pkg`). `if __name__ == "__main__":` checks for it. → `how-python-runs-code`

**May-analysis**: An analysis that reports what *might* happen on at least one path through the code. → `dataflow-and-taint`

**Median**: The middle value of sorted data. Unlike the mean, it isn't dragged around by a few outliers. → `measuring-performance`

**Mermaid**: A text diagram format that GitHub renders in Markdown. → `graph-visualisation`

**Minimal vs. minimum**: *Minimal* means you can't remove any single element and still succeed. *Minimum* means the smallest possible. A minimal cut set isn't necessarily a minimum one. → `breaking-cycles`

**Module**: A single `.py` file, as seen by the import system, with a dotted name like `pkg.sub.mod`.

**Module `__getattr__` (PEP 562)**: A function defined in a module that handles lookups of attributes the module doesn't otherwise define. It was a common way to fake lazy imports before PEP 810.

**`mypy` / `pyright` / `pyrefly` / `ty`**: Static type checkers. They disagree on edge cases, and C4 studies those disagreements. → `how-type-checkers-work`

**mypyc**: Compiles type-annotated Python into a C extension for speed. → `mypyc`

**Namespace package (PEP 420)**: A package directory *without* `__init__.py`. It can be split across several directories. → `import-system`

**Node (graph)**: A vertex. In C1, a module.

**NP-hard**: A class of problems for which no known algorithm solves every case quickly. We use heuristics instead. → `breaking-cycles`

**OIDC (OpenID Connect)**: A standard for issuing short-lived signed identity tokens. Trusted Publishing uses GitHub's OIDC tokens. → `trusted-publishing`

**Oracle (testing)**: A trusted implementation whose answers we compare ours against (for example networkx for SCCs).

**p99 latency**: The latency that 99 % of requests beat. It measures the slow tail, not the average.

**Package**: A directory of modules (with or without `__init__.py`) that you can import.

**paramstyle**: How a DB-API driver writes placeholders: `qmark` (`?`), `format` (`%s`), `pyformat` (`%(name)s`), `named` (`:name`), `numeric` (`:1`). Cartographer's SQL adapters are named after these: `qmark`, `numeric`, `named`, `format_style` (for `format`, which would clash with the built-in), `pyformat`. → `dbapi-and-paramstyles`

**Pending publisher**: A Trusted Publisher registered on (Test)PyPI *before* the project exists, so the first upload can create it. → `trusted-publishing`

**PEP**: Python Enhancement Proposal, a design document for a Python change. For example, PEP 750 introduced t-strings.

**PEP 503 name normalisation**: Lowercase a project name and turn runs of `-`, `_` and `.` into a single `-`. `Foo.Bar_baz` becomes `foo-bar-baz`. → `pypi-and-provenance`

**PEP 639 licence metadata**: The SPDX `license = "MIT"` expression and `license-files` fields in `pyproject.toml`. → `packaging-and-build-backends`

**Placeholder (SQL)**: The parameter marker in a query (`?`, `%s`, `:name`) that the driver fills in safely. → `dbapi-and-paramstyles`

**Pratt parser**: An expression parser that handles operator precedence by giving each operator a "binding power". C7's `${{ }}` expression scanner uses one. → `actions-expressions`

**Precise coverage (C4)**: Annotated slots that don't contain `Any`, divided by all slots. → `gradual-typing`

**Property (in property-based testing)**: A statement that should hold for *all* inputs, for example "sorting twice equals sorting once".

**Provenance**: Where an artefact came from and how it was built. → `pypi-and-provenance`

**`.pth` file**: A file in `site-packages` that adds paths to `sys.path` at startup. Lines starting with `import` are *executed*, which is a stealthy persistence trick. PEP 829 deprecates that in 3.15. → `site-and-pth-files`

**`pull_request_target`**: A GitHub Actions trigger that runs with the *base* repo's secrets even for PRs from forks. It's dangerous when it checks out or interpolates PR content. → `ci-attack-patterns`

**`pycache_prefix`**: An `-X` option / `PYTHONPYCACHEPREFIX` env var that writes `.pyc` files to a separate directory. C2 uses it to control warm vs. cold imports. → `importtime`

**PyPI**: The Python Package Index, where `pip`/`uv` download packages from. **TestPyPI** is a separate practice instance.

**Qualified name**: The full dotted name an expression refers to at runtime. After `from time import sleep as nap`, `nap` has qualified name `time.sleep`. → `visitor-pattern`

**RECORD file**: A wheel's manifest listing every file with its hash and size. → `wheels-and-sdists`

**Re-export**: A package `__init__` importing a name so users can reach it through the package (`from pkg import Thing`). → `import-system`

**Reference implementation**: An existing tool we compare against *after* building ours (D-008).

**Regular expression (regex)**: A pattern language for matching text (`re`). We avoid regex for parsing code, because tokenizers and parsers are correct where regexes are not.

**Reification (lazy imports)**: The moment a lazy proxy is replaced by the real imported module, on first use.

**Relative import**: `from . import x` / `from ..pkg import y`. It resolves relative to the current package. → `import-system`

**Release candidate (rc)**: A PEP 440 pre-release such as `1.0.0rc1`. → `versioning-and-releases`

**Reproducible build / `SOURCE_DATE_EPOCH`**: Getting identical bytes from identical inputs. The env var pins timestamps inside archives. → `packaging-and-build-backends`

**Reusable workflow**: A GitHub workflow that another workflow calls with `jobs.<id>.uses:`. → `github-actions-model`

**Reverse topological order**: An ordering of a DAG where every edge points *backwards*, so dependencies come before the things that depend on them. → `graphs-and-scc`

**Runner (CI)**: The fresh virtual machine GitHub starts to run one CI job. → `git-and-github-actions-basics`

**SARIF**: Static Analysis Results Interchange Format, a JSON standard for tool findings. GitHub code scanning reads it. → `sarif-and-machine-output`

**SCC (strongly connected component)**: A maximal group of nodes where every node can reach every other. An SCC with more than one module is an import cycle. → `graphs-and-scc`

**sdist (source distribution)**: A `.tar.gz` of a project's source. Installing one may *run build code* (`setup.py`). → `wheels-and-sdists`

**Self-loop**: An edge from a node to itself, for example a module importing itself. → `graphs-and-scc`

**Severity**: How serious a diagnostic is: `info`, `warning`, `error`.

**Shannon entropy**: The average information per character. Encoded or compressed blobs score high, which is one obfuscation signal. → `obfuscation-signals`

**Shrinking (Hypothesis)**: After finding a failing input, Hypothesis searches for the *simplest* input that still fails.

**Sink**: A function where dangerous data causes harm: `cursor.execute`, `subprocess.run(…, shell=True)`, HTML responses. → `dataflow-and-taint`

**`site-packages`**: The directory where installed third-party packages live.

**Skeleton (verifier)**: A template's fixed structure (its static text with slots) before any values are chosen. → `structure-preservation`

**Slots (`__slots__`)**: Declaring a fixed set of attributes, which saves memory and blocks typo'd attributes.

**Source root**: A directory containing top-level packages (`src/` in src layout, the repo root in flat layout). Spec C1 defines detection.

**Source (taint)**: Where untrusted or dynamic data enters, for example function parameters or `input()`. → `dataflow-and-taint`

**Spike**: A short experiment to verify a fact before depending on it (spec 08).

**Squash merge**: Merging a pull request as one single commit on `main`, however many commits the branch had. → `git-and-github-actions-basics`

**SSTI (server-side template injection)**: Injecting into a template's *source* (for example a Jinja template string), which can run code on the server. → `injection-attacks`

**Static analysis**: Learning about code **without running it**, by reading and parsing it.

**stdout / stderr**: The two output streams of a program. Results go to stdout. Logs and errors go to stderr.

**Supply-chain attack**: Compromising software by attacking something it depends on, such as a package, a CI workflow or a build cache.

**Suppression comment**: `# cartographer: ignore[CODE]`, which silences one diagnostic on that line (03 §5). → `tokenize-and-comments`

**Symbol table (`symtable`)**: The compiler's record of which names are local, global or free in each scope.

**`sys.modules`**: The dictionary of every module imported so far. A second `import` of the same module is a lookup here, not a re-run. → `how-python-runs-code`

**`sys.path`**: The list of folders `import` searches, in order. Its first entry depends on how Python was started. → `how-python-runs-code`

**Taint analysis**: Tracking whether dynamic or untrusted data can flow from a source to a sink. → `dataflow-and-taint`

**Tangle**: Dropbox's word for a large SCC: hundreds of modules all mutually reachable.

**Tarjan's algorithm**: Finds all SCCs in one depth-first search, in O(V + E). → `graphs-and-scc`

**Template injection (CI)**: When `${{ … }}` expands attacker-controlled text (a branch name, a PR title) directly into a shell script. → `actions-expressions`

**TEST-NET-1 (192.0.2.0/24)**: An IP range reserved for documentation, which is never routed. C6's replica "beacon" points there.

**Token / tokenizer**: The tokenizer splits source text into tokens (names, operators, strings, comments). It runs before the parser. → `tokenize-and-comments`

**Trove classifier**: A standard PyPI metadata tag such as `Programming Language :: Python :: 3.15`. → `packaging-and-build-backends`

**Trusted Publishing**: Publishing to PyPI from CI using short-lived OIDC credentials instead of a stored API token. → `trusted-publishing`

**t-string (PEP 750)**: `t"Hello {name}"`. Unlike an f-string, it produces a `string.templatelib.Template` that keeps the literal parts and the interpolated values separate, so a processor can escape or parameterise the values. → `template-strings`

**`TYPE_CHECKING`**: A constant in `typing` that is `False` at runtime and treated as `True` by type checkers. It's used to import things only for annotations. → `type-checking-guard`

**Universal newlines**: Text mode turning `\r\n` and `\r` into `\n` on read. → `text-and-encodings`

**UTF-8 mode (`-X utf8`, PEP 540)**: Forces UTF-8 for all I/O regardless of the system locale. It's the default from 3.15 (PEP 686). → `text-and-encodings`

**uv**: A fast Python project and package manager from Astral. → `virtual-environments-and-uv`

**Value position (SQL)**: A place in a query where a parameter is allowed, such as a value but not a table or column name. → `dbapi-and-paramstyles`

**Virtual environment (venv)**: An isolated directory with its own `site-packages`, so projects don't share installed packages. → `virtual-environments-and-uv`

**Visitor (pattern)**: An object with one method per node type (`visit_Call`, `visit_Import`), called while walking a tree. → `visitor-pattern`

**Wheel**: A pre-built package (`.whl`, which is a ZIP). Installing a wheel runs no build code. → `wheels-and-sdists`

**`-X importtime`**: An interpreter option that prints each import's self and cumulative time in microseconds to stderr. → `importtime`

**YAML anchor / alias / merge key**: `&name` defines a reusable node, `*name` reuses it, and `<<:` merges a mapping. → `yaml-and-its-traps`

**Zip bomb**: A tiny archive that expands to an enormous size. **Zip slip**: an archive entry named `../../evil.py` that escapes the extraction directory. → `archive-safety`
