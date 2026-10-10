import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate import validate
ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / 'site/data/catalog.json').read_text())
RESEARCH = json.loads((ROOT / 'site/data/research.json').read_text())

class DataTests(unittest.TestCase):
    def test_catalog_is_ready(self):
        self.assertTrue(validate(CATALOG, RESEARCH))
        self.assertEqual(len(CATALOG['companies']),51)
        phases = [s['phase'] for s in CATALOG['stages']]
        self.assertEqual(phases, ['front']*6+['back']*3)
        for stage in CATALOG['stages']:
            self.assertTrue(any(c['category']=='equipment' and stage['id'] in c['stageIds'] for c in CATALOG['companies']))

    def test_added_suppliers_have_correct_codes_and_stage_roles(self):
        companies = {c['id']: c for c in CATALOG['companies']}
        for cid, ticker in [('rorze','6323.T'),('sinfonia','6507.T'),('ferrotec','6890.T'),('tatsumo','6266.T')]:
            c = companies[cid]
            self.assertEqual(c['listing']['ticker'], ticker)
            self.assertEqual(c['marketCapSource']['ticker'], ticker)
            self.assertTrue(c['profile']['summary'])
            self.assertTrue(c['aliases'])
        self.assertEqual(companies['rorze']['category'], 'parts')
        self.assertEqual(companies['sinfonia']['category'], 'parts')
        self.assertEqual(companies['ferrotec']['category'], 'parts')
        self.assertEqual(companies['tatsumo']['category'], 'equipment')
        self.assertIn('packaging', companies['tatsumo']['stageIds'])

    def market(self):
        return {'id':'test-market','status':'verified','product':'TEST ONLY','year':2025,'region':'世界','measure':'売上金額','definition':'TEST ONLY','sourceUrl':'https://example.test/report','verifiedAt':'2026-10-10','rows':[{'companyId':'asml','share':50},{'companyId':'nikon','share':30}]}

    def test_market_missing_source_and_excess_share_rejected(self):
        for change in [{'sourceUrl':''},{'rows':[{'companyId':'asml','share':90},{'companyId':'nikon','share':60}]}]:
            data=copy.deepcopy(RESEARCH)
            data['markets']=[{**self.market(),**change}]
            with self.assertRaises(ValueError):validate(CATALOG,data)

    def test_market_unknown_company_rejected(self):
        data=copy.deepcopy(RESEARCH)
        market=self.market()
        market['rows'][0]['companyId']='unknown'
        data['markets']=[market]
        with self.assertRaises(ValueError):validate(CATALOG,data)

    def test_finance_missing_verification_provenance_rejected(self):
        data=copy.deepcopy(RESEARCH)
        data['finance']['tel']={'sales':{'status':'verified','segment':10,'total':20}}
        with self.assertRaises(ValueError):validate(CATALOG,data)

    def test_finance_verified_zero_and_negative_profit_remain_explicit(self):
        data=copy.deepcopy(RESEARCH)
        data['finance']['tel']={'period':'TEST','segment':'TEST','basis':'TEST','unit':'TEST','sourceUrl':'https://example.test/report','verifiedAt':'2026-10-10','sales':{'status':'verified','segment':0,'total':0},'operatingProfit':{'status':'verified','segment':-1,'total':-2}}
        self.assertTrue(validate(CATALOG,data))

    def test_unsafe_disclosure_url_rejected(self):
        data=copy.deepcopy(RESEARCH)
        data['disclosures']['tel']=[{'status':'verified','title':'TEST','publishedAt':'2026-10-10','publisher':'TEST','url':'javascript:alert(1)'}]
        with self.assertRaises(ValueError):validate(CATALOG,data)
