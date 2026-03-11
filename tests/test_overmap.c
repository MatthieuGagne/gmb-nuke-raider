#include "unity.h"
#include "state_overmap.h"
#include "state_hub.h"
#include "config.h"
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

void setUp(void) {
    input = 0;
    prev_input = 0;
    state_overmap.enter();
}

void tearDown(void) {}

void test_car_starts_at_hub(void) {
    TEST_ASSERT_EQUAL_UINT8(OVERMAP_HUB_TX, overmap_get_car_tx());
    TEST_ASSERT_EQUAL_UINT8(OVERMAP_HUB_TY, overmap_get_car_ty());
}

void test_left_moves_onto_road(void) {
    tick(J_LEFT);
    TEST_ASSERT_EQUAL_UINT8(OVERMAP_HUB_TX - 1u, overmap_get_car_tx());
    TEST_ASSERT_EQUAL_UINT8(OVERMAP_HUB_TY,      overmap_get_car_ty());
}

void test_right_moves_onto_road(void) {
    tick(J_RIGHT);
    TEST_ASSERT_EQUAL_UINT8(OVERMAP_HUB_TX + 1u, overmap_get_car_tx());
}

void test_up_moves_onto_road_tile(void) {
    /* Row 7 col 9 is now a road tile — moving up from spawn must succeed */
    tick(J_UP);
    TEST_ASSERT_EQUAL_UINT8(OVERMAP_HUB_TY - 1u, overmap_get_car_ty());
}

void test_down_blocked_by_blank(void) {
    tick(J_DOWN);
    TEST_ASSERT_EQUAL_UINT8(OVERMAP_HUB_TY, overmap_get_car_ty());
}

void test_held_button_does_not_repeat(void) {
    /* KEY_TICKED fires only on the rising edge, not while held */
    prev_input = J_LEFT;
    input      = J_LEFT;
    state_overmap.update();
    TEST_ASSERT_EQUAL_UINT8(OVERMAP_HUB_TX, overmap_get_car_tx());
}

void test_dest_left_sets_race_id(void) {
    /* Walk left from hub (tx=9) to dest (tx=2): 7 ticks */
    uint8_t moves = OVERMAP_HUB_TX - OVERMAP_DEST_LEFT_TX;
    uint8_t i;
    for (i = 0; i < moves; i++) {
        tick(J_LEFT);
    }
    TEST_ASSERT_EQUAL_UINT8(0u, current_race_id);
}

void test_dest_right_sets_race_id(void) {
    uint8_t moves = OVERMAP_DEST_RIGHT_TX - OVERMAP_HUB_TX;
    uint8_t i;
    for (i = 0; i < moves; i++) {
        tick(J_RIGHT);
    }
    TEST_ASSERT_EQUAL_UINT8(1u, current_race_id);
}

void test_city_hub_tile_triggers_hub_entry(void) {
    /* City hub building is at (9, 6) — two moves north from spawn. */
    overmap_hub_entered = 0u;
    tick(J_UP);  /* (9,8) → (9,7) road */
    TEST_ASSERT_EQUAL_UINT8(0u, overmap_hub_entered);  /* road: no trigger yet */
    tick(J_UP);  /* (9,7) → (9,6) city hub */
    TEST_ASSERT_EQUAL_UINT8(1u, overmap_hub_entered);
}

void test_city_hub_tile_car_position_unchanged_after_enter(void) {
    /* Car should stay at (9,6) after entering hub */
    tick(J_UP);
    tick(J_UP);
    TEST_ASSERT_EQUAL_UINT8(OVERMAP_HUB_TX,      overmap_get_car_tx());
    TEST_ASSERT_EQUAL_UINT8(OVERMAP_HUB_TY - 2u, overmap_get_car_ty());
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_car_starts_at_hub);
    RUN_TEST(test_left_moves_onto_road);
    RUN_TEST(test_right_moves_onto_road);
    RUN_TEST(test_up_moves_onto_road_tile);
    RUN_TEST(test_down_blocked_by_blank);
    RUN_TEST(test_held_button_does_not_repeat);
    RUN_TEST(test_dest_left_sets_race_id);
    RUN_TEST(test_dest_right_sets_race_id);
    RUN_TEST(test_city_hub_tile_triggers_hub_entry);
    RUN_TEST(test_city_hub_tile_car_position_unchanged_after_enter);
    return UNITY_END();
}
