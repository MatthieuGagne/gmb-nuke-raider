#pragma bank 255
#include "player.h"
#include "checkpoint.h"
#include "config.h"

static const CheckpointDef *cp_defs;   /* points to WRAM buffer in track.c */
static uint8_t cp_count;
uint8_t cp_next;

void checkpoint_init(const CheckpointDef *defs, uint8_t count) BANKED {
    if (count > MAX_CHECKPOINTS) count = MAX_CHECKPOINTS;
    cp_defs  = defs;
    cp_count = count;
    cp_next  = 0u;
}

void checkpoint_update(int16_t px, int16_t py, uint8_t pdir) BANKED {
    const CheckpointDef *cp;
    if (cp_next >= cp_count) return;
    cp = &cp_defs[cp_next];
    /* AABB: car top-left (px, py) vs checkpoint rect.
     * Cast safety: cp->x + cp->w promoted to uint16_t before (int16_t) cast;
     * map coordinates are always non-negative so no wrap concern. */
    if (px < cp->x)                          return;
    if (px >= (int16_t)(cp->x + cp->w))      return;
    if (py < cp->y)                          return;
    if (py >= (int16_t)(cp->y + cp->h))      return;
    /* Direction check — if/else is equivalent to switch on SDCC/SM83 for 4 constants.
     * Uses facing direction (pdir) instead of velocity to avoid racer-blocking bug
     * where collision zeroes vx/vy and silently skips the checkpoint. */
    if      (cp->direction == CHECKPOINT_DIR_N) { if (pdir != DIR_T  && pdir != DIR_RT && pdir != DIR_LT) return; }
    else if (cp->direction == CHECKPOINT_DIR_S) { if (pdir != DIR_B  && pdir != DIR_RB && pdir != DIR_LB) return; }
    else if (cp->direction == CHECKPOINT_DIR_E) { if (pdir != DIR_R  && pdir != DIR_RT && pdir != DIR_RB) return; }
    else if (cp->direction == CHECKPOINT_DIR_W) { if (pdir != DIR_L  && pdir != DIR_LT && pdir != DIR_LB) return; }
    cp_next++;
}

uint8_t checkpoint_all_cleared(void) BANKED {
    return (cp_next >= cp_count);
}

void checkpoint_reset(void) BANKED {
    cp_next = 0u;
}

uint8_t checkpoint_get_cp_next(void) BANKED {
    return cp_next;
}

const CheckpointDef *checkpoint_get_next_def(void) BANKED {
    if (cp_next >= cp_count) return NULL;
    return &cp_defs[cp_next];
}
