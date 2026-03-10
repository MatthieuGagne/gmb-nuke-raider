#include <gb/gb.h>
#include <gbdk/console.h>
#include <stdio.h>
#include "input.h"
#include "state_manager.h"
#include "state_title.h"
#include "state_playing.h"

static void enter(void) {
    cls();
    gotoxy(2, 6);
    printf("WASTELAND RACER");
    gotoxy(3, 10);
    printf("Press START");
}

static void update(void) {
    if (KEY_TICKED(J_START)) {
        state_replace(&state_playing);
    }
}

static void st_exit(void) {
}

const State state_title = { enter, update, st_exit };
