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


# --------------------------------------------------------------------------
# Build/run engine
# --------------------------------------------------------------------------

def run_subprocess(cmd, cwd, timeout):
    """Run one command. Returns (returncode, combined output).

    A hung child is returncode 124, mirroring coreutils timeout. clean_env
    strips GIT_DIR and friends so the engine behaves identically under the
    pre-commit hook and a plain shell.
    """
    try:
        proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=timeout,
                              env=install_hooks.clean_env())
        return proc.returncode, proc.stdout.decode('utf-8', 'replace')
    except subprocess.TimeoutExpired:
        return 124, 'timeout after %ds: %s' % (timeout, ' '.join(cmd))
    except FileNotFoundError as err:
        raise MutationError('cannot spawn %r: %s' % (cmd[0], err))


def exe(path):
    """Binary path as gcc will actually name it on this platform."""
    return path + '.exe' if os.name == 'nt' else path


def module_of(path):
    """src/foo.c -> foo; tests/test_foo.c -> test_foo."""
    return os.path.splitext(os.path.basename(path))[0]


class Project(object):
    """Everything the engine needs to know about a buildable test suite."""

    def __init__(self, root, flags, lib_sources, test_sources,
                 support_sources, workdir):
        self.root = os.path.abspath(root)
        self.flags = list(flags)
        self.lib_sources = sorted(lib_sources)
        self.test_sources = sorted(test_sources)
        self.support_sources = sorted(support_sources)
        self.workdir = workdir  # absolute

    def mutants_dir(self):
        return os.path.join(self.workdir, 'mutants')


def host_project(root):
    """The repo's real host suite, mirroring the Makefile `test` recipe."""
    root = os.path.abspath(root)

    def rel(pattern_dir, suffix):
        d = os.path.join(root, pattern_dir)
        if not os.path.isdir(d):
            return []
        return [pattern_dir + '/' + f for f in os.listdir(d)
                if f.endswith(suffix)]

    lib = [p for p in rel('src', '.c') if p != 'src/main.c']
    tests = [p for p in rel('tests', '.c')
             if os.path.basename(p).startswith('test_')]
    support = ['tests/unity/src/unity.c'] + rel('tests/mocks', '.c')
    flags = ['-Itests/mocks', '-Itests/unity/src', '-Isrc',
             '-Ilib/hUGEDriver/include', '-Wall', '-Wextra',
             '-DDEBUG_MAILBOX']
    return Project(root, flags, lib, tests, support,
                   os.path.join(root, 'build', 'mutation'))


def _compile(project, run, src_rel_or_abs, out_obj):
    cmd = ['gcc', '-c'] + project.flags + [src_rel_or_abs, '-o', out_obj]
    return run(cmd, project.root, COMPILE_TIMEOUT)


def _link(project, run, objs, out_bin):
    return run(['gcc'] + objs + ['-o', out_bin], project.root,
               COMPILE_TIMEOUT)


def _check_deadline(deadline, phase, clock=time.monotonic):
    if deadline is not None and clock() > deadline:
        raise MutationError('%s exceeded --timeout-seconds' % phase)


def build_baseline(project, run, deadline=None, clock=time.monotonic):
    """Compile every pristine source once, link and run every test binary.

    Object caching (R4a): these objects are compiled exactly once per
    invocation. Raises MutationError if anything fails — mutation results
    are meaningless against a red baseline. The deadline (R4) covers this
    phase too: the baseline is the expensive part of an invocation and
    must not escape the wall clock.
    """
    obj_dir = os.path.join(project.workdir, 'obj')
    sup_dir = os.path.join(project.workdir, 'support')
    tobj_dir = os.path.join(project.workdir, 'testobj')
    bin_dir = os.path.join(project.workdir, 'bin')
    for d in (obj_dir, sup_dir, tobj_dir, bin_dir):
        os.makedirs(d, exist_ok=True)

    lib_objs = {}
    for src in project.lib_sources:
        _check_deadline(deadline, 'baseline compile', clock)
        out = os.path.join(obj_dir, module_of(src) + '.o')
        rc, text = _compile(project, run, src, out)
        if rc:
            raise MutationError('baseline compile failed: %s\n%s'
                                % (src, text))
        lib_objs[module_of(src)] = out

    support_objs = []
    for src in project.support_sources:
        _check_deadline(deadline, 'baseline compile', clock)
        out = os.path.join(sup_dir, module_of(src) + '.o')
        rc, text = _compile(project, run, src, out)
        if rc:
            raise MutationError('baseline compile failed: %s\n%s'
                                % (src, text))
        support_objs.append(out)

    binaries = []  # (name, test_obj, baseline_bin)
    for src in project.test_sources:
        _check_deadline(deadline, 'baseline link', clock)
        name = module_of(src)
        tobj = os.path.join(tobj_dir, name + '.o')
        rc, text = _compile(project, run, src, tobj)
        if rc:
            raise MutationError('baseline compile failed: %s\n%s'
                                % (src, text))
        bin_path = exe(os.path.join(bin_dir, name))
        rc, text = _link(project, run,
                         [tobj] + support_objs + sorted(lib_objs.values()),
                         bin_path)
        if rc:
            raise MutationError('baseline link failed: %s\n%s'
                                % (name, text))
        binaries.append((name, tobj, bin_path))

    for name, _tobj, bin_path in binaries:
        _check_deadline(deadline, 'baseline run', clock)
        rc, text = run([bin_path], project.root, RUN_TIMEOUT)
        if rc:
            raise MutationError(
                'baseline test %s failed (rc %d) — fix the suite before '
                'mutating:\n%s' % (name, rc, text))
    return lib_objs, support_objs, binaries


def test_mutant(project, lib_objs, support_objs, binaries, mutant, run):
    """Compile one mutant, link and run tests in relevance order (R4b).

    The mutated source is written only under project.mutants_dir(); the
    tracked file is read, never written (R8). The pristine object in
    lib_objs is never overwritten — the mutant object is substituted at
    link time only.
    """
    started = time.monotonic()
    module = module_of(mutant['file'])
    mdir = project.mutants_dir()
    os.makedirs(mdir, exist_ok=True)

    with open(os.path.join(project.root, mutant['file']),
              'r', encoding='utf-8', errors='replace') as fh:
        text = fh.read()
    mutated_src = os.path.join(mdir, module + '.c')
    with open(mutated_src, 'w', encoding='utf-8') as fh:
        fh.write(apply_mutant(text, mutant))

    result = {'compiles': 0, 'binaries_run': 0}
    mutated_obj = os.path.join(mdir, module + '.o')
    rc, out = _compile(project, run, mutated_src, mutated_obj)
    result['compiles'] += 1  # counted from the actual call, not asserted
    if rc:
        result.update(status='invalid',
                      detail=out.strip().splitlines()[-1] if out.strip()
                      else 'compile failed',
                      seconds=time.monotonic() - started)
        return result

    linked_objs = dict(lib_objs)
    linked_objs[module] = mutated_obj
    own = 'test_' + module
    ordered = ([b for b in binaries if b[0] == own]
               + [b for b in binaries if b[0] != own])
    for name, tobj, _bin in ordered:
        mbin = exe(os.path.join(mdir, name))
        rc, out = _link(project, run,
                        [tobj] + support_objs
                        + sorted(linked_objs.values()), mbin)
        if rc:
            result.update(status='invalid',
                          detail='link failed for %s' % name,
                          seconds=time.monotonic() - started)
            return result
        rc, out = run([mbin], project.root, RUN_TIMEOUT)
        result['binaries_run'] += 1
        if rc:
            result.update(status='killed', killed_by=name,
                          seconds=time.monotonic() - started)
            return result
    result.update(status='survived', seconds=time.monotonic() - started)
    return result
