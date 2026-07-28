# The stage-log writer is exempt from the registry's sole-writer invariant

`tools/factory_run.py` opens by declaring itself "the only writer of the registry. Every
other factory tool reads," and #436 R1 says the same. PRD-10 (#450) puts stage logs at
`.factory/runs/issue-<N>/logs/<stage>.log` — inside that registry — written by a second
module, `tools/factory_log.py`. A reader who finds two writers there will reasonably
conclude that someone violated `docs/adr/0003`. Nobody did: **the invariant is narrowed to
run state and the journal, and `factory_log` becomes the sole writer of the `logs/`
subtree.**

The invariant was never about the directory. It exists to protect the ordering guarantee in
ADR 0003 — `append_event()` writes the journal line first, then re-saves state atomically,
so state may lag the journal by one event and can never lead it. A single writer is what
makes that orderable at all. Stage logs participate in no projection: nothing derives from
them, #450 puts parsing them out of scope, and they are opaque byte streams whose only
consumer is a human running `grep`. A stage log that is truncated, empty, or missing
entirely cannot make state disagree with the journal, because no code reads it. There is no
consistency for a second writer to corrupt.

What does not move is ownership of the *path*. `factory_run` gains
`log_path(issue, stage, registry=None)` alongside `state_path()` and `journal_path()`, and
`factory_log` calls it rather than re-deriving the convention. #436 keeps the registry
layout, the stage vocabulary (`STAGES`), and the clock seam; #450 gets only the writing.
That split also inherits the `GIT_DIR` fix from #462 for free instead of re-introducing it
in a second place.

## Considered options

**Fold the helper into `factory_run.py`.** The invariant survives untouched. #450's own
notes already considered and rejected this — to stop the epic's sole remaining
critical-path blocker from growing — and that reason has since expired, because #436
shipped. Rejected on the merits instead: it mixes an incremental streaming concern into the
module whose stated job is schema ownership, and it means every future caller of a
subprocess wrapper imports the registry writer.

**Route the writes through `factory_run.append_log(issue, stage, chunk)`.** Preserves the
invariant literally. Rejected because it is literal compliance at the cost of the thing the
invariant protects: a per-chunk API on the module that must remain a small, ordered,
atomic-write surface, and every flush of a `make` build dragged through the module that
shells out to git.

**Record log-write failures as journal events.** Considered while specifying #450's
fail-open behavior and rejected outright. `EVENT_KINDS` is a closed tuple and
`apply_event()` projects each kind into state; `failure` already means a terminal run
failure. A swallowed log-write error appended there would project a healthy run as dead —
the projection corruption this invariant exists to prevent, arriving by the front door.

## Consequences

**Two documents must be corrected, not merely extended.** `factory_run.py`'s module
docstring and `docs/dev-workflow.md` §9 "Who writes what" both assert the un-narrowed
invariant today. Shipping #450 without changing them leaves the documentation contradicting
the code.

**The exemption is specific, not a precedent.** It is granted because stage logs feed no
projection. Any future artifact written into the registry by a module other than
`factory_run` must re-run this argument on its own facts; "logs got an exemption" is not
one of them.

**#436 R4's autopsy exclusion now rests on this decision.** Autopsy bundles copy in
everything worktree-resident but deliberately skip stage logs, on the grounds that they are
already in the registry and already survive worktree deletion. That is only true while
something actually writes them there — which is what this decision authorizes.
