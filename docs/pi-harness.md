# Pi harness

Imported by [`CLAUDE.md`](../CLAUDE.md). Relevant only when running the Pi coding agent (`pi`);
under Claude Code none of this applies.

`.pi/settings.json` exposes the same project skills and agents to the Pi coding agent
(`pi`), so a session started there is not flying blind. It wires `skills: ["../.claude/skills"]`
(all 18 project skills), the `pi-subagents` and `@hsingjui/pi-hooks` packages, and the four
portable hooks with Pi's lowercase tool matchers (`bash|powershell`, `write|edit`). `.pi/agents/*.md` are
thin wrappers: each carries Pi-native frontmatter and tells the child to read the matching
`.claude/agents/<name>.md` and follow it, so persona text lives in exactly one place.

**One-time step:** run `pi` from the repo root and accept the `/trust` prompt. Untrusted, Pi
loads none of the above.

**Gates that do not exist under Pi** — assume they are absent, do not rely on them:
- `tools/skill_overlay_hook.py` — not ported. Both halves are Claude-shaped: the `PostToolUse`
  half matches a `Skill` tool Pi does not have, and the `UserPromptSubmit` half parses `/<name>`
  while Pi registers skills as `/skill:<name>`. **Skill overlays never inject under Pi**, so a
  project delta in `.claude/skill-overlays/` is silently missing — read it yourself.
- `tools/factory_permission_hook.py` — not ported. It is a `Notification` hook and pi-hooks
  exposes no `Notification` event, so factory's permission-escalation path is unguarded.
- **The `pwsh-*` background-job tools are ungated** (#572). `@marcfargas/pi-powershell` registers
  `pwsh-start-job` and friends alongside the shell tools; those names match no hook matcher, so
  a command run through a job bypasses the deny gate, the Emulicious window hook and the
  post-build memory check. Widening the matchers is not enough for the deny gate: it filters
  again internally on `SHELL_TOOLS` in `tools/deny_gate_hook.py`, which admits only `bash` /
  `powershell` (either case). Run builds and pushes through the shell tool, not a job.

Also note the deny gate and bank check must exit **2** to block; under pi-hooks any other
non-zero exit is reported as a hook error and the tool call proceeds anyway.

The matchers are regex, not exact strings — pi-hooks does `new RegExp(matcher).test(toolName)`
(`@hsingjui/pi-hooks`, `src/config.ts` `matcherMatches`) — which is what lets one matcher name
both shell tools.

**The two harnesses anchor their hook commands differently, and the Pi anchor is the weaker of
the two.** `.claude/settings.json` uses Claude Code's `${CLAUDE_PROJECT_DIR}` placeholder;
`.pi/settings.json` uses the bash-evaluated
`$(git rev-parse --show-toplevel 2>/dev/null || echo .)`. That is not a stylistic difference:
pi-hooks (0.0.2) substitutes no placeholders and runs every hook command under `bash -c`, so
`${CLAUDE_PROJECT_DIR}` in `.pi/settings.json` would be expanded by bash as an undefined
variable and every Pi hook would resolve to `python "/tools/<name>.py"` — broken from every
directory, repository root included. The coverage is not equal either: the Claude placeholder
resolves from any working directory, while the Pi expression resolves only from a working
directory inside the repository. Outside one, `git rev-parse` fails and the `|| echo .` fallback
degrades the command to the pre-existing relative path rather than to `/tools/<name>.py`.
**Do not copy either form into the other file.**

Pi shell setup is **machine-local**, deliberately not committed: the build needs PowerShell,
`GBDK_HOME`, and Git's `bin`/`usr\bin` on `PATH`, and pointing Pi's `shellPath` at them takes
absolute paths. Configure that in `~/.pi/agent/settings.json`, not here.
