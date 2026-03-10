#include "unity.h"
#include "../src/state_manager.h"
#include <stdint.h>

/* ── Call tracking ────────────────────────────────────────────────── */
static int calls_a_enter = 0;
static int calls_a_update = 0;
static int calls_a_exit = 0;
static int calls_b_enter = 0;
static int calls_b_update = 0;
static int calls_b_exit = 0;

/* Track call order globally */
static int call_order[16];
static int call_order_len = 0;

#define LOG_A_ENTER  1
#define LOG_A_EXIT   2
#define LOG_B_ENTER  3
#define LOG_B_EXIT   4

static void a_enter(void)  { calls_a_enter++;  call_order[call_order_len++] = LOG_A_ENTER; }
static void a_update(uint8_t input) { (void)input; calls_a_update++; }
static void a_exit(void)   { calls_a_exit++;   call_order[call_order_len++] = LOG_A_EXIT; }

static void b_enter(void)  { calls_b_enter++;  call_order[call_order_len++] = LOG_B_ENTER; }
static void b_update(uint8_t input) { (void)input; calls_b_update++; }
static void b_exit(void)   { calls_b_exit++;   call_order[call_order_len++] = LOG_B_EXIT; }

static const State state_a = { a_enter, a_update, a_exit };
static const State state_b = { b_enter, b_update, b_exit };

/* ── setUp / tearDown ─────────────────────────────────────────────── */
void setUp(void) {
    calls_a_enter = calls_a_update = calls_a_exit = 0;
    calls_b_enter = calls_b_update = calls_b_exit = 0;
    call_order_len = 0;
    state_manager_init();
}

void tearDown(void) {}

/* ── Tests ────────────────────────────────────────────────────────── */

/* push calls enter on the pushed state */
void test_push_calls_enter(void) {
    state_push(&state_a);
    TEST_ASSERT_EQUAL_INT(1, calls_a_enter);
}

/* update calls the top state's update */
void test_update_calls_top_state_update(void) {
    state_push(&state_a);
    state_manager_update(0);
    TEST_ASSERT_EQUAL_INT(1, calls_a_update);
    TEST_ASSERT_EQUAL_INT(0, calls_b_update);
}

/* push a second state — update goes to the new top, not the base */
void test_push_second_update_routes_to_top(void) {
    state_push(&state_a);
    state_push(&state_b);
    state_manager_update(0);
    TEST_ASSERT_EQUAL_INT(0, calls_a_update);
    TEST_ASSERT_EQUAL_INT(1, calls_b_update);
}

/* pop: calls exit on top, then enter on resumed base state */
void test_pop_calls_exit_then_base_enter(void) {
    state_push(&state_a);
    state_push(&state_b);
    /* reset counters after setup so we only measure the pop */
    calls_a_enter = 0;
    calls_b_exit  = 0;
    call_order_len = 0;

    state_pop();

    TEST_ASSERT_EQUAL_INT(1, calls_b_exit);
    TEST_ASSERT_EQUAL_INT(1, calls_a_enter);
    /* exit must precede enter */
    TEST_ASSERT_EQUAL_INT(LOG_B_EXIT,  call_order[0]);
    TEST_ASSERT_EQUAL_INT(LOG_A_ENTER, call_order[1]);
}

/* pop: after popping modal, update routes back to base state */
void test_pop_routes_update_to_base(void) {
    state_push(&state_a);
    state_push(&state_b);
    state_pop();
    calls_a_update = 0;
    calls_b_update = 0;

    state_manager_update(0);
    TEST_ASSERT_EQUAL_INT(1, calls_a_update);
    TEST_ASSERT_EQUAL_INT(0, calls_b_update);
}

/* replace: calls exit on old top, enter on new top; depth unchanged */
void test_replace_calls_exit_then_enter(void) {
    state_push(&state_a);
    calls_a_enter = 0;
    call_order_len = 0;

    state_replace(&state_b);

    TEST_ASSERT_EQUAL_INT(1, calls_a_exit);
    TEST_ASSERT_EQUAL_INT(1, calls_b_enter);
    /* order: exit before enter */
    TEST_ASSERT_EQUAL_INT(LOG_A_EXIT,  call_order[0]);
    TEST_ASSERT_EQUAL_INT(LOG_B_ENTER, call_order[1]);
}

/* replace: update routes to the new state, not the old one */
void test_replace_routes_update_to_new_state(void) {
    state_push(&state_a);
    state_replace(&state_b);
    calls_a_update = 0;
    calls_b_update = 0;

    state_manager_update(0);
    TEST_ASSERT_EQUAL_INT(0, calls_a_update);
    TEST_ASSERT_EQUAL_INT(1, calls_b_update);
}

/* overflow guard: pushing beyond capacity does not crash and does not
 * corrupt the stack. The third push is silently ignored. */
void test_push_beyond_capacity_is_safe(void) {
    static const State state_c = { a_enter, a_update, a_exit }; /* reuse fns */
    state_push(&state_a);
    state_push(&state_b);
    state_push(&state_c); /* depth already at max — must not crash */

    /* update must still work (routes to state_b, the last valid top) */
    calls_b_update = 0;
    state_manager_update(0);
    TEST_ASSERT_EQUAL_INT(1, calls_b_update);
}

/* ── main ─────────────────────────────────────────────────────────── */
int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_push_calls_enter);
    RUN_TEST(test_update_calls_top_state_update);
    RUN_TEST(test_push_second_update_routes_to_top);
    RUN_TEST(test_pop_calls_exit_then_base_enter);
    RUN_TEST(test_pop_routes_update_to_base);
    RUN_TEST(test_replace_calls_exit_then_enter);
    RUN_TEST(test_replace_routes_update_to_new_state);
    RUN_TEST(test_push_beyond_capacity_is_safe);
    return UNITY_END();
}
