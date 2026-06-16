#ifndef EXPLOSION_H
#define EXPLOSION_H
#include <stdint.h>

/* Explosion kinds — the `is_car` parameter of explosion_spawn().
 * TURRET: self-positions each frame from world coords (wx px, wty tiles).
 * PLAYER: positioned by player_render; gates game-over via explosion_is_done().
 * RACER:  positioned by racer_render; does NOT gate game-over and skips
 *         clear_sprite on completion (the racer owns hiding its own slots). */
#define EXPLOSION_KIND_TURRET 0u
#define EXPLOSION_KIND_PLAYER 1u
#define EXPLOSION_KIND_RACER  2u

void explosion_init(uint8_t turret_base, uint8_t car_base) BANKED;
void explosion_spawn(uint8_t oam, uint8_t tile_base, uint8_t flip, uint8_t is_car, uint8_t wx, uint8_t wty) BANKED;
void explosion_update(void) BANKED;
void explosion_render(void) BANKED;
uint8_t explosion_is_done(void) BANKED;
uint8_t explosion_car_base(void) BANKED;

#ifndef __SDCC
uint8_t explosion_active_count(void);
#endif
#endif
