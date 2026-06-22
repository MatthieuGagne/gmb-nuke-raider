#pragma bank 255
#include "loadout.h"

static uint8_t ld_car;
static uint8_t ld_armor;
static uint8_t ld_weapon1;
static uint8_t ld_weapon2;
static uint8_t ld_unlock_mask;   /* bit f set => field f tier-1 unlocked */

void loadout_init(void) BANKED {
    ld_car     = LOADOUT_DEFAULT_CAR;
    ld_armor   = LOADOUT_DEFAULT_ARMOR;
    ld_weapon1 = LOADOUT_DEFAULT_WEAPON1;
    ld_weapon2 = LOADOUT_DEFAULT_WEAPON2;
    ld_unlock_mask = 0u;
}

uint8_t loadout_get_car(void) BANKED     { return ld_car;     }
uint8_t loadout_get_armor(void) BANKED   { return ld_armor;   }
uint8_t loadout_get_weapon1(void) BANKED { return ld_weapon1; }
uint8_t loadout_get_weapon2(void) BANKED { return ld_weapon2; }

void loadout_set_car(uint8_t v) BANKED     { ld_car     = v; }
void loadout_set_armor(uint8_t v) BANKED   { ld_armor   = v; }
void loadout_set_weapon1(uint8_t v) BANKED { ld_weapon1 = v; }
void loadout_set_weapon2(uint8_t v) BANKED { ld_weapon2 = v; }

uint8_t loadout_is_option_unlocked(uint8_t field, uint8_t option) BANKED {
    if (option == 0u) return 1u;                       /* tier 0 always available */
    if (field == LOADOUT_FIELD_CAR) return 1u;         /* CAR never gated (out of scope) */
    return (uint8_t)((ld_unlock_mask >> field) & 1u);
}

void loadout_unlock_option(uint8_t field) BANKED {
    ld_unlock_mask |= (uint8_t)(1u << field);
}

static uint8_t cycle(uint8_t field, uint8_t cur, int8_t dir) {
    uint8_t next = cur;
    uint8_t i;
    for (i = 0u; i < LOADOUT_OPTIONS_PER_FIELD; i++) {
        if (dir > 0) {
            next = (uint8_t)((next + 1u) % LOADOUT_OPTIONS_PER_FIELD);
        } else {
            next = (next == 0u) ? (uint8_t)(LOADOUT_OPTIONS_PER_FIELD - 1u)
                                : (uint8_t)(next - 1u);
        }
        if (loadout_is_option_unlocked(field, next)) return next;
    }
    return cur;  /* no other unlocked option — stay put */
}

void loadout_cycle_car(int8_t dir) BANKED     { ld_car     = cycle(LOADOUT_FIELD_CAR,     ld_car,     dir); }
void loadout_cycle_armor(int8_t dir) BANKED   { ld_armor   = cycle(LOADOUT_FIELD_ARMOR,   ld_armor,   dir); }
void loadout_cycle_weapon1(int8_t dir) BANKED { ld_weapon1 = cycle(LOADOUT_FIELD_WEAPON1, ld_weapon1, dir); }
void loadout_cycle_weapon2(int8_t dir) BANKED { ld_weapon2 = cycle(LOADOUT_FIELD_WEAPON2, ld_weapon2, dir); }
