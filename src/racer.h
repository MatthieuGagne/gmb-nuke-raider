#ifndef RACER_H
#define RACER_H

#include <stdint.h>
#include "banking.h"

extern uint8_t racer_active[];   /* SoA active flags — exported for state queries */

void    racer_init(uint8_t tile_base) BANKED;
void    racer_init_empty(void) BANKED;
void    racer_hide(void) BANKED;
uint8_t racer_update(void) BANKED;
void    racer_render(void) BANKED;
int16_t racer_get_px(uint8_t slot) BANKED;
int16_t racer_get_py(uint8_t slot) BANKED;
uint8_t racer_get_wp_idx_banked(uint8_t slot) BANKED;
uint8_t racer_get_wp_count(uint8_t slot) BANKED;
uint8_t racer_get_wp_tx(uint8_t slot, uint8_t idx) BANKED;
uint8_t racer_get_wp_ty(uint8_t slot, uint8_t idx) BANKED;
uint8_t racer_blocks_pixel(int16_t wx, int16_t wy) BANKED;
uint8_t racer_overlaps_player(int16_t px, int16_t py) BANKED;
/* Mutual contact damage (#412 + #417). On any active-racer overlap with the
 * player AABB: chips ENEMY_RAM_DAMAGE off the racer behind a per-racer 30-frame
 * cooldown (blink, route to the #411 death path on a lethal result) AND applies
 * RACER_RAM_DAMAGE to the player (debounced by damage.c i-frames). Returns 1 on
 * any overlap (caller plays SFX), 0 otherwise. Dying racers (active=0) excluded. */
uint8_t racer_apply_contact_damage(int16_t px, int16_t py) BANKED;

#ifndef __SDCC
void    racer_spawn_for_test(int16_t px, int16_t py,
                              uint8_t *wp_tx, uint8_t *wp_ty,
                              uint8_t wp_count, uint8_t finish_dir,
                              uint8_t lap_total);
void    racer_place_on_finish_for_test(uint8_t tx, uint8_t ty, uint8_t dir);
void    racer_set_wp_idx_for_test(uint8_t slot, uint8_t idx);
void    racer_set_pos_for_test(uint8_t slot, int16_t px, int16_t py);
uint8_t racer_get_wp_idx(uint8_t slot);
int8_t  racer_get_vx(uint8_t slot);
int8_t  racer_get_vy(uint8_t slot);
uint8_t racer_get_gear(uint8_t slot);
void    racer_set_vel_for_test(uint8_t slot, int8_t vx, int8_t vy);
void    racer_set_gear_for_test(uint8_t slot, uint8_t gear);
uint8_t racer_get_hp_for_test(uint8_t slot);
void    racer_set_hp_for_test(uint8_t slot, uint8_t hp);
uint8_t racer_get_ram_cd_for_test(uint8_t slot);
void    racer_set_ram_cd_for_test(uint8_t slot, uint8_t c);
uint8_t racer_get_hit_flash_for_test(uint8_t slot);
void    racer_set_dir_for_test(uint8_t slot, uint8_t dir);
uint8_t racer_is_dying_for_test(uint8_t slot);
uint8_t racer_get_death_timer_for_test(uint8_t slot);
void    racer_set_oam_for_test(uint8_t slot, uint8_t h0, uint8_t h1, uint8_t h2, uint8_t h3);
#endif

#endif /* RACER_H */
