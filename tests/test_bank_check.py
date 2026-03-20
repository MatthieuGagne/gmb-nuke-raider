"""Tests for tools/bank_check.py"""
import json
import os
import sys
import tempfile
import unittest

# Allow importing from tools/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import bank_check


class TestBankCheck(unittest.TestCase):

    def _write_manifest(self, d, entries):
        path = os.path.join(d, 'bank-manifest.json')
        with open(path, 'w') as f:
            json.dump(entries, f)
        return path

    def _write_c(self, d, name, lines):
        path = os.path.join(d, 'src', name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write('\n'.join(lines) + '\n')
        return path

    # ── Happy path ────────────────────────────────────────────────────────────

    def test_bank255_pragma_matches(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = {'src/foo.c': {'bank': 255, 'reason': 'autobank'}}
            self._write_manifest(d, manifest)
            self._write_c(d, 'foo.c', ['#pragma bank 255', '#include <gb/gb.h>'])
            errors = bank_check.check(d)
        self.assertEqual(errors, [])

    def test_bank1_pragma_matches(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = {'src/state_manager.c': {'bank': 1, 'reason': 'pinned'}}
            self._write_manifest(d, manifest)
            self._write_c(d, 'state_manager.c', ['#pragma bank 1', '#include <gb/gb.h>'])
            errors = bank_check.check(d)
        self.assertEqual(errors, [])

    def test_bank0_no_pragma(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = {'src/main.c': {'bank': 0, 'reason': 'HOME bank'}}
            self._write_manifest(d, manifest)
            self._write_c(d, 'main.c', ['#include <gb/gb.h>', 'void main() {}'])
            errors = bank_check.check(d)
        self.assertEqual(errors, [])

    # ── Error: wrong pragma ───────────────────────────────────────────────────

    def test_bank255_wrong_pragma(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = {'src/foo.c': {'bank': 255, 'reason': 'autobank'}}
            self._write_manifest(d, manifest)
            self._write_c(d, 'foo.c', ['#pragma bank 1', '#include <gb/gb.h>'])
            errors = bank_check.check(d)
        self.assertEqual(len(errors), 1)
        self.assertIn('foo.c', errors[0])
        self.assertIn('255', errors[0])

    def test_bank0_has_pragma(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = {'src/main.c': {'bank': 0, 'reason': 'HOME bank'}}
            self._write_manifest(d, manifest)
            self._write_c(d, 'main.c', ['#pragma bank 255', '#include <gb/gb.h>'])
            errors = bank_check.check(d)
        self.assertEqual(len(errors), 1)
        self.assertIn('main.c', errors[0])

    # ── Error: file not in manifest ────────────────────────────────────────────

    def test_file_missing_from_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = {}
            self._write_manifest(d, manifest)
            self._write_c(d, 'new_module.c', ['#pragma bank 255'])
            errors = bank_check.check(d)
        self.assertEqual(len(errors), 1)
        self.assertIn('new_module.c', errors[0])
        self.assertIn('manifest', errors[0].lower())

    # ── SET_BANK/SWITCH_ROM in banked files ───────────────────────────────────

    def test_set_bank_in_banked_file_is_error(self):
        """A #pragma bank 255 file containing SET_BANK is an error."""
        with tempfile.TemporaryDirectory() as d:
            manifest = {'src/foo.c': {'bank': 255, 'reason': 'autobank'}}
            self._write_manifest(d, manifest)
            self._write_c(d, 'foo.c', [
                '#pragma bank 255',
                '#include "banking.h"',
                'void foo(void) BANKED {',
                '    SET_BANK(bar_data);',
                '    use(bar_data);',
                '    RESTORE_BANK();',
                '}',
            ])
            errors = bank_check.check(d)
        self.assertEqual(len(errors), 1)
        self.assertIn('SET_BANK', errors[0])
        self.assertIn('foo.c', errors[0])

    def test_switch_rom_in_banked_file_is_error(self):
        """A #pragma bank 255 file containing SWITCH_ROM is an error."""
        with tempfile.TemporaryDirectory() as d:
            manifest = {'src/foo.c': {'bank': 255, 'reason': 'autobank'}}
            self._write_manifest(d, manifest)
            self._write_c(d, 'foo.c', [
                '#pragma bank 255',
                'void foo(void) BANKED {',
                '    SWITCH_ROM(2);',
                '}',
            ])
            errors = bank_check.check(d)
        self.assertEqual(len(errors), 1)
        self.assertIn('SWITCH_ROM', errors[0])

    def test_set_bank_in_bank0_file_is_ok(self):
        """A bank-0 file may freely call SET_BANK."""
        with tempfile.TemporaryDirectory() as d:
            manifest = {'src/loader.c': {'bank': 0, 'reason': 'HOME bank'}}
            self._write_manifest(d, manifest)
            self._write_c(d, 'loader.c', [
                '/* no pragma */',
                'void load_tiles(void) {',
                '    SET_BANK(tile_data);',
                '    set_bkg_data(0, 10, tile_data);',
                '    RESTORE_BANK();',
                '}',
            ])
            errors = bank_check.check(d)
        self.assertEqual(errors, [])

    # ── Edge cases ────────────────────────────────────────────────────────────

    def test_pragma_on_line_2_still_found(self):
        """Pragma may appear on line 2 (after a comment)."""
        with tempfile.TemporaryDirectory() as d:
            manifest = {'src/foo.c': {'bank': 255, 'reason': 'autobank'}}
            self._write_manifest(d, manifest)
            self._write_c(d, 'foo.c', ['/* comment */', '#pragma bank 255', '#include <gb/gb.h>'])
            errors = bank_check.check(d)
        self.assertEqual(errors, [])

    def test_empty_src_dir_no_errors(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = {}
            self._write_manifest(d, manifest)
            os.makedirs(os.path.join(d, 'src'))
            errors = bank_check.check(d)
        self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()
