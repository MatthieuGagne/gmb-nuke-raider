#pragma bank 255
#include <gb/gb.h>
#include "state_manager.h"

#define STACK_MAX 2

static const State *stack[STACK_MAX];
static uint8_t depth = 0;

void state_manager_init(void) BANKED {
    depth = 0;
}

void state_manager_update(void) BANKED {
    if (depth == 0) return;
    stack[depth - 1]->update();
}

void state_push(const State *s) BANKED {
    if (depth >= STACK_MAX) return;
    stack[depth++] = s;
    s->enter();
}

void state_pop(void) BANKED {
    if (depth == 0) return;
    stack[depth - 1]->exit();
    depth--;
    if (depth > 0) {
        stack[depth - 1]->enter();
    }
}

void state_replace(const State *s) BANKED {
    if (depth == 0) {
        stack[depth++] = s;
        s->enter();
        return;
    }
    stack[depth - 1]->exit();
    stack[depth - 1] = s;
    s->enter();
}
