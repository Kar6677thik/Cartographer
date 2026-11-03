# C6: Dependency upgrade diff (`cartographer depdiff`)

> **Status:** Approved spec, revision 1 (2026-11-03). Parts marked **Provisional (S-NN)** depend on a spike in [08](../08-spikes-and-risks.md).
> **Size:** XL · **Version at end:** 0.6.0 · **Depends on:** M0 · **Research:** §2.11 (Ultralytics, PyPI in 2025), §00 rows "Single-version package audit", "Comparing what two versions of a package do", "Provenance changes between releases".
> **Package:** `src/cartographer/depdiff/` · **Codes:** CRT601–CRT609 ([03 §6](../03-cli-config-output.md#crt6xx-dependency-diff-c6))

---

## 1. Summary

You are about to upgrade a dependency, say `requests 2.31.0 → 2.32.0`. `cartographer depdiff requests 2.31.0 2.32.0` downloads both versions from PyPI, checks that the bytes match what PyPI published, opens the archives **without extracting anything to your disk**, and builds a **capability manifest** for each version. The manifest records everything the package *can do* that matters for security: open network connections, start processes, run dynamically built code, load native code, write files, read environment variables, run code at install time or at interpreter startup. Cartographer then **diffs** the two manifests and reports what the new version can do that the old one couldn't. It also compares **provenance**, the record of who built and published each file: did the new version lose its attestations? Was it published from a different repository or workflow? Optionally (`--dynamic`), it imports each version inside a **disposable Docker container with no network**, records what really happens using Python's **audit hooks**, and diffs that too.

## 2. Why this matters

### 2.1 The incident: Ultralytics, December 2024 (research §2.11)
`ultralytics` is a popular computer-vision package. Attackers got malicious code into four releases:
1. A GitHub Actions workflow was injectable through a **branch name** containing `$(…)`. That's C7's subject.
2. The attackers stole tokens and most likely **poisoned the build cache**, so the build itself produced malicious files.
3. Releases **8.3.41 and 8.3.42** were published by the project's *real* Trusted Publishing workflow. They carried **valid Sigstore attestations** and still contained a cryptocurrency miner.
4. Releases **8.3.45 and 8.3.46** were uploaded with a leftover API token and had **no attestations at all**.

Two lessons shape this milestone:
- **"Attested" doesn't mean "safe."** An attestation proves *where* a file was built, not *what it does*. Detecting 8.3.41 needs a **behaviour diff**: the new version suddenly starts a process and talks to the network.
- **Losing provenance is a signal.** 8.3.45 would have been caught by a simple rule: "the previous version was attested, this one isn't" (CRT604).

### 2.2 The bigger picture: PyPI in 2025
PyPI processed over 2,000 malware reports in 2025, handling 66 % within 4 hours. Over 50,000 projects use Trusted Publishing, and 17 % of uploads carry attestations (research §2.11). Malware is common, and most of it relies on a few tricks we can detect statically: code that runs at **install time** (`setup.py`), at **startup** (`.pth` files), or at **import time**, often hidden behind `exec(base64.b64decode(...))`.

### 2.3 What already exists (research §00)
GuardDog, Packj and pip-audit audit **one** version. OpenSSF package-analysis runs packages in a sandbox. **Upgrade X-Ray** and Socket compare two versions. LastPyMile showed that what is *in the wheel* can differ from what is *in the source*. We rebuild a small, understandable version of the "compare two versions" idea, which the research rates as the most useful question at upgrade time.

## 3. Read before starting

### 3.1 Concept notes
Earlier notes (already written): `ast-basics`, `paths-and-files`, `text-and-encodings`, `exceptions`, `subprocess` (C2), `property-based-testing`.

Notes this milestone writes (owner: C6, curriculum Stage 6). Read each as it lands:
`wheels-and-sdists`, `archive-safety`, `hashing-and-integrity`, `asyncio-fan-out`, `pypi-and-provenance`, `obfuscation-signals`, `audit-hooks`, `containers-and-sandboxing`.

### 3.2 Prediction questions (answer in `docs/learn/predictions/C6.md` before Stage B)
1. A wheel is a ZIP file. If you `unzip` a wheel, which files would you expect to see besides the Python code?
2. Installing a **wheel** vs. installing an **sdist**: which one can run arbitrary code on your machine during installation, and why?
3. If a file's SHA-256 hash matches the hash PyPI publishes, what does that prove? What does it *not* prove?
4. What do you think happens if a ZIP file contains an entry named `../../Windows/evil.dll` and you call `extractall()`?
5. Ultralytics 8.3.41 had a valid attestation. Would a "provenance lost" check have caught it? What would?
6. Guess: of the top 20 packages you know (`requests`, `numpy`…), how many contain code that opens network connections? Would "new network capability" be noisy?
7. Why might `exec(base64.b64decode("..."))` be a stronger malware signal than `exec(code)`?
8. A Python audit hook sees an event every time code calls `open()`. Can an audit hook *stop* malicious code? Why might it not be enough?
9. Docker's `--network none` gives a container no network. What else could malicious code in the container still do?
10. Downloading 4 files and 4 provenance records one after another takes about 8 round trips. How much faster do you expect running them concurrently to be, and what limits it?
11. Why might a `.pth` file be an attractive hiding place for malware?

## 4. Scope

### 4.1 In scope
- Inputs: two versions of one project from a PyPI-compatible index (`PKG OLD NEW`), **or** local artefacts (`--old-file`, `--new-file`).
- Artefact selection, download, SHA-256 verification, cache, offline mode.
- Concurrent network fetching with `asyncio` (`TaskGroup`, `Semaphore`, `to_thread`, timeouts, retries).
- Hostile-archive validation for wheels (`.whl`, ZIP) and sdists (`.tar.gz`; `.zip` sdists too), producing CRT606.
- A static capability manifest from `ast`, archive file listings and package metadata.
- Manifest diff → CRT601, CRT602, CRT603, CRT607.
- Provenance via PyPI's Integrity API → CRT604, CRT605 (**Provisional, S-08**).
- Optional dynamic run in Docker → CRT608 (**Provisional, S-06**).
- sdist-vs-wheel content comparison → CRT609.
- An Ultralytics-style **replica** (benign) for tests and the demo.

### 4.2 Out of scope (and why)
| Out | Why |
|---|---|
| Cryptographic verification of attestations (Sigstore) | Needs a new dependency (`sigstore` / `pypi-attestations`) and is a big topic. We rely on PyPI having verified them at upload (**Provisional, S-08**: confirm PyPI's documented behaviour). Stretch item. |
| Whole lockfile diffs (`uv.lock` A vs. B) | Natural follow-up. Stretch item S6-3. |
| Transitive dependency changes | A new version may add dependencies. We **list** added/removed `Requires-Dist` entries in the payload but do not recurse. |
| Building sdists, or running `setup.py` | Running build code is exactly the danger. We analyse `setup.py` statically only. |
| npm / other ecosystems | Python only (non-goal NG1 spirit). |
| Typosquatting checks | Different question ("is this the right package?"). Stretch S6-5. |
| Analysing every wheel of a multi-platform release | We pick one wheel per version (§6.3) to keep runs fast and deterministic. |

## 5. User-facing behaviour

### 5.1 Command synopsis
```
cartographer depdiff PKG OLD NEW [options]
cartographer depdiff --old-file FILE [--old-file FILE] --new-file FILE [--new-file FILE] [options]

Options:
  --index-url URL         Index base URL (default https://pypi.org). The JSON API is <URL>/pypi/…,
                          the Integrity API <URL>/integrity/…
  --offline               Never touch the network; use only the cache. Missing data → exit 4
  --refresh               Ignore cached JSON metadata (files are still reused if their hash matches)
  --artifacts {wheel,sdist,both}   Which artefacts to analyse (default both)
  --no-provenance         Skip provenance lookups
  --dynamic               Also run the Docker sandbox (needs Docker; see §6.10)
  --extract-to DIR        Debug aid: safely extract both artefacts into DIR for human inspection
                          (never executed). DIR must be empty or not exist
  --format {text,json,sarif}
```
`PKG` is normalised per PEP 503 (`Foo_Bar.baz` → `foo-bar-baz`). `OLD`/`NEW` are exact version strings as listed on the index. If `NEW` < `OLD` by PEP 440 ordering, the diff still runs ("downgrade") with an INFO log.

Local mode: each `--old-file`/`--new-file` may be given up to twice, at most one wheel and one sdist per side. In local mode there is no hash verification (there's nothing to compare against) and no provenance, and the payload records `"source": "local"`.

### 5.2 Example: the replica scenario (normative output)

Two golden files pin this scenario:
- **MVP golden** (phase P3, T-C6-33): `tests/golden/depdiff/replica_100_101_mvp.txt`, run with `--no-provenance --artifacts wheel`. It needs only P1–P3.
- **Full golden** (phase P6, T-C6-19): `tests/golden/depdiff/replica_100_101.txt`, with provenance (P4) and CRT609 (P6).

MVP golden:
```
$ cartographer depdiff ultra-replica 1.0.0 1.0.1 --index-url fixture://ultralytics --no-provenance --artifacts wheel
Comparing ultra-replica 1.0.0 → 1.0.1
  old: ultra_replica-1.0.0-py3-none-any.whl (sha256 ok, provenance not checked)
  new: ultra_replica-1.0.1-py3-none-any.whl (sha256 ok, provenance not checked)

ultra_replica-1.0.1-py3-none-any.whl!ultra_replica/__init__.py:6:1: CRT601 [warning] new capability: code-exec (builtins.exec) at import time in ultra_replica
  help: check the release notes and source repository for why 1.0.1 runs dynamically built code
ultra_replica-1.0.1-py3-none-any.whl!ultra_replica/__init__.py:6:1: CRT607 [warning] new obfuscation signal: exec() of base64.b64decode() result at import time
  help: decode the payload by hand (never run it) and read what it does before upgrading
ultra_replica-1.0.1-py3-none-any.whl!ultra_replica/_beacon.py:12:9: CRT601 [warning] new capability: network (socket.create_connection) at import time in ultra_replica._beacon
  help: check the release notes and source repository for why 1.0.1 opens network connections
ultra_replica-1.0.1-py3-none-any.whl!ultra_replica/_beacon.py:18:5: CRT601 [warning] new capability: subprocess (subprocess.Popen) at import time in ultra_replica._beacon
  help: check the release notes and source repository for why 1.0.1 starts processes
ultra_replica-1.0.1-py3-none-any.whl!ultra_replica_init.pth:1:1: CRT603 [error] new .pth file with an executable line: ultra_replica_init.pth
  help: .pth import lines run at every interpreter startup, even if you never import the package

Found 1 error, 4 warnings, 0 info in 2 artifacts (0.12 s).
```
The `exec(base64.b64decode(…))` line gives **two** findings on purpose. CRT601 says "this version can now run dynamically built code", and CRT607 says "and it hides what that code is". They are different facts, and the diff reports both. Order follows 02 §4.4: path, line, column, then code.

Full golden:
```
$ cartographer depdiff ultra-replica 1.0.0 1.0.1 --index-url fixture://ultralytics
Comparing ultra-replica 1.0.0 → 1.0.1
  old: ultra_replica-1.0.0-py3-none-any.whl (sha256 ok, attested: example/ultra-replica .github/workflows/publish.yml)
       ultra_replica-1.0.0.tar.gz (sha256 ok, attested: example/ultra-replica .github/workflows/publish.yml)
  new: ultra_replica-1.0.1-py3-none-any.whl (sha256 ok, attested: example/ultra-replica .github/workflows/publish.yml)
       ultra_replica-1.0.1.tar.gz (sha256 ok, attested: example/ultra-replica .github/workflows/publish.yml)

ultra_replica-1.0.1-py3-none-any.whl!ultra_replica/__init__.py:6:1: CRT601 [warning] new capability: code-exec (builtins.exec) at import time in ultra_replica
  help: check the release notes and source repository for why 1.0.1 runs dynamically built code
ultra_replica-1.0.1-py3-none-any.whl!ultra_replica/__init__.py:6:1: CRT607 [warning] new obfuscation signal: exec() of base64.b64decode() result at import time
  help: decode the payload by hand (never run it) and read what it does before upgrading
ultra_replica-1.0.1-py3-none-any.whl!ultra_replica/_beacon.py:1:1: CRT609 [warning] wheel file ultra_replica/_beacon.py has no counterpart in the sdist
  help: code that exists only in the built wheel was not in the published source; compare with the repository
ultra_replica-1.0.1-py3-none-any.whl!ultra_replica/_beacon.py:12:9: CRT601 [warning] new capability: network (socket.create_connection) at import time in ultra_replica._beacon
  help: check the release notes and source repository for why 1.0.1 opens network connections
ultra_replica-1.0.1-py3-none-any.whl!ultra_replica/_beacon.py:18:5: CRT601 [warning] new capability: subprocess (subprocess.Popen) at import time in ultra_replica._beacon
  help: check the release notes and source repository for why 1.0.1 starts processes
ultra_replica-1.0.1-py3-none-any.whl!ultra_replica_init.pth:1:1: CRT603 [error] new .pth file with an executable line: ultra_replica_init.pth
  help: .pth import lines run at every interpreter startup, even if you never import the package

Found 1 error, 5 warnings, 0 info in 4 artifacts (0.21 s).
Note: both versions are attested by the same publisher. Attestations prove where a file was built, not what it does.
```
Header status words per artefact: `attested: <repo> <workflow path>`, `not attested`, `provenance unknown` (lookup failed) or `provenance not checked` (`--no-provenance`, local mode, or any run before P4 exists). The `--no-provenance` and `--artifacts` flags are implemented from P2, so the MVP golden runs unchanged after P4.

The final `Note:` line is printed (text format only) whenever capability findings exist **and** both versions are attested by the same publisher. It is the Ultralytics lesson, made visible.

### 5.3 Example: provenance lost (`1.0.1 → 1.0.2`)
```
$ cartographer depdiff ultra-replica 1.0.1 1.0.2 --index-url fixture://ultralytics
…
ultra_replica-1.0.2-py3-none-any.whl:1:1: CRT604 [error] provenance lost: 1.0.1 was attested by example/ultra-replica, 1.0.2 has no attestations
  help: an upload without attestations may have used a leaked API token (as with ultralytics 8.3.45); verify with the maintainers

Found 1 error, 0 warnings, 0 info in 4 artifacts (0.18 s).
```
Artefact-level findings (CRT604, CRT605, CRT606 for the archive as a whole) use `line 1, column 1` of the artefact filename as their location.

### 5.4 Exit codes (in addition to [03 §3](../03-cli-config-output.md#3-exit-codes))
| Situation | Exit |
|---|---|
| Version or project not found on the index (HTTP 404 for JSON) | 2 (`UsageError: ultra-replica 9.9.9 not found on https://pypi.org`) |
| Network unreachable / DNS failure after retries / `--offline` with cache miss | 4 (`ToolEnvironmentError`) |
| Downloaded bytes don't match the published SHA-256 | 4 (`ToolEnvironmentError: …sha256 mismatch…`). The file is deleted and never analysed |
| `--dynamic` and Docker not available / daemon not running | 4 |
| No analysable artefact (e.g. only `.egg` files) | 2 |

### 5.5 JSON payload (`--format json`, inside the envelope of 02 §4.8)
```json
{
  "package": "ultra-replica",
  "source": "index",
  "index_url": "fixture://ultralytics",
  "old": {
    "version": "1.0.0",
    "artifacts": [
      {"filename": "ultra_replica-1.0.0-py3-none-any.whl", "kind": "wheel",
       "sha256": "…", "size": 4321, "verified": true, "yanked": false,
       "provenance": {"status": "attested",
                      "publishers": [{"kind": "GitHub", "repository": "example/ultra-replica",
                                      "workflow": "publish.yml", "environment": null}]}}
    ],
    "requires_dist": ["idna>=3"],
    "manifest": {"evidence": [ {"capability": "network", "api": "urllib.request.urlopen",
                  "scope": "call-time", "module": "ultra_replica.fetch",
                  "file": "ultra_replica/fetch.py", "line": 9, "column": 12,
                  "snippet": "urllib.request.urlopen(url, timeout=10)"} ],
                 "entry_points": [], "pth_files": [], "native_files": [],
                 "file_count": 6}
  },
  "new": { "…same shape…": true },
  "diff": {
    "added":   [{"capability": "network", "api": "socket.create_connection",
                 "scope": "import-time", "module": "ultra_replica._beacon", "evidence_count": 1}],
    "removed": [],
    "requires_dist_added": [], "requires_dist_removed": [],
    "entry_points_added": [], "entry_points_removed": []
  },
  "dynamic": null
}
```

## 6. Design

### 6.1 Modules (all under `src/cartographer/depdiff/`)
| Module | Responsibility | Phase |
|---|---|---|
| `__init__.py` | Public exports: `diff_dependency`, `DepDiffResult` | P1 |
| `model.py` | Frozen dataclasses: `ArtifactRef`, `Evidence`, `CapKey`, `Manifest`, `Provenance`, `Publisher`, `DiffResult` | P1 |
| `filenames.py` | Parse wheel and sdist filenames (hand-written, per the wheel spec) | P1 |
| `archive.py` | `ArchiveReader`: validate every member, then give bounded in-memory reads. `safe_extract()` for `--extract-to` | P1 |
| `metadata.py` | Parse `METADATA` (email-header format via `email.parser`), `entry_points.txt` (`configparser`), `RECORD` (csv), `WHEEL`, `top_level.txt` | P1 |
| `transport.py` | `Transport` protocol, `UrllibTransport`, `FixtureTransport` (tests and `fixture://` URLs) | P2 |
| `pypi.py` | JSON API client, artefact selection, the Integrity API (P4) | P2 / P4 |
| `cache.py` | Content-addressed file cache, JSON metadata cache, atomic writes | P2 |
| `fetch.py` | The async fan-out orchestrator | P2 |
| `capabilities.py` | Capability taxonomy + the rule table (qualified name → capability) | P3 |
| `names.py` | Thin layer over C3's `core.qualnames.QualNameResolver` (D-037). It adds only the `getattr(X, "literal")` and `__builtins__` cases. **There is no second resolver** | P3 |
| `static_scan.py` | Walk each module's AST and produce `Evidence`. Scope detection. Obfuscation signals | P3 |
| `entropy.py` | Shannon entropy and long-literal detection | P3 |
| `install_hooks.py` | sdist `setup.py` / `pyproject.toml` build-system analysis. `.pth` analysis | P3 |
| `manifest.py` | Build a `Manifest` from an `ArchiveReader` | P3 |
| `diff.py` | Manifest diff → diagnostics CRT601/602/603/607 | P3 |
| `provenance.py` | Normalise attestation bundles → `Provenance`. Compare → CRT604/605 | P4 |
| `sandbox/Dockerfile`, `sandbox/runner.py`, `sandbox/probe.py` | Container image + in-container scripts (stdlib only; package data) | P5 |
| `dynamic.py` | Build or locate the image, run the container, parse its JSON lines, normalise and diff events → CRT608 | P5 |
| `mismatch.py` | sdist ⇄ wheel comparison → CRT609 | P6 |
| `cli/commands/depdiff.py` | argparse wiring only (D-031) | P1+ |

### 6.2 Data model (`model.py`)
```python
class ArtifactKind(StrEnum):
    WHEEL = "wheel"
    SDIST = "sdist"

@dataclass(frozen=True, slots=True)
class ArtifactRef:
    filename: str                 # "ultra_replica-1.0.1-py3-none-any.whl"
    kind: ArtifactKind
    version: str
    url: str | None               # None in local mode
    sha256: str | None            # published digest (lowercase hex); None in local mode
    size: int | None
    yanked: bool = False
    local_path: Path | None = None   # where the verified bytes live (cache or user path)

class Capability(StrEnum):
    NETWORK = "network"
    SUBPROCESS = "subprocess"
    SHELL = "shell"                       # subprocess with shell=True, os.system, os.popen
    CODE_EXEC = "code-exec"               # eval/exec/compile, marshal/pickle loads, runpy
    DYNAMIC_IMPORT = "dynamic-import"     # __import__, importlib.import_module, spec_from_file_location
    FS_WRITE = "filesystem-write"         # open(w/a/x/+), os.remove/rename/chmod, shutil.rmtree/move/copy
    ENV_READ = "env-read"                 # os.environ, os.getenv
    NATIVE_CODE = "native-code"           # ctypes, cffi, shipped .so/.pyd/.dll/.dylib
    OBFUSCATION = "obfuscation"           # see §6.7.4
    INSTALL_HOOK = "install-hook"         # setup.py code, custom build backend, cmdclass
    STARTUP_HOOK = "startup-hook"         # .pth files with executable lines
    ENTRY_POINT = "entry-point"           # console_scripts / gui_scripts / plugin groups

class Scope(StrEnum):
    INSTALL = "install-time"   # setup.py, in-tree build backends
    STARTUP = "startup"        # .pth files (run at every interpreter start)
    IMPORT = "import-time"     # module-level code (incl. class bodies)
    CALL = "call-time"         # inside a def / lambda; runs only if called

@dataclass(frozen=True, slots=True)
class Evidence:
    capability: Capability
    api: str                   # qualified name ("socket.create_connection"), or a file kind (".pth", ".pyd")
    scope: Scope
    module: str | None         # dotted module name, None for non-module files
    file: str                  # member path inside the archive, posix
    line: int                  # 1-based (1 for whole-file evidence)
    column: int                # 1-based code points
    snippet: str               # ≤ 120 chars of source, single line, never executed

@dataclass(frozen=True, slots=True, order=True)
class CapKey:                  # what the diff compares: NO line numbers (code moves between versions)
    capability: Capability
    api: str
    scope: Scope
    module: str | None

@dataclass(frozen=True, slots=True)
class EntryPoint:
    group: str; name: str; value: str

@dataclass(frozen=True, slots=True)
class Manifest:
    artifact: ArtifactRef
    evidence: tuple[Evidence, ...]              # sorted by (file, line, column, capability)
    entry_points: tuple[EntryPoint, ...]
    pth_files: tuple[str, ...]
    native_files: tuple[str, ...]
    requires_dist: tuple[str, ...]
    file_count: int
    anomalies: tuple[Diagnostic, ...]           # CRT606 found while reading
    def keys(self) -> frozenset[CapKey]: ...
    def evidence_for(self, key: CapKey) -> tuple[Evidence, ...]: ...

@dataclass(frozen=True, slots=True)
class Publisher:
    kind: str                  # e.g. "GitHub", "GitLab"
    repository: str | None     # "owner/repo"
    workflow: str | None       # file name, e.g. "publish.yml"
    environment: str | None

@dataclass(frozen=True, slots=True)
class Provenance:
    status: Literal["attested", "none", "unknown"]   # unknown = lookup failed / skipped
    publishers: tuple[Publisher, ...]
```

### 6.3 Artefact selection (`pypi.py`)
Input: the JSON API response for `<index>/pypi/<project>/<version>/json` (**Provisional, S-08**, confirming the fields: `urls[]` with `filename`, `packagetype` (`"bdist_wheel"` / `"sdist"`), `digests.sha256`, `url`, `size`, `yanked`).

Rules, applied identically to OLD and NEW:
1. Ignore anything that is not a wheel (`.whl`) or an sdist (`.tar.gz`, `.zip`).
2. **Wheel choice:**
   a. Prefer a **pure** wheel: every tag triple has `abi == "none"` and `platform == "any"` (e.g. `py3-none-any`, `py2.py3-none-any`).
   b. Otherwise rank the platform wheels by: (i) an interpreter tag matching `target-version` (`cp315` for 3.15) or `abi3`; (ii) platform order from config `depdiff.platform-preference` (default `["manylinux_*_x86_64", "manylinux2014_x86_64", "musllinux_*_x86_64", "win_amd64", "macosx_*_arm64", "macosx_*_x86_64"]`, glob-matched); (iii) the filename, lexicographically, as a final tie-breaker (determinism).
   c. If the chosen wheels for OLD and NEW have different platform tags, add `payload.notes += ["old and new wheels were built for different platforms: …"]`, because the diff may show noise.
3. **Sdist choice:** the single sdist. If several exist, prefer `.tar.gz`, then lexicographic order.
4. `--artifacts wheel|sdist` restricts the choice. If a side has no artefact of the requested kind, that side is analysed with what exists, and a note says so. CRT609 needs both kinds on the NEW side and is skipped otherwise (a note in the payload).
5. Yanked files are analysed anyway and get `yanked: true`, plus a WARNING log line ("1.0.1 is yanked: reason …").

**Wheel filename parsing** (`filenames.py`), per the binary distribution format spec: `{distribution}-{version}(-{build tag})?-{python tag}-{abi tag}-{platform tag}.whl`. Tags may be compressed with `.` (`py2.py3`). Split on `-`. There must be 5 or 6 parts. Expand each compressed tag with `.` and take the cartesian product of triples. Invalid filename → the artefact is skipped with a log line (not a crash). A Hypothesis round-trip test generates valid names.

### 6.4 Transport, retries and the cache
```python
class Transport(Protocol):
    def get(self, url: str, *, headers: Mapping[str, str], timeout: float) -> Response: ...

@dataclass(frozen=True, slots=True)
class Response:
    status: int
    headers: Mapping[str, str]      # lower-cased keys
    body: bytes                     # for downloads: streamed to disk instead (see below)
```
- `UrllibTransport` uses `urllib.request.urlopen(Request(url, headers=…), timeout=…)`. `HTTPError` is converted into a `Response` (so 404/429/5xx are data, not exceptions). `URLError`/`TimeoutError`/`OSError` raise `TransientNetworkError`.
- `User-Agent: cartographer-py/<version> (+https://github.com/Kar6677thik/Cartographer)`. PyPI asks clients to identify themselves.
- **Only `https://` and `fixture://` schemes are accepted.** Anything else is a `UsageError`. Redirects are followed by urllib only if the target is also `https`.
- `FixtureTransport` maps `fixture://<name>/…` URLs to files under `tests/fixtures/pypi/<name>/` (recorded or generated responses, §6.12). Tests always use it, because tests never touch the network (D-013).
- **Retries:** at most `depdiff.retries` (default 3) extra attempts, only for `TransientNetworkError`, 429, 500, 502, 503 and 504. Delay = `min(cap, base · 2^attempt) · jitter`, with `base = 0.5 s`, `cap = 8 s` and `jitter` uniform in `[0.5, 1.5)` from an **injected** `random.Random` (seeded in tests). If a `Retry-After` header holds a number of seconds ≤ 60, that value is used instead. Sleeping uses `await asyncio.sleep`, so it can be cancelled. Tests use a fake clock.
- **Downloads** stream to `<cache>/tmp/<random>.part` in 64 KiB chunks while computing SHA-256 incrementally (`hashlib.sha256().update`). They abort if the bytes exceed `max-download-mb` (default 200) or the declared `size`. On completion the digest is compared with the published one: if it matches → `os.replace()` into `<cache>/files/<sha256[:2]>/<sha256>/<filename>` (an atomic rename on the same volume). If not → delete the file and raise `ToolEnvironmentError`.
- **Cache layout** (`cache.py`): root from D-025 (`%LOCALAPPDATA%\cartographer\cache`, `~/.cache/cartographer`, or `CARTOGRAPHER_CACHE_DIR`), overridable with `depdiff.cache-dir`.
  - `files/…` is content-addressed. A cached file is reused only after **re-hashing it** (cheap, and it protects against a tampered cache).
  - `json/<index-id>/<project>/<version>.json` holds metadata, with a JSON sidecar `{"fetched_at": <unix>}`. It's reused for `depdiff.metadata-ttl-hours` (default 24) unless `--refresh`. `<index-id>` is the SHA-256 of the index URL, first 16 hex chars.
  - `integrity/<index-id>/<filename>.json` holds provenance, with the same TTL.
- `--offline`: the transport is replaced by one that raises `ToolEnvironmentError("offline: … not in cache")`.

#### 6.4.1 Validating untrusted names before they touch the disk
Filenames, versions and project names in index JSON are **attacker-controlled**: a hostile `--index-url`, or a `depdiff.index-url` set in a cloned repo's `pyproject.toml`, controls them. They become parts of cache paths (`files/…/<filename>`, `json/…/<project>/<version>.json`, `integrity/…/<filename>.json`), so each one is validated **before** any path is built (`pypi.py:validate_index_entry`):

| Value | Must satisfy | Otherwise |
|---|---|---|
| `filename` | parses as a wheel name (§6.3 grammar) or an sdist name `{name}-{version}.tar.gz` / `.zip`; matches `^[A-Za-z0-9._+!-]+$`; contains none of `/`, `\`, `:`, NUL, and no `..` component; isn't a Windows reserved name (§6.6 `windows-unsafe-name` rules); is ≤ 200 characters; **equals the last path segment of its `url`** (after percent-decoding) | the entry is skipped with a WARNING log `ignoring index entry with unsafe filename: <display_text(name)>`. If that leaves no artefact, exit 2 |
| `version` (requested and reported) | matches the PEP 440 public-version pattern `^[0-9][0-9A-Za-z.+!-]*$`, ≤ 64 characters, no `..` | `UsageError` (exit 2) for user input; the entry is skipped for index data |
| project name | already normalised by PEP 503 to `^[a-z0-9]+(-[a-z0-9]+)*$` | `UsageError` |
| `url` | `https://` (or `fixture://` in tests), with no userinfo (`user:pass@`) | the entry is skipped |

As defence in depth, `cache.py` also asserts that every final path `is_relative_to(cache_root)` before it writes, and treats a violation as a bug (`AnalysisError`, exit 3).

### 6.5 Async fan-out (`fetch.py`)
**Why async here:** a run needs about 2 metadata requests, up to 4 downloads and up to 4 provenance lookups. Done one after another, total time is the sum of the round trips. Done concurrently, it's roughly the slowest one. This is the only place Cartographer uses concurrency (D-022).

```
async def fetch_all(project, old, new, cfg, transport, clock, rng) -> FetchResult:
    sem = asyncio.Semaphore(cfg.concurrency)                  # default 8 (D-025)
    async def call(fn, *args):                                # every network call goes through here
        async with sem:
            return await with_retries(lambda: asyncio.to_thread(fn, *args), cfg, clock, rng)

    async with asyncio.timeout(cfg.total_timeout_s):          # default 300 s for the whole fan-out
        async with asyncio.TaskGroup() as tg:                 # stage 1: metadata
            t_old = tg.create_task(call(get_json, project, old))
            t_new = tg.create_task(call(get_json, project, new))
        arts = select(t_old.result()) + select(t_new.result())
        async with asyncio.TaskGroup() as tg:                 # stage 2: files + provenance in parallel
            dl  = {a: tg.create_task(call(download, a)) for a in arts}
            prv = {a: tg.create_task(call(get_provenance, a)) for a in arts} if cfg.provenance else {}
    return FetchResult(...)
```
Rules and teaching points (each one a why-comment in the code):
- **`asyncio.to_thread`** runs the blocking `urlopen` in a worker thread, so the event loop isn't blocked. That's the C3 `blocking-call-in-async` lesson in reverse.
- **`TaskGroup` cancellation:** if one task fails (for example a 404 for NEW), the group cancels its siblings and raises an `ExceptionGroup`. We unwrap it with `except* UsageError` / `except* ToolEnvironmentError` and re-raise the first error of the highest-priority class (UsageError > ToolEnvironmentError > other).
- **Threads can't be cancelled.** Cancelling the awaiting task doesn't stop the thread. It keeps running until its own socket `timeout` (`depdiff.request-timeout-s`, default 30) fires. That's why every `urlopen` has a per-request timeout as well as the overall `asyncio.timeout`. The concept note demonstrates this.
- **Provenance failures never fail the run:** `get_provenance` catches network errors itself and returns `Provenance("unknown", ())`.
- `KeyboardInterrupt` → exit 130 (03 §3). Partial `.part` files are deleted in a `finally`.
- Local mode skips `fetch_all` entirely.

### 6.6 Hostile-archive validation (`archive.py`) → CRT606
**Cartographer never extracts archives onto the host for analysis.** `ArchiveReader` validates the member list, then reads individual members **into memory** with hard caps. The only host extraction is the explicit `--extract-to DIR` debug aid, which uses the same validation plus `safe_extract()`.

Limits (config `[tool.cartographer.depdiff.limits]`, defaults):
| Key | Default | Applies to |
|---|---|---|
| `max-members` | 20 000 | number of entries |
| `max-total-mb` | 500 | sum of declared uncompressed sizes |
| `max-member-mb` | 100 | any single entry (declared and actually read) |
| `max-ratio` | 100 | ZIP: `file_size / max(compress_size, 1)` per entry |
| `max-path-length` | 240 | characters of an entry name (Windows' 260-char limit, minus headroom) |
| `max-py-file-kb` | 2048 | `.py` files larger than this are listed but not parsed (CRT003 info) |

Per-member checks, all producing **one CRT606 per anomaly** (with `data.reason`):
| `reason` | Condition |
|---|---|
| `absolute-path` | name starts with `/` or `\`, or matches `^[A-Za-z]:` (drive letter), or starts with `\\` (UNC) |
| `path-traversal` | any component (after splitting on `/` **and** `\`) equals `..` |
| `nul-in-name` | name contains `\x00` |
| `symlink` | ZIP: `(external_attr >> 16) & 0o170000 == 0o120000`. tar: `issym()` |
| `hardlink` | tar: `islnk()` |
| `special-file` | tar: `ischr() / isblk() / isfifo() / isdev()` |
| `duplicate-name` | the same normalised name appears twice (ZIP allows it, and readers disagree on which wins) |
| `case-collision` | two names equal after `casefold()` + Unicode NFC but different as written. They would overwrite each other on Windows/macOS |
| `too-many-members` / `too-large` / `ratio-exceeded` / `path-too-long` | the limits above |
| `size-lie` | The header doesn't match the data. **ZIP:** reading the member raises `zipfile.BadZipFile`. `zipfile` never returns more than the declared `file_size`, so a lying header shows up as a CRC-32 mismatch ("Bad CRC-32") or a local-header/central-directory inconsistency, not as extra bytes. **tar:** the member's data ends before its header `size` (`tarfile.ReadError` / short read). Either way the member is discarded and none of its bytes are analysed |
| `windows-unsafe-name` | a path component is unusable or dangerous on Windows: a reserved device name (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`, `CONIN$`, `CONOUT$`, case-insensitive, with or without an extension, e.g. `con.py`), ends with a space or `.`, or contains `:` (NTFS alternate data streams), `<>"\|?*` or a control character. Checked with `ntpath.isreserved(component)` when the running Python has it (`getattr(ntpath, "isreserved", None)`, since it's new in 3.13: verify in P1), **plus** a hand-written list that is always applied, so results never depend on the interpreter or OS |
| `encrypted` | ZIP flag bit 0 set (wheels must never be encrypted) |
| `record-mismatch` | wheel only: a file's hash or size doesn't match `RECORD`, or a file is missing from `RECORD` (except `RECORD` itself and `*.jws`/`*.p7s` signatures) |
| `bad-archive` | `zipfile.BadZipFile` / `tarfile.TarError` / truncated. The **whole artefact** is unanalysable, and the manifest is empty with only this anomaly |

**Untrusted names in output (D-050).** Member names come from the attacker. Every member name that goes into a diagnostic `message`, `help` or `Location.path` passes through `core.diagnostics.display_text()`, which escapes newlines, ANSI escape sequences and other control characters, lone surrogates and trailing dots/spaces. The **raw** name goes into `data.member` (JSON-escaped by `json.dumps`). So a member named `evil\n.py` is shown as `evil\x0a.py`, and a name containing `\x1b[2J` can't clear your terminal. The same applies to filenames and versions from index JSON (§6.4.1).

#### 6.6.1 Reading model

- **ZIP (wheels, `.zip` sdists):** `zipfile.ZipFile` reads the central directory when it opens. That's bounded, because the file itself is bounded by `max-download-mb`. Right after opening, `len(infolist())` is checked against `max-members`, then every entry is validated, all **before any member data is read**. `read(member)` uses `ZipFile.open(info)` and reads in 64 KiB chunks. It counts bytes and stops at `min(declared, max-member-mb)`. A `BadZipFile` during a read is a `size-lie` anomaly.
- **tar.gz sdists: a single streaming pass.** We **never call `getmembers()`**. It would read and keep every header in memory before we could check anything, which is exactly what a bomb with millions of tiny members exploits. Instead:
  ```
  raw    = open(path, "rb")
  gz     = CountingReader(gzip.GzipFile(fileobj=raw), limit=max_total_mb * MiB + TAR_OVERHEAD)  # counts DEcompressed bytes
  tar    = tarfile.open(fileobj=gz, mode="r|")     # "r|" = stream mode: sequential, no seeking, no index
  count  = 0
  for info in tar:                                 # next() reads one header at a time
      count += 1
      if count > max_members: anomaly("too-many-members"); unanalysable = True; break
      problems = validate(info)                    # the same table as above
      if not problems and wanted(info.name):       # .py .pyi .pth .toml .cfg .txt PKG-INFO setup.py
          data = bounded_read(tar.extractfile(info), info.size, max_member_mb)
          buffered[info.name] = data               # total buffered ≤ max-total-mb
  ```
  `CountingReader.read()` raises `ArchiveLimitExceeded` once decompressed bytes exceed the limit, which becomes CRT606 `too-large`, and the artefact is marked unanalysable. The total ratio `decompressed / compressed` is checked against `max-ratio` as well. `TAR_OVERHEAD` = 512 bytes × `max-members` (one header block per member). Because stream mode can't go back, `ArchiveReader.read()` for tar serves members from `buffered`. Members that weren't buffered (not `wanted`) can't be read, and that's deliberate.
- **Members that failed validation are never read**, in either format.

#### 6.6.2 `ArchiveReader` API (consumed by `manifest.py`, `mismatch.py`, `--extract-to` and C8 §6.9)
```python
@dataclass(frozen=True, slots=True)
class Member:
    name: str                                  # raw name as stored in the archive (UNTRUSTED)
    display: str                               # display_text(name), safe to print (D-050)
    size: int                                  # declared uncompressed size
    kind: Literal["file", "dir", "symlink", "hardlink", "special"]
    ok: bool                                   # passed every §6.6 check

class ArchiveReader:
    @classmethod
    def open(cls, path: Path, kind: ArtifactKind, *, display_name: str,
             limits: ArchiveLimits) -> "ArchiveReader": ...
        # Never raises for hostile content: problems become anomalies.
        # Raises OSError only if `path` itself can't be read.
    display_name: str                          # artefact filename used in Location.path
    members: tuple[Member, ...]                # archive order
    anomalies: tuple[Diagnostic, ...]          # CRT606, sorted
    unanalysable: bool                         # bad-archive / too-many-members / too-large / ratio-exceeded (total)
    def read(self, name: str) -> bytes: ...    # ok "file" members only; bounded; KeyError otherwise
    def iter_files(self, suffixes: tuple[str, ...] | None = None) -> Iterator[tuple[Member, bytes]]: ...
        # readable ok files, in archive order (tar: only buffered members)
    def close(self) -> None: ...               # also a context manager (__enter__/__exit__)
```

`safe_extract(reader, dest)` (debug aid only): refuses if `dest` exists and isn't empty. For each validated regular file it computes `target = (dest / name).resolve()` and asserts `target.is_relative_to(dest.resolve())` (defence in depth), creates parents, and writes with `open(target, "xb")`, where `x` refuses to overwrite. For tar sdists it makes a **second streaming pass** and calls `tar.extract(info, dest, filter="data")` only for members that passed our validation (two independent layers; the `data` filter also strips dangerous permission bits). Members with any anomaly, including `windows-unsafe-name`, are never extracted, so `--extract-to` behaves the same on Windows and Linux. Nothing extracted is ever executed or imported.

### 6.7 Static capability manifest (`names.py`, `static_scan.py`, `capabilities.py`)

#### 6.7.1 Which files
- Wheel: every `*.py` member outside `*.dist-info/`, mapped to a module name. Members under `<name>.data/purelib/` and `platlib/` are stripped of that prefix. Members under `<name>.data/scripts/` are scanned with module `None` and scope `call-time` (they run when invoked).
- sdist: the top directory (`pkg-1.0/`) is stripped. Then `setup.py` (scope **install-time**), `pyproject.toml` (§6.8), and all `*.py` under the detected package roots (`src/` if present, else the stripped root). Test directories (`tests/`, `test/`, `testing/`, `docs/`, `examples/`) are excluded from capability scanning in sdists, because they never get installed. They are still checked by CRT606.
- Non-Python files of interest: `*.pth` (§6.8), and native files with suffixes `.so`, `.pyd`, `.dll`, `.dylib` (evidence `native-code`, `api` = the suffix, scope `import-time` if inside a package dir, line 1).
- **Suppression comments inside artefacts are never honoured (D-050, D-051).** A malicious package could otherwise add `# cartographer: ignore-file[CRT601, CRT607]` to its own code and hide its findings. Artefact locations contain `!`, so the suppression provider returns `None` for them. C6 also never builds a `PythonSuppressionProvider` over artefact sources. Suppressions in the **user's** project config (`ignore`, `per-file-ignores` matched against the `!` path) still work, because the user controls those.

#### 6.7.2 Qualified-name resolution (`names.py`, reusing `core.qualnames`)
Goal: turn the expression in `sp.run(...)` into `"subprocess.run"`.

**We reuse C3's `QualNameResolver` (C3 §6.3, D-037) unchanged.** Its scope rules, relative-import handling (against the module name derived from the archive member path), star-import pollution and builtin fallback (`"builtins.<name>"` only when no scope binds the name) are exactly what C6 needs. That includes E8: `exec = my_exec` makes `exec` an `other` binding, so it resolves to `None`. A second resolver would drift from the first and give two answers to the same question.

`names.py` adds a function `qualify(resolver, expr, scope_chain) -> tuple[str | None, bool]` (the bool is `via_getattr`), which handles two cases before delegating:
```
def qualify(resolver, expr, scope_chain):
    # Case 1: getattr with a literal attribute name. Attackers use it to hide calls.
    if expr is Call(func=f, args=[X, Constant(str s)], keywords=[]) \
       and resolver.resolve(f, scope_chain) == "builtins.getattr":
        base = qualify(resolver, X, scope_chain)[0]
        return (base + "." + s, True) if base else (None, False)
    # Case 2: __builtins__ used as a namespace, e.g. __builtins__.exec or getattr(__builtins__, "exec").
    # It's a module in __main__ and a dict elsewhere; either way the target is the builtins module.
    if expr is Name("__builtins__") and resolver.resolve(expr, scope_chain) in (None, "builtins.__builtins__") \
       and not bound_in_any_scope("__builtins__"):
        return ("builtins", False)
    if expr is Attribute(Name("__builtins__"), attr) and qualify(resolver, Name("__builtins__"), ...)[0] == "builtins":
        return ("builtins." + attr, False)
    return (resolver.resolve(expr, scope_chain), False)
```
`via_getattr = True` evidence also produces an obfuscation signal (§6.7.4 rule 3). Method calls on instances (`Path(p).write_text`) resolve to `None` here and are handled by the receiver rule in §6.7.3.

Complexity: the `QualNameResolver` pre-pass is O(N) per module, and each `qualify` call is O(scope depth + attribute-chain length).

> **If C3's resolver needs to change** to support these cases more cleanly, change it in `core/qualnames.py` (with C3's tests still passing) instead of forking the logic here.

#### 6.7.3 Rule table (`capabilities.py`)
A tuple of `CapabilityRule(pattern: str, capability: Capability, kind: Literal["call", "attr"])`. `pattern` is an exact qualified name, or ends in `.*` to match any attribute below that prefix. `kind="call"` matches `ast.Call.func`. `kind="attr"` matches any `Attribute`/`Name` load, used for `os.environ`, which is usually subscripted rather than called.

| Capability | Patterns (initial set; extending the table needs only a test) |
|---|---|
| network | `socket.socket`, `socket.create_connection`, `socket.create_server`, `socket.getaddrinfo`, `socket.socket.connect` (via-getattr only), `urllib.request.urlopen`, `urllib.request.Request`, `urllib.request.build_opener`, `http.client.HTTPConnection`, `http.client.HTTPSConnection`, `ftplib.*`, `smtplib.*`, `xmlrpc.client.ServerProxy`, `asyncio.open_connection`, `requests.*`, `httpx.*`, `aiohttp.*`, `urllib3.*`, `websocket.*`, `websockets.*` |
| subprocess | `subprocess.Popen`, `subprocess.run`, `subprocess.call`, `subprocess.check_call`, `subprocess.check_output`, `os.execv`, `os.execve`, `os.execl*`, `os.execvp*`, `os.spawn*`, `os.posix_spawn`, `os.posix_spawnp`, `os.startfile`, `pty.spawn`, `asyncio.create_subprocess_exec` |
| shell | `os.system`, `os.popen`, `subprocess.getoutput`, `subprocess.getstatusoutput`, `asyncio.create_subprocess_shell`, **and** any `subprocess` rule above when the call has `shell=True` with a literal `True` (then `api` = `"subprocess.run[shell=True]"`, and the capability is `shell` *instead of* `subprocess`) |
| code-exec | `builtins.eval`, `builtins.exec`, `builtins.compile`, `marshal.loads`, `marshal.load`, `pickle.loads`, `pickle.load`, `pickle.Unpickler`, `runpy.run_path`, `runpy.run_module`, `code.InteractiveInterpreter`, `types.CodeType`, `types.FunctionType` |
| dynamic-import | `builtins.__import__`, `importlib.import_module`, `importlib.__import__`, `importlib.util.spec_from_file_location`, `importlib.util.module_from_spec`, `importlib.machinery.SourceFileLoader`, `zipimport.zipimporter` |
| filesystem-write | `builtins.open` / `io.open` / `os.open` **only when** the mode argument (2nd positional or `mode=`) is a string literal containing any of `w a x +`; `os.remove`, `os.unlink`, `os.rmdir`, `os.removedirs`, `os.rename`, `os.replace`, `os.chmod`, `os.chown`, `os.symlink`, `os.link`, `shutil.rmtree`, `shutil.move`, `shutil.copy*`, `pathlib.Path.write_text`, `pathlib.Path.write_bytes`, `pathlib.Path.unlink` (these three match only when written as `Path(...).method`, where the receiver is a `Call` whose func qualifies to `pathlib.Path`) |
| env-read | attr: `os.environ`, call: `os.getenv`, `os.getenvb` |
| native-code | `ctypes.CDLL`, `ctypes.WinDLL`, `ctypes.PyDLL`, `ctypes.OleDLL`, `ctypes.cdll.LoadLibrary`, `ctypes.windll.*`, `ctypes.util.find_library`, `cffi.FFI` + shipped native files (§6.7.1) |

`open()` with a non-literal mode is recorded as `filesystem-write` with `api = "builtins.open[mode?]"`. That's an over-approximation, documented. Each matched node becomes one `Evidence`. Each `(file, line, column, capability, api)` is recorded at most once.

#### 6.7.4 Obfuscation signals (`entropy.py`, part of `static_scan.py`) → CRT607
Evidence with `capability = obfuscation`, created when **any** of these holds:
1. **Decode-then-execute:** a `code-exec` or `dynamic-import` call whose argument subtree contains a call qualifying to any *decoder*: `base64.b64decode`, `base64.b32decode`, `base64.b16decode`, `base64.a85decode`, `base64.b85decode`, `base64.decodebytes`, `binascii.a2b_base64`, `binascii.unhexlify`, `bytes.fromhex`, `zlib.decompress`, `lzma.decompress`, `bz2.decompress`, `gzip.decompress`, `codecs.decode`, `marshal.loads`. `api` = `"builtins.exec(base64.b64decode)"`, the outer and inner names.
2. **High-entropy literal:** a `str` or `bytes` constant of length ≥ `depdiff.long-literal-min` (default 512) with Shannon entropy ≥ `depdiff.entropy-threshold` (default 4.8 bits/char). `api` = `"literal[entropy=5.97,len=4096]"`, with entropy rounded to 2 decimals.
   *Why 4.8:* English text sits around 4.0–4.5 bits/char, base64 around 6.0, hex around 4.0. So 4.8 catches base64 blobs, deliberately misses hex, and avoids prose. The concept note shows the measurements, and the write-up recalibrates the threshold on 20 real packages.
   Entropy: `H = −Σ p(c)·log2 p(c)` over characters (or bytes). O(n).
3. **getattr indirection to a dangerous API:** `getattr(os, "system")` or `getattr(__builtins__, "exec")` with a literal string. This creates normal evidence for the resolved API **plus** obfuscation evidence `api = "getattr→os.system"`.
4. **`__import__` with a non-literal argument combined with a decoder** (covered by rule 1, listed separately in the concept note).

#### 6.7.5 Scope detection
Walk with a stack of enclosing nodes. If any ancestor is a `FunctionDef`, `AsyncFunctionDef` or `Lambda`, scope = `call-time`. Otherwise `import-time` (module level, `if`/`try` blocks and **class bodies**, which execute at import). Overrides: anything in sdist `setup.py` is `install-time`, and in-tree build backends are `install-time` (§6.8). One more rule: `if __name__ == "__main__":` blocks at module level are `call-time`, because they don't run on import.

### 6.8 Install-time and startup hooks (`install_hooks.py`)
- **sdist `setup.py`:** if present, add `Evidence(INSTALL_HOOK, api="setup.py", scope=INSTALL, line=1)`. Then scan it like a module with scope forced to `install-time`, so `setup.py` opening a socket yields `network/install-time`. A `cmdclass=` keyword passed to a call qualifying to `setuptools.setup` / `distutils.core.setup` adds `INSTALL_HOOK api="setup.py:cmdclass"` (custom build commands are a classic install-time hook).
- **sdist `pyproject.toml`:** parsed with `tomllib` (errors → CRT606 `reason="bad-pyproject"`). `[build-system] backend-path` present → `INSTALL_HOOK api="in-tree-backend:<build-backend>"`, and the backend's modules under `backend-path` are scanned with install-time scope. A `build-backend` not in the known list (`setuptools.build_meta`, `setuptools.build_meta:__legacy__`, `hatchling.build`, `flit_core.buildapi`, `pdm.backend`, `poetry.core.masonry.api`, `maturin`, `scikit_build_core.build`, `mesonpy`, `uv_build`) → `INSTALL_HOOK api="unknown-backend:<name>"`.
- **`.pth` files** (wheel root, or `.data/purelib|platlib/` root): always listed in `pth_files`. Each line whose first token is `import` (a line starting with `import ` or `import\t`, which is what `site.py` executes) → `Evidence(STARTUP_HOOK, api=".pth:import", scope=STARTUP, line=n, snippet=line)`. **Provisional (S-11):** record PEP 829's exact 3.15 behaviour in the concept note. The rule is the same either way, because older interpreters still execute those lines.
- **Entry points:** `entry_points.txt` (wheel) is parsed with `configparser` (`interpolation=None`, `delimiters=("=",)`, case-sensitive keys via `optionxform = str`). Each entry → `EntryPoint`, and → `Evidence(ENTRY_POINT, api="<group>:<name>", scope=CALL)`. Entry points in group `console_scripts` or `gui_scripts` matter most for the diff, because they put new commands on `PATH`.

### 6.9 The diff (`diff.py`)
```
added_keys   = new.keys() - old.keys()
removed_keys = old.keys() - new.keys()
for key in sorted(added_keys):                      # CapKey has order=True → deterministic
    ev = new.evidence_for(key)                      # ≥ 1
    primary, rest = ev[0], ev[1:6]                  # related: up to 5 more locations
    code = (CRT602 if key.scope == INSTALL or key.capability == INSTALL_HOOK
            else CRT603 if key.capability == STARTUP_HOOK
            else CRT607 if key.capability == OBFUSCATION
            else CRT601)
    emit(code, location=archive_location(new.artifact, primary), related=rest, data={...})
```
- **Why no line numbers in the key:** between versions, code moves. Comparing `(capability, api, scope, module)` means "1.0.1 has `socket.create_connection` at import time in `ultra_replica._beacon` and 1.0.0 didn't", which is the question we care about.
- **Scope escalation counts as new:** `network/call-time` in OLD and `network/import-time` in NEW is an added key, because running at import is a real behaviour change.
- **Module renames** produce add+remove pairs. That's accepted noise, documented in the write-up.
- **CRT603** also fires when a `.pth` *filename* is new, even if it has no import lines (`data.executable = false`, and the message says "new .pth file: x.pth").
- `ENTRY_POINT` additions go into the payload (`entry_points_added`), **not** diagnostics, except new `console_scripts`/`gui_scripts`, which are CRT601 with `capability = "entry-point"`.
- Removed keys and `requires_dist` changes are payload-only (removal isn't a risk).
- If the wheel and the sdist are both analysed, the **wheel's** manifest is primary (it's what gets installed). The sdist contributes **only** install-time evidence (`setup.py`, backends) to the manifest. That avoids double-reporting.
- CRT606 anomalies from **either** version are emitted, with `data.version`, since an anomalous old version is worth knowing about too.

`archive_location(artifact, ev)` → `Location(path=f"{artifact.filename}!{ev.file}", line=ev.line, column=ev.column)` (02 §4.2 `!` convention).

### 6.10 Provenance (`provenance.py`): **Provisional (S-08)**
- For each selected artefact: `GET <index>/integrity/<project>/<version>/<filename>/provenance`, with header `Accept: application/vnd.pypi.integrity.v1+json` (S-08 confirms the media type).
  - 200 → parse the attestation bundles and extract each bundle's **publisher**: `kind`, `repository`, `workflow`, `environment` (exact JSON field names confirmed by S-08) → `Provenance("attested", publishers)`.
  - 404 → `Provenance("none", ())`.
  - Anything else / network error / `--no-provenance` / local mode → `Provenance("unknown", ())`.
- Per version, `version_provenance` = the provenance of the **wheel** if one was selected, else the sdist.
- **CRT604 `provenance-lost` (error):** OLD status `attested` and NEW status `none`. Never fired on `unknown`. Message: `provenance lost: <old> was attested by <repo>, <new> has no attestations`.
- **CRT605 `publisher-changed` (error):** both `attested`, and the set of `(kind, repository, workflow)` differs. `environment`-only differences are payload notes, not diagnostics (renaming an environment is routine). Message: `publisher changed: example/ultra-replica publish.yml → attacker/ultra-replica release.yml`.
- `data` for both: `{"old_publishers": [...], "new_publishers": [...]}`.
- **What we don't do:** verify signatures (stretch S6-1). The concept note `pypi-and-provenance` explains what PyPI verifies at upload and what an attestation does and doesn't prove.

### 6.11 Dynamic sandbox (`dynamic.py`, `sandbox/`): **Provisional (S-06)**
**Purpose:** see what the package *actually does* on import, and compare OLD with NEW. **Never runs on the host.**

**Image.** `sandbox/Dockerfile`:
```dockerfile
FROM python:3.15-slim            # S-06 confirms the tag; fallback python:3.15
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin sandbox
COPY runner.py probe.py /opt/cartographer/
USER 10001:10001
ENTRYPOINT ["python", "-I", "/opt/cartographer/runner.py"]
```
Image tag: `cartographer-sandbox:<first 12 hex of sha256(Dockerfile + runner.py + probe.py)>`. `dynamic.py` runs `docker image inspect <tag>`. If the image is missing it builds it with `docker build -t <tag> -` using a tar build context built in memory from the package data (no repo directory is ever sent as context). Docker missing (`FileNotFoundError` on `docker`) or `docker info` failing → `ToolEnvironmentError` → exit 4.

**Getting the wheel in: stdin, not mounts.** The wheel bytes are piped to the container's **stdin**, and results come back on **stdout** as JSON lines. No bind mounts, no `docker cp`. *Why:* `--read-only` stops `docker cp` from writing into the container's root filesystem, and bind mounts on Docker Desktop for Windows are slow and expose host paths (R-08). Stdin gives a one-way, size-limited channel. (S-06 verifies this works on Docker Desktop. If it doesn't, the fallback is `docker create` + `docker cp` into a writable volume, documented in the spike.)

**Run command** (built as an argument list, never a shell string):
```
docker run --rm -i --name cartographer-sbx-<uuid8>
  --network none --read-only --tmpfs /tmp:rw,nosuid,nodev,size=512m
  --cap-drop ALL --security-opt no-new-privileges
  --pids-limit 128 --memory 512m --memory-swap 512m --cpus 1
  --user 10001:10001 --env PYTHONDONTWRITEBYTECODE=1
  cartographer-sandbox:<tag>
```
(`/tmp` is **not** `noexec`, because native extensions must be loadable. The concept note explains the trade-off.) Host side: `subprocess.run(args, input=wheel_bytes, capture_output=True, timeout=depdiff.sandbox-timeout-s + 15)`, default 120 + 15 s. On `TimeoutExpired` → `docker kill cartographer-sbx-<uuid8>`, and the version's dynamic result is `{"status": "timeout"}` (payload note, no crash). Wheels larger than `max-download-mb` are refused. **Only wheels run dynamically.** sdists would need building, which is out of scope. If a side has no wheel, the dynamic diff is skipped with a note. **If an artefact has any CRT606 anomaly, it isn't run** (note: "refused: archive anomalies").

**`runner.py`** (stdlib only, inside the container):
1. Read stdin to `/tmp/in.whl` (cap 200 MB), unzip to `/tmp/site/` with `zipfile` (the host has already validated it).
2. Determine the top-level modules: `*.dist-info/top_level.txt` if present, else the directories containing `__init__.py` plus top-level `*.py` files (excluding `*.dist-info`, `*.data`).
3. Run **one probe per step**, each as a fresh `python -I /opt/cartographer/probe.py <step>` subprocess with `timeout=depdiff.probe-timeout-s` (default 15):
   - step `site`: calls `site.addsitedir("/tmp/site")`, which **processes `.pth` files** exactly as Python startup would;
   - step `import:<module>` for each top-level module: `sys.path.insert(0, "/tmp/site")`, then `importlib.import_module(module)`.
4. Forward each probe's JSON lines to stdout, adding `{"step": …, "exit": rc, "timed_out": bool}`.

**`probe.py`** installs an audit hook (`sys.addaudithook`) **before** doing its step, and writes one JSON line per *interesting* event to a saved duplicate of the stdout file descriptor (so the package's own `print`s can't spoof events; package stdout/stderr go to `/dev/null`). Interesting events (**Provisional (S-06)**: the spike lists which actually fire on 3.15): `socket.connect`, `socket.getaddrinfo`, `socket.bind`, `subprocess.Popen`, `os.system`, `os.exec`, `os.posix_spawn`, `os.spawn`, `os.fork`, `open` (only when the mode includes `w`, `a`, `x` or `+`, or the path is outside `/tmp/site` and the stdlib prefix), `exec` (only code objects whose filename isn't a real file under `/tmp/site` or the stdlib, i.e. dynamically built code), `compile` (only source not read from a file: filename `<string>` or similar), `ctypes.dlopen`, `urllib.Request`, `os.remove`, `os.rename`, `os.chmod`, `shutil.rmtree`, `os.putenv`, `marshal.loads`, `pickle.find_class`. The hook must never raise and must guard against re-entrancy (a flag), because writing JSON triggers its own events. The concept note `audit-hooks` explains why hooks are **observation, not a sandbox**: code can detect them, and some C-level actions raise no events. **The container is the sandbox.**

**Normalisation** (host side): each event → `(event, normalised_args)`. Paths starting `/tmp/site/` become `<pkg>/…`, other `/tmp/` paths become `<tmp>/…`. Socket addresses stay `host:port`. `subprocess.Popen` keeps the executable basename and the argv with the same path normalisation. PIDs, fds and object reprs are dropped. The result is a set of normalised events per step, with counts.

**Diff → CRT608 `new-runtime-behavior` (warning):** for each normalised `(step, event, args)` present in NEW but not OLD, one diagnostic. Location = the NEW wheel at line 1, column 1 (runtime events have no source line). `data = {"step": "import:ultra_replica", "event": "socket.connect", "args": "192.0.2.1:9", "count": 1}`. Message: `new runtime behaviour on import of ultra_replica: socket.connect 192.0.2.1:9`.

### 6.12 Test fixtures: recorded responses and the replica
- `tests/fixtures/pypi/recorded/<project>/`: JSON API and Integrity API responses for **one real upgrade** of a small, attested package, chosen in S-08. Recorded once by `scripts/record_pypi.py` (network, run manually), with the artefacts' SHA-256 values. **Artefact bytes aren't committed** for real packages. Tests that need bytes use the replica.
- **Replica** (`tests/fixtures/replicas/ultralytics/`), benign by construction and labelled as such in its `README.md`:
  - `src/v1.0.0/ultra_replica/…`: a tiny clean package (`fetch.py` with a call-time `urllib.request.urlopen`, so OLD already has *some* network capability; the diff has to find *new* ones).
  - `src/v1.0.1/`: adds, at **import time**:
    - `__init__.py` line 6: `exec(base64.b64decode("cHJpbnQoJ3JlcGxpY2EgcGF5bG9hZDogdGhpcyB3b3VsZCBoYXZlIGJlZW4gYSBtaW5lcicp"))`, which decodes to `print('replica payload: this would have been a miner')`;
    - `_beacon.py`: `socket.create_connection(("192.0.2.1", 9), timeout=0.01)` inside `try/except OSError: pass`. **192.0.2.0/24 is TEST-NET-1**, a range reserved for documentation that is never routed. It also starts `subprocess.Popen([sys.executable, "-c", "pass"])`, a "miner stand-in" that does nothing;
    - `ultra_replica_init.pth` containing `import ultra_replica._beacon`;
    - the sdist for 1.0.1 is built from the 1.0.0 file list plus the new `__init__.py`, **without `_beacon.py`**. That mimics Ultralytics, where the malicious code came from the build, not from the source (→ CRT609).
  - Versions 1.0.0 and 1.0.1 are attested by publisher `kind=GitHub`, `repository=example/ultra-replica`, `workflow=publish.yml`, **`environment=null`**. This matches C7's replica `publish.yml`, which has no `environment:` (that's why C7 reports CRT704 on it). The two replicas tell one consistent story.
  - `1.0.2`: same code as 1.0.1, published with **no attestation** (→ CRT604).
  - `1.0.3`: same code, attested by `attacker/ultra-replica` with workflow `release.yml` (→ CRT605).
  - `scripts/build_replicas.py` builds deterministic wheels and sdists with **our own minimal writer**: `zipfile` with fixed timestamps (1980-01-01), sorted entries, generated `METADATA`/`WHEEL`/`RECORD`; `tarfile` with `mtime=0`, `uid=gid=0` and sorted entries. It also generates the matching JSON API documents and synthetic provenance documents (shaped per S-08) into `tests/fixtures/pypi/ultralytics/`. A pytest session fixture runs the same builder into a temp dir, and a test asserts the committed JSON hashes match a fresh build (determinism check). Hostile-archive fixtures (`zip_slip.zip`, `symlink.tar.gz`, `bomb.zip`, `dupe.zip`, `case.zip`, `lying_header.zip`) are built in-test by `tests/unit/depdiff/archives.py` helpers, so no binary blobs get committed.
  - `FixtureTransport` serves `fixture://ultralytics/pypi/ultra-replica/<v>/json`, `…/integrity/…`, and file URLs pointing at the built artefacts.

### 6.13 Edge cases (each one has a test)
| # | Case | Behaviour |
|---|---|---|
| E1 | `OLD == NEW` | runs, and reports nothing new. INFO log "identical versions" |
| E2 | Version exists but has zero files | exit 2, "no files published for X" |
| E3 | Only `.egg` / `.exe` files | exit 2, "no analysable artefacts" |
| E4 | Project name with odd case/underscores | normalised (PEP 503) before the URL is built |
| E5 | A `.py` file that fails to parse (e.g. Python 2 code in an old sdist) | CRT001 with the `!` path. That file contributes no evidence. The run continues |
| E6 | A `.py` file in a non-UTF-8 encoding | decoded per PEP 263 via `tokenize.detect_encoding` on the bytes; failure → CRT002 |
| E7 | `from m import *` | no aliases; `data.star_imports` lists them (possible blind spot) |
| E8 | Name shadowing a builtin (`exec = my_exec`) | `QualNameResolver` sees an `other` binding → `None` → no `code-exec` evidence |
| E9 | `subprocess.run(cmd, shell=flag)` with non-literal `shell` | capability `subprocess`, `api` suffixed `[shell=?]` |
| E10 | The same API used 50 times in a module | one CapKey. Evidence capped at 50 per key in the payload (`truncated: true`) |
| E11 | A wheel with `RECORD` missing | CRT606 `record-mismatch` (`data.detail="RECORD missing"`) |
| E12 | A ZIP with two entries `a.py` and `A.py` | CRT606 `case-collision` |
| E13 | A ZIP entry `pkg\..\..\x.py` (backslashes) | CRT606 `path-traversal` |
| E14 | Huge single-line minified file | parsed normally if ≤ `max-py-file-kb`. Snippets truncated to 120 chars |
| E15 | Network flakes once, then succeeds | the retry succeeds, and a DEBUG log shows the attempt count |
| E16 | Cached file tampered with | re-hash mismatch → deleted and re-downloaded (online) or exit 4 (offline) |
| E17 | Ctrl+C during downloads | exit 130, no `.part` files left behind |
| E18 | `--dynamic` with no Docker | exit 4 *before* any download (checked first) |
| E19 | Probe times out (package sleeps forever on import) | `timed_out: true` for that step; the others continue |
| E20 | Wheel and sdist versions disagree with the requested version | CRT606 `reason="version-mismatch"` (metadata `Version` ≠ requested) |

## 7. Diagnostics

| Code | Trigger (summary; details in §6) | Severity | Location | `data` fields | Example message |
|---|---|---|---|---|---|
| CRT601 `new-capability` | Added CapKey with capability ∉ {install-hook, startup-hook, obfuscation} and scope ∉ {install-time}; or a new console/gui script | warning | first evidence in NEW | `capability`, `api`, `scope`, `module`, `evidence_count`, `old_version`, `new_version` | `new capability: network (socket.create_connection) at import time in ultra_replica._beacon` |
| CRT602 `install-time-code` | Added CapKey with scope install-time, or new `install-hook` evidence | error | `setup.py` / `pyproject.toml` evidence | same as CRT601 | `install-time code gained capability: network (urllib.request.urlopen) in setup.py` |
| CRT603 `pth-file-added` | New `.pth` filename, or a `.pth` gains executable lines | error | the `.pth` member, at the first import line (or line 1) | `pth_file`, `executable` (bool), `lines` (list of str, ≤ 5) | `new .pth file with an executable line: ultra_replica_init.pth` |
| CRT604 `provenance-lost` | OLD attested and NEW none (§6.10) | error | NEW primary artefact, 1:1 | `old_publishers`, `new_publishers` | see §5.3 |
| CRT605 `publisher-changed` | Both attested; publisher set differs | error | NEW primary artefact, 1:1 | same | `publisher changed: example/ultra-replica publish.yml → attacker/ultra-replica release.yml` |
| CRT606 `archive-anomaly` | Any §6.6 anomaly, in either version | error | the member (or the artefact 1:1) | `reason`, `member`, `version`, `detail` | `archive anomaly (path-traversal): ../../evil.py in ultra_replica-6.6.6.tar.gz` |
| CRT607 `obfuscation-signal` | Added obfuscation CapKey | warning | evidence | `api`, `scope`, `module`, `entropy` (if any) | `new obfuscation signal: exec() of base64.b64decode() result at import time` |
| CRT608 `new-runtime-behavior` | New normalised sandbox event | warning | NEW wheel, 1:1 | `step`, `event`, `args`, `count` | `new runtime behaviour on import of ultra_replica: socket.connect 192.0.2.1:9` |
| CRT609 `sdist-wheel-mismatch` | NEW wheel `.py` member with no sdist counterpart, or different content (§9 P6) | warning | the wheel member, 1:1 | `wheel_member`, `sdist_member` (or null), `reason` (`missing` \| `content-differs`) | `wheel file ultra_replica/_beacon.py has no counterpart in the sdist` |

Each code gets its `cartographer explain` text in the phase that implements it (04 §5). The "Why it matters" section of CRT604, CRT607 and CRT609 retells the relevant Ultralytics step.

## 8. Configuration (`[tool.cartographer.depdiff]`)
| Key | Type | Default | Meaning |
|---|---|---|---|
| `index-url` | str | `"https://pypi.org"` | Index base URL |
| `cache-dir` | str \| null | null (D-025 default) | Cache root |
| `metadata-ttl-hours` | int ≥ 0 | 24 | Reuse cached JSON/provenance for this long |
| `concurrency` | int 1–32 | 8 | Semaphore size |
| `request-timeout-s` | float > 0 | 30 | Per-request socket timeout |
| `total-timeout-s` | float > 0 | 300 | Whole fan-out |
| `retries` | int 0–10 | 3 | Extra attempts for transient failures |
| `max-download-mb` | int | 200 | Per artefact |
| `artifacts` | `"wheel"`\|`"sdist"`\|`"both"` | `"both"` | Same as `--artifacts` |
| `provenance` | bool | true | `false` = like `--no-provenance` |
| `platform-preference` | list[str] | see §6.3 | Glob patterns over platform tags |
| `long-literal-min` | int | 512 | Obfuscation literal length |
| `entropy-threshold` | float | 4.8 | bits/char |
| `mismatch-ignore` | list[str] | `["*/_version.py", "*/version.py", "*/_build_info.py"]` | Globs exempt from CRT609 (generated files) |
| `sandbox-image` | str \| null | null (auto-build) | Use a pre-built image instead |
| `sandbox-timeout-s` | int | 120 | Whole container run |
| `probe-timeout-s` | int | 15 | Per probe step |
| `[depdiff.limits]` | table | §6.6 | Archive limits |

## 9. Phases & tasks

Phases **P1–P3 are the MVP** (R-02). If time runs short, P4–P6 may move to the stretch list without failing the milestone. The write-up must then say so, and A-C6-09…A-C6-12 become "deferred".

### P1: Artefacts and hostile archives (MVP) · branch `c6/archives`
- [ ] Write concept notes `wheels-and-sdists`, `archive-safety`, `hashing-and-integrity`.
- [ ] `model.py` (§6.2), `filenames.py` + Hypothesis round-trip test.
- [ ] `archive.py`: `ArchiveReader` (API §6.6.2) for ZIP and **streaming** tar (§6.6.1, no `getmembers()`), with all §6.6 checks (including `windows-unsafe-name`), bounded reads, and `display_text()` for every member name in output (D-050). `safe_extract()`.
- [ ] Hostile-archive builders in `tests/unit/depdiff/archives.py`. 🖐 *Good hands-on task: write the `case-collision` check and its test.*
- [ ] `metadata.py` (METADATA, entry_points.txt, RECORD, top_level.txt).
- [ ] CLI local mode (`--old-file/--new-file`) that prints the artefact list and CRT606 findings, and `--extract-to`.
- [ ] `cartographer explain` for CRT606.

### P2: Index client, cache, async fan-out (MVP) · branch `c6/fetch`
- [ ] **Spike S-08** (PyPI JSON + Integrity API shapes): record a real upgrade with `scripts/record_pypi.py` and write `docs/learn/spikes/S-08-pypi-apis.md`. Update §6.3/§6.10 if needed.
- [ ] Write concept notes `asyncio-fan-out` and `pypi-and-provenance` (part 1: JSON API, hashes, Trusted Publishing overview).
- [ ] `transport.py` (`UrllibTransport`, `FixtureTransport`, the scheme allow-list).
- [ ] `cache.py` (content-addressed files, TTL JSON, atomic writes, re-hash on reuse).
- [ ] `pypi.py` JSON client + selection (§6.3) + `validate_index_entry` (§6.4.1) **before** any cache path is built.
- [ ] `fetch.py` (§6.5) with injected clock and RNG. Retry/backoff tests with a fake transport that fails N times.
- [ ] `--offline`, `--refresh`, exit codes 2/4, Ctrl+C cleanup.

### P3: Static manifest and diff (MVP) · branch `c6/manifest`
- [ ] Write concept note `obfuscation-signals`.
- [ ] `names.py` (`qualify()` over C3's `QualNameResolver`, §6.7.2), `capabilities.py` (rule table), `static_scan.py` (evidence + scope), `entropy.py`, `install_hooks.py`, `manifest.py`.
- [ ] `diff.py` → CRT601, CRT602, CRT603, CRT607. Text/JSON/SARIF output and the §5.2 **MVP** golden (`--no-provenance --artifacts wheel`, T-C6-33).
- [ ] Test that a planted `# cartographer: ignore-file[...]` inside a replica wheel doesn't hide anything (T-C6-31).
- [ ] `scripts/build_replicas.py` + the session fixture + the determinism test. Replica scenarios 1.0.0→1.0.1.
- [ ] 🖐 *Hands-on: add three patterns to the rule table (for example `paramiko.*` → network) with tests.*
- [ ] `explain` texts for CRT601/602/603/607.

### P4: Provenance · branch `c6/provenance`
- [ ] `pypi.py` Integrity API call and `provenance.py` normalisation per S-08.
- [ ] CRT604, CRT605. Replica scenarios 1.0.1→1.0.2 and 1.0.1→1.0.3. The `Note:` line from §5.2.
- [ ] Concept note `pypi-and-provenance` part 2 (attestations, what they prove, the Ultralytics lesson).

### P5: Dynamic sandbox · branch `c6/sandbox`
- [ ] **Spike S-06 Part B** (audit events on 3.15; stdin transport on Docker Desktop for Windows). Part A (the image tag and hardening flags) was done in C2 phase 7. Append the results to `docs/learn/spikes/S-06-sandbox.md` and update §6.11.
- [ ] Write concept notes `audit-hooks` and `containers-and-sandboxing`.
- [ ] `sandbox/Dockerfile`, `runner.py`, `probe.py` (stdlib only, D-005 syntax). Unit-test `probe.py`'s event filter **in-process on the host** against our own harmless code only (never package code).
- [ ] `dynamic.py`: image tag/build, run, timeouts/kill, normalisation, diff → CRT608.
- [ ] `@pytest.mark.docker` integration test on the replica (1.0.0 vs 1.0.1 must show `socket.connect 192.0.2.1:9` and `subprocess.Popen`).

### P6: sdist ⇄ wheel mismatch, acceptance, docs · branch `c6/mismatch`
- [ ] `mismatch.py`: for each NEW wheel `.py` member (excluding `*.dist-info`, `*.data/scripts`, and `mismatch-ignore` globs), find sdist members whose path ends with `/<member path>` (try `src/<path>`, then `<path>` under the stripped sdist root). None → `missing`. Found but `sha256(normalise(content))` differs → `content-differs`, where `normalise` converts `\r\n` to `\n` and strips trailing whitespace on each line. Complexity O(W + S) using a suffix index dict keyed by the last 2 path components.
- [ ] CRT609, replica 1.0.1 test.
- [ ] The §5.2 **full** golden (T-C6-19), which needs P4 (provenance) and CRT609.
- [ ] Acceptance runs (§11), walkthrough, write-up, comparison.

### Stretch list (not required for 0.6.0)
- S6-1 Verify attestation signatures (needs a new dependency, so a decision record first).
- S6-2 Dynamic analysis of sdists (build inside the sandbox).
- S6-3 `depdiff --lock OLD.lock NEW.lock`: run the diff for every changed package in a `uv.lock`.
- S6-4 Diff `Requires-Dist` recursively (new transitive dependencies).
- S6-5 Typosquat signal (edit distance to the top packages).

## 10. Test plan
| ID | What | Kind |
|---|---|---|
| T-C6-01 | Wheel filename parse/format round-trip; compressed tags expand correctly | Hypothesis |
| T-C6-02 | Each CRT606 `reason` in §6.6 fires on its hostile fixture, and the member is never read | unit (one parametrised case per reason) |
| T-C6-03 | Lying-header ZIP (central directory declares a smaller `file_size`/wrong CRC than the real data) → `zipfile.BadZipFile` during the read → CRT606 `size-lie`, and no bytes of that member reach the scanner. Truncated tar member → `size-lie`. Reads never return more than `min(declared, max-member-mb)` bytes | unit |
| T-C6-04 | `safe_extract` refuses non-empty dest, never writes outside dest, never overwrites; tar path also uses `filter="data"` | unit |
| T-C6-05 | RECORD verification: tampered member → `record-mismatch` | unit |
| T-C6-06 | Artefact selection: pure wheel preferred; platform ranking; tie-break determinism; mismatched-platform note | unit (table-driven) |
| T-C6-07 | Download verifies SHA-256; mismatch deletes and raises exit-4 error | unit (fake transport) |
| T-C6-08 | Retries: 2 × 503 then 200 succeeds; `Retry-After` honoured; 404 not retried; delays follow the formula under a seeded RNG + fake clock | unit |
| T-C6-09 | TaskGroup failure on NEW 404 cancels the sibling tasks and gives exit 2 | unit (asyncio) |
| T-C6-10 | Concurrency never exceeds the semaphore (instrumented fake transport records the max in-flight count) | Hypothesis over concurrency 1–16 |
| T-C6-11 | Cache: reuse after re-hash; tampered cache re-downloads; offline miss → exit 4; TTL expiry | unit (tmp cache dir) |
| T-C6-12 | `names.qualify` over C3's resolver: all import forms, `getattr(X, "lit")` (via_getattr), `__builtins__.exec` / `getattr(__builtins__, "exec")`, and shadowed builtins (E8). Also asserts that `names.py` defines no resolver of its own (it imports `core.qualnames`) | unit (table of snippets) |
| T-C6-13 | Every rule-table pattern has at least one positive and one negative snippet test | unit (generated from the table) |
| T-C6-14 | Scope detection: module level, class body, function, lambda, `if __name__ == "__main__"`, setup.py | unit |
| T-C6-15 | Entropy function matches `−Σp log2 p` on random strings; prose < 4.8 and base64 > 4.8 on samples | Hypothesis + unit |
| T-C6-16 | Obfuscation rules 1–3 | unit |
| T-C6-17 | `.pth` detection: import lines vs. path lines; CRT603 for a new file without import lines (`executable=false`) | unit |
| T-C6-18 | Diff: line moves aren't findings; scope escalation is; removals are payload-only; deterministic order | unit + Hypothesis (shuffling the evidence order never changes the output) |
| T-C6-19 | Replica 1.0.0→1.0.1 text output equals golden §5.2 | golden |
| T-C6-20 | Replica 1.0.1→1.0.2 gives CRT604; 1.0.1→1.0.3 gives CRT605; 1.0.0→1.0.1 gives no provenance finding plus the `Note:` line | integration |
| T-C6-21 | Provenance unknown (network error) never yields CRT604 | unit |
| T-C6-22 | CRT609 on replica 1.0.1; `mismatch-ignore` respected; CRLF-only differences ignored | unit |
| T-C6-23 | JSON payload validates against the documented shape (§5.5) and SARIF validates against a minimal SARIF schema check | integration |
| T-C6-24 | Sandbox command line contains every required flag (§6.11) and no `-v`/`--mount` | unit (args inspection, no Docker) |
| T-C6-25 | Replica dynamic diff shows `socket.connect 192.0.2.1:9` and `subprocess.Popen` as CRT608 | `@pytest.mark.docker` |
| T-C6-26 | Probe timeout and `docker kill` path (a fixture wheel whose import sleeps 999 s) | `@pytest.mark.docker` |
| T-C6-27 | Edge cases E1–E20 (one test each, IDs in the docstrings) | unit/integration |
| T-C6-28 | No test opens a real socket: a session fixture monkeypatches `socket.socket.connect` to raise unless `-m network` | guard |
| T-C6-29 | Replica builder is deterministic (two builds → identical bytes) | unit |
| T-C6-30 | Unsafe index entries: filenames `../x.whl`, `a/b.whl`, `c:evil.whl`, `x\0.whl`, `con.whl`, a filename differing from the URL basename, a version `../../1`. Each is skipped or rejected per §6.4.1, nothing is written outside the temp cache root (directory listing before/after), and the `is_relative_to` guard is exercised by calling `cache.py` directly with a bad name | unit (FixtureTransport with a hostile index) |
| T-C6-31 | A replica 1.0.1 variant whose `_beacon.py` starts with `# cartographer: ignore-file[CRT601, CRT607]` and whose `__init__.py` line 6 ends with `# cartographer: ignore[CRT601]` produces **the same findings** as the unmodified replica | integration |
| T-C6-32 | Hostile member names `evil\n.py`, `a\x1b[2J.py`, `trailing.` and `bad\udcff.py` (lone surrogate via `surrogateescape`) never crash (no exit 3). Messages and `Location.path` contain the escaped `display_text` form, `data.member` holds the raw value, and text output contains no raw control characters | unit |
| T-C6-33 | MVP golden (§5.2, `--no-provenance --artifacts wheel`) matches `replica_100_101_mvp.txt` | golden (P3) |
| T-C6-34 | Streaming tar: a tar.gz with `max-members + 1` tiny members stops after `max-members + 1` headers (instrumented reader counts `next()` calls), `getmembers` is never called (monkeypatched to raise), and a gzip whose decompressed size exceeds `max-total-mb` aborts with `too-large` after reading at most the limit plus one chunk | unit |
| T-C6-35 | `windows-unsafe-name`: `con.py`, `pkg/aux.txt`, `x.py.`, `a:b.py`, `nul` → CRT606 on **every** OS (the hand list is always applied), and `--extract-to` never creates them | unit (parametrised) |

## 11. Acceptance criteria
| ID | Criterion |
|---|---|
| A-C6-01 | `cartographer depdiff ultra-replica 1.0.0 1.0.1 --index-url fixture://ultralytics` produces exactly the §5.2 **full** output (golden test T-C6-19 passes on Windows and Ubuntu). |
| A-C6-02 | All 17 CRT606 reasons in the §6.6 table (plus `bad-pyproject` and `version-mismatch`) are detected on their fixtures, and none of those fixtures causes a write outside the temp dir (T-C6-02/04). |
| A-C6-03 | `cartographer depdiff` never writes to the host filesystem except the cache dir and `--output`/`--extract-to` targets. Verified by a test that runs the replica diff with the cache in a temp dir and compares a before/after listing of the temp root and the CWD. |
| A-C6-04 | A tampered download (one flipped byte) is rejected with exit 4 and isn't analysed (T-C6-07). |
| A-C6-05 | With a fake transport adding 200 ms latency to each of 10 requests, `fetch_all` finishes in < 0.6 s at concurrency 8 (versus ≥ 2 s sequential). The timing is asserted on the fake clock, so it is deterministic. |
| A-C6-06 | Rule table: ≥ 60 patterns, each with positive and negative tests (T-C6-13). |
| A-C6-07 | Network-free test suite: `pytest -m "not network and not docker"` passes with sockets blocked (T-C6-28). |
| A-C6-08 | **Real-package run** (`-m network`, run manually once and recorded in the write-up): `depdiff` on the S-08-chosen real upgrade completes in < 60 s, and every reported finding is classified true/false positive in the write-up. |
| A-C6-09 | Replica provenance scenarios produce CRT604 and CRT605 exactly as specified (T-C6-20). |
| A-C6-10 | `--dynamic` on the replica (1.0.0→1.0.1) reports CRT608 for the beacon and the Popen, inside a container started with all §6.11 flags (T-C6-24/25). |
| A-C6-11 | `--dynamic` without Docker exits 4 with a message that names Docker, before any download. |
| A-C6-12 | CRT609 fires for `_beacon.py` on replica 1.0.1 and not on 1.0.0 (T-C6-22). |
| A-C6-13 | `cartographer explain` works for CRT601–609, with all six sections. |
| A-C6-14 | Docs: all eight Stage-6 concept notes ✅, walkthrough, write-up, comparison. |
| A-C6-15 | **MVP line (end of P3):** the §5.2 MVP output is produced exactly (T-C6-33), on Windows and Ubuntu. |
| A-C6-16 | **Untrusted input never escapes its box:** T-C6-30 (unsafe index names), T-C6-31 (planted suppressions) and T-C6-32/T-C6-35 (hostile member names) all pass. |

## 12. Documentation deliverables
- **Concept notes** (Stage 6, owner C6): `wheels-and-sdists`, `archive-safety`, `hashing-and-integrity`, `asyncio-fan-out`, `pypi-and-provenance`, `obfuscation-signals`, `audit-hooks`, `containers-and-sandboxing`. Specific musts:
  - `wheels-and-sdists`: open a real wheel with `zipfile` in a `pycon` session; explain METADATA, RECORD and entry points; explain why sdist installs can run code.
  - `archive-safety`: zip-slip demo against a temp dir showing the *unsafe* outcome with a naive extractor, then our checks; `tarfile` filters.
  - `asyncio-fan-out`: a runnable demo with `asyncio.sleep` standing in for the network, showing sequential vs. concurrent timing; the "threads can't be cancelled" demo.
  - `obfuscation-signals`: an entropy table for English, Python source, hex and base64, measured by a snippet in the note.
  - `audit-hooks`: a `pycon` session registering a hook and printing `open` events, plus a demo showing a hook *can't* stop determined code.
  - `containers-and-sandboxing`: what each `docker run` flag in §6.11 does, one row per flag.
- **Walkthrough** `docs/learn/walkthroughs/C6.md`: trace replica 1.0.0→1.0.1 from `fetch_all` through `ArchiveReader`, `static_scan`, `diff` and the renderer, showing the actual `Evidence` and `CapKey` objects.
- **Write-up** `docs/learn/writeups/C6.md`: the A-C6-08 real-package results with a precision estimate; the entropy-threshold calibration on ≥ 20 popular packages (how many trip CRT607 on their *current* version, which shows the noise); fan-out timing on real PyPI (median of 5 runs, sequential vs. concurrent).
- **Comparison** `docs/learn/comparisons/C6.md`: **GuardDog** (rule format, Semgrep-based source rules vs. our `ast` rules), **Upgrade X-Ray** (read its public description only; it's an Apify actor, so its source may not be available, and say so), **trustcheck** (publisher drift). Questions to answer: Which GuardDog heuristics would we add? How does trustcheck compare publishers? Run GuardDog on replica 1.0.1 and compare the findings table.

## 13. Reference implementations to compare after
| Tool | What to look at | Questions |
|---|---|---|
| GuardDog | source heuristics, metadata heuristics | How do Semgrep rules compare with our qualified-name rules for precision? |
| Upgrade X-Ray | the public description of its diff categories (install hooks, `.pth`, network/shell/eval) | Which categories do we miss? |
| trustcheck | how it detects publisher/workflow drift | Does it handle environment renames the way we do? |
| OpenSSF package-analysis | its sandbox design (gVisor) and the events it captures | What does a stronger sandbox give that Docker doesn't? |
| LastPyMile (paper) | sdist-vs-repo discrepancy method | We compare wheel to sdist, they compare package to repository. Which is stronger, and why? |

## 14. Risks & open items
- **S-06** (sandbox facts; Part A in C2 phase 7, Part B in this milestone's P5) and **S-08** (PyPI APIs) are the two provisional areas. Both have fallbacks in §6.10/§6.11.
- **Scope (D-047):** C6 emits CRT001/CRT002/CRT003 for unparseable, undecodable or oversized `.py` files inside artefacts (E5, E6, `max-py-file-kb`), **in addition to** CRT6xx. D-047's `depdiff` scope must therefore be `CRT001–CRT003 + CRT6xx` (flagged to the foundation docs).
- **R-02**: XL milestone. The MVP line is P1–P3.
- **R-05**: false positives. Popular packages legitimately use network, subprocess and so on, but we only report *additions*, which keeps noise down. Measured in the write-up.
- **R-08**: Docker Desktop specifics. The stdin transport avoids mounts.
- Static analysis can be evaded (`exec(getattr(__import__("b"+"ase64"), …))`). The write-up must include a short "how an attacker would evade this" section, because honesty about limits is part of the lesson.

## 15. Exercises for the learner
1. Download any wheel you use with `uvx pip download --only-binary=:all: --no-deps requests -d tmp` (or click "Download files" on pypi.org) and open it with `python -m zipfile -l tmp\<file>.whl`. `--only-binary=:all:` matters: it refuses sdists. Downloading an sdist with pip may **build** it, which runs its build code on your machine. That is the very thing C6 warns about. Find `METADATA`, `RECORD` and `entry_points.txt`. *Hint:* RECORD lines are `path,sha256=<urlsafe-b64>,size`.
2. Compute the SHA-256 of that wheel with `hashlib` and compare it with the value on its PyPI page. *Hint:* `hashlib.file_digest(f, "sha256")`.
3. Write a 5-line audit hook that prints every `open` event, then import `json`. Why are there so few events? *Hint:* frozen and cached modules.
4. Compute the Shannon entropy of this paragraph and of `base64.b64encode(os.urandom(300))`. *Hint:* `collections.Counter` + `math.log2`.
5. Decode the replica payload in §6.12 **by hand** with `base64.b64decode(...)` and read it. Don't `exec` it, even though you know it's harmless, and practise the habit.
6. Read PyPI's write-up of the Ultralytics attack (research §8, "Security"). Which CRT6xx codes would have fired for 8.3.41, and which for 8.3.45?
