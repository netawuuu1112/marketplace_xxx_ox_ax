"""Verify the loopback V2 deployment without logging credentials or user data."""
import argparse
import http.cookiejar
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--sources', help='Optional comma-separated sources for one genuine search')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    password = next(line.partition('=')[2] for line in (root / '.env').read_text().splitlines()
                    if line.startswith('WEB_ADMIN_PASSWORD='))
    base = f'http://127.0.0.1:{args.port}'
    cookies = http.cookiejar.CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookies))

    def request(path, payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        with opener.open(Request(base + path, data=body,
                                 headers={'Origin': base, 'Content-Type': 'application/json'}), timeout=15) as response:
            return json.load(response)

    with opener.open(base + '/', timeout=15) as response:
        if response.headers.get_content_type() != 'text/html':
            raise RuntimeError('V2 web did not serve HTML')
    health = request('/health')
    if health.get('ok') is not True or health.get('demo') is not False:
        raise RuntimeError('API health or demo configuration mismatch')
    try:
        request('/api/v2/admin/usage')
    except HTTPError as error:
        if error.code not in (401, 403):
            raise
    else:
        raise RuntimeError('Admin API accepted an anonymous request')
    if request('/api/auth/login', {'password': password}).get('role') != 'super_admin':
        raise RuntimeError('Admin login failed')
    for path in ('profile', 'favorites', 'recent', 'watches', 'notifications', 'admin/usage'):
        request('/api/v2/' + path)
    print('Verified web, API, authenticated V2 sections and admin access control.', flush=True)
    if not args.sources:
        return

    job = request('/api/v2/search', {'query': 'Kingston NV3 1TB', 'sources': args.sources.split(',')})
    deadline = time.monotonic() + 240
    while job['status'] in ('queued', 'running') and time.monotonic() < deadline:
        time.sleep(2)
        job = request('/api/v2/search/' + job['search_id'])
    if job['status'] != 'complete':
        raise RuntimeError(f"Search ended in {job['status']}")
    print(json.dumps([{key: row[key] for key in ('source', 'status', 'detail', 'offers_count', 'region')}
                      for row in job['sources']], ensure_ascii=True))


if __name__ == '__main__':
    main()
