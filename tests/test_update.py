import copy
from datetime import datetime, timedelta, timezone
import http.server
import json
from pathlib import Path
import sys
import threading
import unittest
import urllib.error
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import update
ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 10, tzinfo=timezone.utc)
COMPANY = {'id': 'tel', 'aliases': ['東京エレクトロン', 'Tokyo Electron'], 'irUrl': 'https://www.tel.com/ir/'}
CONFIG = json.loads((ROOT / 'sources.json').read_text())
RSS = (ROOT / 'tests/fixtures/news.xml').read_bytes()


class CollectorTests(unittest.TestCase):
    def test_news_filters_company_industry_date_and_url(self):
        result = update.parse_news(RSS, COMPANY, NOW)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['publisher'], 'Example Test')
        self.assertEqual(result[0]['publishedAt'], '2026-10-09T03:00:00Z')

    def test_dedup_and_repeatability(self):
        data = update.parse_news(RSS, COMPANY, NOW)
        merged = update.merge_items([], data, NOW, 90, 12)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged, update.merge_items(merged, data, NOW, 90, 12))

    def test_company_alias_does_not_match_substring(self):
        self.assertFalse(update.alias_matches('CLASSIC semiconductor', 'AS'))
        self.assertTrue(update.alias_matches('ASML semiconductor', 'ASML'))

    def test_nonrss_and_xml_entities_rejected(self):
        for data in [b'<html>Access denied</html>', b'<!DOCTYPE rss [<!ENTITY x "test">]><rss/>']:
            with self.assertRaises(ValueError):
                update.parse_news(data, COMPANY, NOW)

    def test_failure_preserves_previous_items_and_last_success(self):
        def fail(*args):
            raise urllib.error.URLError('Tunnel connection failed: 403 Forbidden')
        old = {'news': [{'id':'old','title':'retained','url':'https://example.test','publishedAt':'2020-01-01T00:00:00Z'}], 'ir':[], 'sources':{'news':{'state':'ok','lastSuccessAt':'2026-10-08T00:00:00Z'}}}
        result = update.collect_company(COMPANY, old, CONFIG, NOW, fail)
        self.assertEqual(result['news'], old['news'])
        self.assertEqual(result['sources']['news']['lastSuccessAt'], '2026-10-08T00:00:00Z')
        self.assertEqual(result['sources']['news']['state'], 'error')
        self.assertEqual(old['sources']['news']['state'], 'ok')

    def test_successful_empty_feed_is_not_failure(self):
        company = {**COMPANY, 'irUrl':None}
        def empty(*args): return b'<rss><channel/></rss>', 'utf-8'
        result = update.collect_company(company, {}, CONFIG, NOW, empty)
        self.assertEqual(result['sources']['news']['state'], 'ok')
        self.assertEqual(result['sources']['news']['matchedCount'], 0)
        self.assertEqual(result['sources']['ir']['state'], 'unconfigured')

    def test_official_links_are_same_host_and_documents(self):
        html = '''<a href="/ir/news/">IRニュース</a><a href="/ir/2026/results.pdf">決算説明資料</a><a href="https://thirdparty.test/results.pdf">financial results</a><a href="javascript:alert(1)">決算</a>'''
        items, _ = update.parse_official(html, COMPANY['irUrl'], NOW)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['url'], 'https://www.tel.com/ir/2026/results.pdf')
        self.assertIsNone(items[0]['publishedAt'])
        self.assertEqual(items[0]['kind'], 'ir')

    def test_ir_index_failure_is_partial(self):
        def fetch(url, timeout):
            if 'news/' in url:
                raise urllib.error.URLError('unavailable')
            if 'google.com' in url:
                return RSS, 'utf-8'
            return b'<a href="news/">IR news</a>', 'utf-8'
        result = update.collect_company(COMPANY, {}, CONFIG, NOW, fetch)
        self.assertEqual(result['sources']['ir']['state'], 'partial')

    def test_new_run_keeps_unselected_company_and_timestamps(self):
        catalog = {'companies':[COMPANY]}
        previous = {'companies':{'other':{'news':[]}},'lastSuccessAt':None}
        def fetch(*args): return RSS, 'utf-8'
        config = copy.deepcopy(CONFIG)
        config['official']['enabled'] = False
        result = update.run(catalog, previous, config, NOW, fetch)
        self.assertIn('other', result['companies'])
        self.assertEqual(result['summary']['newsSucceeded'], 1)
        self.assertEqual(result['lastSuccessAt'], '2026-10-10T00:00:00Z')
        self.assertEqual(previous['lastSuccessAt'], None)

    def test_failed_run_does_not_advance_success(self):
        def fail(*args): raise TimeoutError()
        result = update.run({'companies':[COMPANY]}, {'companies':{},'lastSuccessAt':'2026-10-01T00:00:00Z'}, CONFIG, NOW, fail)
        self.assertEqual(result['lastSuccessAt'], '2026-10-01T00:00:00Z')
        self.assertEqual(result['summary']['newsFailed'], 1)

    def test_real_http_fetch_and_parsing(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type','application/rss+xml; charset=utf-8')
                self.end_headers()
                self.wfile.write(RSS)
            def log_message(self,*args): pass
        server = http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            body, charset = update.fetch(f'http://127.0.0.1:{server.server_port}/feed')
            self.assertEqual(charset,'utf-8')
            self.assertEqual(len(update.parse_news(body,COMPANY,NOW)),2)
        finally:
            server.shutdown()
            server.server_close()

    def test_atomic_output_is_valid_json(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'data.json'
            update.atomic_write(path, {'日本語':'保持'})
            self.assertEqual(json.loads(path.read_text()), {'日本語':'保持'})

if __name__ == '__main__': unittest.main()
