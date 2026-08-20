---
summary: tools/trace.py shadows Python's stdlib trace module — importers must sys.path.insert tools/ first; a missing module surfaces as AttributeError (missing function), not ModuleNotFoundError
tags: [python, tooling, trace, sys-path, import, stdlib, gotcha]
---

# tools/trace.py shadows the stdlib `trace` module

`tools/trace.py` (added 2026-07-26 for issue #435) collides with Python's stdlib
`trace` module. Any test or script that does `import trace` **succeeds even when our
file is absent** — it just binds the stdlib tracer. `tests/test_trace.py` avoids this
with `sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))`
before the import.

**Why:** the failure mode is silent and misleading. During TDD the RED phase surfaced
as `AttributeError: module 'trace' has no attribute 'parse_plan_name'`, not
`ModuleNotFoundError` — so a missing/mis-pathed module looks like a missing *function*,
and anyone debugging chases the wrong thing. The name was kept because the issue
specifies the `tools/trace.py` path.

**How to apply:** any new module importing it must put `tools/` at the front of
`sys.path` first. If a future test module imports stdlib `trace` before
`tests/test_trace.py` runs, `sys.modules` caching means ours never loads — check import
order before trusting a green run. Related: [[test-tools-gate-history]].
