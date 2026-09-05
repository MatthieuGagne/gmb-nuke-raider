---
summary: Recurring shapes of a verification step that passes without checking anything — self-defeating asserts matching their own comment or spanning a hard wrap, wrapper-shape asserts that never round-trip the payload, and commands that were never actually run (invented helpers, wrong gh subcommand fields, gh issue list defaulting to open, PATHEXT casing)
tags: [verification, testing, prove-it-bites, antipattern, grep, gh, gotcha]
---

# Verification antipatterns (checks that check nothing)

The failure shapes behind the rule "a verification step is unrun code": a plan command,
test assertion or grep gate that reports success while checking nothing. Observed in
#441, #472, #437, #436 and #633. The techniques for proving a check *can* fail live in
[[verification-techniques]]; this page catalogues what goes wrong when nobody does.

## Self-defeating assert

The pattern matches the comment explaining the rule rather than the rule's real use, or
a hard-wrapped phrase spans two physical lines (prose in this repo wraps at ~90 cols) so
a single-line grep can never match it.

Fix: re-wrap the prose byte-identical, or anchor the pattern. **Never weaken the pattern
until it passes** — that converts a real failure into a permanent false green.

## Wrapper-shape assert

An assertion of the form "it was embedded / encoded / written" that only inspects the
wrapper and never the payload. Round-trip instead: decode the base64 and check the magic
bytes, re-parse the JSON and read the field back. Then prove the new assert bites on the
old broken input.

## Commands that were never run

The step was written from memory rather than executed, and the shell would have rejected
it. Recurring instances:

- Invented helper scripts or flags that do not exist.
- Reversed argument order.
- `gh --json` fields taken from the wrong subcommand.
- `gh issue list` defaulting to open issues — this repo closes ADRs on acceptance, so
  ADR queries need `--state all`.
- `PATHEXT` casing on Windows.

Fix: read the real seam, then run the real command and read its actual output.

## Related

- [[verification-techniques]] — the prove-it-bites techniques that make a check
  demonstrably fail.
- Agent shells reproduce each other's environment, so gates written for a human at a
  real terminal (`! …`) must be proven too — the #441 `GIT_DIR` leak is the case.
- Cross-project: `C:\Code\knowledge\claude-code-hooks-no-hot-reload.md`.
