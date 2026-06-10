#pragma bank 255

#include "enemy_common.h"

/* enemy_aim_dir — verbatim body of the former turret_dir_to_pixel(). */
player_dir_t enemy_aim_dir(uint8_t tx, uint8_t ty,
                           int16_t player_px, int16_t player_py) BANKED {
    int16_t dx = player_px - (int16_t)((uint16_t)tx * 8u);
    int16_t dy = player_py - (int16_t)((uint16_t)ty * 8u);
    int16_t ax = dx < 0 ? -dx : dx;
    int16_t ay = dy < 0 ? -dy : dy;
    uint8_t toward_x;

    /* Threshold 1: cardinal E/W — |dx| > 2*|dy| */
    if (ax > (int16_t)(ay << 1)) {
        return dx > 0 ? DIR_R : DIR_L;
    }
    /* Threshold 2: cardinal N/S — |dy| > 2*|dx| */
    if (ay > (int16_t)(ax << 1)) {
        return dy > 0 ? DIR_B : DIR_T;
    }
    /* Threshold 3: intermediate sector — |dx| vs |dy| */
    toward_x = (uint8_t)(ax > ay);
    if (dx >= 0 && dy < 0) { return toward_x ? DIR_ENE : DIR_NNE; }
    if (dx >= 0)            { return toward_x ? DIR_ESE : DIR_SSE; }
    if (dy >= 0)            { return toward_x ? DIR_WSW : DIR_SSW; }
    return toward_x ? DIR_WNW : DIR_NNW;
}

/* enemy_dir_from_delta — verbatim body of the former static racer_dir_from_delta(). */
uint8_t enemy_dir_from_delta(int8_t dx, int8_t dy) BANKED {
    int8_t ax = dx < 0 ? -dx : dx;
    int8_t ay = dy < 0 ? -dy : dy;
    if (ay > ax) {
        return (dy < 0) ? DIR_T : DIR_B;
    } else if (ax > ay) {
        return (dx < 0) ? DIR_L : DIR_R;
    } else {
        /* Diagonal: ax == ay */
        if (dy < 0 && dx < 0) return DIR_LT;
        if (dy < 0 && dx > 0) return DIR_RT;
        if (dy > 0 && dx < 0) return DIR_LB;
        return DIR_RB;
    }
}

/* enemy_wp_reached — Manhattan-distance threshold check. */
uint8_t enemy_wp_reached(int8_t dx, int8_t dy, uint8_t threshold) BANKED {
    uint8_t abs_dx = (uint8_t)(dx < 0 ? -dx : dx);
    uint8_t abs_dy = (uint8_t)(dy < 0 ? -dy : dy);
    return ((uint8_t)(abs_dx + abs_dy) < threshold) ? 1u : 0u;
}

/* enemy_wp_advance — advance/wrap a waypoint index when reached. */
uint8_t enemy_wp_advance(uint8_t cur_idx, uint8_t wp_count, uint8_t reached) BANKED {
    if (reached) {
        uint8_t next = (uint8_t)(cur_idx + 1u);
        return (next >= wp_count) ? 0u : next;
    }
    return cur_idx;
}
