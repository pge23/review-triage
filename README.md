# review-triage

One pass over every open pull request authored by your team, raising the ones that
need your review, including the ones nobody assigned to you.

GitHub can tell you when someone requests your review. It cannot tell you that a teammate
just touched a module you own and pulled in three reviewers who have not looked at it. That
second case is most of the problem, so this does the judgment GitHub will not.

## What it produces

```
review queue                               20 open · 3 need you · 2026-09-21 09:02

ASSIGNED TO YOU
  web#1214  teammate-a  3 files  7d old
    Adds an error message for when an order number sequence runs out.
    Requested you directly. Touches checkout-feature plus both locale files.

YOURS BY OWNERSHIP
  web#1203  teammate-b  7 files  +182/-10  4d old
    Editable note field in the order details sidebar.
    checkout-feature and order-history are team paths. Only CodeRabbit has looked.

  api#4506  teammate-c  8 files  +148/-9  2d old
    Partial refunds in the order refunds endpoint.
    Invoices module plus a DB migration. Five reviewers requested, none has reviewed.

COVERED (3)      web#1265, web#1188, api#4463
OUT OF SCOPE (14) docs 3, e2e-tests 2, infra 2, …
DEFERRED (0)     nothing past the 10-per-day cap
```

## How it decides

Three buckets, all mechanical, all decided in `bin/review-triage-fetch`:

| Bucket | Rule |
| --- | --- |
| **Assigned to you** | Review requested from you or from your team, and your last review predates the current head SHA. |
| **Yours by ownership** | Touches a path CODEOWNERS assigns to your team, and no human has approved yet. CodeRabbit and Copilot are not humans. |
| **Covered** | In scope, but already approved, already reviewed by you at this head, or snoozed. Collapsed to a count. |
| **Mine** | You have commits on the branch, so it is yours to get reviewed, not yours to review. Never raised. |

Filters applied before any of that:

- **Open only.** The search is `is:pr is:open draft:false`.
- **Scoped repos.** Only the repos in `scope_repos`. Everything else is counted, never
  raised. Each one needs a CODEOWNERS entry for `owner_ref`, so one ownership rule covers all.
- **Not yours.** The author list is the live team roster minus your own login, and any PR
  with commits by you is filtered out too, which catches branches you pushed to or
  co-authored rather than opened.
- **Not scratch.** Titles matching `DO NOT MERGE`, `WIP` and similar are dropped and listed.
- **Ten per day.** A ceiling, not a quota. Slots are never backfilled with out-of-scope PRs.
  Overflow is recorded as deferred and comes back with priority, and `DEFERRED (n)` is
  always printed so the cap cannot trim the list invisibly.

Ownership filtering does real work rather than just narrowing by repo. A PR that
touches only paths another team owns drops out, even though it is a teammate's PR in a
scoped repo.

## Architecture

Three layers, split so the expensive part runs rarely and the visible part is free.

| Layer | What | Cost |
| --- | --- | --- |
| Statusline badge | `bin/review-triage-status` renders ` rev:3` from the state file, cached with stale-while-revalidate so a slow `gh` call never blocks a render. | No LLM, always on |
| Triage pass | `skills/triage-reviews/SKILL.md` drives `bin/review-triage-fetch`, reads the diffs of raised PRs only, renders and persists the digest. | One LLM pass, on demand |
| Monday refresh | `bin/review-triage-cron` under launchd at Monday 09:00. Runs the mechanical pass only, so the badge is already accurate when the week starts. | No LLM |

```
bin/review-triage-fetch   fetch, filter, bucket, rank, cap, emit JSON, write state
bin/review-triage-status  statusline badge from the state file
bin/review-triage-snooze  silence a PR for N days
bin/review-triage-cron    scheduled mechanical refresh, run by launchd
launchd/                  plist template for the Monday job
lib/codeowners.py         CODEOWNERS matcher, gitignore-like, last match wins
config/config.json        team, scope repos, cap, title filters, paths
skills/triage-reviews/    the skill that does the judgment
```

## Install

**Configure first.** `config/config.json` ships with placeholders. Set `org`, `team`,
`owner_ref` and `scope_repos` before running `install.sh`. Your GitHub login
comes from `gh auth`, so there is nothing to set for it.

```sh
git clone <repo-url> review-triage
cd review-triage
./install.sh
```

`install.sh` symlinks the skill into `~/.claude/skills/` and prints how to show the badge:
a `statusLine` entry for `~/.claude/settings.json`, or the call to add to the statusline
script you already have. It changes nothing else and is safe to re-run.

## Use

```sh
/triage-reviews                            # full pass in Claude Code
./bin/review-triage-fetch                  # raw JSON, state untouched
./bin/review-triage-fetch --commit-state   # same, then record what was raised
./bin/review-triage-fetch --no-cache       # bypass cached roster, CODEOWNERS, file lists
./bin/review-triage-snooze web#1203 14 "waiting on design"
./bin/review-triage-snooze --list
./bin/review-triage-status --plain         # what the statusline shows
```

## The Monday refresh

```sh
./install-cron.sh install     # load the launchd job, Monday 09:00
./install-cron.sh status      # loaded? last exit code? last few runs?
./install-cron.sh run-now     # fire it immediately
./install-cron.sh uninstall
```

launchd rather than crontab, because if the Mac is asleep at 09:00 the job runs on wake,
which is what "when you start work" actually means. cron would skip it.

The scheduled run does the **mechanical pass only**: search, filter, bucket, cap, write
state, refresh badge. It uses `--refresh-only`, so it never increments the nag counter;
that counter means "times the user was shown this PR", and a background run shows nobody
anything. Writing the per-PR digest is a judgment pass and stays interactive: when the
badge shows a number, run `/triage-reviews`.

To make it every weekday instead of Mondays, replace the single `Weekday` integer in
`launchd/local.review-triage.plist.template` with an array of dicts, one per day, then
re-run `./install-cron.sh install`.

Logs: `~/.claude/triage/cron.log`, plus `cron.out.log` and `cron.err.log` from launchd.

State lives at `~/.claude/triage/state.json`, digests at
`~/.claude/triage/digest-<date>.md`, caches at `~/.claude/cache/review-triage/`. Nothing is
written inside this repo at runtime.

## Tuning it

Most changes are config, not code:

- Another team: `org`, `team` and `owner_ref`.
- Another repo in scope: add to `scope_repos`. It needs a CODEOWNERS entry for `owner_ref`
  or every PR there lands in `covered`.
- Noisier or quieter: `daily_cap`.
- New scratch-PR pattern: `exclude_title_patterns`, lowercase regex.

Code changes worth making next are in `TODO.md`. The main one: a team owns more paths than
any one member reviews, so if the ownership bucket runs long, weight matched paths by whether
you have commits in them.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

25 tests, no network. `test_codeowners.py` covers the matcher, where a silent failure looks
like an empty queue rather than an error. `test_buckets.py` covers the bucketing rules with
the GitHub calls stubbed: bot approvals not counting as human, a stale review of yours not
covering a newer head, and your own commits winning over ownership. State tests cover the
scheduled refresh leaving nag counts and last-seen SHAs alone.

Next steps live in `TODO.md`, ordered by value.
