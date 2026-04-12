#include "unity.h"
#include "config.h"

void setUp(void) {}
void tearDown(void) {}

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
    RUN_TEST(test_portrait_box_width);
    RUN_TEST(test_dialog_box_width);
    return UNITY_END();
}
