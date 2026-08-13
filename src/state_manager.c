/* state_manager.c — bank 0 (no #pragma bank). Uses invoke() to dispatch
 * state callbacks; SWITCH_ROM is safe from bank-0 code. */
#include <gb/gb.h>
#include "state_manager.h"
#include "debug.h"

typedef struct {
    uint8_t bank;
    void (*enter)(void);
    void (*update)(void);
    void (*exit)(void);
} StateEntry;

DBG_STATIC StateEntry stack[STACK_MAX];
DBG_STATIC uint8_t sm_depth = 0;

/* Which State struct each stack slot came from. The address identifies the
 * state, because every State is a distinct `const State` in banked ROM
 * (#588 R9). The game never reads this array; a headless scenario reads it
 * out of WRAM to name the state the game is in.
 *
 * It is compiled into BOTH ROMs on purpose. An `#ifdef DEBUG` array would add
 * code to the debug ROM only, and the two ROMs must hold the same bytes (AC2).
 * DBG_STATIC is what makes the symbol reachable in the debug build alone. */
DBG_STATIC const State *sm_slot_src[STACK_MAX];

static void invoke(void (*fn)(void), uint8_t bank) {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(bank);
    fn();
    SWITCH_ROM(saved);
}

/* Safely read a State struct from banked ROM into a WRAM StateEntry.
 * Must be called from bank-0 code; switches to `bank` to dereference `s`.
 * Takes the slot index rather than a pointer so it can record the source
 * address without dividing by the struct size on SM83. */
static void load_entry(uint8_t slot, const State *s, uint8_t bank) {
    uint8_t saved = CURRENT_BANK;
    SWITCH_ROM(bank);
    stack[slot].bank   = s->bank;
    stack[slot].enter  = s->enter;
    stack[slot].update = s->update;
    stack[slot].exit   = s->exit;
    SWITCH_ROM(saved);
    sm_slot_src[slot] = s;
}

void state_manager_init(void) {
    sm_depth = 0;
}

void state_manager_update(void) {
    if (sm_depth == 0) return;
    invoke(stack[sm_depth - 1].update, stack[sm_depth - 1].bank);
}

void state_push(const State *s, uint8_t bank) {
    if (sm_depth >= STACK_MAX) return;
    load_entry(sm_depth, s, bank);
    sm_depth++;
    invoke(stack[sm_depth - 1].enter, stack[sm_depth - 1].bank);
}

void state_pop(void) {
    if (sm_depth == 0) return;
    invoke(stack[sm_depth - 1].exit, stack[sm_depth - 1].bank);
    sm_depth--;
    /* Clear the slot we left. A stale pointer here would make a debug reader
     * name a state the game has already exited (#588 R9). */
    sm_slot_src[sm_depth] = 0;
    if (sm_depth > 0) {
        invoke(stack[sm_depth - 1].enter, stack[sm_depth - 1].bank);
    }
}

void state_replace(const State *s, uint8_t bank) {
    if (sm_depth == 0) {
        load_entry(sm_depth, s, bank);
        sm_depth++;
        invoke(stack[sm_depth - 1].enter, stack[sm_depth - 1].bank);
        return;
    }
    invoke(stack[sm_depth - 1].exit, stack[sm_depth - 1].bank);
    load_entry(sm_depth - 1, s, bank);
    invoke(stack[sm_depth - 1].enter, stack[sm_depth - 1].bank);
}

#ifdef DEBUG_MAILBOX
uint8_t state_manager_depth(void) {
    return sm_depth;
}

const State *state_manager_top(void) {
    return (sm_depth == 0u) ? 0 : sm_slot_src[sm_depth - 1u];
}
#endif
