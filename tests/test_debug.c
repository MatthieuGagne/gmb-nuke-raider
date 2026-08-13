#include "unity.h"

/* Force DEBUG on for this test so macros expand to EMU_printf calls */
#define DEBUG
#include "debug.h"
#include "state_manager.h"
#include "economy.h"
#include "loadout.h"
#include "damage.h"
#include "turret.h"
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

/* ---- substitutable game seams (host build only) --------------------------- */
static uint8_t fake_spawn_calls;
static uint8_t fake_spawn_tx;
static uint8_t fake_spawn_ty;
static uint8_t fake_spawn_result;
static uint8_t fake_despawn_slot;
static uint8_t fake_despawn_result;

static uint8_t fake_spawn(uint8_t tx, uint8_t ty) {
    fake_spawn_calls++; fake_spawn_tx = tx; fake_spawn_ty = ty;
    return fake_spawn_result;
}
static uint8_t fake_despawn(uint8_t slot) {
    fake_despawn_slot = slot; return fake_despawn_result;
}
static const DbgEnemyOps FAKE_OPS = {fake_spawn, fake_despawn};

/* Seven stand-ins for the seven real states. Only `playing` counts its updates. */
static uint8_t playing_updates;
static void nop_enter(void) {}
static void nop_update(void) {}
static void nop_exit(void) {}
static void playing_update(void) { playing_updates++; }

static const State FAKE_PLAIN   = {0u, nop_enter, nop_update, nop_exit};
static const State FAKE_PLAYING = {0u, nop_enter, playing_update, nop_exit};

static const State *const FAKE_STATES[DBG_STATE_COUNT] = {
    &FAKE_PLAIN, &FAKE_PLAIN, &FAKE_PLAIN, &FAKE_PLAIN,
    &FAKE_PLAYING,                      /* index DBG_STATE_PLAYING */
    &FAKE_PLAIN, &FAKE_PLAIN
};

static void mailbox_fixture(void) {
    fake_spawn_calls = 0u; fake_spawn_result = 1u;
    fake_despawn_slot = 0xFFu; fake_despawn_result = 1u;
    playing_updates = 0u;
    debug_set_enemy_ops(&FAKE_OPS);
    debug_set_state_table(FAKE_STATES, DBG_STATE_COUNT);
    debug_mailbox_start();
    economy_init();
    loadout_init();
    damage_init();
    state_manager_init();
}

static uint8_t run_cmd(uint8_t opcode, uint8_t arg0, uint8_t arg1) {
    mb_put(opcode, arg0, arg1, (uint8_t)(DBG_MB_SEED ^ opcode ^ arg0 ^ arg1));
    debug_mailbox_poll();
    return debug_mb_read(DBG_MB_OFF_OUTCOME);
}

void test_add_scrap_reaches_the_economy(void) {
    mailbox_fixture();
    TEST_ASSERT_EQUAL_UINT8(DBG_OUT_OK,
                            run_cmd(DBG_OP_ADD_SCRAP, 0x2Cu, 0x01u));  /* 300 */
    TEST_ASSERT_EQUAL_UINT16(300u, economy_get_scrap());
}

void test_equipping_a_locked_option_is_refused_and_names_the_field(void) {
    mailbox_fixture();
    TEST_ASSERT_EQUAL_UINT8(
        DBG_OUT_LOCKED,
        run_cmd(DBG_OP_SET_OPTION, LOADOUT_FIELD_WEAPON1, LOADOUT_WEAPON1_LASER));
    TEST_ASSERT_EQUAL_UINT8(LOADOUT_FIELD_WEAPON1, debug_mb_read(DBG_MB_OFF_DETAIL));
    TEST_ASSERT_EQUAL_UINT8(LOADOUT_DEFAULT_WEAPON1, loadout_get_weapon1());
}

void test_unlocking_first_lets_the_laser_be_equipped(void) {
    mailbox_fixture();
    TEST_ASSERT_EQUAL_UINT8(DBG_OUT_OK,
                            run_cmd(DBG_OP_UNLOCK_FIELD, LOADOUT_FIELD_WEAPON1, 0u));
    TEST_ASSERT_EQUAL_UINT8(
        DBG_OUT_OK,
        run_cmd(DBG_OP_SET_OPTION, LOADOUT_FIELD_WEAPON1, LOADOUT_WEAPON1_LASER));
    TEST_ASSERT_EQUAL_UINT8(LOADOUT_WEAPON1_LASER, loadout_get_weapon1());
}

/* AC4 */
void test_a_loadout_change_during_a_race_is_refused_and_changes_nothing(void) {
    mailbox_fixture();
    run_cmd(DBG_OP_UNLOCK_FIELD, LOADOUT_FIELD_WEAPON1, 0u);
    state_push(FAKE_STATES[DBG_STATE_PLAYING], 0u);      /* the game is now racing */
    TEST_ASSERT_EQUAL_UINT8(
        DBG_OUT_IN_RACE,
        run_cmd(DBG_OP_SET_OPTION, LOADOUT_FIELD_WEAPON1, LOADOUT_WEAPON1_LASER));
    TEST_ASSERT_EQUAL_UINT8(LOADOUT_DEFAULT_WEAPON1, loadout_get_weapon1());
}

/* AC5 */
void test_a_push_at_the_depth_limit_is_refused_and_the_depth_holds(void) {
    mailbox_fixture();
    state_push(&FAKE_PLAIN, 0u);
    state_push(&FAKE_PLAIN, 0u);             /* depth is now STACK_MAX */
    TEST_ASSERT_EQUAL_UINT8(STACK_MAX, state_manager_depth());
    TEST_ASSERT_EQUAL_UINT8(DBG_OUT_STACK_FULL,
                            run_cmd(DBG_OP_FORCE_STATE, DBG_STATE_PLAYING, 0u));
    TEST_ASSERT_EQUAL_UINT8(STACK_MAX, state_manager_depth());
    TEST_ASSERT_EQUAL_UINT8(STACK_MAX, debug_mb_read(DBG_MB_OFF_DETAIL));
}

/* AC12: a forced transition must give the new state its first update on the FOLLOWING frame,
 * exactly as a real transition does. The counting state is the transition's destination, so
 * a poll that ran the new state's update immediately would fail the first assertion. */
void test_a_forced_push_runs_the_new_state_update_on_the_following_frame(void) {
    mailbox_fixture();
    state_push(&FAKE_PLAIN, 0u);                          /* depth 1, not the counter */

    /* Frame N: state_manager_update() runs the OLD state, then the poll pushes the new one. */
    state_manager_update();
    TEST_ASSERT_EQUAL_UINT8(DBG_OUT_OK,
                            run_cmd(DBG_OP_FORCE_STATE, DBG_STATE_PLAYING, 0u));
    TEST_ASSERT_EQUAL_UINT8(2u, state_manager_depth());
    TEST_ASSERT_EQUAL_UINT8(0u, playing_updates);         /* not on the frame it entered */

    /* Frame N+1: the new state gets its first update. */
    state_manager_update();
    TEST_ASSERT_EQUAL_UINT8(1u, playing_updates);

    /* Frame N+2: and its second, so the count is a count and not a one-shot. */
    state_manager_update();
    TEST_ASSERT_EQUAL_UINT8(2u, playing_updates);
}

void test_a_forced_pop_at_depth_zero_is_refused(void) {
    mailbox_fixture();
    TEST_ASSERT_EQUAL_UINT8(0u, state_manager_depth());
    TEST_ASSERT_EQUAL_UINT8(DBG_OUT_STACK_FULL,
                            run_cmd(DBG_OP_FORCE_STATE, 0u, 1u));
}

void test_a_forced_replace_swaps_the_top_slot_without_changing_the_depth(void) {
    mailbox_fixture();
    state_push(&FAKE_PLAIN, 0u);
    TEST_ASSERT_EQUAL_UINT8(DBG_OUT_OK,
                            run_cmd(DBG_OP_FORCE_STATE, DBG_STATE_PLAYING, 2u));
    TEST_ASSERT_EQUAL_UINT8(1u, state_manager_depth());
    TEST_ASSERT_EQUAL_PTR(FAKE_STATES[DBG_STATE_PLAYING], state_manager_top());
}

void test_damage_reaches_the_damage_module(void) {
    mailbox_fixture();
    TEST_ASSERT_EQUAL_UINT8(DBG_OUT_OK, run_cmd(DBG_OP_DAMAGE, 10u, 0u));
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(PLAYER_MAX_HP - 10u), damage_get_hp());
    TEST_ASSERT_EQUAL_UINT8(damage_get_hp(), debug_mb_read(DBG_MB_OFF_DETAIL));
}

void test_damage_during_invincibility_reports_no_effect(void) {
    mailbox_fixture();
    run_cmd(DBG_OP_DAMAGE, 10u, 0u);                    /* arms the i-frames */
    TEST_ASSERT_EQUAL_UINT8(DBG_OUT_NO_EFFECT, run_cmd(DBG_OP_DAMAGE, 10u, 0u));
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(PLAYER_MAX_HP - 10u), damage_get_hp());
}

void test_heal_reaches_the_damage_module(void) {
    mailbox_fixture();
    run_cmd(DBG_OP_DAMAGE, 20u, 0u);
    TEST_ASSERT_EQUAL_UINT8(DBG_OUT_OK, run_cmd(DBG_OP_HEAL, 5u, 0u));
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(PLAYER_MAX_HP - 15u), damage_get_hp());
}

void test_spawn_turret_passes_the_tile_position_through(void) {
    mailbox_fixture();
    TEST_ASSERT_EQUAL_UINT8(DBG_OUT_OK, run_cmd(DBG_OP_SPAWN_TURRET, 7u, 9u));
    TEST_ASSERT_EQUAL_UINT8(1u, fake_spawn_calls);
    TEST_ASSERT_EQUAL_UINT8(7u, fake_spawn_tx);
    TEST_ASSERT_EQUAL_UINT8(9u, fake_spawn_ty);
}

void test_a_full_turret_pool_reports_pool_full(void) {
    mailbox_fixture();
    fake_spawn_result = 0u;
    TEST_ASSERT_EQUAL_UINT8(DBG_OUT_POOL_FULL, run_cmd(DBG_OP_SPAWN_TURRET, 1u, 1u));
}

void test_despawn_reaches_the_pool(void) {
    mailbox_fixture();
    TEST_ASSERT_EQUAL_UINT8(DBG_OUT_OK, run_cmd(DBG_OP_DESPAWN_TURRET, 3u, 0u));
    TEST_ASSERT_EQUAL_UINT8(3u, fake_despawn_slot);
}

void test_despawning_an_inactive_slot_is_refused(void) {
    mailbox_fixture();
    fake_despawn_result = 0u;                    /* turret_despawn returns 0 for a free slot */
    TEST_ASSERT_EQUAL_UINT8(DBG_OUT_NOT_ACTIVE, run_cmd(DBG_OP_DESPAWN_TURRET, 3u, 0u));
    TEST_ASSERT_EQUAL_UINT8(3u, debug_mb_read(DBG_MB_OFF_DETAIL));
}

void test_a_reserved_spawn_reports_unsupported_over_the_wire(void) {
    mailbox_fixture();
    TEST_ASSERT_EQUAL_UINT8(DBG_OUT_UNSUPPORTED, run_cmd(DBG_OP_SPAWN_RACER, 1u, 1u));
    TEST_ASSERT_EQUAL_UINT8(0u, fake_spawn_calls);
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
    RUN_TEST(test_add_scrap_reaches_the_economy);
    RUN_TEST(test_equipping_a_locked_option_is_refused_and_names_the_field);
    RUN_TEST(test_unlocking_first_lets_the_laser_be_equipped);
    RUN_TEST(test_a_loadout_change_during_a_race_is_refused_and_changes_nothing);
    RUN_TEST(test_a_push_at_the_depth_limit_is_refused_and_the_depth_holds);
    RUN_TEST(test_a_forced_push_runs_the_new_state_update_on_the_following_frame);
    RUN_TEST(test_a_forced_pop_at_depth_zero_is_refused);
    RUN_TEST(test_a_forced_replace_swaps_the_top_slot_without_changing_the_depth);
    RUN_TEST(test_damage_reaches_the_damage_module);
    RUN_TEST(test_damage_during_invincibility_reports_no_effect);
    RUN_TEST(test_heal_reaches_the_damage_module);
    RUN_TEST(test_spawn_turret_passes_the_tile_position_through);
    RUN_TEST(test_a_full_turret_pool_reports_pool_full);
    RUN_TEST(test_despawn_reaches_the_pool);
    RUN_TEST(test_despawning_an_inactive_slot_is_refused);
    RUN_TEST(test_a_reserved_spawn_reports_unsupported_over_the_wire);
    return UNITY_END();
}
