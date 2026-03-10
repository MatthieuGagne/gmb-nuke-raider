#ifndef HUD_H
#define HUD_H

#include <stdint.h>

/* --- Public API --- */
void    hud_init(void);          /* call in state_playing enter(), display must be OFF */
void    hud_update(void);        /* call in game logic phase each frame */
void    hud_render(void);        /* call in VBlank phase — writes win tiles when dirty */
void    hud_set_hp(uint8_t hp);  /* future use: wire to player damage system */

/* --- Test accessors (also useful for debug) --- */
uint16_t hud_get_seconds(void);  /* total elapsed seconds */
uint8_t  hud_is_dirty(void);     /* 1 if render needed, 0 if up to date */

#endif /* HUD_H */
