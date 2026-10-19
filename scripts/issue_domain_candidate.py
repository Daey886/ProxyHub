#!/usr/bin/env python3
"""Validate an Issue domain request and update the candidate catalogue.

The Issue body is untrusted input. This script only accepts explicit fields and
writes a JSON candidate file; it never edits generated production rules.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
PUBLIC_SUFFIXES = {"com", "org", "net", "io", "ai", "co", "cn", "dev", "app", "me", "sh", "xyz"}
SHARED_ROOTS = {"google.com", "googleapis.com", "gstatic.com", "cloudflare.com", "amazonaws.com", "aliyuncs.com", "github.com"}
MARKER = "<!-- proxyhub-domain-candidate -->"


def registrable(domain: str) -> str:
    parts = domain.split(".")
    return ".".join(parts[-2:])


def parse(body: str) -> tuple[str, str, str]:
    fields = {}
    for line in body.splitlines():
        m = re.match(r"^\s*(域名|目标规则集|官方证据)\s*[：:]\s*(.+?)\s*$", line, re.I)
        if m:
            fields[m.group(1)] = m.group(2).strip()
    domain = fields.get("域名", "").lower().rstrip(".")
    target = fields.get("目标规则集", "")
    evidence = fields.get("官方证据", "")
    if not domain or not target or not evidence:
        raise ValueError("required fields: 域名、目标规则集、官方证据")
    if target not in {"海外 AI", "国内 AI", "overseas", "domestic"}:
        raise ValueError("目标规则集 must be 海外 AI or 国内 AI")
    target = "overseas" if target in {"海外 AI", "overseas"} else "domestic"
    if not DOMAIN_RE.fullmatch(domain) or domain.startswith("www."):
        raise ValueError("域名必须是裸 FQDN，不得包含协议、路径、通配符或 IP")
    if domain.split(".")[-1] not in PUBLIC_SUFFIXES:
        raise ValueError("域名后缀不在允许列表")
    if domain in SHARED_ROOTS or registrable(domain) in SHARED_ROOTS:
        raise ValueError("共享 CDN/基础设施根域名不接受社区自动候选")
    parsed = urlparse(evidence)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("官方证据必须是不带参数的 HTTPS URL")
    evidence_host = (parsed.hostname or "").lower().rstrip(".")
    if not evidence_host or registrable(evidence_host) != registrable(domain):
        raise ValueError("官方证据 URL 必须来自提交域名的同一注册域名")
    return domain, target, evidence


def main(event_path: str, data_path: str) -> int:
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    body = event.get("issue", {}).get("body") or ""
    try:
        domain, target, evidence = parse(body)
    except ValueError as exc:
        print(f"candidate_rejected={exc}")
        return 2
    path = Path(data_path)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"overseas": [], "domestic": []}
    for key in ("overseas", "domestic"):
        data.setdefault(key, [])
        data[key] = sorted(set(data[key]))
    other = "domestic" if target == "overseas" else "overseas"
    if domain in data[other]:
        print("candidate_rejected=domain already belongs to the opposite ruleset")
        return 2
    if domain in data[target]:
        print(f"candidate_added={domain}")
        print(f"candidate_target={target}")
        print(f"candidate_evidence={evidence}")
        print("candidate_duplicate=true")
        return 0

    data[target].append(domain)
    data[target].sort()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"candidate_added={domain}")
    print(f"candidate_target={target}")
    print(f"candidate_evidence={evidence}")
    print(f"{MARKER}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
