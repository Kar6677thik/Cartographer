# 08 — Verification spikes and risk register

> **A spike** is a short, time-boxed experiment that answers one factual question before we depend on it. The research notes describe Python 3.15 and several 2026 tools. Some details (exact API names, output formats, library support) **must be checked on the real software** before code is written against them. Specs that depend on an unverified fact are marked *Provisional* and link here.
>
> **Output of every spike:** a short note `docs/learn/spikes/S-NN-<slug>.md` with *question → what we ran → what we saw (paste output) → conclusion → spec changes made*. Spikes are also learning material: they show you how to check facts yourself instead of trusting docs, blogs or AI.
>
> **Rule:** if a spike contradicts a spec, update the spec (and `01-decisions.md` if needed) **in the same PR** as the spike note.

---

## 1. Spikes

| ID | Question | Needed by | Fallback if the answer is "no" |
|---|---|---|---|
| S-00 | Does `uv python install 3.13 3.14 3.15 3.15t` work on this machine, and do the GitHub runners (windows-latest, ubuntu-latest) get all four via `astral-sh/setup-uv`? | M0 phase 1 | Use `actions/setup-python` with `3.15t` / `allow-prereleases`; drop 3.15t from the Windows CI matrix if unavailable and note it |
| S-01 | **PEP 810 on 3.15:** exact syntax (`lazy import x`, `lazy from x import y`); behaviour of `__lazy_modules__`; `-X lazy_imports=…` values and the `PYTHON_LAZY_IMPORTS` env var; `sys.set_lazy_imports_filter()` signature; how a lazy binding looks at runtime (proxy type name); what reifies it (including attribute access from *another* module); whether `lazy` is allowed under a module-level `if`; which name `__lazy_modules__` expects for `from a.b import c` | C2 phase 1 | Adjust C2's advisor output and the `startup compare` mechanism to whatever exists |
| S-02 | **`-X importtime` format** on 3.13, 3.14 and 3.15: header line, column order, units, indentation rule for nesting, and whether `-X importtime=2` exists (and what it adds) | C2 phase 1 | The parser supports exactly the formats observed; fixtures are recorded from real runs |
| S-03 | **LibCST:** latest version; prebuilt wheels for 3.13/3.14/3.15/3.15t on Windows; can it **parse and emit** t-strings (PEP 750) and `lazy import` (PEP 810)? Node names? `PositionProvider` column base and units? | C5 phase 1 (the backend is used from C5 phase 6) | D-023 fallback: LibCST locates nodes, and exact text edits do the rewrite. If LibCST can't even *parse* the 3.15 file, the codemod skips that file with `CRT001` |
| S-04 | **Free-threading:** under 3.15t, does importing `libcst` or `yaml` re-enable the GIL (`sys._is_gil_enabled()`)? | M0 phase 4 (report only) | Record the result in the C4/C8 write-ups. No code change (D-029) |
| S-05 | **Third-party t-string processors:** do `sql-tstring`, `tdom` and `tstr` exist on PyPI as described, what are their APIs, and do they accept `string.templatelib.Template`? | C5 phase 4 | Ship only our reference adapters (D-024). Third-party adapters become documented config examples |
| S-06 | **Sandbox basics:** does `python:3.15-slim` exist on Docker Hub? Which audit events (PEP 578) fire for `socket.connect`, `subprocess.Popen`, `os.system`, `open`, `exec`, `compile`, `import`, `urllib.Request`, `ctypes.dlopen` on 3.15? Does `--network none` + `--read-only` + `--cap-drop ALL` + `--pids-limit` + `--memory` work on Docker Desktop for Windows? Does piping a wheel in on **stdin** and JSON lines out on stdout work reliably (D-040)? (C8 Final acceptance F2 also uses Docker.) | **Part A** (image exists; the D-052 hardening flags work): C2 phase 7. **Part B** (audit events; stdin transport): C6 phase 5 | Build our own image from `python:3.15` or a uv-based image. The event list in C6 is adjusted to what actually fires |
| S-07 | **Acceptance corpus:** choose and pin repos that satisfy G2 (see §3) | C1 phase 1 (pinned before C1 acceptance) | Replace a candidate; worst case, a replica fixture stands in for one criterion and the write-up says so |
| S-08 | **PyPI APIs:** JSON API (`/pypi/<project>/<version>/json`) fields for files and SHA-256 digests; **Integrity API** (`/integrity/<project>/<version>/<filename>/provenance`) response shape; how the Trusted Publisher identity (repository, workflow, environment) appears in PEP 740 attestation bundles; does **TestPyPI** serve the Integrity API too (C8 §6.7)? | C6 phase 2 | Provenance checks report "unknown" (info) instead of failing. The capability diff still works |
| S-09 | **Type-checker CLIs:** current versions and machine-readable output flags for mypy, pyright, pyrefly and ty | C4 phase 4 | Parse the text output with per-tool regexes, and pin tool versions in `scripts/checker_matrix.py` |
| S-10 | **`ast` node shapes:** on 3.14/3.15, the node classes and fields for t-strings (`TemplateStr`, `Interpolation`?) and lazy imports (a flag on `Import`/`ImportFrom`?); on 3.13, what `SyntaxError` message t-strings and `lazy` produce (for the D-004 hint); `string.templatelib.Template`/`Interpolation` constructor signatures and iteration semantics; `tokenize` token positions for f-/t-strings around escaped `{{`/`}}` | M0 phase 3 (hint), C2, C5 phase 1 | Adapt the visitors. The hint falls back to a token-based guess (`t"` prefix / leading `lazy` keyword) |
| S-11 | **PEP 829 (`.pth` / `.start` files)** in 3.15: what exactly is deprecated, what a `.start` file is, and what warning appears | C2 phase 5 | CRT205 reports executable `.pth` lines with the generic "runs code at every startup" explanation |
| S-12 | **mypyc on 3.15:** can it compile `cartographer.graph.scc` and `core.source` on Windows (it needs MSVC Build Tools)? | C4 phase 5 | Run the mypyc experiment in WSL2 or CI (ubuntu) and document why |
| S-14 | **Runtime annotations:** how do `dataclasses`, `typing.NamedTuple`, `typing.TypedDict`, `functools.singledispatch`, `typing.get_type_hints` and `annotationlib.get_annotations` behave when an annotation names a `TYPE_CHECKING`-only import, on 3.13/3.14/3.15, with and without `from __future__ import annotations`? | C4 phase 3 | Keep those consumers at `medium` confidence in CRT406, with a version-dependent note |
| S-15 | **3.15 builtins and misc. facts:** do `sentinel` (PEP 661) and `frozendict` (PEP 814) exist as builtins in 3.15 and under which names? Does the `merge_group` trigger run with base-repo secrets? Does mypyc on 3.15 also need `setuptools` installed? | C2 phase 2, C3 phase 5, C7 phase 3, C4 phase 5 | Remove the builtin from the known-safe lists; classify `merge_group` as privileged (safer default); add `setuptools` to the experiment's tool list |
| S-13 | **Real attack-replica fidelity:** gather from public write-ups (Woodruff, PyPI blog) the exact *shape* of the vulnerable Ultralytics workflow and composite action, so our replica is realistic | C7 phase 1 | Construct from the research's description (§2.11), labelled "reconstructed" |

Each spike is a **task in the milestone named in "Needed by"**. Milestone specs reference these IDs.

## 2. Risk register

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-01 | A research fact (2026 releases, APIs, numbers) is wrong or has changed | Medium | Medium | Spikes (§1). Primary sources first. Milestone write-ups re-verify the numbers we quote |
| R-02 | C5 and C6 are too big and stall the project | High | High | Each has a **minimum viable line** (marked "MVP" in its phases). Phases past it are allowed to slip to a "stretch" list without failing the milestone |
| R-03 | Learner overwhelm: too many concepts at once | Medium | High | Curriculum spread across milestones. Predictions may be short. FAQ captures doubts. "Read before starting" lists only what's needed |
| R-04 | Windows-specific bugs (paths, encodings, line endings, long paths) | High | Medium | Windows in the CI matrix. D-018/D-019/D-020. Golden-file normalisation |
| R-05 | Heuristic analyses (taint, side effects, Any-leaks) give noisy false positives | High | Medium | Confidence levels in `data`. Corpus calibration with measured precision in the write-ups. Defaults favour precision over recall |
| R-06 | Malicious code in a corpus repo or downloaded package | Low | High | Static-only by default (D-013). Docker sandbox with no network for C6. `-I` subprocesses |
| R-07 | LibCST lags behind 3.15 syntax | Medium | Medium | D-023 fallback; S-03 |
| R-08 | Docker Desktop bind mounts on Windows are slow or leak host paths into the container | Medium | Low | Copy artefacts in with `docker cp` (or a read-only mount of a temp dir only). Never mount the repo |
| R-09 | PyPI rate limits / outages | Low | Low | Local cache + recorded fixtures. Network tests are opt-in |
| R-10 | Type-checker output formats change (ty is beta) | High | Low | Pin versions in the checker-matrix script and record them in the C4 write-up |
| R-11 | Scope creep ("let's also support GitLab CI / Poetry locks…") | Medium | Medium | Non-goals (00 §5). New scope needs a decision record and goes into a "post-1.0 ideas" list in `docs/spec/09-future.md` (created on first use) |
| R-12 | AI implementer writes code that the learner can't follow | Medium | High | Documentation standard (04) is a hard gate. The owner can reject any PR with "I don't understand X", which is a valid review comment. The fix is better docs, or simpler code |

## 3. Acceptance corpus: selection criteria (for S-07)

Final acceptance (C8) needs, on **real** repositories pinned by SHA:
1. **≥ 1 real import cycle.** Candidates: mid-sized, mature libraries with many modules. Large frameworks such as Sphinx, Django and SQLAlchemy are known to manage cycles with function-level imports, but check the *current* code.
2. **≥ 1 startup win.** A CLI tool with heavy top-level imports. Candidates: `httpie`, `black`, `pip-audit`, `sphinx-build`. Measured with `startup compare` on 3.15.
3. **≥ 1 injection-risky sink with a working rewrite.** Real, well-maintained libraries rarely build SQL with f-strings, so use an **intentionally vulnerable training app**. Candidates: OWASP **PyGoat** (Django), **DVPWA** (aiohttp). Plus any real repo where we find one, which goes in the write-up.
4. **≥ 1 dependency or CI risk.** Any repo with `.github/workflows` (unpinned actions are very common), and/or `depdiff` on a real package upgrade.

Constraints: open source with a licence permitting analysis; ≤ ~3,000 Python files; clonable without LFS. Record each pick in `corpus/corpus.toml`:
```toml
[[repo]]
name = "pygoat"
url = "https://github.com/adeyosemanputra/pygoat"
sha = "<40-char sha>"
purpose = ["injection"]
notes = "Intentionally vulnerable; never run it."
```
