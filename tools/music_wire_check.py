#!/usr/bin/env python3
"""
music_wire_check.py — validates music_data.h, music.c, and bank-manifest.json
are mutually consistent.

Checks:
  1. Every BANKREF_EXTERN(name) in src/music_data.h has a matching
     'extern const hUGESong_t name' in the same file
  2. Every name declared in src/music_data.h appears as BANK(name)
     in src/music.c
  3. src/bank-manifest.json has an entry for 'src/music_data.c'

Usage:
    python3 tools/music_wire_check.py [repo_root]

Exits 0 when consistent, non-zero with clear error on any mismatch.
"""
import json
import os
import re
import sys


def check(repo_root='.'):
    errors = []

    # --- Parse src/music_data.h ---
    h_path = os.path.join(repo_root, 'src', 'music_data.h')
    with open(h_path) as f:
        h_content = f.read()

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
    with open(c_path) as f:
        c_content = f.read()

    bank_names = set(re.findall(r'\bBANK\((\w+)\)', c_content))

    # Check 2: each declared song name has a BANK(name) reference in music.c
    for name in bankref_extern_names:
        if name not in bank_names:
            errors.append(
                f"ERROR: '{name}' is declared in music_data.h "
                f"but has no BANK({name}) call in music.c"
            )

    # --- Parse bank-manifest.json ---
    manifest_path = os.path.join(repo_root, 'bank-manifest.json')
    with open(manifest_path) as f:
        manifest = json.load(f)

    # Check 3: bank-manifest.json must have an entry for src/music_data.c
    if 'src/music_data.c' not in manifest:
        errors.append(
            "ERROR: bank-manifest.json is missing an entry for 'src/music_data.c'"
        )

    return errors


def main():
    repo_root = sys.argv[1] if len(sys.argv) > 1 else '.'
    errors = check(repo_root)
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)
    print("OK: music_data.h, music.c, and bank-manifest.json are consistent")


if __name__ == '__main__':
    main()
