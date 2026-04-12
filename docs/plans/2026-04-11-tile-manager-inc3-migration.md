# Tile Manager — Increment 3: State Migration + Fix `load_bkg_row()` Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace all hardcoded `load_X_tiles()` call sites with `loader_load_state()`/`loader_unload_state()`, update module init functions to accept a `uint8_t tile_base` parameter, fix the `load_bkg_row()` VBlank timing hazard, delete all legacy loader functions, and remove obsolete tile-base constants from `config.h`.

**Architecture:** State coordinators (`state_playing.c`, `state_overmap.c`, `state_hub.c`) call `loader_load_state()` at entry and `loader_unload_state()` at exit. After loading, each state retrieves VRAM slots via `loader_get_slot(asset)` (NONBANKED — safe from any bank) and passes them to module init functions. Modules (`player.c`, `projectile.c`, `enemy.c`) store the slot as a `static uint8_t` and use it during rendering; they no longer call any load_*() function directly.

**Tech Stack:** GBDK-2020 / SDCC / SM83. All loader API functions are `NONBANKED` (callable from any ROM bank). Manifests `k_playing_assets`, `k_overmap_assets`, `k_hub_assets` are declared `extern` in `loader.h` — no new includes needed in state files.

## Open questions (must resolve before starting)

- None — all design decisions resolved via grill-me session.

---

## Execution status (updated 2026-04-11)

### Completed
| Commit | Task |
|--------|------|
| `b54d742` | Task 1: Wire `state_playing.c` to loader |
| `350e75a` | Task 2: Wire `state_overmap.c`; parameterise `overmap_car_props` |
| `3601db3` | Task 3: Wire `state_hub.c` to loader |
| `42a0fb6` | Docs: gbdk-expert double-enter bug; `timeout 30 make test` in test skill |

### Discovered during Batch 1

**Double-enter hang in `test_state_hub.c`:** After `loader_load_state()` was added to `enter()`, three tests called `enter()` a second time (after setUp already called it) without resetting loader state — triggering the double-load assert (`while(1){}`). Fix: add `state_hub.exit(); loader_reset_bitmap_for_test();` before each extra `enter()` call. Documented in `gbdk-expert.md` and `test/SKILL.md`.

### Smoketest Checkpoint 1 — BLOCKED

**Hub crash:** Game crashed when entering the city hub. Root cause unknown — needs `systematic-debugging` investigation before Batch 2 can proceed.

**Suspected area:** `state_hub.c` `enter()` — the hub migration (Task 3) is the most invasive change. Possible causes:
- `loader_get_slot(TILE_ASSET_DIALOG_ARROW)` returns wrong slot → `set_sprite_tile()` corrupts OAM
- `s_border_slot` computed before enough state is initialized
- `hub_render_menu()` runs before tiles are in VRAM (no `DISPLAY_OFF` guard around the full enter sequence)
- Banking issue in `loader_load_state()` path from bank-0 state_hub code

**Next step:** Run `systematic-debugging` to find root cause before continuing with Batch 2.

---

## Background: what exists today

| File | Current state |
|------|--------------|
| `player.c` | `player_init()` calls `load_player_tiles()` (hardcoded slot 0) |
| `projectile.c` | `projectile_init()` calls `load_bullet_tiles()` (hardcoded slot 17) |
| `enemy.c` | `enemy_init()` calls `load_object_sprites()` (hardcoded slot 18) |
| `state_overmap.c` | `enter()` calls `load_overmap_car_tiles()` (hardcoded slot 18) |
| `state_hub.c` | `enter()` and `hub_start_dialog()` use `SET_BANK`/`set_sprite_data`/`set_bkg_data` directly |
| `state_playing.c` | No loader calls — tiles load as side-effect of module inits |
| `loader.c` | `loader_load_state()` / `loader_unload_state()` defined but **never called** from state code |
| `track.c` | `track_init()` calls `track_table[id].load_tiles()` function pointer → legacy loaders |
| `camera.c` | `stream_row_direct()` calls `load_bkg_row()` (raw VRAM pointer write, display-OFF path) |

---

## Batch 1 — State wiring (Tasks 1–3, all parallel)

Tasks 1, 2, and 3 touch different files (`state_playing.c`, `state_overmap.c`+`state_overmap.h`, `state_hub.c`) and have no shared state. All three may be dispatched simultaneously.

After this batch: `loader_load_state()` / `loader_unload_state()` are called in all three states. Legacy module-init loaders still fire (double VRAM write — safe, redundant) because module signatures haven't changed yet. The game must run identically to before.

---

### Task 1: Wire `state_playing.c` to loader

**Files:**
- Modify: `src/state_playing.c`

**Depends on:** none
**Parallelizable with:** Task 2, Task 3

**Step 1: No new unit test**

`state_playing` entry/exit is integration-tested via smoketest. Unit-testing it would require mocking `player_render`, `camera_init`, etc. Verify instead that `make test` still passes after the change (no regressions).

**Step 2: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. Confirm `src/state_playing.c` has an entry in `bank-manifest.json` (it does — bank 255). No new files.

**Step 3: HARD GATE — gbdk-expert**

Dispatch: `"implement this task: in state_playing.c enter(), add loader_set_track(track_get_id()) then loader_load_state(k_playing_assets, k_playing_assets_count) as the first two lines. Add loader_unload_state() to sp_exit(). Both loader functions are NONBANKED. track_get_id() is BANKED (bank 255). Confirm calling convention is correct from bank-255 state_playing code."`

**Step 4: Write implementation**

In `src/state_playing.c` `enter()`:

```c
static void enter(void) {
    loader_set_track(track_get_id());
    loader_load_state(k_playing_assets, k_playing_assets_count);
    int16_t sx = track_get_start_x();
    /* ... rest of enter() unchanged ... */
```

In `sp_exit()`:

```c
static void sp_exit(void) {
    loader_unload_state();
    HIDE_WIN;
    cam_scx_shadow = 0u;
    cam_scy_shadow = 0u;
}
```

**Step 5: Run tests**

```bash
make test
```
Expected: PASS — no regressions.

**Step 6: HARD GATE — build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: ROM at `build/nuke-raider.gb`, zero errors.

**Step 7: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill.

**Step 8: Refactor checkpoint**

`loader_load_state()` is now called every time STATE_PLAYING is entered, including when popped back to from STATE_GAME_OVER. That is correct — each state entry loads a fresh slate. No generalisation issue.

**Step 9: HARD GATE — gb-c-optimizer**

Run `gb-c-optimizer` on `src/state_playing.c`. Validate only — report issues, do not apply fixes yet.

**Step 10: Commit**

```bash
git add src/state_playing.c
git commit -m "feat(playing): wire loader_load_state/unload_state to state entry/exit"
```

---

### Task 2: Wire `state_overmap.c` + update `overmap_car_props` signature

**Files:**
- Modify: `src/state_overmap.c`, `src/state_overmap.h`, `tests/test_overmap.c`

**Depends on:** none
**Parallelizable with:** Task 1, Task 3

**Step 1: Write the failing test**

Update `tests/test_overmap.c` — change all four `overmap_car_props` calls to pass a `uint8_t car_tile_base` argument (second positional parameter, before `*tile`):

```c
void test_overmap_car_props_up(void) {
    uint8_t tile, props;
    overmap_car_props(J_UP, 18u, &tile, &props);
    TEST_ASSERT_EQUAL_UINT8(18u, tile);
    TEST_ASSERT_EQUAL_UINT8(0u, props);
}
void test_overmap_car_props_down(void) {
    uint8_t tile, props;
    overmap_car_props(J_DOWN, 18u, &tile, &props);
    TEST_ASSERT_EQUAL_UINT8(18u, tile);
    TEST_ASSERT_EQUAL_UINT8(S_FLIPY, props);
}
void test_overmap_car_props_left(void) {
    uint8_t tile, props;
    overmap_car_props(J_LEFT, 18u, &tile, &props);
    TEST_ASSERT_EQUAL_UINT8(19u, tile);    /* base + 1 */
    TEST_ASSERT_EQUAL_UINT8(0u, props);
}
void test_overmap_car_props_right(void) {
    uint8_t tile, props;
    overmap_car_props(J_RIGHT, 18u, &tile, &props);
    TEST_ASSERT_EQUAL_UINT8(19u, tile);    /* base + 1 */
    TEST_ASSERT_EQUAL_UINT8(S_FLIPX, props);
}
```

**Step 2: Run test to verify it fails**

```bash
make test
```
Expected: FAIL — `test_overmap.c` compile error (wrong arg count).

**Step 3: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. `state_overmap.c` is bank 0 (no `#pragma bank`). Manifest entry exists.

**Step 4: HARD GATE — gbdk-expert**

Dispatch: `"implement this task: in state_overmap.c enter(), remove load_overmap_car_tiles() call, add loader_load_state(k_overmap_assets, k_overmap_assets_count) as the first line. Store the car tile slot: static uint8_t s_car_tile_base; assign s_car_tile_base = loader_get_slot(TILE_ASSET_OVERMAP_CAR) after loader_load_state(). Add loader_unload_state() to om_exit(). Update overmap_car_props() signature in both state_overmap.c and state_overmap.h to add uint8_t car_tile_base as second parameter; replace OVERMAP_CAR_TILE_BASE references inside with car_tile_base. Update the single call site in update() to pass s_car_tile_base. state_overmap.c is bank 0 — no pragma bank directive."`

**Step 5: Write implementation**

`src/state_overmap.h` — updated signature:
```c
void overmap_car_props(uint8_t dir, uint8_t car_tile_base, uint8_t *tile, uint8_t *props);
```

`src/state_overmap.c`:

Add at file scope (after includes):
```c
static uint8_t s_car_tile_base;
```

`enter()` first line:
```c
static void enter(void) {
    loader_load_state(k_overmap_assets, k_overmap_assets_count);
    s_car_tile_base = loader_get_slot(TILE_ASSET_OVERMAP_CAR);
    /* ... rest of enter(), with load_overmap_car_tiles() removed ... */
```

`om_exit()`:
```c
static void om_exit(void) {
    loader_unload_state();
}
```

`overmap_car_props()` — updated signature and body (replace `OVERMAP_CAR_TILE_BASE` with `car_tile_base`):
```c
void overmap_car_props(uint8_t dir, uint8_t car_tile_base, uint8_t *tile, uint8_t *props) {
    if (dir == J_LEFT) {
        *tile  = (uint8_t)(car_tile_base + 1u);
        *props = 0u;
    } else if (dir == J_RIGHT) {
        *tile  = (uint8_t)(car_tile_base + 1u);
        *props = S_FLIPX;
    } else if (dir == J_DOWN) {
        *tile  = car_tile_base;
        *props = S_FLIPY;
    } else {
        *tile  = car_tile_base;
        *props = 0u;
    }
}
```

Call site in `update()` — pass `s_car_tile_base`:
```c
overmap_car_props(travel_dir, s_car_tile_base, &tile, &props);
```

**Step 6: Run tests**

```bash
make test
```
Expected: PASS.

**Step 7: HARD GATE — build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: zero errors.

**Step 8: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill.

**Step 9: Refactor checkpoint**

`overmap_car_props` is now a pure function — no global state. The single car state is stored in `s_car_tile_base` at state scope. Generalises correctly to N cars if needed.

**Step 10: HARD GATE — gb-c-optimizer**

Run on `src/state_overmap.c`. Validate only.

**Step 11: Commit**

```bash
git add src/state_overmap.c src/state_overmap.h tests/test_overmap.c
git commit -m "feat(overmap): wire loader_load_state; parameterise overmap_car_props with car_tile_base"
```

---

### Task 3: Wire `state_hub.c` to loader

**Files:**
- Modify: `src/state_hub.c`

**Depends on:** none
**Parallelizable with:** Task 1, Task 2

**Step 1: No new unit test**

Hub entry/exit is integration-tested via smoketest. `make test` must pass (no regressions).

**Step 2: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. `state_hub.c` is bank 0. Manifest entry exists.

**Step 3: HARD GATE — gbdk-expert**

Dispatch: `"implement this task: refactor state_hub.c to use loader_load_state(k_hub_assets, k_hub_assets_count) at the start of enter() and loader_unload_state() in hub_exit(). The portrait_map[] and border tile arrays (portrait_top, portrait_side, portrait_bot, dialog_top, dialog_side, dialog_bot) are currently static const arrays initialised from compile-time constants HUB_PORTRAIT_TILE_SLOT and HUB_BORDER_TILE_SLOT. After migration these slots are runtime values from loader_get_slot(), so those arrays must become static (non-const) and be rebuilt at runtime. Add module-level statics s_portrait_slot and s_border_slot. Add a static void hub_rebuild_tile_maps(void) that populates all seven arrays from s_portrait_slot and s_border_slot. Call hub_rebuild_tile_maps() from hub_start_dialog() after setting s_portrait_slot. Set s_border_slot = loader_get_slot(TILE_ASSET_DIALOG_BORDER) in enter(). Remove load_portrait() entirely (tiles already in VRAM via loader). Remove the SET_BANK/set_bkg_data/RESTORE_BANK block for border tiles from hub_start_dialog(). In enter(), replace the SET_BANK/set_sprite_data/RESTORE_BANK block for dialog_arrow with: set_sprite_tile(DIALOG_ARROW_OAM_SLOT, loader_get_slot(TILE_ASSET_DIALOG_ARROW)). The BRD_* #defines can be removed since the arrays are now built explicitly. state_hub.c is bank 0."`

**Step 4: Write implementation**

At file scope in `src/state_hub.c`, add statics and replace const arrays:

```c
static uint8_t s_portrait_slot;
static uint8_t s_border_slot;

/* Tile arrays — non-const; populated at runtime by hub_rebuild_tile_maps() */
static uint8_t portrait_map[16];
static uint8_t portrait_top[HUB_PORTRAIT_BOX_W];
static uint8_t portrait_side[HUB_PORTRAIT_BOX_W];
static uint8_t portrait_bot[HUB_PORTRAIT_BOX_W];
static uint8_t dialog_top[HUB_DIALOG_BOX_W];
static uint8_t dialog_side[HUB_DIALOG_BOX_W];
static uint8_t dialog_bot[HUB_DIALOG_BOX_W];
```

`hub_rebuild_tile_maps()`:

```c
static const uint8_t portrait_offsets[16] = {
    0u,4u,8u,12u, 1u,5u,9u,13u, 2u,6u,10u,14u, 3u,7u,11u,15u
};

static void hub_rebuild_tile_maps(void) {
    uint8_t i;
    uint8_t bl = s_border_slot;
    for (i = 0u; i < 16u; i++) portrait_map[i] = s_portrait_slot + portrait_offsets[i];

    portrait_top[0]=bl;    portrait_top[1]=bl+1u; portrait_top[2]=bl+1u;
    portrait_top[3]=bl+1u; portrait_top[4]=bl+1u; portrait_top[5]=bl+2u;
    portrait_side[0]=bl+3u; portrait_side[1]=0u;  portrait_side[2]=0u;
    portrait_side[3]=0u;    portrait_side[4]=0u;  portrait_side[5]=bl+4u;
    portrait_bot[0]=bl+5u; portrait_bot[1]=bl+6u; portrait_bot[2]=bl+6u;
    portrait_bot[3]=bl+6u; portrait_bot[4]=bl+6u; portrait_bot[5]=bl+7u;

    dialog_top[0] =bl;    dialog_top[13]=bl+2u;
    { uint8_t j; for (j=1u; j<13u; j++) dialog_top[j]=bl+1u; }
    dialog_side[0]=bl+3u; dialog_side[13]=bl+4u;
    { uint8_t j; for (j=1u; j<13u; j++) dialog_side[j]=0u; }
    dialog_bot[0] =bl+5u; dialog_bot[13]=bl+7u;
    { uint8_t j; for (j=1u; j<13u; j++) dialog_bot[j]=bl+6u; }
}
```

`enter()` — replace arrow tile-load block and add loader wiring:

```c
static void enter(void) {
    loader_load_state(k_hub_assets, k_hub_assets_count);
    s_border_slot = loader_get_slot(TILE_ASSET_DIALOG_BORDER);
    overmap_hub_entered = 0u;
    /* ... existing setup ... */
    move_sprite(DIALOG_ARROW_OAM_SLOT, 0u, 0u);
    DISPLAY_OFF;
    /* Replace the SET_BANK/set_sprite_data/RESTORE_BANK block with: */
    set_sprite_tile(DIALOG_ARROW_OAM_SLOT, loader_get_slot(TILE_ASSET_DIALOG_ARROW));
    hub_render_menu();
    DISPLAY_ON;
    SHOW_BKG;
}
```

`hub_start_dialog()` — remove `load_portrait()` and the border `SET_BANK` block; set `s_portrait_slot` and rebuild maps:

```c
static void hub_start_dialog(uint8_t npc_cursor) {
    tile_asset_t portrait_asset;
    /* ... existing setup ... */
    if (npc_cursor == 0u)      portrait_asset = TILE_ASSET_NPC_MECHANIC;
    else if (npc_cursor == 1u) portrait_asset = TILE_ASSET_NPC_TRADER;
    else                       portrait_asset = TILE_ASSET_NPC_DRIFTER;
    s_portrait_slot = loader_get_slot(portrait_asset);
    hub_rebuild_tile_maps();
    vbl_display_off();
    clear_visible_rows();
    /* load_portrait(npc_cursor) — REMOVED */
    /* SET_BANK(dialog_border_tiles)/set_bkg_data/RESTORE_BANK — REMOVED */
    hub_render_dialog();
    DISPLAY_ON;
}
```

Remove `load_portrait()` function body entirely.

Remove the `#define BRD_*` / `#undef BRD_*` block since arrays are now built by `hub_rebuild_tile_maps()`.

In `hub_render_dialog()`, the arrays (`portrait_top`, `portrait_side`, etc.) are still referenced by name — no changes needed there since they're now the same non-const statics.

`hub_exit()`:
```c
static void hub_exit(void) {
    loader_unload_state();
}
```

**Step 5: Run tests**

```bash
make test
```
Expected: PASS.

**Step 6: HARD GATE — build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: zero errors.

**Step 7: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill.

**Step 8: Refactor checkpoint**

`hub_rebuild_tile_maps()` is called once per dialog open — not every frame. `portrait_offsets[]` is `static const` in ROM. No AoS/SoA concern. Generalises correctly.

**Step 9: HARD GATE — gb-c-optimizer**

Run on `src/state_hub.c`. Validate only.

**Step 10: Commit**

```bash
git add src/state_hub.c
git commit -m "feat(hub): wire loader_load_state; replace direct tile-load calls with loader_get_slot"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 1

| Group | Tasks | Notes |
|-------|-------|-------|
| A (parallel) | Task 1, Task 2, Task 3 | Different output files; no shared state |

---

### Smoketest Checkpoint 1 — all three states load tiles via loader; game unchanged

**Step 1: Fetch and merge latest master (from worktree directory)**
```bash
git fetch origin && git merge origin/master
```

**Step 2: Clean build**
```bash
make clean && GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: ROM at `build/nuke-raider.gb`, zero errors.

**Step 3: Memory check**
```bash
make memory-check
```
Expected: All budgets PASS. Fix any FAIL or ERROR before continuing.

**Step 4: Launch ROM (run from worktree directory)**
```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

**Step 5: Confirm with user**

Ask the user to verify:
- Title screen renders correctly
- Overmap renders correctly; car sprite visible and moves
- Entering a race: track tiles load, player sprite visible, enemy turrets visible
- Hub: entering dialog shows portrait + border + dialog arrow sprite
- Exiting each state and re-entering works (no VRAM corruption)

---

## Batch 2 — Module signature updates (Tasks 4→5→6, sequential)

Tasks 4, 5, and 6 all modify `state_playing.c` (replacing the placeholder `0u` passed to each module init with the correct `loader_get_slot()` call). They **must run sequentially** in the order 4 → 5 → 6. Each task builds cleanly before the next starts.

After this batch: no module init function calls any legacy `load_*_tiles()` function. All tile slots come from the loader.

---

### Task 4: `player_init(uint8_t tile_base)`

**Files:**
- Modify: `src/player.c`, `src/player.h`
- Modify: `src/state_playing.c` (update call site)
- Modify: `tests/test_player.c`, `tests/test_player_physics.c`, `tests/test_terrain_physics.c`

**Depends on:** Task 1 (state_playing.c has `loader_load_state` in enter())
**Parallelizable with:** none — writes `state_playing.c` (same file as Tasks 5 and 6)

**Step 1: Write the failing test**

In `tests/test_player.c`, change `setUp()` to pass a non-zero tile_base (16u) so assertions exercise the offset arithmetic:

```c
void setUp(void) {
    player_init(16u);
}
```

Update render assertions to use `16u + literal_offset` instead of `PLAYER_TILE_UP_BASE + N`:
```c
/* DIR_T: no flip */
TEST_ASSERT_EQUAL_UINT8(16u + 0u, mock_sprite_tile[0]);
TEST_ASSERT_EQUAL_UINT8(16u + 1u, mock_sprite_tile[1]);
TEST_ASSERT_EQUAL_UINT8(16u + 2u, mock_sprite_tile[2]);
TEST_ASSERT_EQUAL_UINT8(16u + 3u, mock_sprite_tile[3]);
/* DIR_B: FLIPY + row-swap → BL gets UP TL (tile 0), TL gets UP BL (tile 1) */
TEST_ASSERT_EQUAL_UINT8(16u + 1u, mock_sprite_tile[0]);
TEST_ASSERT_EQUAL_UINT8(16u + 0u, mock_sprite_tile[1]);
/* ...and so on for all directions */
```
Apply the same `+16u` offset consistently across all direction test cases. The offset values (0..15) match the existing `PLAYER_TILE_*_BASE + N` values because `PLAYER_TILE_UP_BASE` is 0 — the lookup tables already use relative offsets.

Also update `tests/test_player_physics.c` setUp:
```c
void setUp(void) { player_init(0u); }
```

And `tests/test_terrain_physics.c` setUp:
```c
player_init(0u);  /* or whatever the local call is — search for player_init() */
```

**Step 2: Run test to verify it fails**

```bash
make test
```
Expected: FAIL — compile error (too many arguments to `player_init`).

**Step 3: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. `player.c` is bank 255. Manifest entry exists.

**Step 4: HARD GATE — gbdk-expert**

Dispatch: `"implement this task: add uint8_t tile_base parameter to player_init() in player.c and player.h. Remove the load_player_tiles() call from player_init(). Store tile_base as static uint8_t s_player_tile_base. In player_render() and any other render function that assigns sprite tiles, replace PLAYER_TILE_UP_BASE with s_player_tile_base+0u, PLAYER_TILE_RIGHT_BASE with s_player_tile_base+4u, PLAYER_TILE_UPRIGHT_BASE with s_player_tile_base+8u, PLAYER_TILE_DOWNRIGHT_BASE with s_player_tile_base+12u. The lookup tables (static const arrays of tile indices) must be updated to use relative offsets (0-3 within each direction block) or add s_player_tile_base at set_sprite_tile call time. player.c is bank 255."`

**Step 5: Write implementation**

`src/player.h` — updated signature:
```c
void player_init(uint8_t tile_base) BANKED;
```

`src/player.c` — key changes:
- Add `static uint8_t s_player_tile_base;` at file scope
- In `player_init()`: `s_player_tile_base = tile_base;` — remove `load_player_tiles()` call
- The static const lookup tables that build absolute VRAM indices must now store **relative offsets** (0–15) and `s_player_tile_base` is added when calling `set_sprite_tile()`:
  ```c
  set_sprite_tile(player_sprite_slot[q], s_player_tile_base + tile_tbl[dir*4+q]);
  ```
  Update `tile_tbl` so all values are 0-based (subtract the old base — since `PLAYER_TILE_UP_BASE`=0 the UP entries are already 0-based; RIGHT entries need 0→0,1,2,3; UPRIGHT 0→0,1,2,3; DOWNRIGHT 0→0,1,2,3).

`src/state_playing.c` — update call:
```c
player_init(loader_get_slot(TILE_ASSET_PLAYER));
```

**Step 6: Run tests**

```bash
make test
```
Expected: PASS.

**Step 7: HARD GATE — build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: zero errors.

**Step 8: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill.

**Step 9: Refactor checkpoint**

Player tile base is now fully runtime-configurable. The lookup tables use relative offsets (0-15). No hard-coded slot assumptions remain in `player.c`.

**Step 10: HARD GATE — gb-c-optimizer**

Run on `src/player.c`. Validate only.

**Step 11: Commit**

```bash
git add src/player.c src/player.h src/state_playing.c \
        tests/test_player.c tests/test_player_physics.c tests/test_terrain_physics.c
git commit -m "feat(player): player_init accepts tile_base param; remove load_player_tiles() call"
```

---

### Task 5: `projectile_init(uint8_t tile_base)`

**Files:**
- Modify: `src/projectile.c`, `src/projectile.h`
- Modify: `src/state_playing.c` (update call site)
- Modify: `tests/test_projectile.c`

**Depends on:** Task 4 (builds on `state_playing.c` edits committed in Task 4)
**Parallelizable with:** none — writes `state_playing.c`

**Step 1: Write the failing test**

In `tests/test_projectile.c`, change `setUp()`:
```c
void setUp(void) {
    sprite_pool_init();
    projectile_init(17u);   /* 17 = PROJ_TILE_BASE — use actual expected slot in tests */
}
```

Add (or update) a test that fires a projectile and confirms `set_sprite_tile` was called with slot 17:
```c
void test_projectile_render_uses_tile_base(void) {
    /* fire one projectile, render once, confirm sprite tile == 17u */
    projectile_fire(80u, 72u, DIR_T, PROJ_OWNER_PLAYER);
    projectile_render();
    /* mock_sprite_tile[oam_slot] should equal 17u */
    /* find which OAM slot was used — it's the first slot claimed after pool init */
    TEST_ASSERT_EQUAL_UINT8(17u, mock_sprite_tile[/* first projectile OAM slot */4u]);
}
```

> **Note to implementer:** check existing test infrastructure in `test_projectile.c` to find how mock OAM slots are inspected. Adjust OAM slot index to match actual pool allocation (likely 4 — slot 0 is player, slots 4+ are projectiles).

**Step 2: Run test to verify it fails**

```bash
make test
```
Expected: FAIL — compile error (too many arguments).

**Step 3: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. `projectile.c` is bank 255. Manifest entry exists.

**Step 4: HARD GATE — gbdk-expert**

Dispatch: `"implement this task: add uint8_t tile_base to projectile_init() in projectile.c and projectile.h. Remove the load_bullet_tiles() call. Store as static uint8_t s_proj_tile_base. In projectile_render(), replace PROJ_TILE_BASE with s_proj_tile_base when calling set_sprite_tile(). projectile.c is bank 255."`

**Step 5: Write implementation**

`src/projectile.h`:
```c
void projectile_init(uint8_t tile_base) BANKED;
```

`src/projectile.c`:
- Add `static uint8_t s_proj_tile_base;`
- `projectile_init()`: `s_proj_tile_base = tile_base;` — remove `load_bullet_tiles()`
- In `projectile_render()`: replace `PROJ_TILE_BASE` → `s_proj_tile_base`

`src/state_playing.c`:
```c
projectile_init(loader_get_slot(TILE_ASSET_BULLET));
```

**Step 6: Run tests**

```bash
make test
```
Expected: PASS.

**Step 7: HARD GATE — build + Step 8: bank-post-build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Then invoke `bank-post-build` skill.

**Step 9: Refactor checkpoint**

Projectile module has no hardcoded VRAM assumptions. Generalises to multiple projectile types if needed.

**Step 10: HARD GATE — gb-c-optimizer**

Run on `src/projectile.c`. Validate only.

**Step 11: Commit**

```bash
git add src/projectile.c src/projectile.h src/state_playing.c tests/test_projectile.c
git commit -m "feat(projectile): projectile_init accepts tile_base param; remove load_bullet_tiles() call"
```

---

### Task 6: `enemy_init(uint8_t tile_base)`

**Files:**
- Modify: `src/enemy.c`, `src/enemy.h`
- Modify: `src/state_playing.c` (update call site)

**Depends on:** Task 5
**Parallelizable with:** none — writes `state_playing.c`

**Step 1: No new test**

`tests/test_enemy.c` setUp uses `enemy_init_empty()` (not `enemy_init()`). No existing test calls `enemy_init()` directly — it requires a map scan. Verify `make test` passes.

Grep for `enemy_init(` in tests to confirm no hidden test call sites:
```bash
grep -r "enemy_init(" tests/
```
Expected: only `enemy_init_empty()` calls.

**Step 2: HARD GATE — bank-pre-write**

Invoke the `bank-pre-write` skill. `enemy.c` is bank 255. Manifest entry exists.

**Step 3: HARD GATE — gbdk-expert**

Dispatch: `"implement this task: add uint8_t tile_base to enemy_init() in enemy.c and enemy.h. Remove the load_object_sprites() call from enemy_init(). Store as static uint8_t s_enemy_tile_base. In enemy_render() (or wherever set_sprite_tile is called), replace TURRET_TILE_BASE with s_enemy_tile_base. enemy.c is bank 255."`

**Step 4: Write implementation**

`src/enemy.h`:
```c
void enemy_init(uint8_t tile_base) BANKED;
```

`src/enemy.c`:
- Add `static uint8_t s_enemy_tile_base;`
- `enemy_init()`: `s_enemy_tile_base = tile_base;` — remove `load_object_sprites()`
- Replace `TURRET_TILE_BASE` with `s_enemy_tile_base` in `set_sprite_tile(...)` call

`src/state_playing.c`:
```c
enemy_init(loader_get_slot(TILE_ASSET_TURRET));
```

**Step 5: Run tests**

```bash
make test
```
Expected: PASS.

**Step 6: HARD GATE — build + Step 7: bank-post-build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Then invoke `bank-post-build` skill.

**Step 8: Refactor checkpoint**

All three module inits now take `tile_base`. No module calls any legacy loader. The `load_object_sprites` comment in `enemy.c`'s `#include "loader.h"` line is now stale — update it to reference `loader_get_slot()` instead.

**Step 9: HARD GATE — gb-c-optimizer**

Run on `src/enemy.c`. Validate only.

**Step 10: Commit**

```bash
git add src/enemy.c src/enemy.h src/state_playing.c
git commit -m "feat(enemy): enemy_init accepts tile_base param; remove load_object_sprites() call"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 2

| Group | Tasks | Notes |
|-------|-------|-------|
| A (sequential) | Task 4, Task 5, Task 6 | All write state_playing.c — must run in order |

---

### Smoketest Checkpoint 2 — module inits use loader slots; no legacy load calls in modules

**Step 1: Fetch and merge latest master**
```bash
git fetch origin && git merge origin/master
```

**Step 2: Clean build**
```bash
make clean && GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: zero errors.

**Step 3: Memory check**
```bash
make memory-check
```
Expected: all PASS.

**Step 4: Launch ROM**
```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

**Step 5: Confirm with user**

- Player sprite renders correctly with correct tiles
- Bullets fire and render correctly
- Enemy turrets render correctly
- All three checks must pass before proceeding to Batch 3

---

## Batch 3 — Legacy cleanup (Tasks 7–8, parallel)

After Batch 2: `load_player_tiles()`, `load_bullet_tiles()`, `load_object_sprites()`, `load_overmap_car_tiles()` have zero call sites. `load_track_tiles/2/3()` are only called from `track.c`'s function-pointer table. `load_bkg_row()` is only called from `camera.c`. This batch deletes all of them and removes the obsolete config constants.

Tasks 7 and 8 touch completely different files (`loader.c`/`loader.h`/`camera.c`/`track.c`/`track.h`/`tests/test_loader.c` vs `src/config.h`) — they are **parallel**.

---

### Task 7: Remove all legacy loader functions + fix `load_bkg_row()`

**Files:**
- Modify: `src/loader.c`, `src/loader.h`
- Modify: `src/camera.c` (replace `load_bkg_row()` calls with `set_bkg_tiles()`)
- Modify: `src/track.c`, `src/track.h` (remove `load_tiles` function pointer)
- Modify: `tests/test_loader.c` (remove tests for deleted functions)
- Modify: `tests/test_track_dispatch.c` (update stale comments)

**Depends on:** Smoketest Checkpoint 2 (ensures zero call sites before deletion)
**Parallelizable with:** Task 8

**Step 1: Verify zero call sites (pre-condition check)**

Before writing anything, confirm no remaining callers:
```bash
grep -r "load_player_tiles\|load_bullet_tiles\|load_object_sprites\|load_overmap_car_tiles" src/
grep -r "load_track_tiles\|load_track2_tiles\|load_track3_tiles" src/
grep -r "load_bkg_row" src/
```

Expected for first two:
- `loader.c` and `loader.h` — function definitions/declarations only (no call sites)
- `track.c` — `track_table` initializer uses function pointer (this is the call site to eliminate in this task)
- `camera.c` — `stream_row_direct()` (this is the call site to fix in this task)
- Zero hits in any other file

If any unexpected call site appears: **STOP** and resolve it before proceeding.

**Step 2: Remove load_bkg_row tests and legacy loader tests from test_loader.c**

In `tests/test_loader.c`, remove:
- `test_load_player_tiles_is_callable()`
- `test_load_track_tiles_is_callable()`
- `test_load_bkg_row_increments_mock_count()`
- `test_load_bkg_row_writes_to_mock_vram()`
- Their `RUN_TEST(...)` entries in `main()`

```bash
make test
```
Expected: FAIL if any of the removed functions are still referenced elsewhere, PASS otherwise. If the removed functions are referenced in other test files, find and remove those references first.

**Step 3: HARD GATE — bank-pre-write (for camera.c, loader.c, track.c)**

Invoke the `bank-pre-write` skill. Confirm:
- `camera.c` is bank 255
- `loader.c` is bank 0
- `track.c` is bank 255
No new files.

**Step 4: HARD GATE — gbdk-expert (load_bkg_row replacement)**

Dispatch: `"implement this task: in camera.c, function stream_row_direct(), replace both load_bkg_row() calls with set_bkg_tiles() calls using the same arguments. load_bkg_row(vram_x, vram_y, count, buf) maps to set_bkg_tiles(vram_x, vram_y, count, 1u, buf). stream_row_direct() is called only during camera_init() with LCD disabled, so set_bkg_tiles() is safe (no VBlank timing concern). Confirm that set_bkg_tiles() is correct here."`

**Step 5: Write implementation**

**camera.c** — `stream_row_direct()`: replace `load_bkg_row()` with `set_bkg_tiles()`:

```c
static void stream_row_direct(uint8_t world_ty) {
    uint8_t vram_y = world_ty & 31u;
    uint8_t vram_x = cam_tile_x_snap & 31u;
    uint8_t first_count;
    track_fill_row_range(world_ty, cam_tile_x_snap, VIS_COLS, row_buf);
    if ((uint8_t)(vram_x + VIS_COLS) > 32u) {
        first_count = 32u - vram_x;
        set_bkg_tiles(vram_x, vram_y, first_count, 1u, row_buf);
        set_bkg_tiles(0u,     vram_y, (uint8_t)(VIS_COLS - first_count), 1u,
                     row_buf + first_count);
    } else {
        set_bkg_tiles(vram_x, vram_y, VIS_COLS, 1u, row_buf);
    }
}
```

Remove `#include "loader.h"` from `camera.c` **only if** `loader.h` is no longer needed by any other function in that file. Check first:
```bash
grep -n "loader_" src/camera.c
```
If no other loader calls exist, remove the include.

**loader.h** — remove declarations:
```c
/* DELETE these lines: */
void load_player_tiles(void) NONBANKED;
void load_track_tiles(void) NONBANKED;
void load_track2_tiles(void) NONBANKED;
void load_track3_tiles(void) NONBANKED;
void load_bullet_tiles(void) NONBANKED;
void load_object_sprites(void) NONBANKED;
void load_overmap_car_tiles(void) NONBANKED;
void load_bkg_row(uint8_t vram_x, uint8_t vram_y, uint8_t count, const uint8_t *tiles) NONBANKED;
```

**loader.c** — remove function bodies for:
- `load_player_tiles()`
- `load_bullet_tiles()`
- `load_object_sprites()`
- `load_overmap_car_tiles()`
- `load_track_tiles()`
- `load_track2_tiles()`
- `load_track3_tiles()`
- `load_bkg_row()`

Also remove any `/* DEPRECATED */` comment blocks and includes that were only needed by these functions (e.g., tile data headers used exclusively by the deleted functions).

**track.h** — remove `load_tiles` field from `TrackDesc`:

```c
typedef struct {
    const uint8_t    *map;
    const int16_t    *start_x;
    const int16_t    *start_y;
    uint8_t           lap_count;
    const uint8_t    *map_type;
    uint16_t          reward;
    /* void (*load_tiles)(void) — REMOVED: tiles loaded by loader_load_state() */
} TrackDesc;
```

**track.c** — update `track_table[]` initializers (remove the function pointer from each row):

```c
static const TrackDesc track_table[] = {
    { track_map,  &track_start_x,  &track_start_y,  1u, &track_map_type,  TRACK1_REWARD },
    { track2_map, &track2_start_x, &track2_start_y, 3u, &track2_map_type, TRACK2_REWARD },
    { track3_map, &track3_start_x, &track3_start_y, 1u, &track3_map_type, 0u            },
};
```

**track.c** — `track_init()`: remove `load_tiles()` call:

```c
void track_init(void) BANKED {
    /* Tile data loaded by loader_load_state() in state_playing.enter() */
    SHOW_BKG;
}
```

**tests/test_track_dispatch.c** — update stale comments (no code changes):
- Line 50: `/* track_select(0) + track_init() must not crash */`
- Line 57: `/* track_select(1) + track_init() must not crash */`
- Line 64: `/* track_select(2) + track_init() must not crash */`
(Remove the parenthetical references to `load_track_tiles` etc.)

Remove `#include "loader.h"` from `track.c` **only if** no other loader functions are used there. Check:
```bash
grep -n "loader_" src/track.c
```

**Step 6: Run tests**

```bash
make test
```
Expected: PASS.

**Step 7: HARD GATE — build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: zero errors, zero warnings about undefined symbols.

**Step 8: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill. Confirm ROM size has decreased (removed ~8 functions).

**Step 9: Refactor checkpoint**

All legacy VRAM-copy functions are gone. The only VRAM tile-load path is `loader_load_state()`. `stream_row_direct()` now uses the same `set_bkg_tiles()` as `stream_row()`. No footgun remains.

**Step 10: HARD GATE — gb-c-optimizer**

Run on `src/loader.c`, `src/camera.c`, `src/track.c`. Validate only.

**Step 11: Commit**

```bash
git add src/loader.c src/loader.h src/camera.c \
        src/track.c src/track.h \
        tests/test_loader.c tests/test_track_dispatch.c
git commit -m "refactor(loader): remove legacy load_X_tiles() + load_bkg_row(); fix stream_row_direct to use set_bkg_tiles"
```

---

### Task 8: Remove obsolete tile-base constants from `config.h`

**Files:**
- Modify: `src/config.h`

**Depends on:** Smoketest Checkpoint 2 (ensures all old usages are gone)
**Parallelizable with:** Task 7

**Step 1: Verify zero usages (pre-condition check)**

```bash
grep -rn "PLAYER_TILE_UP_BASE\|PLAYER_TILE_RIGHT_BASE\|PLAYER_TILE_UPRIGHT_BASE\|PLAYER_TILE_DOWNRIGHT_BASE\|PROJ_TILE_BASE\|TURRET_TILE_BASE\|OVERMAP_CAR_TILE_BASE\|DIALOG_ARROW_TILE_BASE\|HUB_PORTRAIT_TILE_SLOT\|HUB_BORDER_TILE_SLOT" src/ tests/
```

Expected: zero hits in any file other than `src/config.h` itself. If any hits remain: **STOP** and trace the remaining usage before proceeding.

**Step 2: No new test needed**

The absence of these constants is verified by successful compilation after removal. Any missed usage will produce a compile error.

**Step 3: bank-pre-write**

Invoke the `bank-pre-write` skill. `config.h` is a header — no bank entry needed, but invoke for record.

**Step 4: Write implementation**

In `src/config.h`, remove these lines:

```c
/* Remove: */
#define PLAYER_TILE_UP_BASE        0u
#define PLAYER_TILE_RIGHT_BASE     4u
#define PLAYER_TILE_UPRIGHT_BASE   8u
#define PLAYER_TILE_DOWNRIGHT_BASE 12u
#define DIALOG_ARROW_TILE_BASE     16u
#define PROJ_TILE_BASE             17u
#define TURRET_TILE_BASE           18u
#define OVERMAP_CAR_TILE_BASE      18u

/* Remove: */
#define HUB_PORTRAIT_TILE_SLOT 96u
#define HUB_BORDER_TILE_SLOT   112u

/* Remove the compile-time assertion that relied on these: */
#if OVERMAP_CAR_TILE_BASE != TURRET_TILE_BASE
#error "OVERMAP_CAR_TILE_BASE and TURRET_TILE_BASE must be equal"
#endif
```

`DIALOG_ARROW_OAM_SLOT` (4) is an OAM slot, not a tile slot — **keep it**.
`POWERUP_TILE_BASE` (19) — check if still referenced:
```bash
grep -rn "POWERUP_TILE_BASE" src/ tests/
```
Remove only if zero usages remain; otherwise leave it.

**Step 5: Build**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: zero errors. Any compile error points to a missed usage — fix it before proceeding.

**Step 6: Run tests**

```bash
make test
```
Expected: PASS.

**Step 7: HARD GATE — bank-post-build**

Invoke the `bank-post-build` skill.

**Step 8: Refactor checkpoint**

`config.h` no longer contains any VRAM slot constants that were implicitly coupling the allocator to fixed addresses. The allocator now owns slot assignment.

**Step 9: HARD GATE — gb-c-optimizer**

No C files changed — skip.

**Step 10: Commit**

```bash
git add src/config.h
git commit -m "refactor(config): remove obsolete hardcoded tile-base and slot constants"
```

---

#### Parallel Execution Groups — Smoketest Checkpoint 3

| Group | Tasks | Notes |
|-------|-------|-------|
| A (parallel) | Task 7, Task 8 | Completely different files; no shared state |

---

### Smoketest Checkpoint 3 — final acceptance gate

**Step 1: Fetch and merge latest master**
```bash
git fetch origin && git merge origin/master
```

**Step 2: Clean build**
```bash
make clean && GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: ROM at `build/nuke-raider.gb`, zero errors.

**Step 3: Memory check**
```bash
make memory-check
```
Expected: all budgets PASS.

**Step 4: Launch ROM**
```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

**Step 5: Confirm all acceptance criteria with user**

Ask the user to verify each acceptance criterion from the issue:

- [ ] No calls to `load_player_tiles()`, `load_bullet_tiles()`, `load_object_sprites()`, `load_overmap_car_tiles()`, `load_track_tiles()`, `load_track2_tiles()`, `load_track3_tiles()` remain (`grep` will confirm at build)
- [ ] `loader_load_state` / `loader_unload_state` called symmetrically in all three state enter/exit
- [ ] `player_init`, `projectile_init`, `enemy_init` accept `tile_base` parameter
- [ ] `make test` passes
- [ ] Smoketest confirms all states render correctly
- [ ] Camera scroll is artifact-free
- [ ] `load_bkg_row()` is deleted

---

## Plan Self-Review Checklist

| # | Check | Status |
|---|-------|--------|
| 1 | No hardcoded values | PASS — all tile slots come from `loader_get_slot()` or literal offsets in tests |
| 2 | All tasks have explicit test criteria | PASS — each task lists expected `make test` output and build result |
| 3 | Parallel annotations justified | PASS — see justification notes on each task |
| 4 | Parallel Execution Groups tables present | PASS — one per smoketest checkpoint |
| 5 | No implementation details leaked from brainstorming | PASS |

### Parallelism annotation justifications

- **Tasks 1/2/3 `Parallelizable with: Task 1, Task 2, Task 3`** — all write different files (`state_playing.c`, `state_overmap.c`+`state_overmap.h`, `state_hub.c`); no shared symbols introduced or consumed between them.
- **Tasks 4/5/6 `Parallelizable with: none`** — all three write `state_playing.c` (different lines, but git merges are error-prone for same-file edits in a fast-moving branch); additionally Task 5 depends on the `state_playing.c` committed by Task 4, and Task 6 depends on Task 5.
- **Tasks 7/8 `Parallelizable with: each other`** — Task 7 touches `loader.c`, `loader.h`, `camera.c`, `track.c`, `track.h`, `test_loader.c`, `test_track_dispatch.c`. Task 8 touches only `config.h`. Zero overlap.
