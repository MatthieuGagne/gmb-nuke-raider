#include "unity.h"
#include "camera.h"
#include "track.h"

void setUp(void)    {}
void tearDown(void) {}

/* --- camera_init centering ------------------------------------------ */

/* Player at world center (160, 144): cam should center on player.
 * cam_x = 160 - 80 = 80, cam_y = 144 - 72 = 72 */
void test_camera_init_centers_on_player(void) {
    camera_init(160, 144);
    TEST_ASSERT_EQUAL_UINT8(80, cam_x);
    TEST_ASSERT_EQUAL_UINT8(72, cam_y);
}

/* --- camera_update centering ---------------------------------------- */

void test_camera_update_centers_on_player(void) {
    camera_init(160, 144);
    camera_update(200, 180);
    /* cam_x = 200-80=120, cam_y = 180-72=108 */
    TEST_ASSERT_EQUAL_UINT8(120, cam_x);
    TEST_ASSERT_EQUAL_UINT8(108, cam_y);
}

/* --- Camera clamp: left / top edge ---------------------------------- */

/* Player so far left that cam would go negative: clamp to 0 */
void test_camera_clamp_left_edge(void) {
    camera_init(40, 144);
    /* cam_x = 40-80 = -40 -> clamped to 0 */
    TEST_ASSERT_EQUAL_UINT8(0, cam_x);
}

void test_camera_clamp_top_edge(void) {
    camera_init(160, 40);
    /* cam_y = 40-72 = -32 -> clamped to 0 */
    TEST_ASSERT_EQUAL_UINT8(0, cam_y);
}

/* --- Camera clamp: right / bottom edge ------------------------------ */

/* MAP_PX_W=320, CAM_MAX_X=160. Player at x=280: cam=280-80=200 -> clamp to 160 */
void test_camera_clamp_right_edge(void) {
    camera_init(280, 144);
    TEST_ASSERT_EQUAL_UINT8(160, cam_x);
}

/* MAP_PX_H=288, CAM_MAX_Y=144. Player at y=260: cam=260-72=188 -> clamp to 144 */
void test_camera_clamp_bottom_edge(void) {
    camera_init(160, 260);
    TEST_ASSERT_EQUAL_UINT8(144, cam_y);
}

/* --- Exact clamp boundaries ----------------------------------------- */

void test_camera_update_clamp_exact_max_x(void) {
    camera_init(160, 144);
    camera_update(240, 144);   /* cam_x = 240-80 = 160 = CAM_MAX_X exactly */
    TEST_ASSERT_EQUAL_UINT8(160, cam_x);
}

void test_camera_update_clamp_exact_max_y(void) {
    camera_init(160, 144);
    camera_update(160, 216);   /* cam_y = 216-72 = 144 = CAM_MAX_Y exactly */
    TEST_ASSERT_EQUAL_UINT8(144, cam_y);
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_camera_init_centers_on_player);
    RUN_TEST(test_camera_update_centers_on_player);
    RUN_TEST(test_camera_clamp_left_edge);
    RUN_TEST(test_camera_clamp_top_edge);
    RUN_TEST(test_camera_clamp_right_edge);
    RUN_TEST(test_camera_clamp_bottom_edge);
    RUN_TEST(test_camera_update_clamp_exact_max_x);
    RUN_TEST(test_camera_update_clamp_exact_max_y);
    return UNITY_END();
}
