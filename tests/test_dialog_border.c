#include "unity.h"
#include "config.h"

void setUp(void) {}
void tearDown(void) {}

/* HUB_BORDER_TILE_SLOT must be exactly 112 (first free slot after portrait 96-111) */
void test_border_tile_slot_is_112(void) {
    TEST_ASSERT_EQUAL_UINT8(112u, HUB_BORDER_TILE_SLOT);
}

/* 8 border tiles must not overflow into HUD font area (starts at 128) */
void test_border_tiles_fit_before_font(void) {
    TEST_ASSERT_TRUE(HUB_BORDER_TILE_SLOT + 8u <= 128u);
}

/* No overlap with portrait tiles (96-111) */
void test_border_slot_does_not_overlap_portrait(void) {
    TEST_ASSERT_TRUE(HUB_BORDER_TILE_SLOT >= HUB_PORTRAIT_TILE_SLOT + 16u);
}

/* Portrait box is 6 tiles wide (cols 0-5) */
void test_portrait_box_width(void) {
    TEST_ASSERT_EQUAL_UINT8(6u, HUB_PORTRAIT_BOX_W);
}

/* Dialog box is 14 tiles wide (cols 6-19) */
void test_dialog_box_width(void) {
    TEST_ASSERT_EQUAL_UINT8(14u, HUB_DIALOG_BOX_W);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_border_tile_slot_is_112);
    RUN_TEST(test_border_tiles_fit_before_font);
    RUN_TEST(test_border_slot_does_not_overlap_portrait);
    RUN_TEST(test_portrait_box_width);
    RUN_TEST(test_dialog_box_width);
    return UNITY_END();
}
