/* src/sfx.h — two-channel SFX system (CH1 + CH4), bank 0 NONBANKED */
#ifndef SFX_H
#define SFX_H

#include <stdint.h>

typedef uint8_t sfx_id_t;

#define SFX_SHOOT  0u  /* CH4 noise burst  — player weapon fire */
#define SFX_HIT    1u  /* CH4 noise hit    — wall/collision damage */
#define SFX_HEAL   2u  /* CH1 rising sweep — repair pad heal */
#define SFX_UI     3u  /* CH1 short blip   — hub dialog confirm */
#define SFX_COUNT  4u  /* total IDs; must match sfx_defs[] table in sfx.c */

void sfx_init(void);
void sfx_play(sfx_id_t id);
void sfx_tick(void);

/* Test-visible helpers — never call from game code.
 * sfx_ch1_id() / sfx_ch4_id() return SFX_COUNT (not a valid id) when idle. */
uint8_t sfx_def_duration(sfx_id_t id);
uint8_t sfx_ch1_timer(void);
uint8_t sfx_ch4_timer(void);
uint8_t sfx_ch1_id(void);
uint8_t sfx_ch4_id(void);

#endif /* SFX_H */
