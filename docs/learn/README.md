# Learning path and curriculum index

> **Start here if you're new.** This page is the map of everything you'll learn by building Cartographer, in the order you'll meet it.
>
> - Questions you have along the way → [`faq.md`](faq.md) (and ask! every question gets an answer written down).
> - Unknown word → [`glossary.md`](glossary.md).
> - How these notes are written → [`../spec/04-documentation-standard.md`](../spec/04-documentation-standard.md).

---

## How to use this page

1. Before a milestone, read the notes marked for it, plus any earlier ones you skipped.
2. Each note ends with exercises. Doing even one fixes the idea in memory far better than rereading.
3. ✅ = written, ☐ = not yet written. The implementer ticks the box in the PR that adds the note.

## Folder map

| Folder | Contents |
|---|---|
| `concepts/` | Concept notes: "X in Python, from zero" |
| `predictions/` | Your guesses *before* each milestone |
| `walkthroughs/` | Guided tours of the code, per milestone |
| `writeups/` | What happened: measurements, surprises, prediction vs. reality |
| `comparisons/` | How the reference tools (ruff, zizmor…) differ from ours |
| `spikes/` | Fact-checking experiments (see spec 08) |

## Curriculum

The slug is the file name: `concepts/<slug>.md`. **Owner** is the milestone that writes the note first. Later milestones may add sections to it.

### Stage 0: Foundations (M0)
| ✓ | Slug | Topic | What you'll be able to explain |
|---|---|---|---|
| ☐ | `how-python-runs-code` | Interpreter, bytecode, modules, scripts vs. `-m` | What actually happens when you type `python file.py` |
| ☐ | `project-layout-and-pyproject` | Packages vs. modules, `src/` layout, `pyproject.toml`, entry points (intro) | Why our repo is shaped the way it is |
| ☐ | `virtual-environments-and-uv` | venvs, `site-packages`, lockfiles, `uv sync/run/python` | Where installed packages live and why projects isolate them |
| ☐ | `type-hints-basics` | Annotations, `X \| None`, generics in brief, `mypy` | How to read every signature in this codebase |
| ☐ | `dataclasses-and-enums` | `@dataclass(frozen, slots)`, `IntEnum`, immutability, hashing | Why our core types are frozen dataclasses |
| ☐ | `exceptions` | Raising, catching, hierarchies, `raise … from …`, exit codes | How errors flow from analyzers to the CLI |
| ☐ | `text-and-encodings` | `str` vs `bytes`, Unicode, UTF-8, BOM, PEP 263, PEP 686, `\r\n` | Why column numbers and Windows consoles are tricky |
| ☐ | `paths-and-files` | `pathlib`, `os.scandir`, globbing, posix vs. Windows paths | How Cartographer finds files |
| ☐ | `cli-with-argparse` | argv, sub-parsers, stdout vs stderr, exit codes | How `cartographer graph --format json` is parsed |
| ☐ | `config-with-tomllib` | TOML, `tomllib`, precedence, validation | How settings get from `pyproject.toml` into code |
| ☐ | `logging` | Loggers, levels, handlers, why not `print` | How `-v` works |
| ☐ | `ast-basics` | Source → tokens → AST; `ast.parse`, nodes, fields, positions, `NodeVisitor` | **The foundation of every milestone** |
| ☐ | `tokenize-and-comments` | The tokenizer, why comments aren't in the AST, finding comments safely | How suppression comments are found |
| ☐ | `descriptors-and-cached-property` | Attribute lookup, descriptors, `property`, `cached_property` | How `SourceFile.tree` parses only once |
| ☐ | `testing-with-pytest` | Tests, fixtures, markers, parametrize, coverage, golden files | How to read and run our tests |
| ☐ | `property-based-testing` | Hypothesis strategies, shrinking, oracles, invariants | How we prove hand-built algorithms correct |
| ☐ | `git-and-github-actions-basics` | Commits, branches, PRs, what a CI workflow is | What happens when you push |
| ☐ | `sarif-and-machine-output` | JSON schemas, SARIF, why tools emit machine formats | How GitHub shows our findings inline |

### Stage 1: The import system (C1)
| ✓ | Slug | Topic |
|---|---|---|
| ☐ | `import-system` | Finders, loaders, specs, `sys.modules`, `sys.path`, packages, `__init__` execution, namespace packages, relative imports |
| ☐ | `circular-imports` | Why cycles break (partially initialised modules), the classic error messages, the fixes |
| ☐ | `type-checking-guard` | `typing.TYPE_CHECKING`, imports needed only for annotations |
| ☐ | `graphs-and-scc` | Directed graphs, DFS, strongly connected components, Tarjan's algorithm |
| ☐ | `breaking-cycles` | Feedback arc sets, why optimal is NP-hard, greedy heuristics (Eades–Lin–Smyth) |
| ☐ | `graph-visualisation` | DOT and Mermaid formats |

### Stage 2: Startup cost and lazy imports (C2)
| ✓ | Slug | Topic |
|---|---|---|
| ☐ | `module-execution-and-side-effects` | A module is a script that runs once: what counts as a side effect, registration patterns |
| ☐ | `lazy-imports` | PEP 810: `lazy import`, `__lazy_modules__`, proxies, reification, gotchas |
| ☐ | `importtime` | `-X importtime`, reading its output, self vs. cumulative time |
| ☐ | `site-and-pth-files` | `site.py`, `.pth` files, why executable lines are risky, PEP 829 |
| ☐ | `subprocess` | Running programs safely: argument lists, timeouts, `-I`, env |
| ☐ | `measuring-performance` | Noise, warm-up, repeated runs, median, bootstrap confidence intervals |

### Stage 3: Rules and plugins (C3)
| ✓ | Slug | Topic |
|---|---|---|
| ☐ | `visitor-pattern` | Visiting trees; one-pass multi-rule dispatch |
| ☐ | `decorators` | Functions as objects, closures, decorators with arguments, `functools.wraps`, `ParamSpec` |
| ☐ | `class-registries` | `__init_subclass__`, class attributes, metaclasses (and why we don't need one) |
| ☐ | `entry-points-and-plugins` | `importlib.metadata.entry_points`, plugin discovery, isolating plugin failures |
| ☐ | `asyncio-basics` | Event loop, coroutines, `await`, why blocking calls freeze everything, `to_thread` |
| ☐ | `try-finally-semantics` | What `finally` guarantees, how `return` in `finally` swallows exceptions, PEP 765 |
| ☐ | `function-defaults` | Defaults are evaluated once, the mutable-default trap, `None` sentinels, PEP 661 `sentinel` |

### Stage 4: Typing (C4)
| ✓ | Slug | Topic |
|---|---|---|
| ☐ | `gradual-typing` | `Any`, how `Any` spreads, annotation coverage, typing core libraries first (Dropbox) |
| ☐ | `generics-and-variance` | PEP 695 syntax, TypeVar, bounds, covariance/contravariance |
| ☐ | `protocols-and-structural-typing` | `Protocol`, duck typing made static |
| ☐ | `typeddict-overloads-paramspec` | TypedDict (incl. PEP 728 `extra_items`), `@overload`, `ParamSpec`, `TypeForm` (PEP 747) |
| ☐ | `narrowing` | `isinstance`, `TypeGuard`/`TypeIs`, exhaustiveness with `assert_never` |
| ☐ | `annotations-at-runtime` | PEP 649/749 deferred annotations, `annotationlib`, `__annotations__`, why `TYPE_CHECKING` imports can break |
| ☐ | `how-type-checkers-work` | Binding, inference, narrowing, incremental checking; why mypy/pyright/pyrefly/ty disagree |
| ☐ | `mypyc` | Compiling typed Python to C extensions, what speeds up and what doesn't |

### Stage 5: Strings, t-strings and injection (C5)
| ✓ | Slug | Topic |
|---|---|---|
| ☐ | `string-formatting` | `%`, `.format()`, f-strings (incl. 3.12 grammar changes), format specs, conversions |
| ☐ | `template-strings` | PEP 750: `t"…"`, `string.templatelib.Template`/`Interpolation`, writing a processor |
| ☐ | `injection-attacks` | SQL, shell and HTML injection, with demos in a sandboxed sqlite3 / `shlex` / `html` |
| ☐ | `dbapi-and-paramstyles` | PEP 249, `?` vs `%s` vs `:name`, why parameters beat escaping |
| ☐ | `literal-string` | PEP 675 `LiteralString` |
| ☐ | `dataflow-and-taint` | Sources, sinks, propagation, may-analysis, intra-procedural limits |
| ☐ | `cst-and-codemods` | AST vs CST, LibCST, preserving formatting, safe rewrites |
| ☐ | `structure-preservation` | Verifying a processor: "data never changes the shape of the query" as a property |

### Stage 6: Packages and the supply chain (C6)
| ✓ | Slug | Topic |
|---|---|---|
| ☐ | `wheels-and-sdists` | What's inside each, `METADATA`, `RECORD`, `entry_points.txt`, build-time code |
| ☐ | `archive-safety` | `zipfile`/`tarfile`, zip slip, symlinks, bombs, `tarfile` filters |
| ☐ | `hashing-and-integrity` | SHA-256, why hashes prove "same bytes" but not "safe bytes" |
| ☐ | `audit-hooks` | PEP 578, `sys.addaudithook`, the event list, limits (hooks can't sandbox) |
| ☐ | `containers-and-sandboxing` | What Docker isolates, `--network none`, read-only FS, dropped capabilities |
| ☐ | `pypi-and-provenance` | PyPI JSON API, Trusted Publishing, PEP 740 attestations, Sigstore, what attestations do *not* prove |
| ☐ | `asyncio-fan-out` | `TaskGroup`, `Semaphore`, `to_thread`, timeouts, cancellation |
| ☐ | `obfuscation-signals` | Shannon entropy, base64 blobs, `exec(decode(...))` patterns |

### Stage 7: CI security (C7)
| ✓ | Slug | Topic |
|---|---|---|
| ☐ | `github-actions-model` | Workflows, triggers, jobs, steps, runners, composite actions, reusable workflows, permissions, tokens |
| ☐ | `yaml-and-its-traps` | YAML 1.1 vs 1.2, the `on: → True` trap, anchors, safe loading, node-level parsing |
| ☐ | `actions-expressions` | `${{ }}` syntax, contexts, which values are attacker-controlled |
| ☐ | `ci-attack-patterns` | The Ultralytics chain step by step; pwn requests; cache poisoning; artefact and credential leaks |

### Stage 8: Shipping (C8)
| ✓ | Slug | Topic |
|---|---|---|
| ☐ | `packaging-and-build-backends` | Build frontends vs. backends, hatchling vs. uv_build vs. setuptools, building wheels |
| ☐ | `versioning-and-releases` | SemVer, PEP 440, changelogs, tags, yanking |
| ☐ | `trusted-publishing` | OIDC, PyPI Trusted Publishers, attestations in a release workflow (builds on `pypi-and-provenance`) |
