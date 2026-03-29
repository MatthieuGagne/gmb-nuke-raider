#!/usr/bin/env bash
# compare_prs.sh <PR_NUMBER>
# Checks out a PR into an isolated worktree, clean-builds the ROM.
# Prints ROM path on success, build error on failure. Exits 0/1.

set -euo pipefail

if [ -z "${1:-}" ]; then
  echo "Usage: compare_prs.sh <PR_NUMBER>" >&2
  exit 1
fi

PR="$1"
WORKTREE_DIR="/tmp/pr-compare-${PR}"
REPO_ROOT="$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)"

trap 'git -C "$REPO_ROOT" worktree remove --force "$WORKTREE_DIR" 2>/dev/null || true' EXIT

# Clean up any stale worktree for this PR
if [ -d "$WORKTREE_DIR" ]; then
  git -C "$REPO_ROOT" worktree remove --force "$WORKTREE_DIR" 2>/dev/null || true
  rm -rf "$WORKTREE_DIR"
fi

# Create worktree and checkout PR branch
git -C "$REPO_ROOT" worktree add "$WORKTREE_DIR" HEAD
cd "$WORKTREE_DIR"

# Fetch and checkout the PR branch into the worktree
gh pr checkout "$PR" --repo MatthieuGagne/gmb-nuke-raider 2>/dev/null || {
  echo "ERROR: Could not checkout PR #${PR}" >&2
  exit 1
}

# Verify CWD is the worktree directory (safety check)
ACTUAL_DIR="$(pwd)"
if [ "$ACTUAL_DIR" != "$WORKTREE_DIR" ]; then
  echo "ERROR: CWD mismatch — expected $WORKTREE_DIR, got $ACTUAL_DIR" >&2
  exit 1
fi

# Clean build
if make clean && GBDK_HOME=/home/mathdaman/gbdk make; then
  trap - EXIT
  echo "ROM:${WORKTREE_DIR}/build/nuke-raider.gb"
  exit 0
else
  echo "ERROR: Build failed for PR #${PR}" >&2
  exit 1
fi
