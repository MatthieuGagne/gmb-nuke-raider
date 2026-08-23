---
name: sprite-builder
description: Use when adding a new sprite type to Nuke Raider — creating the Aseprite source, exporting PNG, running png_to_tiles, allocating OAM slots, loading tile data, and rendering the sprite in game.
---

# Sprite Builder — dispatch stub

This skill owns no pipeline detail of its own. The **`sprite-expert` agent** does, and it
executes the whole job end-to-end autonomously — it carries the 10-step execution checklist
(Aseprite source → PNG → `png_to_tiles.py` → `extern` decls → `set_sprite_data` → OAM slots →
`move_sprite` → `config.h` → build → smoketest), the OAM coordinate math, CGB palette setup, an
Error Patterns table and a self-correction retry loop.

**Do this:** dispatch the `sprite-expert` agent (Agent tool) with

```
implement this task: <the sprite task, verbatim>
```

Then read its report.

## Facts that survive outside the agent

- **Aseprite CLI:** invoke the **`aseprite`** skill before running any `aseprite` command.
  In particular, `--save-as` on a **multi-frame** `.aseprite` writes numbered files
  (`name1.png`, `name2.png`, …), not a sheet — use `--sheet` and add a Makefile override rule
  for that sprite.
- **Art format:** indexed color, exactly 4 palette entries, canvas dimensions multiples of 8.
  Palette index 0 is always transparent — never use it for visible pixels.
- **Never hand-edit `src/*_sprite.c`** — generated; edit the `.aseprite`, re-export, re-convert.
- **OAM:** allocate through `get_sprite()`, never a hardcoded slot; check for
  `SPRITE_POOL_INVALID` (`0xFF`). Fully visible range is `oam_x ∈ [8, 167]`,
  `oam_y ∈ [16, 159]`; place a screen pixel with `move_sprite(slot, sx + 8, sy + 16)`.
- **Banked tile data** must be loaded from bank-0 code (the `src/loader.c` wrappers), not from a
  BANKED caller.

## Cross-references

- **`sprite-expert`** agent — the real pipeline reference; dispatch it
- **`aseprite`** skill — full Aseprite CLI reference
- **`gbdk-expert`** agent — OAM hardware, PPU modes, VBlank timing, LCDC
