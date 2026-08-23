# Banking architecture (post-autobank-migration)

Read by the `gbdk-expert` agent. Per-file bank assignment and validation are owned by the
`bank-pre-write` skill, the automatic post-build bank-budget gate and `bank-manifest.json` — this file describes the
code shapes those gates assume.

**Invariant:** Only bank-0 files (no `#pragma bank`) may call `SET_BANK` or `SWITCH_ROM`.
Files with `#pragma bank 255` (autobank) or an explicit bank N call BANKED functions or NONBANKED
loader wrappers — they never touch `SWITCH_ROM` directly.

## loader.c / tile_base pattern

`loader_load_state()` (NONBANKED, bank 0) loads all assets for the current state into VRAM. The
state coordinator then calls each module init with the assigned slot:

```c
/* In state_playing.enter(): */
loader_load_state(&playing_state_manifest);
player_init(loader_get_slot(TILE_ASSET_PLAYER));      /* e.g. slot 0 */
projectile_init(loader_get_slot(TILE_ASSET_BULLET));  /* e.g. slot 17 */
enemy_init(loader_get_slot(TILE_ASSET_TURRET));       /* e.g. slot 18 */
camera_set_tile_base(loader_get_slot(TILE_ASSET_TRACK)); /* e.g. slot 143 */
camera_init();

/* In player.c: */
void player_init(uint8_t tile_base) BANKED {
    s_player_tile_base = tile_base;
    /* ... */
    set_sprite_tile(0, s_player_tile_base + 0u);  /* never set_sprite_data() */
}
```

## invoke() state dispatch pattern

`state_manager.c` (bank 0) holds:

```c
static void invoke(void (*fn)(void), uint8_t bank) {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(bank);
    fn();
    SWITCH_ROM(saved);
}
```

The state struct carries a `uint8_t bank` field. Callbacks are plain function pointers (NOT
BANKED — SDCC generates a broken double-dereference for BANKED struct field pointers).

## BANKREF for autobank

Use `BANKREF(sym)` in `#pragma bank 255` files — bankpack rewrites `___bank_sym` to the real
assigned bank at link time. Use `volatile __at(N)` only for an explicit bank N (not 255), in
data-only files.

Pinned banks: 31 = `src/music_data.c`, 30 = `src/debug.c` (test command mailbox, debug ROM only,
#590). A pinned **code** file needs the `#pragma bank N` line and nothing else — the
`volatile __at(N)` form is for data-only files whose bank symbol a loader reads.
