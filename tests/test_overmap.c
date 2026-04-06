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

void test_overmap_car_props_up(void) {
    uint8_t tile, props;
    overmap_car_props(J_UP, &tile, &props);
    TEST_ASSERT_EQUAL_UINT8(OVERMAP_CAR_TILE_BASE, tile);
    TEST_ASSERT_EQUAL_UINT8(0u, props);
}

void test_overmap_car_props_down(void) {
    uint8_t tile, props;
    overmap_car_props(J_DOWN, &tile, &props);
    TEST_ASSERT_EQUAL_UINT8(OVERMAP_CAR_TILE_BASE, tile);
    TEST_ASSERT_EQUAL_UINT8(S_FLIPY, props);
}

void test_overmap_car_props_left(void) {
    uint8_t tile, props;
    overmap_car_props(J_LEFT, &tile, &props);
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(OVERMAP_CAR_TILE_BASE + 1u), tile);
    TEST_ASSERT_EQUAL_UINT8(0u, props);
}

void test_overmap_car_props_right(void) {
    uint8_t tile, props;
    overmap_car_props(J_RIGHT, &tile, &props);
    TEST_ASSERT_EQUAL_UINT8((uint8_t)(OVERMAP_CAR_TILE_BASE + 1u), tile);
    TEST_ASSERT_EQUAL_UINT8(S_FLIPX, props);
}

void test_id_map_contains_dest_track_ids(void) {
    /* left dest (tx=2, ty=8): track_id=1 in Tiled -> 0-based index 0 */
    TEST_ASSERT_EQUAL_UINT8(0u, overmap_id_map[(uint16_t)8u * OVERMAP_W + 2u]);
    /* right dest (tx=17, ty=8): track_id=2 -> index 1 */
    TEST_ASSERT_EQUAL_UINT8(1u, overmap_id_map[(uint16_t)8u * OVERMAP_W + 17u]);
    /* bottom dest (tx=9, ty=9): track_id=3 -> index 2 */
    TEST_ASSERT_EQUAL_UINT8(2u, overmap_id_map[(uint16_t)9u * OVERMAP_W + 9u]);
}

void test_id_map_contains_city_hub_id(void) {
    /* city hub (tx=9, ty=6): hub_id=1 in Tiled -> 0-based index 0 */
    TEST_ASSERT_EQUAL_UINT8(0u, overmap_id_map[(uint16_t)6u * OVERMAP_W + 9u]);
}

void test_id_map_blank_tile_is_sentinel(void) {
    /* top-left corner is OVERMAP_TILE_BLANK — no id */
    TEST_ASSERT_EQUAL_UINT8(0xFFu, overmap_id_map[0u]);
}

void test_hub_spawn_constants(void) {
    TEST_ASSERT_EQUAL_UINT8(9u, overmap_hub_spawn_tx);
    TEST_ASSERT_EQUAL_UINT8(8u, overmap_hub_spawn_ty);
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
    RUN_TEST(test_overmap_car_props_up);
    RUN_TEST(test_overmap_car_props_down);
    RUN_TEST(test_overmap_car_props_left);
    RUN_TEST(test_overmap_car_props_right);
    RUN_TEST(test_id_map_contains_dest_track_ids);
    RUN_TEST(test_id_map_contains_city_hub_id);
    RUN_TEST(test_id_map_blank_tile_is_sentinel);
    RUN_TEST(test_hub_spawn_constants);
    return UNITY_END();
}
