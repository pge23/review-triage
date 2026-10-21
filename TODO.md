# TODO

Ordered by value. Each item says what is wrong now, not just what to build.

## 1. Weight owned paths by whether the reviewer has commits in them

The badge over-reports. A team owns more paths than any one member reviews, so a
one-line locale string and a DB view alter both land in the same count, and only
running the skill tells them apart. Ownership is currently team-wide and binary.

Fix: for each path that matched a CODEOWNERS rule, check whether the reviewer has commits in it
(`git log --author=<login> -- <path>` against a local clone, or the GitHub commits API), and
use that to rank within the owned bucket, or to demote a PR out of it entirely. A three-line locale change would then
stop counting toward the badge.

Needs a decision first: demote, or just rank lower? Demoting risks missing a new file in an
area the reviewer owns but has never touched.

## 2. Warn on CODEOWNERS drift

Paths get renamed and an ownership rule silently stops matching. The failure looks like an
empty queue, not an error, which is the worst shape a bug can take here.

Fix: record how many paths each `owner_ref` rule matched on the last run, and flag it in
the digest when a rule that used to match goes to zero, or when `owner_ref` matches nothing
at all in a repo that is in scope.

## 3. Say something when a scoped repo has no CODEOWNERS entry

Add a repo to `scope_repos` without an `owner_ref` entry in its CODEOWNERS and every PR
there lands in `covered` with no explanation. Should be a loud warning at fetch time.

## 4. Snooze by author or path, not just by PR

Snoozing is per PR, so a teammate doing a long series of PRs in an area the reviewer does not care about
has to be snoozed one at a time.

## 5. Diff against the previous digest

"What changed since Monday" is the question after the first read of the week. The state file
already has the head SHAs to answer it; nothing renders it yet.

## 6. Optional pre-baked digest

The Monday job is mechanical only, so the badge is fresh but the write-ups are not. A
headless `claude -p "/triage-reviews"` would pre-bake them. Deliberately not the default: an
unattended LLM pass reading diffs weekly is cost nobody asked for. Add behind an explicit
flag in `install-cron.sh` if it turns out to be wanted.
