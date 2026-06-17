#ifndef PATROL_H
#define PATROL_H

#include <stdint.h>
#include "player.h"   /* player_dir_t */
#include "config.h"

/* Initialise the patrol pool from track.tmx NPC_TYPE_PATROL spawn + route.
 * tile_base: OBJ tile index from loader_get_slot(TILE_ASSET_PLAYER) (reuses
 * the racer/player car sprite). Reads track_get_id(); call after track_select(). */
void    patrol_init(uint8_t tile_base) BANKED;

/* Zero the pool without a map scan — host-test helper only. */
void    patrol_init_empty(void) BANKED;

/* Per-frame update. px/py = player world position.
 * Returns void — player death flows through damage.c (like turret). */
void    patrol_update(int16_t px, int16_t py) BANKED;

/* Per-frame VBlank render: 4-OAM directional car, screen pos recomputed each frame. */
void    patrol_render(void) BANKED;

/* Hide all patrol OAM sprites (call on state exit). */
void    patrol_hide(void) BANKED;

/* Number of active patrols. */
uint8_t patrol_count_active(void) BANKED;

/* Pure FSM transition: hysteresis on Manhattan(dx,dy) where (dx,dy)=player-patrol.
 * Enter CHASE when Manhattan < PATROL_DETECT_RADIUS;
 * return PATROL when Manhattan >= PATROL_LEAVE_RADIUS; else keep `mode`. */
uint8_t patrol_fsm_next(uint8_t mode, int16_t dx, int16_t dy) BANKED;

/* Test-only accessors — not for production callers. */
#ifndef __SDCC
uint8_t patrol_get_state(uint8_t i);
uint8_t patrol_get_hp(uint8_t i);
uint8_t patrol_get_hit_flash_for_test(uint8_t i);
int16_t patrol_get_px(uint8_t i);
int16_t patrol_get_py(uint8_t i);
uint8_t patrol_get_wp_idx(uint8_t i);
uint8_t patrol_is_active(uint8_t i);
void    patrol_set_pos_for_test(uint8_t i, int16_t px, int16_t py);
void    patrol_set_mode_for_test(uint8_t i, uint8_t mode);
void    patrol_set_hp_for_test(uint8_t i, uint8_t hp);
void    patrol_set_fire_timer_for_test(uint8_t i, uint8_t t);
void    patrol_spawn_for_test(int16_t px, int16_t py,
                              uint8_t *wp_tx, uint8_t *wp_ty, uint8_t wp_count);
#endif

#endif /* PATROL_H */
