# Nuke Raider

Shared vocabulary for this repository. Definitions only — no implementation
detail, no decisions. Decisions live in `docs/adr/`; requirements live in
GitHub issues.

## Language

### Agent settings & permissions

**Machine tier**:
The per-machine settings layer, outside the repository, holding values that are
true of this computer rather than of the project.
_Avoid_: user settings, global settings, local settings

**Repo tier**:
The tracked settings layer inside the repository, holding the curated
allowlist, the deny list, and all hook wiring.
_Avoid_: project settings, shared settings

**Scratch tier**:
The untracked settings layer inside the repository, holding transient
session-granted approvals that are never committed.
_Avoid_: local settings, settings.local

**Promotion**:
Deliberately rewriting a transient approval as a generalized rule in the repo
tier. The only sanctioned route from the scratch tier into version control.
_Avoid_: saving a permission, persisting a permission

**Allow rule**:
A single permission pattern granting a class of tool invocations.
_Avoid_: permission, allowlist entry, grant

**Canonical form**:
The one rule spelling each tool is permitted to use, so that a single intent
cannot be written two ways.
_Avoid_: rule format, syntax

**Deny gate**:
The pair of mechanisms that refuse forbidden operations regardless of what any
allow rule permits.
_Avoid_: blocklist, denylist, guard

**Unconditional rule**:
A deny rule for an operation that is never legitimate in this repository.
_Avoid_: hard deny, global deny

**Factory-gated rule**:
A deny rule for an operation that is legitimate when a human is driving and
forbidden to an unattended run.
_Avoid_: soft deny, conditional deny

**Coverage inventory**:
The checked-in record of the commands this project's automated stages and gate
sequence issue, against which the allowlist is validated.
_Avoid_: command list, fixture, manifest

**Self-rooting hook**:
A hook script that locates the repository root from its own invocation context
rather than trusting the working directory it inherits.
_Avoid_: relative hook, portable hook
