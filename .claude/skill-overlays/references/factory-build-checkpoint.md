# Factory mode — BUILD stage logging and headless checkpoint

Extracted from the `subagent-driven-development` overlay. Applies only when `NUKE_FACTORY_RUN`
is set (the BUILD stage of a `/factory` run).

## Stage-log capture (#654)

BUILD is not exempt from the factory's stage-log rule, and it is the only stage whose commands
are run by two actors. `LOG BUILD -- <argv>` below is shorthand for

```
python tools/factory_log.py --stage BUILD --issue <N> -- <argv>
```

with `<N>` the run's issue number, passed explicitly because `NUKE_FACTORY_RUN` does not cross a
dispatch. Add `--stream` when the output is read rather than exit-code checked. Between the two
actors, `.factory/runs/issue-<N>/logs/BUILD.log` ends up holding the stage's real command output:

- **The controller** wraps the checkpoint commands below and the `git log --oneline -1`
  verification it runs after every implementer dispatch.
- **Every implementer** wraps its own `make`, `make test` and `git commit`. Put the wrapper and
  the issue number in the brief — a subagent that is not told the number cannot write to the
  run's log. It is one prefix and nothing else changes: the exit code passes through verbatim,
  a failing command still prints its whole output, and the 300 s commit budget and the
  `pre-commit` hook behave exactly as before.

## Headless batch-boundary checkpoint

At each batch boundary, run this instead of the Emulicious pause:

1. `LOG BUILD -- git fetch origin` then `LOG BUILD -- git merge origin/master`
2. `LOG BUILD -- make clean` then `LOG BUILD -- make`
3. `LOG BUILD -- make memory-check` — **any FAIL or ERROR aborts the run immediately.** No retry.
4. `LOG BUILD --stream -- python tools/smoketest_headless.py --scenario generic-smoke --json` —
   this replaces "ask the user before launching Emulicious" and "wait for visual confirmation".
   Exit 0 continues. `--stream` because the JSON verdict is read, not merely exit-code checked.
5. Record the outcome (bookkeeping, not wrapped):
   ```
   python tools/factory_event.py --issue <N> --kind scenario --field scenario=generic-smoke --field result=<pass|fail> --field blocking=true
   ```

## Retry budget

**2 attempts per task.** Append `--kind retry --field stage=BUILD --attempt <k>` before the
second attempt. Exhausted → terminal failure; do not proceed to the next task.

This counts **task attempts inside a run**; it does not shorten the baseline's five-round fix
loop inside a single task review.
