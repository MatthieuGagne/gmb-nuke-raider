/* state_manager.c — bank 0 (no #pragma bank). Uses invoke() to dispatch
 * state callbacks; SWITCH_ROM is safe from bank-0 code. */
#include <gb/gb.h>
#include "state_manager.h"

#define STACK_MAX 2

typedef struct {
    uint8_t bank;
    void (*enter)(void);
    void (*update)(void);
    void (*exit)(void);
} StateEntry;

static StateEntry stack[STACK_MAX];
static uint8_t depth = 0;

static void invoke(void (*fn)(void), uint8_t bank) {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(bank);
    fn();
    SWITCH_ROM(saved);
}

/* Safely read a State struct from banked ROM into a WRAM StateEntry.
 * Must be called from bank-0 code; switches to `bank` to dereference `s`. */
static void load_entry(StateEntry *entry, const State *s, uint8_t bank) {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(bank);
    entry->bank   = s->bank;
    entry->enter  = s->enter;
    entry->update = s->update;
    entry->exit   = s->exit;
    SWITCH_ROM(saved);
}

void state_manager_init(void) {
    depth = 0;
}

void state_manager_update(void) {
    if (depth == 0) return;
    invoke(stack[depth - 1].update, stack[depth - 1].bank);
}

void state_push(const State *s, uint8_t bank) {
    if (depth >= STACK_MAX) return;
    load_entry(&stack[depth], s, bank);
    depth++;
    invoke(stack[depth - 1].enter, stack[depth - 1].bank);
}

void state_pop(void) {
    if (depth == 0) return;
    invoke(stack[depth - 1].exit, stack[depth - 1].bank);
    depth--;
    if (depth > 0) {
        invoke(stack[depth - 1].enter, stack[depth - 1].bank);
    }
}

void state_replace(const State *s, uint8_t bank) {
    if (depth == 0) {
        load_entry(&stack[depth], s, bank);
        depth++;
        invoke(stack[depth - 1].enter, stack[depth - 1].bank);
        return;
    }
    invoke(stack[depth - 1].exit, stack[depth - 1].bank);
    load_entry(&stack[depth - 1], s, bank);
    invoke(stack[depth - 1].enter, stack[depth - 1].bank);
}
