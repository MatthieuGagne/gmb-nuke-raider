# Index

## GBDK & SDCC Fundamentals

- [[sdcc-banking-rules]] — recurring SDCC/GBDK banking hazards: the ternary
  register-corruption bug, BANKED qualifier rules, data placement, codegen gotchas
- [[autobank-symbol-placement]] — autobank packing, `___bank_*` co-location checks,
  clean-build authority, sdld whole-module linking, HOME-bank ordering
- [[config-h-patterns]] — table macros vs compound literals, `#if`/`#error` range
  guards, config.h is not a Makefile dependency
- [[banked-call-optimization]] — cutting bank-trampoline cost in hot loops: lazy
  caching of loop-invariant BANKED accessors, single-call block detection, safe SoA
  hoisting, verified int8 thrust headroom

## Engine Architecture

- [[camera-streaming]] — BG streaming queue (`camera_invalidate_row/col`), acceptance
  return codes, buffer-cap asymmetry, `camera_repair_cells`
- [[beam-laser-module]] — the LASER hitscan weapon: BG-tile lane with zero OAM,
  raycast, player/frame-loop wiring, enemy polling, test lane geometry
- [[beam-trail-repair]] — incremental trail repair, `s_lane_repair` fallback, the
  `beam_cast` memo and its mandatory reset
- [[explosion-oam-patterns]] — explosion module API, OAM slot hand-off on death,
  screen-space drift fix
- [[enemy-damage-pipeline]] — `enemy_apply_damage`, patrol destroy/hit-flash/ram
  cooldown, armor tier, per-weapon damage cache, loadout seeding order
- [[state-hub-shop]] — vendor shop sub-state in bank-0 `state_hub.c`, dialog_to_c
  generated-table bank placement (`hub_data.c` vs `dialog_data.c`)

## Assets & Loader

- [[loader-registry-and-tooling-checks]] — positional asset registry,
  `TILE_ASSET_COUNT` test coupling, `memory_check.py` VRAM glob, `bank_check.py`
  comment false positives
- [[png-to-tiles-rgb-bug]] — `png_to_tiles.py` mis-decodes RGB PNGs; emit indexed
  mode "P" assets

## Debug & Symbol Visibility

- [[dbg-static-visibility]] — `DBG_STATIC`/`DEBUG_TRACE`, WRAM symbol exports for
  headless scenarios (#448), `dbg_static_lint.py`, the #588 sweep
- [[rom-parity-testing]] — release-vs-debug ROM parity test: relocation
  classification, trampoline shifts, compared-banks derivation

## Build & Test

- [[host-test-gotchas]] — `make test` timeouts, dangling map pointer, test ordering,
  Windows binary-lock retries
- [[verification-techniques]] — prove-it-bites: gcc `-Wconversion` audit, neutered
  functions, flip-header tests, bytearray mutation, two-ROM differential runtime test
- [[trace-py-stdlib-shadow]] — `tools/trace.py` shadows the stdlib `trace` module
- [[test-tools-gate-history]] — the months-red unenforced `make test-tools` gate and
  its #441 fix (discovery over enumeration)
