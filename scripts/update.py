"""Free RSS and public IR link collector. No paid articles or PDF body extraction."""
from __future__ import annotations
import argparse
import concurrent.futures
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import ssl
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc
MAX_BYTES = 2_000_000
TERMS = re.compile(r'半導体|semiconductor|\bchips?\b|wafer|ウェ[ーイ]ハ|EUV|DUV|エッチング|etching|リソグラフィ|lithograph|フォトレジスト|photoresist|CMP|ALD|ボンディング|bonding|真空|vacuum|成膜|ダイシング|dicing|プローブカード|probe card|封止|silicon', re.I)
IR_TERMS = re.compile(r'決算|有価証券|適時開示|決算説明|業績|配当|自己株式|annual report|financial results|earnings|quarterly|financial report|investor presentation', re.I)
INDEX_TERMS = re.compile(r'ニュース|開示|news|release|financial results|決算|earnings', re.I)


def timestamp(now=None):
    return (now or datetime.now(UTC)).isoformat(timespec='seconds').replace('+00:00', 'Z')


def safe_url(value):
    try:
        p = urllib.parse.urlsplit(value)
        return p.scheme in ('http', 'https') and bool(p.hostname) and not p.username and not p.password
    except ValueError:
        return False


def canonical_url(url):
    p = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
    query = [(k, v) for k, v in query if not k.lower().startswith('utm_') and k.lower() not in ('gclid', 'fbclid')]
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(query), ''))


def identity(url):
    return hashlib.sha256(canonical_url(url).encode()).hexdigest()[:20]


def clean(text):
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]*>', '', text or ''))).strip()[:500]


def fetch(url, timeout=15):
    if not safe_url(url):
        raise ValueError('Unsupported URL')
    req = urllib.request.Request(url, headers={'User-Agent': 'SemiAtlas/2.0 (+https://github.com/mawtiru/first)', 'Accept': 'application/rss+xml,application/atom+xml,text/html;q=0.8'})
    # Uses inherited proxy and trusted CA; certificate validation remains enabled.
    with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as response:
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError('Response exceeds 2 MB limit')
        charset = response.headers.get_content_charset() or 'utf-8'
        return body, charset


def error_code(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return f'HTTP {exc.code}'
    if isinstance(exc, urllib.error.URLError):
        # Do not store URLs with credentials or proxy response contents.
        reason = str(exc.reason)
        if '403' in reason:
            return '接続拒否（403）'
        return 'ネットワーク接続失敗'
    if isinstance(exc, ET.ParseError):
        return 'フィード形式を解析できません'
    return type(exc).__name__


def parse_date(value):
    try:
        dt = parsedate_to_datetime(value)
    except (ValueError, TypeError, OverflowError):
        try:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except (ValueError, TypeError, AttributeError):
            return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).astimezone(UTC)


def rss_query(company, days):
    aliases = ' OR '.join('"' + a.replace('"', '') + '"' for a in company['aliases'])
    query = f'({aliases}) (半導体 OR semiconductor OR wafer OR EUV OR chip) when:{days}d'
    return 'https://news.google.com/rss/search?' + urllib.parse.urlencode({'q': query, 'hl': 'ja', 'gl': 'JP', 'ceid': 'JP:ja'})


def alias_matches(text, alias):
    if re.fullmatch(r'[\x00-\x7f]+', alias):
        return bool(re.search(r'(?<![\w])' + re.escape(alias) + r'(?![\w])', text, re.I))
    return alias.casefold() in text.casefold()


def parse_news(body, company, now, days=90):
    if b'<!DOCTYPE' in body.upper() or b'<!ENTITY' in body.upper():
        raise ValueError('DTD is not accepted')
    root = ET.fromstring(body)
    if root.tag != 'rss' or root.find('channel') is None:
        raise ValueError('Expected RSS channel')
    result = []
    for node in root.findall('./channel/item'):
        title = clean(node.findtext('title', ''))
        url = node.findtext('link', '').strip()
        date = parse_date(node.findtext('pubDate', ''))
        if not safe_url(url) or date is None or date > now + timedelta(days=1) or date < now - timedelta(days=days):
            continue
        # Title-only filter avoids mistaking publisher names/HTML summaries for company mentions.
        if not TERMS.search(title) or not any(alias_matches(title, alias) for alias in company['aliases']):
            continue
        source = node.find('source')
        result.append({'id': identity(url), 'title': title, 'url': canonical_url(url), 'publishedAt': timestamp(date), 'publisher': clean(source.text if source is not None else 'Google News'), 'kind': 'news', 'retrievedAt': timestamp(now), 'relevance': '企業名と半導体関連語が見出しに一致（自動判定）'})
    return result


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.current = None
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag == 'a':
            self.current = dict(attrs).get('href')
            self.parts = []

    def handle_data(self, data):
        if self.current is not None and not self.hidden:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.hidden:
            self.hidden -= 1
        if tag == 'a' and self.current is not None:
            self.links.append((self.current, clean(' '.join(self.parts))))
            self.current = None
            self.parts = []


def official_link(url, base):
    return safe_url(url) and urllib.parse.urlsplit(url).hostname == urllib.parse.urlsplit(base).hostname


def parse_official(text, base, now):
    parser = Links()
    parser.feed(text)
    items = []
    for href, title in parser.links:
        url = urllib.parse.urljoin(base, href)
        if not title or not official_link(url, base) or not IR_TERMS.search(title):
            continue
        # Navigation/index links are not disclosures. Only document/dated detail links.
        path = urllib.parse.urlsplit(url).path.lower()
        if not (path.endswith(('.pdf', '.pdf/')) or re.search(r'/(?:19|20)\d{2}(?:/|[-_]?\d{2})', path) or re.search(r'\d{8}', path)):
            continue
        items.append({'id': identity(url), 'title': title, 'url': canonical_url(url), 'publishedAt': None, 'publisher': '企業公式IR', 'kind': 'ir', 'retrievedAt': timestamp(now), 'relevance': '公式IR資料リンク。適時開示の該当性・公表日は未確認。'})
    return items, parser.links


def merge_items(old, new, now, days, limit, keep_old=False):
    merged = {item['id']: item for item in old}
    for item in new:
        merged[item['id']] = item
    items = list(merged.values())
    if not keep_old:
        items = [i for i in items if i.get('publishedAt') is None or (parse_date(i['publishedAt']) or now) >= now - timedelta(days=days)]
    items.sort(key=lambda i: i.get('publishedAt') or i.get('retrievedAt') or '', reverse=True)
    return items[:limit]


def collect_company(company, previous, config, now, fetcher=fetch):
    output = json.loads(json.dumps(previous or {}))
    output.setdefault('news', [])
    output.setdefault('ir', [])
    output.setdefault('sources', {})
    attempted = timestamp(now)
    news_cfg = config['news']
    if news_cfg.get('enabled'):
        url = rss_query(company, news_cfg['windowDays'])
        try:
            body, _ = fetcher(url, config['timeoutSeconds'])
            fresh = parse_news(body, company, now, news_cfg['windowDays'])
            output['news'] = merge_items(output['news'], fresh, now, config['retentionDays'], news_cfg['maxItems'])
            output['sources']['news'] = {'state': 'ok', 'lastAttemptAt': attempted, 'lastSuccessAt': attempted, 'matchedCount': len(fresh), 'feedUrl': url}
        except Exception as exc:
            status = output['sources'].get('news', {})
            output['sources']['news'] = {**status, 'state': 'error', 'lastAttemptAt': attempted, 'error': error_code(exc), 'feedUrl': url}
    else:
        output['sources']['news'] = {'state': 'disabled'}
    ir_url = company.get('irUrl')
    if not config['official'].get('enabled'):
        output['sources']['ir'] = {'state': 'disabled'}
    elif not ir_url:
        output['sources']['ir'] = {'state': 'unconfigured'}
    else:
        try:
            body, charset = fetcher(ir_url, config['timeoutSeconds'])
            fresh, links = parse_official(body.decode(charset, errors='replace'), ir_url, now)
            # At most one same-host IR index is followed; no article/paywall scraping.
            candidate = next((urllib.parse.urljoin(ir_url, href) for href, title in links if INDEX_TERMS.search(title) and official_link(urllib.parse.urljoin(ir_url, href), ir_url) and canonical_url(urllib.parse.urljoin(ir_url, href)) != canonical_url(ir_url) and not urllib.parse.urlsplit(href).path.lower().endswith('.pdf')), None)
            detail_error = None
            if candidate:
                try:
                    body, charset = fetcher(candidate, config['timeoutSeconds'])
                    found, _ = parse_official(body.decode(charset, errors='replace'), candidate, now)
                    fresh.extend(found)
                except Exception as exc:
                    detail_error = error_code(exc)
            output['ir'] = merge_items(output['ir'], fresh, now, config['retentionDays'], config['official']['maxItems'])
            output['sources']['ir'] = {'state': 'partial' if detail_error else 'ok', 'lastAttemptAt': attempted, 'lastSuccessAt': attempted, 'matchedCount': len(fresh), 'sourceUrl': ir_url}
            if detail_error:
                output['sources']['ir']['error'] = detail_error
        except Exception as exc:
            output['sources']['ir'] = {**output['sources'].get('ir', {}), 'state': 'error', 'lastAttemptAt': attempted, 'error': error_code(exc), 'sourceUrl': ir_url}
    return output


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp.write('\n')
        name = tmp.name
    Path(name).replace(path)


def run(catalog, previous, config, now, fetcher=fetch, limit=None):
    result = json.loads(json.dumps(previous))
    result.setdefault('companies', {})
    selected = catalog['companies'][:limit] if limit else catalog['companies']
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        pending = {executor.submit(collect_company, c, result['companies'].get(c['id'], {}), config, now, fetcher): c['id'] for c in selected}
        for task in concurrent.futures.as_completed(pending):
            result['companies'][pending[task]] = task.result()
    result['lastAttemptAt'] = timestamp(now)
    statuses = [result['companies'][c['id']]['sources'] for c in selected]
    success = any(s.get('news', {}).get('state') == 'ok' or s.get('ir', {}).get('state') in ('ok', 'partial') for s in statuses)
    if success:
        result['lastSuccessAt'] = timestamp(now)
    result['summary'] = {'companiesAttempted': len(selected), 'newsSucceeded': sum(s.get('news', {}).get('state') == 'ok' for s in statuses), 'newsFailed': sum(s.get('news', {}).get('state') == 'error' for s in statuses), 'irSucceeded': sum(s.get('ir', {}).get('state') == 'ok' for s in statuses), 'irPartial': sum(s.get('ir', {}).get('state') == 'partial' for s in statuses), 'irFailed': sum(s.get('ir', {}).get('state') == 'error' for s in statuses)}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    catalog = json.loads((ROOT / 'site/data/catalog.json').read_text())
    config = json.loads((ROOT / 'sources.json').read_text())
    path = ROOT / 'site/data/updates.json'
    previous = json.loads(path.read_text())
    result = run(catalog, previous, config, datetime.now(UTC), limit=args.limit)
    atomic_write(path, result)
    print(json.dumps(result['summary'], ensure_ascii=False))
    if config['news']['enabled'] and result['summary']['newsSucceeded'] == 0:
        print('No news feed could be fetched. Previous articles preserved.', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
