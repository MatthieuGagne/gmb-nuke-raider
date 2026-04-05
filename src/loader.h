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

/* Writes a single row of BG tiles directly to VRAM tilemap at (vram_x, vram_y).
 * vram_x and vram_y wrap mod 32. Must be called during VBlank or DISPLAY_OFF. */
void load_bkg_row(uint8_t vram_x, uint8_t vram_y,
                  uint8_t count, const uint8_t *tiles) NONBANKED;

#endif /* LOADER_H */
