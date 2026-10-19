"""Regression tests for ruleset *content* invariants.

``test_auto_update_ai.py`` mostly exercises the sync machinery.  This module
pins down guarantees about the committed rulesets themselves and about the
truncated-entry guard, so a future regeneration cannot quietly reintroduce a
dead host or a malformed changelog row.

Run with the standard library only::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import ai_rules_catalog as catalog  # noqa: E402
import auto_update_ai as aua  # noqa: E402

RULESET_DIRS = ("loon", "surge", "shadowrocket", "qx", "clash", "v2ray")
RULESETS = ("AI-Overseas", "AI-Domestic")


def _changelog_rows(text: str) -> list[str]:
    """Return the generated changelog rows (``| `YYYY-MM-DD` | ...``)."""
    return [
        line
        for line in text.splitlines()
        if re.match(r"^\| `\d{4}-\d{2}-\d{2}` \|", line)
    ]


class TruncatedHostGuardTests(unittest.TestCase):
    """``accounts.google`` is a truncated ``accounts.google.com``, not a host."""

    TRUNCATED = ("accounts.google", "gemini.google", "oauth2.googleapis")

    def test_truncated_hosts_are_flagged(self):
        for domain in self.TRUNCATED:
            with self.subTest(domain=domain):
                self.assertNotEqual(aua.plausible_host_errors(domain), [])

    def test_truncated_host_blocks_a_run(self):
        errors = aua.validate_ruleset("AI-Overseas", {"accounts.google"}).errors
        self.assertEqual(len(errors), 1)
        self.assertIn("accounts.google", errors[0])

    def test_real_google_brand_tld_host_still_allowed(self):
        """``antigravity.google`` is a live host under Google's brand TLD."""
        self.assertEqual(aua.plausible_host_errors("antigravity.google"), [])
        self.assertEqual(aua.validate_ruleset("AI-Overseas", {"antigravity.google"}).errors, [])
        self.assertEqual(aua.plausible_host_errors("antigravity-unleash.goog"), [])

    def test_unverified_brand_tld_host_is_rejected(self):
        """Only verified brand-TLD hosts pass; others are probable truncations."""
        self.assertEqual(aua.plausible_host_errors("gemini.google"), [
            "'gemini.google' ends in Google's brand TLD; the real host is "
            "gemini.google.com -- did the parser truncate it?"
        ])
        self.assertNotEqual(aua.plausible_host_errors("something.google"), [])

    def test_truncated_hosts_are_dropped_when_sanitizing(self):
        result = aua.sanitize_domains(set(self.TRUNCATED) | {"accounts.google.com"})
        self.assertEqual(result.removed_malformed, sorted(self.TRUNCATED))
        self.assertIn("accounts.google.com", result.kept)

    def test_catalog_contains_no_truncated_hosts(self):
        for label, providers in (("overseas", catalog.OVERSEAS_PROVIDERS),
                                 ("domestic", catalog.DOMESTIC_PROVIDERS)):
            for provider, domains in providers.items():
                for domain in domains:
                    with self.subTest(ruleset=label, provider=provider, domain=domain):
                        self.assertEqual(aua.plausible_host_errors(domain), [])


class CommittedRulesetTests(unittest.TestCase):
    """Guarantees about the files that are actually served to clients."""

    def test_no_shared_cdn_root_is_routed(self):
        for name in RULESETS:
            for relative, domains in aua.load_client_domains(REPO_ROOT, name).items():
                for domain in domains:
                    with self.subTest(file=relative, domain=domain):
                        self.assertNotIn(domain, catalog.SHARED_CDN_ROOTS)

    def test_no_truncated_hosts_are_served(self):
        for name in RULESETS:
            for relative, domains in aua.load_client_domains(REPO_ROOT, name).items():
                for domain in domains:
                    with self.subTest(file=relative, domain=domain):
                        self.assertEqual(aua.plausible_host_errors(domain), [])

    def test_committed_rulesets_are_up_to_date(self):
        """``--check`` must pass, i.e. the files match what the script renders."""
        result = aua.run(REPO_ROOT, offline=True, check=True, logger=lambda *_a, **_k: None)
        self.assertEqual(result.exit_code, 0, result.report.get("check"))

    def test_gemini_fix_from_branch_is_still_served(self):
        """The original point of this branch must reach every client."""
        served = aua.load_client_domains(REPO_ROOT, "AI-Overseas")
        for domain in (
            "gemini.google.com",
            "generativelanguage.googleapis.com",
            "aistudio.google.com",
            "aiplatform.googleapis.com",
        ):
            for relative, domains in served.items():
                with self.subTest(file=relative, domain=domain):
                    self.assertIn(domain, domains)

    def test_header_domain_count_matches_body(self):
        for name in RULESETS:
            per_client = aua.load_client_domains(REPO_ROOT, name)
            for relative, domains in per_client.items():
                path = REPO_ROOT / relative
                header = re.search(
                    r"^#\s*Total Domains:\s*(\d+)$",
                    path.read_text(encoding="utf-8"),
                    re.MULTILINE,
                )
                if header is None:
                    continue
                with self.subTest(file=relative):
                    self.assertEqual(int(header.group(1)), len(domains),
                                     f"{relative} header count is stale")


class ChangelogTests(unittest.TestCase):
    """The README changelog must gain at most one row per date."""

    def _readme(self) -> str:
        return (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    def test_exactly_one_generated_row_per_date(self):
        """Each date may have at most one row per generator label.

        ``2026-10-18`` legitimately carries both an ``🤖 自动同步`` row and a
        ``🚀 初始化上线`` row, so uniqueness is per (date, label).
        """
        seen: dict[tuple[str, str], int] = {}
        for row in _changelog_rows(self._readme()):
            date = re.match(r"^\| `(\d{4}-\d{2}-\d{2})`", row).group(1)
            label = row.split("|")[2].strip()
            seen[(date, label)] = seen.get((date, label), 0) + 1
        duplicates = {k: v for k, v in seen.items() if v > 1}
        self.assertEqual(duplicates, {}, f"duplicate dated rows: {duplicates}")

    def test_no_row_is_added_when_nothing_was_added(self):
        text = self._readme()
        with tempfile.TemporaryDirectory() as tmp:
            readme = Path(tmp) / "README.md"
            readme.write_text(text, encoding="utf-8")
            before = _changelog_rows(text)
            # Same day, no new domains, no platforms -> nothing to record.
            after_text, inserted = aua.update_changelog(
                text, "2099-01-01", [], {"AI-Overseas": [], "AI-Domestic": []}
            )
            self.assertFalse(inserted)
            self.assertEqual(after_text, text)
            self.assertEqual(_changelog_rows(after_text), before)

    def test_second_row_for_same_date_is_refused(self):
        text = self._readme()
        existing = re.search(r"^\| `(\d{4}-\d{2}-\d{2})` \| 🤖", text, re.MULTILINE)
        self.assertIsNotNone(existing, "expected an auto-generated row to test against")
        today = existing.group(1)
        # A different generator label for the same date must still be refused.
        marker = f"| `{today}` | 🤖 **自动同步** |"
        self.assertIn(marker, text)
        updated, inserted = aua.update_changelog(
            text, today, ["openai"], {"AI-Overseas": ["example.com"], "AI-Domestic": []}
        )
        self.assertFalse(inserted)
        self.assertEqual(updated, text)

    def test_new_date_gets_exactly_one_new_row(self):
        text = self._readme()
        # Strip every existing row for the target date so the insert is real.
        target = "2099-02-02"
        updated, inserted = aua.update_changelog(
            text, target, ["openai"], {"AI-Overseas": ["example.com"], "AI-Domestic": []}
        )
        self.assertTrue(inserted)
        added_rows = [r for r in _changelog_rows(updated)
                      if r.startswith(f"| `{target}`")]
        self.assertEqual(len(added_rows), 1)
        self.assertEqual(_changelog_rows(updated)[0], added_rows[0], "row must be newest-first")
        # And a further run for the same date must not duplicate it.
        again, inserted_again = aua.update_changelog(
            updated, target, ["openai"], {"AI-Overseas": ["example.com"], "AI-Domestic": []}
        )
        self.assertFalse(inserted_again)
        self.assertEqual(again, updated)


class WorkflowArtifactTests(unittest.TestCase):
    """Guard the workflow contract that the audit report depends on."""

    WORKFLOW = REPO_ROOT / ".github" / "workflows" / "sync-ai-leaderboard.yml"

    def test_workflow_passes_audit_report_flag(self):
        text = self.WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("--audit-report", text)
        self.assertIn("upload-artifact", text)

    def test_workflow_runs_the_test_suite(self):
        text = self.WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("unittest discover -s tests", text)


if __name__ == "__main__":
    unittest.main()
