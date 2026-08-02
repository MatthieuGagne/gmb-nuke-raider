#!/usr/bin/env python3
"""
bank_post_build.py — post-build ROM bank validation.

Checks:
  1. romusage budget (bank 1 WARN >90% or >=100%; others WARN >80% or >=100%)
  2. state code must not appear beyond the ROM's real bank capacity
  3. __bank_ symbol values must match bank-manifest.json for pinned files
  4. highest bank in use must be < the ROM's real bank capacity

Exits 0 on PASS/WARN, 1 on FAIL.

Usage:
    python3 tools/bank_post_build.py [repo_root]
    or imported: bank_post_build.check(repo_root, romusage_output=None) -> dict
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys

BANK_STRIDE = 0x10000    # .noi addresses advance one bank per 0x10000

# Cartridge header (Pan Docs). 0x148 is the ROM-size code makebin writes from
# the auto-sized image; every code it emits maps to `2 << code` banks.
ROM_SIZE_OFFSET = 0x148
ROM_SIZE_CODE_MAX = 0x08
HEADER_MIN_LEN = 0x150


def _run_romusage(rom_path):
    """Run romusage -a and return stdout.

    The binary is resolved from PATH: ADR 443 forbids absolute machine paths
    in tracked files, and this function held one for long enough to make
    `make bank-post-build` unrunnable on the machine that ships it (#441).
    """
    exe = shutil.which('romusage')
    if exe is None:
        raise FileNotFoundError(
            'romusage not found on PATH — add your GBDK bin/ directory to '
            'PATH (GBDK ships bin/romusage).')
    result = subprocess.run(
        [exe, rom_path, '-a'], capture_output=True, text=True, check=False,
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


def _read_rom_capacity(rom_path):
    """Return the cartridge's real ROM bank count, or None if undeterminable.

    The bound comes from the built ROM, not the Makefile.  Two sources were
    available (#487 R1) and this is the one that answers the question actually
    being asked:

    * romusage's bank table lists only banks the linker put content in, so its
      maximum is a floor on *usage*.  It cannot report that a cartridge has 32
      banks while 4 are occupied — which is exactly the bound both capacity
      checks need.
    * Header byte 0x148 is what makebin writes from the auto-sized image
      (`-yo A`), and what the MBC and every emulator read to size the cart.  It
      is also readable when romusage cannot run — the state that hid #461.

    `-Wm-ya` is deliberately not consulted.  It is makebin's *RAM* bank count
    (`-ya n  number of ram banks`); ROM banks are auto-sized and never declared
    anywhere in this build.  The built header proves the flag is discarded:
    0x148=0x04 (32 banks) alongside 0x149=0x00 (no RAM banks) under -Wm-ya32.
    That `-Wm-ya32` and 32 ROM banks agree today is a coincidence, and the
    roadmap's `-Wm-ya1` SRAM save is the day it stops agreeing.

    Returns None — never a guessed default (#487 R3) — when the ROM is absent,
    truncated, or carries a size code this mapping does not cover.  Callers must
    defer on None, not substitute a bound.
    """
    try:
        with open(rom_path, 'rb') as fh:
            header = fh.read(HEADER_MIN_LEN)
    except OSError:
        return None
    if len(header) < HEADER_MIN_LEN:
        return None
    code = header[ROM_SIZE_OFFSET]
    if code > ROM_SIZE_CODE_MAX:
        return None      # incl. legacy 0x52/0x53/0x54, which makebin never emits
    return 2 << code


def _check_romusage(banks):
    """Return list of (bank_num, pct, status) for each bank."""
    results = []
    for bank_num, pct in banks:
        if pct >= 100:
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


def _check_state_symbols(symbols, capacity=None):
    """Return list of (sym, hex_addr) for _state_* symbols beyond ROM capacity.

    A state callback is safe in ANY bank the cartridge actually has: invoke() in
    state_manager.c dispatches through each State's .bank field, so the call site
    never assumes a bank.  The old rule stopped at bank 2, but that ceiling was
    never justified by this argument — it was a snapshot of where the linker
    happened to put things, and autobank legitimately spilled past it once banks
    0/1/2 reached 95/100/95% (ADR 461).

    What IS a real defect is a state callback beyond the ROM's actual bank
    capacity — a symbol whose address lands in a bank the cartridge does not
    have.  `capacity` is that bank count, read from the built ROM's cartridge
    header by _read_rom_capacity; see its docstring for why the header rather
    than -Wm-ya or the romusage table (#487).  None means capacity could not be
    determined, and the check defers rather than inventing a bound.

    The guard is `is None`, and _check_capacity and _format_report agree with
    it.  A falsy guard would also swallow capacity 0 — unreachable from this
    source, but a falsy guard here paired with an `is None` guard in the report
    is precisely what produced the "all within declared capacity (0 banks)"
    line on a path that had in fact deferred.

    When romusage output is available this overlaps _check_capacity, which
    catches the same overflow via the bank table.  It is retained because it is
    the only capacity signal when romusage cannot run — the state that hid this
    very bug until #441 made romusage resolvable on Windows.
    """
    if capacity is None:
        return []
    limit = capacity * BANK_STRIDE
    bad = []
    for sym, addr in symbols.items():
        if sym.startswith('_state_') and addr >= limit:
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


def _check_capacity(capacity, banks):
    """Return (highest_bank, status) for the banks romusage reported.

    A cartridge of N banks numbers them 0 to N-1, so bank N or higher is
    overflow.  `capacity` is None when it could not be determined, and the
    check reports SKIP rather than assuming one (#487 R3).
    """
    if capacity is None:
        return None, 'SKIP'
    if not banks:
        return 0, 'PASS'
    highest = max(b[0] for b in banks)
    status = 'FAIL' if highest >= capacity else 'PASS'
    return highest, status


def overall_status(result):
    """Return 'PASS', 'WARN', or 'FAIL' from a check() result dict."""
    if (result['bad_state_symbols']
            or result['bank_sym_errors']
            or result['capacity_status'] == 'FAIL'
            or any(r[2] == 'FAIL' for r in result['bank_results'])):
        return 'FAIL'
    if (result['capacity_status'] == 'WARN'
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
        capacity = result['rom_capacity']
        if capacity is None:
            lines.append("State symbols: OK — ROM capacity unknown "
                         "(cartridge header unreadable)")
        else:
            lines.append(
                f"State symbols: OK — all within ROM capacity "
                f"({capacity} banks)")

    if result['bank_sym_errors']:
        lines.append("__bank_ symbols: FAIL")
        for e in result['bank_sym_errors']:
            lines.append(f"  {e}")
    else:
        lines.append("__bank_ symbols: OK")

    if result['capacity_status'] == 'SKIP':
        lines.append("ROM capacity: SKIP (cartridge header unreadable — "
                     "no build/nuke-raider.gb, or an unmapped size code)")
    elif result['capacity_status'] == 'FAIL':
        lines.append(
            f"ROM capacity: FAIL — {result['rom_capacity']} banks "
            f"(cartridge header 0x148), highest bank in use is "
            f"{result['highest_bank']}"
        )
    else:
        lines.append(
            f"ROM capacity: OK — {result['rom_capacity']} banks "
            f"(cartridge header 0x148), highest bank in use "
            f"{result['highest_bank']}"
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
    manifest_path = os.path.join(repo_root, 'bank-manifest.json')
    src_dir = os.path.join(repo_root, 'src')

    if romusage_output is None:
        romusage_output = _run_romusage(rom_path)

    banks = _parse_romusage(romusage_output)
    bank_results = _check_romusage(banks)

    # One capacity read feeds both capacity-dependent checks (#487 R2) — the
    # two cannot disagree because there is only one source.
    capacity = _read_rom_capacity(rom_path)
    highest, capacity_status = _check_capacity(capacity, banks)

    symbols = _parse_noi(noi_path)
    bad_state = _check_state_symbols(symbols, capacity)

    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)
    bank_sym_errors = _check_bank_symbols(symbols, src_dir, manifest)

    return {
        'bank_results': bank_results,
        'bad_state_symbols': bad_state,
        'bank_sym_errors': bank_sym_errors,
        'rom_capacity': capacity,
        'highest_bank': highest,
        'capacity_status': capacity_status,
    }


def main():
    repo_root = sys.argv[1] if len(sys.argv) > 1 else '.'
    result = check(repo_root)
    print(_format_report(result))
    status = overall_status(result)
    sys.exit(0 if status in ('PASS', 'WARN') else 1)


if __name__ == '__main__':
    main()
