#pragma bank 255
#include "loadout.h"

static uint8_t ld_car;
static uint8_t ld_armor;
static uint8_t ld_weapon1;
static uint8_t ld_weapon2;

void loadout_init(void) BANKED {
    ld_car     = LOADOUT_DEFAULT_CAR;
    ld_armor   = LOADOUT_DEFAULT_ARMOR;
    ld_weapon1 = LOADOUT_DEFAULT_WEAPON1;
    ld_weapon2 = LOADOUT_DEFAULT_WEAPON2;
}

uint8_t loadout_get_car(void) BANKED     { return ld_car;     }
uint8_t loadout_get_armor(void) BANKED   { return ld_armor;   }
uint8_t loadout_get_weapon1(void) BANKED { return ld_weapon1; }
uint8_t loadout_get_weapon2(void) BANKED { return ld_weapon2; }

void loadout_set_car(uint8_t v) BANKED     { ld_car     = v; }
void loadout_set_armor(uint8_t v) BANKED   { ld_armor   = v; }
void loadout_set_weapon1(uint8_t v) BANKED { ld_weapon1 = v; }
void loadout_set_weapon2(uint8_t v) BANKED { ld_weapon2 = v; }

static uint8_t cycle(uint8_t cur, int8_t dir) {
    if (dir > 0) {
        return (uint8_t)((cur + 1u) % LOADOUT_OPTIONS_PER_FIELD);
    } else {
        return (cur == 0u) ? (uint8_t)(LOADOUT_OPTIONS_PER_FIELD - 1u) : (uint8_t)(cur - 1u);
    }
}

void loadout_cycle_car(int8_t dir) BANKED     { ld_car     = cycle(ld_car,     dir); }
void loadout_cycle_armor(int8_t dir) BANKED   { ld_armor   = cycle(ld_armor,   dir); }
void loadout_cycle_weapon1(int8_t dir) BANKED { ld_weapon1 = cycle(ld_weapon1, dir); }
void loadout_cycle_weapon2(int8_t dir) BANKED { ld_weapon2 = cycle(ld_weapon2, dir); }
