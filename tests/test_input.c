#include "unity.h"
#include <gb/gb.h>
#include "../src/input.h"

/* input/prev_input globals defined in tests/mocks/input_globals.c */

void setUp(void)    { input = 0; prev_input = 0; }
void tearDown(void) {}

/* KEY_PRESSED --------------------------------------------------------- */

void test_key_pressed_true_when_button_held(void) {
    input = J_LEFT;
    TEST_ASSERT_TRUE(KEY_PRESSED(J_LEFT));
}

void test_key_pressed_false_when_button_not_held(void) {
    input = 0;
    TEST_ASSERT_FALSE(KEY_PRESSED(J_LEFT));
}

/* KEY_TICKED ---------------------------------------------------------- */

void test_key_ticked_true_on_first_press(void) {
    prev_input = 0;
    input      = J_START;
    TEST_ASSERT_TRUE(KEY_TICKED(J_START));
}

void test_key_ticked_false_while_held(void) {
    prev_input = J_START;
    input      = J_START;
    TEST_ASSERT_FALSE(KEY_TICKED(J_START));
}

void test_key_ticked_false_when_not_pressed(void) {
    prev_input = 0;
    input      = 0;
    TEST_ASSERT_FALSE(KEY_TICKED(J_START));
}

/* KEY_RELEASED -------------------------------------------------------- */

void test_key_released_true_on_first_release(void) {
    prev_input = J_A;
    input      = 0;
    TEST_ASSERT_TRUE(KEY_RELEASED(J_A));
}

void test_key_released_false_when_still_held(void) {
    prev_input = J_A;
    input      = J_A;
    TEST_ASSERT_FALSE(KEY_RELEASED(J_A));
}

void test_key_released_false_when_never_pressed(void) {
    prev_input = 0;
    input      = 0;
    TEST_ASSERT_FALSE(KEY_RELEASED(J_A));
}

/* KEY_DEBOUNCE -------------------------------------------------------- */

void test_key_debounce_true_when_held_both_frames(void) {
    prev_input = J_B;
    input      = J_B;
    TEST_ASSERT_TRUE(KEY_DEBOUNCE(J_B));
}

void test_key_debounce_false_on_first_press(void) {
    prev_input = 0;
    input      = J_B;
    TEST_ASSERT_FALSE(KEY_DEBOUNCE(J_B));
}

void test_key_debounce_false_after_release(void) {
    prev_input = J_B;
    input      = 0;
    TEST_ASSERT_FALSE(KEY_DEBOUNCE(J_B));
}

/* input_update -------------------------------------------------------- */

/* The mock joypad() in tests/mocks/gb/gb.h always returns 0.
 * So after input_update(): prev_input = old input, input = 0. */
void test_input_update_saves_input_to_prev(void) {
    input = J_LEFT;
    input_update();
    TEST_ASSERT_EQUAL_UINT8(J_LEFT, prev_input);
}

void test_input_update_reads_joypad_into_input(void) {
    input = J_LEFT;
    input_update();                 /* mock returns 0 */
    TEST_ASSERT_EQUAL_UINT8(0, input);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_key_pressed_true_when_button_held);
    RUN_TEST(test_key_pressed_false_when_button_not_held);
    RUN_TEST(test_key_ticked_true_on_first_press);
    RUN_TEST(test_key_ticked_false_while_held);
    RUN_TEST(test_key_ticked_false_when_not_pressed);
    RUN_TEST(test_key_released_true_on_first_release);
    RUN_TEST(test_key_released_false_when_still_held);
    RUN_TEST(test_key_released_false_when_never_pressed);
    RUN_TEST(test_key_debounce_true_when_held_both_frames);
    RUN_TEST(test_key_debounce_false_on_first_press);
    RUN_TEST(test_key_debounce_false_after_release);
    RUN_TEST(test_input_update_saves_input_to_prev);
    RUN_TEST(test_input_update_reads_joypad_into_input);
    return UNITY_END();
}
