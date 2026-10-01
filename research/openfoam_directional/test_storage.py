"""Lossless publication transport checks; no solver execution."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
import storage


class TestStorage(unittest.TestCase):
    def test_all_original_identities(self):
        items = storage.records()
        self.assertEqual(len(items), 5)
        for item in items:
            data = storage.unpack(item)
            self.assertEqual(len(data), item['bytes'])
            self.assertEqual(hashlib.sha256(data).hexdigest(), item['sha256'])
            self.assertEqual(storage.read_bytes(storage.HERE / item['path']), data)
            self.assertTrue(all(p['bytes'] <= 60000 for p in item['parts']))

    def test_bad_original_hash_rejected(self):
        item = copy.deepcopy(storage.records()[0])
        item['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            storage.unpack(item)

    def test_bad_part_hash_rejected(self):
        item = copy.deepcopy(storage.records()[0])
        item['parts'][0]['sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            storage.unpack(item)

    def test_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                storage.checked_path(Path(tmp), '../escape')


if __name__ == '__main__':
    unittest.main()
