#!/usr/bin/env python3
"""Create a deterministic, human-readable rules diff report."""
from __future__ import annotations
import re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULE_DIRS = ('loon', 'surge', 'shadowrocket', 'qx', 'clash', 'v2ray')

def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else 'HEAD^'
    cmd = ['git', 'diff', '--unified=0', f'{base}...HEAD', '--', *RULE_DIRS]
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if result.returncode not in (0, 1):
        raise SystemExit(f'git diff failed: {result.stderr.strip()}')
    diff = result.stdout
    added = [x[1:] for x in diff.splitlines() if x.startswith('+') and not x.startswith('+++')]
    removed = [x[1:] for x in diff.splitlines() if x.startswith('-') and not x.startswith('---')]
    files = sorted({line[6:] for line in diff.splitlines() if line.startswith('+++ b/')})
    domains = lambda rows: sorted(set(re.findall(r'(?i)(?:DOMAIN-SUFFIX[, ]|domain:\s*|\+\.)?([a-z0-9][a-z0-9.-]+\.[a-z]{2,})', '\n'.join(rows))))
    out = ['# Rules Change Report', '', f'- Base: `{base}`', f'- Files changed: {len(files)}', f'- Added lines: {len(added)}', f'- Removed lines: {len(removed)}', f'- Added domains: {len(domains(added))}', f'- Removed domains: {len(domains(removed))}', '', '## Files', *[f'- `{x}`' for x in files], '', '## Added domains', *[f'- `{x}`' for x in domains(added)], '', '## Removed domains', *[f'- `{x}`' for x in domains(removed)]]
    print('\n'.join(out) + '\n')
    return 0
if __name__ == '__main__': raise SystemExit(main())
