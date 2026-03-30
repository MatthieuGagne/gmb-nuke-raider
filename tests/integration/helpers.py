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

    def write_wram(self, addr: int, value: int) -> None:
        """Write one byte to WRAM (0xC000–0xDFFF)."""
        if not (0xC000 <= addr <= 0xDFFF):
            raise ValueError(f"Address 0x{addr:04X} outside WRAM range")
        self._pyboy.memory[addr] = value & 0xFF

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


def find_wram_read_in_fn(noi_path: str, rom_path: str, fn_symbol: str) -> int:
    """Find the WRAM address read by a function, via ROM disassembly.

    Parses the .noi debug-symbol file for fn_symbol's address, converts to a
    physical ROM byte offset, then scans for 'LD A,(nn)' (opcode 0xFA) to
    extract the WRAM address.

    Useful for locating WRAM addresses of *static* file-scope variables, which
    SDCC does not export to the .map symbol table.  Requires a debug ROM built
    with `make build-debug` (produces both .gb and .noi).
    """
    import re

    pattern = re.compile(r'DEF\s+' + re.escape(fn_symbol) + r'\s+0x([0-9A-Fa-f]+)')
    try:
        with open(noi_path) as f:
            content = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"NOI file not found: {noi_path}. Run: make build-debug")

    m = pattern.search(content)
    if not m:
        raise KeyError(f"Symbol '{fn_symbol}' not found in {noi_path}")

    noi_addr = int(m.group(1), 16)

    # .noi address encoding: high 16 bits = bank number, low 16 bits = GB window
    # address (0x4000–0x7FFF for banked banks).
    # Physical ROM byte offset:
    #   bank 0 → phys = gb_addr
    #   bank N → phys = (N - 1) * 0x4000 + gb_addr
    bank_num   = noi_addr >> 16
    gb_addr    = noi_addr & 0xFFFF
    phys_offset = gb_addr if bank_num == 0 else (bank_num - 1) * 0x4000 + gb_addr

    with open(rom_path, 'rb') as f:
        f.seek(phys_offset)
        fn_bytes = f.read(32)

    for i in range(len(fn_bytes) - 2):
        if fn_bytes[i] == 0xFA:          # LD A, (nn) — absolute WRAM load
            addr = fn_bytes[i + 1] | (fn_bytes[i + 2] << 8)
            if 0xC000 <= addr <= 0xDFFF:
                return addr

    raise KeyError(
        f"No 'LD A,(WRAM)' found in first 32 bytes of '{fn_symbol}' "
        f"(ROM offset 0x{phys_offset:X})"
    )


def find_wram_sym_from_map(map_path: str, symbol: str) -> int:
    """Parse build/nuke-raider.map for a WRAM symbol address.

    SDCC emits static file-scope variables only in the .map file (not .noi).
    Filters to WRAM range 0xC000–0xDFFF to avoid false matches.
    Raises KeyError if symbol not found.
    """
    import re
    pattern = re.compile(r'([0-9A-Fa-f]{4,8})\s+' + re.escape(symbol) + r'\b')
    try:
        with open(map_path) as f:
            content = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"Map file not found: {map_path}. Run: make build-debug")
    for m in pattern.finditer(content):
        addr = int(m.group(1), 16)
        if 0xC000 <= addr <= 0xDFFF:
            return addr
    raise KeyError(f"Symbol '{symbol}' not found in WRAM range in {map_path}")
