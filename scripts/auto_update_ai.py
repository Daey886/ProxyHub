#!/usr/bin/env python3
"""ProxyHub AI ruleset generator: audit + auto-sync, safe by design.

Responsibilities
----------------
1. Discover *activity* from official public APIs (OpenRouter models, Hugging
   Face trending models) -- read-only, best-effort.
2. Combine the curated catalogue (``scripts/ai_rules_catalog.py``) with every
   domain already present in the repository, so human-maintained domains are
   never dropped by an automatic sync.
3. Validate the combined set (syntax, forbidden shared-CDN roots, overseas
   vs. DIRECT conflicts) *before* touching any file.
4. Write all six client formats atomically and then verify that the generated
   clients are mutually consistent.
5. Print a JSON audit report; optionally write it to ``--audit-report``.

Safety guarantees
-----------------
* A failed discovery fetch never leads to a write.  By default the whole run
  aborts (exit code 2) with every generated file untouched.  With
  ``--allow-partial-fetch`` the existing repository domains are still kept
  and regenerated, but the run is reported as ``"ok_with_fetch_errors"``.
* Validation failure aborts before any write (exit code 3).
* Writes are all-or-nothing per file (temp file + ``os.replace``) and every
  file that changed is rolled back if a later step fails.
* ``--dry-run`` reports the planned changes without writing anything.
* The changelog only records real additions, at most one row per UTC date,
  and only when the run completed with all discovery sources healthy.

Usage
-----
    python3 scripts/auto_update_ai.py --dry-run
    python3 scripts/auto_update_ai.py --check
    python3 scripts/auto_update_ai.py --audit-report build/audit.json
    python3 scripts/auto_update_ai.py --offline --base-dir /tmp/fixture
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ai_rules_catalog import (  # noqa: E402  (path bootstrap above)
    DOMESTIC_PROVIDERS,
    OFFICIAL_SOURCES,
    OVERSEAS_PROVIDERS,
    PROVIDER_ALIASES,
    SHARED_CDN_ROOTS,
    SHARED_ROOT_EXCEPTIONS,
    SYNC_SOURCES,
    shared_root_violation,
)

# ---------------------------------------------------------------------------
# Output layout
# ---------------------------------------------------------------------------

#: Ruleset name -> list of (relative path, format) written by the generator.
OUTPUT_SPECS = {
    "AI-Overseas": [
        ("loon/AI-Overseas.list", "domain-suffix"),
        ("surge/AI-Overseas.list", "domain-suffix"),
        ("shadowrocket/AI-Overseas.list", "domain-suffix"),
        ("qx/AI-Overseas.snippet", "host-suffix"),
        ("clash/AI-Overseas.yaml", "clash"),
        ("v2ray/AI-Overseas.txt", "domain"),
    ],
    "AI-Domestic": [
        ("loon/AI-Domestic.list", "domain-suffix"),
        ("surge/AI-Domestic.list", "domain-suffix"),
        ("shadowrocket/AI-Domestic.list", "domain-suffix"),
        ("qx/AI-Domestic.snippet", "host-suffix"),
        ("clash/AI-Domestic.yaml", "clash"),
        ("v2ray/AI-Domestic.txt", "domain"),
    ],
}

#: Every ruleset referenced by the clients' shared schema.  Only the AI
#: rulesets are generated here, but validation insists that the whole family
#: exists so a broken checkout cannot produce a half-updated client.
REQUIRED_RULESETS = ("AI-Overseas", "AI-Domestic", "Advertising", "Development", "Social", "Streaming")

RULESET_HEADER = {
    "domain-suffix": "# {name} Ruleset (Auto-Generated)\n# Total Domains: {count}\n# Managed by scripts/auto_update_ai.py - manual additions are preserved.\n",
    "host-suffix": "# {name} Ruleset for Quantumult X\n# Total Domains: {count}\n# Managed by scripts/auto_update_ai.py - manual additions are preserved.\n",
    "clash": None,  # payload list only
    "domain": "# {name} Ruleset for V2Ray / Xray / v2rayN / v2rayNG\n# Total Domains: {count}\n# Managed by scripts/auto_update_ai.py - manual additions are preserved.\n",
}

DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?\.)+[a-z][a-z0-9-]{0,62}$")

#: TLDs legitimately used by the platforms in this repository.  A host whose
#: last label is not in here is almost certainly a truncated entry: parsing
#: ``DOMAIN-SUFFIX,accounts.google.com`` with a non-anchored extractor yields
#: ``accounts.google`` -- a "domain" that resolves nowhere.  Google really
#: owns ``.google``/``.goog`` brand TLDs, so ``antigravity.google`` passes
#: while the truncated ``accounts.google`` (which must end in ``.com``) is
#: rejected by the catalogue's own list rather than by this set alone.
KNOWN_TLDS = frozenset(
    {
        "com", "org", "net", "io", "ai", "co", "dev", "app", "cn", "xyz",
        "me", "sh", "chat", "run", "cc", "tv", "info", "tech", "cloud",
        "google", "goog",
    }
)


class GenerationError(RuntimeError):
    """Raised when the run must abort without writing anything."""


def plausible_host_errors(domain: str) -> list[str]:
    """Return reasons a host is not a usable public hostname.

    Catches truncation-style typos (``accounts.google`` instead of
    ``accounts.google.com``) that :data:`DOMAIN_RE` alone accepts, because
    syntactically any ``label.label`` is a valid domain name.
    """
    errors: list[str] = []
    tld = domain.rsplit(".", 1)[-1]
    if tld not in KNOWN_TLDS:
        errors.append(f"{domain!r} has unregistered-looking TLD {tld!r} (truncated entry?)")
    if tld in {"google", "goog"} and not domain.startswith(("antigravity",)):
        errors.append(
            f"{domain!r} ends in Google's brand TLD; the real host is "
            f"{domain}.com -- did the parser truncate it?"
        )
    return errors


# ---------------------------------------------------------------------------
# Discovery (official, read-only APIs)
# ---------------------------------------------------------------------------


@dataclass
class FetchResult:
    name: str
    url: str
    ok: bool
    orgs: set[str] = field(default_factory=set)
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "url": self.url,
            "ok": self.ok,
            "publishers": len(self.orgs),
            "error": self.error,
        }


def _http_get_json(url: str, timeout: float) -> object:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ProxyHub-Rules-Audit/1.0 (+https://github.com/Daey886/ProxyHub)"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    if not raw or not raw.strip():
        raise ValueError("empty response body")
    return json.loads(raw.decode("utf-8", errors="replace"))


def _extract_orgs(payload: object, kind: str) -> set[str]:
    """Return publisher slugs from a discovery payload.

    Only the slug (left of ``/``) is kept -- it is used to *match* known
    providers, never to synthesise a domain.
    """
    if kind == "openrouter_models":
        items = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise ValueError("unexpected OpenRouter payload shape")
        ids = [item.get("id", "") for item in items if isinstance(item, dict)]
    elif kind == "huggingface_models":
        if not isinstance(payload, list):
            raise ValueError("unexpected Hugging Face payload shape")
        ids = [item.get("id", "") for item in payload if isinstance(item, dict)]
    else:  # pragma: no cover - defensive
        raise ValueError(f"unknown source kind: {kind}")
    if not ids:
        raise ValueError("source returned no models")
    orgs = set()
    for model_id in ids:
        if not isinstance(model_id, str) or "/" not in model_id:
            continue
        org = model_id.split("/", 1)[0].strip().lower()
        if org:
            orgs.add(org)
    if not orgs:
        raise ValueError("source returned no publisher slugs")
    return orgs


def fetch_source(source: dict, timeout: float = 15.0, opener=_http_get_json) -> FetchResult:
    """Fetch one discovery source.  Never raises: failures are recorded."""
    try:
        payload = opener(source["url"], timeout)
        orgs = _extract_orgs(payload, source["kind"])
        return FetchResult(source["name"], source["url"], True, orgs)
    except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return FetchResult(source["name"], source["url"], False, set(), f"{type(exc).__name__}: {exc}")


def discover(
    sources=SYNC_SOURCES,
    offline: bool = False,
    offline_orgs: set[str] | None = None,
    timeout: float = 15.0,
    opener=_http_get_json,
) -> list[FetchResult]:
    if offline:
        return [
            FetchResult(
                source["name"],
                source["url"],
                True,
                set(offline_orgs or ()),
                None if offline_orgs is not None else "offline mode",
            )
            for source in sources
        ]
    return [fetch_source(source, timeout=timeout, opener=opener) for source in sources]


def match_providers(orgs: set[str]) -> list[str]:
    """Map publisher slugs to catalogue provider keys (exact alias only)."""
    matched = set()
    for org in orgs:
        if org in OVERSEAS_PROVIDERS or org in DOMESTIC_PROVIDERS:
            matched.add(org)
        elif org in PROVIDER_ALIASES:
            matched.add(PROVIDER_ALIASES[org])
    return sorted(matched)


# ---------------------------------------------------------------------------
# Reading the repository
# ---------------------------------------------------------------------------

_EXTRACTORS = (
    # clash: +.example.com / "+ .example.com" / - '+.example.com'
    # (the quoted YAML list form is what the generator emits, so it must parse
    #  back to the same set -- otherwise every run rewrites the file and any
    #  domain only present there would be silently dropped).
    re.compile(r"^-\s*['\"]?\+\s*\.\s*(?P<v>[^'\"\s#]+)['\"]?$"),
    re.compile(r"^(?:DOMAIN-SUFFIX|HOST-SUFFIX|DOMAIN|HOST),\s*(?P<v>[^,\s#]+)"),
    re.compile(r"^domain:\s*(?P<v>[^,\s#]+)$"),  # v2ray: full-line only
)

#: Lines that belong to the clash payload structure rather than to a rule.
_CLASH_STRUCTURAL_LINES = frozenset({"payload:", "payload"})


def parse_domain_line(line: str) -> str | None:
    """Extract a normalised domain from one rule line, else ``None``."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    for pattern in _EXTRACTORS:
        match = pattern.match(stripped)
        if match:
            value = match.group("v").strip().strip("'\"").lstrip(".").lower()
            if value and DOMAIN_RE.match(value):
                return value
    return None


def read_domains(path: Path) -> set[str]:
    """All domains referenced by one ruleset file (raw parse, no validation)."""
    if not path.exists():
        return set()
    domains = set()
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            domain = parse_domain_line(line)
            if domain:
                domains.add(domain)
    return domains


def load_existing_domains(base_dir: Path, name: str) -> set[str]:
    """Union of every domain already present for ``name`` across all clients."""
    existing: set[str] = set()
    for relative, _fmt in OUTPUT_SPECS.get(name, []):
        existing |= read_domains(base_dir / relative)
    return existing


def load_client_domains(base_dir: Path, name: str) -> dict[str, set[str]]:
    """Per-file domain sets, used to detect pre-existing client drift."""
    return {
        relative: read_domains(base_dir / relative)
        for relative, _fmt in OUTPUT_SPECS.get(name, [])
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings}


def _suffix_overlap(a: str, b: str) -> bool:
    return a == b or a.endswith("." + b) or b.endswith("." + a)


def is_shared_root_domain(domain: str) -> bool:
    """True for a shared CDN root itself (``googleapis.com``, ``gstatic.com``)."""
    return domain in SHARED_CDN_ROOTS


def is_under_shared_root(domain: str) -> bool:
    return any(domain != root and domain.endswith("." + root) for root in SHARED_CDN_ROOTS)


@dataclass
class SanitizeResult:
    kept: set[str] = field(default_factory=set)
    removed_shared_roots: list[str] = field(default_factory=list)
    rejected_guesses: list[str] = field(default_factory=list)
    #: Hosts dropped because they do not look like a real public hostname
    #: (truncated entries such as ``accounts.google``).  The catalogue is the
    #: source of truth for their valid counterparts, so no rule is lost.
    removed_malformed: list[str] = field(default_factory=list)
    #: Lines that exist in a ruleset but could not be parsed into a domain.
    #: These are *not* silently repairable: dropping them would delete a
    #: hand-maintained rule, so their presence aborts the run.
    unparsable: list[str] = field(default_factory=list)


def read_domains_with_unparsable(path: Path) -> tuple[set[str], list[str]]:
    """Parse one ruleset file, returning ``(domains, unparsable_lines)``."""
    if not path.exists():
        return set(), []
    domains: set[str] = set()
    unparsable: list[str] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # Structural YAML lines of the clash payload, not rules.
            if stripped in _CLASH_STRUCTURAL_LINES:
                continue
            domain = parse_domain_line(line)
            if domain:
                domains.add(domain)
            else:
                unparsable.append(f"{path.name}:{number}: {stripped}")
    return domains, unparsable


def sanitize_domains(domains: set[str]) -> SanitizeResult:
    """Drop shared-CDN roots and reject unaudited hosts beneath such roots.

    A shared root (``googleapis.com``) is removed without complaint -- it is a
    known over-broad entry from older generated rulesets.  A *sub-domain* of a
    shared root that is not in the audited exception list
    (``lh3.googleusercontent.com``) is an unsupported guess and aborts the run.
    Malformed hosts that an older parser wrote into the rulesets
    (``accounts.google``) are dropped as stale artifacts; their valid
    counterpart is supplied by the catalogue.
    """
    result = SanitizeResult()
    for domain in sorted(domains):
        if is_shared_root_domain(domain):
            result.removed_shared_roots.append(domain)
        elif plausible_host_errors(domain):
            result.removed_malformed.append(domain)
        elif is_under_shared_root(domain) and domain not in SHARED_ROOT_EXCEPTIONS:
            result.rejected_guesses.append(domain)
        else:
            result.kept.add(domain)
    return result


def validate_ruleset(name: str, domains: set[str]) -> ValidationResult:
    """Validate one ruleset before rendering."""
    result = ValidationResult()
    for domain in sorted(domains):
        if not DOMAIN_RE.match(domain):
            result.errors.append(f"{name}: invalid domain {domain!r}")
            continue
        for message in plausible_host_errors(domain):
            result.errors.append(f"{name}: {message}")
        # Single source of truth: the catalogue explains why a host is refused.
        violation = shared_root_violation(domain)
        if violation:
            result.errors.append(f"{name}: {violation}")
    return result


def validate_no_conflicts(overseas: set[str], domestic: set[str]) -> ValidationResult:
    """A domain (or a parent of one) must not be both proxied and DIRECT."""
    result = ValidationResult()
    domestic_sorted = sorted(domestic)
    for domain in sorted(overseas):
        for other in domestic_sorted:
            if _suffix_overlap(domain, other):
                result.errors.append(
                    f"conflict: {domain!r} (AI-Overseas) overlaps {other!r} (AI-Domestic)"
                )
    return result


def validate_catalog_provenance() -> ValidationResult:
    """Every routed domain must be traceable to an official-source note."""
    result = ValidationResult()
    for label, providers in (("overseas", OVERSEAS_PROVIDERS), ("domestic", DOMESTIC_PROVIDERS)):
        for provider, domains in providers.items():
            for domain in domains:
                if domain not in OFFICIAL_SOURCES:
                    result.errors.append(f"catalog[{label}][{provider}]: {domain!r} has no OFFICIAL_SOURCES entry")
                result.errors.extend(
                    f"catalog[{label}][{provider}]: {message}"
                    for message in plausible_host_errors(domain)
                )
    for domain in sorted(OFFICIAL_SOURCES):
        if not DOMAIN_RE.match(domain):
            result.errors.append(f"OFFICIAL_SOURCES: malformed domain {domain!r}")
    return result


def validate_generated(base_dir: Path) -> ValidationResult:
    """Post-write consistency check across every client format."""
    result = ValidationResult()
    expected = {name: load_existing_domains(base_dir, name) for name in ("AI-Overseas", "AI-Domestic")}
    for name, domains in expected.items():
        if not domains:
            result.errors.append(f"{name}: generated ruleset is empty")

    for name, specs in OUTPUT_SPECS.items():
        expected_domains = expected[name]
        for relative, fmt in specs:
            path = base_dir / relative
            if not path.exists():
                result.errors.append(f"{relative}: missing generated file")
                continue
            text = path.read_text(encoding="utf-8")
            actual = read_domains(path)
            if actual != expected_domains:
                missing = sorted(expected_domains - actual)
                extra = sorted(actual - expected_domains)
                result.errors.append(
                    f"{relative}: domain set differs from {name} canonical set "
                    f"(missing={missing[:5]}, extra={extra[:5]})"
                )
            _validate_syntax(relative, text, fmt, name, expected_domains, result)

    for root in sorted(SHARED_CDN_ROOTS):
        leaked = sorted(
            domain
            for domains in expected.values()
            for domain in domains
            if domain == root or (domain.endswith("." + root) and domain not in SHARED_ROOT_EXCEPTIONS)
        )
        if leaked:
            result.errors.append(f"shared CDN root {root!r} leaked into generated rulesets: {leaked[:5]}")

    for other in REQUIRED_RULESETS:
        for relative, _fmt in OUTPUT_SPECS.get(other, []):
            if not (base_dir / relative).exists():
                result.warnings.append(f"{relative}: ruleset family member missing")

    result.errors.extend(validate_no_conflicts(expected["AI-Overseas"], expected["AI-Domestic"]).errors)
    return result


def _validate_syntax(
    relative: str,
    text: str,
    fmt: str,
    name: str,
    domains: set[str],
    result: ValidationResult,
) -> None:
    """Strict check of one rendered file; used by tests and ``--strict``."""
    if not text.endswith("\n"):
        result.errors.append(f"{relative}: file must end with a newline")
    if "\r" in text:
        result.errors.append(f"{relative}: CRLF line endings are not allowed")
    lines = text.splitlines()
    if fmt == "clash":
        if not lines or lines[0].strip() != "payload:":
            result.errors.append(f"{relative}: Clash provider must start with 'payload:'")
            return
        entries = [line.strip() for line in lines[1:] if line.strip()]
        bad = [entry for entry in entries if not (entry.startswith("- ") and entry[2:].strip("'\"").startswith("+."))]
        if bad:
            result.errors.append(f"{relative}: non '+.domain' payload entries: {bad[:3]}")
        if len(entries) != len(domains):
            result.errors.append(f"{relative}: {len(entries)} payload entries for {len(domains)} domains")
        if [entry.strip("'\"+-. ") for entry in entries] != sorted(domains):
            result.errors.append(f"{relative}: payload entries are not sorted / not 1:1 with domains")
        return

    prefix = {"domain-suffix": "DOMAIN-SUFFIX,", "host-suffix": "HOST-SUFFIX,", "domain": "domain:"}[fmt]
    rule_lines = [line for line in lines if line.strip() and not line.startswith("#")]
    bad = [line for line in rule_lines if not line.startswith(prefix)]
    if bad:
        result.errors.append(f"{relative}: unexpected rule syntax: {bad[:3]}")
    if len(rule_lines) != len(domains):
        result.errors.append(f"{relative}: {len(rule_lines)} rules for {len(domains)} domains")
    if rule_lines != sorted(rule_lines):
        result.errors.append(f"{relative}: rules are not sorted")
    if len(set(rule_lines)) != len(rule_lines):
        result.errors.append(f"{relative}: duplicate rules present")
    header = lines[0] if lines else ""
    if not header.startswith(f"# {name} Ruleset"):
        result.errors.append(f"{relative}: unexpected header {header!r}")
    total = re.search(r"^# Total Domains: (\d+)$", text, re.MULTILINE)
    if not total:
        result.errors.append(f"{relative}: 'Total Domains' header line missing")
    elif int(total.group(1)) != len(domains):
        result.errors.append(f"{relative}: header count {total.group(1)} != {len(domains)}")


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render(name: str, domains: set[str], fmt: str) -> str:
    ordered = sorted(domains)
    if fmt == "clash":
        return "\n".join(["payload:"] + [f"  - '+.{domain}'" for domain in ordered]) + "\n"
    body = "\n".join(
        {
            "domain-suffix": f"DOMAIN-SUFFIX,{domain}",
            "host-suffix": f"HOST-SUFFIX,{domain}",
            "domain": f"domain:{domain}",
        }[fmt]
        for domain in ordered
    )
    header = RULESET_HEADER[fmt].format(name=name, count=len(ordered))
    return header + "\n" + body + "\n"


# ---------------------------------------------------------------------------
# Atomic, transactional writes
# ---------------------------------------------------------------------------


class FileTransaction:
    """Apply file writes all-or-nothing: roll back on any failure."""

    def __init__(self) -> None:
        self._pending: dict[Path, str] = {}
        self._originals: dict[Path, bytes | None] = {}
        self._written: list[Path] = []

    def stage(self, path: Path, content: str) -> bool:
        """Stage a write.  Returns ``True`` when content differs from disk."""
        original = path.read_bytes() if path.exists() else None
        self._originals[path] = original
        if original is not None and original == content.encode("utf-8"):
            return False
        self._pending[path] = content
        return True

    @property
    def changed(self) -> list[Path]:
        return list(self._pending)

    def commit(self) -> None:
        try:
            for path, content in self._pending.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
                try:
                    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                        handle.write(content)
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(tmp_name, path)
                finally:
                    if os.path.exists(tmp_name):
                        os.unlink(tmp_name)
                self._written.append(path)
        except BaseException:
            self.rollback()
            raise

    def rollback(self) -> None:
        for path in reversed(self._written):
            original = self._originals.get(path)
            if original is None:
                if path.exists():
                    path.unlink()
            else:
                path.write_bytes(original)
        self._written.clear()
        self._pending.clear()


# ---------------------------------------------------------------------------
# Changelog
# ---------------------------------------------------------------------------

CHANGELOG_MARKER = "| :--- | :--- | :--- | :--- | :--- |\n"


def update_changelog(
    readme_text: str,
    today: str,
    platforms: list[str],
    added: dict[str, list[str]],
) -> tuple[str, bool]:
    """Insert one generated changelog row for ``today`` (idempotent)."""
    total_added = sum(len(values) for values in added.values())
    if not total_added and not platforms:
        return readme_text, False
    date_marker = f"| `{today}` | 🤖 **自动同步** |"
    if date_marker in readme_text:
        return readme_text, False
    if CHANGELOG_MARKER not in readme_text:
        raise GenerationError("README changelog table header not found")
    rows = [f"{ruleset}: {len(values)}" for ruleset, values in sorted(added.items()) if values]
    breakdown = f"（{', '.join(rows)}）" if rows else ""
    row = (
        f"| `{today}` | 🤖 **自动同步** | {', '.join(platforms) or 'official sources'} | "
        f"`海外AI` / `DIRECT` | 收录 {len(platforms)} 个匹配平台，"
        f"新增 {total_added} 个域名{breakdown}，重复域名已去重 |\n"
    )
    return readme_text.replace(CHANGELOG_MARKER, CHANGELOG_MARKER + row, 1), True


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


@dataclass
class RunResult:
    status: str
    exit_code: int
    changed_files: list[str] = field(default_factory=list)
    report: dict = field(default_factory=dict)


def build_plan(
    base_dir: Path,
    overseas_domains: set[str],
    domestic_domains: set[str],
) -> tuple[dict[str, set[str]], dict[str, dict[str, list[str]]]]:
    """Curated + every domain already in the repository (never drop manual ones).

    Returns ``(plan, removed)`` where ``removed`` maps each ruleset to
    ``{"shared_roots": [...], "malformed": [...]}``, the over-broad roots and
    stale malformed hosts that were intentionally dropped.  Manual domains
    outside shared CDN roots always survive.
    """
    plan: dict[str, set[str]] = {}
    removed: dict[str, dict[str, list[str]]] = {}
    for name, seeded in (("AI-Overseas", overseas_domains), ("AI-Domestic", domestic_domains)):
        combined = {domain.lower() for domain in seeded} | load_existing_domains(base_dir, name)
        sanitized = sanitize_domains(combined)
        plan[name] = sanitized.kept
        removed[name] = {
            "shared_roots": sorted(sanitized.removed_shared_roots),
            "malformed": sorted(sanitized.removed_malformed),
        }
    return plan, removed


def run(
    base_dir: Path | str,
    *,
    offline: bool = False,
    offline_orgs: set[str] | None = None,
    dry_run: bool = False,
    check: bool = False,
    allow_partial_fetch: bool = False,
    no_changelog: bool = False,
    timeout: float = 15.0,
    opener=_http_get_json,
    sources=SYNC_SOURCES,
    today: str | None = None,
    logger=print,
) -> RunResult:
    base = Path(base_dir).resolve()
    report: dict = {
        "status": "unknown",
        "base_dir": str(base),
        "dry_run": dry_run,
        "offline": offline,
        "sources": [],
        "matched_platforms": [],
        "counts": {},
        "added": {},
        "changed_files": [],
        "validation": {},
    }

    # 1. Discovery ---------------------------------------------------------
    results = discover(sources, offline=offline, offline_orgs=offline_orgs, timeout=timeout, opener=opener)
    report["sources"] = [item.as_dict() for item in results]
    failed = [item for item in results if not item.ok]
    if failed and not allow_partial_fetch:
        for item in failed:
            logger(f"source fetch failed: {item.name}: {item.error}")
        report["status"] = "fetch_failed"
        report["error"] = "one or more official sources were unreachable; nothing was written"
        return RunResult("fetch_failed", 2, [], report)
    if failed:
        report["status_note"] = "continuing with preserved repository domains despite fetch errors"

    all_orgs: set[str] = set()
    for item in results:
        all_orgs |= item.orgs
    platforms = match_providers(all_orgs)
    report["matched_platforms"] = platforms
    logger(f"discovered {len(all_orgs)} publishers from {len(results)} official sources; "
           f"matched {len(platforms)} known providers")

    # 2. Plan (curated + manual) ------------------------------------------
    overseas_domains = {d for domains in OVERSEAS_PROVIDERS.values() for d in domains}
    domestic_domains = {d for domains in DOMESTIC_PROVIDERS.values() for d in domains}
    before = {name: load_existing_domains(base, name) for name in ("AI-Overseas", "AI-Domestic")}
    plan, removed = build_plan(base, overseas_domains, domestic_domains)
    report["removed_shared_roots"] = removed

    # 3. Validate before rendering ---------------------------------------
    validation = ValidationResult()
    validation.errors.extend(validate_catalog_provenance().errors)
    # Unparsable lines would be silently deleted when the file is regenerated,
    # so they are a hard error rather than something to clean up automatically.
    unparsable: list[str] = []
    for name, specs in OUTPUT_SPECS.items():
        for relative, _fmt in specs:
            _domains, bad = read_domains_with_unparsable(base / relative)
            unparsable.extend(f"{name}: {line}" for line in bad)
    if unparsable:
        report["unparsable_rules"] = unparsable
        validation.errors.extend(
            f"unparsable rule line in an existing ruleset (refusing to drop it): {line}"
            for line in unparsable
        )
    validation.errors.extend(validate_ruleset("AI-Overseas", plan["AI-Overseas"]).errors)
    validation.errors.extend(validate_ruleset("AI-Domestic", plan["AI-Domestic"]).errors)
    validation.errors.extend(validate_no_conflicts(plan["AI-Overseas"], plan["AI-Domestic"]).errors)
    report["validation"] = validation.as_dict()
    report["counts"] = {name: len(plan[name]) for name in plan}
    report["added"] = {
        name: sorted(plan[name] - before[name]) for name in plan
    }
    report["removed"] = {
        name: sorted(before[name] - plan[name]) for name in plan
    }
    if not validation.ok:
        for error in validation.errors:
            logger(f"validation error: {error}")
        report["status"] = "validation_failed"
        return RunResult("validation_failed", 3, [], report)

    # 4. Stage renders ----------------------------------------------------
    transaction = FileTransaction()
    for name, specs in OUTPUT_SPECS.items():
        for relative, fmt in specs:
            transaction.stage(base / relative, render(name, plan[name], fmt))

    # Check mode: report whether regeneration would change anything.
    if check:
        drift = {}
        for name in plan:
            for relative, _fmt in OUTPUT_SPECS[name]:
                difference = load_client_domains(base, name)[relative] ^ plan[name]
                if difference:
                    drift[relative] = sorted(difference)
        report["check"] = {
            "up_to_date": not transaction.changed,
            "drift": drift,
        }
        report["changed_files"] = [str(path.relative_to(base)) for path in transaction.changed]
        report["status"] = "clean" if not transaction.changed else "out_of_date"
        return RunResult(report["status"], 0 if not transaction.changed else 1, report["changed_files"], report)

    # Changelog (only when every source is healthy and domains were added).
    changelog_row = False
    if not no_changelog and not failed:
        readme_path = base / "README.md"
        if readme_path.exists():
            added = report["added"]
            if any(added.values()):
                try:
                    new_text, changelog_row = update_changelog(
                        readme_path.read_text(encoding="utf-8"),
                        today or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        platforms,
                        added,
                    )
                except GenerationError as exc:
                    report["status"] = "validation_failed"
                    report["error"] = str(exc)
                    return RunResult("validation_failed", 3, [], report)
                if changelog_row:
                    transaction.stage(readme_path, new_text)
    report["changelog_updated"] = changelog_row

    report["changed_files"] = [str(path.relative_to(base)) for path in transaction.changed]

    if dry_run:
        report["status"] = "dry_run" if transaction.changed else "clean"
        logger(f"dry run: would update {len(transaction.changed)} file(s)")
        return RunResult(report["status"], 0, report["changed_files"], report)

    # 5. Commit + post-write verification --------------------------------
    if transaction.changed:
        try:
            transaction.commit()
            post = validate_generated(base)
        except BaseException as exc:  # noqa: BLE001 - roll back on anything
            transaction.rollback()
            report["status"] = "write_failed"
            report["error"] = f"{type(exc).__name__}: {exc}"
            logger(f"write failed and was rolled back: {report['error']}")
            return RunResult("write_failed", 4, [], report)
        report["post_validation"] = post.as_dict()
        if not post.ok:
            transaction.rollback()
            for error in post.errors:
                logger(f"post-write validation error: {error}")
            report["status"] = "post_validation_failed"
            return RunResult("post_validation_failed", 3, [], report)
        logger(f"updated {len(report['changed_files'])} file(s)")
    else:
        report["post_validation"] = validate_generated(base).as_dict()
        logger("rules already up to date")

    report["status"] = "ok_with_fetch_errors" if failed else "ok"
    return RunResult(report["status"], 0, report["changed_files"], report)


def main(argv: list[str] | None = None, opener=_http_get_json, logger=print) -> int:
    parser = argparse.ArgumentParser(description="Audit and auto-sync ProxyHub AI rulesets safely.")
    parser.add_argument("--base-dir", default=str(Path(__file__).resolve().parent.parent),
                        help="repository root that contains loon/ surge/ qx/ clash/ v2ray/ (default: repo root)")
    parser.add_argument("--dry-run", action="store_true", help="report planned changes without writing")
    parser.add_argument("--check", action="store_true", help="exit 1 if generated files are out of date; never writes")
    parser.add_argument("--offline", action="store_true", help="skip network discovery")
    parser.add_argument("--allow-partial-fetch", action="store_true",
                        help="regenerate from preserved domains when a source is unreachable "
                             "(never records a changelog entry)")
    parser.add_argument("--no-changelog", action="store_true", help="never touch README.md")
    parser.add_argument("--audit-report", metavar="PATH", help="write the JSON audit report to PATH")
    parser.add_argument("--timeout", type=float, default=15.0, help="per-source timeout in seconds")
    args = parser.parse_args(argv)

    result = run(
        args.base_dir,
        offline=args.offline,
        dry_run=args.dry_run,
        check=args.check,
        allow_partial_fetch=args.allow_partial_fetch,
        no_changelog=args.no_changelog,
        timeout=args.timeout,
        opener=opener,
        logger=logger,
    )
    payload = json.dumps(result.report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.audit_report:
        report_path = Path(args.audit_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(payload + "\n", encoding="utf-8")
        logger(f"audit report written to {report_path}")
    logger(payload)
    logger(f"AUDIT_STATUS={result.status}")
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
