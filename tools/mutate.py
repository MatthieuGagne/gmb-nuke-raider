"""Host-side mutation testing harness for changed C sources (issue #700).

Mutates functions touched by a diff, rebuilds the host test suite against
each mutant using a per-invocation object cache, and reports survivors.

Exit codes:
    0  every tested mutant was killed (or nothing was in scope)
    1  at least one mutant survived
    2  operational or usage error (bad flags, missing gcc, red baseline)
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import install_hooks  # noqa: E402  (path must be set first)
import crap_score     # noqa: E402

DEFAULT_BUDGET = 30
DEFAULT_TIMEOUT_SECONDS = 600
COMPILE_TIMEOUT = 120   # seconds, per gcc invocation
RUN_TIMEOUT = 60        # seconds, per test binary run

EXEMPT_FILES = crap_score.EXEMPT_FILES


class MutationError(Exception):
    """Operational failure that must abort the run with exit code 2."""


# --------------------------------------------------------------------------
# Source masking
# --------------------------------------------------------------------------

def mask_source(text):
    """Blank comments, string/char literals and preprocessor lines to spaces.

    Length and newlines are preserved, so column offsets in the masked text
    map 1:1 onto the original. Operators only ever match masked text, which
    is what keeps a mutant from landing inside a comment or a string (a
    no-op mutant would report as a false survivor).
    """
    out = list(text)
    i, n = 0, len(text)
    state = 'code'
    at_line_start = True
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ''
        if state == 'code':
            if at_line_start and c == '#':
                state = 'pp'
                out[i] = ' '
            elif c == '/' and nxt == '/':
                state = 'line_comment'
                out[i] = out[i + 1] = ' '
                i += 1
            elif c == '/' and nxt == '*':
                state = 'block_comment'
                out[i] = out[i + 1] = ' '
                i += 1
            elif c == '"':
                state = 'string'
                out[i] = ' '
            elif c == "'":
                state = 'char'
                out[i] = ' '
        elif state == 'pp':
            if c == '\n':
                if i > 0 and text[i - 1] == '\\':
                    pass  # backslash continuation stays preprocessor
                else:
                    state = 'code'
            else:
                out[i] = ' '
        elif state == 'line_comment':
            if c == '\n':
                state = 'code'
            else:
                out[i] = ' '
        elif state == 'block_comment':
            if c == '*' and nxt == '/':
                out[i] = out[i + 1] = ' '
                i += 1
                state = 'code'
            elif c != '\n':
                out[i] = ' '
        elif state == 'string':
            if c == '\\' and nxt:
                out[i] = out[i + 1] = ' '
                i += 1
            elif c == '"':
                state = 'code'
                out[i] = ' '
            elif c != '\n':
                out[i] = ' '
        elif state == 'char':
            if c == '\\' and nxt:
                out[i] = out[i + 1] = ' '
                i += 1
            elif c == "'":
                state = 'code'
                out[i] = ' '
            elif c != '\n':
                out[i] = ' '
        if c == '\n':
            at_line_start = True
        elif not (at_line_start and c in ' \t'):
            at_line_start = False
        i += 1
    return ''.join(out)


# --------------------------------------------------------------------------
# Mutation operators
# --------------------------------------------------------------------------

# Ordered alternation: two-char tokens before their one-char prefixes.
COMPARISON_RE = re.compile(r'(?<![<>=!&|+\-*/%^])(==|!=|<=|>=|<|>)(?![<>=])')
COMPARISON_SWAP = {'==': '!=', '!=': '==', '<': '>=', '>': '<=',
                   '<=': '>', '>=': '<'}

ARITH_RE = re.compile(r'(?<![+\-*/=<>!&|^%])([+\-*/])(?![+\-*/=>])')
ARITH_SWAP = {'+': '-', '-': '+', '*': '/', '/': '*'}

INT_RE = re.compile(r'(?<![\w.])(\d+)(?![\w.])')

RETURN_RE = re.compile(r'\breturn\b\s*([^;]+);')

IF_RE = re.compile(r'\bif\s*\(')


C_TYPE_KEYWORDS = frozenset((
    'int', 'char', 'short', 'long', 'unsigned', 'signed', 'float',
    'double', 'void', 'const', 'volatile', 'static', 'register'))


def _has_binary_left_operand(masked_line, col):
    """True when the char left of col (ignoring spaces) can end an operand.

    Filters unary minus and dereferences out of the arithmetic operator so
    the budget is not eaten by mutants that cannot change behaviour or
    cannot compile.
    """
    j = col - 1
    while j >= 0 and masked_line[j] == ' ':
        j -= 1
    return j >= 0 and (masked_line[j].isalnum() or masked_line[j] in '_)]')


def _left_token(masked_line, col):
    """The identifier/keyword immediately left of col, skipping spaces."""
    j = col - 1
    while j >= 0 and masked_line[j] == ' ':
        j -= 1
    end = j + 1
    while j >= 0 and (masked_line[j].isalnum() or masked_line[j] == '_'):
        j -= 1
    return masked_line[j + 1:end]


def iter_line_mutants(masked_line, line):
    """All single-site mutants of one line, in column order."""
    found = []
    for m in COMPARISON_RE.finditer(masked_line):
        tok = m.group(1)
        found.append({'col': m.start(1), 'op': 'comparison',
                      'original': tok, 'mutated': COMPARISON_SWAP[tok]})
    for m in ARITH_RE.finditer(masked_line):
        tok = m.group(1)
        if not _has_binary_left_operand(masked_line, m.start(1)):
            continue
        left = _left_token(masked_line, m.start(1))
        if tok == '*' and (left in C_TYPE_KEYWORDS or left.endswith('_t')):
            continue  # pointer declaration, not multiplication
        found.append({'col': m.start(1), 'op': 'arithmetic',
                      'original': tok, 'mutated': ARITH_SWAP[tok]})
    for m in INT_RE.finditer(masked_line):
        tok = m.group(1)
        found.append({'col': m.start(1), 'op': 'constant',
                      'original': line[m.start(1):m.end(1)],
                      'mutated': str(int(tok) + 1)})
    m = RETURN_RE.search(masked_line)
    if m and m.group(1).strip():
        expr = line[m.start(1):m.end(1)]
        repl = '1' if expr.strip() == '0' else '0'
        found.append({'col': m.start(1), 'op': 'return',
                      'original': expr, 'mutated': repl})
    m = IF_RE.search(masked_line)
    if m:
        open_paren = m.end() - 1
        depth = 0
        close_paren = -1
        for j in range(open_paren, len(masked_line)):
            if masked_line[j] == '(':
                depth += 1
            elif masked_line[j] == ')':
                depth -= 1
                if depth == 0:
                    close_paren = j
                    break
        if close_paren > open_paren + 1:
            cond = line[open_paren + 1:close_paren]
            found.append({'col': open_paren + 1, 'op': 'negate-condition',
                          'original': cond, 'mutated': '!(%s)' % cond})
    return sorted(found, key=lambda f: (f['col'], f['op']))


# --------------------------------------------------------------------------
# Scoping
# --------------------------------------------------------------------------

def touched_functions(path, text, changed_lines=None):
    """1-based inclusive (start, end) spans of functions to mutate.

    changed_lines None means the whole file is in scope (--files mode).
    """
    lizard = crap_score._import_lizard()
    analysis = lizard.analyze_file.analyze_source_code(path, text)
    spans = [(f.start_line, f.end_line) for f in analysis.function_list]
    if changed_lines is None:
        return spans
    return [s for s in spans
            if any(s[0] <= ln <= s[1] for ln in changed_lines)]


def generate_candidates(root, scope):
    """Mutants for every in-scope function, deterministic order.

    scope maps repo-relative posix path -> set of changed lines, or None
    for whole-file scope. Exempt and missing files must be filtered out by
    the caller; this function trusts its scope.
    """
    candidates = []
    for path in sorted(scope):
        abs_path = os.path.join(root, path)
        with open(abs_path, 'r', encoding='utf-8', errors='replace') as fh:
            text = fh.read()
        masked = mask_source(text)
        lines = text.splitlines()
        masked_lines = masked.splitlines()
        for start, end in touched_functions(path, text, scope[path]):
            for ln in range(start, min(end, len(lines)) + 1):
                for frag in iter_line_mutants(masked_lines[ln - 1],
                                              lines[ln - 1]):
                    mut = dict(frag)
                    mut['file'] = path
                    mut['line'] = ln
                    candidates.append(mut)
    # Overlapping lizard spans could emit duplicates, and function order is
    # lizard's, not ours: de-dup and impose the documented order explicitly.
    unique = {(c['file'], c['line'], c['col'], c['op']): c
              for c in candidates}
    return [unique[key] for key in sorted(unique)]


def apply_mutant(text, mutant):
    """File text with the mutant's fragment substituted on its line."""
    lines = text.splitlines(keepends=True)
    i = mutant['line'] - 1
    line = lines[i]
    col = mutant['col']
    lines[i] = (line[:col] + mutant['mutated']
                + line[col + len(mutant['original']):])
    return ''.join(lines)
