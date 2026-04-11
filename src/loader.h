#ifndef LOADER_H
#define LOADER_H

#include <gb/gb.h>
#include <stdint.h>
#include "checkpoint.h"

/* NONBANKED VRAM loaders — bank-0 code, safe to call SWITCH_ROM.
 * Call these from any bank to load asset data into VRAM. */
void load_player_tiles(void) NONBANKED;
void load_track_tiles(void) NONBANKED;
void load_track2_tiles(void) NONBANKED;
void load_track3_tiles(void) NONBANKED;
void load_track_start_pos(int16_t *x, int16_t *y) NONBANKED;
void load_bullet_tiles(void) NONBANKED;
void load_object_sprites(void) NONBANKED;
void load_overmap_car_tiles(void) NONBANKED;

/* Cross-bank checkpoint copy — switches to the generated map file's bank,
 * copies checkpoint ROM array to dst[], and writes count. Bank-0 only. */
void load_checkpoints(uint8_t id, CheckpointDef *dst, uint8_t *count) NONBANKED;

/* Reads width and height from the 2-byte header of the active track's ROM array.
 * Sets active_map_w and active_map_h in track.c.
 * Must be called before track_select() uses active_map for tile lookups. */
void load_track_header(uint8_t id) NONBANKED;

/* Copies NPC spawn arrays for track `id` (0=track, 1=track2, 2=track3).
 * Output buffers must be at least MAX_ENEMIES bytes each.
 * out_type receives NPC_TYPE_* values; out_dir receives DIR_* or DIR_NONE. */
void load_npc_positions(uint8_t id,
                         uint8_t *out_tx,
                         uint8_t *out_ty,
                         uint8_t *out_type,
                         uint8_t *out_dir,
                         uint8_t *out_count) NONBANKED;

/* Copies powerup spawn arrays for track `id` (0=track, 1=track2, 2=track3).
 * Output buffers must be at least MAX_POWERUPS bytes each.
 * out_type receives POWERUP_TYPE_* values. */
void load_powerup_positions(uint8_t id,
                             uint8_t *out_tx,
                             uint8_t *out_ty,
                             uint8_t *out_type,
                             uint8_t *out_count) NONBANKED;

/* Writes a single row of BG tiles directly to VRAM tilemap at (vram_x, vram_y).
 * vram_x and vram_y wrap mod 32. Must be called during VBlank or DISPLAY_OFF. */
void load_bkg_row(uint8_t vram_x, uint8_t vram_y,
                  uint8_t count, const uint8_t *tiles) NONBANKED;

/* Reads start position and map type for track `id` from their ROM bank.
 * NONBANKED — safe to call from any bank. */
void load_track_scalars(uint8_t id, int16_t *sx, int16_t *sy, uint8_t *mtype) NONBANKED;

/* NONBANKED tile-read helpers — switch to the active track's data bank,
 * copy the requested data, and restore. Call from BANKED code in track.c. */
uint8_t loader_map_read_byte(uint16_t idx) NONBANKED;
void    loader_map_fill_row(uint8_t ty, uint8_t w, uint8_t *buf) NONBANKED;
void    loader_map_fill_range(uint8_t ty, uint8_t w, uint8_t tx_start, uint8_t count, uint8_t *buf) NONBANKED;
void    loader_map_fill_col(uint8_t tx, uint8_t w, uint8_t h, uint8_t ty_start, uint8_t count, uint8_t *buf) NONBANKED;

/* Switches to BANK(npc_dialogs), copies node text/name/choices/next into
 * dialog.c WRAM cache buffers, then restores bank.
 * Call before dialog_start() and after dialog_advance() returns 1. */
void loader_dialog_cache_node(uint8_t npc_id, uint8_t node_idx) NONBANKED;

/* Tile asset registry — one entry per loaded asset.
 * TILE_ASSET_HUD_FONT is self-managed by hud.c; its registry entry is a NULL sentinel. */
typedef enum {
    TILE_ASSET_PLAYER         = 0,
    TILE_ASSET_BULLET         = 1,
    TILE_ASSET_TURRET         = 2,
    TILE_ASSET_OVERMAP_CAR    = 3,
    TILE_ASSET_DIALOG_ARROW   = 4,
    TILE_ASSET_TRACK          = 5,
    TILE_ASSET_OVERMAP_BG     = 6,
    TILE_ASSET_HUD_FONT       = 7,   /* self-managed by hud.c — NULL registry entry */
    TILE_ASSET_NPC_DRIFTER    = 8,
    TILE_ASSET_NPC_MECHANIC   = 9,
    TILE_ASSET_NPC_TRADER     = 10,
    TILE_ASSET_DIALOG_BORDER  = 11,
    TILE_ASSET_COUNT          = 12
} tile_asset_t;

/* Registry struct — ROM-resident; bank stored separately in loader_asset_bank[]. */
typedef struct {
    const uint8_t *data;       /* ROM pointer to tile data; NULL for self-managed assets */
    const uint8_t *count_ptr;  /* pointer to X_tile_data_count variable; NULL if self-managed */
    uint8_t        is_sprite;  /* 1 = sprite region (slots 0-63), 0 = BG region (slots 64-254) */
} tile_registry_entry_t;

/* VRAM slot bitmap allocator.
 * Slots 0-63 = sprite region. Slots 64-254 = BG region. Slot 255 = reserved failure sentinel.
 * Returns first slot of a free run of `count` consecutive slots in [region_start, region_end] (inclusive),
 * or 0xFF on failure (including if region_end > 254). */
uint8_t loader_alloc_slots(uint8_t region_start, uint8_t region_end, uint8_t count) NONBANKED;

/* Clears `count` consecutive bitmap bits starting at `first_slot`. */
void    loader_free_slots(uint8_t first_slot, uint8_t count) NONBANKED;

/* Returns the first VRAM slot allocated to `asset`, or 0xFF if not yet allocated. */
uint8_t loader_get_asset_slot(tile_asset_t asset) NONBANKED;

/* Initializes the VRAM bitmap (all free) and asset slot table (all 0xFF).
 * Call once during STATE_INIT. */
void    loader_init_allocator(void) NONBANKED;

/* Returns a pointer to the ROM-resident registry entry for `asset`.
 * Returns NULL if asset >= TILE_ASSET_COUNT. */
const tile_registry_entry_t *loader_get_registry(tile_asset_t asset) NONBANKED;

/* Returns the bank number for `asset` from the ROM-resident bank table. */
uint8_t loader_get_asset_bank(tile_asset_t asset) NONBANKED;

/* Sets the active track index (0-2) used by loader_get_registry() for TILE_ASSET_TRACK.
 * Call before loader_load_state() when entering a track-based state.
 * Asserts (halts) if track_id > 2. */
void loader_set_track(uint8_t track_id) NONBANKED;

/* Allocates VRAM slots and writes tile data for each asset in `assets[0..count-1]`.
 * Assets are allocated from the sprite region (slots 0-63) or BG region (slots 64-254)
 * based on each asset's is_sprite registry flag.
 * Asserts (halts) if: called while a state is already loaded; any asset has NULL data
 * (self-managed); or the VRAM region is exhausted. */
void loader_load_state(const tile_asset_t *assets, uint8_t count) NONBANKED;

/* Frees all allocated VRAM slots and resets the slot table to 0xFF.
 * Asserts (halts) if no state is currently loaded. */
void loader_unload_state(void) NONBANKED;

/* Returns the VRAM slot assigned to `asset`.
 * Asserts (halts) if the asset is not currently loaded.
 * Use loader_get_asset_slot() for a non-asserting query (returns 0xFF if not loaded). */
uint8_t loader_get_slot(tile_asset_t asset) NONBANKED;

/* Allocates and loads a single asset outside a state manifest (e.g. dynamic portrait).
 * Asserts (halts) if the asset is already loaded, out of range, or self-managed (NULL data). */
void loader_load_asset(tile_asset_t asset) NONBANKED;

#ifndef __SDCC
/* Test-only seam: inject a synthetic active map without a hardware bank switch. */
void loader_test_set_active_map(const uint8_t *map, uint8_t data_bank);
/* Test-only seam: reset bitmap and slot table to initial state. Call in setUp(). */
void loader_reset_bitmap_for_test(void);
#endif

#endif /* LOADER_H */
