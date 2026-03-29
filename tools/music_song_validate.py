#!/usr/bin/env python3
"""
music_song_validate.py — validates a hUGETracker GBDK .c export.

Checks:
  1. File has '#pragma bank 255'
  2. File has 'BANKREF(name)'
  3. 'const hUGESong_t name = ...' variable name matches BANKREF name

Usage:
    python3 tools/music_song_validate.py <song.c>

Exits 0 on valid export, non-zero with error message on failure.
"""
import re
import sys


def validate(path):
    with open(path) as f:
        content = f.read()

    errors = []

    # Check 1: #pragma bank 255
    if '#pragma bank 255' not in content:
        errors.append("ERROR: missing '#pragma bank 255' — add it to the top of the file")

    # Check 2: BANKREF(name)
    bankref_match = re.search(r'\bBANKREF\((\w+)\)', content)
    if not bankref_match:
        errors.append("ERROR: missing 'BANKREF(name)' — add 'BANKREF(your_song_name)' to the top")
        for e in errors:
            print(e, file=sys.stderr)
        return False

    bankref_name = bankref_match.group(1)

    # Check 3: const hUGESong_t name matches BANKREF name
    song_match = re.search(r'\bconst\s+hUGESong_t\s+(\w+)\s*=', content)
    if not song_match:
        errors.append("ERROR: no 'const hUGESong_t <name> = ...' declaration found")
    else:
        song_name = song_match.group(1)
        if song_name != bankref_name:
            errors.append(
                f"ERROR: variable name mismatch — BANKREF uses '{bankref_name}' "
                f"but hUGESong_t variable is '{song_name}' — they must match"
            )

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return False

    print(f"OK: {path} — BANKREF({bankref_name}), #pragma bank 255, hUGESong_t {bankref_name}")
    return True


def main():
    if len(sys.argv) != 2:
        print("Usage: music_song_validate.py <song.c>", file=sys.stderr)
        sys.exit(1)
    if not validate(sys.argv[1]):
        sys.exit(1)


if __name__ == '__main__':
    main()
