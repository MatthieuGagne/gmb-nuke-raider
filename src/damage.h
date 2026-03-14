#ifndef DAMAGE_H
#define DAMAGE_H

#include <gb/gb.h>
#include "banking.h"
#include "config.h"

BANKREF_EXTERN(damage_module)

void    damage_init(void) BANKED;
void    damage_tick(void) BANKED;
void    damage_apply(uint8_t amount) BANKED;
void    damage_heal(uint8_t amount) BANKED;
uint8_t damage_get_hp(void) BANKED;
uint8_t damage_is_invincible(void) BANKED;
uint8_t damage_is_dead(void) BANKED;

#endif /* DAMAGE_H */
