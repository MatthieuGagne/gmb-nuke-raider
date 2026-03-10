#include "unity.h"
#include <gb/gb.h>
#include "sprite_pool.h"

void setUp(void)    { mock_move_sprite_reset(); sprite_pool_init(); }
void tearDown(void) {}

/* --- sprite_pool_init ----------------------------------------------- */

/* After init all 40 slots are free: get_sprite() returns a valid index */
void test_init_all_slots_free(void) {
    uint8_t slot = get_sprite();
    TEST_ASSERT_NOT_EQUAL(SPRITE_POOL_INVALID, slot);
}

/* get_sprite returns indices in range [0, 39] */
void test_get_sprite_returns_valid_index(void) {
    uint8_t slot = get_sprite();
    TEST_ASSERT_LESS_THAN(40u, slot);
}

/* --- get_sprite ----------------------------------------------------- */

/* Each call returns a different (incrementing) slot */
void test_get_sprite_returns_sequential_slots(void) {
    uint8_t s0 = get_sprite();
    uint8_t s1 = get_sprite();
    TEST_ASSERT_EQUAL_UINT8(0u, s0);
    TEST_ASSERT_EQUAL_UINT8(1u, s1);
}

/* After all 40 slots are claimed, returns INVALID */
void test_get_sprite_returns_invalid_when_full(void) {
    uint8_t i;
    for (i = 0u; i < 40u; i++) get_sprite();
    TEST_ASSERT_EQUAL_UINT8(SPRITE_POOL_INVALID, get_sprite());
}

/* --- clear_sprite --------------------------------------------------- */

/* clear_sprite frees the slot so it can be re-claimed */
void test_clear_sprite_frees_slot(void) {
    uint8_t s0 = get_sprite(); /* claims slot 0 */
    clear_sprite(s0);
    uint8_t reclaimed = get_sprite(); /* should get slot 0 back */
    TEST_ASSERT_EQUAL_UINT8(s0, reclaimed);
}

/* clear_sprite calls move_sprite with y=0 (off-screen) */
void test_clear_sprite_hides_sprite(void) {
    uint8_t s0 = get_sprite();
    mock_move_sprite_reset();   /* reset counter after init */
    clear_sprite(s0);
    TEST_ASSERT_EQUAL_UINT8(s0, mock_move_sprite_last_nb);
    TEST_ASSERT_EQUAL_UINT8(0u, mock_move_sprite_last_y);
}

/* --- clear_sprites_from -------------------------------------------- */

/* clear_sprites_from(20) frees slots 20-39 */
void test_clear_sprites_from_frees_range(void) {
    uint8_t i;
    uint8_t next;
    /* Claim all 40 slots */
    for (i = 0u; i < 40u; i++) get_sprite();
    /* Free from 20 onward */
    clear_sprites_from(20u);
    /* Next allocation should be in [20, 39] */
    next = get_sprite();
    TEST_ASSERT_GREATER_OR_EQUAL_UINT8(20u, next);
    TEST_ASSERT_LESS_THAN(40u, next);
}

/* clear_sprites_from(0) frees everything */
void test_clear_sprites_from_zero_frees_all(void) {
    uint8_t i;
    for (i = 0u; i < 40u; i++) get_sprite();
    clear_sprites_from(0u);
    TEST_ASSERT_NOT_EQUAL(SPRITE_POOL_INVALID, get_sprite());
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_init_all_slots_free);
    RUN_TEST(test_get_sprite_returns_valid_index);
    RUN_TEST(test_get_sprite_returns_sequential_slots);
    RUN_TEST(test_get_sprite_returns_invalid_when_full);
    RUN_TEST(test_clear_sprite_frees_slot);
    RUN_TEST(test_clear_sprite_hides_sprite);
    RUN_TEST(test_clear_sprites_from_frees_range);
    RUN_TEST(test_clear_sprites_from_zero_frees_all);
    return UNITY_END();
}
