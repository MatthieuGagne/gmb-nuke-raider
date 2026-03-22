#ifndef CAMERA_H
#define CAMERA_H

#include <stdint.h>

/* Current camera scroll Y in world pixels. Range [0, 656] — requires uint16_t. */
extern volatile uint16_t cam_y;

/* Shadow SCY register written by camera_apply_scroll(); applied by VBL ISR.
 * Guarantees SCY hardware register is updated at VBlank start, before any
 * scanline is drawn, regardless of how long the main loop takes. */
extern volatile uint8_t cam_scy_shadow;

/* Call once when entering STATE_PLAYING (after track_init).
 * Preloads the 18 initially visible rows and sets cam_y. */
void camera_init(int16_t player_world_x, int16_t player_world_y) BANKED;

/* Call every frame in game-logic phase. Decreases cam_y as player moves up
 * (upward-only — cam_y never increases). Buffers new top-row streams.
 * Does NOT write VRAM directly. */
void camera_update(int16_t player_world_x, int16_t player_world_y) BANKED;

/* Call in VBlank phase after wait_vbl_done(). Drains buffered row streams. */
void camera_flush_vram(void) BANKED;

/* Call immediately after camera_flush_vram() in the VBlank phase.
 * Writes cam_y into cam_scy_shadow; the VBL ISR applies the shadow to the
 * hardware SCY register at the guaranteed-safe VBlank start. */
void camera_apply_scroll(void) BANKED;

#endif /* CAMERA_H */
