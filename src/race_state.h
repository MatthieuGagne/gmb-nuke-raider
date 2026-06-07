#ifndef RACE_STATE_H
#define RACE_STATE_H

#include <stdint.h>
#include "banking.h"
#include "track.h"   /* CheckpointDef, CHECKPOINT_DIR_*, track_get_checkpoints() */

/* Lifecycle */
void    race_state_init(uint8_t lap_total) BANKED;
void    race_state_set_active(uint8_t slot, uint8_t active) BANKED;

/* Per-frame update: AABB+direction checkpoint detection for one slot */
void    race_state_update_cp(uint8_t slot, int16_t x, int16_t y, uint8_t dir) BANKED;

/* Lap gate — call when finish tile + direction validated for this slot.
 * Returns 1 if race is over for this slot, 0 if lap incremented. */
uint8_t race_state_advance_lap(uint8_t slot) BANKED;

/* Accessors */
uint8_t race_state_get_cp(uint8_t slot) BANKED;
uint8_t race_state_get_laps(uint8_t slot) BANKED;   /* 0-based completed laps */
uint8_t race_state_get_lap_total(void) BANKED;
uint8_t race_state_all_cp_cleared(uint8_t slot) BANKED;

/* Position ranking — returns player's 1-based ordinal rank among all active slots */
uint8_t race_state_rank_player(void) BANKED;

#ifndef __SDCC
/* Test-only seams */
void    race_state_set_laps_for_test(uint8_t slot, uint8_t n);
void    race_state_set_cp_for_test(uint8_t slot, uint8_t n);
/* Direction-aware position comparison (static in SDCC, exposed for host tests). */
uint8_t pos_from_dir(uint8_t dir,
                     int16_t px,  int16_t py,
                     int16_t rpx, int16_t rpy);
/* Manhattan-distance tiebreaker to checkpoint center. */
uint8_t pos_from_manhattan(int16_t px,  int16_t py,
                           int16_t rpx, int16_t rpy,
                           const CheckpointDef *next);
#endif

#endif /* RACE_STATE_H */
