---
name: triage-reviews
description: |
  TRIGGER: "triage reviews", "triage my reviews", "what needs my review", "review queue", /triage-reviews.
  SKIP: reviewing, fixing, or watching CI on one specific PR; any org other than the one in config/config.json.
version: 1.0.0
---

One pass over every open PR authored by your team (set in `config/config.json`), raising the ones that need your
review, including the ones nobody assigned to you.

## Prerequisites

- `gh` authenticated as the reviewer (`gh auth status`).
- This skill installed by `install.sh`, which symlinks it from the review-triage repo.
- Nothing else. The fetch script re-reads team membership and CODEOWNERS itself.

The scripts live in that repo, not the current one, so start every script command with
`R="$(cd "$(readlink ~/.claude/skills/triage-reviews)/../.." && pwd)";` and call them as
`"$R"/bin/<script>`. Shell state does not carry between commands, so repeat the prefix.

## Steps

### 1. Fetch and bucket

Run `"$R"/bin/review-triage-fetch`. Do **not** pass `--commit-state` yet; a
dry run leaves the nag counters untouched in case the pass is abandoned.

When the user asks for "today's digest" rather than a fresh pass, print
`~/.claude/triage/digest-<YYYY-MM-DD>.md` for today if it exists and stop there.

The JSON hands you four ordered lists (`raised`, `deferred`, `covered`, `mine`) plus totals. The
buckets are already decided; do not re-derive them:

- `assigned`: review requested from you or from the team in the JSON's `team` field, and your last review
  predates the current head.
- `owned`: touches a path CODEOWNERS assigns to the configured `owner_ref`, and no human has
  approved yet. CodeRabbit and Copilot do not count as humans.
- `covered`: in scope but already approved, already reviewed by you at this head, or
  snoozed.
- `mine`: you have commits on the branch, so it is yours to get reviewed rather than yours
  to review. Never raised. Report it only as a count.

### 2. Read the diffs, but only for what is raised

For each entry in `raised` (never for `covered` or `deferred`), read the diff:

```
gh pr diff <url>
```

Prefer `owned_files` over the full file list when the diff is large: those are the paths
that put the PR in your queue in the first place.

Write exactly two lines per PR:

1. **What it does.** One sentence, in plain terms, from the diff and not from the title.
2. **Why it wants your eyes.** The concrete hook: which owned path, a migration or DB
   patch, locale churn, a public contract change, no reviewer yet, or a risky area.

Flag it when the diff contradicts the title, and say so in line 2.

### 3. Render the digest

Print to the terminal in this shape. Keep it terse; it is a queue, not a report.

```
review queue                               20 open · 3 need you · 2026-09-21 09:02

ASSIGNED TO YOU
  web#1214  teammate-a  3 files  7d old
    Adds an error message for when an order number sequence runs out.
    Requested you directly. Touches checkout-feature plus both locale files.

YOURS BY OWNERSHIP
  web#1203  teammate-b  7 files  +182/-10  4d old  (3rd time)
    Editable note field in the order details sidebar.
    checkout-feature and order-history are team paths. Only CodeRabbit has looked.

COVERED (3)      web#1265, web#1188, api#4463
MINE (1)         web#1190  (you have commits on that branch)
OUT OF SCOPE (14) docs 3, e2e-tests 2, infra 2, …
DEFERRED (0)     nothing past the 10-per-day cap
```

Rules for the render:

- Append `(Nth time)` when `times_raised >= 2`, so a PR that keeps resurfacing reads as a
  nag rather than as news.
- Append `(new commits since you last saw it)` when `new_since_last_raise` is true.
- Print `DEFERRED (n)` **always**, even at zero, so the daily cap can never trim the list
  invisibly.
- Collapse `covered`, `mine` and out-of-scope to one line each. Never expand them unasked.
  Omit the `MINE` line entirely when the count is zero.

### 4. Persist

Write the rendered digest to `~/.claude/triage/digest-<YYYY-MM-DD>.md`, then run
`"$R"/bin/review-triage-fetch --commit-state` so the state file and the statusline badge agree
with what you just showed.

### 5. Offer one next step

End with a single line offering the most useful follow-up, usually reviewing the top PR. Do
not offer more than one.

On a yes, hand the review to a general-purpose subagent so the diff stays out of this
context. Brief it with the PR URL, the two digest lines, and `owned_files`, and ask for
correctness and risk findings ranked by severity, read-only, nothing posted to GitHub.

When a PR is finished mid-session and you offer the next one, prefix the offer with a one-line
queue status (done, remaining, and which is next). Handle the queue in stated priority order:
direct requests first, then list order.

## Snoozing

When the user dismisses a PR ("not mine", "skip that one"), run:

```
"$R"/bin/review-triage-snooze <repo>#<number> <days> "<reason>"
```

That drops it from the raised set immediately and keeps it out until the date passes.

## Examples

- "triage reviews": full pass, fresh fetch, render, persist.
- "what needs my review today": same, but read today's digest file first if it exists.
- "triage reviews, skip web": full pass, then leave `web` out of the rendered
  output and say what you filtered. Skip `--commit-state`: the hidden PRs were not shown.
