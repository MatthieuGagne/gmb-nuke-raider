---
name: post-build-gates
description: "Fallback reference for the two post-build hard gates — `make bank-post-build` (ROM bank budgets) and `make memory-check` (WRAM/VRAM/OAM budgets). BOTH NORMALLY FIRE AUTOMATICALLY: tools/post_build_hook.py runs them, in that order, as a PostToolUse hook after any non-clean `make`. Read the hook output instead of re-running them. Invoke this skill only to interpret a result, or when a build ran somewhere the hook did not fire (e.g. a Pi `pwsh-*` background job)."
---

# Post-Build Gates — bank budgets + memory budgets

`tools/post_build_hook.py` runs `make bank-post-build`, and — only if that exits 0 —
`make memory-check`, surfacing both outputs. **Do not re-run what the hook just ran.** If the
hook output is present, read it and act on the verdicts below.

Manual fallback (from the worktree directory):

```sh
make bank-post-build   # ROM bank budgets
make memory-check      # WRAM / VRAM / OAM budgets — only if the above exits 0
```

## Verdicts

| Result | Action |
|--------|--------|
| `bank-post-build` exit 1 | **BLOCK.** Report the output; fix before smoketest. `memory-check` is skipped by the hook in this case. |
| `bank-post-build` exit 0 | Proceed to the memory budgets. |
| memory: all PASS | Proceed to smoketest. |
| memory: any WARN | Advisory — proceed, but note the category in the PR description. |
| memory: any FAIL | **STOP.** Hard gate; manual fix required. |
| memory: ERROR (map symbol missing) | Treat as FAIL — the ROM may not be built correctly. |

ROM bank FAILs come from `bank-post-build`, never from `make memory-check`.

## Autobanker co-location check (do when a PR adds ROM data)

If any bank's percentage increased since the last known-good build, compare `___bank_*` symbols
in `build/nuke-raider.noi` against master's `.noi`. If a file moved to a new bank (e.g.
`___bank_track3_map` went from `0x1` to `0x2`), check whether any `BANKED` function in `src/`
dereferences ROM pointers from that file without a bank switch — if so, flag it as a silent
data-corruption risk. Fix: route those reads through a `NONBANKED` helper in `loader.c` (see
`loader_map_read_byte`, `loader_map_fill_row`).

## Debug ROM notes

- The debug ROM reports one bank the release ROM does not: **bank 30**, the test command mailbox
  (#590). Its absence from the release report is the expected result, not a missing check.
- The debug ROM links with `-Wl-g.STACK=0xDF00`, reserving `0xDF00-0xDFFF` for the mailbox
  (`0xDF70-0xDF78`) and the debug ring buffer (`0xDF80-0xDFC1`). `make memory-check-debug` reads
  `s__HEAP_E`, which must stay below `0xDF00`; `tests/test_debug_symbols.py` enforces it.
