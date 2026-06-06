/* GENERATED — do not edit by hand. Source: assets/maps/track3.tmx */
/* Regenerate: python3 tools/tmx_to_c.py assets/maps/track3.tmx src/track3_map.c --prefix track3 */
#pragma bank 255
#include <gb/gb.h>
#include "track.h"
#include "banking.h"

BANKREF(track3_start_x)
const int16_t track3_start_x = 80;
BANKREF(track3_start_y)
const int16_t track3_start_y = 16;

BANKREF(track3_finish_line_y)
const uint8_t track3_finish_line_y = 24;

BANKREF(track3_map_type)
const uint8_t track3_map_type = 1u;

BANKREF(track3_lap_count)
const uint8_t track3_lap_count = 1u;

BANKREF(track3_finish_direction)
const uint8_t track3_finish_direction = 1u; /* S */

BANKREF(track3_start_dir)
const uint8_t track3_start_dir = 4u; /* S */

BANKREF(track3_map)
const uint8_t track3_map[522] = {
    /* header */ 20, 26,
    /* row  0 */ 0,0,0,0,0,0,0,0,3,3,3,22,0,0,0,0,0,0,0,0,
    /* row  1 */ 0,0,0,0,0,0,0,0,3,3,3,3,22,0,0,0,0,0,0,0,
    /* row  2 */ 0,0,0,0,0,0,0,56,3,3,3,3,3,22,25,0,0,0,0,0,
    /* row  3 */ 0,0,0,0,0,0,0,3,3,3,49,16,3,3,22,0,0,0,0,0,
    /* row  4 */ 0,0,0,0,0,0,0,3,3,21,3,3,3,3,3,0,0,0,0,0,
    /* row  5 */ 0,0,0,0,0,0,0,3,3,3,3,3,3,3,3,0,0,0,0,0,
    /* row  6 */ 0,0,0,0,0,0,0,3,3,3,3,3,3,3,3,0,0,0,0,0,
    /* row  7 */ 0,0,0,0,0,0,0,59,3,3,3,3,13,3,3,0,0,0,0,0,
    /* row  8 */ 0,0,0,0,0,0,0,0,59,3,3,3,3,3,3,0,0,0,0,0,
    /* row  9 */ 0,0,0,0,0,0,0,0,0,3,3,3,3,3,58,0,0,0,0,0,
    /* row 10 */ 0,0,0,0,0,0,0,0,0,3,3,3,3,3,0,0,0,0,0,0,
    /* row 11 */ 0,0,0,0,0,0,0,0,0,3,3,3,3,58,0,0,0,0,0,0,
    /* row 12 */ 0,0,0,0,0,0,0,0,56,3,3,49,3,0,0,0,0,0,0,0,
    /* row 13 */ 0,0,0,0,0,0,0,0,3,3,42,3,58,56,3,0,0,0,0,0,
    /* row 14 */ 0,0,0,0,0,0,0,0,3,3,3,58,56,3,21,0,0,0,0,0,
    /* row 15 */ 0,0,0,0,0,0,0,0,3,3,3,0,59,3,3,0,0,0,0,0,
    /* row 16 */ 0,0,0,0,0,0,0,0,3,21,3,0,0,56,3,0,0,0,0,0,
    /* row 17 */ 0,0,0,0,0,0,0,57,3,3,3,0,0,3,51,0,0,0,0,0,
    /* row 18 */ 0,0,0,0,0,0,0,3,3,15,3,0,0,3,3,0,0,0,0,0,
    /* row 19 */ 0,0,0,0,0,0,0,3,3,3,3,22,56,3,3,0,0,0,0,0,
    /* row 20 */ 0,0,0,0,0,0,0,59,3,3,3,3,3,3,3,0,0,0,0,0,
    /* row 21 */ 0,0,0,0,0,0,0,0,3,3,3,3,9,3,58,0,0,0,0,0,
    /* row 22 */ 0,0,0,0,0,0,0,0,3,3,3,3,3,3,0,0,0,0,0,0,
    /* row 23 */ 0,0,0,0,0,0,0,0,3,3,3,3,3,3,0,0,0,0,0,0,
    /* row 24 */ 0,0,0,0,0,0,0,0,18,18,18,18,18,18,0,0,0,0,0,0,
    /* row 25 */ 0,0,0,0,0,0,0,0,3,3,3,3,3,3,0,0,0,0,0,0,
};

BANKREF(track3_checkpoints)
const CheckpointDef track3_checkpoints[1] = {
    { 0, 0, 0, 0, 0, 0 },
};
const uint8_t track3_checkpoint_count = 0;

BANKREF(track3_npc_count)
const uint8_t track3_npc_count = 0u;

BANKREF(track3_npc_tx)
const uint8_t track3_npc_tx[8] = { 0u, 0u, 0u, 0u, 0u, 0u, 0u, 0u };

BANKREF(track3_npc_ty)
const uint8_t track3_npc_ty[8] = { 0u, 0u, 0u, 0u, 0u, 0u, 0u, 0u };

BANKREF(track3_npc_type)
const uint8_t track3_npc_type[8] = { 0u, 0u, 0u, 0u, 0u, 0u, 0u, 0u };

BANKREF(track3_npc_dir)
const uint8_t track3_npc_dir[8] = { 0u, 0u, 0u, 0u, 0u, 0u, 0u, 0u };

BANKREF(track3_powerup_count)
const uint8_t track3_powerup_count = 0u;

BANKREF(track3_powerup_tx)
const uint8_t track3_powerup_tx[4] = { 0u, 0u, 0u, 0u };

BANKREF(track3_powerup_ty)
const uint8_t track3_powerup_ty[4] = { 0u, 0u, 0u, 0u };

BANKREF(track3_powerup_type)
const uint8_t track3_powerup_type[4] = { 0u, 0u, 0u, 0u };

BANKREF(track3_racer_wp_count)
const uint8_t track3_racer_wp_count = 0u;

BANKREF(track3_racer_wp_tx)
const uint8_t track3_racer_wp_tx[1] = { 0u };

BANKREF(track3_racer_wp_ty)
const uint8_t track3_racer_wp_ty[1] = { 0u };

