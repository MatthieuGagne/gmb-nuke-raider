/*
 * tests/test_gamestate.c — Unit tests for game state logic.
 *
 * Compiled with gcc + mock GBDK headers (no hardware dependency).
 * Pattern: define TESTING before including main.c to skip void main(void).
 *
 * Add tests here as pure logic is extracted from main.c into helper
 * functions. E.g. move collision detection, scoring, etc. into
 * src/logic.c and test those functions directly.
 */

#include "unity/src/unity.h"

/* Pull in mock CGB type so _cpu is defined */
#include "mocks/gb/cgb.h"
uint8_t _cpu = DMG_TYPE;  /* default to DMG in tests */

/* ------------------------------------------------------------------ */
/* Example: test the GameState enum values are what we expect.
   Replace with real logic tests as the game grows.                    */
/* ------------------------------------------------------------------ */

/* Replicate the enum locally (or include a shared header once one exists) */
typedef enum {
    STATE_INIT,
    STATE_TITLE,
    STATE_PLAYING,
    STATE_GAME_OVER
} GameState;

void setUp(void) {}
void tearDown(void) {}

void test_gamestate_enum_values(void) {
    TEST_ASSERT_EQUAL_INT(0, STATE_INIT);
    TEST_ASSERT_EQUAL_INT(1, STATE_TITLE);
    TEST_ASSERT_EQUAL_INT(2, STATE_PLAYING);
    TEST_ASSERT_EQUAL_INT(3, STATE_GAME_OVER);
}

void test_gamestate_initial_is_not_playing(void) {
    GameState s = STATE_INIT;
    TEST_ASSERT_NOT_EQUAL(STATE_PLAYING, s);
}

/* ------------------------------------------------------------------ */
/* Runner                                                               */
/* ------------------------------------------------------------------ */

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_gamestate_enum_values);
    RUN_TEST(test_gamestate_initial_is_not_playing);
    return UNITY_END();
}
