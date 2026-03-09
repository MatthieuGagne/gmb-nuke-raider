#include "unity.h"

/* Force DEBUG on for this test so macros expand to EMU_printf calls */
#define DEBUG
#include "debug.h"

void setUp(void) {}
void tearDown(void) {}

void test_dbg_int_compiles_and_runs(void) {
    /* Smoke test: macros must compile and not crash */
    DBG_INT("cam_x", 42);
    DBG_INT("stream_len", 0);
    TEST_PASS();
}

void test_dbg_str_compiles_and_runs(void) {
    DBG_STR("hello debug");
    TEST_PASS();
}

void test_dbg_macros_empty_without_debug(void) {
    /* Undef DEBUG and guard so debug.h re-includes and gives empty macros */
#undef DEBUG
#undef DBG_INT
#undef DBG_STR
#undef DEBUG_H
#include "debug.h"
    DBG_INT("x", 1);
    DBG_STR("y");
    TEST_PASS();
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_dbg_int_compiles_and_runs);
    RUN_TEST(test_dbg_str_compiles_and_runs);
    RUN_TEST(test_dbg_macros_empty_without_debug);
    return UNITY_END();
}
