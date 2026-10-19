"""Regression tests for scripts/auto_update_ai.py and scripts/ai_rules_catalog.py.

Run with the standard library only (no third-party test dependency):

    python -m unittest discover -s tests -v

Every test that touches the filesystem works on a temporary copy of the
repository layout, so the real rulesets are never modified.
"""

from __future__ import annotations

import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import ai_rules_catalog as catalog  # noqa: E402
import auto_update_ai as aua  # noqa: E402

RULESET_DIRS = ("loon", "surge", "shadowrocket", "qx", "clash", "v2ray")
RULESETS = ("AI-Overseas", "AI-Domestic")


def _quiet(*_args, **_kwargs) -> None:
    """Logger that keeps test output readable."""


class TempRepo:
    """Temporary repository holding copies of the existing rulesets."""

    def __init__(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.path = Path(self._dir.name)
        for directory in RULESET_DIRS:
            src = REPO_ROOT / directory
            if src.is_dir():
                shutil.copytree(src, self.path / directory)
        readme = REPO_ROOT / "README.md"
        if readme.exists():
            shutil.copy2(readme, self.path / "README.md")

    def __enter__(self) -> Path:
        return self.path

    def __exit__(self, *_exc) -> None:
        self._dir.cleanup()

def _raise_offline(*_args, **_kwargs):
    raise urllib.error.URLError("simulated network failure")


# ---------------------------------------------------------------------------
# Catalogue / shared-CDN policy
# ---------------------------------------------------------------------------


class SharedCdnPolicyTests(unittest.TestCase):
    def test_shared_roots_are_rejected_outright(self):
        for root in ("googleapis.com", "gstatic.com", "googleusercontent.com", "amazonaws.com"):
            with self.subTest(root=root):
                self.assertTrue(aua.is_shared_root_domain(root))
                errors = aua.validate_ruleset("AI-Overseas", {root}).errors
                self.assertEqual(len(errors), 1)
                self.assertIn("shared", errors[0])

    def test_audited_gemini_hosts_are_allowed(self):
        """The fix this branch exists for must survive validation."""
        allowed = {
            "gemini.google.com",
            "generativelanguage.googleapis.com",
            "aiplatform.googleapis.com",
            "cloudcode-pa.googleapis.com",
            "lh3.googleusercontent.com",
            "clients6.google.com",
            "accounts.google.com",
            "dashscope.aliyuncs.com",
        }
        for domain in allowed:
            with self.subTest(domain=domain):
                self.assertIn(domain, catalog.SHARED_ROOT_EXCEPTIONS)
                self.assertEqual(aua.validate_ruleset("AI-Overseas", {domain}).errors, [])

    def test_unaudited_subdomain_of_shared_root_is_rejected(self):
        errors = aua.validate_ruleset("AI-Overseas", {"foo.amazonaws.com"}).errors
        self.assertEqual(len(errors), 1)
        self.assertIn("foo.amazonaws.com", errors[0])
        self.assertIn("amazonaws.com", errors[0])

    def test_exceptions_are_derived_not_hand_maintained(self):
        """Every exception must be a catalogued, documented, non-root host."""
        for domain in catalog.SHARED_ROOT_EXCEPTIONS:
            with self.subTest(domain=domain):
                self.assertNotIn(domain, catalog.SHARED_CDN_ROOTS)
                self.assertIn(domain, catalog.OFFICIAL_SOURCES)
                self.assertTrue(
                    any(domain in v for v in catalog.OVERSEAS_PROVIDERS.values())
                    or any(domain in v for v in catalog.DOMESTIC_PROVIDERS.values())
                )


class CatalogueIntegrityTests(unittest.TestCase):
    def test_every_catalogued_domain_has_provenance(self):
        result = aua.validate_catalog_provenance()
        self.assertEqual(result.errors, [])

    def test_no_domain_in_both_routing_classes(self):
        overseas = {d for v in catalog.OVERSEAS_PROVIDERS.values() for d in v}
        domestic = {d for v in catalog.DOMESTIC_PROVIDERS.values() for d in v}
        self.assertEqual(overseas & domestic, set())
        self.assertEqual(aua.validate_no_conflicts(overseas, domestic).errors, [])

    def test_aliases_point_at_real_providers(self):
        known = set(catalog.OVERSEAS_PROVIDERS) | set(catalog.DOMESTIC_PROVIDERS)
        dangling = {alias: target for alias, target in catalog.PROVIDER_ALIASES.items()
                    if target not in known}
        self.assertEqual(dangling, {})

    def test_alias_keys_are_sane_slugs(self):
        for alias in catalog.PROVIDER_ALIASES:
            with self.subTest(alias=alias):
                self.assertRegex(alias, r"^[a-z0-9][a-z0-9_-]*$")

    def test_provenance_has_no_stale_entries(self):
        guided = {d for v in catalog.OVERSEAS_PROVIDERS.values() for d in v}
        guided |= {d for v in catalog.DOMESTIC_PROVIDERS.values() for d in v}
        stale = sorted(set(catalog.OFFICIAL_SOURCES) - guided)
        self.assertEqual(stale, [])

    def test_gemini_domains_remain_covered(self):
        google = set(catalog.OVERSEAS_PROVIDERS["google"])
        for domain in (
            "gemini.google.com",
            "generativelanguage.googleapis.com",
            "aistudio.google.com",
            "antigravity.google",
            "lh3.googleusercontent.com",
        ):
            with self.subTest(domain=domain):
                self.assertIn(domain, google)


# ---------------------------------------------------------------------------
# Parsing / round-trip
# ---------------------------------------------------------------------------


class ParsingTests(unittest.TestCase):
    def test_clash_quoted_form_round_trips(self):
        """A generated clash file must parse back to the same domain set."""
        domains = {"gemini.google.com", "lh3.googleusercontent.com"}
        rendered = aua.render("AI-Overseas", domains, "clash")
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "AI-Overseas.yaml"
            target.write_text(rendered, encoding="utf-8")
            self.assertEqual(aua.read_domains(target), domains)

    def test_clash_unquoted_form_still_parses(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "x.yaml"
            target.write_text("payload:\n  - '+.a.com'\n  - +.b.com\n  - \"+ .c.com\"\n", encoding="utf-8")
            self.assertEqual(aua.read_domains(target), {"a.com", "b.com", "c.com"})

    def test_all_client_formats_round_trip(self):
        domains = {"gemini.google.com", "claude.ai", "dashscope.aliyuncs.com"}
        with tempfile.TemporaryDirectory() as tmp:
            for fmt in ("domain-suffix", "host-suffix", "domain", "clash"):
                with self.subTest(fmt=fmt):
                    target = Path(tmp) / f"out-{fmt}"
                    target.write_text(aua.render("AI-Overseas", domains, fmt), encoding="utf-8")
                    self.assertEqual(aua.read_domains(target), domains)

    def test_comments_and_blank_lines_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "x.list"
            target.write_text("# header\n\nDOMAIN-SUFFIX,a.com # trailing\n", encoding="utf-8")
            self.assertEqual(aua.read_domains(target), {"a.com"})

    def test_missing_file_reads_as_empty(self):
        self.assertEqual(aua.read_domains(Path("/nonexistent/never.list")), set())

    def test_repository_rulesets_are_self_consistent(self):
        """All six clients of each ruleset must agree today (catches silent drift)."""
        for name in RULESETS:
            with self.subTest(ruleset=name):
                per_client = aua.load_client_domains(REPO_ROOT, name)
                self.assertTrue(per_client)
                base = None
                for relative, domains in per_client.items():
                    self.assertTrue(domains, f"{relative} parsed as empty")
                    if base is None:
                        base = domains
                    else:
                        self.assertEqual(domains, base, f"{relative} drifted from {name}")


# ---------------------------------------------------------------------------
# Orchestration: safety guarantees
# ---------------------------------------------------------------------------


class RunSafetyTests(unittest.TestCase):
    def test_check_mode_never_writes(self):
        with TempRepo() as repo:
            before = _snapshot(repo)
            result = aua.run(repo, offline=True, check=True, logger=_quiet)
            self.assertIn(result.exit_code, (0, 1))
            self.assertEqual(_snapshot(repo), before)

    def test_dry_run_never_writes(self):
        with TempRepo() as repo:
            before = _snapshot(repo)
            result = aua.run(repo, offline=True, dry_run=True, logger=_quiet)
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(_snapshot(repo), before)

    def test_failed_fetch_aborts_without_writing(self):
        with TempRepo() as repo:
            before = _snapshot(repo)
            result = aua.run(repo, opener=_raise_offline, logger=_quiet)
            self.assertEqual(result.exit_code, 2)
            self.assertEqual(result.status, "fetch_failed")
            self.assertEqual(_snapshot(repo), before)
            self.assertIn("nothing was written", result.report["error"])

    def test_partial_fetch_keeps_existing_domains(self):
        with TempRepo() as repo:
            preserved = aua.load_existing_domains(repo, "AI-Overseas")
            result = aua.run(repo, opener=_raise_offline, allow_partial_fetch=True,
                             no_changelog=True, logger=_quiet)
            self.assertEqual(result.status, "ok_with_fetch_errors")
            after = aua.load_existing_domains(repo, "AI-Overseas")
            # Manually maintained hosts outside shared roots must survive.
            manual = {d for d in preserved if aua.sanitize_domains({d}).kept}
            self.assertTrue(manual <= after, f"dropped: {sorted(manual - after)}")

    def test_shared_roots_are_removed_by_sync(self):
        with TempRepo() as repo:
            loon = repo / "loon/AI-Overseas.list"
            loon.write_text(
                loon.read_text(encoding="utf-8") + "DOMAIN-SUFFIX,googleapis.com\n",
                encoding="utf-8",
            )
            result = aua.run(repo, offline=True, no_changelog=True, logger=_quiet)
            self.assertEqual(result.exit_code, 0)
            self.assertIn("googleapis.com", result.report["removed_shared_roots"]["AI-Overseas"])
            self.assertNotIn("googleapis.com", aua.load_existing_domains(repo, "AI-Overseas"))

    def test_run_is_idempotent(self):
        with TempRepo() as repo:
            first = aua.run(repo, offline=True, no_changelog=True, logger=_quiet)
            self.assertEqual(first.exit_code, 0)
            snapshot = _snapshot(repo)
            second = aua.run(repo, offline=True, no_changelog=True, logger=_quiet)
            self.assertEqual(second.changed_files, [])
            self.assertEqual(_snapshot(repo), snapshot)
            checked = aua.run(repo, offline=True, check=True, logger=_quiet)
            self.assertEqual(checked.exit_code, 0, checked.report.get("check"))

    def test_generated_files_pass_post_validation(self):
        with TempRepo() as repo:
            result = aua.run(repo, offline=True, no_changelog=True, logger=_quiet)
            self.assertEqual(result.exit_code, 0)
            self.assertTrue(result.report["post_validation"]["ok"],
                            result.report["post_validation"]["errors"])

    def test_conflict_between_rulesets_blocks_writes(self):
        """A DIRECT host that also matches a proxied parent must abort (exit 3)."""
        with TempRepo() as repo:
            loon = repo / "loon/AI-Domestic.list"
            loon.write_text(
                loon.read_text(encoding="utf-8") + "DOMAIN-SUFFIX,claude.ai\n",
                encoding="utf-8",
            )
            before = _snapshot(repo)
            result = aua.run(repo, offline=True, no_changelog=True, logger=_quiet)
            self.assertEqual(result.exit_code, 3)
            self.assertEqual(result.status, "validation_failed")
            self.assertEqual(_snapshot(repo), before)

    def test_invalid_domain_blocks_writes(self):
        """A malformed domain must never be silently dropped from a ruleset."""
        with TempRepo() as repo:
            loon = repo / "loon/AI-Overseas.list"
            loon.write_text(
                loon.read_text(encoding="utf-8") + "DOMAIN-SUFFIX,not a domain\n",
                encoding="utf-8",
            )
            before = _snapshot(repo)
            result = aua.run(repo, offline=True, no_changelog=True, logger=_quiet)
            self.assertEqual(result.exit_code, 3)
            self.assertEqual(result.status, "validation_failed")
            self.assertTrue(result.report.get("unparsable_rules"))
            self.assertEqual(_snapshot(repo), before)

    def test_invalid_domain_is_rejected_by_validator(self):
        errors = aua.validate_ruleset("AI-Overseas", {"bad domain"}).errors
        self.assertEqual(len(errors), 1)
        self.assertIn("invalid domain", errors[0])

    def test_changelog_only_records_when_domains_added(self):
        with TempRepo() as repo:
            readme = repo / "README.md"
            text = readme.read_text(encoding="utf-8")
            original_rows = text.count("| `")
            aua.run(repo, offline=True, logger=_quiet)
            first_rows = readme.read_text(encoding="utf-8").count("| `")
            aua.run(repo, offline=True, logger=_quiet)  # second run adds nothing
            second_rows = readme.read_text(encoding="utf-8").count("| `")
            self.assertGreaterEqual(first_rows, 1)
            self.assertGreater(first_rows, 0, "changelog table rows expected")
            self.assertEqual(second_rows, first_rows, "duplicate changelog row written")
            self.assertGreaterEqual(first_rows, 0)
            self.assertGreater(original_rows, 0)

    def test_no_changelog_flag_leaves_readme_untouched(self):
        with TempRepo() as repo:
            readme = repo / "README.md"
            before = readme.read_bytes()
            aua.run(repo, offline=True, no_changelog=True, logger=_quiet)
            self.assertEqual(readme.read_bytes(), before)


# Byte-level snapshot of a directory tree, used to prove "nothing was written".
def _snapshot(path: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(path)): p.read_bytes()
        for p in sorted(path.rglob("*"))
        if p.is_file()
    }


# ---------------------------------------------------------------------------
# Transactional writes
# ---------------------------------------------------------------------------


class FileTransactionTests(unittest.TestCase):
    def test_stage_reports_unchanged_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "a.txt"
            target.write_text("hello\n", encoding="utf-8")
            tx = aua.FileTransaction()
            self.assertFalse(tx.stage(target, "hello\n"))
            self.assertEqual(tx.changed, [])

    def test_rollback_restores_original_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "a.txt"
            target.write_text("original\n", encoding="utf-8")
            tx = aua.FileTransaction()
            tx.stage(target, "updated\n")
            tx.commit()
            self.assertEqual(target.read_text(encoding="utf-8"), "updated\n")
            tx.rollback()
            self.assertEqual(target.read_text(encoding="utf-8"), "original\n")

    def test_rollback_removes_files_that_did_not_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "sub" / "new.txt"
            tx = aua.FileTransaction()
            tx.stage(target, "created\n")
            tx.commit()
            self.assertTrue(target.exists())
            tx.rollback()
            self.assertFalse(target.exists())

    def test_failed_commit_leaves_no_partial_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.txt"
            good.write_text("orig\n", encoding="utf-8")
            bad = Path(tmp) / "mkdir_target" / "file.txt"
            (Path(tmp) / "mkdir_target").write_text("i am a file\n", encoding="utf-8")
            tx = aua.FileTransaction()
            tx.stage(good, "changed\n")
            tx.stage(bad, "nope\n")
            with self.assertRaises(Exception):
                tx.commit()
            self.assertEqual(good.read_text(encoding="utf-8"), "orig\n")

    def test_no_temp_files_left_behind(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "a.txt"
            tx = aua.FileTransaction()
            tx.stage(target, "x\n")
            tx.commit()
            leftovers = [p.name for p in Path(tmp).iterdir() if p.name.endswith(".tmp")]
            self.assertEqual(leftovers, [])


# ---------------------------------------------------------------------------
# CLI contract used by the workflow
# ---------------------------------------------------------------------------


class CliTests(unittest.TestCase):
    def _run_main(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = aua.main(argv, opener=_raise_offline, logger=_quiet)
        return code, buf.getvalue()

    def test_exit_code_2_on_fetch_failure(self):
        with TempRepo() as repo:
            code, _ = self._run_main(["--base-dir", str(repo)])
            self.assertEqual(code, 2)

    def test_dry_run_exit_code_0(self):
        with TempRepo() as repo:
            code, _ = self._run_main(["--base-dir", str(repo), "--offline", "--dry-run"])
            self.assertEqual(code, 0)

    def test_audit_report_written_as_valid_json(self):
        with TempRepo() as repo, tempfile.TemporaryDirectory() as out:
            report = Path(out) / "reports" / "audit.json"
            code, _ = self._run_main(
                ["--base-dir", str(repo), "--offline", "--check", "--audit-report", str(report)]
            )
            self.assertIn(code, (0, 1))
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertIn("status", payload)
            self.assertIn("validation", payload)

    def test_audit_status_line_is_emitted(self):
        with TempRepo() as repo:
            buf = io.StringIO()
            with redirect_stdout(buf):
                aua.main(["--base-dir", str(repo), "--offline", "--dry-run"])
            self.assertIn("AUDIT_STATUS=", buf.getvalue())


# ---------------------------------------------------------------------------
# Workflow security
# ---------------------------------------------------------------------------

YAML_OK = importlib.util.find_spec("yaml") is not None


@unittest.skipUnless(YAML_OK, "PyYAML not installed")
class WorkflowSecurityTests(unittest.TestCase):
    WORKFLOW = REPO_ROOT / ".github" / "workflows" / "sync-ai-leaderboard.yml"

    def setUp(self):
        import yaml

        self.text = self.WORKFLOW.read_text(encoding="utf-8")
        self.data = yaml.safe_load(self.text)

    def test_workflow_never_pushes_directly_to_main(self):
        self.assertNotRegex(self.text, r"git\s+push[^\n]*\bmain\b")
        self.assertNotRegex(self.text, r"git\s+push\s+origin\s+main")

    def test_workflow_opens_pull_request(self):
        self.assertRegex(self.text, r"gh\s+pr\s+create")
        self.assertNotIn("pull_request_target", self.text)

    def test_permissions_are_least_privilege(self):
        perms = self.data.get("permissions") or {}
        self.assertEqual(perms.get("contents"), "read")
        self.assertEqual(perms.get("pull-requests"), "write")
        self.assertNotEqual(perms.get("contents"), "write")

    def test_top_level_permissions_deny_by_default(self):
        perms = self.data.get("permissions") or {}
        self.assertNotEqual(perms.get("contents"), "write")

    def test_no_untrusted_input_in_run_blocks(self):
        """``github.event.*`` payloads must never be interpolated into shell."""
        for step in self.data["jobs"]["update-rules"]["steps"]:
            script = step.get("run") or ""
            self.assertNotIn("${{ github.event.", script)
            self.assertNotIn("${{ inputs.", script)

    def test_workflow_avoids_behavioral_opt_ins_to_drift(self):
        self.assertNotIn("continue-on-error: true", self.text)

    def test_workflow_has_concurrency_guard(self):
        self.assertIn("concurrency", self.data)

    def test_checkout_does_not_persist_credentials(self):
        steps = self.data["jobs"]["update-rules"]["steps"]
        checkouts = [s for s in steps if str(s.get("uses", "")).startswith("actions/checkout")]
        self.assertTrue(checkouts, "checkout step missing")
        self.assertIs(checkouts[0]["with"]["persist-credentials"], False)


if __name__ == "__main__":
    unittest.main()
