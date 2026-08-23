/**
 * Post-build gates — run `make bank-post-build` then `make memory-check` after
 * a build command, and surface their output to the agent.
 *
 * omp equivalent of the `.pi/settings.json` PostToolUse entry matching
 * `bash|powershell`. `tools/post_build_hook.py` decides for itself whether the
 * command was a build (it looks for `make` and applies its own skip pattern),
 * so this wrapper forwards every successful `bash` result and lets the script
 * filter.
 *
 * The script reports budget failures on stdout rather than by exit code, and
 * `tool_result` cannot block a call that already ran — so the output is appended
 * to the tool result instead. A FAIL is therefore visible to the agent, not
 * enforced against it; the smoketest gate in CLAUDE.md is what stops the push.
 */
import type { HookAPI } from "@oh-my-pi/pi-coding-agent/extensibility/hooks";
import { runPythonHook } from "../lib/py.ts";

export default function (pi: HookAPI): void {
	pi.on("tool_result", async (event, ctx) => {
		if (event.toolName !== "bash" || event.isError) return;

		const res = runPythonHook(
			"post_build_hook.py",
			event.toolName,
			event.input,
			ctx.cwd,
		);

		const report = [res.stdout, res.stderr].filter(Boolean).join("\n").trim();
		if (!report) return; // not a build command, or nothing to say

		return {
			content: [...event.content, { type: "text", text: report }],
		};
	});
}
