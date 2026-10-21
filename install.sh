#!/bin/bash
# Wire this repo into Claude Code. Idempotent and safe to re-run: it symlinks the skill and
# prints the statusline snippet rather than editing your statusline for you.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS="$HOME/.claude/skills"
LINK="$SKILLS/triage-reviews"

mkdir -p "$SKILLS" "$HOME/.claude/triage" "$HOME/.claude/cache/review-triage"

# 1. Skill symlink, so edits in the repo take effect without reinstalling.
if [ -L "$LINK" ]; then
  ln -sfn "$REPO/skills/triage-reviews" "$LINK"
  echo "updated symlink  $LINK"
elif [ -e "$LINK" ]; then
  echo "SKIP  $LINK exists and is not a symlink. Move it aside and re-run."
else
  ln -s "$REPO/skills/triage-reviews" "$LINK"
  echo "linked           $LINK -> $REPO/skills/triage-reviews"
fi

# 2. Statusline: print, do not patch. Editing someone's statusline behind their back is
#    how you end up with a broken prompt and no idea why.
SETTINGS="$HOME/.claude/settings.json"
BADGE="$REPO/bin/review-triage-status"
echo
# Separate calls: BSD grep -r skips a symlinked dir when it is not the only operand.
if grep -qs "review-triage-status" "$SETTINGS" || grep -rqs "review-triage-status" "$HOME/.claude/scripts/"; then
  echo "Statusline already wired up."
elif grep -qs '"statusLine"' "$SETTINGS"; then
  cat <<EOF
You already have a statusline. To show the badge, call this from the script that
$SETTINGS points statusLine at, and append its output to what it prints:

  "$BADGE"

It renders " rev:3" when PRs are waiting and nothing when the queue is clear.
EOF
else
  cat <<EOF
To show the badge as your statusline, add this to $SETTINGS:

  "statusLine": { "type": "command", "command": "$BADGE" }

It renders " rev:3" when PRs are waiting and nothing when the queue is clear.
EOF
fi

echo
echo "Verify with:"
echo "  python3 -m unittest discover -s $REPO/tests"
echo "  $REPO/bin/review-triage-fetch | head -20"
echo "  /triage-reviews          (in Claude Code, after a session restart)"
