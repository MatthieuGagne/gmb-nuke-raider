/**
 * Deny gate — refuse operations that must never happen in this repo (ADR 443).
 *
 * omp equivalent of the `.pi/settings.json` PreToolUse entry matching
 * `bash|powershell`. omp exposes a single shell tool, `bash`, and
 * `tools/deny_gate_hook.py` already folds tool names to lowercase, so the
 * lowercase spelling reaches the same code path Claude Code's `Bash` does.
 */
import type { HookAPI } from "@oh-my-pi/pi-coding-agent/extensibility/hooks";
import { runPythonHook } from "../lib/py.ts";

export default function (pi: HookAPI): void {
	pi.on("tool_call", async (event, ctx) => {
		if (event.toolName !== "bash") return;

		const res = runPythonHook(
			"deny_gate_hook.py",
			event.toolName,
			event.input,
			ctx.cwd,
		);
		if (!res.blocked) return;

		return {
			block: true,
			reason: res.stderr || "Refused by the deny gate.",
		};
	});
}
