# Three-tier Claude settings with a two-layer deny gate

Status: accepted

Claude settings had accreted into a single tracked `.claude/settings.local.json`
carrying 159 allow rules — 49 of them wildcard-free one-shots that can never
match again, 30 embedding machine-specific absolute paths — plus environment
values and hook registrations. We split it into three tiers: a machine tier
outside the repository for per-computer values, a tracked repo tier holding the
curated allowlist, the deny list and all hook wiring, and an untracked scratch
tier for transient approvals. New permissions are promoted deliberately as
generalized rules or discarded; they are never accumulated.

## Considered options

**Deny rules alone.** Claude Code matches Bash rules by string prefix, so
`Bash(git push --force:*)` stops `git push --force origin x` but not
`git push -f`, not a trailing `--force`, and not `bash -c "git push --force"`.
A deny list alone documents intent without enforcing it.

**A deny hook alone.** Enforces reliably, but leaves nothing behind if the hook
is disabled or its script fails.

**Both, split by conditionality (chosen).** `permissions.deny` carries only
operations that are never legitimate here — force push, pushing to the default
branch, merging a PR — as a backstop that survives a broken hook.
`tools/deny_gate_hook.py` scans the raw command string of both shell tools,
catching spellings and wrapper invocations prefix rules miss. The hook adds a
second rule set — worktree removal, branch deletion, hard reset — that is
active only when `NUKE_FACTORY_RUN` is set, because those operations are
legitimate when a human is driving and forbidden to an unattended run. A deny
rule cannot express that distinction; a hook can.

## Consequences

The allowlist grammar is deliberately narrow: one canonical rule form per tool
(`Bash(prefix:*)`, `PowerShell(prefix *)`). This is not style enforcement. The
coverage check must decide whether a command is permitted, and a checker that
approximates Claude Code's full matching semantics can report coverage the real
harness will not honour. Constraining the grammar makes the checker exact over
the file it reads, moving the approximation out of the tool and into a lint rule.

Hook commands invoke their scripts by repo-relative path so a worktree runs its
own copy — previously they were pinned into the main working tree, meaning a
branch that modified a hook script tested the new script while the old one
actually executed. Because the working directory can drift, the scripts also
re-root themselves from the hook payload rather than trusting it.

The deny gate's guarantee is asserted for the permission modes this project
uses. Hooks fire regardless of permission mode, so the hook layer — not the
deny list — is what holds under a permissive mode.

Curation is lossy on purpose. A genuinely needed rule that was dropped
re-prompts once and is then promoted; the pre-migration file remains in git
history if a dropped rule needs to be recovered.
