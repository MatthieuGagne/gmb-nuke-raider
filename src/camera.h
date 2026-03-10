#ifndef CAMERA_H
#define CAMERA_H

#include <stdint.h>

/* Current camera scroll Y in world pixels. Range [0, 656] — requires uint16_t. */
extern uint16_t cam_y;

/* Call once when entering STATE_PLAYING (after track_init).
 * Preloads the 18 initially visible rows and sets cam_y. */
void camera_init(int16_t player_world_x, int16_t player_world_y);

/* Call every frame in game-logic phase. Advances cam_y monotonically and
 * buffers any new bottom-row streams. Does NOT write VRAM directly. */
void camera_update(int16_t player_world_x, int16_t player_world_y);

/* Call in VBlank phase after wait_vbl_done(). Drains buffered row streams. */
void camera_flush_vram(void);

#endif /* CAMERA_H */
