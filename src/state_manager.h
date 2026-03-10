#ifndef STATE_MANAGER_H
#define STATE_MANAGER_H

#include <stdint.h>

typedef struct {
    void (*enter)(void);
    void (*update)(uint8_t input);
    void (*exit)(void);
} State;

void state_manager_init(void);
void state_manager_update(uint8_t input);

void state_push(const State *s);
void state_pop(void);
void state_replace(const State *s);

#endif
