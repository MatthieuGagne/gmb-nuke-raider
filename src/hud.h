#ifndef HUD_H
#define HUD_H

#include <stdint.h>

/* --- Public API --- */
void    hud_init(void) BANKED;          /* call in state_playing enter(), display must be OFF */
void    hud_update(void) BANKED;        /* call in game logic phase each frame */
void    hud_render(void) BANKED;        /* call in VBlank phase — writes win tiles when dirty */
void    hud_set_hp(uint8_t hp) BANKED;  /* wire to player damage system */
void    hud_set_lap(uint8_t current, uint8_t total) BANKED;

/* --- Test accessors (also useful for debug) --- */
uint16_t hud_get_seconds(void) BANKED;  /* total elapsed seconds */
uint8_t  hud_is_dirty(void) BANKED;     /* 1 if render needed, 0 if up to date */

#endif /* HUD_H */
