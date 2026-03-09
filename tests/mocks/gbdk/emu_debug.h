/* tests/mocks/gbdk/emu_debug.h — stub for host-side tests */
#ifndef __MOCK_EMU_DEBUG_H
#define __MOCK_EMU_DEBUG_H
/* EMU_printf is a no-op in tests; use a macro to avoid link-time stub */
#define EMU_printf(fmt, ...) ((void)0)
#endif
