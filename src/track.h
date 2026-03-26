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
#define TILE_FINISH 6u

TileType track_tile_type_from_index(uint8_t tile_idx) BANKED;
TileType track_tile_type(int16_t world_x, int16_t world_y) BANKED;

#define MAP_PX_W  160u   /* MAP_TILES_W * 8 */
#define MAP_PX_H  800u   /* MAP_TILES_H * 8 */

extern const uint8_t track_tile_data[];
extern const uint8_t track_tile_data_count;
extern const int16_t track_start_x;
extern const int16_t track_start_y;
extern const uint8_t track_map[];
extern const uint8_t track2_map[];
extern const int16_t track2_start_x;
extern const int16_t track2_start_y;

#include "banking.h"
BANKREF_EXTERN(track_map)
BANKREF_EXTERN(track_tile_data)
BANKREF_EXTERN(track_start_x)
BANKREF_EXTERN(track_start_y)
BANKREF_EXTERN(track2_map)
BANKREF_EXTERN(track2_start_x)

/* --- TrackDesc dispatch table --- */

/* Select active track before entering STATE_PLAYING.
 * Must be called from bank-0 code (state_overmap.c) via the BANKED trampoline. */
void track_select(uint8_t id) BANKED;

/* Accessors — read from active TrackDesc */
uint8_t track_get_lap_count(void) BANKED;
int16_t track_get_start_x(void) BANKED;
int16_t track_get_start_y(void) BANKED;

void    track_init(void) BANKED;
uint8_t track_passable(int16_t world_x, int16_t world_y) BANKED;

/* Returns the raw tile index at world tile position (tx, ty).
 * BANKED — trampoline handles cross-bank dispatch safely. */
uint8_t track_get_raw_tile(uint8_t tx, uint8_t ty) BANKED;

#endif /* TRACK_H */
