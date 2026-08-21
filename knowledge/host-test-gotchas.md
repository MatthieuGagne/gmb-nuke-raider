---
summary: Host test suite gotchas — make test 30s timeout with 33+ binaries, never chain two make test runs, dangling loader_active_map_ptr after track_test_set_map, test ordering, cam_x/cam_y pinning, intermittent Windows Permission denied on fresh test binaries
tags: [testing, make-test, host-tests, windows, timeout, unity, gotcha]
---

# Host test gotchas

Hazards of the gcc host-test suite (`make test`, `tests/test_*.c`,
`tests/mocks/gb/gb.h`). Beam-specific test geometry lives in [[beam-laser-module]];
verification techniques in [[verification-techniques]].

## Suite runtime & timeouts

- **`make test` timeout 30 is too short for 33+ test binaries on this Windows
  machine.** The 30-second global timeout fires before all binaries are compiled. Run
  individual binaries directly (`./build/test_X`) to verify. The timeout is not a hang
  in `test_explosion` or any specific test — it is a build-time capacity issue on this
  host. All 33 test binaries pass when run individually.
- **Do not chain two `make test` runs in one PowerShell call** — the suite takes
  ~5 min, so two exceed even the 600 s tool timeout and the call gets backgrounded. Run
  the suite once, then invoke a single rebuilt binary directly (`./build/test_X.exe`)
  for a specific count.
- **Intermittent `Permission denied` executing a just-linked `build/test_X.exe` on
  Windows** (observed in #588 Task 6) — looked like antivirus/indexer holding a lock on
  the fresh binary, not a real test failure; a bare re-run of `make test` passed all
  binaries with no source changes. Don't diagnose this as a code regression; retry once
  before investigating further.

## The dangling-map-pointer trap (track_test_set_map)

`setUp` restores `active_map_w/h` but NEVER restores `loader_active_map_ptr`, so any
test that runs after a `track_test_set_map()` caller reads a dangling/stale map.

**`tests/test_player.c`: any test added AFTER the racer group reads a dangling map
pointer.** `test_player_blocked_by_racer` and its two siblings call
`track_test_set_map(s_road_12x8, 12u, 8u)`, and `setUp` restores `active_map_w/h` to
20/100 but NEVER restores `loader_active_map_ptr` — so a later test's
`track_passable()` indexes `ty*20+tx` (up to 1999) into a 96-byte array. A DIR_R beam
raycast from (64,64) then breaks immediately on garbage and the test fails for a reason
that has nothing to do with the code under test. Fix without touching the map: put the
new `RUN_TEST` lines ABOVE the racer group in `main()` (the default map is `track_map`,
20x100, road = cols 4-15, so (64,64) is road and a DIR_R lane along world row 9 stays
on road until col 16 = x128). Leave a comment at both the test bodies and the
`RUN_TEST` block saying why the order is load-bearing.

The same trap governs `tests/test_racer.c` (beam tests must go ABOVE every
`track_test_set_map()` caller) and is why `tests/test_camera.c` deliberately never
injects a map — details in [[beam-laser-module]] and [[camera-streaming]].
`tests/test_turret.c`'s `setUp` does NOT reset `cam_x`/`cam_y` and a neighbouring
visibility test leaves `cam_y = 100`, so pin both in the test body.

## `src/race_state.c` is predominantly LF, not CRLF

When bypassing broken Edit hooks with `[System.IO.File]::WriteAllText`, match the file's
existing dominant line ending — LF here, despite the repo being Windows-native. Forcing CRLF
makes the match string fail to be found and risks leaving mixed endings in the file.
