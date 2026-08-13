#include "unity.h"

/* Force DEBUG on for this test so macros expand to EMU_printf calls */
#define DEBUG
#include "debug.h"
#include "state_manager.h"
#include "config.h"

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

void test_dbg_tick_inc_compiles_and_runs(void) {
    DBG_TICK_INC();
    TEST_PASS();
}

void test_dbg_macros_empty_without_debug(void) {
    /* Undef DEBUG and guard so debug.h re-includes and gives empty macros */
#undef DEBUG
#undef DBG_INT
#undef DBG_STR
#undef DBG_TICK_INC
#undef DEBUG_H
#include "debug.h"
    DBG_INT("x", 1);
    DBG_STR("y");
    DBG_TICK_INC();
    TEST_PASS();
}

/* ---- #590: the test command mailbox ---------------------------------------- */

static void mb_put(uint8_t opcode, uint8_t arg0, uint8_t arg1, uint8_t commit) {
    debug_mb_write(DBG_MB_OFF_ARG0, arg0);
    debug_mb_write(DBG_MB_OFF_ARG1, arg1);
    debug_mb_write(DBG_MB_OFF_COMMIT, commit);
    debug_mb_write(DBG_MB_OFF_OPCODE, opcode);   /* opcode last (#590 R7) */
}

static uint8_t mb_commit(uint8_t opcode, uint8_t arg0, uint8_t arg1) {
    return (uint8_t)(DBG_MB_SEED ^ opcode ^ arg0 ^ arg1);
}

void test_start_sets_the_ready_byte(void) {
    debug_mailbox_start();
    TEST_ASSERT_EQUAL_UINT8(DBG_MB_READY_VALUE, debug_mb_read(DBG_MB_OFF_READY));
}

void test_start_clears_the_command_byte(void) {
    debug_mb_write(DBG_MB_OFF_OPCODE, 99u);
    debug_mailbox_start();
    TEST_ASSERT_EQUAL_UINT8(0u, debug_mb_read(DBG_MB_OFF_OPCODE));
}

void test_an_empty_mailbox_does_not_move_the_epoch(void) {
    uint8_t before;
    debug_mailbox_start();
    before = debug_mb_read(DBG_MB_OFF_EPOCH);
    debug_mailbox_poll();
    TEST_ASSERT_EQUAL_UINT8(before, debug_mb_read(DBG_MB_OFF_EPOCH));
}

void test_a_torn_commit_runs_nothing_and_counts(void) {
    uint8_t torn;
    debug_mailbox_start();
    torn = debug_mb_read(DBG_MB_OFF_TORN);
    /* HEAL 5, with a commit byte computed for HEAL 6 — the fold disagrees. */
    mb_put(DBG_OP_HEAL, 5u, 0u, mb_commit(DBG_OP_HEAL, 6u, 0u));
    debug_mailbox_poll();
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(torn + 1u), debug_mb_read(DBG_MB_OFF_TORN));
    TEST_ASSERT_EQUAL_UINT8(0u, debug_mb_read(DBG_MB_OFF_OPCODE));
}

void test_the_frame_after_a_torn_commit_runs_the_command(void) {
    uint8_t epoch;
    debug_mailbox_start();
    mb_put(DBG_OP_HEAL, 5u, 0u, mb_commit(DBG_OP_HEAL, 6u, 0u));
    debug_mailbox_poll();                       /* torn, nothing runs */
    epoch = debug_mb_read(DBG_MB_OFF_EPOCH);
    mb_put(DBG_OP_HEAL, 5u, 0u, mb_commit(DBG_OP_HEAL, 5u, 0u));
    debug_mailbox_poll();                       /* recovers */
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(epoch + 1u), debug_mb_read(DBG_MB_OFF_EPOCH));
    TEST_ASSERT_EQUAL_UINT8(DBG_OUT_OK, debug_mb_read(DBG_MB_OFF_OUTCOME));
}

void test_an_unknown_opcode_is_refused_and_names_itself(void) {
    debug_mailbox_start();
    mb_put(200u, 0u, 0u, mb_commit(200u, 0u, 0u));
    debug_mailbox_poll();
    TEST_ASSERT_EQUAL_UINT8(DBG_OUT_UNKNOWN_OP, debug_mb_read(DBG_MB_OFF_OUTCOME));
    TEST_ASSERT_EQUAL_UINT8(200u, debug_mb_read(DBG_MB_OFF_DETAIL));
}

/* AC8: this loop reads the generated table, so a new DBG_CMD line needs no new test code. */
void test_every_command_refuses_an_argument_above_its_declared_maximum(void) {
    uint8_t i;
    uint8_t checked = 0u;
    for (i = 0u; i < dbg_cmd_count; i++) {
        const DbgCmdSpec *spec = &dbg_cmd_table[i];
        DbgRequest req;
        DbgEnv env;
        if (spec->arg0_max == 255u) continue;   /* no uint8_t value can exceed it */
        req.opcode = spec->opcode;
        req.arg0 = (uint8_t)(spec->arg0_max + 1u);
        req.arg1 = 0u;
        env.depth = 1u; env.in_race = 0u; env.option_unlocked = 1u;
        TEST_ASSERT_EQUAL_UINT8(DBG_OUT_ARG_RANGE, debug_decide(&req, &env));
        checked++;
    }
    TEST_ASSERT_TRUE(checked > 0u);   /* the loop must not be vacuous */
}

void test_every_command_accepts_its_declared_maximum(void) {
    uint8_t i;
    for (i = 0u; i < dbg_cmd_count; i++) {
        const DbgCmdSpec *spec = &dbg_cmd_table[i];
        DbgRequest req;
        DbgEnv env;
        if (spec->opcode == DBG_OP_SPAWN_RACER ||
            spec->opcode == DBG_OP_SPAWN_PATROL) continue;   /* reserved (R17) */
        req.opcode = spec->opcode;
        req.arg0 = spec->arg0_max;
        req.arg1 = (spec->argc > 1u) ? spec->arg1_max : 0u;
        env.depth = 1u; env.in_race = 0u; env.option_unlocked = 1u;
        TEST_ASSERT_NOT_EQUAL_UINT8(DBG_OUT_ARG_RANGE, debug_decide(&req, &env));
    }
}

void test_a_reserved_opcode_reports_unsupported(void) {
    DbgRequest req;
    DbgEnv env;
    req.opcode = DBG_OP_SPAWN_RACER; req.arg0 = 0u; req.arg1 = 0u;
    env.depth = 1u; env.in_race = 0u; env.option_unlocked = 1u;
    TEST_ASSERT_EQUAL_UINT8(DBG_OUT_UNSUPPORTED, debug_decide(&req, &env));
}

/* The three refusals R4 names, proved on the pure function with no game state at all (R19). */
void test_the_pure_decision_refuses_a_locked_option(void) {
    DbgRequest req; DbgEnv env;
    req.opcode = DBG_OP_SET_OPTION; req.arg0 = 2u; req.arg1 = 1u;
    env.depth = 1u; env.in_race = 0u; env.option_unlocked = 0u;
    TEST_ASSERT_EQUAL_UINT8(DBG_OUT_LOCKED, debug_decide(&req, &env));
}

void test_the_pure_decision_refuses_a_loadout_change_during_a_race(void) {
    DbgRequest req; DbgEnv env;
    req.opcode = DBG_OP_SET_OPTION; req.arg0 = 2u; req.arg1 = 1u;
    env.depth = 1u; env.in_race = 1u; env.option_unlocked = 1u;
    TEST_ASSERT_EQUAL_UINT8(DBG_OUT_IN_RACE, debug_decide(&req, &env));
}

void test_the_pure_decision_refuses_a_push_at_the_depth_limit(void) {
    DbgRequest req; DbgEnv env;
    req.opcode = DBG_OP_FORCE_STATE; req.arg0 = 4u; req.arg1 = 0u;   /* push */
    env.depth = STACK_MAX; env.in_race = 0u; env.option_unlocked = 1u;
    TEST_ASSERT_EQUAL_UINT8(DBG_OUT_STACK_FULL, debug_decide(&req, &env));
}

void test_the_three_named_refusals_are_distinct(void) {
    TEST_ASSERT_NOT_EQUAL_UINT8(DBG_OUT_LOCKED, DBG_OUT_IN_RACE);
    TEST_ASSERT_NOT_EQUAL_UINT8(DBG_OUT_LOCKED, DBG_OUT_STACK_FULL);
    TEST_ASSERT_NOT_EQUAL_UINT8(DBG_OUT_IN_RACE, DBG_OUT_STACK_FULL);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_dbg_int_compiles_and_runs);
    RUN_TEST(test_dbg_str_compiles_and_runs);
    RUN_TEST(test_dbg_tick_inc_compiles_and_runs);
    RUN_TEST(test_dbg_macros_empty_without_debug);
    RUN_TEST(test_start_sets_the_ready_byte);
    RUN_TEST(test_start_clears_the_command_byte);
    RUN_TEST(test_an_empty_mailbox_does_not_move_the_epoch);
    RUN_TEST(test_a_torn_commit_runs_nothing_and_counts);
    RUN_TEST(test_the_frame_after_a_torn_commit_runs_the_command);
    RUN_TEST(test_an_unknown_opcode_is_refused_and_names_itself);
    RUN_TEST(test_every_command_refuses_an_argument_above_its_declared_maximum);
    RUN_TEST(test_every_command_accepts_its_declared_maximum);
    RUN_TEST(test_a_reserved_opcode_reports_unsupported);
    RUN_TEST(test_the_pure_decision_refuses_a_locked_option);
    RUN_TEST(test_the_pure_decision_refuses_a_loadout_change_during_a_race);
    RUN_TEST(test_the_pure_decision_refuses_a_push_at_the_depth_limit);
    RUN_TEST(test_the_three_named_refusals_are_distinct);
    return UNITY_END();
}
