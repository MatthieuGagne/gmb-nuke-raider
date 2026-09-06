#!/usr/bin/env bash
# compare_prs.sh <PR_NUMBER>
# Checks out a PR into an isolated temporary checkout (a shared clone — never
# `git worktree`, which is reserved for Orca on this machine), clean-builds the ROM.
# Prints ROM path on success, build error on failure. Exits 0/1.

set -euo pipefail

if [ -z "${1:-}" ]; then
  echo "Usage: compare_prs.sh <PR_NUMBER>" >&2
  exit 1
fi

PR="$1"
CHECKOUT_DIR="/tmp/pr-compare-${PR}"
REPO_ROOT="$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)"

trap 'rm -rf "$CHECKOUT_DIR"' EXIT

# Clean up any stale checkout for this PR
rm -rf "$CHECKOUT_DIR"

# Create a shared clone (no worktree involvement, cleanup is a plain delete)
git clone --shared --no-checkout "$REPO_ROOT" "$CHECKOUT_DIR"
cd "$CHECKOUT_DIR"

# Fetch and checkout the PR branch into the checkout
gh pr checkout "$PR" --repo MatthieuGagne/gmb-nuke-raider 2>/dev/null || {
  echo "ERROR: Could not checkout PR #${PR}" >&2
  exit 1
}

# Verify CWD is the checkout directory (safety check)
ACTUAL_DIR="$(pwd)"
if [ "$ACTUAL_DIR" != "$CHECKOUT_DIR" ]; then
  echo "ERROR: CWD mismatch — expected $CHECKOUT_DIR, got $ACTUAL_DIR" >&2
  exit 1
fi

# Clean build
if make clean && GBDK_HOME=/home/mathdaman/gbdk make; then
  trap - EXIT
  echo "ROM:${CHECKOUT_DIR}/build/nuke-raider.gb"
  exit 0
else
  echo "ERROR: Build failed for PR #${PR}" >&2
  exit 1
fi
