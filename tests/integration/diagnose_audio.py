#!/usr/bin/env python3
"""diagnose_audio.py — detect music_tick() double-ticks on the title screen.

Usage:
    make build-debug          # compile ROM with DEBUG=1
    python3 tests/integration/diagnose_audio.py

Hypothesis being tested (H1):
    If music_tick() / hUGE_dosound() spans a VBlank boundary, the VBL ISR is
    deferred (interrupts are disabled inside __critical). When __critical exits,
    the ISR fires immediately, setting frame_ready=1. The main loop then calls
    music_tick() again in the same visible frame — a double-tick.

Expected result (no bug):    delta == 1 every frame for 300 frames.
Anomaly (H1 confirmed):      delta == 0 or delta >= 2 for one or more frames.
"""
import os
import sys

ROM_PATH = "build/nuke-raider.gb"
FRAMES   = 300   # ~5 seconds at 60 fps; title screen requires no input
DEBUG_TICK_ADDR = 0xDFC1  # must match config.h DEBUG_TICK_ADDR

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from tests.integration.helpers import GameSession


def main() -> None:
    if not os.path.exists(ROM_PATH):
        print(f"ERROR: ROM not found at {ROM_PATH}")
        print("Run:  make build-debug")
        sys.exit(1)

    print(f"Booting {ROM_PATH} headlessly for {FRAMES} frames...")
    anomalies: list[tuple[int, int]] = []  # (frame_number, delta)

    with GameSession.boot(ROM_PATH, headless=True) as session:
        prev_tick = session.read_wram(DEBUG_TICK_ADDR)

        for frame in range(1, FRAMES + 1):
            session.advance(1)
            curr_tick = session.read_wram(DEBUG_TICK_ADDR)
            delta = (curr_tick - prev_tick) & 0xFF  # handle uint8 wrap

            if delta != 1:
                anomalies.append((frame, delta))

            prev_tick = curr_tick

    print(f"\n=== Results: {FRAMES} frames on title screen ===")
    if not anomalies:
        print("PASS — music_tick() called exactly once per frame for all 300 frames.")
        print("H1 (double-tick) RULED OUT on title screen.")
    else:
        print(f"ANOMALIES DETECTED: {len(anomalies)} frame(s) with delta != 1")
        print(f"{'Frame':>8}  {'Delta':>6}  Interpretation")
        print("-" * 40)
        for fr, d in anomalies:
            if d == 0:
                interp = "SKIPPED (music_tick not called this frame)"
            elif d >= 2:
                interp = f"DOUBLE-TICK x{d} (called {d} times this frame)"
            else:
                interp = f"unexpected delta={d}"
            print(f"{fr:>8}  {d:>6}  {interp}")
        print("\nH1 CONFIRMED — music_tick() is being called != 1 times per frame.")
        print("Next step: inspect main loop timing around VBL boundary.")


if __name__ == "__main__":
    main()
