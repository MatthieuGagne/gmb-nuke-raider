#ifndef STATE_OVERMAP_H
#define STATE_OVERMAP_H

#include <stdint.h>
#include <gb/gb.h>
#include "state_manager.h"
#include "banking.h"

BANKREF_EXTERN(state_overmap)
extern const State state_overmap;
extern uint8_t current_race_id;
extern uint8_t current_hub_id;

/* Generated tile and map data (from assets/maps/overmap_tiles.png and overmap.tmx) */
BANKREF_EXTERN(overmap_tile_data)
extern const uint8_t overmap_tile_data[];
extern const uint8_t overmap_tile_data_count;

BANKREF_EXTERN(overmap_map)
extern const uint8_t overmap_map[];
extern const uint8_t overmap_id_map[];    /* combined dest/city-hub id map; 0xFF = no id */
extern const uint8_t overmap_hub_spawn_tx;
extern const uint8_t overmap_hub_spawn_ty;

/* Accessors used by unit tests */
uint8_t overmap_get_car_tx(void);
uint8_t overmap_get_car_ty(void);
uint8_t overmap_get_spawn_tx(void);
uint8_t overmap_get_spawn_ty(void);

/* Called by state_prerace before popping back to overmap to preserve car position */
void overmap_set_returning(void);

/* Direction → tile/prop mapping — pure function, testable host-side */
void overmap_car_props(uint8_t dir, uint8_t *tile, uint8_t *props);

#endif /* STATE_OVERMAP_H */
