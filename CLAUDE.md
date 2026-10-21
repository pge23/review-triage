# CLAUDE.md

Context for working on this repo. Read `README.md` first for what the tool does; this file is
about how to change it without breaking it.

## What this is

A review-queue triage tool for one reviewer, whoever `gh` is authenticated as, reviewing PRs
from the team in `config/config.json`. Each user runs their
own clone. Not a library, not a service, not multi-user. Keep it that size.

## The one design rule

**Mechanical decisions go in `bin/review-triage-fetch`. Judgment goes in the skill.**

Bucketing, ranking, the daily cap, dedup, snoozing and the CODEOWNERS match are all
deterministic, so they are Python and they are testable. Reading a diff and saying why it
wants a human's attention is not deterministic, so it lives in
`skills/triage-reviews/SKILL.md` and costs tokens.

When adding a feature, decide which side of that line it falls on first. If you can write an
assertion for it, it does not belong in the skill.

## Layout

```
bin/review-triage-fetch   the whole pipeline: search, filter, bucket, rank, cap, emit, persist
bin/review-triage-status  statusline badge, bash, no LLM
bin/review-triage-snooze  snooze/list/clear, bash
bin/review-triage-cron    scheduled mechanical refresh, run by launchd on Monday 09:00
launchd/                  plist template, installed by install-cron.sh
lib/codeowners.py         CODEOWNERS matcher, the only non-trivial logic
config/config.json        everything tunable
skills/triage-reviews/    the LLM pass
tests/                    unittest, no dependencies
```

## Invariants

Breaking any of these is a bug even if nothing errors:

1. **Never write inside this repo at runtime.** State goes to `~/.claude/triage/`, caches to
   `~/.claude/cache/review-triage/`. A clone stays clean.
2. **A dry run must not mutate state.** `--commit-state` is the only thing that writes the
   state file. The skill commits state only after it has rendered the digest.
3. **Deferred PRs never increment `times`.** That counter exists to distinguish a nag from
   news; counting a PR the user never saw would corrupt it.
4. **`DEFERRED (n)` is always printed, even at zero.** A silent cap hides work, which is the
   exact failure this tool exists to prevent.
5. **Team membership is read live, never hardcoded.** Joiners and leavers must land for free.
   The cache TTL is fine; a literal list of logins is not.
6. **A branch the reviewer touched is never raised.** The search excludes PRs they authored;
   `commit_actors` excludes PRs they have any commit on. Both matter: reviewers push to
   teammates' branches. These land in the `mine` bucket rather than vanishing, so the count stays
   auditable.
7. **Bots are not humans.** `BOTS` in `review-triage-fetch` gates the "no human approval"
   test. A CodeRabbit approval must never mark a PR covered.
8. **The scheduled run is mechanical only.** `review-triage-cron` uses `--refresh-only` and
   never invokes an LLM. Two reasons: `times` counts how often the user was actually shown
   a PR, and an unattended agent reading diffs on a schedule is a cost and a trust problem
   nobody asked for. If a pre-baked digest is ever wanted, it should be the user's explicit
   opt-in, not a default.
9. **The statusline never blocks.** `review-triage-status` renders from cache and refreshes in
   a background subshell. Never add a synchronous `gh` call to the render path.

## Working on the CODEOWNERS matcher

`lib/codeowners.py` implements gitignore-like semantics with **last match wins**, which is
GitHub's rule and the opposite of first-match intuition. Two details that are easy to get
wrong:

- A pattern with no slash (`*.md`) matches at any depth. A pattern with a slash
  (`/libs/foo`) is anchored.
- A trailing slash (`/code/modules/Invoices/`) matches only things under the directory.

Change this file and run the tests. A regression here does not raise an error; it silently
empties the ownership bucket, which reads as "nothing needs my review today".

## Testing

```sh
python3 -m unittest discover -s tests -v     # unit tests, no network
./bin/review-triage-fetch | python3 -m json.tool | head -40   # live smoke test
```

`tests/test_buckets.py` loads `bin/review-triage-fetch` through a `SourceFileLoader` (it has
no `.py` extension) and stubs `changed_paths` and `commit_actors`, so bucketing is testable
offline. Add a case there for any new rule.

There is no mock for the GitHub search itself. The live smoke test is the integration test: check that
`totals.in_scope` is plausible and that a PR you know is out of your area lands in `covered`
rather than `raised`.

A good signal the ownership rule works: a team PR that touches only paths another team owns
lands in `covered`, not `raised`.

## Conventions

- Python 3 standard library only. No dependencies, no virtualenv, no package manifest.
- Bash for anything the statusline touches, Python for anything with branching logic.
- Single-line comments explaining **why**, not what. No comment blocks.
- No em-dashes or en-dashes anywhere, including code comments and commit messages.
- `gh` is the only GitHub interface. No raw curl, no PATs in config.

## Next steps

`TODO.md`, ordered by value, with the current state of each problem rather than just a
label. The highest-value one: a team owns more
paths than any one reviewer actually reviews, so if the ownership bucket runs long, weight matched
paths by whether the reviewer has commits in them rather than tightening the repo scope further.
