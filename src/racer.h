#ifndef RACER_H
#define RACER_H

#include <stdint.h>
#include "banking.h"

void    racer_init(uint8_t tile_base) BANKED;
void    racer_init_empty(void) BANKED;
void    racer_hide(void) BANKED;
uint8_t racer_update(void) BANKED;
void    racer_render(void) BANKED;

#ifndef __SDCC
void    racer_spawn_for_test(int16_t px, int16_t py,
                              uint8_t *wp_tx, uint8_t *wp_ty,
                              uint8_t wp_count, uint8_t finish_dir,
                              uint8_t lap_total);
void    racer_set_laps_done_for_test(uint8_t n);
void    racer_place_on_finish_for_test(uint8_t tx, uint8_t ty, uint8_t dir);
void    racer_set_wp_idx_for_test(uint8_t slot, uint8_t idx);
void    racer_set_pos_for_test(uint8_t slot, int16_t px, int16_t py);
uint8_t racer_get_wp_idx(uint8_t slot);
int8_t  racer_get_vx(uint8_t slot);
int8_t  racer_get_vy(uint8_t slot);
uint8_t racer_get_gear(uint8_t slot);
int16_t racer_get_px(uint8_t slot);
int16_t racer_get_py(uint8_t slot);
void    racer_set_vel_for_test(uint8_t slot, int8_t vx, int8_t vy);
void    racer_set_gear_for_test(uint8_t slot, uint8_t gear);
#endif

#endif /* RACER_H */
