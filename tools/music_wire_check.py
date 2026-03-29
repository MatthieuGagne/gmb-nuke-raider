#!/usr/bin/env python3
"""
music_wire_check.py — validates mutual consistency of music_data.h, music.c,
and bank-manifest.json.
Exits 0 on success, 1 if any check fails.

Usage:
    python3 tools/music_wire_check.py [repo_root]
    or imported as a module: music_wire_check.check(repo_root) -> list[str]

Checks:
    1. src/music_data.h: BANKREF_EXTERN(name) and extern hUGESong_t name must match
    2. src/music.c: SET_BANK(name) and hUGE_init(&name) must match name from check 1
    3. bank-manifest.json: entry for src/music_data.c must exist, bank must not be 0
    4. src/music.c must NOT contain #pragma bank
"""
import json
import os
import re
import sys


def check(repo_root='.'):
    errors = []

    # --- Parse src/music_data.h ---
    h_path = os.path.join(repo_root, 'src', 'music_data.h')
    try:
        with open(h_path) as f:
            h_content = f.read()
    except OSError as e:
        errors.append(f"ERROR: cannot open '{h_path}': {e}")
        return errors

    bankref_extern_names = set(re.findall(r'\bBANKREF_EXTERN\((\w+)\)', h_content))
    extern_song_names = set(re.findall(r'\bextern\s+const\s+hUGESong_t\s+(\w+)', h_content))

    # Check 1: BANKREF_EXTERN and extern const hUGESong_t names must match
    for name in bankref_extern_names - extern_song_names:
        errors.append(
            f"ERROR: music_data.h has BANKREF_EXTERN({name}) "
            f"but no 'extern const hUGESong_t {name}'"
        )
    for name in extern_song_names - bankref_extern_names:
        errors.append(
            f"ERROR: music_data.h has 'extern const hUGESong_t {name}' "
            f"but no BANKREF_EXTERN({name})"
        )

    # --- Parse src/music.c ---
    c_path = os.path.join(repo_root, 'src', 'music.c')
    try:
        with open(c_path) as f:
            c_content = f.read()
    except OSError as e:
        errors.append(f"ERROR: cannot open '{c_path}': {e}")
        return errors

    # Check 2: each declared song name has SET_BANK(name) and hUGE_init(&name) in music.c
    set_bank_names = set(re.findall(r'\bSET_BANK\((\w+)\)', c_content))
    huge_init_names = set(re.findall(r'\bhUGE_init\(&(\w+)\)', c_content))

    for name in bankref_extern_names:
        if name not in set_bank_names:
            errors.append(
                f"ERROR: '{name}' is declared in music_data.h "
                f"but has no SET_BANK({name}) call in music.c"
            )
        if name not in huge_init_names:
            errors.append(
                f"ERROR: '{name}' is declared in music_data.h "
                f"but has no hUGE_init(&{name}) call in music.c"
            )

    # Check 4: music.c must NOT contain #pragma bank (as a directive, not in comments)
    if re.search(r'^\s*#pragma\s+bank', c_content, re.MULTILINE):
        errors.append(
            f"ERROR: {c_path} contains '#pragma bank' — "
            f"music.c must be in bank 0 (no pragma). "
            f"SET_BANK/SWITCH_ROM inside a banked file would remap instructions "
            f"out from under itself."
        )

    # --- Parse bank-manifest.json ---
    manifest_path = os.path.join(repo_root, 'bank-manifest.json')
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
    except OSError as e:
        errors.append(f"ERROR: cannot open '{manifest_path}': {e}")
        return errors

    # Check 3: bank-manifest.json must have an entry for src/music_data.c
    # and it must not be assigned to bank 0
    if 'src/music_data.c' not in manifest:
        errors.append(
            "ERROR: bank-manifest.json is missing an entry for 'src/music_data.c'"
        )
    elif manifest['src/music_data.c']['bank'] == 0:
        errors.append(
            "ERROR: bank-manifest.json has 'src/music_data.c' assigned to bank 0 "
            "— music data must be in a non-zero bank"
        )

    return errors


def main():
    repo_root = sys.argv[1] if len(sys.argv) > 1 else '.'
    errors = check(repo_root)
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)
    print("music_wire_check: all consistent")
    sys.exit(0)


if __name__ == '__main__':
    main()
