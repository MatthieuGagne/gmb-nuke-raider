"""conftest.py — shared pytest fixtures for integration tests."""
from __future__ import annotations

import os
import pytest
from tests.integration.helpers import GameSession

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ROM_PATH  = os.path.join(REPO_ROOT, "build", "nuke-raider.gb")
MAP_PATH  = os.path.join(REPO_ROOT, "build", "nuke-raider.map")


@pytest.fixture(scope="session")
def rom_path() -> str:
    if not os.path.exists(ROM_PATH):
        pytest.skip(f"Debug ROM not found: {ROM_PATH}. Run: make build-debug")
    return ROM_PATH


@pytest.fixture(scope="session")
def map_path() -> str:
    if not os.path.exists(MAP_PATH):
        pytest.skip(f"Map file not found: {MAP_PATH}. Run: make build-debug")
    return MAP_PATH


@pytest.fixture(scope="session")
def game_session(rom_path):
    """Boot the debug ROM once for the entire test session."""
    session = GameSession.boot(rom_path, headless=True)
    yield session
    session.close()
