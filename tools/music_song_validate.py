#!/usr/bin/env python3
"""
music_song_validate.py — validates a hUGETracker .c export before adding it to the project.
Exits 0 on success, 1 if any check fails.

Usage:
    python3 tools/music_song_validate.py <song.c> [repo_root]
    or imported as a module: music_song_validate.validate(file_path) -> list[str]

Checks:
    1. Any '#pragma bank N' must appear in first 5 lines
    2. 'BANKREF(varname)' must be present — extracts varname
    3. 'const hUGESong_t varname' must appear and varname must match BANKREF name
"""
import re
import sys


def validate(file_path):
    """Return list of error strings. Empty list means all clear."""
    try:
        with open(file_path) as f:
            content = f.read()
    except OSError as e:
        return [f"ERROR: cannot open '{file_path}': {e}"]

    errors = []

    lines = content.splitlines()
    first_lines = lines[:5]

    # Check 1: any #pragma bank N in first 5 lines
    pragma_lines = [l for l in first_lines if re.match(r'#pragma bank \d+', l.strip())]
    if not pragma_lines:
        errors.append(
            f"ERROR: {file_path} missing '#pragma bank N' in first 5 lines "
            f"(hUGETracker exports use 255; adapted files use the assigned bank number)"
        )

    # Check 2: BANKREF(name)
    bankref_match = re.search(r'\bBANKREF\((\w+)\)', content)
    if not bankref_match:
        errors.append("ERROR: missing 'BANKREF(name)' — add 'BANKREF(your_song_name)' to the top")
        return errors

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

    return errors


def main():
    if len(sys.argv) != 2:
        print("Usage: music_song_validate.py <song.c>", file=sys.stderr)
        sys.exit(1)
    errors = validate(sys.argv[1])
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)
    print(f"OK: {sys.argv[1]} — validated successfully")
    sys.exit(0)


if __name__ == '__main__':
    main()
