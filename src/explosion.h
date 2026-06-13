#ifndef EXPLOSION_H
#define EXPLOSION_H
#include <stdint.h>

void explosion_init(uint8_t turret_base, uint8_t car_base) BANKED;
void explosion_spawn(uint8_t oam, uint8_t tile_base, uint8_t flip, uint8_t is_car) BANKED;
void explosion_update(void) BANKED;
void explosion_render(void) BANKED;
uint8_t explosion_is_done(void) BANKED;

#ifndef __SDCC
uint8_t explosion_active_count(void);
#endif
#endif
