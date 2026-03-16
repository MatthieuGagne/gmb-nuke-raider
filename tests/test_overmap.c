#include "unity.h"
#include "state_overmap.h"
#include "state_hub.h"

#include "input.h"

/* input and prev_input defined by tests/mocks/input_globals.c */

/* Helper: simulate a single button tick (rising edge only) */
static void tick(uint8_t btn) {
    prev_input = 0;
    input = btn;
    state_overmap.update();
    prev_input = input;
    input = 0;
}

/* Helper: arm travel with one press, then run 80 frames to complete */
static void travel_to_node(uint8_t btn) {
    uint8_t i;
    prev_input = 0; input = btn;
    state_overmap.update();
    prev_input = input; input = 0;
    for (i = 0u; i < 80u; i++) { state_overmap.update(); }
}

void setUp(void) {
    input = 0;
    prev_input = 0;
    state_overmap.enter();
}

void tearDown(void) {}

void test_car_starts_at_hub(void) {
    TEST_ASSERT_EQUAL_UINT8(overmap_get_spawn_tx(), overmap_get_car_tx());
    TEST_ASSERT_EQUAL_UINT8(overmap_get_spawn_ty(), overmap_get_car_ty());
}

void test_left_travels_to_dest(void) {
    travel_to_node(J_LEFT);
    TEST_ASSERT_EQUAL_UINT8(2u, overmap_get_car_tx());
}

void test_right_travels_to_dest(void) {
    travel_to_node(J_RIGHT);
    TEST_ASSERT_EQUAL_UINT8(17u, overmap_get_car_tx());
}

void test_up_travels_to_city_hub(void) {
    travel_to_node(J_UP);
    /* city hub tile is at (9,6) — arrives at (9,6) which triggers hub entry */
    /* car_ty should be 6 (city hub is at row 6) */
    TEST_ASSERT_EQUAL_UINT8(6u, overmap_get_car_ty());
}

void test_down_blocked_by_blank(void) {
    tick(J_DOWN);
    TEST_ASSERT_EQUAL_UINT8(overmap_get_spawn_ty(), overmap_get_car_ty());
}

void test_held_button_does_not_repeat(void) {
    /* KEY_TICKED fires only on the rising edge, not while held */
    prev_input = J_LEFT;
    input      = J_LEFT;
    state_overmap.update();
    TEST_ASSERT_EQUAL_UINT8(overmap_get_spawn_tx(), overmap_get_car_tx());
}

void test_dest_left_sets_race_id(void) {
    travel_to_node(J_LEFT);
    TEST_ASSERT_EQUAL_UINT8(0u, current_race_id);
}

void test_dest_right_sets_race_id(void) {
    travel_to_node(J_RIGHT);
    TEST_ASSERT_EQUAL_UINT8(1u, current_race_id);
}

void test_city_hub_tile_triggers_hub_entry(void) {
    overmap_hub_entered = 0u;
    travel_to_node(J_UP);
    TEST_ASSERT_EQUAL_UINT8(1u, overmap_hub_entered);
}

void test_city_hub_tile_car_position_unchanged_after_enter(void) {
    travel_to_node(J_UP);
    TEST_ASSERT_EQUAL_UINT8(overmap_get_spawn_tx(), overmap_get_car_tx());
    TEST_ASSERT_EQUAL_UINT8(6u,                     overmap_get_car_ty());
}

void test_input_ignored_while_traveling(void) {
    uint8_t i;
    prev_input = 0; input = J_LEFT; state_overmap.update();  /* arm travel */
    prev_input = 0; input = J_RIGHT; state_overmap.update(); /* mid-travel: ignored */
    prev_input = input; input = 0;
    for (i = 0u; i < 80u; i++) { state_overmap.update(); }
    TEST_ASSERT_EQUAL_UINT8(2u, overmap_get_car_tx());
}

void test_travel_advances_one_tile_per_four_frames(void) {
    uint8_t i;
    prev_input = 0; input = J_LEFT; state_overmap.update();
    prev_input = input; input = 0;
    for (i = 0u; i < 3u; i++) state_overmap.update();
    TEST_ASSERT_EQUAL_UINT8(overmap_get_spawn_tx(),           overmap_get_car_tx()); /* no move at frame 3 */
    state_overmap.update();
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(overmap_get_spawn_tx() - 1u), overmap_get_car_tx()); /* moved at frame 4 */
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_car_starts_at_hub);
    RUN_TEST(test_left_travels_to_dest);
    RUN_TEST(test_right_travels_to_dest);
    RUN_TEST(test_up_travels_to_city_hub);
    RUN_TEST(test_down_blocked_by_blank);
    RUN_TEST(test_held_button_does_not_repeat);
    RUN_TEST(test_dest_left_sets_race_id);
    RUN_TEST(test_dest_right_sets_race_id);
    RUN_TEST(test_city_hub_tile_triggers_hub_entry);
    RUN_TEST(test_city_hub_tile_car_position_unchanged_after_enter);
    RUN_TEST(test_input_ignored_while_traveling);
    RUN_TEST(test_travel_advances_one_tile_per_four_frames);
    return UNITY_END();
}
