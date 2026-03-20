/* state_manager.c — bank 0 (no #pragma bank). Uses invoke() to dispatch
 * state callbacks; SWITCH_ROM is safe from bank-0 code. */
#include <gb/gb.h>
#include "state_manager.h"

#define STACK_MAX 2

static const State *stack[STACK_MAX];
static uint8_t depth = 0;

static void invoke(void (*fn)(void), uint8_t bank) {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(bank);
    fn();
    SWITCH_ROM(saved);
}

void state_manager_init(void) {
    depth = 0;
}

void state_manager_update(void) {
    if (depth == 0) return;
    invoke(stack[depth - 1]->update, stack[depth - 1]->bank);
}

void state_push(const State *s) {
    if (depth >= STACK_MAX) return;
    stack[depth++] = s;
    invoke(s->enter, s->bank);
}

void state_pop(void) {
    if (depth == 0) return;
    invoke(stack[depth - 1]->exit, stack[depth - 1]->bank);
    depth--;
    if (depth > 0) {
        invoke(stack[depth - 1]->enter, stack[depth - 1]->bank);
    }
}

void state_replace(const State *s) {
    if (depth == 0) {
        stack[depth++] = s;
        invoke(s->enter, s->bank);
        return;
    }
    invoke(stack[depth - 1]->exit, stack[depth - 1]->bank);
    stack[depth - 1] = s;
    invoke(s->enter, s->bank);
}
