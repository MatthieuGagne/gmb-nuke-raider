# Design: Vendor Unity (Remove Submodule)

Date: 2026-03-09

## Problem

`tests/unity` is a git submodule. Git worktrees don't share submodule checkouts — each worktree requires its own `git submodule update --init`, adding friction to every worktree-based workflow.

## Solution

Vendor the three Unity source files directly into the repo. Remove the submodule entirely.

## Files to Vendor

Copy from `tests/unity/src/` into `tests/unity/src/` (same paths, now tracked files):

- `unity.c`
- `unity.h`
- `unity_internals.h`

## Steps

1. Copy the three files out of the submodule checkout.
2. Remove the submodule: `git submodule deinit tests/unity`, `git rm tests/unity`, delete `.gitmodules`.
3. Re-add the three files at `tests/unity/src/`.
4. Commit everything in one commit on a feature branch.
5. Open PR to master.

## No Makefile Changes Needed

The Makefile already references:
- `UNITY_SRC := tests/unity/src/unity.c`
- `TEST_FLAGS := -Itests/unity/src ...`

These paths are preserved exactly.

## CI Impact

None. CI uses `make test` which compiles Unity from source. The vendored files are identical to the submodule checkout.
