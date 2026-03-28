#ifndef VRAM_QUEUE_H
#define VRAM_QUEUE_H

#include <stdint.h>

/* Maximum number of VRAM write entries per frame.
   Worst case: 1 camera row + 3 HUD win entries = 4. Cap of 8 is safe. */
#define VRAM_QUEUE_CAP      8u

/* Flat tile copy buffer. Worst case per frame:
   1 camera row (20 tiles) + 3 HUD entries (<=5 tiles each) = 35 bytes.
   64-byte buffer is safe. */
#define VRAM_TILE_BUF_SIZE  64u

/* Call once at startup (also resets queue state between frames). */
void vram_queue_init(void);

/* Queue a set_bkg_tiles() call. Copies tile data immediately. */
void vram_queue_bkg(uint8_t x, uint8_t y, uint8_t w, uint8_t h,
                    const uint8_t *tiles);

/* Queue a set_win_tiles() call. Copies tile data immediately. */
void vram_queue_win(uint8_t x, uint8_t y, uint8_t w, uint8_t h,
                    const uint8_t *tiles);

/* Drain all pending entries. Called from VBL ISR only. */
void vram_queue_flush(void);

#endif /* VRAM_QUEUE_H */
