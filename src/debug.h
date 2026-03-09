#ifndef DEBUG_H
#define DEBUG_H

#ifdef DEBUG
  #include <gbdk/emu_debug.h>
  /* Log a labeled integer value to the Emulicious debug console */
  #define DBG_INT(label, val) EMU_printf(label ": %d\n", (int)(val))
  /* Log a plain string */
  #define DBG_STR(s)          EMU_printf("%s\n", (s))
#else
  #define DBG_INT(label, val)
  #define DBG_STR(s)
#endif

#endif /* DEBUG_H */
