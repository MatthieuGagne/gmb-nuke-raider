#ifndef LOADER_H
#define LOADER_H

#include <gb/gb.h>
#include <stdint.h>

/* NONBANKED VRAM loaders — bank-0 code, safe to call SWITCH_ROM.
 * Call these from any bank to load asset data into VRAM. */
void load_player_tiles(void) NONBANKED;
void load_track_tiles(void) NONBANKED;
void load_track_start_pos(int16_t *x, int16_t *y) NONBANKED;
void load_bullet_tiles(void) NONBANKED;

#endif /* LOADER_H */
