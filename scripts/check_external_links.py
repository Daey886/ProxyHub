#!/usr/bin/env python3
from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parent.parent
URL_RE=re.compile(r'https?://[^\s<>"\)]+')

def main():
    urls=sorted(set(u.rstrip('.,') for p in [ROOT/'README.md',ROOT/'docs/index.html'] for u in URL_RE.findall(p.read_text(encoding='utf-8'))))
    failures=[]
    for url in urls:
        try:
            req=Request(url, headers={'User-Agent':'ProxyHub-link-check/1.0'}, method='HEAD')
            with urlopen(req, timeout=15) as r: status=r.status
            if status >= 400: failures.append(f'{status} {url}')
        except Exception as e:
            failures.append(f'ERROR {url}: {e.__class__.__name__}')
    print(f'LINK_CHECK urls={len(urls)} failures={len(failures)}')
    if failures: print('\n'.join(failures)); return 1
    return 0
if __name__=='__main__': sys.exit(main())
