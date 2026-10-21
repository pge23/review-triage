"""Bucketing tests. The GitHub calls inside classify() are stubbed, so these run offline."""

import importlib.machinery
import importlib.util
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from codeowners import CodeOwners  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
# The script has no .py extension, so it needs an explicit source loader.
_path = os.path.join(ROOT, "bin", "review-triage-fetch")
spec = importlib.util.spec_from_loader(
    "triage", importlib.machinery.SourceFileLoader("triage", _path))
triage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(triage)

CO = CodeOwners("/libs/orders/checkout-feature @acme/platform\n/libs/search/module @acme/search")
CFG = {"team": "platform", "org": "acme"}
ME = "reviewer"
NOW = datetime.now(timezone.utc)


def iso(delta_hours=0):
    return (NOW + timedelta(hours=delta_hours)).isoformat().replace("+00:00", "Z")


def make_pr(requested=(), reviews=(), number=1):
    return {
        "number": number, "title": "ABC-1 thing", "url": "u", "headRefOid": "deadbeefcafe",
        "createdAt": iso(-72), "updatedAt": iso(-2), "additions": 10, "deletions": 1,
        "changedFiles": 2, "author": {"login": "teammate-b"},
        "repository": {"name": "web"},
        "commits": {"nodes": [{"commit": {"pushedDate": iso(-24), "committedDate": iso(-24)}}]},
        "reviewRequests": {"nodes": [
            {"requestedReviewer": {"__typename": "User", "login": r}} if not r.startswith("team:")
            else {"requestedReviewer": {"__typename": "Team", "slug": r[5:]}}
            for r in requested]},
        "reviews": {"nodes": list(reviews)},
    }


def review(login, state, hours_ago):
    return {"author": {"login": login}, "state": state, "submittedAt": iso(-hours_ago)}


class TestBuckets(unittest.TestCase):
    def setUp(self):
        self._paths = ["libs/orders/checkout-feature/src/a.tsx"]
        self._actors = ["teammate-b", "web-flow"]
        triage.changed_paths = lambda *a, **k: self._paths
        triage.commit_actors = lambda *a, **k: self._actors

    def classify(self, pr):
        return triage.classify(pr, CFG, ME, "@acme/platform", CO, ".github/CODEOWNERS", False)

    def test_review_requested_from_me_is_assigned(self):
        self.assertEqual(self.classify(make_pr(requested=["reviewer"]))["bucket"], "assigned")

    def test_review_requested_from_my_team_is_assigned(self):
        self.assertEqual(self.classify(make_pr(requested=["team:platform"]))["bucket"], "assigned")

    def test_owned_path_with_no_human_approval_is_owned(self):
        self.assertEqual(self.classify(make_pr())["bucket"], "owned")

    def test_bot_approval_does_not_cover_a_pr(self):
        pr = make_pr(reviews=[review("coderabbitai", "APPROVED", 5)])
        self.assertEqual(self.classify(pr)["bucket"], "owned")

    def test_human_approval_covers_a_pr(self):
        pr = make_pr(reviews=[review("teammate-c", "APPROVED", 5)])
        self.assertEqual(self.classify(pr)["bucket"], "covered")

    def test_my_review_at_current_head_covers_it(self):
        pr = make_pr(reviews=[review("reviewer", "COMMENTED", 2)])
        self.assertEqual(self.classify(pr)["bucket"], "covered")

    def test_my_stale_review_does_not_cover_a_newer_head(self):
        pr = make_pr(reviews=[review("reviewer", "COMMENTED", 48)])
        self.assertEqual(self.classify(pr)["bucket"], "owned")

    def test_unowned_path_is_covered(self):
        self._paths = ["libs/search/module/src/a.tsx"]
        self.assertEqual(self.classify(make_pr())["bucket"], "covered")

    def test_my_commits_on_the_branch_make_it_mine(self):
        # A branch the reviewer pushed to is theirs to get reviewed, not theirs to review.
        self._actors = ["teammate-b", "reviewer"]
        item = self.classify(make_pr(requested=["reviewer"]))
        self.assertEqual(item["bucket"], "mine")
        self.assertIn("you have commits on this branch", item["reasons"])

    def test_my_commits_win_over_ownership(self):
        self._actors = ["reviewer"]
        self.assertEqual(self.classify(make_pr())["bucket"], "mine")

    def test_commit_actor_match_is_case_insensitive(self):
        self._actors = ["REVIEWER"]
        self.assertEqual(self.classify(make_pr())["bucket"], "mine")


class TestStateUpdate(unittest.TestCase):
    ITEM = {"id": "web#1", "head_sha": "new"}
    PRIOR = {"web#1": {"sha": "old", "first_raised": "2026-10-01",
                          "last_raised": "2026-10-01", "times": 1}}

    def test_refresh_keeps_the_sha_the_user_last_saw(self):
        entry = triage.next_raised(self.PRIOR, [self.ITEM], "2026-10-19", shown=False)["web#1"]
        self.assertEqual((entry["sha"], entry["times"]), ("old", 1))
        self.assertTrue(triage.new_since_seen(entry, "new"))

    def test_shown_run_records_the_new_sha_and_counts_a_nag(self):
        entry = triage.next_raised(self.PRIOR, [self.ITEM], "2026-10-19", shown=True)["web#1"]
        self.assertEqual((entry["sha"], entry["times"]), ("new", 2))
        self.assertEqual(entry["first_raised"], "2026-10-01")

    def test_pr_only_ever_refreshed_is_not_new_since_seen(self):
        entry = triage.next_raised({}, [self.ITEM], "2026-10-19", shown=False)["web#1"]
        self.assertEqual((entry["sha"], entry["times"], entry["first_raised"]), (None, 0, None))
        self.assertFalse(triage.new_since_seen(entry, "new"))

    def test_first_shown_run_sets_first_raised(self):
        entry = triage.next_raised({}, [self.ITEM], "2026-10-19", shown=True)["web#1"]
        self.assertEqual((entry["first_raised"], entry["times"]), ("2026-10-19", 1))


if __name__ == "__main__":
    unittest.main()
