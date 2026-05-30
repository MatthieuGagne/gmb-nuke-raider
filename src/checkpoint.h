#ifndef CHECKPOINT_H
#define CHECKPOINT_H

#include <gb/gb.h>
/* Note: callers needing DIR_* constants must include "player.h" before this header.
 * checkpoint.h cannot include player.h directly — player.h → track.h → checkpoint.h (cycle). */

/* Direction constants — match Tiled 'direction' property values */
#define CHECKPOINT_DIR_N 0u  /* north: player facing DIR_T/RT/LT */
#define CHECKPOINT_DIR_S 1u  /* south: player facing DIR_B/RB/LB */
#define CHECKPOINT_DIR_E 2u  /* east:  player facing DIR_R/RT/RB */
#define CHECKPOINT_DIR_W 3u  /* west:  player facing DIR_L/LT/LB */

/* Static descriptor for one checkpoint — populated by tmx_to_c.py-generated C.
 * Used as a ROM table (generated files) and a WRAM copy buffer (track.c).
 * AoS is correct here: checkpoint_update() reads ALL fields of ONE entry per frame. */
typedef struct {
    int16_t x;
    int16_t y;
    uint8_t w;
    uint8_t h;
    uint8_t index;
    uint8_t direction;
} CheckpointDef;

/* checkpoint_init: call in state_playing enter() via track_get_checkpoints().
 * defs must point to a stable WRAM buffer (WRAM copy from track.c — NOT a ROM pointer). */
void    checkpoint_init(const CheckpointDef *defs, uint8_t count) BANKED;

/* checkpoint_update: call every frame after player_update().
 * px, py = player top-left world position; pdir = player facing direction (uint8_t, DIR_* constants). */
void    checkpoint_update(int16_t px, int16_t py, uint8_t pdir) BANKED;

/* Returns 1 if all checkpoints cleared (or count == 0), 0 otherwise. */
uint8_t checkpoint_all_cleared(void) BANKED;

/* Resets cp_next to 0. Call after a valid non-final lap. */
void    checkpoint_reset(void) BANKED;

#endif /* CHECKPOINT_H */
