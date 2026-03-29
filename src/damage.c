#pragma bank 255
#include "damage.h"
#include "config.h"

static uint8_t hp;
static uint8_t invincibility_cooldown;

void damage_init(void) BANKED {
    hp                     = PLAYER_MAX_HP;
    invincibility_cooldown = 0u;
}

void damage_tick(void) BANKED {
    if (invincibility_cooldown > 0u) {
        invincibility_cooldown = (uint8_t)(invincibility_cooldown - 1u);
    }
}

void damage_apply(uint8_t amount) BANKED {
    if (invincibility_cooldown > 0u) return;
    if (hp == 0u)                    return;
    if (amount >= hp) {
        hp = 0u;
    } else {
        hp = (uint8_t)(hp - amount);
    }
    invincibility_cooldown = DAMAGE_INVINCIBILITY_FRAMES;
}

void damage_heal(uint8_t amount) BANKED {
    uint8_t new_hp = (uint8_t)(hp + amount);
    if (new_hp > PLAYER_MAX_HP || new_hp < hp) {  /* overflow guard */
        hp = PLAYER_MAX_HP;
    } else {
        hp = new_hp;
    }
}

uint8_t damage_is_dead(void) BANKED {
    return (hp == 0u) ? 1u : 0u;
}

uint8_t damage_get_hp(void) BANKED {
    return hp;
}
