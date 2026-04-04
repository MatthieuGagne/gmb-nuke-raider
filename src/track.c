#pragma bank 255
#include <gb/gb.h>
#include "track.h"
#include "banking.h"
#include "loader.h"
#include "checkpoint.h"

extern const int16_t track3_start_x;
extern const int16_t track3_start_y;
extern const uint8_t track3_map[];

static const TrackDesc track_table[] = {
    { track_map,  &track_start_x,  &track_start_y,  1u, &track_map_type,  TRACK1_REWARD, load_track_tiles  },
    { track2_map, &track2_start_x, &track2_start_y, 3u, &track2_map_type, TRACK2_REWARD, load_track2_tiles },
    { track3_map, &track3_start_x, &track3_start_y, 1u, &track3_map_type, 0u,            load_track3_tiles },
};

/* Tile index → TileType lookup table — static const is linked into ROM by SDCC on sm83 */
#define TILE_LUT_LEN 9u
static const uint8_t tile_type_lut[TILE_LUT_LEN] = {
    TILE_WALL,   /* 0: off-road */
    TILE_ROAD,   /* 1: road */
    TILE_ROAD,   /* 2: center dashes */
    TILE_SAND,   /* 3: sand */
    TILE_OIL,    /* 4: oil puddle */
    TILE_BOOST,  /* 5: boost pad */
    TILE_FINISH, /* 6: finish line — triggers lap detection */
    TILE_REPAIR, /* 7: repair pad */
    TILE_TURRET, /* 8: turret emplacement — impassable while active */
};

/* --- Track dispatch state --- */
static uint8_t active_track_id;
static uint8_t active_map_type = 0u;

/* Runtime track dimensions — set by load_track_header() at track_select() time.
 * Default to track 0 compile-time dimensions so calls work before track_select(). */
uint8_t active_map_w = 20u;   /* default: track 0 width  — overwritten by load_track_header() */
uint8_t active_map_h = 100u;  /* default: track 0 height — overwritten by load_track_header() */

/* Active track parameters — copied from the selected track's descriptor
 * at track_select() time. Avoids cross-bank reads in hot-path accessors.
 * active_map points PAST the 2-byte header so index math active_map[ty*w+tx] is correct. */
static const uint8_t *active_map     = track_map + 2;
static int16_t        active_start_x;
static int16_t        active_start_y;
static uint8_t        active_lap_count;

/* WRAM checkpoint buffer — filled by load_checkpoints() (bank-0 loader) at track_select() time.
 * Always accessed from WRAM; never read directly from ROM in banked code. */
static CheckpointDef wram_checkpoints[MAX_CHECKPOINTS];
static uint8_t       active_checkpoint_count = 0u;

void track_select(uint8_t id) BANKED {
    const TrackDesc *t;
    active_track_id = id;
    load_track_header(id);
    t = &track_table[id];
    active_map       = t->map + 2;
    active_start_x   = *t->start_x;
    active_start_y   = *t->start_y;
    active_lap_count = t->lap_count;
    active_map_type  = *t->map_type;
    load_checkpoints(id, wram_checkpoints, &active_checkpoint_count);
}

uint8_t  track_get_lap_count(void) BANKED { return active_lap_count; }
uint8_t  track_get_map_type(void)  BANKED { return active_map_type;  }
int16_t  track_get_start_x(void)   BANKED { return active_start_x;   }
int16_t  track_get_start_y(void)   BANKED { return active_start_y;   }
/* track_table is static const in this file; same bank guaranteed by #pragma bank 255 */
uint16_t track_get_reward(void)    BANKED { return track_table[active_track_id].reward; }
uint8_t  track_get_id(void)        BANKED { return active_track_id; }

TileType track_tile_type_from_index(uint8_t tile_idx) BANKED {
    if (tile_idx >= TILE_LUT_LEN) return TILE_ROAD;
    return (TileType)tile_type_lut[tile_idx];
}

TileType track_tile_type(int16_t world_x, int16_t world_y) BANKED {
    uint8_t tx;
    uint8_t ty;
    if (world_x < 0 || world_y < 0) return TILE_WALL;
    tx = (uint8_t)((uint16_t)world_x >> 3u);
    ty = (uint8_t)((uint16_t)world_y >> 3u);
    if (tx >= active_map_w || ty >= active_map_h) return TILE_WALL;
    return track_tile_type_from_index(active_map[(uint16_t)ty * active_map_w + tx]);
}

void track_init(void) BANKED {
    track_table[active_track_id].load_tiles();
    /* Tilemap loaded by camera_init() */
    SHOW_BKG;
}

uint8_t track_get_raw_tile(uint8_t tx, uint8_t ty) BANKED {
    if (tx >= active_map_w || ty >= active_map_h) return 0u;
    return active_map[(uint16_t)ty * active_map_w + tx];
}

void track_fill_row(uint8_t ty, uint8_t *buf) BANKED {
    uint8_t tx;
    uint16_t row_base;
    if (ty >= active_map_h) {
        for (tx = 0u; tx < active_map_w; tx++) buf[tx] = 0u;
        return;
    }
    row_base = (uint16_t)ty * active_map_w;
    for (tx = 0u; tx < active_map_w; tx++) {
        buf[tx] = active_map[row_base + tx];
    }
}

uint8_t track_passable(int16_t world_x, int16_t world_y) BANKED {
    uint8_t tx;
    uint8_t ty;
    if (world_x < 0 || world_y < 0) return 0u;
    tx = (uint8_t)((uint16_t)world_x >> 3u);
    ty = (uint8_t)((uint16_t)world_y >> 3u);
    if (tx >= active_map_w || ty >= active_map_h) return 0u;
    return active_map[(uint16_t)ty * active_map_w + tx] != 0u;
}

const CheckpointDef *track_get_checkpoints(void) BANKED { return wram_checkpoints; }
uint8_t track_get_checkpoint_count(void) BANKED { return active_checkpoint_count; }

void track_fill_row_range(uint8_t ty, uint8_t tx_start, uint8_t count, uint8_t *buf) BANKED {
    uint8_t i;
    uint16_t row_base;
    uint8_t tx;
    if (ty >= active_map_h) {
        for (i = 0u; i < count; i++) buf[i] = 0u;
        return;
    }
    row_base = (uint16_t)ty * active_map_w;
    for (i = 0u; i < count; i++) {
        tx = tx_start + i;
        buf[i] = (tx < active_map_w) ? active_map[row_base + tx] : 0u;
    }
}

void track_fill_col(uint8_t tx, uint8_t ty_start, uint8_t count, uint8_t *buf) BANKED {
    uint8_t i;
    uint8_t ty;
    if (tx >= active_map_w) {
        for (i = 0u; i < count; i++) buf[i] = 0u;
        return;
    }
    for (i = 0u; i < count; i++) {
        ty = ty_start + i;
        buf[i] = (ty < active_map_h)
            ? active_map[(uint16_t)ty * active_map_w + tx]
            : 0u;
    }
}

#ifndef __SDCC
/* Test-only seam — not compiled into the GB ROM. */
void track_test_set_map(const uint8_t *map, uint8_t w, uint8_t h) {
    active_map   = map;
    active_map_w = w;
    active_map_h = h;
}
#endif
