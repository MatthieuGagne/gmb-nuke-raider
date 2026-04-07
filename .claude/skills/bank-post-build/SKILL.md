---
name: bank-post-build
description: Hard gate — invoke after a successful build, before smoketest. Runs make bank-post-build and reports the output.
---

# Bank Post-Build Gate

Run after `GBDK_HOME=/home/mathdaman/gbdk make` succeeds. Block proceeding to smoketest if exit code is 1.

```sh
make bank-post-build
```
Report the full output to the user. If exit code is 1, **BLOCK** and tell the user to fix the reported issue before proceeding to smoketest.

If exit code is 0, proceed — the script already printed the pass/warn status.

**Autobanker co-location check (do when a PR adds ROM data):** If any bank's percentage increased since the last known-good build, compare `___bank_*` symbols in `build/nuke-raider.noi` against master's `.noi` file. If any file moved to a new bank (e.g. `___bank_track3_map` changed from `0x1` to `0x2`), check whether any `BANKED` function in `src/` dereferences ROM pointers from that file without a bank switch — if so, flag as silent data corruption risk. Fix: route those reads through a `NONBANKED` helper in `loader.c` (see `loader_map_read_byte`, `loader_map_fill_row`).

After `make bank-post-build` exits 0, run `make memory-check` (the `gb-memory-validator` skill) for WRAM/VRAM/OAM budget checks.
