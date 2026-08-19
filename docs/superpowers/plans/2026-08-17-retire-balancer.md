# Retire the Balancer, Gate Config Drift, Fix the Header Dependency — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the two balancer implementations Garage replaced, make an unclassified `#define` fail this repository's tool suite at commit time, and make `make` rebuild the objects that read `src/config.h` when a `#define` changes.

**Architecture:** Three independent pieces that share one spec. The deletions are pure removal plus four dangling citations. The drift check is a new standalone script, `tools/garage_drift_lint.py`, that compares the `#define` names in `src/config.h` against the classification file in a *Garage* checkout it locates by scanning sibling directories for a matching `origin` remote — and which succeeds, loudly saying it did nothing, when no such checkout exists. It is wired in by being exercised from a discovered test module rather than by a Makefile line, so the pre-commit hook gates it too. The Makefile piece is a single prerequisite line.

**Tech Stack:** Python 3 (stdlib only — `re`, `json`, `subprocess`, `unittest`), GNU Make, GBDK-2020 via `lcc`, PowerShell 7 on Windows, `git`, `gh` CLI.

**Spec:** https://github.com/MatthieuGagne/gmb-nuke-raider/issues/612 (read it in full before Task 1; its Notes section carries the reasoning for both the drift check and the header dependency)

## Global Constraints

- **Repository:** `C:\Code\nuke-raider` (`MatthieuGagne/gmb-nuke-raider`). The default branch is **`master`**, not `main`. Do not confuse it with `C:\Code\nuke-raider-garage`, which is a different repository and **must not be modified by this work**.
- **No Garage file changes.** The Garage repository is read from and never written to. `tools/garage/tunables.json` lives there and stays there.
- **No new dependency.** `tools/garage_drift_lint.py` imports only the Python standard library. It must **not** import anything from a Garage checkout, even when one is present — this repository's suite must never break because a repository it does not depend on refactored a module.
- **Unclassified means absent.** A `#define` is classified when `tunables.json` names it under `entries`, whatever its `class` (`tunable`, `structural`, `derived` or `marker`). Spec R4's phrase "neither tunable nor structural" is imprecise: taken literally it would fail on `CONFIG_H` (a `marker`) and on every `derived` entry. Garage's own `tools/garage_lint.py` uses the "absent" reading and the two checks must never disagree.
- **One direction only.** Report a `#define` in `config.h` that `tunables.json` does not classify. Do **not** report the reverse (an entry whose `#define` is gone). Its fix would live in the Garage repository, and this suite must never require a change in a repository it does not own in order to go green.
- **Verified precondition:** at the time of writing, `src/config.h` holds **133** `#define`s and `tunables.json` holds **133** entries, with zero difference in either direction. The check is green on a clean tree. If Task 2 finds otherwise, the discrepancy is real news — stop and report it rather than loosening the check.
- **Captured output.** Every test that runs the check must capture stdout (`contextlib.redirect_stdout`). A passing suite that prints the word `FAIL` trains a reader to skim past it; the sibling repository fixed exactly this in its commit `e404048`.
- **PowerShell syntax throughout.** `2>$null` not `2>/dev/null`, `$env:VAR` not `export`, backtick for line continuation.
- **Never read `$LASTEXITCODE` after a piped command** — the pipe masks it. Run the command bare, check the code on the next line.
- **Commit messages** end with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`, matching this repository's recent history.
- **`make` needs bash and `GBDK_HOME`.** For a Python-only check, run the suite directly: `python -m unittest discover -s tests -p 'test_*.py'` from the repository root. That is byte-identical to what both `make test-tools` and `.githooks/pre-commit` run.

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `tools/balancer.py` | **Delete** | The Python TUI Garage replaced (R1). |
| `tools/balancer/` | **Delete** | A second, Go implementation of the same tool — `main.go`, `go.mod`, `.gitignore` (R1). |
| `tests/test_balancer.py` | **Delete** | Covered `parse_config` and `apply_changes`; Garage carries the equivalent against `tools/garage/core/config_io.py` (R2). |
| `docs/dev-workflow.md` | **Modify** (line 222) | Section 4's guarded-POSIX-import example cites two files; the balancer name goes, `dialog_editor` stays (R3). |
| `tools/dialog_editor.py` | **Modify** (line 40) | A comment citing `tools/balancer.py` as the guard precedent. Not covered by the spec; found while planning. |
| `tests/test_dialog_editor.py` | **Modify** (line 17) | The same citation in a class docstring. Not covered by the spec; found while planning. |
| `tools/garage_drift_lint.py` | **Create** | The drift check: locate a Garage checkout, parse `#define` names, compare against `tunables.json`, exit 1 naming each unclassified name (R4, AC4, AC5). |
| `tests/test_garage_drift_lint.py` | **Create** | Unit coverage for the check, plus the live test that runs it against this repository's real `src/config.h` — which is what actually gates the suite. |
| `Makefile` | **Modify** (compile rule) | `$(OBJS): src/config.h`, so a `#define` edit rebuilds (R5, AC6). |

The Makefile's `test-tools` recipe and `.githooks/pre-commit` are **deliberately not modified**. `test-tools` runs `python -m unittest discover -s tests -p 'test_*.py'`, discovery finds the new module, and the hook runs the identical command — so the drift check gates both, with no Makefile edit and no risk to the byte-identity that `tests/test_repo_hooks.py` enforces. This departs from the spec's "Files Impacted" line, which anticipated an explicit `test-tools` line; the departure is deliberate and gives R4 what its own rationale asks for — the report arriving at the commit that introduces the `#define`.

---

### Task 1: Delete the balancer and repair every citation

**Files:**
- Delete: `tools/balancer.py`, `tools/balancer/` (whole directory), `tests/test_balancer.py`
- Modify: `docs/dev-workflow.md:222`, `tools/dialog_editor.py:40`, `tests/test_dialog_editor.py:17`
- Test: no new test. The deletion is verified by the suite still passing with five fewer tests than the baseline captured in Step 1, and by a repository-wide search finding no surviving reference.

**Interfaces:**
- Consumes: nothing.
- Produces: a tree with no balancer. Task 2 is independent of it, but both land in one PR.

- [ ] **Step 1: Record the baseline before deleting anything**

```powershell
cd C:\Code\nuke-raider
git status --short
git rev-parse --abbrev-ref HEAD
python -m unittest discover -s tests -p 'test_*.py' 2>&1 | Select-Object -Last 4
```

Expected: a final line reading `OK` with a test count. **Write the count down** — Step 8 compares against it. `tests/test_balancer.py` contributes 9 tests (4 in `TestParseConfig`, 5 in `TestApplyChanges`), so the count after deletion must be exactly 9 lower.

The only expected `git status` entry is `?? docs/superpowers/plans/2026-08-17-retire-balancer.md` — this plan, written before the branch existed. It rides along on the branch and is picked up by Step 10's `git add -A`, matching the eight plan documents already committed under that directory. **Anything else in the status output is a user's uncommitted work: stop and report rather than stashing it.**

- [ ] **Step 2: Create the branch**

```powershell
git checkout master
git pull --ff-only
git checkout -b chore/retire-balancer
```

- [ ] **Step 3: Confirm nothing imports the balancer**

The two files that mention it must be comments only. Verify before deleting, because an import would make this a blocker rather than a deletion.

```powershell
Select-String -Path tools\*.py,tests\*.py -Pattern 'import balancer|from balancer'
```

Expected: exactly one hit, `tests/test_balancer.py:8: import balancer`, which is itself being deleted. Any other hit means a live dependency — STOP and report it.

- [ ] **Step 4: Delete the three targets**

```powershell
git rm tools/balancer.py
git rm -r tools/balancer
git rm tests/test_balancer.py
git status --short
```

Expected: `D` lines for `tools/balancer.py`, `tests/test_balancer.py`, and three files under `tools/balancer/` — `main.go`, `go.mod`, `.gitignore`.

- [ ] **Step 5: Repair the docs citation (R3)**

In `docs/dev-workflow.md`, line 222 currently reads:

```
the TUI entry point — see `tools/balancer.py` and `tools/dialog_editor.py`. An unguarded import
```

Replace that line with:

```
the TUI entry point — see `tools/dialog_editor.py`. An unguarded import
```

R3 wants the balancer name gone and a guarded example still standing; `dialog_editor` is that example, and it stays until spec #613 retires it.

- [ ] **Step 6: Repair the comment in `tools/dialog_editor.py`**

Lines 38-40 currently read:

```python
# The curses TUI is POSIX-only — CPython ships _curses on POSIX only. Import it
# lazily so the pure helpers stay importable, and unit-testable, on Windows.
# Same guard as tools/balancer.py's termios/tty guard.
```

Replace the third line so it cites the rule rather than a deleted file:

```python
# The curses TUI is POSIX-only — CPython ships _curses on POSIX only. Import it
# lazily so the pure helpers stay importable, and unit-testable, on Windows.
# The rule is docs/dev-workflow.md section 4; balancer.py was the other example
# until #612 retired it.
```

- [ ] **Step 7: Repair the docstring in `tests/test_dialog_editor.py`**

Lines 15-21 currently read:

```python
    """The TUI is POSIX-only; the pure helpers must import anywhere.

    Same guard as tools/balancer.py's termios/tty guard (PR #439). Without it
    the whole module — and therefore this whole test file — errors at import
    on Windows, which is how tests/test_dialog_editor.py stayed out of the
    tool suite (#441).
    """
```

Replace the citing sentence:

```python
    """The TUI is POSIX-only; the pure helpers must import anywhere.

    The rule is docs/dev-workflow.md section 4 (PR #439); balancer.py was the
    other example until #612 retired it. Without the guard the whole module —
    and therefore this whole test file — errors at import on Windows, which is
    how tests/test_dialog_editor.py stayed out of the tool suite (#441).
    """
```

- [ ] **Step 8: Run the suite and check the count (AC2)**

```powershell
python -m unittest discover -s tests -p 'test_*.py' 2>&1 | Select-Object -Last 4
```

Expected: `OK`, with a count exactly 9 lower than Step 1's. A different delta means something else changed — investigate before committing.

- [ ] **Step 9: Confirm no reference survives (AC1, AC3)**

`Select-String` has no `-Recurse` parameter — feed it from `Get-ChildItem`:

```powershell
Get-ChildItem -Recurse -File -Include *.py,*.md,*.go,*.mod,*.yml,*.yaml,*.sh,Makefile |
    Where-Object { $_.FullName -notmatch '\\(build|\.git)\\' } |
    Select-String -Pattern 'balancer' |
    Select-Object Path, LineNumber, Line
```

Expected output after the edits: only the two files whose comments now say "balancer.py was the other example until #612 retired it", plus this plan document. No `tools/balancer*` path, and no citation presenting the balancer as a file a reader could open.

- [ ] **Step 10: Commit**

```powershell
git add -A
git commit -m @'
chore: retire the balancer Garage replaced

tools/balancer.py and tools/balancer/ were two implementations of one
tuning TUI -- a Python curses version and a Go rewrite -- and Garage
replaces both with a Windows desktop window. tests/test_balancer.py
covered parse_config and apply_changes; Garage carries the equivalent
coverage against tools/garage/core/config_io.py, so the suite loses
nine tests and no coverage.

Three citations pointed at the deleted file. docs/dev-workflow.md
section 4 used it as one of two guarded-POSIX-import examples, which
the spec calls out; tools/dialog_editor.py and its test file each
carried the same citation in a comment, which it does not. All three
now cite the rule instead, and dialog_editor.py remains the worked
example until #613 retires it too.

Part of #612

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
'@
```

The closing `'@` must sit at column 0 with no leading whitespace, or PowerShell throws a parse error.

---

### Task 2: The drift check

**Files:**
- Create: `tools/garage_drift_lint.py`
- Test: `tests/test_garage_drift_lint.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: module `garage_drift_lint` with this public surface, which Task 3 does not use and nothing else imports:
  - `GARAGE_REMOTE_MARKER: str` — `"nuke-raiders-garage"`
  - `TUNABLES_RELPATH: str` — `os.path.join("tools", "garage", "tunables.json")`
  - `find_defines(text: str) -> list[str]` — `#define` names, in header order, duplicates preserved
  - `load_classified(tunables_path: str) -> set[str]` — the keys of the file's `entries` object
  - `find_garage_checkout(repo_root: str, remote_reader=None) -> str | None`
  - `run(repo_root: str = None, tunables_path: str = None) -> int` — process exit code, 0 = pass
  - `main() -> int`

Written test-first, one behaviour at a time. Every step below is a separate run of the suite.

- [ ] **Step 1: Write the failing tests for `find_defines`**

Create `tests/test_garage_drift_lint.py` with exactly this content:

```python
#!/usr/bin/env python3
"""Tests for tools/garage_drift_lint.py"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import garage_drift_lint as lint


CONFIG = (
    '#ifndef CONFIG_H\n'
    '#define CONFIG_H\n'
    '\n'
    '/* a comment mentioning #define NOT_A_DEFINE */\n'
    '#define MAX_NPCS     8\n'
    '#define GEAR1_MAX_SPEED        2u\n'
    '#define MAX_RACERS           (MAX_ENEMY_RACERS + 1u)  /* player + enemies */\n'
    '  #define INDENTED_ONE 3\n'
    '\n'
    '#endif\n'
)

NAMES = ['CONFIG_H', 'MAX_NPCS', 'GEAR1_MAX_SPEED', 'MAX_RACERS', 'INDENTED_ONE']


class TestFindDefines(unittest.TestCase):
    def test_finds_every_name_in_header_order(self):
        self.assertEqual(lint.find_defines(CONFIG), NAMES)

    def test_ignores_a_define_word_inside_a_comment(self):
        self.assertNotIn('NOT_A_DEFINE', lint.find_defines(CONFIG))

    def test_takes_the_name_not_the_value(self):
        self.assertNotIn('8', lint.find_defines(CONFIG))


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

```powershell
python -m unittest tests.test_garage_drift_lint -v
```

Expected: `ModuleNotFoundError: No module named 'garage_drift_lint'`.

- [ ] **Step 3: Create the module with `find_defines` only**

Create `tools/garage_drift_lint.py`:

```python
#!/usr/bin/env python3
"""Fail this repository's tool suite when src/config.h holds a #define that
Garage's classification file does not classify (#612 R4).

Garage carries its own drift check, so an unclassified #define is reported
the next time Garage runs. That report arrives late: the #define enters
*this* repository through a commit here, and the commit that introduces it
is the moment its author can classify it. This check moves the report to
that moment -- tests/test_garage_drift_lint.py exercises it, discovery
gates that module, and both `make test-tools` and .githooks/pre-commit run
discovery.

The classification file lives in the Garage repository, which is NOT a
requirement of this one. When no Garage checkout is found beside this
repository, this check succeeds and says it did not run (AC5).

This module imports nothing from Garage, on purpose. Reading its schema
module would make this repository's suite break whenever a repository it
does not depend on refactors, and the comparison here is a set difference.

Usage: python tools/garage_drift_lint.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

GARAGE_REMOTE_MARKER = "nuke-raiders-garage"
TUNABLES_RELPATH = os.path.join("tools", "garage", "tunables.json")

# `#define` at the start of a line (leading whitespace allowed), then the
# name. Anchored so the word inside a comment or a string is not a match.
_DEFINE_RE = re.compile(r'^[ \t]*#[ \t]*define[ \t]+([A-Za-z_]\w*)', re.MULTILINE)


def find_defines(text: str) -> list:
    """Every #define name in `text`, in the order the header declares them."""
    return _DEFINE_RE.findall(text)
```

- [ ] **Step 4: Run the tests to verify they pass**

```powershell
python -m unittest tests.test_garage_drift_lint -v
```

Expected: 3 tests, `OK`.

- [ ] **Step 5: Write the failing tests for `load_classified`**

Append to `tests/test_garage_drift_lint.py`, above the `if __name__` block:

```python
def write_tunables(path, names_to_classes):
    entries = {
        name: {'class': cls, 'reason': 'test fixture'}
        for name, cls in names_to_classes.items()
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'_shape': 'test fixture', 'entries': entries}, f)


class TestLoadClassified(unittest.TestCase):
    def test_returns_every_entry_name(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'tunables.json')
            write_tunables(p, {'CONFIG_H': 'marker', 'MAX_NPCS': 'structural'})
            self.assertEqual(lint.load_classified(p), {'CONFIG_H', 'MAX_NPCS'})

    def test_every_class_counts_as_classified(self):
        """R4 says "neither tunable nor structural", but the schema has four
        classes and Garage's own check treats any entry as classified. A
        literal reading would fail on CONFIG_H, a marker.
        """
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'tunables.json')
            write_tunables(p, {
                'A': 'tunable', 'B': 'structural', 'C': 'derived', 'D': 'marker',
            })
            self.assertEqual(lint.load_classified(p), {'A', 'B', 'C', 'D'})
```

- [ ] **Step 6: Run to verify failure**

```powershell
python -m unittest tests.test_garage_drift_lint -v
```

Expected: `AttributeError: module 'garage_drift_lint' has no attribute 'load_classified'`.

- [ ] **Step 7: Implement `load_classified`**

Append to `tools/garage_drift_lint.py`:

```python
def load_classified(tunables_path: str) -> set:
    """The set of #define names tunables.json classifies.

    Every class counts. The file's four classes -- tunable, structural,
    derived, marker -- all mean "someone decided what this is"; only a name
    the file never mentions is unclassified.
    """
    with open(tunables_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return set(data.get('entries', {}).keys())
```

- [ ] **Step 8: Run to verify pass**

```powershell
python -m unittest tests.test_garage_drift_lint -v
```

Expected: 5 tests, `OK`.

- [ ] **Step 9: Write the failing tests for `find_garage_checkout`**

Append above the `if __name__` block:

```python
TUNABLES = os.path.join('tools', 'garage', 'tunables.json')


def make_garage(parent, dirname):
    """A directory that looks like a Garage checkout: it holds the
    classification file at the expected relative path.
    """
    root = os.path.join(parent, dirname)
    os.makedirs(os.path.join(root, 'tools', 'garage'), exist_ok=True)
    write_tunables(os.path.join(root, TUNABLES), {'CONFIG_H': 'marker'})
    return root


class TestFindGarageCheckout(unittest.TestCase):
    def test_finds_a_sibling_whose_remote_matches(self):
        with tempfile.TemporaryDirectory() as d:
            repo = os.path.join(d, 'nuke-raider')
            os.makedirs(repo)
            garage = make_garage(d, 'nuke-raider-garage')
            found = lint.find_garage_checkout(
                repo,
                remote_reader=lambda p: 'https://github.com/X/nuke-raiders-garage.git',
            )
            self.assertEqual(found, garage)

    def test_dirname_does_not_have_to_match_the_repo_name(self):
        """The checkout on the author's machine is 'nuke-raider-garage' while
        the repository is 'nuke-raiders-garage'. Matching on the remote and
        not on the directory name is what makes the check actually run.
        """
        with tempfile.TemporaryDirectory() as d:
            repo = os.path.join(d, 'nuke-raider')
            os.makedirs(repo)
            garage = make_garage(d, 'some-other-name')
            found = lint.find_garage_checkout(
                repo, remote_reader=lambda p: 'git@github.com:X/nuke-raiders-garage.git',
            )
            self.assertEqual(found, garage)

    def test_returns_none_when_no_sibling_holds_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            repo = os.path.join(d, 'nuke-raider')
            os.makedirs(repo)
            os.makedirs(os.path.join(d, 'unrelated'))
            self.assertIsNone(
                lint.find_garage_checkout(repo, remote_reader=lambda p: 'x/nuke-raiders-garage')
            )

    def test_returns_none_when_the_remote_does_not_match(self):
        with tempfile.TemporaryDirectory() as d:
            repo = os.path.join(d, 'nuke-raider')
            os.makedirs(repo)
            make_garage(d, 'nuke-raider-garage')
            self.assertIsNone(
                lint.find_garage_checkout(repo, remote_reader=lambda p: 'git@github.com:X/other.git')
            )

    def test_returns_none_when_the_sibling_is_not_a_git_checkout(self):
        with tempfile.TemporaryDirectory() as d:
            repo = os.path.join(d, 'nuke-raider')
            os.makedirs(repo)
            make_garage(d, 'nuke-raider-garage')
            self.assertIsNone(lint.find_garage_checkout(repo, remote_reader=lambda p: None))

    def test_does_not_consider_the_repository_itself(self):
        """A repo that somehow holds the file must not match itself."""
        with tempfile.TemporaryDirectory() as d:
            repo = make_garage(d, 'nuke-raider')
            self.assertIsNone(
                lint.find_garage_checkout(repo, remote_reader=lambda p: 'x/nuke-raiders-garage')
            )

    def test_the_default_remote_reader_returns_none_outside_a_checkout(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(lint.git_remote(d))
```

- [ ] **Step 10: Run to verify failure**

```powershell
python -m unittest tests.test_garage_drift_lint -v
```

Expected: `AttributeError: module 'garage_drift_lint' has no attribute 'find_garage_checkout'`.

- [ ] **Step 11: Implement `git_remote` and `find_garage_checkout`**

Append to `tools/garage_drift_lint.py`:

```python
def git_remote(path: str):
    """The `origin` URL of the checkout at `path`, or None when `path` is not
    a git checkout, has no origin, or git is unavailable.
    """
    try:
        proc = subprocess.run(
            ['git', '-C', path, 'remote', 'get-url', 'origin'],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def find_garage_checkout(repo_root: str, remote_reader=None):
    """The Garage checkout beside `repo_root`, or None when there is none.

    A sibling qualifies when it holds tools/garage/tunables.json AND its
    origin remote names the Garage repository. The remote is what confirms
    it: the checkout on the author's machine is named 'nuke-raider-garage'
    while the repository is 'nuke-raiders-garage', so a directory-name match
    would silently never fire -- and a check that never fires looks exactly
    like a check that passes.
    """
    if remote_reader is None:
        remote_reader = git_remote
    repo_root = os.path.abspath(repo_root)
    parent = os.path.dirname(repo_root)
    try:
        names = sorted(os.listdir(parent))
    except OSError:
        return None
    for name in names:
        candidate = os.path.join(parent, name)
        if os.path.abspath(candidate) == repo_root:
            continue
        if not os.path.isfile(os.path.join(candidate, TUNABLES_RELPATH)):
            continue
        remote = remote_reader(candidate)
        if remote and GARAGE_REMOTE_MARKER in remote:
            return candidate
    return None
```

- [ ] **Step 12: Run to verify pass**

```powershell
python -m unittest tests.test_garage_drift_lint -v
```

Expected: 12 tests, `OK`.

- [ ] **Step 13: Write the failing tests for `run`**

Append above the `if __name__` block:

```python
def make_repo(parent, config_text):
    root = os.path.join(parent, 'nuke-raider')
    os.makedirs(os.path.join(root, 'src'), exist_ok=True)
    with open(os.path.join(root, 'src', 'config.h'), 'w', encoding='utf-8') as f:
        f.write(config_text)
    return root


def run_capturing(**kwargs):
    """Run the check, returning (exit_code, stdout). Captured because a
    passing suite must never print the word FAIL.
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = lint.run(**kwargs)
    return code, buf.getvalue()


class TestRun(unittest.TestCase):
    def test_passes_when_every_define_is_classified(self):
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, '#define CONFIG_H\n#define MAX_NPCS 8\n')
            t = os.path.join(d, 'tunables.json')
            write_tunables(t, {'CONFIG_H': 'marker', 'MAX_NPCS': 'structural'})
            code, out = run_capturing(repo_root=repo, tunables_path=t)
            self.assertEqual(code, 0, out)
            self.assertIn('OK', out)
            self.assertNotIn('FAIL', out)

    def test_fails_on_an_unclassified_define(self):
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, '#define CONFIG_H\n#define BRAND_NEW_DIAL 7\n')
            t = os.path.join(d, 'tunables.json')
            write_tunables(t, {'CONFIG_H': 'marker'})
            code, out = run_capturing(repo_root=repo, tunables_path=t)
            self.assertEqual(code, 1)

    def test_the_failure_names_the_define(self):
        """AC4: the failure must name it -- a bare exit code makes the
        author hunt for which of 133 lines is the new one.
        """
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, '#define CONFIG_H\n#define BRAND_NEW_DIAL 7\n')
            t = os.path.join(d, 'tunables.json')
            write_tunables(t, {'CONFIG_H': 'marker'})
            _, out = run_capturing(repo_root=repo, tunables_path=t)
            self.assertIn('BRAND_NEW_DIAL', out)

    def test_the_failure_says_where_to_fix_it(self):
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, '#define CONFIG_H\n#define BRAND_NEW_DIAL 7\n')
            t = os.path.join(d, 'tunables.json')
            write_tunables(t, {'CONFIG_H': 'marker'})
            _, out = run_capturing(repo_root=repo, tunables_path=t)
            self.assertIn('tunables.json', out)

    def test_names_every_unclassified_define_not_just_the_first(self):
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, '#define CONFIG_H\n#define ONE 1\n#define TWO 2\n')
            t = os.path.join(d, 'tunables.json')
            write_tunables(t, {'CONFIG_H': 'marker'})
            _, out = run_capturing(repo_root=repo, tunables_path=t)
            self.assertIn('ONE', out)
            self.assertIn('TWO', out)

    def test_a_stale_entry_is_not_reported(self):
        """The reverse drift -- an entry whose #define is gone -- is Garage's
        to report. Its fix lives in a repository this suite does not own, so
        reporting it here would mean this suite could only go green by
        someone editing elsewhere.
        """
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, '#define CONFIG_H\n')
            t = os.path.join(d, 'tunables.json')
            write_tunables(t, {'CONFIG_H': 'marker', 'DELETED_LONG_AGO': 'tunable'})
            code, out = run_capturing(repo_root=repo, tunables_path=t)
            self.assertEqual(code, 0, out)
            self.assertNotIn('DELETED_LONG_AGO', out)


class TestRunWithoutAGarageCheckout(unittest.TestCase):
    """AC5: green, and it says it did not run."""

    def test_succeeds_when_no_garage_checkout_is_found(self):
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, '#define CONFIG_H\n#define ANYTHING 1\n')
            code, _ = run_capturing(repo_root=repo)
            self.assertEqual(code, 0)

    def test_says_it_did_not_run(self):
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, '#define CONFIG_H\n#define ANYTHING 1\n')
            _, out = run_capturing(repo_root=repo)
            self.assertIn('did not run', out)

    def test_stays_quiet_about_failure(self):
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, '#define CONFIG_H\n#define ANYTHING 1\n')
            _, out = run_capturing(repo_root=repo)
            self.assertNotIn('FAIL', out)
```

- [ ] **Step 14: Run to verify failure**

```powershell
python -m unittest tests.test_garage_drift_lint -v
```

Expected: `AttributeError: module 'garage_drift_lint' has no attribute 'run'`.

- [ ] **Step 15: Implement `run` and `main`**

Append to `tools/garage_drift_lint.py`:

```python
def repository_root() -> str:
    """This repository's root, derived from this file's location:
    tools/garage_drift_lint.py -> the root is two levels up.
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(repo_root: str = None, tunables_path: str = None) -> int:
    """Run the drift check. Returns a process exit code (0 = pass).

    Both arguments are override hooks for tests; a real invocation leaves
    them None and resolves this repository and the Garage checkout beside
    it normally.
    """
    if repo_root is None:
        repo_root = repository_root()

    if tunables_path is None:
        garage = find_garage_checkout(repo_root)
        if garage is None:
            print(
                "garage_drift_lint: no Garage checkout was found beside "
                f"'{repo_root}', so the config.h drift check did not run. "
                "This is not a failure -- Garage is not a requirement of "
                "this repository."
            )
            return 0
        tunables_path = os.path.join(garage, TUNABLES_RELPATH)

    config_h = os.path.join(repo_root, 'src', 'config.h')
    with open(config_h, 'r', encoding='utf-8') as f:
        defines = find_defines(f.read())

    classified = load_classified(tunables_path)

    seen = set()
    unclassified = []
    for name in defines:
        if name not in classified and name not in seen:
            seen.add(name)
            unclassified.append(name)

    if not unclassified:
        print(
            f"garage_drift_lint: OK -- all {len(defines)} #defines in "
            "src/config.h are classified in Garage's tunables.json."
        )
        return 0

    print(
        "garage_drift_lint: FAIL -- src/config.h has drifted ahead of "
        "Garage's tunables.json"
    )
    for name in unclassified:
        print(
            f"  - '{name}' is defined in src/config.h but is not classified "
            f"in {tunables_path} (add it as tunable/structural/derived/"
            "marker)."
        )
    return 1


def main() -> int:
    return run()


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 16: Run to verify pass**

```powershell
python -m unittest tests.test_garage_drift_lint -v
```

Expected: 21 tests, `OK`.

- [ ] **Step 17: Add the live test — the one that actually gates the suite**

Everything so far runs against fixtures. This is the test that fails when a real `#define` goes unclassified. Append above the `if __name__` block:

```python
class TestAgainstThisRepository(unittest.TestCase):
    """The gate itself. Discovery finds this module, `make test-tools` and
    .githooks/pre-commit both run discovery, so an unclassified #define
    fails the suite at the commit that introduces it (#612 R4).

    It is green two ways: the drift check passes, or no Garage checkout is
    present and the check reports that it did not run.
    """

    def test_config_h_has_not_drifted_from_tunables_json(self):
        code, out = run_capturing()
        self.assertEqual(code, 0, out)
```

- [ ] **Step 18: Run the live test and read its output**

```powershell
python -m unittest tests.test_garage_drift_lint.TestAgainstThisRepository -v
```

Expected: `OK`. To see which of the two green paths it took, run the check directly:

```powershell
python tools/garage_drift_lint.py
```

Expected on the author's machine, where `C:\Code\nuke-raider-garage` is a sibling: `garage_drift_lint: OK -- all 133 #defines in src/config.h are classified in Garage's tunables.json.`

If it instead reports that it did not run, the sibling scan failed — check that `C:\Code\nuke-raider-garage` holds `tools/garage/tunables.json` and that its `origin` remote contains `nuke-raiders-garage`. Do not proceed to Step 19 with the check silently skipping; a check that never fires is the failure mode this design exists to avoid.

- [ ] **Step 19: Verify AC4 by hand — make it actually fail**

The unit tests prove the logic on fixtures. This proves the gate on the real repository.

```powershell
Add-Content src/config.h "`n#define GARAGE_DRIFT_PROBE 1"
python tools/garage_drift_lint.py
```

Expected: exit code 1, and output naming `GARAGE_DRIFT_PROBE`. Check the code on its own line (a pipe would mask it):

```powershell
$LASTEXITCODE
```

Then confirm the suite fails the same way, and undo:

```powershell
python -m unittest tests.test_garage_drift_lint.TestAgainstThisRepository 2>&1 | Select-Object -Last 6
git checkout src/config.h
python tools/garage_drift_lint.py
```

Expected: the unittest run reports a failure whose message contains `GARAGE_DRIFT_PROBE`; after `git checkout`, the check prints `OK` again. **Confirm `git status --short` shows `src/config.h` unmodified before continuing.**

- [ ] **Step 20: Run the whole suite**

```powershell
python -m unittest discover -s tests -p 'test_*.py' 2>&1 | Select-Object -Last 4
```

Expected: `OK`, with a count 22 higher than Task 1 Step 8's (21 unit tests plus the live one). No `FAIL` text anywhere in the output — if `garage_drift_lint: FAIL` appears on a passing run, a test is missing its `redirect_stdout`.

- [ ] **Step 21: Commit**

```powershell
git add tools/garage_drift_lint.py tests/test_garage_drift_lint.py
git commit -m @'
feat: fail the tool suite on a #define Garage cannot classify

Garage may only edit #defines that tools/garage/tunables.json classifies,
and it carries its own drift check -- but that check runs the next time
someone opens Garage. The #define enters this repository through a commit
here, and that commit is the moment its author knows what the value is
for. This check moves the report to that moment.

It is not wired into the Makefile. tests/test_garage_drift_lint.py
exercises the real check against the real src/config.h, discovery finds
that module, and both `make test-tools` and .githooks/pre-commit run
discovery -- so the gate covers the commit as well as CI, and the recipe
those two must keep byte-identical is untouched.

The Garage checkout is found by scanning sibling directories for one that
holds tools/garage/tunables.json and whose origin remote names the Garage
repository. The remote is what confirms it, because the checkout is named
nuke-raider-garage while the repository is nuke-raiders-garage -- a
directory-name match would never fire, and a check that never fires reads
exactly like a check that passes. When no checkout is found the run is
green and says it did not run: Garage is not a requirement of this
repository and CI has no checkout of it.

It imports nothing from Garage. Reading Garage's schema module would let a
refactor over there break `make test-tools` over here, and the comparison
is a set difference. It also reports one direction only -- a tunables.json
entry whose #define is gone is Garage's to fix, and this suite must never
need an edit in a repository it does not own to go green.

Part of #612

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
'@
```

---

### Task 3: Make a `#define` edit rebuild what reads it

**Files:**
- Modify: `Makefile` (the `$(OBJ_DIR)/%.o: src/%.c` rule)
- Test: none automated. AC6 is a build-behaviour criterion; verifying it needs a real GBDK toolchain and three `make` runs. Step 2 below is that verification, and its output is the evidence this task delivers.

**Interfaces:**
- Consumes: nothing.
- Produces: nothing any other task reads.

- [ ] **Step 1: Add the prerequisite**

In `Makefile`, the compile rule currently reads:

```makefile
$(OBJ_DIR)/%.o: src/%.c | $(OBJ_DIR)
	$(LCC) $(CFLAGS) $(ROMFLAGS) -c -o $@ $<
```

Add the dependency directly beneath it:

```makefile
$(OBJ_DIR)/%.o: src/%.c | $(OBJ_DIR)
	$(LCC) $(CFLAGS) $(ROMFLAGS) -c -o $@ $<

# A #define edit changes values compiled into every object that reaches this
# header, directly or through one of the nine headers that include it. Without
# this, make sees no .c file newer than its .o, relinks stale objects, exits 0
# and hands back a ROM that does not carry the edit -- which reads as "the
# change did not work" (#612 R5).
#
# This rebuilds all 52 objects, not only the ~40 that reach config.h. Exact
# per-object dependencies would need generated depfiles from lcc; the extra
# precision saves about a fifth of a rebuild, and a silently ignored tuning
# edit costs a debugging session.
$(OBJS): src/config.h
```

- [ ] **Step 2: Verify AC6 against a real build**

This needs `GBDK_HOME` to resolve and `bash` on PATH. Check first:

```powershell
$env:GBDK_HOME
bash --version
```

If `GBDK_HOME` is empty or `lcc` is not under it, **stop and report AC6 as unverified** rather than claiming it — do not mark this step done on a build that did not run. Note that `GBDK_HOME` must use forward slashes; a backslash path has broken this build before.

With the toolchain present, run the three-build sequence:

```powershell
make
Get-Item build/nuke-raider.gb | Select-Object Length, LastWriteTime
(Get-FileHash build/nuke-raider.gb -Algorithm SHA256).Hash
```

Then edit one `#define` — `PLAYER_MAX_HP` is a `tunable` and changes a value the ROM carries — and rebuild:

```powershell
(Get-Content src/config.h) -replace '(#define PLAYER_MAX_HP\s+)100u', '${1}90u' | Set-Content src/config.h
make 2>&1 | Select-String -Pattern '\.o$|\.o ' | Measure-Object | Select-Object -ExpandProperty Count
(Get-FileHash build/nuke-raider.gb -Algorithm SHA256).Hash
```

Expected: objects recompile (a non-zero count), and the ROM hash **differs** from the first one. A matching hash means the edit did not reach the ROM and R5 is not satisfied.

Then run `make` a third time with no edit:

```powershell
make
```

Expected: `make: Nothing to be done` or only the link step — **no `.o` recompilation**. A rebuild here means the dependency is retriggering every time, which would make every build a full build.

Finally restore the header and confirm the tree is clean:

```powershell
git checkout src/config.h
git status --short
```

- [ ] **Step 3: Run both suites**

```powershell
python -m unittest discover -s tests -p 'test_*.py' 2>&1 | Select-Object -Last 4
make test
```

Expected: the tool suite reports `OK`; `make test` passes. The Makefile edit touches only the ROM compile rule, so neither should change — running them is how that claim gets evidence.

- [ ] **Step 4: Commit**

```powershell
git add Makefile
git commit -m @'
build: rebuild the objects that read config.h when it changes

The compile rule was `$(OBJ_DIR)/%.o: src/%.c` with no header prerequisite
and no generated dependency files, so editing a #define left every .o
looking current: make relinked them, exited 0, and produced a ROM that did
not carry the new value. Only src/dialog_data.c and src/hub_data.c named
src/config.h as a prerequisite, so only those two rebuilt.

Found while building Garage's compile panel, where the whole point is
change a value, compile, look -- and the compile step silently did not
carry the change. make was right to do nothing; nothing it knew about had
changed. This tells it.

`$(OBJS): src/config.h` rebuilds all 52 objects rather than only the ~40
that reach the header directly or through one of the nine headers that
include it. Exact dependencies would need depfiles out of lcc, which buys
about a fifth of a rebuild.

Garage compares build/obj/ against config.h's mtime and runs `make clean`
first when the objects predate it. That workaround exists only because
this was open, and can now be removed.

Part of #612

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
'@
```

---

### Task 4: Open the PR

**Files:** none.

**Interfaces:**
- Consumes: the three commits from Tasks 1-3.
- Produces: a PR against `master`.

- [ ] **Step 1: Confirm the full acceptance list before asking anyone to read it**

```powershell
Test-Path tools/balancer.py, tools/balancer, tests/test_balancer.py
Select-String -Path docs/dev-workflow.md -Pattern 'balancer'
python tools/garage_drift_lint.py
python -m unittest discover -s tests -p 'test_*.py' 2>&1 | Select-Object -Last 4
git log --oneline master..HEAD
```

Expected: three `False` values (AC1, AC2), no match in `docs/dev-workflow.md` (AC3), `garage_drift_lint: OK` (AC4/AC5 exercised), the suite `OK` (AC2), and three commits.

- [ ] **Step 2: Write the PR body to a file**

PowerShell flattens a multi-line string passed inline to `gh`, so the body goes in a file. Write `docs/superpowers/plans/.pr-body.md`:

```markdown
Closes #612.

**The deletions.** `tools/balancer.py` and `tools/balancer/` were a Python
curses TUI and a Go rewrite of the same tool; Garage replaces both.
`tests/test_balancer.py` goes with them — Garage carries equivalent coverage
against `tools/garage/core/config_io.py`.

Three places cited the deleted file as the guarded-POSIX-import example.
`docs/dev-workflow.md` section 4 is the one R3 names; `tools/dialog_editor.py`
and `tests/test_dialog_editor.py` each carried the same citation in a comment
and were not in the spec. All three now cite the rule, and `dialog_editor.py`
remains the worked example until #613 retires it.

**The drift check.** `tools/garage_drift_lint.py` fails when `src/config.h`
holds a `#define` that Garage's `tunables.json` does not classify, naming each
one. It is exercised from a discovered test module rather than wired into the
`test-tools` recipe, which means the pre-commit hook gates it too — R4's own
rationale is that the report should reach the author at the commit that
introduces the `#define`, and only that route delivers it. It also leaves the
recipe that `tests/test_repo_hooks.py` requires to stay byte-identical to the
hook alone.

Two deliberate readings of the spec, both worth a reviewer's attention:

- R4 says "neither tunable nor structural", but the schema has four classes.
  Taken literally the check would fail on `CONFIG_H`, a `marker`. It treats any
  entry as classified, matching Garage's own `garage_lint.py`.
- It reports one direction only. A `tunables.json` entry whose `#define` is gone
  is Garage's to fix, and this suite must never require an edit in a repository
  it does not own in order to go green.

The Garage checkout is found by scanning siblings for one holding
`tools/garage/tunables.json` whose `origin` remote names the Garage repository.
Matching on the remote rather than the directory name matters: the checkout is
`nuke-raider-garage` and the repository is `nuke-raiders-garage`. With no
checkout present the check is green and says it did not run.

**The header dependency.** `$(OBJS): src/config.h`. Editing a `#define` used to
leave every `.o` looking current, so `make` relinked stale objects and returned
a ROM without the change. Verified by hand: build, edit `PLAYER_MAX_HP`, rebuild
(objects recompile, ROM hash changes), build again (nothing recompiles).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

- [ ] **Step 3: Push and open the PR**

```powershell
git push -u origin chore/retire-balancer
gh pr create --repo MatthieuGagne/gmb-nuke-raider --base master --head chore/retire-balancer --title "chore: retire the balancer, gate config drift, fix the header dependency" --body-file docs/superpowers/plans/.pr-body.md
```

- [ ] **Step 4: Delete the scratch body file**

```powershell
Remove-Item docs/superpowers/plans/.pr-body.md
git status --short
```

Expected: clean. The body file is scratch and must not be committed.

- [ ] **Step 5: Report, and name what is not verified**

Report to the user with output pasted, not summarised: the three `False` path checks, the `garage_drift_lint: OK` line, the suite's `OK` line and test count, the AC4 probe (exit 1 naming `GARAGE_DRIFT_PROBE`), and the three ROM hashes from AC6.

State plainly which acceptance criteria are covered and which are not:

- AC1, AC2, AC3 — verified by the commands in Step 1.
- AC4 — verified twice: unit tests on fixtures, and the real probe in Task 2 Step 19.
- AC5 — verified by unit test. A full end-to-end check would mean moving the Garage checkout, which is not worth doing to a user's working directory.
- AC6 — verified by hand in Task 3 Step 2, **or reported as unverified if `GBDK_HOME` did not resolve**. Do not claim it otherwise.

Merging is the user's call. Do not merge without being asked.

Note for follow-up, not part of this PR: Task 3's commit message says Garage's `make clean` workaround "can now be removed". That removal is a change to the *Garage* repository and belongs in a separate issue filed there, after this merges.

---

## Notes for the reviewer

- **Why the drift check is not in the `test-tools` recipe.** The Makefile comment above `test-tools` says its command must stay byte-identical to `.githooks/pre-commit`, enforced by `tests/test_repo_hooks.py`. Adding a line to the recipe would leave the hook not running the check, so a commit introducing an unclassified `#define` would pass the local gate and fail only in CI — the opposite of R4's stated rationale. Riding on discovery gates both and edits neither.
- **Why not import Garage's `schema.py`.** It would remove a set-difference's worth of duplication and add a cross-repository coupling in exchange: a refactor in a repository this one does not depend on could turn `make test-tools` red here.
- **Why the blanket `$(OBJS)` dependency.** 24 of 52 sources include `config.h` directly, and nine headers include it too, so the transitive set is roughly 40 of 52. Exact depfiles would need `-Wp-MD` to survive lcc, which the spec flags as unverified, to save about a fifth of a rebuild.
- **What is still open after this.** `tools/dialog_editor.py` stays until #613. AC3 and AC4 of the Garage epic need that spec too, since they ask for both tools to be gone.
