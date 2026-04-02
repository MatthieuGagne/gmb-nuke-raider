/* tests/test_economy.c — unit tests for the economy module */
#include "unity.h"
#include <gb/gb.h>
#include "../src/economy.h"

void setUp(void)    { economy_init(); }
void tearDown(void) {}

/* --- init --- */

void test_init_balance_is_zero(void) {
    TEST_ASSERT_EQUAL_UINT16(0u, economy_get_scrap());
}

/* --- economy_add_scrap --- */

void test_add_increases_balance(void) {
    economy_add_scrap(50u);
    TEST_ASSERT_EQUAL_UINT16(50u, economy_get_scrap());
}

void test_add_accumulates(void) {
    economy_add_scrap(50u);
    economy_add_scrap(100u);
    TEST_ASSERT_EQUAL_UINT16(150u, economy_get_scrap());
}

/* --- economy_spend_scrap --- */

void test_spend_decreases_balance(void) {
    economy_add_scrap(100u);
    economy_spend_scrap(40u);
    TEST_ASSERT_EQUAL_UINT16(60u, economy_get_scrap());
}

void test_spend_returns_true_when_sufficient(void) {
    economy_add_scrap(100u);
    TEST_ASSERT_EQUAL_UINT8(1u, economy_spend_scrap(100u));
}

void test_spend_returns_false_when_insufficient(void) {
    economy_add_scrap(50u);
    TEST_ASSERT_EQUAL_UINT8(0u, economy_spend_scrap(100u));
}

void test_spend_balance_unchanged_when_insufficient(void) {
    economy_add_scrap(50u);
    economy_spend_scrap(100u);
    TEST_ASSERT_EQUAL_UINT16(50u, economy_get_scrap());
}

void test_spend_exact_amount_leaves_zero(void) {
    economy_add_scrap(75u);
    economy_spend_scrap(75u);
    TEST_ASSERT_EQUAL_UINT16(0u, economy_get_scrap());
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_init_balance_is_zero);
    RUN_TEST(test_add_increases_balance);
    RUN_TEST(test_add_accumulates);
    RUN_TEST(test_spend_decreases_balance);
    RUN_TEST(test_spend_returns_true_when_sufficient);
    RUN_TEST(test_spend_returns_false_when_insufficient);
    RUN_TEST(test_spend_balance_unchanged_when_insufficient);
    RUN_TEST(test_spend_exact_amount_leaves_zero);
    return UNITY_END();
}
