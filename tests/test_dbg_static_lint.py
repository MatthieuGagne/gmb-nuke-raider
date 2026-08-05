"""Tests for tools/dbg_static_lint.py (#588 R7, AC6)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import dbg_static_lint

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _violations(source):
    """Run the lint over one synthetic translation unit."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'probe.c')
        with open(path, 'w') as f:
            f.write(source)
        return dbg_static_lint.check_file(path)


class TestFlagged(unittest.TestCase):
    def test_plain_mutable_declaration(self):
        self.assertEqual(len(_violations('static uint8_t foo;\n')), 1)

    def test_array_declaration(self):
        self.assertEqual(len(_violations('static uint8_t buf[8];\n')), 1)

    def test_array_with_initialiser(self):
        self.assertEqual(len(_violations('static uint8_t t[2] = {1, 2};\n')), 1)

    def test_volatile_declaration(self):
        self.assertEqual(
            len(_violations('static volatile uint8_t owed = 0u;\n')), 1)

    def test_multi_declarator_line_is_one_violation(self):
        self.assertEqual(len(_violations('static int16_t a, b;\n')), 1)

    def test_mutable_pointer_to_const_data(self):
        self.assertEqual(
            len(_violations('static const uint8_t *p = 0;\n')), 1)

    def test_comment_holding_parentheses_is_not_a_function(self):
        src = 'static uint8_t n; /* seeded by init() at race start (#424) */\n'
        self.assertEqual(len(_violations(src)), 1)

    def test_message_names_the_file_the_line_and_the_identifier(self):
        msgs = _violations('\n\nstatic uint8_t ld_weapon1;\n')
        self.assertEqual(len(msgs), 1)
        self.assertIn('probe.c', msgs[0])
        self.assertIn(':3', msgs[0])
        self.assertIn('ld_weapon1', msgs[0])

    def test_line_number_skips_preprocessor_lines_in_the_same_chunk(self):
        """The real shape of every src/*.c file: includes, then declarations.

        A chunk starts after the previous `;` or `}`, so it carries every
        `#include` and `#define` above the declaration. Numbering from the
        chunk's first non-space character reports the `#` line instead, which
        sends an executor to edit a `#define`.
        """
        msgs = _violations('#include <gb/gb.h>\n#define K 3\nstatic uint8_t foo;\n')
        self.assertEqual(len(msgs), 1)
        self.assertIn(':3', msgs[0])

    def test_line_number_is_right_at_the_top_of_a_file(self):
        msgs = _violations('#include "a.h"\n#include "b.h"\n\nstatic uint8_t v;\n')
        self.assertEqual(len(msgs), 1)
        self.assertIn(':4', msgs[0])


class TestAccepted(unittest.TestCase):
    def test_dbg_static_declaration(self):
        self.assertEqual(_violations('DBG_STATIC uint8_t foo;\n'), [])

    def test_static_const_array(self):
        self.assertEqual(
            _violations('static const uint8_t T[] = {1, 2, 3};\n'), [])

    def test_static_const_pointer_to_const(self):
        self.assertEqual(
            _violations('static const char* const names[] = {"a"};\n'), [])

    def test_static_function_definition(self):
        self.assertEqual(
            _violations('static uint8_t f(uint8_t x) { return x; }\n'), [])

    def test_static_function_declaration(self):
        self.assertEqual(_violations('static uint8_t f(uint8_t x);\n'), [])

    def test_function_local_static(self):
        src = 'void g(void) {\n    static uint8_t x;\n    x++;\n}\n'
        self.assertEqual(_violations(src), [])

    def test_preprocessor_split_function_qualifier(self):
        """The src/race_state.c shape: `static` alone on a line inside #else."""
        src = ('#ifndef __SDCC\n'
               'uint8_t\n'
               '#else\n'
               'static uint8_t\n'
               '#endif\n'
               'pos_from_dir(uint8_t dir) {\n'
               '    return dir;\n'
               '}\n')
        self.assertEqual(_violations(src), [])

    def test_the_word_static_inside_a_comment(self):
        self.assertEqual(
            _violations('/* large arrays must be static, never local */\n'), [])

    def test_the_word_static_inside_a_string(self):
        self.assertEqual(
            _violations('const char *m = "static";\n'), [])

    def test_non_static_global(self):
        self.assertEqual(_violations('uint8_t racer_active[4];\n'), [])


class TestMain(unittest.TestCase):
    def test_main_returns_one_and_prints_when_a_file_is_dirty(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'dirty.c'), 'w') as f:
                f.write('static uint8_t foo;\n')
            self.assertEqual(dbg_static_lint.main([d]), 1)

    def test_main_returns_zero_when_every_file_is_clean(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'clean.c'), 'w') as f:
                f.write('DBG_STATIC uint8_t foo;\n'
                        'static const uint8_t T[] = {0};\n'
                        'static void f(void) { }\n')
            self.assertEqual(dbg_static_lint.main([d]), 0)


class TestRepositorySources(unittest.TestCase):
    """AC6: this is what fails when someone adds a bare `static` to src/."""

    def test_every_src_c_file_uses_dbg_static(self):
        messages = []
        for path in dbg_static_lint.iter_sources([os.path.join(_REPO, 'src')]):
            messages.extend(dbg_static_lint.check_file(path))
        self.assertEqual(messages, [], '\n'.join(messages))

    def test_a_new_bare_static_is_reported_by_the_same_code_path(self):
        """The input flip that proves the check above can fail.

        A probe module goes through iter_sources + check_file, exactly as the
        repository check does. Without it the test above only states the tree's
        current shape and would never catch a regression.
        """
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'probe.c'), 'w') as f:
                f.write('#include "config.h"\nstatic uint8_t probe_var;\n')
            messages = []
            for path in dbg_static_lint.iter_sources([d]):
                messages.extend(dbg_static_lint.check_file(path))
        self.assertEqual(len(messages), 1)
        self.assertIn('probe_var', messages[0])
        self.assertIn(':2', messages[0])
