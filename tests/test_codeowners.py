import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from codeowners import CodeOwners  # noqa: E402

# Shaped like a real monorepo CODEOWNERS file.
SAMPLE = """
# comment line, ignored
*.md                                 @acme/docs

/libs/orders/checkout-feature    @acme/platform
/libs/orders/common              @acme/platform @acme/payments
/libs/search/module                     @acme/search
/code/modules/Invoices/         @acme/platform
/code/Acme.Rest/Orders         @acme/platform

# last match wins, so this narrows the rule above it
/libs/orders/checkout-feature/src/legacy   @acme/payments
"""


class TestCodeOwners(unittest.TestCase):
    def setUp(self):
        self.co = CodeOwners(SAMPLE)

    def test_anchored_prefix_match(self):
        pattern, owners = self.co.owners_of(
            "libs/orders/checkout-feature/src/cart/CartView.tsx")
        self.assertEqual(pattern, "/libs/orders/checkout-feature")
        self.assertEqual(owners, ["@acme/platform"])

    def test_last_match_wins(self):
        # The legacy rule appears after the broader one, so it takes precedence.
        _, owners = self.co.owners_of(
            "libs/orders/checkout-feature/src/legacy/Old.tsx")
        self.assertEqual(owners, ["@acme/payments"])

    def test_trailing_slash_matches_only_below(self):
        _, owners = self.co.owners_of(
            "code/modules/Invoices/Acme.Invoices/Entities/Line.cs")
        self.assertEqual(owners, ["@acme/platform"])
        _, none = self.co.owners_of("code/modules/InvoicesOther/Thing.cs")
        self.assertEqual(none, [])

    def test_unanchored_pattern_matches_any_depth(self):
        self.assertEqual(self.co.owners_of("README.md")[1], ["@acme/docs"])
        self.assertEqual(self.co.owners_of("docs/deep/nested.md")[1], ["@acme/docs"])

    def test_multiple_owners(self):
        _, owners = self.co.owners_of("libs/orders/common/src/index.ts")
        self.assertEqual(owners, ["@acme/platform", "@acme/payments"])

    def test_unowned_path(self):
        self.assertEqual(self.co.owners_of("public/locales/da.json"), (None, []))

    def test_other_team_path_is_not_ours(self):
        # The regression that matters: an in-scope repo PR in someone else's area.
        hits = self.co.matched_by(
            ["libs/search/module/src/components/chat/message/MessageList.tsx"],
            "@acme/platform")
        self.assertEqual(hits, {})

    def test_matched_by_reports_patterns_and_files(self):
        hits = self.co.matched_by([
            "libs/orders/checkout-feature/src/a.tsx",
            "code/modules/Invoices/b.cs",
            "public/locales/da.json",
        ], "@acme/platform")
        self.assertEqual(sorted(hits.keys()),
                         ["/code/modules/Invoices/",
                          "/libs/orders/checkout-feature"])

    def test_owner_match_is_case_insensitive(self):
        hits = self.co.matched_by(
            ["libs/orders/checkout-feature/src/a.tsx"], "@Acme/PLATFORM")
        self.assertTrue(hits)

    def test_malformed_lines_are_skipped(self):
        co = CodeOwners("/no/owners/here\n[[[bad-glob   @acme/platform\n/ok @acme/platform")
        self.assertEqual(co.owners_of("ok/file.txt")[1], ["@acme/platform"])


if __name__ == "__main__":
    unittest.main()
