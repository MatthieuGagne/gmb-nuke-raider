# Pipeline self-correction (shared)

Read by the `map-expert` and `sprite-expert` agents when a pipeline step fails.

## Policy

1. **Capture the complete error output** of the failed tool or command — exit code plus stderr.
2. **Retry only the failed step.** Never restart the checklist from the top; earlier steps already
   wrote files, and re-running them can clobber good output or re-create work.
3. **Each retry must change something** — a flag, an intermediate file, an input — based on the
   error text. A byte-identical retry is not an attempt.
4. **Maximum 3 attempts per step.**
5. **On the 3rd failure: halt.** Surface all three error outputs in full, name the step, and
   cross-reference the agent's own Common Mistakes table for the most likely root cause. Wait for
   human instruction. Never fall back to a silent workaround (hand-editing a generated file,
   skipping the converter, hardcoding data).

## Reading a failure

The pipeline tools (`png_to_tiles.py`, `tmx_to_c.py`, `overmap_to_c.py`, `make`) all print the
actual cause on stderr and exit non-zero. Read that output before theorizing — do not classify a
failure from the exit code alone.

Two failure shapes the exit code does *not* reveal, so check for them explicitly:

- **Converter exited 0 but wrote nothing** — the generated `.c` is absent or unchanged. Check the
  output path argument.
- **Tool succeeded, output is wrong** — e.g. a tile count that does not match
  `(px_width / 8) × (px_height / 8)` per frame, or a multi-frame Aseprite export that produced
  numbered files instead of a sheet. These need a content check, not an exit-code check.
