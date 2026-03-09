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

/* Call every frame in STATE_PLAYING game-logic phase (after player_update).
 * Centers camera on player and buffers any new tile column/row streams.
 * Does NOT write VRAM or call move_bkg() directly — see camera_flush_vram(). */
void camera_update(int16_t player_world_x, int16_t player_world_y);

/* Call every frame in STATE_PLAYING VBlank phase, immediately after
 * wait_vbl_done() and before move_bkg(). Drains the pending tile-stream
 * buffer accumulated by camera_update() and resets it to empty. */
void camera_flush_vram(void);

#endif /* CAMERA_H */
