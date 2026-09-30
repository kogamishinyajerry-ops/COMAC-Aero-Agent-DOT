"""HTTP contract and isolation tests for the independent Mod II assembly lab."""
from __future__ import annotations
import http.client
import json
import threading
from http.server import ThreadingHTTPServer
import unittest

from aerolab.server import Handler


class NacelleApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=120)
        conn.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers or {})
        response = conn.getresponse()
        data = response.read()
        status, headers = response.status, response.headers
        conn.close()
        return status, data, headers

    def test_catalog_geometry_and_shared_fingerprint(self):
        status, raw, _ = self.request('GET', '/api/nacelle/catalog')
        self.assertEqual(status, 200)
        catalog = json.loads(raw)
        self.assertIn('geometry', catalog)
        self.assertIn('boundary', catalog)
        status, raw, _ = self.request('GET', '/api/nacelle/geometry')
        self.assertEqual(status, 200)
        geometry = json.loads(raw)
        self.assertGreater(len(geometry['components']), 15)
        ids = [part['id'] for part in geometry['components']]
        self.assertEqual(len(ids), len(set(ids)))
        status, raw, _ = self.request('POST', '/api/nacelle/geometry', {})
        self.assertEqual(status, 200)
        self.assertEqual(geometry['fingerprint'], json.loads(raw)['fingerprint'])
        status, raw, _ = self.request('POST', '/api/nacelle/evaluate', {'geometry': geometry['parameters']})
        self.assertEqual(status, 200)
        result = json.loads(raw)
        self.assertEqual(result['geometry'], geometry['parameters'])
        self.assertEqual(result['metrics']['fingerprint'], geometry['fingerprint'])

    def test_comparison_consistent_boundaries(self):
        status, raw, _ = self.request('POST', '/api/nacelle/compare', {})
        self.assertEqual(status, 200)
        result = json.loads(raw)
        self.assertEqual(result['reference']['boundary'], result['candidate']['boundary'])
        self.assertEqual(result['reference']['geometry'], result['candidate']['geometry'])

    def test_bounded_live_story_has_no_user_supplied_targets(self):
        status, raw, _ = self.request('POST', '/api/nacelle/story', {})
        self.assertEqual(status, 200)
        story = json.loads(raw)
        self.assertEqual(story['execution'], 'computed')
        self.assertEqual(len(story['cases']), 6)
        self.assertFalse(story['claims']['physically_validated'])
        self.assertEqual(self.request('POST', '/api/nacelle/story', {'geometry': {}})[0], 400)
        self.assertEqual(self.request('POST', '/api/nacelle/story', {'boundary': {}})[0], 400)

    def test_named_default_step_without_arbitrary_files(self):
        status, raw, headers = self.request('POST', '/api/nacelle/step', {})
        self.assertEqual(status, 200)
        self.assertTrue(raw.startswith(b'ISO-10303-21;'))
        self.assertEqual(headers['Content-Type'], 'model/step')
        for body in ({'path': '/tmp/data'}, {'geometry': {}, 'boundary': {}}, {'geometry': {'untrusted': 1}}):
            self.assertEqual(self.request('POST', '/api/nacelle/step', body)[0], 400)
        self.assertEqual(self.request('GET', '/cad/nacelle/manifest.json')[0], 404)

    def test_invalid_input_and_cross_origin(self):
        invalid = [[], {'unexpected': 1}, {'geometry': []}, {'geometry': {'__proto__': 1}}, {'boundary': {'ambient_c': float('inf')}}, {'boundary': {'ambient_c': 10**400}}]
        for body in invalid:
            self.assertEqual(self.request('POST', '/api/nacelle/evaluate', body)[0], 400, repr(body))
        self.assertEqual(self.request('POST', '/api/nacelle/evaluate', {}, {'Origin': 'https://example.com'})[0], 403)

    def test_separate_ui_and_old_model_access(self):
        status, raw, _ = self.request('GET', '/nacelle')
        self.assertEqual(status, 200)
        self.assertIn(b'nacelle.js', raw)
        for path, expected in [('/nacelle.js', 'text/javascript'), ('/nacelle.css', 'text/css'), ('/nacelle_story.js', 'text/javascript')]:
            status, raw, headers = self.request('GET', path)
            self.assertEqual(status, 200)
            self.assertIn(expected, headers['Content-Type'])
            self.assertGreater(len(raw), 100)
        self.assertEqual(self.request('GET', '/api/cad/catalog')[0], 200)
        self.assertEqual(self.request('GET', '/api/catalog')[0], 200)
