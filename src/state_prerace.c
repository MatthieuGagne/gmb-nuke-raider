/* src/state_prerace.c — stub, completed in Task 5 */
#pragma bank 255
#include "state_prerace.h"
#include "state_manager.h"

BANKREF(state_prerace)

static void enter(void) {}
static void update(void) {}
static void pr_exit(void) {}
const State state_prerace = {255, enter, update, pr_exit};
