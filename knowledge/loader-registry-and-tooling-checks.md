---
summary: Loader asset registry positionality (loader_registry_tbl indexed by tile_asset_t), TILE_ASSET_COUNT test coupling, memory_check.py VRAM filename-glob counting, bank_check.py comment false positives (bank-pre-write hook)
tags: [loader, tile-asset, registry, memory-check, bank-check, hooks, tooling, vram]
---

# Loader registry & bank/memory tooling checks

How tile assets are registered in `loader.c` and how the `tools/` checkers
(`memory_check.py`, `bank_check.py`) actually count things. Related:
[[autobank-symbol-placement]] for the post-build co-location check,
[[png-to-tiles-rgb-bug]] for the asset conversion pipeline.

## The registry array is POSITIONAL, indexed by (uint8_t)tile_asset_t

A new enum value's registry row MUST be inserted at the matching array index, not
merely appended. `loader_registry_tbl[TILE_ASSET_COUNT]` is read via
`&loader_registry_tbl[(uint8_t)asset]` in `loader_get_registry()`; the enum's
declaration order in `loader.h` and the array's row order in `loader.c` must match
exactly, or every asset declared after the misplaced one silently resolves to the wrong
tile data (no crash, no test failure unless a test checks that specific later asset).
Verify by counting: enum member N's ordinal position must equal the array literal's Nth
row (both start at 0). Contrast with `loader_get_asset_bank()`'s bank table, which is a
`switch`/`case` dispatch — case order is irrelevant there, only the
`case TILE_ASSET_X:` label position relative to that one enum value matters.
`k_playing_assets[]` (the state manifest) is neither positional nor order-sensitive —
it's a flat membership list consumed by a linear scan in `loader_load_state()`, so
appending a new asset to the end is always safe.

## A new tile_asset_t bumps TILE_ASSET_COUNT, which breaks count-hardcoding tests

`tests/test_loader.c` has `test_tile_asset_count_is_correct` (asserts
`(uint8_t)TILE_ASSET_COUNT`) and `test_playing_manifest_count_is_correct` (asserts
`k_playing_assets_count`) — both must be bumped in the same change or `make test`
regresses on an unrelated-looking assertion. Grep `tests/` for the enum/count symbol
names before declaring the task done;
`grep -rn "TILE_ASSET_COUNT\|k_playing_assets_count" tests/` found only `test_loader.c`
referenced them (#430 Task 5), but that isn't guaranteed to stay true as more state
manifests grow tests.

## memory_check.py's VRAM check counts by filename glob, not loader reachability

`tools/memory_check.py`'s `_check_vram()` sums every `*_count = N` in every file
matching `src/*_tiles.c`, regardless of whether `loader.c` actually references that
data — so a generated tile asset (e.g. `beam_tiles.c`, added and compiled in an earlier
task) already counts toward the VRAM total the moment the `.c` file exists in `src/`,
even before any task wires it into the loader registry or a state manifest. Wiring it
in later (as `loader_get_registry`/`k_playing_assets` entries) changes zero bytes in
this report. Don't expect the VRAM line to move when a task's job is only to register
an already-compiled asset — check `git log -- src/<name>_tiles.c` to see when the file
was actually added if the reported total looks stale relative to a task's stated
baseline.

## bank_check.py's header check false-positived on comments (#430 Task 5)

`tools/bank_check.py`'s SET_BANK/SWITCH_ROM header check was a raw substring search —
it false-positived on doc-comment prose, blocking every edit to `src/loader.h` and
`src/banking.h`. `loader.h` has always had comments like
`"bank-0 code, safe to call SWITCH_ROM"`; `banking.h` legitimately *defines*
`SET_BANK`/`SWITCH_ROM` as macros. Neither is a real violation, but
`'SWITCH_ROM' in content` matched both, so `bank-pre-write`'s PreToolUse hook blocked
**any** edit to `loader.h`, unrelated to the edit's content — pre-existing, unrelated
to the feature being added, present since the check was added 2026-03-26. Fixed by
stripping `//` and `/* */` comments before scanning
(`_strip_comments`/`_has_bank_switch_call` in `tools/bank_check.py`); real calls are
always code, never comment text, so this only removes false positives, never weakens
detection (regression tests: header-comment-passes, header-real-call-still-errors,
banked-.c-comment-passes). `banking.h` still legitimately fails the check (real macro
*definitions*, not a use-site) — that's a separate, correctly-flagged, pre-existing,
out-of-scope condition; do not "fix" it by exempting the filename. `tools/bank_check.py`
is NOT under `src/`, so editing it is not itself gated by bank-pre-write. If
`bank-pre-write` blocks editing a `.h` file whose SET_BANK/SWITCH_ROM parts you did not
touch, run `python tools/bank_check.py <path>` directly first to see the exact reported
line before assuming it's your change.
