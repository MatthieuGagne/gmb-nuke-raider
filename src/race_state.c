#pragma bank 255
#include "race_state.h"
#include "track.h"
#include "player.h"    /* player_get_x(), player_get_y(), DIR_T/B/L/R/... */
#include "racer.h"     /* racer_get_px(), racer_get_py() */

static uint8_t rs_cp_next[MAX_RACERS];
static uint8_t rs_laps[MAX_RACERS];
static uint8_t rs_active[MAX_RACERS];
static uint8_t rs_lap_total;

void race_state_init(uint8_t lap_total) BANKED {
    uint8_t i;
    rs_lap_total = lap_total;
    for (i = 0u; i < MAX_RACERS; i++) {
        rs_cp_next[i] = 0u;
        rs_laps[i]    = 0u;
        rs_active[i]  = 0u;
    }
}

void race_state_set_active(uint8_t slot, uint8_t active) BANKED {
    rs_active[slot] = active;
}

void race_state_update_cp(uint8_t slot, int16_t x, int16_t y, uint8_t dir) BANKED {
    const CheckpointDef *defs;
    const CheckpointDef *cp;
    uint8_t count;

    if (!rs_active[slot]) return;
    count = track_get_checkpoint_count();
    if (rs_cp_next[slot] >= count) return;
    defs = track_get_checkpoints();
    cp   = &defs[rs_cp_next[slot]];

    if (x < cp->x)                                              return;
    if (x >= (int16_t)((uint16_t)cp->x + (uint16_t)cp->w))    return;
    if (y < cp->y)                                              return;
    if (y >= (int16_t)((uint16_t)cp->y + (uint16_t)cp->h))    return;

    if      (cp->direction == CHECKPOINT_DIR_N) { if (dir != DIR_T  && dir != DIR_RT && dir != DIR_LT) return; }
    else if (cp->direction == CHECKPOINT_DIR_S) { if (dir != DIR_B  && dir != DIR_RB && dir != DIR_LB) return; }
    else if (cp->direction == CHECKPOINT_DIR_E) { if (dir != DIR_R  && dir != DIR_RT && dir != DIR_RB) return; }
    else if (cp->direction == CHECKPOINT_DIR_W) { if (dir != DIR_L  && dir != DIR_LT && dir != DIR_LB) return; }

    rs_cp_next[slot]++;
}

uint8_t race_state_advance_lap(uint8_t slot) BANKED {
    if ((uint8_t)(rs_laps[slot] + 1u) >= rs_lap_total) {
        return 1u;
    }
    rs_laps[slot]    = (uint8_t)(rs_laps[slot] + 1u);
    rs_cp_next[slot] = 0u;
    return 0u;
}

uint8_t race_state_get_cp(uint8_t slot) BANKED       { return rs_cp_next[slot]; }
uint8_t race_state_get_laps(uint8_t slot) BANKED     { return rs_laps[slot]; }
uint8_t race_state_get_lap_total(void) BANKED         { return rs_lap_total; }

uint8_t race_state_all_cp_cleared(uint8_t slot) BANKED {
    return (rs_cp_next[slot] >= track_get_checkpoint_count()) ? 1u : 0u;
}

/* Direction-aware position comparison. Static in SDCC build; exposed for host tests. */
#ifndef __SDCC
uint8_t
#else
static uint8_t
#endif
pos_from_dir(uint8_t dir,
             int16_t px,  int16_t py,
             int16_t rpx, int16_t rpy) {
    if (dir == CHECKPOINT_DIR_N) return (py  <= rpy) ? 1u : 2u;
    if (dir == CHECKPOINT_DIR_S) return (py  >= rpy) ? 1u : 2u;
    if (dir == CHECKPOINT_DIR_E) return (px  >= rpx) ? 1u : 2u;
    return (px <= rpx) ? 1u : 2u;   /* CHECKPOINT_DIR_W */
}

/* Manhattan-distance tiebreaker. Static in SDCC build; exposed for host tests. */
#ifndef __SDCC
uint8_t
#else
static uint8_t
#endif
pos_from_manhattan(int16_t px,  int16_t py,
                   int16_t rpx, int16_t rpy,
                   const CheckpointDef *next) {
    int16_t cx  = next->x + (int16_t)(next->w >> 1u);
    int16_t cy  = next->y + (int16_t)(next->h >> 1u);
    int16_t pdx = px  - cx; if (pdx < 0) pdx = -pdx;
    int16_t pdy = py  - cy; if (pdy < 0) pdy = -pdy;
    int16_t rdx = rpx - cx; if (rdx < 0) rdx = -rdx;
    int16_t rdy = rpy - cy; if (rdy < 0) rdy = -rdy;
    uint16_t pd = (uint16_t)pdx + (uint16_t)pdy;
    uint16_t rd = (uint16_t)rdx + (uint16_t)rdy;
    return (pd <= rd) ? 1u : 2u;
}

uint8_t race_state_rank_player(void) BANKED {
    uint8_t i;
    uint8_t pos = 1u;
    uint8_t player_laps = rs_laps[PLAYER_SLOT];
    uint8_t player_cp   = rs_cp_next[PLAYER_SLOT];
    /* Full-tie inputs are loop-invariant for one call; compute lazily on the
     * first full tie, then reuse for every subsequent full-tie rival. Each
     * value comes from a BANKED accessor, so caching avoids repeat trampolines. */
    int16_t player_px = 0;
    int16_t player_py = 0;
    const CheckpointDef *next = 0;
    uint8_t finish_dir = 0u;
    uint8_t count = 0u;
    uint8_t tie_ready = 0u;
    uint8_t past_all_cps = 0u;

    for (i = 0u; i < MAX_RACERS; i++) {
        if (i == PLAYER_SLOT) continue;
        if (!rs_active[i]) continue;

        if (player_laps > rs_laps[i]) {
            /* player ahead on laps — pos unaffected */
        } else if (player_laps < rs_laps[i]) {
            pos++;
        } else if (player_cp > rs_cp_next[i]) {
            /* tied on laps, player ahead on checkpoints — pos unaffected */
        } else if (player_cp < rs_cp_next[i]) {
            pos++;
        } else {
            /* Full tie: Manhattan distance / finish direction.
             * Each rival ahead by distance increments pos (a 3-car field can
             * resolve to P:3). Same laps->CPs->distance order for every rival. */
            if (!tie_ready) {
                count     = track_get_checkpoint_count();
                player_px = player_get_x();
                player_py = player_get_y();
                if (player_cp < count) {
                    next = &track_get_checkpoints()[player_cp];
                } else {
                    /* Past all CPs — compare by finish direction */
                    finish_dir   = track_get_finish_direction();
                    past_all_cps = 1u;
                }
                tie_ready = 1u;
            }

            if (!past_all_cps) {
                if (pos_from_manhattan(player_px, player_py,
                                       racer_get_px(i), racer_get_py(i),
                                       next) == 2u) {
                    pos++;
                }
            } else {
                if (pos_from_dir(finish_dir, player_px, player_py,
                                 racer_get_px(i), racer_get_py(i)) == 2u) {
                    pos++;
                }
            }
        }
    }
    return pos;
}

#ifndef __SDCC
void race_state_set_laps_for_test(uint8_t slot, uint8_t n) { rs_laps[slot] = n; }
void race_state_set_cp_for_test(uint8_t slot, uint8_t n)   { rs_cp_next[slot] = n; }
#endif
