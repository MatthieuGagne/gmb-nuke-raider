#ifndef DEBUG_H
#define DEBUG_H

/* DBG_STATIC — visibility, not behaviour (#588 R3).
 *
 * `static` in a release ROM, empty in a debug ROM. A file-scope variable that
 * keeps the bare `static` keyword reaches neither the .noi symbol file nor the
 * link map, so the headless smoketest cannot watch it or assert on it. Every
 * MUTABLE file-scope data declaration in src/*.c uses this macro.
 *
 * It does NOT apply to:
 *   - static functions. `update` and `enter` each occur 7 times in src/, so
 *     stripping `static` from functions breaks the link (R4).
 *   - `static const` data. It sits in ROM, and the symbol reader accepts WRAM
 *     addresses only (R5). A mutable POINTER to const data is not const data.
 *
 * SDCC gives a file-scope variable the same area and the same address whether
 * it is static or not, and the access code is identical, so the two ROMs hold
 * the same bytes. tests/test_rom_parity.py checks that.
 */
#ifdef DEBUG
  #define DBG_STATIC
#else
  #define DBG_STATIC static
#endif

/* The emitting diagnostics live behind DEBUG_TRACE, not behind DEBUG.
 * DEBUG must not add one instruction to the ROM (AC2); these macros do add
 * instructions, so they need their own flag. Build them with:
 *     make build-debug DEBUG_TRACE=1
 */
#ifdef DEBUG_TRACE
  #include <gbdk/emu_debug.h>
  #include "config.h"

  #ifdef __SDCC
  /* Internal write: appends string s to the WRAM ring buffer at DEBUG_LOG_ADDR.
   * Only active on SDCC/GBC — host tests use the no-op stub below. */
  static void dbg_write(const char *s) {
      uint8_t idx = *(volatile uint8_t *)DEBUG_LOG_IDX;
      while (*s) {
          ((volatile uint8_t *)DEBUG_LOG_ADDR)[idx % DEBUG_LOG_SIZE] = (uint8_t)*s++;
          idx = (uint8_t)((idx + 1U) % DEBUG_LOG_SIZE);
      }
      *(volatile uint8_t *)DEBUG_LOG_IDX = idx;
  }
  /* Increment the music_tick() call counter in WRAM */
  #define DBG_TICK_INC() \
      do { \
          (*(volatile uint8_t *)DEBUG_TICK_ADDR)++; \
      } while (0)
  #else
  /* Host/GCC: WRAM addresses don't exist — no-op stubs for unit tests */
  static void dbg_write(const char *s) { (void)s; }
  #define DBG_TICK_INC()  do {} while (0)
  #endif

  /* Log a labeled integer value to Emulicious console */
  #define DBG_INT(label, val) \
      do { \
          EMU_printf(label ": %d\n", (int)(val)); \
      } while (0)

  /* Log a plain string to Emulicious console AND WRAM ring buffer */
  #define DBG_STR(s) \
      do { \
          EMU_printf("%s\n", (s)); \
          dbg_write(s); \
          dbg_write("\n"); \
      } while (0)

#else
  #define DBG_INT(label, val)  do {} while (0)
  #define DBG_STR(s)           do {} while (0)
  #define DBG_TICK_INC()       do {} while (0)
#endif

#endif /* DEBUG_H */
