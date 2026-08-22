/**
 * Bridge from omp's TS hook API to this repo's Python hook scripts.
 *
 * The scripts in `tools/*_hook.py` speak the Claude Code hook protocol: a JSON
 * payload on stdin with `tool_name`, `tool_input` and `cwd`, and an exit code
 * that decides the verdict. omp has no declarative hook config — hooks are TS
 * factories discovered under `.omp/hooks/pre/*.ts` — so each script gets a thin
 * wrapper module that calls through here.
 *
 * Exit-code contract, unchanged from the other two harnesses: **2 blocks**, and
 * any other non-zero code is surfaced but does not block. Every hook in this
 * repo fails open on unparseable input, so a bridge failure (no interpreter,
 * spawn error) must allow the call rather than wedge the session.
 */
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

export interface PyHookResult {
	/** Script exited 2 — the tool call must not proceed. */
	blocked: boolean;
	/** Text to show as the block reason, or as surfaced hook output. */
	stderr: string;
	stdout: string;
}

const ALLOW: PyHookResult = { blocked: false, stderr: "", stdout: "" };

/**
 * Walk up from `start` to the nearest directory holding a `.git` entry.
 *
 * Mirrors `hook_common.find_repo_root`. In a worktree `.git` is a file rather
 * than a directory, so `existsSync` is the right test — not `isDirectory`.
 */
export function findRepoRoot(start: string): string | null {
	let dir = resolve(start);
	for (;;) {
		if (existsSync(join(dir, ".git"))) return dir;
		const parent = dirname(dir);
		if (parent === dir) return null;
		dir = parent;
	}
}

/**
 * Run `tools/<script>` with a Claude-Code-shaped payload on stdin.
 *
 * `cwd` is the session's working directory. It is passed through in the payload
 * so the script's own `hook_common.reroot()` lands on the same repo root this
 * function resolved — the anchor locates the script, the payload locates the work.
 */
export function runPythonHook(
	script: string,
	toolName: string,
	input: Record<string, unknown> | undefined,
	cwd: string,
): PyHookResult {
	const root = findRepoRoot(cwd);
	if (!root) return ALLOW; // outside a checkout — nothing to gate

	const scriptPath = join(root, "tools", script);
	if (!existsSync(scriptPath)) return ALLOW; // hook not present on this branch

	const payload = JSON.stringify({
		tool_name: toolName,
		tool_input: input ?? {},
		cwd,
	});

	const res = spawnSync("python", [scriptPath], {
		input: payload,
		encoding: "utf8",
		cwd: root,
	});

	// No interpreter, or the spawn itself failed: fail open, like the scripts do.
	if (res.error || res.status === null) return ALLOW;

	return {
		blocked: res.status === 2,
		stderr: (res.stderr ?? "").trim(),
		stdout: (res.stdout ?? "").trim(),
	};
}

/** Not a hook. Exported so a stray loader that imports this file gets a no-op. */
export default function (): void {}
