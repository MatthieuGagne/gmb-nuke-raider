#ifndef LOADOUT_H
#define LOADOUT_H

#include <gb/gb.h>
#include <stdint.h>
#include "config.h"

void loadout_init(void) BANKED;

uint8_t loadout_get_car(void) BANKED;
uint8_t loadout_get_armor(void) BANKED;
uint8_t loadout_get_weapon1(void) BANKED;
uint8_t loadout_get_weapon2(void) BANKED;

void loadout_set_car(uint8_t v) BANKED;
void loadout_set_armor(uint8_t v) BANKED;
void loadout_set_weapon1(uint8_t v) BANKED;
void loadout_set_weapon2(uint8_t v) BANKED;

void loadout_cycle_car(int8_t dir) BANKED;
void loadout_cycle_armor(int8_t dir) BANKED;
void loadout_cycle_weapon1(int8_t dir) BANKED;
void loadout_cycle_weapon2(int8_t dir) BANKED;

#endif /* LOADOUT_H */
