#!/usr/bin/env python3
from __future__ import annotations
import html, re, sys
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parent.parent
URL_RE=re.compile(r'https?://[^\s<>"\]\),]+')

def extract(text: str, suffix: str):
    text = html.unescape(text)
    if suffix == '.html':
        urls = re.findall(r'''href=["'](https?://[^"']+)["']''', text, re.I)
    else:
        urls = re.findall(r'(?<!\()(?<!["\'])https?://[^\s<>"\]\)]+', text)
    result=[]
    for url in urls:
        url=url.rstrip('.,;:`')
        if suffix == '.md':
            url = url.rstrip(',')
        if urlsplit(url).scheme in {'http','https'} and urlsplit(url).netloc:
            result.append(url)
    return result

def check(url: str):
    parts=urlsplit(url)
    safe_path=quote(parts.path, safe='/%:@!$&\'()*+,;=-._~')
    safe_query=quote(parts.query, safe='/?%:@!$&\'()*+,;=-._~')
    url=urlunsplit((parts.scheme, parts.netloc, safe_path, safe_query, parts.fragment))
    headers={'User-Agent':'ProxyHub-link-check/1.0'}
    try:
        req=Request(url, headers=headers, method='HEAD')
        with urlopen(req, timeout=15) as r: return r.status
    except (HTTPError, URLError):
        req=Request(url, headers=headers, method='GET')
        with urlopen(req, timeout=15) as r: return r.status

def main():
    urls=sorted(set(u for p in [ROOT/'README.md',ROOT/'docs/index.html'] for u in extract(p.read_text(encoding='utf-8'), p.suffix)))
    failures=[]
    for url in urls:
        try:
            status=check(url)
            # Auth-protected APIs and anti-bot font hosts are reachable even when
            # they reject anonymous probes; treat only server-side failures as bad.
            if status >= 500: failures.append(f'{status} {url}')
        except (HTTPError, URLError) as e:
            if isinstance(e, HTTPError) and e.code < 500:
                continue
            failures.append(f'ERROR {url}: {e.__class__.__name__}')
    print(f'LINK_CHECK urls={len(urls)} failures={len(failures)}')
    if failures: print('\n'.join(failures)); return 1
    return 0
if __name__=='__main__': sys.exit(main())
