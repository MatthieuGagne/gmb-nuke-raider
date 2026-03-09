#ifndef MOCK_CONSOLE_H
#define MOCK_CONSOLE_H

/* Mock stubs for <gbdk/console.h> — host-side unit test compilation only. */

static inline void cls(void) {}
static inline void gotoxy(unsigned char x, unsigned char y) {
    (void)x; (void)y;
}

#endif /* MOCK_CONSOLE_H */
