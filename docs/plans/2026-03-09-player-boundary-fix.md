# Player Right/Bottom Boundary Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix `PX_MAX` and `PY_MAX` so the player sprite's right and bottom edges clamp at the screen edge (screen x=159, screen y=143) rather than 7 pixels past it.

**Architecture:** Two constants in `src/player.c` are wrong. Fix the constants, then update the two tests in `tests/test_player.c` that assert the old (wrong) boundary values. TDD order: update tests first (they go red), fix constants (they go green).

**Tech Stack:** C, GBDK-2020, Unity (test framework), `make test` (gcc host build)

---

### Task 1: Update right-boundary test to expect correct value

**Files:**
- Modify: `tests/test_player.c:58-62`

**Step 1: Edit the test**

In `tests/test_player.c`, replace:

```c
void test_player_update_clamps_at_right_boundary(void) {
    player_set_pos(167, 72);
    player_update(J_RIGHT);
    TEST_ASSERT_EQUAL_UINT8(167, player_get_x());
}
```

with:

```c
void test_player_update_clamps_at_right_boundary(void) {
    player_set_pos(160, 72);
    player_update(J_RIGHT);
    TEST_ASSERT_EQUAL_UINT8(160, player_get_x());
}
```

**Step 2: Run tests to verify this test now fails**

```bash
make test
```

Expected: `test_player_update_clamps_at_right_boundary` FAIL (player can move past 160 since PX_MAX is still 167).

---

### Task 2: Update bottom-boundary test to expect correct value

**Files:**
- Modify: `tests/test_player.c:70-74`

**Step 1: Edit the test**

In `tests/test_player.c`, replace:

```c
void test_player_update_clamps_at_bottom_boundary(void) {
    player_set_pos(80, 159);
    player_update(J_DOWN);
    TEST_ASSERT_EQUAL_UINT8(159, player_get_y());
}
```

with:

```c
void test_player_update_clamps_at_bottom_boundary(void) {
    player_set_pos(80, 152);
    player_update(J_DOWN);
    TEST_ASSERT_EQUAL_UINT8(152, player_get_y());
}
```

**Step 2: Run tests to verify this test also fails**

```bash
make test
```

Expected: both `test_player_update_clamps_at_right_boundary` and `test_player_update_clamps_at_bottom_boundary` FAIL.

**Step 3: Commit the failing tests**

```bash
git add tests/test_player.c
git commit -m "test: update right/bottom boundary tests to use correct sprite-edge values"
```

---

### Task 3: Fix PX_MAX and PY_MAX constants

**Files:**
- Modify: `src/player.c:17-20`

**Step 1: Edit the constants**

In `src/player.c`, replace:

```c
#define PX_MAX  167u
```
```c
#define PY_MAX  159u
```

with:

```c
#define PX_MAX  160u  /* sprite right edge at screen x=159: (160-8)+7=159 */
```
```c
#define PY_MAX  152u  /* sprite bottom edge at screen y=143: (152-16)+7=143 */
```

**Step 2: Run tests to verify all pass**

```bash
make test
```

Expected: all tests PASS.

**Step 3: Build ROM to verify no compiler errors**

Use `/build` skill or:

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```

Expected: `build/wasteland-racer.gb` produced with no errors.

**Step 4: Commit**

```bash
git add src/player.c
git commit -m "fix: clamp player right/bottom boundary at sprite edge, not upper-left pixel"
```
