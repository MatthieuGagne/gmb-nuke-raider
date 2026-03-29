#pragma bank 255
#include "checkpoint.h"
#include "config.h"

static const CheckpointDef *cp_defs;   /* points to WRAM buffer in track.c */
static uint8_t cp_count;
static uint8_t cp_next;

void checkpoint_init(const CheckpointDef *defs, uint8_t count) BANKED {
    if (count > MAX_CHECKPOINTS) count = MAX_CHECKPOINTS;
    cp_defs  = defs;
    cp_count = count;
    cp_next  = 0u;
}

void checkpoint_update(int16_t px, int16_t py, int8_t vx, int8_t vy) BANKED {
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
    /* Direction check — if/else is equivalent to switch on SDCC/SM83 for 4 constants */
    if (cp->direction == CHECKPOINT_DIR_N)      { if (vy >= 0) return; }
    else if (cp->direction == CHECKPOINT_DIR_S) { if (vy <= 0) return; }
    else if (cp->direction == CHECKPOINT_DIR_E) { if (vx <= 0) return; }
    else if (cp->direction == CHECKPOINT_DIR_W) { if (vx >= 0) return; }
    cp_next++;
}

uint8_t checkpoint_all_cleared(void) BANKED {
    return (cp_next >= cp_count);
}

void checkpoint_reset(void) BANKED {
    cp_next = 0u;
}
