/**
 * Emulicious window placement — rewrite the emulator's saved window geometry
 * before a ROM launch.
 *
 * Cosmetic only. `tools/emulicious_window_hook.py` always exits 0 and swallows
 * its own OSErrors, so this wrapper never blocks; it is registered on
 * `tool_call` purely to run before the launch command executes.
 */
import type { HookAPI } from "@oh-my-pi/pi-coding-agent/extensibility/hooks";
import { runPythonHook } from "../lib/py.ts";

export default function (pi: HookAPI): void {
	pi.on("tool_call", async (event, ctx) => {
		if (event.toolName !== "bash") return;

		runPythonHook(
			"emulicious_window_hook.py",
			event.toolName,
			event.input,
			ctx.cwd,
		);
		// No return value: this hook must never block a launch.
	});
}
