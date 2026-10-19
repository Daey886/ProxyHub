#!/usr/bin/env python3
"""Verify a candidate's HTTPS evidence is reachable and same-site."""
from __future__ import annotations
import json, sys
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def registrable(host: str) -> str:
    return '.'.join(host.lower().rstrip('.').split('.')[-2:])


def main(event_path: str) -> int:
    event = json.loads(Path(event_path).read_text(encoding='utf-8'))
    body = event.get('issue', {}).get('body') or ''
    evidence = ''
    domain = ''
    for line in body.splitlines():
        for label, key in (('官方证据', 'evidence'), ('域名', 'domain')):
            if line.startswith((label + ':', label + '：')):
                value = line[len(label):].lstrip(':：').strip()
                if key == 'evidence': evidence = value
                else: domain = value
                break
    if not evidence or not domain:
        print('evidence_rejected=域名 and 官方证据 are required')
        return 2
    parsed = urlparse(evidence)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        print('evidence_rejected=HTTPS URL without credentials, query, or fragment required')
        return 2
    if registrable(parsed.hostname) != registrable(domain):
        print('evidence_rejected=same registrable domain required')
        return 2
    try:
        req = Request(evidence, headers={'User-Agent': 'ProxyHub-evidence-check/1.0'})
        with urlopen(req, timeout=15) as response:
            status = response.status
            response.read(4096)
        if status >= 500:
            print(f'evidence_rejected=server status {status}')
            return 2
    except Exception as exc:
        print(f'evidence_rejected={exc.__class__.__name__}')
        return 2
    print(f'evidence_verified={evidence}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1]))
