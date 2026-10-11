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
        self.assertEqual(len(CATALOG['companies']),77)
        phases = [s['phase'] for s in CATALOG['stages']]
        self.assertEqual(phases, ['front']*8+['back']*3)
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
        self.assertEqual(companies['rorze']['category'], 'equipment')
        self.assertEqual(companies['sinfonia']['category'], 'equipment')
        self.assertEqual(companies['ferrotec']['category'], 'parts')
        self.assertEqual(companies['tatsumo']['category'], 'equipment')
        self.assertIn('packaging', companies['tatsumo']['stageIds'])

    def test_probe_test_precedes_dicing_and_is_not_final_test(self):
        stages = {s['id']: s for s in CATALOG['stages']}
        stage_ids = [s['id'] for s in CATALOG['stages']]
        self.assertEqual(stages['inspection']['phase'], 'front')
        self.assertLess(stage_ids.index('inspection'), stage_ids.index('dicing'))
        self.assertEqual(stages['test']['phase'], 'back')
        for cid in ('mjc', 'jem'):
            company = next(c for c in CATALOG['companies'] if c['id'] == cid)
            self.assertIn('inspection', company['stageIds'])
            self.assertNotIn('test', company['stageIds'])

    def test_common_infrastructure_is_separate_from_process_sequence(self):
        companies = {c['id']: c for c in CATALOG['companies']}
        self.assertEqual({t['id'] for t in CATALOG['infrastructure']}, {'wafer-handling', 'water-treatment', 'electronics-assembly', 'factory-support', 'vacuum-abatement', 'fluid-management'})
        for cid in ('rorze', 'sinfonia', 'daifuku', 'murata-machinery', 'nomura-micro', 'kurita'):
            self.assertEqual(companies[cid]['stageIds'], [])
            self.assertEqual(companies[cid]['infrastructureIds'], ['water-treatment' if cid in ('nomura-micro', 'kurita') else 'wafer-handling'])
        self.assertIn('wafer-handling', companies['tatsumo']['infrastructureIds'])
        self.assertIn('packaging', companies['tatsumo']['stageIds'])
        data = copy.deepcopy(CATALOG)
        data['companies'][0]['infrastructureIds'] = ['unknown']
        with self.assertRaises(ValueError):
            validate(data, RESEARCH)

    def test_added_mask_and_equipment_suppliers_have_distinct_roles(self):
        companies = {c['id']: c for c in CATALOG['companies']}
        expected = {'lasertec': ('6920.T', 'parts', ['lithography']),
                    'shibaura-mechatronics': ('6590.T', 'equipment', ['clean', 'deposition', 'etch', 'packaging']),
                    'tekscend-photomask': ('429A.T', 'materials', ['lithography']),
                    'hoya': ('7741.T', 'materials', ['lithography'])}
        for cid, (ticker, category, stages) in expected.items():
            c = companies[cid]
            self.assertEqual(c['listing']['ticker'], ticker)
            self.assertEqual(c['category'], category)
            self.assertEqual(c['stageIds'], stages)
            self.assertEqual(c['profile']['informationStatus'], 'reference')
            self.assertTrue(c['profile']['industryPosition'])
        self.assertIn('Toppan Photomask', companies['tekscend-photomask']['aliases'])
        self.assertIn('マスクブランクス', companies['hoya']['products'])
        self.assertIn('フォトマスク', companies['tekscend-photomask']['products'])
        self.assertIsNone(companies['tekscend-photomask']['marketCapSource'])

    def test_chemical_materials_have_correct_roles_and_company_identity(self):
        companies = {c['id']: c for c in CATALOG['companies']}
        expected = {'fuso-chemical': ('4368.T', ['clean']),
                    'kanto-denka': ('4047.T', ['etch', 'deposition', 'clean']),
                    'asahi-kasei': ('3407.T', ['packaging']),
                    'mitsubishi-chemical': (None, ['lithography', 'clean']),
                    'mitsui-chemicals': ('4183.T', ['lithography', 'dicing', 'packaging']),
                    'jx-advanced-metals': ('5016.T', ['deposition', 'packaging']),
                    'adeka': ('4401.T', ['deposition', 'lithography'])}
        for cid, (ticker, stages) in expected.items():
            c = companies[cid]
            self.assertEqual(c['listing']['ticker'], ticker)
            self.assertEqual(c['stageIds'], stages)
            self.assertEqual(c['category'], 'materials')
            self.assertEqual(c['profile']['informationStatus'], 'reference')
        subsidiary = companies['mitsubishi-chemical']
        self.assertEqual(subsidiary['listing']['status'], 'subsidiary')
        self.assertEqual(subsidiary['listing']['parent'], '三菱ケミカルグループ')
        self.assertIsNone(subsidiary['marketCapSource'])

    def test_wafer_container_suppliers_are_independent_infrastructure(self):
        companies = {c['id']: c for c in CATALOG['companies']}
        for cid in ('shin-etsu-polymer', 'miraial'):
            c = companies[cid]
            self.assertEqual(c['category'], 'parts')
            self.assertEqual(c['stageIds'], [])
            self.assertEqual(c['infrastructureIds'], ['wafer-handling'])
            self.assertTrue(c['profile']['strengths'])
        self.assertNotEqual(companies['shin-etsu-polymer']['id'], companies['shinetsu']['id'])
        self.assertEqual(companies['shin-etsu-polymer']['listing']['status'], 'unknown')
        self.assertIsNone(companies['shin-etsu-polymer']['marketCapSource'])
        self.assertEqual(companies['miraial']['listing']['ticker'], '4238.T')
        self.assertEqual(companies['hirata']['listing']['ticker'], '6258.T')

    def test_vacuum_equipment_and_board_assembly_are_distinct(self):
        companies = {c['id']: c for c in CATALOG['companies']}
        self.assertEqual(companies['ulvac']['stageIds'], ['deposition', 'etch'])
        self.assertEqual(companies['ulvac']['listing']['ticker'], '6728.T')
        fuji = companies['fuji']
        self.assertEqual(fuji['stageIds'], [])
        self.assertEqual(fuji['infrastructureIds'], ['electronics-assembly'])
        self.assertEqual(fuji['listing']['ticker'], '6134.T')
        self.assertIn('富士機械製造', fuji['aliases'])
        self.assertIn('半導体パッケージ完成後', fuji['profile']['industryPosition'])

    def test_industrial_suppliers_and_ngk_identity(self):
        companies = {c['id']: c for c in CATALOG['companies']}
        for cid in ('tocalo', 'japan-material', 'technoflex', 'nsk', 'niterra', 'rigaku-holdings', 'fig', 'daido-steel', 'marumae'):
            self.assertTrue(companies[cid]['profile']['industryPosition'])
        self.assertEqual(companies['ngk']['listing']['ticker'], '5333.T')
        self.assertEqual(companies['niterra']['listing']['ticker'], '5334.T')
        self.assertIn('NGK', companies['ngk']['aliases'])
        self.assertEqual(companies['rigaku-holdings']['stageIds'], ['inspection'])
        self.assertEqual(companies['sumitomo-heavy-industries']['stageIds'], ['ion-implantation'])
        self.assertEqual(companies['sumitomo-heavy-industries']['listing']['ticker'], '6302.T')
        for cid in ('nsk', 'fig', 'daido-steel'):
            self.assertEqual(companies[cid]['stageIds'], [])
            self.assertEqual(companies[cid]['infrastructureIds'], ['factory-support'])

    def test_handling_system_suppliers_are_equipment_and_containers_are_parts(self):
        companies = {c['id']: c for c in CATALOG['companies']}
        for cid in ('rorze', 'hirata', 'sinfonia', 'tatsumo'):
            self.assertEqual(companies[cid]['category'], 'equipment')
            self.assertIn('wafer-handling', companies[cid]['infrastructureIds'])
        for cid in ('shin-etsu-polymer', 'miraial'):
            self.assertEqual(companies[cid]['category'], 'parts')
        self.assertEqual(companies['tatsumo']['stageIds'], ['lithography', 'clean', 'packaging'])

    def test_audit_moves_and_override_validation(self):
        companies = {c['id']: c for c in CATALOG['companies']}
        self.assertEqual(companies['ebara']['stageIds'], ['clean'])
        self.assertEqual(companies['ebara']['category'], 'equipment')
        self.assertEqual(companies['edwards']['stageIds'], [])
        self.assertNotIn('test', companies['accretech']['stageIds'])
        self.assertEqual(companies['entegris']['infrastructureCategories']['wafer-handling'], 'parts')
        self.assertEqual(companies['japan-material']['category'], 'services')
        self.assertEqual(companies['tocalo']['category'], 'services')
        self.assertIn('thermal', companies['kokusai']['stageIds'])
        for overrides in ({'missing': 'parts'}, {'lithography': 'invalid'}):
            catalog = copy.deepcopy(CATALOG)
            catalog['companies'][0]['stageCategories'] = overrides
            with self.assertRaises(ValueError):
                validate(catalog, RESEARCH)

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
