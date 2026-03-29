---
name: Python test permission
description: Don't ask for permission before running Python tests (unittest, pytest, PYTHONPATH=. python3 -m unittest)
type: feedback
---

Don't ask for permission before running Python tests.

**Why:** User said "don't ask again for python test" — running tests is always safe and expected.

**How to apply:** Run `PYTHONPATH=. python3 -m unittest ...` or any Python test command without prompting first.
