#include "unity.h"
#include "vram_queue.h"

/* Pull in mock tracking state from mock_bkg.c */
extern uint8_t  mock_vram[32u * 32u];
extern uint8_t  mock_win_vram[32u * 32u];
extern int      mock_set_bkg_tiles_call_count;
extern int      mock_set_win_tiles_call_count;
void mock_vram_clear(void);

void setUp(void) {
    vram_queue_init();
    mock_vram_clear();
}
void tearDown(void) {}

/* Flushing an empty queue calls nothing */
void test_flush_empty_does_nothing(void) {
    vram_queue_flush();
    TEST_ASSERT_EQUAL_INT(0, mock_set_bkg_tiles_call_count);
    TEST_ASSERT_EQUAL_INT(0, mock_set_win_tiles_call_count);
}

/* A queued BKG write is dispatched to set_bkg_tiles on flush */
void test_enqueue_bkg_dispatches_on_flush(void) {
    static const uint8_t tiles[3] = {10u, 11u, 12u};
    vram_queue_bkg(2u, 5u, 3u, 1u, tiles);
    vram_queue_flush();
    TEST_ASSERT_EQUAL_INT(1, mock_set_bkg_tiles_call_count);
    /* Verify data landed in mock_vram at (2,5) */
    TEST_ASSERT_EQUAL_UINT8(10u, mock_vram[5u * 32u + 2u]);
    TEST_ASSERT_EQUAL_UINT8(11u, mock_vram[5u * 32u + 3u]);
    TEST_ASSERT_EQUAL_UINT8(12u, mock_vram[5u * 32u + 4u]);
}

/* A queued WIN write is dispatched to set_win_tiles on flush */
void test_enqueue_win_dispatches_on_flush(void) {
    static const uint8_t tiles[5] = {20u, 21u, 22u, 23u, 24u};
    vram_queue_win(15u, 0u, 5u, 1u, tiles);
    vram_queue_flush();
    TEST_ASSERT_EQUAL_INT(1, mock_set_win_tiles_call_count);
    TEST_ASSERT_EQUAL_UINT8(20u, mock_win_vram[0u * 32u + 15u]);
}

/* flush() clears the queue — second flush is a no-op */
void test_flush_clears_queue(void) {
    static const uint8_t tiles[1] = {7u};
    vram_queue_bkg(0u, 0u, 1u, 1u, tiles);
    vram_queue_flush();
    mock_vram_clear();
    vram_queue_flush();  /* second flush — queue should be empty */
    TEST_ASSERT_EQUAL_INT(0, mock_set_bkg_tiles_call_count);
}

/* Tile data is COPIED into the queue (caller's buffer can change after enqueue) */
void test_enqueue_copies_tile_data(void) {
    uint8_t buf[3] = {1u, 2u, 3u};
    vram_queue_bkg(0u, 0u, 3u, 1u, buf);
    buf[0] = 99u;       /* mutate caller's buffer after enqueue */
    vram_queue_flush();
    /* mock_vram[0] must be 1 (the original value), not 99 */
    TEST_ASSERT_EQUAL_UINT8(1u, mock_vram[0u]);
}

/* Multiple entries flush in enqueue order */
void test_multiple_entries_flush_in_order(void) {
    static const uint8_t t0[1] = {1u};
    static const uint8_t t1[1] = {2u};
    vram_queue_bkg(0u, 0u, 1u, 1u, t0);
    vram_queue_bkg(0u, 1u, 1u, 1u, t1);
    vram_queue_flush();
    TEST_ASSERT_EQUAL_INT(2, mock_set_bkg_tiles_call_count);
    TEST_ASSERT_EQUAL_UINT8(1u, mock_vram[0u * 32u + 0u]);
    TEST_ASSERT_EQUAL_UINT8(2u, mock_vram[1u * 32u + 0u]);
}

/* Mixed BKG + WIN entries both flush correctly */
void test_mixed_bkg_win_flush(void) {
    static const uint8_t bkg[1] = {5u};
    static const uint8_t win[1] = {6u};
    vram_queue_bkg(0u, 0u, 1u, 1u, bkg);
    vram_queue_win(0u, 0u, 1u, 1u, win);
    vram_queue_flush();
    TEST_ASSERT_EQUAL_INT(1, mock_set_bkg_tiles_call_count);
    TEST_ASSERT_EQUAL_INT(1, mock_set_win_tiles_call_count);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_flush_empty_does_nothing);
    RUN_TEST(test_enqueue_bkg_dispatches_on_flush);
    RUN_TEST(test_enqueue_win_dispatches_on_flush);
    RUN_TEST(test_flush_clears_queue);
    RUN_TEST(test_enqueue_copies_tile_data);
    RUN_TEST(test_multiple_entries_flush_in_order);
    RUN_TEST(test_mixed_bkg_win_flush);
    return UNITY_END();
}
