#ifndef LOADOUT_H
#define LOADOUT_H

#include <stdint.h>
#include "config.h"

void loadout_init(void);

uint8_t loadout_get_car(void);
uint8_t loadout_get_armor(void);
uint8_t loadout_get_weapon1(void);
uint8_t loadout_get_weapon2(void);

void loadout_set_car(uint8_t v);
void loadout_set_armor(uint8_t v);
void loadout_set_weapon1(uint8_t v);
void loadout_set_weapon2(uint8_t v);

void loadout_cycle_car(int8_t dir);
void loadout_cycle_armor(int8_t dir);
void loadout_cycle_weapon1(int8_t dir);
void loadout_cycle_weapon2(int8_t dir);

#endif /* LOADOUT_H */
