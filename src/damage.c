#pragma bank 255
#include <gb/gb.h>
#include "banking.h"
#include "damage.h"
#include "config.h"

BANKREF(damage_module)

static uint8_t hp;
static uint8_t invincibility_frames;

void damage_init(void) BANKED {
    hp                   = PLAYER_MAX_HP;
    invincibility_frames = 0u;
}

void damage_tick(void) BANKED {
    if (invincibility_frames > 0u) invincibility_frames--;
}

void damage_apply(uint8_t amount) BANKED {
    if (invincibility_frames > 0u) return;
    hp = (amount >= hp) ? 0u : (uint8_t)(hp - amount);
    invincibility_frames = DAMAGE_INVINCIBILITY_FRAMES;
}

void damage_heal(uint8_t amount) BANKED {
    uint8_t new_hp = (uint8_t)(hp + amount);
    /* overflow guard: if addition wrapped or exceeded max, clamp to max */
    hp = (new_hp > PLAYER_MAX_HP || new_hp < hp) ? PLAYER_MAX_HP : new_hp;
}

uint8_t damage_get_hp(void) BANKED        { return hp; }
uint8_t damage_is_invincible(void) BANKED { return invincibility_frames > 0u; }
uint8_t damage_is_dead(void) BANKED       { return hp == 0u; }
