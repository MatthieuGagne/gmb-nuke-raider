#ifndef TRACK_H
#define TRACK_H

#include <gb/gb.h>
#include <stdint.h>
#include "config.h"

/* Terrain tile types — uint8_t, NOT typedef enum (SDCC makes enums 16-bit) */
typedef uint8_t TileType;
#define TILE_WALL   0u
#define TILE_ROAD   1u
#define TILE_SAND   2u
#define TILE_OIL    3u
#define TILE_BOOST  4u
#define TILE_REPAIR 5u
#define TILE_FINISH  6u
#define TILE_TURRET  7u

TileType track_tile_type_from_index(uint8_t tile_idx) BANKED;
TileType track_tile_type(int16_t world_x, int16_t world_y) BANKED;

extern const uint8_t track_tile_data[];
extern const uint8_t track_tile_data_count;
extern const int16_t track_start_x;
extern const int16_t track_start_y;
extern const uint8_t track_map[];
extern const uint8_t track2_map[];
extern const int16_t track2_start_x;
extern const int16_t track2_start_y;

/* Runtime track dimensions — set by load_track_header() at track_select() time.
 * Replace compile-time MAP_TILES_W / MAP_TILES_H in all runtime code. */
extern uint8_t active_map_w;
extern uint8_t active_map_h;

#include "checkpoint.h"
#include "banking.h"
BANKREF_EXTERN(track_map)
BANKREF_EXTERN(track_tile_data)
BANKREF_EXTERN(track_start_x)
BANKREF_EXTERN(track_start_y)
BANKREF_EXTERN(track2_map)
BANKREF_EXTERN(track2_start_x)

/* Checkpoint ROM tables — emitted by tmx_to_c.py into track_map.c / track2_map.c */
extern const CheckpointDef track_checkpoints[];
extern const uint8_t        track_checkpoint_count;
extern const CheckpointDef track2_checkpoints[];
extern const uint8_t        track2_checkpoint_count;

/* --- TrackDesc dispatch table --- */

/* Select active track before entering STATE_PLAYING.
 * Must be called from bank-0 code (state_overmap.c) via the BANKED trampoline. */
void track_select(uint8_t id) BANKED;

/* Accessors — read from active TrackDesc */
uint8_t track_get_lap_count(void) BANKED;
int16_t track_get_start_x(void) BANKED;
int16_t track_get_start_y(void) BANKED;

const CheckpointDef *track_get_checkpoints(void) BANKED;
uint8_t              track_get_checkpoint_count(void) BANKED;

void    track_init(void) BANKED;
uint8_t track_passable(int16_t world_x, int16_t world_y) BANKED;

/* Returns the raw tile index at world tile position (tx, ty).
 * BANKED — trampoline handles cross-bank dispatch safely. */
uint8_t track_get_raw_tile(uint8_t tx, uint8_t ty) BANKED;

/* Fills buf[0..active_map_w-1] with raw tile indices for world tile row ty.
 * Zeros buf on OOB ty. One BANKED call replaces 20 serial track_get_raw_tile()
 * calls in camera stream_row — reduces VBlank overrun risk. */
void track_fill_row(uint8_t ty, uint8_t *buf) BANKED;

/* Fills buf[0..count-1] with raw tile indices for columns tx_start..tx_start+count-1
 * of world tile row ty. Zeros buf entries for any OOB tile. BANKED. */
void track_fill_row_range(uint8_t ty, uint8_t tx_start, uint8_t count, uint8_t *buf) BANKED;

/* Fills buf[0..count-1] with raw tile indices for rows ty_start..ty_start+count-1
 * of world tile column tx. Zeros buf entries for any OOB tile. BANKED. */
void track_fill_col(uint8_t tx, uint8_t ty_start, uint8_t count, uint8_t *buf) BANKED;

#ifndef __SDCC
/* Test-only seam: inject a synthetic map without hardware (gcc host tests only).
 * Never compiled into the GB ROM. */
void track_test_set_map(const uint8_t *map, uint8_t w, uint8_t h);
#endif

#endif /* TRACK_H */
