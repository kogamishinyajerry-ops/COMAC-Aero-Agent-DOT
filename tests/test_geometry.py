"""Analytic contract, bundled CAD integrity and optional independent kernel tests."""
from dataclasses import asdict
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from aerolab.geometry import (
    CAD_DIR, GEOMETRY_PRESETS, Geometry, build_solid, cad_status,
    generate_step, generate_stl, geometry_fingerprint, geometry_metrics,
    geometry_preview_svg, inspect_brep, inspect_stl, parse_geometry,
)


class GeometryContractTests(unittest.TestCase):
    def test_reference_source_dimensions_and_exact_si_metrics(self):
        p, m = Geometry(), geometry_metrics()
        self.assertEqual(p.fin_count, 43)
        self.assertAlmostEqual(p.gap_mm, 3.137380952380952)
        self.assertAlmostEqual(m['volume_mm3'], 1178985.198, places=6)
        self.assertAlmostEqual(m['volume_m3'], .001178985198, places=12)
        self.assertAlmostEqual(m['mass_kg'], 3.1832600346, places=10)
        self.assertAlmostEqual(m['channel_heated_area_m2'], 1.389544222, places=10)
        self.assertAlmostEqual(m['flow_area_m2'], .00540257, places=10)
        self.assertAlmostEqual(m['hydraulic_diameter_m'], .005828738192979712, places=12)
        self.assertEqual(m['bbox_mm'], {'x': 179.5, 'y': 388.6, 'z': 47})
        self.assertEqual(m['method'], 'analytic_rectangular_fin_geometry')

    def test_heated_area_and_geometrical_wetted_perimeter_are_distinct(self):
        p, m = Geometry(), geometry_metrics()
        self.assertLess(m['heated_perimeter_m'], m['wetted_perimeter_m'])
        self.assertAlmostEqual(m['wetted_perimeter_m']-m['heated_perimeter_m'], (p.fin_count-1)*p.gap_mm/1000)
        self.assertAlmostEqual(m['channel_heated_area_m2'], m['heated_perimeter_m']*m['length_m'])
        self.assertAlmostEqual(m['hydraulic_diameter_m'], 4*m['flow_area_m2']/m['wetted_perimeter_m'])
        self.assertLess(m['channel_heated_area_m2'], m['all_solid_surface_area_m2'])

    def test_invalid_dimensions_are_rejected_at_constructor_and_parser(self):
        cases = [({'length_mm': 0}), ({'width_mm': -1}), ({'fin_count': True}),
                 ({'fin_count': 43.5}), ({'fin_count': 10**1000}), ({'fin_count': 1}), ({'fin_count': 121}),
                 ({'fin_height_mm': float('nan')}), ({'base_thickness_mm': float('inf')}),
                 ({'fin_thickness_mm': '1.11'}), ({'fin_count': 120, 'fin_thickness_mm': 2}),
                 ({'width_mm': 47.75, 'fin_count': 43, 'fin_thickness_mm': 1.11})]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    parse_geometry(kwargs)
                with self.assertRaises(ValueError):
                    Geometry(**kwargs)
        for bad in ([], 'reference', 3, {'gap_mm': 3}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_geometry(bad)

    def test_validation_includes_density(self):
        for density in (0, -1, True, '2700', float('nan'), float('inf')):
            with self.subTest(density=density), self.assertRaises(ValueError):
                geometry_metrics(density_kg_m3=density)
        self.assertAlmostEqual(geometry_metrics(density_kg_m3=1350)['mass_kg']*2, geometry_metrics()['mass_kg'])

    def test_fingerprint_is_canonical_and_changes_each_dimension(self):
        p = Geometry()
        fingerprint = geometry_fingerprint(p)
        self.assertEqual(fingerprint, geometry_fingerprint(asdict(p)))
        self.assertEqual(fingerprint, geometry_fingerprint({'fin_count': 43.0}))
        self.assertEqual(fingerprint, geometry_fingerprint(dict(reversed(list(asdict(p).items())))))
        for key, value in asdict(p).items():
            changed = {**asdict(p), key: value + (1 if key == 'fin_count' else .1)}
            self.assertNotEqual(fingerprint, geometry_fingerprint(changed))

    def test_three_meaningful_variants_are_geometrically_different(self):
        ref, light, dense = (geometry_metrics(GEOMETRY_PRESETS[k]) for k in ('reference', 'light', 'dense'))
        self.assertLess(light['mass_kg'], ref['mass_kg'])
        self.assertGreater(dense['mass_kg'], ref['mass_kg'])
        self.assertLess(dense['gap_mm'], ref['gap_mm'])
        self.assertGreater(dense['channel_heated_area_m2'], ref['channel_heated_area_m2'])
        self.assertLess(dense['flow_area_m2'], ref['flow_area_m2'])

    def test_preview_has_same_fingerprint_and_actual_fin_count(self):
        for name, p in GEOMETRY_PRESETS.items():
            with self.subTest(name=name):
                root = ET.fromstring(geometry_preview_svg(p))
                self.assertEqual(root.attrib['data-geometry-fingerprint'], geometry_fingerprint(p))
                fins = [element for element in root.iter() if element.attrib.get('class') == 'fin-section']
                self.assertEqual(len(fins), p.fin_count)
                self.assertIn(f'L {p.length_mm:g} mm', geometry_preview_svg(p))


class BundledCADTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((CAD_DIR/'manifest.json').read_text(encoding='utf-8'))

    def test_compressed_files_match_manifest_and_parameter_fingerprints(self):
        self.assertEqual(set(self.manifest['presets']), set(GEOMETRY_PRESETS))
        for name, p in GEOMETRY_PRESETS.items():
            item = self.manifest['presets'][name]
            self.assertEqual(item['fingerprint'], geometry_fingerprint(p))
            self.assertEqual(item['parameters'], asdict(p))
            for kind, artifact in item['artifacts'].items():
                with self.subTest(name=name, kind=kind):
                    compressed = (CAD_DIR/artifact['file']).read_bytes()
                    data = gzip.decompress(compressed)
                    self.assertEqual(hashlib.sha256(compressed).hexdigest(), artifact['compressed_sha256'])
                    self.assertEqual(hashlib.sha256(data).hexdigest(), artifact['sha256'])
                    self.assertEqual(len(data), artifact['uncompressed_bytes'])
                    if kind == 'step':
                        self.assertTrue(data.startswith(b'ISO-10303-21;'))
                        self.assertIn(b'MANIFOLD_SOLID_BREP', data)
                    else:
                        self.assertTrue(inspect_stl(data, p)['passed'])

    def test_all_preset_evidence_contains_independent_validations(self):
        for name, p in GEOMETRY_PRESETS.items():
            status = cad_status(p)
            self.assertEqual(status['verification'], 'verified_brep')
            self.assertEqual(status['preset_id'], name)
            self.assertEqual(status['geometry_fingerprint'], geometry_fingerprint(p))
            self.assertTrue(status['step_available'])
            for stage in ('brep', 'step_roundtrip', 'stl'):
                self.assertTrue(status['validation'][stage]['passed'])
            self.assertEqual(status['validation']['brep']['solid_count'], 1)
            self.assertEqual(status['validation']['brep']['euler_characteristic'], 2)

    def test_custom_geometry_never_borrows_reference_verification(self):
        status = cad_status({'fin_count': 42})
        self.assertEqual(status['verification'], 'analytic_only')
        self.assertIsNone(status['preset_id'])
        self.assertNotIn('validation', status)

    def test_preset_exports_and_metrics_work_without_kernel(self):
        with patch('aerolab.geometry._load_kernel', side_effect=RuntimeError('No CAD kernel')):
            for p in GEOMETRY_PRESETS.values():
                self.assertTrue(generate_step(p).startswith(b'ISO-10303-21;'))
                self.assertTrue(inspect_stl(generate_stl(p), p)['passed'])
                self.assertGreater(geometry_metrics(p)['mass_kg'], 0)
            with self.assertRaisesRegex(RuntimeError, 'No CAD kernel'):
                generate_step({'fin_count': 42})

    def test_stdlib_only_process_can_export_checked_preset(self):
        command = 'from aerolab.geometry import *; assert cad_status()["verification"] == "verified_brep"; assert generate_step().startswith(b"ISO-10303-21;"); assert inspect_stl(generate_stl())["passed"]; print("stdlib-ok")'
        completed = subprocess.run([sys.executable, '-S', '-c', command], cwd=CAD_DIR.parent, capture_output=True, text=True, check=True)
        self.assertIn('stdlib-ok', completed.stdout)

    def test_artifact_tamper_cannot_claim_brep_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path/'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')
            item = self.manifest['presets']['reference']
            for artifact in item['artifacts'].values():
                (path/artifact['file']).write_bytes(gzip.compress(b'tampered'))
            with patch('aerolab.geometry.CAD_DIR', path):
                status = cad_status()
                self.assertEqual(status['verification'], 'analytic_only')
                with self.assertRaisesRegex(RuntimeError, 'checksum'):
                    generate_step()

    def test_mesh_validator_detects_open_surface(self):
        data = bytearray(generate_stl())
        count = struct.unpack_from('<I', data, 80)[0]
        struct.pack_into('<I', data, 80, count-1)
        del data[-50:]
        status = inspect_stl(bytes(data))
        self.assertFalse(status['passed'])
        self.assertFalse(status['watertight'])
        for malformed in (b'', b'not stl', bytes(data[:100])):
            with self.assertRaises(ValueError):
                inspect_stl(malformed)


@unittest.skipUnless(importlib.util.find_spec('cadquery'), 'Optional CadQuery kernel not installed')
class IndependentKernelTests(unittest.TestCase):
    def test_all_preset_step_files_reimport_as_single_valid_solid(self):
        import cadquery as cq
        with tempfile.TemporaryDirectory() as tmp:
            for name, p in GEOMETRY_PRESETS.items():
                with self.subTest(name=name):
                    path = Path(tmp)/f'{name}.step'
                    path.write_bytes(generate_step(p))
                    check = inspect_brep(cq.importers.importStep(str(path)).val(), p)
                    self.assertTrue(check['passed'], check)
                    self.assertEqual(check['faces'], 4*p.fin_count+2)
                    self.assertEqual(check['vertices'], 8*p.fin_count)
                    self.assertLess(check['relative_volume_error'], 1e-9)

    def test_custom_parameter_export_is_real_new_brep(self):
        import cadquery as cq
        p = Geometry(length_mm=302, width_mm=168, fin_height_mm=35, base_thickness_mm=7, fin_thickness_mm=1.25, fin_count=37)
        solid = build_solid(p)
        self.assertTrue(inspect_brep(solid, p)['passed'])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'custom.step'
            path.write_bytes(generate_step(p, force_regenerate=True))
            check = inspect_brep(cq.importers.importStep(str(path)).val(), p)
            self.assertTrue(check['passed'], check)
        self.assertTrue(inspect_stl(generate_stl(p, force_regenerate=True), p)['passed'])
        self.assertNotEqual(geometry_metrics(p)['volume_mm3'], geometry_metrics()['volume_mm3'])


if __name__ == '__main__':
    unittest.main()
