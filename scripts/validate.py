"""Validate published catalog and reviewed financial/market data."""
import json
import math
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def valid_url(value):
    try:
        p = urlsplit(value)
        return p.scheme in ('https', 'http') and p.hostname and not p.username and not p.password
    except (TypeError, ValueError):
        return False


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate(catalog, research):
    companies = catalog['companies']
    ids = {c['id'] for c in companies}
    stage_ids = {s['id'] for s in catalog['stages']}
    require(len(ids) == len(companies), 'Duplicate company ID')
    require(len(stage_ids) == len(catalog['stages']), 'Duplicate stage ID')
    for c in companies:
        require(c['name'] and c['aliases'] and c['stageIds'], f"Incomplete company: {c['id']}")
        require(c['category'] in ('equipment', 'parts', 'materials'), 'Invalid category')
        require(set(c['stageIds']) <= stage_ids, 'Unknown stage reference')
        require(valid_url(c['website']), 'Invalid company URL')
        require(c.get('irUrl') is None or valid_url(c['irUrl']), 'Invalid IR URL')
    for cid, f in research['finance'].items():
        require(cid in ids, 'Unknown financial company ID')
        for key in ('period', 'segment', 'basis', 'unit', 'sourceUrl', 'verifiedAt'):
            require(f.get(key), f'Missing financial provenance: {key}')
        require(valid_url(f['sourceUrl']), 'Invalid financial source URL')
        for metric in ('sales', 'operatingProfit'):
            m = f.get(metric, {'status': 'unverified'})
            require(m['status'] in ('verified', 'undisclosed', 'unverified'), 'Invalid financial status')
            if m['status'] == 'verified':
                require(finite(m.get('total')) and finite(m.get('segment')), 'Missing verified amounts')
                if metric == 'sales':
                    require(m['total'] >= 0 and m['segment'] >= 0, 'Sales must not be negative')
    market_ids = set()
    for market in research['markets']:
        require(market['id'] not in market_ids, 'Duplicate market ID')
        market_ids.add(market['id'])
        require(market['status'] in ('verified', 'unverified'), 'Invalid market status')
        if market['status'] != 'verified':
            continue
        for key in ('product', 'year', 'region', 'measure', 'definition', 'sourceUrl', 'verifiedAt'):
            require(market.get(key), f'Missing market provenance: {key}')
        require(valid_url(market['sourceUrl']), 'Invalid market source URL')
        rows = market['rows']
        require(len(rows) >= 2, 'Market comparison requires at least two rows')
        seen = set()
        total = 0
        for row in rows:
            require(not row.get('companyId') or row['companyId'] in ids, 'Unknown market company ID')
            rid = row.get('companyId') or row.get('name')
            require(rid and rid not in seen, 'Duplicate or missing market row name')
            seen.add(rid)
            share = row.get('share')
            require(share is None or (finite(share) and 0 <= share <= 100), 'Invalid market share')
            total += share or 0
        require(total <= 100.5, 'Market shares exceed 100% beyond rounding tolerance')
    for cid, items in research['disclosures'].items():
        require(cid in ids, 'Unknown disclosure company ID')
        for item in items:
            require(item['status'] in ('verified', 'unverified'), 'Invalid disclosure status')
            if item['status'] == 'verified':
                require(item.get('title') and item.get('publishedAt') and item.get('publisher') and valid_url(item.get('url')), 'Incomplete verified disclosure')
    return True


if __name__ == '__main__':
    catalog = json.loads((ROOT / 'site/data/catalog.json').read_text())
    research = json.loads((ROOT / 'site/data/research.json').read_text())
    validate(catalog, research)
    print(f"Validated: {len(catalog['companies'])} companies, {len(catalog['stages'])} stages")
