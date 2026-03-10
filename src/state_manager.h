#ifndef STATE_MANAGER_H
#define STATE_MANAGER_H

#include <gb/gb.h>
#include <stdint.h>

typedef struct {
    void (*enter)(void) BANKED;
    void (*update)(void) BANKED;
    void (*exit)(void) BANKED;
} State;

void state_manager_init(void) BANKED;
void state_manager_update(void) BANKED;

void state_push(const State *s) BANKED;
void state_pop(void) BANKED;
void state_replace(const State *s) BANKED;

#endif
