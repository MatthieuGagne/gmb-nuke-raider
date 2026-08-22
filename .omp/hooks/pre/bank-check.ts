/**
 * Bank pre-write gate — validate the bank manifest before any `src/*.{c,h}` write.
 *
 * omp equivalent of the `.pi/settings.json` PreToolUse entry matching
 * `write|edit`. The payload is passed through untouched: `tools/bank_check_hook.py`
 * reads `file_path` first and falls back to `path`, which covers both spellings
 * without this wrapper having to know which key omp's edit tool uses.
 */
import type { HookAPI } from "@oh-my-pi/pi-coding-agent/extensibility/hooks";
import { runPythonHook } from "../lib/py.ts";

const WRITE_TOOLS = new Set(["write", "edit"]);

export default function (pi: HookAPI): void {
	pi.on("tool_call", async (event, ctx) => {
		if (!WRITE_TOOLS.has(event.toolName)) return;

		const res = runPythonHook(
			"bank_check_hook.py",
			event.toolName,
			event.input,
			ctx.cwd,
		);
		if (!res.blocked) return;

		return {
			block: true,
			reason: res.stderr || "Refused by the bank pre-write gate.",
		};
	});
}
