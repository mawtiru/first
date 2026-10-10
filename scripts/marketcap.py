"""Read a market-cap figure from a publicly accessible company page, without estimates."""
from datetime import timezone
from html.parser import HTMLParser
import math
import re

VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}


class CapPage(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.in_title = False
        self.title = []
        self.current = None
        self.boxes = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in VOID:
            return
        self.depth += 1
        if tag == 'title':
            self.in_title = True
        if tag in ('script','style'):
            self.hidden += 1
        classes = dict(attrs).get('class','').split()
        if 'info-box' in classes and self.current is None:
            self.current = {'depth':self.depth,'text':[]}

    def handle_data(self, value):
        if self.hidden:
            return
        if self.in_title:
            self.title.append(value)
        if self.current is not None:
            self.current['text'].append(value)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if self.current is not None and self.depth == self.current['depth']:
            self.boxes.append(' '.join(self.current['text']))
            self.current = None
        if tag == 'title':
            self.in_title = False
        if tag in ('script','style') and self.hidden:
            self.hidden -= 1
        self.depth = max(0,self.depth-1)


def parse_marketcap(text, company):
    parser = CapPage()
    parser.feed(text)
    title = ' '.join(parser.title)
    ticker = company['marketCapSource']['ticker']
    # Exact exchange-qualified ticker avoids confusing Merck KGaA with Merck & Co.,
    # parent vs subsidiary, and unrelated companies with similar names.
    if not re.search(r'\(\s*' + re.escape(ticker) + r'\s*\)', title, re.I):
        raise ValueError('Market-cap page does not match the configured company ticker')
    if not re.search(r'market cap(?:italization)?', title, re.I):
        raise ValueError('Not a market-cap page')
    values = []
    for box in parser.boxes:
        if not re.search(r'\bMarket cap\b', box, re.I):
            continue
        match = re.search(r'\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*([TBMK])\b', box, re.I)
        if not match:
            continue
        value = float(match[1].replace(',','')) * {'T':1e12,'B':1e9,'M':1e6,'K':1e3}[match[2].upper()]
        if math.isfinite(value) and value > 0:
            values.append(value)
    if len(values) != 1:
        raise ValueError('Exactly one USD market-cap figure was not found')
    return {'value':values[0],'currency':'USD','quoteDate':None,'sourceTitle':title.strip(),'ticker':ticker}


def collect_marketcap(company, previous, config, now, fetcher, format_time, describe_error):
    output = dict(previous or {})
    source = company.get('marketCapSource')
    if company.get('listing',{}).get('status') in ('private','subsidiary'):
        return {'state':'not_listed'}
    if not config.get('marketCap',{}).get('enabled',False):
        return {**output,'state':'disabled'}
    if not source:
        return {**output,'state':'unconfigured'}
    slug = source['slug']
    if not re.fullmatch(r'[a-z0-9-]+', slug):
        raise ValueError('Invalid market-cap source slug')
    url = f'https://companiesmarketcap.com/{slug}/marketcap/'
    try:
        body, charset = fetcher(url, config['timeoutSeconds'])
        value = parse_marketcap(body.decode(charset,errors='replace'),company)
        return {**value,'state':'ok','lastAttemptAt':format_time(now),'lastSuccessAt':format_time(now),'retrievedAt':format_time(now),'sourceUrl':url,'provider':'CompaniesMarketCap','note':'全社の株式時価総額・米ドル参考値。取得元に算定基準日の明示なし。半導体事業単独の価値ではありません。'}
    except Exception as exc:
        return {**output,'state':'error','lastAttemptAt':format_time(now),'sourceUrl':url,'error':describe_error(exc)}
