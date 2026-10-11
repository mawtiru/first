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
    infrastructure = catalog.get('infrastructure', [])
    infrastructure_ids = {t['id'] for t in infrastructure}
    require(len(infrastructure_ids) == len(infrastructure), 'Duplicate infrastructure ID')
    for t in infrastructure:
        require(t.get('name') and t.get('description'), 'Incomplete infrastructure topic')
    for c in companies:
        require(c['name'] and c['aliases'] and (c['stageIds'] or c.get('infrastructureIds')), f"Incomplete company: {c['id']}")
        require(c['category'] in ('equipment', 'parts', 'materials', 'services'), 'Invalid category')
        require(set(c['stageIds']) <= stage_ids, 'Unknown stage reference')
        require(set(c.get('infrastructureIds', [])) <= infrastructure_ids, 'Unknown infrastructure reference')
        for field, refs in [('stageCategories', c['stageIds']), ('infrastructureCategories', c.get('infrastructureIds', []))]:
            overrides = c.get(field, {})
            require(set(overrides) <= set(refs), 'Category override outside company scope')
            require(all(v in ('equipment', 'parts', 'materials', 'services') for v in overrides.values()), 'Invalid category override')
        require(valid_url(c['website']), 'Invalid company URL')
        require(c.get('irUrl') is None or valid_url(c['irUrl']), 'Invalid IR URL')
        profile = c.get('profile')
        if profile:
            require(profile.get('summary') and profile.get('industryPosition') and profile.get('strengths'), 'Incomplete company profile')
            require(profile['informationStatus'] in ('reference', 'verified'), 'Invalid profile status')
            require(valid_url(profile.get('sourceUrl')), 'Invalid profile confirmation URL')
            if profile['informationStatus'] == 'verified':
                require(profile.get('verifiedAt'), 'Verified profile needs confirmation date')
        listing = c.get('listing')
        if listing:
            require(listing['status'] in ('listed', 'private', 'subsidiary', 'unknown'), 'Invalid listing status')
            if listing['status'] != 'listed':
                require(not c.get('marketCapSource'), 'Do not fetch a parent market cap for an unlisted company')
                require(not listing.get('ticker'), 'Unlisted company must not use a parent ticker')
        cap_source = c.get('marketCapSource')
        if cap_source:
            import re
            require(cap_source['provider'] == 'companiesmarketcap', 'Unsupported market-cap provider')
            require(re.fullmatch(r'[a-z0-9-]+', cap_source['slug']), 'Invalid market-cap slug')
            require(cap_source.get('ticker') == listing.get('ticker'), 'Company and market-cap tickers differ')
        for facility in c.get('facilities', []):
            require(facility.get('name') and facility.get('location') and facility.get('function'), 'Incomplete facility')
            require(facility['status'] in ('verified', 'unverified'), 'Invalid facility verification status')
            require(facility['kind'] in ('manufacturing_candidate', 'manufacturing', 'rd'), 'Invalid facility type')
            require(valid_url(facility.get('sourceUrl')), 'Invalid facility confirmation URL')
            if facility['status'] == 'verified':
                require(facility.get('verifiedAt'), 'Verified facility needs confirmation date')

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
