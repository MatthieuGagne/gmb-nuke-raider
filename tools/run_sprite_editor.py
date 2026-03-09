#!/usr/bin/env python3
import sys
import os

# Ensure repo root is on the path so `tools.sprite_editor` is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.sprite_editor.main import run

if __name__ == '__main__':
    run()
