#ifndef DEBUG_H
#define DEBUG_H

#ifdef DEBUG
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
