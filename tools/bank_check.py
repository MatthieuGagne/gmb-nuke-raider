#!/usr/bin/env python3
"""
bank_check.py — validates #pragma bank in src/*.c against bank-manifest.json.
Exits 0 on success, 1 if any mismatches found.

Usage:
    python3 tools/bank_check.py [repo_root]
    or imported as a module: bank_check.check(repo_root) -> list[str]
"""
import glob
import json
import os
import sys


def check(repo_root='.'):
    """Return list of error strings. Empty list means all clear."""
    manifest_path = os.path.join(repo_root, 'bank-manifest.json')
    with open(manifest_path) as f:
        manifest = json.load(f)

    errors = []
    src_files = glob.glob(os.path.join(repo_root, 'src', '*.c'))

    for abs_path in sorted(src_files):
        rel_path = 'src/' + os.path.basename(abs_path)
        if rel_path not in manifest:
            errors.append(
                f"ERROR: {rel_path} is not in bank-manifest.json — "
                f"add an entry before writing this file"
            )
            continue

        expected_bank = manifest[rel_path]['bank']

        with open(abs_path) as f:
            first_lines = [f.readline().rstrip() for _ in range(5)]

        pragma_lines = [l for l in first_lines if l.startswith('#pragma bank')]

        if expected_bank == 0:
            # Bank-0 files must NOT have #pragma bank
            if pragma_lines:
                errors.append(
                    f"ERROR: {rel_path} has '{pragma_lines[0]}' but manifest says bank 0 "
                    f"(bank-0 files must omit #pragma bank entirely)"
                )
        else:
            expected_pragma = f'#pragma bank {expected_bank}'
            if not any(l == expected_pragma for l in pragma_lines):
                found = pragma_lines[0] if pragma_lines else '(none in first 5 lines)'
                errors.append(
                    f"ERROR: {rel_path} pragma mismatch — "
                    f"manifest expects '{expected_pragma}', found: {found}"
                )

            # Check 2b: no SET_BANK/SWITCH_ROM in banked files
            with open(abs_path) as f:
                content = f.read()
            if 'SET_BANK' in content or 'SWITCH_ROM' in content:
                errors.append(
                    f"ERROR: {rel_path} contains SET_BANK or SWITCH_ROM but is not bank 0 "
                    f"(bank {expected_bank}). Only bank-0 files may call these. "
                    f"Move to loader.c or another bank-0 wrapper."
                )

    return errors


def main():
    repo_root = sys.argv[1] if len(sys.argv) > 1 else '.'
    errors = check(repo_root)
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        sys.exit(1)
    src_count = len(glob.glob(os.path.join(repo_root, 'src', '*.c')))
    print(f"bank_check: all {src_count} src/*.c files match manifest")
    sys.exit(0)


if __name__ == '__main__':
    main()
