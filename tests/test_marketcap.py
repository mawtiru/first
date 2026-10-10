from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
import urllib.error
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'scripts'))
from marketcap import parse_marketcap, collect_marketcap
from update import timestamp, error_code

COMPANY={'id':'asml','listing':{'status':'listed'},'marketCapSource':{'provider':'companiesmarketcap','slug':'asml','ticker':'ASML'}}
PAGE='''<!doctype html><html><head><title>ASML (ASML) - Market capitalization</title></head><body><div class="info-box"><div class="line1">$1.23 T</div><div class="line2">Market cap</div></div><div class="info-box"><div class="line1">$999.00</div><div class="line2">Share price</div></div></body></html>'''
CONFIG={'marketCap':{'enabled':True},'timeoutSeconds':15}
NOW=datetime(2026,10,11,tzinfo=timezone.utc)

class MarketCapTests(unittest.TestCase):
    def test_extracts_only_market_cap_and_preserves_unknown_quote_date(self):
        r=parse_marketcap(PAGE,COMPANY)
        self.assertEqual(r['value'],1.23e12)
        self.assertEqual(r['currency'],'USD')
        self.assertIsNone(r['quoteDate'])

    def test_units_commas_and_markup(self):
        for amount,expected in [('$123.45 B',123.45e9),('$1,200.5 M',1200.5e6),('$567 K',567e3)]:
            self.assertEqual(parse_marketcap(PAGE.replace('$1.23 T',amount),COMPANY)['value'],expected)

    def test_identity_prevents_parent_or_ambiguous_company_confusion(self):
        with self.assertRaises(ValueError):parse_marketcap(PAGE.replace('(ASML)','(OTHER)'),COMPANY)
        merck={**COMPANY,'marketCapSource':{'slug':'merck-kgaa','ticker':'MRK.DE'}}
        with self.assertRaises(ValueError):parse_marketcap(PAGE.replace('ASML','MRK'),merck)

    def test_page_change_and_multiple_figures_are_rejected(self):
        for html in ['<html>Access denied</html>', PAGE.replace('Market cap</div>','Assets</div>'),PAGE.replace('</body>','<div class="info-box">$2 B Market cap</div></body>')]:
            with self.assertRaises(ValueError):parse_marketcap(html,COMPANY)

    def test_failure_keeps_last_successful_market_cap(self):
        old={'state':'ok','value':3e9,'currency':'USD','lastSuccessAt':'2026-10-10T00:00:00Z','retrievedAt':'2026-10-10T00:00:00Z'}
        def fail(*args):raise urllib.error.URLError('Tunnel connection failed: 403 Forbidden')
        r=collect_marketcap(COMPANY,old,CONFIG,NOW,fail,timestamp,error_code)
        self.assertEqual(r['state'],'error')
        self.assertEqual(r['value'],3e9)
        self.assertEqual(r['lastSuccessAt'],old['lastSuccessAt'])
        self.assertEqual(old['state'],'ok')

    def test_private_and_subsidiary_never_request_parent_market_cap(self):
        def no_fetch(*args):raise AssertionError('must not fetch')
        for status in ('private','subsidiary'):
            r=collect_marketcap({**COMPANY,'listing':{'status':status}}, {},CONFIG,NOW,no_fetch,timestamp,error_code)
            self.assertEqual(r,{'state':'not_listed'})

    def test_valid_response_gets_source_and_fetch_timestamp(self):
        def fetch(*args):return PAGE.encode(),'utf-8'
        r=collect_marketcap(COMPANY,{},CONFIG,NOW,fetch,timestamp,error_code)
        self.assertEqual(r['state'],'ok')
        self.assertEqual(r['retrievedAt'],'2026-10-11T00:00:00Z')
        self.assertEqual(r['sourceUrl'],'https://companiesmarketcap.com/asml/marketcap/')

    def test_disabled_or_missing_source_is_explicit(self):
        def no_fetch(*args):raise AssertionError()
        r=collect_marketcap(COMPANY,{}, {'marketCap':{'enabled':False}},NOW,no_fetch,timestamp,error_code)
        self.assertEqual(r['state'],'disabled')
        r=collect_marketcap({'listing':{'status':'listed'}},{},CONFIG,NOW,no_fetch,timestamp,error_code)
        self.assertEqual(r['state'],'unconfigured')
