#!/usr/bin/env python3
"""Fail-closed audit for generated proxy rule files."""
from __future__ import annotations
import ipaddress, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULE_DIRS = ("loon", "surge", "shadowrocket", "qx", "clash", "v2ray")
BROAD = {"google.com", "microsoft.com", "apple.com", "amazon.com", "cloudflare.com"}
PUBLIC_SUFFIXES = {"com", "net", "org", "io", "ai", "cn", "co", "dev", "app"}
DOMAIN_RE = re.compile(r"(?i)^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$")

def domains(path: Path):
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("#", ";", "//")) or line.startswith(("payload:", "rules:", "rule-providers:", "  ")):
            continue
        for token in re.findall(r"(?i)(?:DOMAIN-SUFFIX[, ]|domain:\s*|\+\.)?([a-z0-9][a-z0-9.-]+\.[a-z]{2,})", line):
            yield token.rstrip("."), n, line

def main() -> int:
    errors, seen = [], {}
    for d in RULE_DIRS:
        for path in sorted((ROOT / d).glob("*")):
            if not path.is_file() or path.name.startswith("version"):
                continue
            for domain, line, raw in domains(path):
                key = domain.lower()
                if not DOMAIN_RE.fullmatch(key): errors.append(f"{path}:{line}: invalid domain {domain}")
                if key in BROAD or key in PUBLIC_SUFFIXES: errors.append(f"{path}:{line}: broad/public suffix {domain}")
                try: ipaddress.ip_address(key); errors.append(f"{path}:{line}: IP literal {domain}")
                except ValueError: pass
                seen.setdefault(key, []).append(str(path))
    overseas = {x for x in seen if any("AI-Overseas" in p for p in seen[x])}
    domestic = {x for x in seen if any("AI-Domestic" in p for p in seen[x])}
    for x in sorted(overseas & domestic): errors.append(f"AI domain appears in both rulesets: {x}")
    if errors:
        print("RULE_AUDIT_FAILED")
        print("\n".join(errors))
        return 1
    print(f"RULE_AUDIT_OK domains={len(seen)} files={sum(1 for d in RULE_DIRS for p in (ROOT/d).glob('*') if p.is_file())}")
    return 0

if __name__ == "__main__": sys.exit(main())
