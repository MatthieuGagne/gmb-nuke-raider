#ifndef STATE_MANAGER_H
#define STATE_MANAGER_H

#include <gb/gb.h>
#include <stdint.h>

/* Stack capacity. Public since #588 R8: a caller — and a test — must be able
 * to size a loop by it instead of hard-coding 2. */
#define STACK_MAX 2

typedef struct {
    uint8_t bank;
    void (*enter)(void);   /* plain, NOT BANKED — invoke() handles bank switching */
    void (*update)(void);
    void (*exit)(void);
} State;

void state_manager_init(void);
void state_manager_update(void);

void state_push(const State *s, uint8_t bank);
void state_pop(void);
void state_replace(const State *s, uint8_t bank);

#endif
