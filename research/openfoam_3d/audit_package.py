#!/usr/bin/env python3
"""Standard-library-only integrity and honest-status audit. No solver execution."""
import argparse,hashlib,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]

def load(p):
 return json.loads(Path(p).read_text(),parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON: '+x)))
def validate_report(r):
 assert r['initial_all_passed']==all(r['initial_gates'].values())
 initial=r['meshes'][:3];med,fine=initial[-2:];change=abs(fine['solved_pressure_gradient_Pa_m']/med['solved_pressure_gradient_Pa_m']-1)
 assert math.isclose(change,r['initial_pressure_refinement_relative_change'],rel_tol=1e-13)
 assert r['initial_gates']['medium_to_fine_pressure_gradient_change']==(change<=.01)
 assert r['physical_experimental_validation'] is None
 assert r['aircraft_applicability']=='not_established'
 assert r['conjugate_solid_fluid']=='not_solved'
 for row in r['meshes']:
  assert row['cells']==math.prod(row['grid']) and min(row['grid'])>1
  assert row['mesh_ok'] and row['three_dimensions']
  assert row['temperature_min_K']>=299.999 and row['temperature_max_K']<=310.001
  flux=sum(v['total_outward_W'] for v in row['boundary_heat_fluxes'].values())
  assert math.isclose(flux,row['energy_imbalance_W'],abs_tol=1e-15)
  assert math.isclose(abs(flux)/.28944,row['relative_energy_imbalance'],abs_tol=1e-14)
  assert row['flow_runtime']['solver']=='simpleFoam' and row['thermal_runtime']['solver']=='scalarTransportFoam'
 if r['additional_refinement']:
  prev,last=r['meshes'][-2:];change=abs(last['solved_pressure_gradient_Pa_m']/prev['solved_pressure_gradient_Pa_m']-1);extra=r['additional_refinement']
  assert math.isclose(change,extra['pressure_relative_change_from_previous_fine'],rel_tol=1e-13)
  assert math.isclose(change*16/3,extra['second_order_equivalent_doubling_relative_change'],rel_tol=1e-13)
 return True

def audit(full_source=False):
 manifest=load(HERE/'evidence/manifest.json')
 for item in manifest['files']:
  path=(REPO/item['path']).resolve();assert path.is_relative_to(HERE)
  assert path.stat().st_size==item['bytes']
  assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256'],str(path)
  assert item['bytes']<(250000 if path.suffix=='.png' else 100000)
 r=load(HERE/'evidence/report.json');validate_report(r)
 source_count=0
 if full_source:
  sources=load(HERE/'evidence/source_artifacts.json');root=(REPO/sources['source_root_relative_to_repository']).resolve();assert root.is_relative_to(REPO/'output')
  for item in sources['files']:
   p=(root/item['path']).resolve();assert p.is_relative_to(root)
   assert p.stat().st_size==item['bytes']
   assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'],str(p)
   source_count+=1
 print(json.dumps({'files_verified':len(manifest['files']),'initial_all_passed':r['initial_all_passed'],'original_failed_gates':[k for k,v in r['initial_gates'].items() if not v],'additional_grid_present':r['additional_refinement'] is not None,'full_source_artifacts_verified':source_count},indent=2))
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--full-source',action='store_true');audit(parser.parse_args().full_source)
