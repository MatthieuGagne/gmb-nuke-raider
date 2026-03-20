#ifndef MUSIC_H
#define MUSIC_H

#include <gb/gb.h>
#include "hUGEDriver.h"

/* music_init() — enable APU and start the default song. Call once in main()
 * before the game loop, after hardware init. */
void music_init(void);

/* music_start() — switch to a different track at runtime.
 * bank: the ROM bank where song lives (use BANK(sym) macro).
 * song: pointer to the hUGESong_t in that bank. */
void music_start(uint8_t bank, const hUGESong_t *song);

/* music_tick() — advance the music driver by one tick. Call once per frame
 * in the main loop (not from vbl_isr). */
void music_tick(void);

#endif /* MUSIC_H */
