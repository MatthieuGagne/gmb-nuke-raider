#ifndef STATE_MANAGER_H
#define STATE_MANAGER_H

#include <gb/gb.h>
#include <stdint.h>

typedef struct {
    uint8_t bank;
    void (*enter)(void);   /* plain, NOT BANKED — invoke() handles bank switching */
    void (*update)(void);
    void (*exit)(void);
} State;

void state_manager_init(void);
void state_manager_update(void);

void state_push(const State *s);
void state_pop(void);
void state_replace(const State *s);

#endif
