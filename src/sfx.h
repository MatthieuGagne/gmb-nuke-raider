/* src/sfx.h — one-shot SFX system */
#ifndef SFX_H
#define SFX_H

#include <gb/gb.h>
#include <stdint.h>

/* SFX identifiers */
#define SFX_EXPLOSION  0u
#define SFX_PICKUP     1u
#define SFX_COUNT      2u  /* total defined SFX; must match sfx_defs[] table size */

void sfx_init(void) BANKED;
void sfx_play(uint8_t sfx_id) BANKED;
void sfx_update(void) BANKED;

/* Test-visible helpers — called only from tests; not wired into the game loop */
uint8_t sfx_active_count(void) BANKED;
uint8_t sfx_def_duration(uint8_t sfx_id) BANKED;

#endif /* SFX_H */
