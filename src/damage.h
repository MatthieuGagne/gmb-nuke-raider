#ifndef DAMAGE_H
#define DAMAGE_H

#include <gb/gb.h>
#include <stdint.h>

/* Initialise HP to PLAYER_MAX_HP and clear invincibility cooldown.
 * Call from state_playing enter(), before DISPLAY_ON. */
void    damage_init(void) BANKED;

/* Decrement invincibility cooldown by 1 (no-op if already 0).
 * Call once per frame in state_playing update(). */
void    damage_tick(void) BANKED;

/* Apply `amount` damage. No-op if invincible or already dead.
 * Sets invincibility cooldown to DAMAGE_INVINCIBILITY_FRAMES on hit. */
void    damage_apply(uint8_t amount) BANKED;

/* Restore `amount` HP, capped at PLAYER_MAX_HP. */
void    damage_heal(uint8_t amount) BANKED;

/* Returns 1 if hp == 0, else 0. */
uint8_t damage_is_dead(void) BANKED;

/* Returns current HP (0–PLAYER_MAX_HP). */
uint8_t damage_get_hp(void) BANKED;

#endif /* DAMAGE_H */
