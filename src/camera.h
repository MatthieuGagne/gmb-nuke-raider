#ifndef CAMERA_H
#define CAMERA_H

#include <stdint.h>

/* Current camera scroll position in world pixels.
 * cam_x ∈ [0, 160], cam_y ∈ [0, 144] — both fit safely in uint8_t. */
extern uint8_t cam_x;
extern uint8_t cam_y;

/* Call once when entering STATE_PLAYING (after track_init).
 * Preloads all world tiles into VRAM ring buffer and sets initial scroll. */
void camera_init(int16_t player_world_x, int16_t player_world_y);

/* Call every frame in STATE_PLAYING loop (after wait_vbl_done).
 * Centers camera on player, streams any new tile columns/rows into VRAM,
 * and calls move_bkg(). */
void camera_update(int16_t player_world_x, int16_t player_world_y);

#endif /* CAMERA_H */
