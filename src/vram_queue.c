/* vram_queue.c — ISR-safe VRAM tile write queue.
 * IMPORTANT: No #pragma bank — this file must stay in bank 0.
 * vram_queue_flush() is called from the VBL ISR. If this code were
 * in a switched bank, SWITCH_ROM would remap the CPU's own instructions. */

#include "vram_queue.h"
#include <gb/gb.h>

/* SoA entry fields (CLAUDE.md: use SoA, not AoS) */
static uint8_t _kind[VRAM_QUEUE_CAP];   /* 0 = BKG, 1 = WIN */
static uint8_t _x[VRAM_QUEUE_CAP];
static uint8_t _y[VRAM_QUEUE_CAP];
static uint8_t _w[VRAM_QUEUE_CAP];
static uint8_t _h[VRAM_QUEUE_CAP];
static uint8_t _off[VRAM_QUEUE_CAP];    /* byte offset into _tile_buf */
static uint8_t _len;

/* Flat tile data copy — avoids dangling pointer to caller's stack buffer */
static uint8_t _tile_buf[VRAM_TILE_BUF_SIZE];
static uint8_t _tile_buf_pos;

void vram_queue_init(void) {
    _len = 0u;
    _tile_buf_pos = 0u;
}

static void enqueue(uint8_t kind, uint8_t x, uint8_t y,
                    uint8_t w, uint8_t h, const uint8_t *tiles) {
    uint8_t i;
    uint8_t count = (uint8_t)(w * h);
    if (_len >= VRAM_QUEUE_CAP) return;
    if ((uint8_t)(_tile_buf_pos + count) > VRAM_TILE_BUF_SIZE) return;
    _kind[_len] = kind;
    _x[_len]    = x;
    _y[_len]    = y;
    _w[_len]    = w;
    _h[_len]    = h;
    _off[_len]  = _tile_buf_pos;
    /* Manual byte copy — avoids memcpy/stdlib dependency */
    for (i = 0u; i < count; i++) {
        _tile_buf[_tile_buf_pos + i] = tiles[i];
    }
    _tile_buf_pos = (uint8_t)(_tile_buf_pos + count);
    _len++;
}

void vram_queue_bkg(uint8_t x, uint8_t y, uint8_t w, uint8_t h,
                    const uint8_t *tiles) {
    enqueue(0u, x, y, w, h, tiles);
}

void vram_queue_win(uint8_t x, uint8_t y, uint8_t w, uint8_t h,
                    const uint8_t *tiles) {
    enqueue(1u, x, y, w, h, tiles);
}

void vram_queue_flush(void) {
    uint8_t i;
    for (i = 0u; i < _len; i++) {
        const uint8_t *data = &_tile_buf[_off[i]];
        if (_kind[i] == 0u) {
            set_bkg_tiles(_x[i], _y[i], _w[i], _h[i], data);
        } else {
            set_win_tiles(_x[i], _y[i], _w[i], _h[i], data);
        }
    }
    _len = 0u;
    _tile_buf_pos = 0u;
}
