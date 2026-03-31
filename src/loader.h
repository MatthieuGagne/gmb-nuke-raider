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
void load_track_start_pos(int16_t *x, int16_t *y) NONBANKED;
void load_bullet_tiles(void) NONBANKED;
void load_turret_tiles(void) NONBANKED;
void load_overmap_car_tiles(void) NONBANKED;

/* Cross-bank checkpoint copy — switches to the generated map file's bank,
 * copies checkpoint ROM array to dst[], and writes count. Bank-0 only. */
void load_checkpoints(uint8_t id, CheckpointDef *dst, uint8_t *count) NONBANKED;

#endif /* LOADER_H */
