# Test-harness-only gotchas (gbdk-expert agent)

One line each (symptom → fix). These bite only in the GCC host-test harness (`make test`), not
on real hardware or a ROM build.

- **`static` header fn dereferencing raw WRAM addr segfaults on GCC host tests.** `(volatile uint8_t*)0xDF80` is fine on GBC, crashes on Linux. Wrap fixed-addr writes: `#ifdef __SDCC` real write / `#else` no-op stub.
- **New GBDK API call in `src/` not mocked** → `make test` "undefined reference". Before committing, grep `tests/mocks/gb/gb.h` for the fn and add a no-op stub if missing.
- **`loader_load_state()` in `enter()` + test calls `enter()` twice → infinite hang** (double-load asserts `disable_interrupts(); while(1){}`). Grep the test for `enter()` calls outside setUp and prepend `state_X.exit(); loader_reset_bitmap_for_test();`. Run `make test` with `timeout 30` so a hang surfaces as a failure.
- **Hardware register mock declared `static` in header** → each TU gets its own copy (`sfx.c` writes its `NR44_REG`, test reads its own =0). Any register observed from a test must be `extern uint8_t` in the header, defined in `tests/mocks/hardware_regs.c`.
