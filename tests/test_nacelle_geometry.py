"""Parameter, topology, flow-area, mesh and stored multi-solid STEP invariants."""
import gzip
import hashlib
import importlib.util
import json
import math
import copy
import io
import random
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch
from aerolab.nacelle_geometry import (CAD_DIR,NacelleParams,assembly_geometry,generate_nacelle_step,
    mesh_audit,nacelle_catalog,nacelle_fingerprint,nacelle_metrics,parse_nacelle,
    _read_step_artifact,STEP_CHUNK_MAX_BYTES,nacelle_cad_status)

class NacelleGeometryTests(unittest.TestCase):
    def test_baseline_anchors_and_inference(self):
        p=NacelleParams();self.assertEqual(p.motor_diameter_mm,355.6);self.assertEqual(p.prop_diameter_mm,1524)
        self.assertEqual(p.hv_fin_count,24);self.assertNotEqual(p.hv_fin_count,43)
        self.assertFalse(nacelle_catalog()['provenance']['original_NASA_CAD'])
        self.assertIn('historical',nacelle_catalog()['provenance']['assumptions'][1])

    def test_invalid_params(self):
        for value in ({'hv_fin_count':24.2},{'hv_fin_count':True},{'hv_fin_count':10**1000},{'cmc_tilt_deg':float('nan')},{'motor_gap_mm':0},{'unknown':3},{'cmc_width_mm':300},[],3):
            with self.subTest(value=value),self.assertRaises(ValueError):parse_nacelle(value)

    def test_every_parameter_changes_fingerprint(self):
        p=NacelleParams();h=nacelle_fingerprint(p)
        for item in nacelle_catalog()['parameters']:
            q=p.to_dict();q[item['key']]+=1 if item['key']=='hv_fin_count' else .1
            self.assertNotEqual(h,nacelle_fingerprint(q))
        self.assertEqual(h,nacelle_fingerprint(p.to_dict()))

    def test_construction_source_identity_invalidates_cached_artifacts(self):
        original=nacelle_fingerprint()
        with patch('aerolab.nacelle_geometry.GEOMETRY_SOURCE_SHA256','changed-construction'):
            self.assertNotEqual(original,nacelle_fingerprint())
            from aerolab.nacelle_geometry import _artifact
            self.assertIsNone(_artifact(None))

    def test_failed_or_incomplete_artifact_is_not_served(self):
        from aerolab.nacelle_geometry import _artifact, GEOMETRY_SOURCE_SHA256
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            for validation in ({'passed':False,'intersection_audit_complete':True},{'passed':True,'intersection_audit_complete':False}):
                manifest={'fingerprint':nacelle_fingerprint(),'geometry_module_sha256':GEOMETRY_SOURCE_SHA256,'validation':validation,'roundtrip':{'passed':True},'mesh_validation':{'passed':True}}
                (directory/'manifest.json').write_text(json.dumps(manifest))
                with patch('aerolab.nacelle_geometry.CAD_DIR',directory):self.assertIsNone(_artifact(None))

    def test_tapered_bypass_lengths_and_forward_fit_guards(self):
        m=nacelle_metrics();c=m['channels']['motor_bypass']
        self.assertEqual(len(c['segments']),6)
        self.assertAlmostEqual(c['length_m'],.221)
        self.assertEqual(c['area_m2'],c['inlet']['area_m2'])
        self.assertAlmostEqual(c['heated_area_m2'],c['heat_exchange']['heated_area_m2'])
        for params in ({'motor_bypass_gap_mm':15},{'motor_bypass_gap_mm':42},{'main_inlet_height_mm':12},{'main_inlet_height_mm':40}):
            self.assertTrue(mesh_audit(params)['passed'])
        with self.assertRaisesRegex(ValueError,'local forward cowling'):
            parse_nacelle({'motor_diameter_mm':390,'motor_bypass_gap_mm':42})

    def test_component_ids_stable_and_mesh_closed(self):
        base=assembly_geometry();other=assembly_geometry({'nacelle_length_mm':1500})
        self.assertEqual([c['id'] for c in base['components']],[c['id'] for c in other['components']])
        self.assertTrue(mesh_audit()['passed'])
        ids={c['id']:c for c in base['components']}
        for key in ('cowling_upper','cowling_lower','cowling_tail','local_wing','motor_rotor','motor_winding','motor_magnet','cmc_left_hv','cmc_right_hv','lv_inlet_left','lv_inlet_right','motor_upper_exhaust'):
            self.assertIn(key,ids)
        self.assertEqual(ids['local_wing']['role'],'installation_context')
        self.assertLess(ids['motor_winding']['bounds_mm']['max'][1],ids['motor_magnet']['bounds_mm']['max'][1])
        self.assertGreater(len(ids['cowling_upper']['vertices']),100)
        for c in base['components']:
            self.assertEqual(len(c['vertices'])%3,0);self.assertEqual(len(c['triangles'])%3,0)
            self.assertLess(max(c['triangles']),len(c['vertices'])//3)
            self.assertGreater(c['volume_mm3'],0)

    def test_mass_excludes_host_wing_and_no_air_solids(self):
        a=assembly_geometry();m=a['metrics']
        self.assertAlmostEqual(m['mass_kg'],sum(c['mass_kg'] for c in a['components'] if c['role']=='hardware'))
        self.assertGreater(m['installation_context_volume_m3'],0)
        self.assertTrue(all(c['role']!='air' for c in a['components']))
        self.assertIn('no volumetric CFD',m['flow_geometry_role'])

    def test_channels_are_consistent_and_slots_parallel(self):
        p=NacelleParams();m=nacelle_metrics()
        for name,c in m['channels'].items():
            self.assertGreater(c['area_m2'],0);self.assertGreater(c['wetted_perimeter_m'],0)
            self.assertAlmostEqual(c['hydraulic_diameter_m'],4*c['area_m2']/c['wetted_perimeter_m'])
        self.assertIn('motor_slots',m['channels'])
        gap=m['channels']['motor_internal'];self.assertAlmostEqual(gap['heated_area_m2'],sum(gap['heated_surfaces_m2'].values()))
        slot=m['channels']['motor_slots'];self.assertEqual(slot['slot_count'],24)
        self.assertGreater(slot['heated_area_m2'],gap['heated_surfaces_m2']['motor_winding'])
        hv=m['channels']['cmc_hv_left'];self.assertAlmostEqual(hv['heated_area_m2'],hv['fin_area_m2']+hv['base_area_m2'])
        lv=m['channels']['lv_fresh_left'];self.assertNotEqual(lv['hydraulic_diameter_m'],lv['heat_exchange']['hydraulic_diameter_m']);self.assertEqual(len(lv['segments']),4)
        self.assertAlmostEqual(m['components']['cmc_left_cpu']['conduction_area_m2'],54*46*1e-6)

    def test_half_moon_inlets_match_actual_section_polygons(self):
        from aerolab.nacelle_geometry import _d_section,_lv_duct_sections,_section_area_perimeter
        for height in (15,30,50):
            p=NacelleParams(upper_inlet_height_mm=height);c=nacelle_metrics(p)['channels']['lv_fresh_left']
            sections=_lv_duct_sections(p,0);points=_d_section(sections[0])
            self.assertEqual(c['section_profile'],'half_ellipse_with_flat_sill')
            self.assertAlmostEqual(points[0][2],points[-1][2])
            self.assertAlmostEqual(max(q[2] for q in points)-points[0][2],height)
            area,perimeter=_section_area_perimeter(points)
            self.assertAlmostEqual(c['area_m2'],area*1e-6)
            self.assertAlmostEqual(c['wetted_perimeter_m'],perimeter*1e-3)
            self.assertAlmostEqual(area/(math.pi*37*height/2),math.sin(math.pi/24)/(math.pi/24))
            self.assertAlmostEqual(c['length_m'],sum(seg['length_m'] for seg in c['segments']))
            for i,(a,b) in enumerate(zip(sections,sections[1:])):
                midpoint=[[sum(v)/2 for v in zip(pa,pb)] for pa,pb in zip(_d_section(a),_d_section(b))]
                area,perimeter=_section_area_perimeter(midpoint)
                self.assertAlmostEqual(c['segments'][i]['area_m2'],area*1e-6)
                self.assertAlmostEqual(c['segments'][i]['wetted_perimeter_m'],perimeter*1e-3)

    def test_hollow_supports_have_real_empty_cores(self):
        from aerolab.nacelle_geometry import _hollow_rod,_mesh_part
        parts=_hollow_rod((0,0,0),(100,0,0),6)
        volume=sum(_mesh_part(part)[2] for part in parts)
        expected=24/2*math.sin(2*math.pi/24)*(6**2-4.8**2)*100
        self.assertAlmostEqual(volume,expected,places=6)
        for part in parts:
            for ring in part['rings']:
                self.assertGreaterEqual(min(math.hypot(v[1],v[2]) for v in ring),4.8-1e-8)
        self.assertEqual(nacelle_metrics()['resolution']['support_tube_wall_mm'],1.2)

    def test_cowling_refinement_has_shared_seams_and_bounded_sampling(self):
        from aerolab.nacelle_geometry import _cowling_stations,_cowling_station,_construction
        for length in (1300,1470,1650):
            p=NacelleParams(nacelle_length_mm=length);stations=_cowling_stations(p,[-25,1445])
            self.assertGreater(len(stations),30)
            for a,b in zip(stations,stations[1:]):
                self.assertLessEqual(b[0]-a[0],55+1e-8)
                for f in (.25,.5,.75):
                    q=_cowling_station(p,a[0]+f*(b[0]-a[0]))
                    for j in (1,2,3):self.assertLessEqual(abs(q[j]-(a[j]+f*(b[j]-a[j]))),.15000001)
        p=NacelleParams();components={c['id']:c for c in _construction(p)}
        def seam_points(component):
            return {tuple(round(v,6) for v in point) for part in component['parts'] for ring in part['rings'] for point in ring if abs(point[2]-_cowling_station(p,point[0])[3])<1e-7 and point[1]>0}
        self.assertEqual(seam_points(components['cowling_upper']),seam_points(components['cowling_lower']))

    def test_refined_aperture_area_tracks_ruled_cowling(self):
        from aerolab.nacelle_geometry import _construction
        for params in ({},{'motor_exhaust_area_mm2':4500},{'motor_exhaust_area_mm2':16000},{'outlet_area_mm2':12000},{'outlet_area_mm2':36000}):
            p=parse_nacelle(params);components={c['id']:c for c in _construction(p)}
            # Lower opening edge is the final outer vertex of the left panel.
            rings=components['cowling_lower']['parts'][1]['rings']
            edge=[ring[32] for ring in rings]
            projected_area=sum((b[0]-a[0])*(abs(a[1])+abs(b[1])) for a,b in zip(edge,edge[1:]))
            self.assertAlmostEqual(projected_area,p.outlet_area_mm2,places=6)
            scale=p.nacelle_length_mm/1470;start=258*scale-p.motor_exhaust_area_mm2/150
            projected_area=0.
            for part in components['cowling_upper']['parts']:
                rings=part['rings']
                if rings[0][0][0]<start-1e-8 or rings[-1][0][0]>258*scale+1e-8:continue
                # Positive-Y aperture edge at the end of the first upper arc.
                if rings[0][0][1]<0 or rings[0][32][1]<0:continue
                edge=[ring[32] for ring in rings]
                projected_area+=sum((b[0]-a[0])*(a[1]+b[1]) for a,b in zip(edge,edge[1:]))
            self.assertAlmostEqual(projected_area,p.motor_exhaust_area_mm2,places=6)

    def test_knobs_change_own_physical_sections(self):
        a=nacelle_metrics();b=nacelle_metrics({'upper_inlet_height_mm':40});c=nacelle_metrics({'backplate_gap_mm':24})
        self.assertGreater(b['channels']['lv_fresh_left']['area_m2'],a['channels']['lv_fresh_left']['area_m2'])
        self.assertEqual(b['channels']['lv_fresh_left']['heat_exchange'],a['channels']['lv_fresh_left']['heat_exchange'])
        self.assertGreater(c['channels']['lv_fresh_left']['heat_exchange']['area_m2'],a['channels']['lv_fresh_left']['heat_exchange']['area_m2'])
        d=nacelle_metrics({'hv_fin_count':30});self.assertGreater(d['channels']['cmc_hv_left']['heated_area_m2'],a['channels']['cmc_hv_left']['heated_area_m2'])

    def test_returns_do_not_mutate_cached_geometry(self):
        a=assembly_geometry();a['components'][0]['vertices'][0]=99999;a['metrics']['channels']['main_inlet']['area_m2']=999
        b=assembly_geometry();self.assertNotEqual(b['components'][0]['vertices'][0],99999);self.assertLess(b['metrics']['channels']['main_inlet']['area_m2'],1)

    def test_bundled_step_manifest_matches_parameters(self):
        manifest_path=CAD_DIR/'manifest.json'
        if not manifest_path.exists():self.skipTest('Generate baseline STEP with scripts/generate_nacelle.py')
        m=json.loads(manifest_path.read_text());self.assertEqual(m['fingerprint'],nacelle_fingerprint())
        artifact=m['artifacts']['step'];self.assertEqual(artifact['storage'],'ordered_chunks_v1')
        compressed=b''.join((CAD_DIR / part['file']).read_bytes() for part in artifact['chunks'])
        data=_read_step_artifact(CAD_DIR,artifact)
        self.assertTrue(all(0<part['bytes']<=STEP_CHUNK_MAX_BYTES for part in artifact['chunks']))
        self.assertEqual([part['index'] for part in artifact['chunks']],list(range(len(artifact['chunks']))))
        self.assertEqual(hashlib.sha256(data).hexdigest(),artifact['sha256'])
        self.assertEqual(hashlib.sha256(compressed).hexdigest(),artifact['compressed_sha256'])
        self.assertIn(b'ISO-10303-21',data);self.assertIn(b'cmc_left_hv',data);self.assertIn(b'motor_winding',data)
        self.assertTrue(m['validation']['passed']);self.assertTrue(m['roundtrip']['passed'])
        self.assertEqual(generate_nacelle_step(),data)

    def test_checked_in_step_download_needs_no_cad_kernel(self):
        artifact=json.loads((CAD_DIR/'manifest.json').read_text())['artifacts']['step']
        expected=_read_step_artifact(CAD_DIR,artifact)
        with patch('aerolab.nacelle_geometry._load_kernel',side_effect=AssertionError('CadQuery must not be loaded')):
            with patch('aerolab.nacelle_geometry.importlib.util.find_spec',return_value=None):
                self.assertEqual(generate_nacelle_step(),expected)
                status=nacelle_cad_status()
                self.assertFalse(status['kernel_available'])
                self.assertTrue(status['stored_step_available'])
                self.assertEqual(status['verification'],'verified_baseline_BRep')


class NacelleGenerationSafetyTests(unittest.TestCase):
    def test_failed_candidate_does_not_replace_verified_cache(self):
        from scripts import generate_nacelle
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);manifest=directory/'manifest.json';manifest.write_text('previous verified cache')
            with patch('sys.argv',['generate_nacelle','--out',tmp]),patch.object(generate_nacelle,'_load_kernel',return_value=Mock()),patch.object(generate_nacelle,'build_nacelle',return_value=(Mock(),{})),patch.object(generate_nacelle,'inspect_nacelle_brep',return_value={'passed':False,'unexpected_intersection_count':1}):
                with self.assertRaisesRegex(SystemExit,'Geometry audit failed'):generate_nacelle.main()
            self.assertEqual(manifest.read_text(),'previous verified cache')
            self.assertTrue((directory/'rejected-validation.json').exists())


class ChunkedStepIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name)
        self.payload=b'ISO-10303-21;'+random.Random(17).randbytes(510000)
        self.packed=gzip.compress(self.payload,mtime=0);parts=[]
        for index,start in enumerate(range(0,len(self.packed),STEP_CHUNK_MAX_BYTES)):
            data=self.packed[start:start+STEP_CHUNK_MAX_BYTES];name=f'test.step.gz.part-{index:04d}'
            (self.root/name).write_bytes(data)
            parts.append({'index':index,'file':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
        self.artifact={'storage':'ordered_chunks_v1','compression':'gzip','chunk_max_bytes':STEP_CHUNK_MAX_BYTES,'chunks':parts,'bytes':len(self.payload),'compressed_bytes':len(self.packed),'sha256':hashlib.sha256(self.payload).hexdigest(),'compressed_sha256':hashlib.sha256(self.packed).hexdigest()}

    def test_exact_reassembly_and_bounded_parts(self):
        self.assertEqual(_read_step_artifact(self.root,self.artifact),self.payload)
        self.assertGreater(len(self.artifact['chunks']),1)
        self.assertTrue(all(c['bytes']<=250000 for c in self.artifact['chunks']))

    def test_missing_chunk_rejected(self):
        (self.root/self.artifact['chunks'][1]['file']).unlink()
        with self.assertRaisesRegex(RuntimeError,'unavailable'):_read_step_artifact(self.root,self.artifact)

    def test_corrupted_chunk_rejected(self):
        path=self.root/self.artifact['chunks'][1]['file'];data=bytearray(path.read_bytes());data[51]^=1;path.write_bytes(data)
        with self.assertRaisesRegex(RuntimeError,'chunk checksum'):_read_step_artifact(self.root,self.artifact)

    def test_concurrent_chunk_growth_is_read_with_a_hard_bound(self):
        part=self.artifact['chunks'][0];data=(self.root/part['file']).read_bytes();reads=[]
        class GrowingFile(io.BytesIO):
            def read(self, size=-1):
                reads.append(size)
                return super().read(size)
        original_open=Path.open
        def growing_open(path,*args,**kwargs):
            if path.name==part['file']:return GrowingFile(data+b'concurrent growth')
            return original_open(path,*args,**kwargs)
        with patch.object(Path,'open',new=growing_open):
            with self.assertRaises(RuntimeError):_read_step_artifact(self.root,self.artifact)
        self.assertEqual(reads,[part['bytes']+1])

    def test_reordered_chunks_rejected(self):
        artifact=copy.deepcopy(self.artifact);artifact['chunks'][0],artifact['chunks'][1]=artifact['chunks'][1],artifact['chunks'][0]
        with self.assertRaisesRegex(RuntimeError,'out of order'):_read_step_artifact(self.root,artifact)
        for index,part in enumerate(artifact['chunks']):part['index']=index
        with self.assertRaisesRegex(RuntimeError,'combined compressed checksum'):_read_step_artifact(self.root,artifact)

    def test_truncated_chunk_rejected(self):
        path=self.root/self.artifact['chunks'][-1]['file'];path.write_bytes(path.read_bytes()[:-1])
        with self.assertRaisesRegex(RuntimeError,'size mismatch'):_read_step_artifact(self.root,self.artifact)

    def test_duplicate_and_escaping_filenames_rejected(self):
        for name in ('../secret','/tmp/secret','folder/part','folder\\part',self.artifact['chunks'][0]['file']):
            artifact=copy.deepcopy(self.artifact);artifact['chunks'][1]['file']=name
            with self.subTest(name=name),self.assertRaises(RuntimeError):_read_step_artifact(self.root,artifact)

    def test_chunk_metadata_and_expansion_bounds_rejected(self):
        changes=[('compressed_bytes',0),('bytes',129*1024*1024),('bytes',len(self.payload)-1),('chunk_max_bytes',250001)]
        for key,value in changes:
            artifact=copy.deepcopy(self.artifact);artifact[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(RuntimeError):_read_step_artifact(self.root,artifact)
        for key,value in [('bytes',250001),('bytes',True),('index',True)]:
            artifact=copy.deepcopy(self.artifact);artifact['chunks'][0][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(RuntimeError):_read_step_artifact(self.root,artifact)

    def test_combined_and_uncompressed_hashes_rejected(self):
        for key in ('compressed_sha256','sha256'):
            artifact=copy.deepcopy(self.artifact);artifact[key]='0'*64
            with self.subTest(key=key),self.assertRaises(RuntimeError):_read_step_artifact(self.root,artifact)

    def test_legacy_single_file_fallback_is_not_accepted(self):
        artifact=copy.deepcopy(self.artifact);artifact.pop('chunks');artifact['file']='old.step.gz'
        (self.root/'old.step.gz').write_bytes(self.packed)
        with self.assertRaises(RuntimeError):_read_step_artifact(self.root,artifact)

if __name__=='__main__':unittest.main()
