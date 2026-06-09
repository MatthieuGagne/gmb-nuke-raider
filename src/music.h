#ifndef MUSIC_H
#define MUSIC_H

#include <gb/gb.h>
#include "hUGEDriver.h"

/* music_init() — enable APU and start the default song. Call once in main()
 * before the game loop, after hardware init. */
void music_init(void);

/* music_start() — switch to a different track at runtime.
 * bank: the ROM bank where song lives (use BANK(sym) macro).
 * song: pointer to the hUGESong_t in that bank. */
void music_start(uint8_t bank, const hUGESong_t *song);

/* music_tick() — advance the music driver by one tick. Call once per frame
 * in the main loop (not from vbl_isr). */
void music_tick(void);

/* music_notify_vblank() — called ONLY from vbl_isr(). Increments the catch-up
 * counter (saturating at 255). No bank switch, no hUGEDriver call -> interrupt-safe.
 * Must stay non-BANKED (bank 0). */
void music_notify_vblank(void);

/* music_service() — drain the catch-up counter: run music_tick() once per VBlank
 * elapsed since the last call (clamped to MUSIC_MAX_CATCHUP). Call once per main-
 * loop iteration in place of music_tick(). Returns the number of ticks run. */
uint8_t music_service(void);

/* music_resync() — zero the catch-up counter. Call on gameplay resume / LCD-on
 * (state_playing enter) and inside music_start(), so accumulated backlog does not
 * drain as an audible catch-up burst at a transition. */
void music_resync(void);

/* music_ticks_owed_peek() — test-visible read of the catch-up counter. */
uint8_t music_ticks_owed_peek(void);

/* vbl_sync() — wait for the next VBlank (via frame_ready flag), then call
 * music_tick(). Use this instead of wait_vbl_done() in any state that needs
 * to block until VBlank — it ensures music never misses a tick. */
void vbl_sync(void);

/* vbl_display_off() — wait for VBlank, tick music, then disable the LCD.
 * Use this as the entry point for any full dialog/menu re-render:
 *
 *   vbl_display_off();        // sync + tick + LCD off — 1 VBlank consumed
 *   cls();                    // VRAM writes safe: display is off
 *   hub_render_dialog();      // VRAM writes safe: display is off
 *   DISPLAY_ON;               // re-enable LCD
 *
 * Unlike DISPLAY_OFF (which calls display_off() → polls LY=145 independently),
 * this function turns off the LCD *inside* the VBlank window it already waited
 * for — exactly 1 VBlank consumed, music ticked for every VBlank consumed. */
void vbl_display_off(void);

/* frame_ready — set by vbl_isr each VBlank, consumed by the main loop and
 * vbl_sync(). Declared here so music.c can implement vbl_sync(). */
extern volatile uint8_t frame_ready;

#endif /* MUSIC_H */
