#pragma bank 255

#include <gb/gb.h>
#include "vehicle_physics.h"
#include "track.h"
#include "config.h"

/* Direction → velocity deltas: 0=T,1=RT,2=R,3=RB,4=B,5=LB,6=L,7=LT.
 * Identical values to player.c DIR_DX/DY and racer.c RACER_DIR_DX/DY. */
const int8_t VEH_DIR_DX[8] = {  0,  1,  1,  1,  0, -1, -1, -1 };
const int8_t VEH_DIR_DY[8] = { -1, -1,  0,  1,  1,  1,  0, -1 };

/* Non-directional 16x16 corner passability: four corners at offsets {0,15}.
 * Static terrain only — dynamic blockers (turret/racer) are caller gates. */
static uint8_t veh_corners_passable(int16_t wx, int16_t wy) {
    if (!track_passable(wx,        wy))        return 0u;
    if (!track_passable(wx + 15,   wy))        return 0u;
    if (!track_passable(wx,        wy + 15))   return 0u;
    if (!track_passable(wx + 15,   wy + 15))   return 0u;
    return 1u;
}

/* Friction portion (PRE gear-accel) — verbatim from player_apply_physics 317-337. */
void vehicle_apply_friction(int8_t *vx, int8_t *vy, uint8_t terrain,
                            uint8_t gas, uint8_t dir) BANKED {
    uint8_t i;
    uint8_t fric_x;
    uint8_t fric_y;

    if (terrain == TILE_SAND) {
        fric_x = (gas && VEH_DIR_DX[dir] != 0) ? 0u : (uint8_t)(PLAYER_FRICTION * TERRAIN_SAND_FRICTION_MUL);
        fric_y = (gas && VEH_DIR_DY[dir] != 0) ? 0u : (uint8_t)(PLAYER_FRICTION * TERRAIN_SAND_FRICTION_MUL);
    } else if (terrain == TILE_OIL) {
        fric_x = 0u;
        fric_y = 0u;
    } else {
        fric_x = (gas && VEH_DIR_DX[dir] != 0) ? 0u : (uint8_t)PLAYER_FRICTION;
        fric_y = (gas && VEH_DIR_DY[dir] != 0) ? 0u : (uint8_t)PLAYER_FRICTION;
    }

    for (i = 0u; i < fric_x; i++) {
        if      (*vx > 0) *vx = (int8_t)(*vx - 1);
        else if (*vx < 0) *vx = (int8_t)(*vx + 1);
    }
    for (i = 0u; i < fric_y; i++) {
        if      (*vy > 0) *vy = (int8_t)(*vy - 1);
        else if (*vy < 0) *vy = (int8_t)(*vy + 1);
    }
}

/* Boost-delta + max-speed clamp (POST gear-accel) — verbatim from 344-358. */
void vehicle_apply_boost_clamp(int8_t *vx, int8_t *vy, uint8_t terrain,
                               uint8_t max_speed) BANKED {
    if (terrain == TILE_BOOST) {
        *vy = (int8_t)(*vy - (int8_t)TERRAIN_BOOST_DELTA);
    }

    if (*vx >  (int8_t)max_speed) *vx =  (int8_t)max_speed;
    if (*vx < -(int8_t)max_speed) *vx = -(int8_t)max_speed;
    if (*vy >  (int8_t)max_speed) *vy =  (int8_t)max_speed;
    if (*vy < -(int8_t)max_speed) *vy = -(int8_t)max_speed;
}

/* Gearless convenience: friction then boost_clamp, NO accel between.
 * For callers with no gear acceleration (patrol, PR4). */
void vehicle_apply_physics(int8_t *vx, int8_t *vy, uint8_t terrain,
                           uint8_t gas, uint8_t dir, uint8_t max_speed) BANKED {
    vehicle_apply_friction(vx, vy, terrain, gas, dir);
    vehicle_apply_boost_clamp(vx, vy, terrain, max_speed);
}

int16_t vehicle_step_axis_x(int16_t px, int16_t py, int8_t vx) BANKED {
    int16_t new_px = (int16_t)(px + (int16_t)vx);
    if (new_px >= 0 &&
        new_px <= (int16_t)((uint16_t)active_map_w * 8u - 16u) &&
        veh_corners_passable(new_px, py)) {
        return new_px;
    }
    return px;
}

int16_t vehicle_step_axis_y(int16_t px, int16_t py, int8_t vy) BANKED {
    int16_t new_py = (int16_t)(py + (int16_t)vy);
    if (new_py >= 0 &&
        new_py <= (int16_t)((uint16_t)active_map_h * 8u - 16u) &&
        veh_corners_passable(px, new_py)) {
        return new_py;
    }
    return py;
}
