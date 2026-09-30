"""Bounded logical-case storage preserves every previous evidence value."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from scripts.generate_nacelle_evidence import (
    CASE_FILE_MAX_BYTES, ROOT, read_evidence, write_evidence, check,
)


class NacelleEvidenceStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved = read_evidence(ROOT / 'examples' / 'nacelle_evidence' / 'manifest.json')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.index = Path(self.tmp.name) / 'manifest.json'
        self.manifest = write_evidence(self.saved, self.index)

    def change_index(self, manifest):
        self.index.write_text(json.dumps(manifest), encoding='utf-8')

    def test_exact_roundtrip_and_complete_bounded_cases(self):
        self.assertEqual(read_evidence(self.index), self.saved)
        self.assertEqual(len(self.manifest['case_files']), 8)
        self.assertNotIn('cases', self.manifest['metadata'])
        for part in self.manifest['case_files']:
            data = (self.index.parent / part['file']).read_bytes()
            self.assertLessEqual(len(data), CASE_FILE_MAX_BYTES)
            self.assertEqual(part['bytes'], len(data))
            self.assertEqual(part['sha256'], hashlib.sha256(data).hexdigest())
            self.assertEqual(json.loads(data), self.saved['cases'][part['name']])

    def test_missing_case_rejected(self):
        (self.index.parent / self.manifest['case_files'][0]['file']).unlink()
        with self.assertRaises(FileNotFoundError): read_evidence(self.index)

    def test_same_size_corruption_rejected(self):
        path = self.index.parent / self.manifest['case_files'][0]['file']
        data = bytearray(path.read_bytes()); data[20] ^= 1; path.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'checksum'): read_evidence(self.index)

    def test_growth_is_bounded_and_rejected(self):
        path = self.index.parent / self.manifest['case_files'][0]['file']
        with path.open('ab') as handle: handle.write(b' ' * 500)
        with self.assertRaisesRegex(ValueError, 'bounded size'): read_evidence(self.index)

    def test_duplicate_and_traversal_names_rejected(self):
        index = copy.deepcopy(self.manifest)
        index['case_files'].append(index['case_files'][0])
        self.change_index(index)
        with self.assertRaisesRegex(ValueError, 'Duplicate'): read_evidence(self.index)
        index = copy.deepcopy(self.manifest)
        index['case_files'][0]['file'] = '../outside.json'
        self.change_index(index)
        with self.assertRaisesRegex(ValueError, 'unsafe'): read_evidence(self.index)

    def test_metadata_or_full_identity_change_rejected(self):
        self.manifest['metadata']['scope'] += ' altered'
        self.change_index(self.manifest)
        with self.assertRaisesRegex(ValueError, 'identity'): read_evidence(self.index)

    def test_writer_rejects_oversize_before_replacing_index(self):
        before = self.index.read_bytes()
        invalid = copy.deepcopy(self.saved)
        invalid['cases']['source_peak_reference']['oversized'] = 'x' * CASE_FILE_MAX_BYTES
        with self.assertRaisesRegex(ValueError, 'exceeds'): write_evidence(invalid, self.index)
        self.assertEqual(self.index.read_bytes(), before)
        self.assertEqual(read_evidence(self.index), self.saved)

    def test_numeric_reproduction_keeps_strict_tolerance(self):
        check(self.saved, read_evidence(self.index))
        changed = copy.deepcopy(self.saved)
        changed['cases']['source_peak_reference']['mass_kg'] += .01
        with self.assertRaisesRegex(ValueError, 'mass_kg'): check(self.saved, changed)
