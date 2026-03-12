# Autobanking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Switch to GBDK's `-autobank` linker flag so the toolchain automatically assigns ROM banks to assets and `BANKED` functions, eliminating hand-managed bank numbers as the ROM grows. Closes #36.

**Architecture:** Add `-Wl-j -Wm-ya4 -autobank -Wb-ext=.rel` to `CFLAGS`. Every `.c` file except `main.c` gets `#pragma bank 255`. Every public function gets `BANKED`. Asset arrays get `BANKREF`/`BANKREF_EXTERN`. Call sites wrap banked data access with `SET_BANK`/`RESTORE_BANK` from a new `src/banking.h`. Generator scripts emit banking boilerplate so regeneration is safe.

**Tech Stack:** GBDK-2020 4.x, SDCC SM83 target, MBC1. `BANKED` = `__banked`. `BANKREF`/`BANKREF_EXTERN`/`BANK()`/`CURRENT_BANK`/`SWITCH_ROM()` all from `<gb/gb.h>`.

**Working directory:** `.worktrees/feat-autobanking` on branch `feat/autobanking`

**Build command:** `GBDK_HOME=/home/mathdaman/gbdk make`
**Test command:** `make test`

---

## Key Rules Before You Start

- **`BANKED` goes after `)` on the function signature**, before `{` or `;`:
  ```c
  void foo(void) BANKED;      /* declaration in .h */
  void foo(void) BANKED { }   /* definition in .c  */
  ```
- **`#pragma bank 255`** goes at the very top of the `.c` file, before includes.
- **`BANKREF(X)`** goes in the `.c` file that **owns** symbol `X`, immediately before its definition.
- **`BANKREF_EXTERN(X)`** goes in the `.h` file or at the top of the `.c` file that **uses** `SET_BANK(X)`.
- **`SET_BANK(X)` declares `_saved_bank`** — it must be the first statement in its block (or at function scope), not inside a nested block after other statements.
- **Static helper functions** (not in any header): leave them untagged (they stay NONBANKED).
- **Function pointer struct fields must NOT use `BANKED`** — SDCC/SM83 generates a double-dereference for `void (*fn)(void) BANKED` struct fields, which is incompatible with direct-address initialization (struct stores `.dw _fn` but call code reads 2 bytes FROM that address as a second pointer). The `State` struct in `state_manager.h` uses plain `void (*fn)(void)`. Callback functions stored in such structs (e.g. `enter`, `update`, `exit` in state_playing/state_title) must also be left non-`BANKED` — they are called from state_manager.c which is in the same bank anyway.
- **`main.c` gets NO `#pragma bank 255`** — it stays in bank 0.
- **`vbl_isr()` in `main.c`** is already `NONBANKED` (ISRs must be bank 0) — leave as-is.
- `BANKED` is a no-op in host-side GCC tests — the mock will define it as empty.

---

## Task 1: Mock stubs + `src/banking.h` + Makefile

**Files:**
- Modify: `tests/mocks/gb/gb.h`
- Create: `src/banking.h`
- Modify: `Makefile`

### Step 1: Add banking no-op stubs to the mock

In `tests/mocks/gb/gb.h`, after the existing `#define NONBANKED` line (line 87), add:

```c
/* Banking macros — no-ops for host-side GCC compilation */
#ifndef BANKED
#define BANKED
#endif
#define BANKREF(x)
#define BANKREF_EXTERN(x)
#define BANK(x)          0u
#define CURRENT_BANK     0u
#define SWITCH_ROM(b)    ((void)(b))
```

### Step 2: Create `src/banking.h`

```c
#ifndef BANKING_H
#define BANKING_H

#include <gb/gb.h>

/* Save current bank, switch to the bank holding VAR's data, restore afterward.
 * Usage (at the top of a block, before other statements):
 *   SET_BANK(my_asset);
 *   use_data(my_asset);
 *   RESTORE_BANK();
 */
#define SET_BANK(var)   uint8_t _saved_bank = CURRENT_BANK; SWITCH_ROM(BANK(var))
#define RESTORE_BANK()  SWITCH_ROM(_saved_bank)

#endif /* BANKING_H */
```

### Step 3: Update `Makefile`

Change line 4 from:
```makefile
CFLAGS    := -Wa-l -Wl-m -Wl-j
```
to:
```makefile
CFLAGS    := -Wa-l -Wl-m -Wl-j -Wm-ya4 -autobank -Wb-ext=.rel
```

### Step 4: Run host tests

```
make test
```
Expected: all 26 tests PASS (banking macros are no-ops in mock).

### Step 5: Run ROM build

```
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: `build/junk-runner.gb` produced with no errors. The flags will now pass through lcc but since no file has `#pragma bank 255` yet, nothing is banked yet.

### Step 6: Commit

```bash
git add tests/mocks/gb/gb.h src/banking.h Makefile
git commit -m "feat: add autobank Makefile flags and banking.h macros"
```

---

## Task 2: `#pragma bank 255` + `BANKED` on all logic modules

**Files (all `.c`/`.h` pairs except `main.c`):**
- Modify: `src/camera.c` + `src/camera.h`
- Modify: `src/dialog.c` + `src/dialog.h`
- Modify: `src/hud.c` + `src/hud.h`
- Modify: `src/player.c` + `src/player.h`
- Modify: `src/sprite_pool.c` + `src/sprite_pool.h`
- Modify: `src/state_manager.c` + `src/state_manager.h`
- Modify: `src/state_playing.c` (no public functions in header — just `extern const State state_playing`)
- Modify: `src/state_title.c` (same)
- Modify: `src/track.c` + `src/track.h`
- Modify: `src/dialog_data.c` (no functions; data only — just pragma for now)
- Modify: `src/player_sprite.c` (auto-generated; pragma only — no header functions)
- Modify: `src/track_tiles.c` (auto-generated; pragma only)
- Modify: `src/track_map.c` (auto-generated; pragma only)

### Step 1: Edit each `.c` file — add `#pragma bank 255`

For every `.c` file in the list above, add `#pragma bank 255` as the **first line** (before any includes). Example for `src/camera.c`:

```c
#pragma bank 255
#include <gb/gb.h>
#include "camera.h"
...
```

The auto-generated files (`player_sprite.c`, `track_tiles.c`, `track_map.c`) have a comment header — put the pragma AFTER the comments, BEFORE the first `#include`.

### Step 2: Edit each `.c` file — add `BANKED` to public function definitions

For every public function (one that appears in the corresponding `.h` file), add `BANKED` after the closing `)` of the parameter list.

**`src/camera.c`** — tag these three:
```c
void camera_init(int16_t player_world_x, int16_t player_world_y) BANKED { ... }
void camera_update(int16_t player_world_x, int16_t player_world_y) BANKED { ... }
void camera_flush_vram(void) BANKED { ... }
```

**`src/dialog.c`** — tag all 8 public functions: `dialog_init`, `dialog_start`, `dialog_get_text`, `dialog_get_num_choices`, `dialog_get_choice`, `dialog_advance`, `dialog_set_flag`, `dialog_get_flag`.

**`src/hud.c`** — tag all 6: `hud_init`, `hud_update`, `hud_render`, `hud_set_hp`, `hud_get_seconds`, `hud_is_dirty`.

**`src/player.c`** — tag all 9: `player_init`, `player_update`, `player_render`, `player_set_pos`, `player_get_x`, `player_get_y`, `player_get_vx`, `player_get_vy`, `player_reset_vel`, `player_apply_physics`.

**`src/sprite_pool.c`** — tag all 4: `sprite_pool_init`, `get_sprite`, `clear_sprite`, `clear_sprites_from`.

**`src/state_manager.c`** — tag: `state_manager_init`, `state_manager_update`, `state_push`, `state_pop`, `state_replace`.

**`src/state_playing.c`** — this file's static functions (`enter`, `update`, `sp_exit`) are function pointer targets stored in a `const State`. Leave them **non-BANKED**:
```c
static void enter(void) { ... }
static void update(void) { ... }
static void sp_exit(void) { ... }
```
> **Why non-BANKED:** SDCC/SM83 generates a double-dereference for `void (*)(void) BANKED` struct field calls — it loads the field value then reads 2 more bytes from that address as a second pointer, which jumps to machine-code bytes = blank screen. The `State` struct uses plain `void (*)(void)` pointers. All state modules are in the same autobank (bank 1), so same-bank calls via non-banked pointer work correctly.

**`src/state_title.c`** — same pattern: leave its internal static `enter`, `update`, `st_exit` functions **non-BANKED**.

**`src/track.c`** — tag: `track_tile_type_from_index`, `track_tile_type`, `track_init`, `track_passable`.

**`src/dialog_data.c`** — no functions, skip.
**`src/player_sprite.c`**, **`src/track_tiles.c`**, **`src/track_map.c`** — no public functions, skip.

### Step 3: Edit each `.h` file — add `BANKED` to declarations

For every public function declaration in a header, add `BANKED` after the `)`:

**`src/camera.h`:**
```c
void camera_init(int16_t player_world_x, int16_t player_world_y) BANKED;
void camera_update(int16_t player_world_x, int16_t player_world_y) BANKED;
void camera_flush_vram(void) BANKED;
```

**`src/dialog.h`:** Add `BANKED` to all 8 declarations.

**`src/hud.h`:** Add `BANKED` to all 6 declarations.

**`src/player.h`:** Add `BANKED` to all 9+1 declarations (including `player_apply_physics`).

**`src/sprite_pool.h`:** Add `BANKED` to all 4.

**`src/state_manager.h`:** Add `BANKED` to `state_manager_init`, `state_manager_update`, `state_push`, `state_pop`, `state_replace`.

**`src/track.h`:** Add `BANKED` to `track_tile_type_from_index`, `track_tile_type`, `track_init`, `track_passable`.

**`src/state_playing.h`** and **`src/state_title.h`**: These only declare `extern const State state_playing` / `state_title` — no function declarations. Leave as-is.

**`src/dialog_data.h`**: No function declarations. Leave as-is for now.

### Step 4: Run host tests

```
make test
```
Expected: all 26 tests PASS (`BANKED` is `#define BANKED` = empty string in mock).

### Step 5: Run ROM build

```
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: `build/junk-runner.gb` built. Bankpack will assign all `#pragma bank 255` files to banks. No linker errors.

### Step 6: Commit

```bash
git add src/camera.c src/camera.h src/dialog.c src/dialog.h src/dialog_data.c \
        src/hud.c src/hud.h src/player.c src/player.h src/player_sprite.c \
        src/sprite_pool.c src/sprite_pool.h src/state_manager.c src/state_manager.h \
        src/state_playing.c src/state_title.c src/track.c src/track.h \
        src/track_map.c src/track_tiles.c
git commit -m "feat: add #pragma bank 255 and BANKED to all non-main modules"
```

---

## Task 3: `BANKREF` on asset files + `SET_BANK`/`RESTORE_BANK` at call sites

**Files:**
- Modify: `src/track_tiles.c`
- Modify: `src/player_sprite.c`
- Modify: `src/track_map.c`
- Modify: `src/dialog_data.c`
- Modify: `src/track.h` (add `BANKREF_EXTERN`)
- Modify: `src/dialog_data.h` (add `BANKREF_EXTERN`)
- Modify: `src/track.c` (add `SET_BANK`/`RESTORE_BANK` in `track_init`)
- Modify: `src/player.c` (add `SET_BANK`/`RESTORE_BANK` in `player_init`)

### Step 1: Add `BANKREF` in `src/track_tiles.c`

After `#pragma bank 255` and the comment header, add `#include "banking.h"` and `BANKREF(track_tile_data)` immediately before the array definition:

```c
/* Auto-generated by tools/png_to_tiles.py ... */
#pragma bank 255
#include <stdint.h>
#include "banking.h"

BANKREF(track_tile_data)
const uint8_t track_tile_data[] = {
    ...
};
```

### Step 2: Add `BANKREF` in `src/player_sprite.c`

```c
/* Auto-generated by tools/png_to_tiles.py ... */
#pragma bank 255
#include <stdint.h>
#include "banking.h"

BANKREF(player_tile_data)
const uint8_t player_tile_data[] = {
    ...
};
```

### Step 3: Add `BANKREF` in `src/track_map.c`

```c
/* GENERATED — do not edit by hand ... */
#pragma bank 255
#include "track.h"
#include "banking.h"

BANKREF(track_start_x)
const int16_t track_start_x = 88;
BANKREF(track_start_y)
const int16_t track_start_y = 720;

BANKREF(track_map)
const uint8_t track_map[MAP_TILES_H * MAP_TILES_W] = {
    ...
};
```

### Step 4: Add `BANKREF` in `src/dialog_data.c`

Add `#include "banking.h"` and `BANKREF(npc_dialogs)` before the array definition:

```c
#pragma bank 255
#include <stddef.h>
#include "dialog_data.h"
#include "banking.h"

...static nodes...

BANKREF(npc_dialogs)
const NpcDialog npc_dialogs[] = {
    ...
};
```

### Step 5: Add `BANKREF_EXTERN` to `src/track.h`

After the existing `extern` declarations, add:

```c
#include "banking.h"
BANKREF_EXTERN(track_map)
BANKREF_EXTERN(track_start_x)
BANKREF_EXTERN(track_start_y)
```

### Step 6: Add `BANKREF_EXTERN` to `src/dialog_data.h`

```c
#include "banking.h"
BANKREF_EXTERN(npc_dialogs)
```

### Step 7: Add `SET_BANK`/`RESTORE_BANK` in `src/track.c` — `track_init()`

Also add `BANKREF_EXTERN(track_tile_data)` near the top of `track.c` (after includes), then wrap the `set_bkg_data` call:

```c
/* near top of file, after includes: */
#include "banking.h"
BANKREF_EXTERN(track_tile_data)

/* In track_init(): */
void track_init(void) BANKED {
    SET_BANK(track_tile_data);
    set_bkg_data(0, track_tile_data_count, track_tile_data);
    RESTORE_BANK();
    /* Tilemap loaded by camera_init() */
    SHOW_BKG;
}
```

> `track_tile_data_count` is in the same file as `track_tile_data` (same bank), so no extra bank switch needed for it.

### Step 8: Add `SET_BANK`/`RESTORE_BANK` in `src/player.c` — `player_init()`

Add `#include "banking.h"` and `BANKREF_EXTERN(player_tile_data)` near the top:

```c
#include "banking.h"
BANKREF_EXTERN(player_tile_data)
```

In `player_init()`:

```c
void player_init(void) BANKED {
    SPRITES_8x8;
    sprite_pool_init();
    player_sprite_slot     = get_sprite();
    player_sprite_slot_bot = get_sprite();
    SET_BANK(player_tile_data);
    set_sprite_data(0, 2, player_tile_data);
    RESTORE_BANK();
    set_sprite_tile(player_sprite_slot,     0);
    set_sprite_tile(player_sprite_slot_bot, 1);
    SET_BANK(track_start_x);
    px = track_start_x;
    py = track_start_y;
    RESTORE_BANK();
    vx = 0;
    vy = 0;
    SHOW_SPRITES;
}
```

> `track_start_x`/`track_start_y` are in `track_map.c` (potentially a different bank from `player.c`). `track.h` already has `BANKREF_EXTERN(track_start_x)` after Task 3 step 5. Since `player.c` already includes `track.h`, no extra extern needed.

### Step 9: Run host tests

```
make test
```
Expected: all 26 tests PASS (`SET_BANK`, `RESTORE_BANK`, `BANKREF`, `BANKREF_EXTERN` are all no-ops or safe macros in mock).

### Step 10: Run ROM build

```
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: builds cleanly. `romusage` (if run) would show assets distributed.

### Step 11: Commit

```bash
git add src/track_tiles.c src/player_sprite.c src/track_map.c src/dialog_data.c \
        src/track.h src/dialog_data.h src/track.c src/player.c
git commit -m "feat: add BANKREF to asset files and SET_BANK at call sites"
```

---

## Task 4: Update generator scripts

**Files:**
- Modify: `tools/png_to_tiles.py`
- Modify: `tools/tmx_to_c.py`

### Step 1: Update `tools/png_to_tiles.py`

In the `png_to_c` function, change the `lines` list to emit `#pragma bank 255`, an `#include "banking.h"`, and a `BANKREF(array_name)` before the array:

Find the `lines = [...]` block (around line 85) and change it to:

```python
    lines = [
        f"/* Auto-generated by tools/png_to_tiles.py from {png_path} -- do not edit manually */",
        "#pragma bank 255",
        "#include <stdint.h>",
        "#include \"banking.h\"",
        "",
        f"BANKREF({array_name})",
        f"const uint8_t {array_name}[] = {{",
    ]
```

### Step 2: Update `tools/tmx_to_c.py`

In the `tmx_to_c` function, find the `with open(out_path, 'w') as f:` block and update the header writes to include `#pragma bank 255` and `BANKREF` declarations:

```python
    with open(out_path, 'w') as f:
        f.write("/* GENERATED — do not edit by hand."
                " Source: assets/maps/track.tmx */\n")
        f.write("/* Regenerate: python3 tools/tmx_to_c.py"
                " assets/maps/track.tmx src/track_map.c */\n")
        f.write("#pragma bank 255\n")
        f.write('#include "track.h"\n')
        f.write('#include "banking.h"\n\n')
        f.write(f"BANKREF(track_start_x)\n")
        f.write(f"const int16_t track_start_x = {spawn_x};\n")
        f.write(f"BANKREF(track_start_y)\n")
        f.write(f"const int16_t track_start_y = {spawn_y};\n\n")
        f.write("BANKREF(track_map)\n")
        f.write("const uint8_t track_map[MAP_TILES_H * MAP_TILES_W] = {\n")
        for row in range(height):
            start = row * width
            vals  = ','.join(str(v) for v in tile_ids[start:start + width])
            f.write(f"    /* row {row:2d} */ {vals},\n")
        f.write("};\n")
```

### Step 3: Verify generators produce correct output

Run both generators and inspect the first few lines:

```bash
python3 tools/png_to_tiles.py assets/maps/tileset.png /tmp/test_tiles.c track_tile_data
head -8 /tmp/test_tiles.c

python3 tools/tmx_to_c.py assets/maps/track.tmx /tmp/test_map.c
head -10 /tmp/test_map.c
```

Expected: both files start with `#pragma bank 255` and contain `BANKREF(...)` before each array.

### Step 4: Run host tests

```
make test
```
Expected: all 26 tests PASS.

### Step 5: Run ROM build

```
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: builds cleanly. The generated files in `src/` are already in git and already have the `BANKREF` declarations from Task 3 — so this mainly confirms the scripts would generate compatible output on next regeneration.

### Step 6: Commit

```bash
git add tools/png_to_tiles.py tools/tmx_to_c.py
git commit -m "feat: update generators to emit #pragma bank 255 and BANKREF"
```

---

## Task 5: Smoketest + PR

### Step 1: Final build

```
GBDK_HOME=/home/mathdaman/gbdk make
```

### Step 2: Launch smoketest

```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/junk-runner.gb &
```

Tell the user the emulator is running and ask them to confirm:
- Title screen renders correctly
- Driving state shows the track tiles and player sprite
- HUD timer displays correctly
- Player movement and collision work

**Do NOT create the PR until the user confirms the smoketest passes.**

### Step 3: Push and create PR

```bash
git push -u origin feat/autobanking
gh pr create \
  --title "feat: autobanking — automatic ROM bank assignment via GBDK -autobank" \
  --body "$(cat <<'EOF'
## Summary
- Adds `-Wl-j -Wm-ya4 -autobank -Wb-ext=.rel` to `CFLAGS` for automatic bank assignment
- New `src/banking.h` defines `SET_BANK`/`RESTORE_BANK` wrappers around GBDK's `CURRENT_BANK`/`SWITCH_ROM`
- All non-`main.c` modules tagged `#pragma bank 255` and public functions tagged `BANKED`
- Asset files (`track_tiles`, `track_map`, `player_sprite`, `dialog_data`) carry `BANKREF` declarations
- Call sites in `track_init()` and `player_init()` use `SET_BANK`/`RESTORE_BANK` for banked data access
- Generator scripts (`png_to_tiles.py`, `tmx_to_c.py`) updated to emit banking boilerplate
- Mock stubs updated so host-side `make test` continues to compile and pass

## Test plan
- [ ] `make test` passes (26 tests, 0 failures)
- [ ] `GBDK_HOME=~/gbdk make` builds with no linker errors
- [ ] Smoketest in Emulicious: title screen, track, player sprite, HUD all render correctly
- [ ] Player movement and tile collision work as before

Closes #36

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
