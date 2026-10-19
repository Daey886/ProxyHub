#!/usr/bin/env python3
from __future__ import annotations
import html, re, sys
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parent.parent
URL_RE=re.compile(r'https?://[^\s<>"\]\)]+')

def extract(text: str, suffix: str):
    text = html.unescape(text)
    if suffix == '.html':
        urls = re.findall(r'''href=["'](https?://[^"']+)["']''', text, re.I)
    else:
        urls = re.findall(r'(?<!\()(?<!["\'])https?://[^\s<>"\]\)]+', text)
    result=[]
    for url in urls:
        url=url.rstrip('.,;:`')
        if urlsplit(url).scheme in {'http','https'} and urlsplit(url).netloc:
            result.append(url)
    return result

def check(url: str):
    headers={'User-Agent':'ProxyHub-link-check/1.0'}
    try:
        req=Request(url, headers=headers, method='HEAD')
        with urlopen(req, timeout=15) as r: return r.status
    except Exception:
        req=Request(url, headers=headers, method='GET')
        with urlopen(req, timeout=15) as r: return r.status

def main():
    urls=sorted(set(u for p in [ROOT/'README.md',ROOT/'docs/index.html'] for u in extract(p.read_text(encoding='utf-8'), p.suffix)))
    failures=[]
    for url in urls:
        try:
            status=check(url)
            if status >= 400: failures.append(f'{status} {url}')
        except Exception as e:
            failures.append(f'ERROR {url}: {e.__class__.__name__}')
    print(f'LINK_CHECK urls={len(urls)} failures={len(failures)}')
    if failures: print('\n'.join(failures)); return 1
    return 0
if __name__=='__main__': sys.exit(main())
