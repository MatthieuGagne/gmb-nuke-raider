# Local gates are repository hooks, split by cost; CI is the authority

CI is the authority on whether a change is sound: it runs the unit suite, the tool
suite, and the ROM build, on every pull request and every push to `master`, with
required status checks that apply to administrators too. Local gates exist only to
fail fast — to save a round-trip, never to be the thing that decides.

Because of that, local gates are **repository hooks** rather than agent hooks, and
they are split by cost: `pre-commit` runs the tool suite (~5s), `pre-push` runs a
clean ROM build (~29s). `core.hooksPath` is pointed at a tracked `.githooks/`
directory by an idempotent installer that `make` invokes, so any clone that builds
once is gated without anyone reading a setup doc.

## Considered options

Agent hooks in `.claude/settings.json` were the incumbent — the clean-build gate
lived there. They were rejected because they guard only work done *through the
agent*, and they identify a commit by regex-matching a command string rather than
observing the commit itself. Three of them had also been registered against a
`Bash` matcher on a machine configured to use the PowerShell tool, so they had
never fired at all; a mechanism whose failure mode is total silence is the wrong
place for a gate.

Adding a `windows-latest` CI job was originally scoped out in favour of the local
gate catching Windows-only breakage. That reasoning was inverted: the local gate
catches Windows defects only because the developer happens to be on Windows, which
stops being true the moment work is produced elsewhere. CI now covers both
platforms, and the local hooks were re-justified on speed alone.

Putting the clean build on `pre-commit` alongside the tool suite was rejected
because commits are frequent and pushes are rare, and this project already mandates
a clean build immediately before push — a `pre-push` hook makes an existing rule
enforceable instead of duplicating work at every commit.

## Consequences

`make` writes to git config. A build having a side effect on repository
configuration is unusual and deliberate: it is the only way the gate is on by
default rather than opt-in, and this repository has already lost four months to a
gate nobody ran. The write is local-scope, idempotent, and undone with a single
`git config --unset core.hooksPath`.

The repo settings tier no longer holds *all* hook wiring — only agent hook wiring.
Gate wiring now lives in two places, which is why `CONTEXT.md` distinguishes an
agent hook from a repository hook.

`--no-verify` still bypasses both hooks. That is acceptable precisely because CI is
the authority; a bypassed local hook costs a round-trip, not correctness.
