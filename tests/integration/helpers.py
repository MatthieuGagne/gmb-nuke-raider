"""GameSession — thin PyBoy wrapper for headless GB/GBC debugging."""
from __future__ import annotations

import os
from typing import Optional

from pyboy import PyBoy
from pyboy.utils import WindowEvent

# WRAM debug buffer layout — must match src/config.h DEBUG_* constants
DEBUG_LOG_ADDR = 0xDF80
DEBUG_LOG_SIZE = 64
DEBUG_LOG_IDX  = 0xDFC0
DEBUG_TICK_ADDR = 0xDFC1

_BUTTON_MAP = {
    "UP":     (WindowEvent.PRESS_ARROW_UP,    WindowEvent.RELEASE_ARROW_UP),
    "DOWN":   (WindowEvent.PRESS_ARROW_DOWN,  WindowEvent.RELEASE_ARROW_DOWN),
    "LEFT":   (WindowEvent.PRESS_ARROW_LEFT,  WindowEvent.RELEASE_ARROW_LEFT),
    "RIGHT":  (WindowEvent.PRESS_ARROW_RIGHT, WindowEvent.RELEASE_ARROW_RIGHT),
    "A":      (WindowEvent.PRESS_BUTTON_A,    WindowEvent.RELEASE_BUTTON_A),
    "B":      (WindowEvent.PRESS_BUTTON_B,    WindowEvent.RELEASE_BUTTON_B),
    "START":  (WindowEvent.PRESS_BUTTON_START,  WindowEvent.RELEASE_BUTTON_START),
    "SELECT": (WindowEvent.PRESS_BUTTON_SELECT, WindowEvent.RELEASE_BUTTON_SELECT),
}


class GameSession:
    """Headless Game Boy session backed by PyBoy."""

    def __init__(self, pyboy: PyBoy) -> None:
        self._pyboy = pyboy
        self._log_cursor = 0  # last-read position in ring buffer

    @staticmethod
    def boot(rom_path: str, headless: bool = True) -> "GameSession":
        """Boot the ROM. headless=True suppresses the SDL window."""
        if not os.path.exists(rom_path):
            raise FileNotFoundError(f"ROM not found: {rom_path}")
        window = "null" if headless else "SDL2"
        pyboy = PyBoy(rom_path, window=window)
        pyboy.set_emulation_speed(0)  # run as fast as possible
        return GameSession(pyboy)

    def advance(self, frames: int = 1) -> None:
        """Advance emulation by N frames without input."""
        for _ in range(frames):
            self._pyboy.tick()

    def press(self, buttons: list[str], hold_frames: int = 1) -> None:
        """Press one or more buttons for hold_frames frames, then release."""
        press_events   = [_BUTTON_MAP[b][0] for b in buttons]
        release_events = [_BUTTON_MAP[b][1] for b in buttons]
        for ev in press_events:
            self._pyboy.send_input(ev)
        self.advance(hold_frames)
        for ev in release_events:
            self._pyboy.send_input(ev)

    def read_wram(self, addr: int) -> int:
        """Read one byte from WRAM (0xC000–0xDFFF)."""
        if not (0xC000 <= addr <= 0xDFFF):
            raise ValueError(f"Address 0x{addr:04X} outside WRAM range")
        return self._pyboy.memory[addr]

    def read_debug_log(self) -> list[str]:
        """Drain unread bytes from the WRAM ring buffer; return as lines."""
        idx = self.read_wram(DEBUG_LOG_IDX)
        result = []
        buf = []
        pos = self._log_cursor
        while pos != idx:
            byte = self.read_wram(DEBUG_LOG_ADDR + (pos % DEBUG_LOG_SIZE))
            if byte == ord('\n'):
                if buf:
                    result.append("".join(chr(b) for b in buf))
                    buf = []
            else:
                buf.append(byte)
            pos = (pos + 1) % DEBUG_LOG_SIZE
        self._log_cursor = idx
        return result

    def screenshot(self, path: str) -> None:
        """Save current screen as PNG."""
        self._pyboy.screen.image.save(path)

    def close(self) -> None:
        self._pyboy.stop()

    def __enter__(self) -> "GameSession":
        return self

    def __exit__(self, *_) -> None:
        self.close()
