#!/usr/bin/env python3
"""dbg_static_lint.py — every mutable file-scope static data declaration in
src/*.c must use DBG_STATIC (#588 R3, R7).

DBG_STATIC is `static` in a release ROM and empty in a debug ROM, so a module
variable reaches the debug symbol file and a headless scenario can watch it. A
declaration that keeps the bare `static` keyword stays invisible.

Three things are deliberately NOT flagged:
  * static functions      — `update` and `enter` each occur 7 times in src/,
                            so widening the macro to functions breaks the
                            link (R4). A chunk whose body opens a brace, or
                            whose declarator ends in a parameter list, is a
                            function.
  * `static const` data   — it holds ROM data, and the symbol reader accepts
                            WRAM addresses only (R5). A mutable POINTER to
                            const data is NOT const data and IS flagged.
  * function-local static — it is not file scope. Brace depth decides.

Usage:
    python3 tools/dbg_static_lint.py [PATH ...]     # default: src/
Exit codes: 0 clean, 1 one or more violations.
"""
from __future__ import annotations

import os
import re
import sys

DEFAULT_PATHS = ('src',)

_IDENT = re.compile(r'[A-Za-z_]\w*')
# A parameter list at the end of a declarator: `f(void)`, `f(uint8_t x) BANKED`.
_FUNC_TAIL = re.compile(r'\)\s*(?:BANKED|NONBANKED)?\s*$')
# The storage-class token, used to line-number the declaration itself.
_STATIC_TOKEN = re.compile(r'(?:^|(?<=\s))(?:DBG_STATIC|static)(?=\s|$)')


def blank_comments_and_strings(text):
    """Replace comment and string bodies with spaces, keeping every offset.

    Line numbers and brace depth stay correct, and the word `static` inside a
    comment or a string literal stops being visible to the parser.
    """
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == '/' and i + 1 < n and text[i + 1] == '*':
            j = text.find('*/', i + 2)
            j = n if j < 0 else j + 2
            out.append(re.sub(r'[^\n]', ' ', text[i:j]))
            i = j
        elif c == '/' and i + 1 < n and text[i + 1] == '/':
            j = text.find('\n', i)
            j = n if j < 0 else j
            out.append(' ' * (j - i))
            i = j
        elif c in '"\'':
            quote, j = c, i + 1
            while j < n and text[j] != quote:
                j += 2 if text[j] == '\\' else 1
            j = min(j + 1, n)
            out.append(re.sub(r'[^\n]', ' ', text[i:j]))
            i = j
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def drop_preprocessor(chunk):
    """Remove whole preprocessor lines. `#ifdef`/`#else` split a declarator."""
    return '\n'.join(line for line in chunk.splitlines()
                     if not line.lstrip().startswith('#'))


def file_scope_chunks(text):
    """Yield (offset, chunk, terminator) for every statement at brace depth 0.

    A `{` that follows a top-level `=` opens an initialiser, not a function
    body: the chunk continues to the `;` after it.
    """
    depth, start, saw_assign, i, n = 0, 0, False, 0, len(text)
    while i < n:
        c = text[i]
        if c == '{':
            if depth == 0 and not saw_assign:
                yield start, text[start:i], '{'
                depth += 1
                start = None
            else:
                depth += 1
        elif c == '}':
            depth -= 1
            if depth <= 0:
                depth = 0
                if start is None:
                    start, saw_assign = i + 1, False
        elif depth == 0 and c == ';':
            if start is not None:
                yield start, text[start:i], ';'
            start, saw_assign = i + 1, False
        elif depth == 0 and c == '=' and \
                text[i - 1:i] not in ('=', '!', '<', '>') and \
                text[i + 1:i + 2] != '=':
            saw_assign = True
        i += 1


def declarator_of(chunk):
    """The chunk up to the first top-level `=`, with subscripts removed."""
    head = chunk
    for i, c in enumerate(chunk):
        if c == '=' and chunk[i - 1:i] not in ('=', '!', '<', '>') \
                and chunk[i + 1:i + 2] != '=':
            head = chunk[:i]
            break
    return re.sub(r'\[[^\]]*\]', '', head)


def is_immutable(declarator):
    """True when the OBJECT is const, not merely what it points at.

    `static const uint8_t *p`      -> the pointer is mutable   -> False
    `static const char* const q[]` -> the pointer is const      -> True
    `static const uint8_t T[]`     -> no pointer, const object  -> True
    """
    if 'const' not in declarator:
        return False
    star = declarator.rfind('*')
    if star < 0:
        return True
    return 'const' in declarator[star:]


def classify(chunk, terminator):
    """'ok', 'skip' or 'bad' for one file-scope chunk."""
    body = drop_preprocessor(chunk).strip()
    if not body:
        return 'skip'
    if body.startswith('DBG_STATIC'):
        return 'ok'
    if not re.search(r'(?:^|\s)static(?:\s|$)', body):
        return 'skip'
    declarator = declarator_of(body).strip()
    if terminator == '{':
        return 'skip'                      # a function body
    if _FUNC_TAIL.search(declarator):
        return 'skip'                      # a function declaration
    if is_immutable(declarator):
        return 'skip'                      # R5
    return 'bad'


def first_identifier_after_type(declarator):
    """Best-effort name for the message: the last identifier in the declarator."""
    names = [n for n in _IDENT.findall(declarator)
             if n not in ('static', 'const', 'volatile', 'unsigned', 'signed')]
    return names[-1] if names else '<unnamed>'


def declaration_offset(chunk):
    """Offset within *chunk* of the `static` token.

    NOT the chunk's first non-space character: a chunk routinely begins with
    `#include` or `#define` lines, and `lstrip()` stops at the `#`, which would
    report the line of a preprocessor directive instead of the declaration.
    """
    m = _STATIC_TOKEN.search(chunk)
    return m.start() if m else len(chunk) - len(chunk.lstrip())


def check_file(path):
    """Return a list of message strings, one per violating declaration."""
    with open(path, encoding='utf-8') as f:
        raw = f.read()
    text = blank_comments_and_strings(raw)
    messages = []
    for offset, chunk, terminator in file_scope_chunks(text):
        if classify(chunk, terminator) != 'bad':
            continue
        line = raw.count('\n', 0, offset + declaration_offset(chunk)) + 1
        name = first_identifier_after_type(declarator_of(drop_preprocessor(chunk)))
        messages.append(
            '%s:%d: mutable file-scope `static` data `%s` must use DBG_STATIC '
            '(#588 R3)' % (path.replace(os.sep, '/'), line, name))
    return messages


def iter_sources(paths):
    for p in paths:
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                if name.endswith('.c'):
                    yield os.path.join(p, name)
        elif p.endswith('.c'):
            yield p


def main(argv=None):
    paths = list(argv) if argv else list(DEFAULT_PATHS)
    messages = []
    for path in iter_sources(paths):
        messages.extend(check_file(path))
    for m in messages:
        print('FAIL %s' % m)
    if messages:
        print('%d declaration(s) missing DBG_STATIC' % len(messages))
        return 1
    print('OK DBG_STATIC applied to every mutable file-scope static in %s'
          % ', '.join(paths))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
