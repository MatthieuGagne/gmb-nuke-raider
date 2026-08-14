#!/usr/bin/env python3
"""The mailbox protocol, read from the C sources so the two cannot drift (#590 R13, R21).

`src/debug_cmds.def` names every opcode. `src/debug.h` names every outcome code and every
mailbox address. This module parses both and owns every human-readable message, because
`src/debug.c` sits in bank 30 and a text table there would hand bank 0 a pointer into an
unmapped bank.

Every read of a C source is lazy and cached. `tools/emit_manifest.py` imports this module on
every link, and a checkout whose `src/debug.h` predates the mailbox must still import it
without raising.
"""

import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(_HERE)

DEF_PATH = os.path.join(REPO_ROOT, 'src', 'debug_cmds.def')
HEADER_PATH = os.path.join(REPO_ROOT, 'src', 'debug.h')

_CMD_RE = re.compile(
    r'^\s*DBG_CMD\(\s*(\w+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)')
_DEFINE_RE = re.compile(r'^\s*#define\s+(\w+)\s+(0[xX][0-9a-fA-F]+|\d+)')

_CACHE = {}


class ProtocolError(Exception):
    """The C sources and this module disagree, or a caller passed a bad argument."""


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def parse_commands(text):
    """Return {name: {'opcode', 'argc', 'arg0_max', 'arg1_max'}} from debug_cmds.def text."""
    out = {}
    seen = {}
    for line in text.splitlines():
        m = _CMD_RE.match(line)
        if not m:
            continue
        name = m.group(1)
        opcode, argc, a0, a1 = (int(g) for g in m.groups()[1:])
        if opcode == 0:
            raise ProtocolError(f'{name}: opcode 0 means "empty", it is not a command')
        if opcode in seen:
            raise ProtocolError(f'opcode {opcode} used twice: {seen[opcode]} and {name}')
        seen[opcode] = name
        out[name.lower()] = {'opcode': opcode, 'argc': argc,
                             'arg0_max': a0, 'arg1_max': a1}
    if not out:
        raise ProtocolError('no DBG_CMD lines found')
    return out


def parse_defines(prefix, text):
    """Return {NAME: int} for every `#define <prefix>...` in the given header text."""
    out = {}
    for line in text.splitlines():
        m = _DEFINE_RE.match(line)
        if m and m.group(1).startswith(prefix):
            out[m.group(1)] = int(m.group(2), 0)
    return out


def commands():
    if 'commands' not in _CACHE:
        _CACHE['commands'] = parse_commands(_read(DEF_PATH))
    return _CACHE['commands']


def _header():
    if 'header' not in _CACHE:
        try:
            _CACHE['header'] = _read(HEADER_PATH)
        except OSError:
            _CACHE['header'] = ''
    return _CACHE['header']


def outcomes():
    if 'outcomes' not in _CACHE:
        _CACHE['outcomes'] = parse_defines('DBG_OUT_', _header())
    return _CACHE['outcomes']


def mailbox():
    """The DBG_MB_* defines. Empty when src/debug.h predates the mailbox."""
    if 'mailbox' not in _CACHE:
        _CACHE['mailbox'] = parse_defines('DBG_MB_', _header())
    return _CACHE['mailbox']


def has_mailbox():
    """True when src/debug.h carries the wire contract. Callers that must not raise use this."""
    return 'DBG_MB_BASE' in mailbox()


def _mb(name):
    try:
        return mailbox()[name]
    except KeyError:
        raise ProtocolError(
            f'{name} is not defined in {HEADER_PATH}; the mailbox contract is missing'
        ) from None


def base():         return _mb('DBG_MB_BASE')
def seed():         return _mb('DBG_MB_SEED')
def ready_value():  return _mb('DBG_MB_READY_VALUE')


# Byte offsets from base(). Keep in step with the block comment in src/debug.h.
OFFSETS = {'ready': 0, 'opcode': 1, 'arg0': 2, 'arg1': 3, 'commit': 4,
           'outcome': 5, 'detail': 6, 'epoch': 7, 'torn': 8}


def addresses():
    b = base()
    return {name: b + off for name, off in OFFSETS.items()}


# Enumerated values a scenario may spell out by name (#590 R24).
FIELDS = {'car': 0, 'armor': 1, 'weapon1': 2, 'weapon2': 3}
FIELD_BY_INDEX = {v: k for k, v in FIELDS.items()}
OPTIONS = {
    'car':     {'viper': 0, 'tank': 1},
    'armor':   {'light': 0, 'heavy': 1},
    'weapon1': {'cannon': 0, 'laser': 1},
    'weapon2': {'rocket': 0, 'mine': 1},
}
# Index order must match REAL_STATES[] in src/debug.c and the table in tools/scenarios/README.md.
STATES = {'title': 0, 'overmap': 1, 'hub': 2, 'prerace': 3,
          'playing': 4, 'results': 5, 'game_over': 6}
MODES = {'push': 0, 'pop': 1, 'replace': 2}

# Named arguments, in wire order, per command (#590 R24).
ARG_NAMES = {
    'add_scrap':      ('amount',),          # one 16-bit argument, split over arg0/arg1
    'unlock_field':   ('field',),
    'set_option':     ('field', 'option'),
    'damage':         ('amount',),
    'heal':           ('amount',),
    'force_state':    ('state', 'mode'),
    'spawn_turret':   ('tx', 'ty'),
    'despawn_turret': ('slot',),
    'spawn_racer':    ('tx', 'ty'),
    'spawn_patrol':   ('tx', 'ty'),
}

OUTCOME_MESSAGES = {
    'DBG_OUT_OK':          'the game ran the command',
    'DBG_OUT_UNKNOWN_OP':  'the game does not know this opcode',
    'DBG_OUT_ARG_RANGE':   'an argument is outside the range the command accepts',
    'DBG_OUT_LOCKED':      'the economy has not unlocked this loadout option yet',
    'DBG_OUT_IN_RACE':     'the mailbox refuses a loadout change during a race, because the '
                           'race latched its loadout when it started',
    'DBG_OUT_STACK_FULL':  'the state stack cannot take this push or pop at its current '
                           'depth (detail = the depth)',
    'DBG_OUT_UNSUPPORTED': 'this opcode is reserved and the game has no function behind it',
    'DBG_OUT_POOL_FULL':   'the entity pool has no free slot',
    'DBG_OUT_NO_EFFECT':   'the game refused the change and left the value alone',
    'DBG_OUT_NOT_ACTIVE':  'that pool slot is not active',
}

REFUSAL_NAMES = tuple(sorted(
    n[len('DBG_OUT_'):].lower() for n in OUTCOME_MESSAGES if n != 'DBG_OUT_OK'))


def refusal_code(short_name):
    """Turn `locked` into the DBG_OUT_LOCKED value from src/debug.h."""
    key = 'DBG_OUT_' + str(short_name).upper()
    try:
        return outcomes()[key]
    except KeyError:
        raise ProtocolError(
            f'unknown refusal {short_name!r}; known: {", ".join(REFUSAL_NAMES)}') from None


def commit_byte(opcode, arg0, arg1):
    """The exclusive-or fold the game checks before it runs a command (#590 R7)."""
    return (seed() ^ opcode ^ arg0 ^ arg1) & 0xFF


def describe_outcome(code, detail=None):
    """One sentence naming what the game did, for a scenario failure message (#590 R21)."""
    by_code = {v: k for k, v in outcomes().items()}
    name = by_code.get(code)
    if name is None:
        return f'unknown outcome code {code}'
    text = OUTCOME_MESSAGES.get(name, 'no message is registered for this code')
    if detail is None:
        return f'{name}: {text}'
    return f'{name}: {text} (detail={detail})'


def _lookup(table, key, what):
    if isinstance(key, int):
        return key
    try:
        return table[str(key).lower()]
    except KeyError:
        raise ProtocolError(
            f'unknown {what} {key!r}; known: {", ".join(sorted(table))}') from None


def _to_int(cmd_name, arg_name, value):
    """int(value), but a bad scenario value is a ProtocolError, never a raw ValueError/TypeError."""
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ProtocolError(
            f'{cmd_name}: {arg_name} must be a whole number, got {value!r}') from None


def pack(cmd, args=None):
    """Turn a named command and named arguments into (opcode, arg0, arg1).

    Raises ProtocolError for an unknown command, an unknown argument name, a missing
    argument, or a value outside the range the .def declares. It never raises anything else,
    so a caller can report the problem instead of crashing.
    """
    args = dict(args or {})
    name = str(cmd).lower()
    table = commands()
    if name not in table:
        raise ProtocolError(
            f'unknown command {cmd!r}; known: {", ".join(sorted(table))}')
    spec = table[name]
    names = ARG_NAMES[name]
    unknown = set(args) - set(names)
    if unknown:
        raise ProtocolError(
            f'{name}: unknown argument(s) {", ".join(sorted(unknown))}; '
            f'accepts {", ".join(names)}')
    missing = [n for n in names if n not in args]
    if missing:
        raise ProtocolError(f'{name}: missing argument(s) {", ".join(missing)}')

    if name == 'add_scrap':
        amount = _to_int(name, 'amount', args['amount'])
        if not 0 <= amount <= 0xFFFF:
            raise ProtocolError(f'add_scrap: amount {amount} is outside 0..65535')
        arg0, arg1 = amount & 0xFF, (amount >> 8) & 0xFF
    elif name == 'unlock_field':
        arg0, arg1 = _lookup(FIELDS, args['field'], 'loadout field'), 0
    elif name == 'set_option':
        field = _lookup(FIELDS, args['field'], 'loadout field')
        if field not in FIELD_BY_INDEX:
            raise ProtocolError(
                f'set_option: field {field} is outside 0..3')
        arg0 = field
        arg1 = _lookup(OPTIONS[FIELD_BY_INDEX[field]], args['option'], 'loadout option')
    elif name == 'force_state':
        arg0 = _lookup(STATES, args['state'], 'state')
        arg1 = _lookup(MODES, args['mode'], 'mode')
    else:
        vals = [_to_int(name, n, args[n]) for n in names]
        arg0 = vals[0]
        arg1 = vals[1] if len(vals) > 1 else 0

    for i, (value, limit) in enumerate(
            ((arg0, spec['arg0_max']), (arg1, spec['arg1_max']))):
        if i >= spec['argc']:
            continue
        if not 0 <= value <= limit:
            raise ProtocolError(
                f'{name}: arg{i} is {value}, the command accepts 0..{limit}')
    return spec['opcode'], arg0, arg1
