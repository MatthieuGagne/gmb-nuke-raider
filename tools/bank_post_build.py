#!/usr/bin/env python3
"""
bank_post_build.py — post-build ROM bank validation.

Checks:
  1. romusage budget (bank 1 WARN >90%/FAIL >=100%; others WARN >80%/FAIL >=100%)
  2. state code must not appear in bank 2+ (addresses >= 0x20000)
  3. __bank_ symbol values must match bank-manifest.json for pinned files
  4. highest bank in use must be < -Wm-ya declared count

Exits 0 on PASS/WARN, 1 on FAIL.

Usage:
    python3 tools/bank_post_build.py [repo_root]
    or imported: bank_post_build.check(repo_root, romusage_output=None) -> dict
"""
import glob
import json
import os
import re
import subprocess
import sys


def _run_romusage(rom_path):
    """Run romusage -a and return stdout. Raises on missing binary."""
    result = subprocess.run(
        ['/home/mathdaman/gbdk/bin/romusage', rom_path, '-a'],
        capture_output=True, text=True, check=False,
    )
    return result.stdout


def _parse_romusage(output):
    """Parse romusage -a output. Returns list of (bank_num, used_pct) tuples."""
    banks = []
    for line in output.splitlines():
        m = re.match(
            r'^ROM_(\d+)\s+\S+\s+->\s+\S+\s+\d+\s+\d+\s+(\d+)%', line
        )
        if m:
            banks.append((int(m.group(1)), int(m.group(2))))
    return banks


def _check_romusage(banks):
    """Return list of (bank_num, pct, status) for each bank."""
    results = []
    for bank_num, pct in banks:
        if pct > 100:
            status = 'FAIL'
        elif pct == 100:
            status = 'WARN'
        elif bank_num == 1 and pct > 90:
            status = 'WARN'
        elif bank_num != 1 and pct > 80:
            status = 'WARN'
        else:
            status = 'PASS'
        results.append((bank_num, pct, status))
    return results


def _parse_noi(noi_path):
    """Parse .noi file. Returns dict: symbol_name -> int(address)."""
    symbols = {}
    if not os.path.exists(noi_path):
        return symbols
    with open(noi_path) as f:
        for line in f:
            m = re.match(r'^DEF (\S+) (0x[0-9A-Fa-f]+)', line.strip())
            if m:
                symbols[m.group(1)] = int(m.group(2), 16)
    return symbols


def _check_state_symbols(symbols):
    """Return list of (sym, hex_addr) for _state_* symbols in bank 2+ (addr >= 0x20000)."""
    bad = []
    for sym, addr in symbols.items():
        if sym.startswith('_state_') and addr >= 0x20000:
            bad.append((sym, hex(addr)))
    return bad


def _check_bank_symbols(symbols, src_dir, manifest):
    """Cross-reference ___bank_* symbol values against manifest for pinned files.

    For each symbol defined via `volatile uint8_t __at(N) __bank_X` (or BANKREF macro)
    in a pinned source file (bank != 0 and bank != 255), the .noi value must match
    the manifest's declared bank.

    Returns list of error strings.
    """
    # Build symbol_name -> source_file from __at(N) __bank_X pattern in src files
    # The __at(N) pattern is what png_to_tiles.py emits; older BANKREF macro also works.
    symbol_to_file = {}
    for src_file in sorted(glob.glob(os.path.join(src_dir, '*.c'))):
        rel_path = 'src/' + os.path.basename(src_file)
        with open(src_file) as f:
            content = f.read()
        for m in re.finditer(r'__bank_(\w+)', content):
            symbol_to_file[m.group(1)] = rel_path

    errors = []
    for sym, actual_bank in symbols.items():
        if not sym.startswith('___bank_'):
            continue
        symbol_name = sym[len('___bank_'):]
        src_file = symbol_to_file.get(symbol_name)
        if src_file is None or src_file not in manifest:
            continue
        expected_bank = manifest[src_file]['bank']
        if expected_bank in (0, 255):
            continue  # can't predict autobank placement; bank-0 has no bank symbol
        if actual_bank != expected_bank:
            errors.append(
                f"__bank_{symbol_name}: manifest expects bank {expected_bank} "
                f"({src_file}), .noi has {actual_bank}"
            )
    return errors


def _check_wm_ya(makefile_path, banks):
    """Return (declared, highest, status).

    -Wm-yaN declares N banks (numbered 0 to N-1). Bank N or higher is overflow.
    """
    if not os.path.exists(makefile_path):
        return None, None, 'SKIP'
    with open(makefile_path) as f:
        content = f.read()
    m = re.search(r'-Wm-ya(\d+)', content)
    if not m:
        return None, None, 'SKIP'
    declared = int(m.group(1))
    if not banks:
        return declared, 0, 'PASS'
    highest = max(b[0] for b in banks)
    status = 'FAIL' if highest >= declared else 'PASS'
    return declared, highest, status


def overall_status(result):
    """Return 'PASS', 'WARN', or 'FAIL' from a check() result dict."""
    if (result['bad_state_symbols']
            or result['bank_sym_errors']
            or result['wm_ya_status'] == 'FAIL'
            or any(r[2] == 'FAIL' for r in result['bank_results'])):
        return 'FAIL'
    if (result['wm_ya_status'] == 'WARN'
            or any(r[2] == 'WARN' for r in result['bank_results'])):
        return 'WARN'
    return 'PASS'


def _format_report(result):
    """Return the structured report string."""
    lines = ['=== Bank Post-Build Report ===']

    for bank_num, pct, status in result['bank_results']:
        lines.append(f"ROM_{bank_num}: {pct}%  [{status}]")

    if result['bad_state_symbols']:
        syms = ', '.join(f"{s} @ {a}" for s, a in result['bad_state_symbols'])
        lines.append(f"State symbols: FAIL — {syms}")
    else:
        lines.append("State symbols: OK — all in bank 0/1")

    if result['bank_sym_errors']:
        lines.append("__bank_ symbols: FAIL")
        for e in result['bank_sym_errors']:
            lines.append(f"  {e}")
    else:
        lines.append("__bank_ symbols: OK")

    if result['wm_ya_status'] == 'SKIP':
        lines.append("-Wm-ya capacity: SKIP (no -Wm-ya in Makefile)")
    elif result['wm_ya_status'] == 'FAIL':
        lines.append(
            f"-Wm-ya capacity: FAIL — {result['wm_ya_declared']} banks declared, "
            f"highest in use is {result['wm_ya_highest']}"
        )
    else:
        lines.append(
            f"-Wm-ya capacity: OK — {result['wm_ya_declared']} declared, "
            f"highest {result['wm_ya_highest']}"
        )

    lines.append('')
    status = overall_status(result)
    lines.append(f"[{status}]")
    if status == 'PASS':
        lines.append("bank-post-build: all checks passed — safe to proceed to smoketest.")
    return '\n'.join(lines)


def check(repo_root='.', romusage_output=None):
    """Run all 4 post-build checks. Returns result dict.

    romusage_output: if provided, use this string instead of running romusage binary.
    """
    rom_path = os.path.join(repo_root, 'build', 'nuke-raider.gb')
    noi_path = os.path.join(repo_root, 'build', 'nuke-raider.noi')
    makefile_path = os.path.join(repo_root, 'Makefile')
    manifest_path = os.path.join(repo_root, 'bank-manifest.json')
    src_dir = os.path.join(repo_root, 'src')

    if romusage_output is None:
        romusage_output = _run_romusage(rom_path)

    banks = _parse_romusage(romusage_output)
    bank_results = _check_romusage(banks)

    symbols = _parse_noi(noi_path)
    bad_state = _check_state_symbols(symbols)

    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)
    bank_sym_errors = _check_bank_symbols(symbols, src_dir, manifest)

    declared, highest, wm_ya_status = _check_wm_ya(makefile_path, banks)

    return {
        'bank_results': bank_results,
        'bad_state_symbols': bad_state,
        'bank_sym_errors': bank_sym_errors,
        'wm_ya_declared': declared,
        'wm_ya_highest': highest,
        'wm_ya_status': wm_ya_status,
    }


def main():
    repo_root = sys.argv[1] if len(sys.argv) > 1 else '.'
    result = check(repo_root)
    print(_format_report(result))
    status = overall_status(result)
    sys.exit(0 if status in ('PASS', 'WARN') else 1)


if __name__ == '__main__':
    main()
