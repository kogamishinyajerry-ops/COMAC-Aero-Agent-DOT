#!/usr/bin/env python3
"""Standard-library, offline integrity/arithmetic audit of a saved fin study.

No scientific packages, model execution, PDF, network, or application mutation.
The application must pin the delivered manifest hash, not trust an arbitrary
replacement manifest. Integrity/equivalence is not physical validation.
"""
from __future__ import annotations
import argparse,hashlib,json,math,pathlib
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[1]
RP='research/plate_fin/';EP='examples/plate_fin_experiment/';MP=EP+'package_manifest.json'
def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def _constant(value):raise ValueError('Nonfinite JSON: '+value)
def strict_json(raw):
 if len(raw)>=100000:raise ValueError('JSON exceeds bounded contract')
 obj=json.loads(raw,parse_constant=_constant)
 def walk(v):
  if isinstance(v,float) and not math.isfinite(v):raise ValueError('Nonfinite numeric JSON')
  if isinstance(v,dict):
   for x in v.values():walk(x)
  elif isinstance(v,list):
   for x in v:walk(x)
 walk(obj);return obj

def same(a,b):
 if isinstance(a,bool) or isinstance(b,bool) or not isinstance(a,(int,float)) or not isinstance(b,(int,float)) or not math.isfinite(a) or not math.isfinite(b):raise ValueError('Finite numeric arithmetic required')
 if not math.isclose(a,b,rel_tol=1e-11,abs_tol=1e-12):raise ValueError(f'Displayed arithmetic mismatch: {a} versus {b}')
def require(test,msg):
 if not test:raise ValueError(msg)

def bounded_read(path,limit,expected_bytes=None):
 size=path.stat().st_size
 require(size<limit and (expected_bytes is None or size==expected_bytes),'Artifact fails size preflight')
 with path.open('rb') as stream:raw=stream.read(limit)
 require(len(raw)<limit and len(raw)==size,'Artifact changed size or exceeded bounded read')
 return raw

def audit(root=ROOT,expected_manifest_sha256=None,return_verified_records=False):
 root=pathlib.Path(root).resolve();manifest_path=(root/MP).resolve()
 require(manifest_path.is_relative_to(root) and manifest_path.is_file(),'Invalid manifest location')
 raw=bounded_read(manifest_path,100000);manifest_sha=sha_bytes(raw)
 if expected_manifest_sha256:require(manifest_sha==expected_manifest_sha256,'Manifest identity differs from pinned hash')
 m=strict_json(raw);records={};sizes={}
 require(m['physical_validation_pass'] is None and m['aircraft_transfer_authorized'] is False and m['application_dependencies_added'] is False,'Invalid package scope')
 require(m['source_pdf_required'] is False and m['source_pdf_redistributed'] is False,'PDF must remain optional and excluded')
 for record in m['files']:
  name=record['proposed_repository_path'];p=pathlib.PurePosixPath(name)
  require(not p.is_absolute() and '..' not in p.parts and name not in records and name.startswith((RP,EP)),'Invalid or duplicate manifest path')
  actual=(root/name).resolve();require(actual.is_relative_to(root) and actual.is_file(),'Missing or escaping artifact')
  require(not any(x in {'__pycache__','.cache','.mplconfig'} for x in p.parts),'Cache must not be published')
  require(actual.suffix.lower() not in {'.pdf','.npz','.npy','.log','.pyc'},'Excluded publication artifact')
  require(isinstance(record['bytes'],int) and not isinstance(record['bytes'],bool) and record['bytes']>=0,'Invalid declared artifact size')
  b=bounded_read(actual,100000 if actual.suffix=='.json' else 250000,record['bytes'])
  require(sha_bytes(b)==record['sha256'],'Artifact hash mismatch: '+name)
  if actual.suffix=='.json':strict_json(b)
  records[name]=b;sizes[name]=len(b)
 require(len(records)==m['files_count'] and sum(sizes.values())==m['total_listed_bytes'],'Inventory count/bytes mismatch')
 for name,want in m['original_freeze_anchors'].items():require(sha_bytes(records[name])==want,'Original anchor changed')
 def data(name):return strict_json(records[name])
 c=data(EP+'experimental_comparison.json');f=data(EP+'frozen_numerics.json');v=data(EP+'verification.json');a=data(EP+'applicability_audit.json');r=data(EP+'plate_fin_report.json');source=data(RP+'inputs/figure8_markers.json');prov=data(RP+'inputs/source_provenance.json');index=data(EP+'replay_index.json');replay=data(EP+'packaging_replay.json');counter=data(EP+'side_channel_counterexample.json');display=data(EP+'display_fields.json')
 ar=RP+'original_freeze/'
 for name,original in [('experimental_comparison.json','comparison.json'),('verification.json','verification.json'),('frozen_numerics.json','frozen_numerics.json'),('independent_limits.json','independent_limits.json'),('applicability_audit.json','applicability_audit.json')]:require(records[EP+name]==records[ar+original],'Packaged saved evidence altered')
 require(records[RP+'conjugate_fin.py']==records[ar+'conjugate_fin.py'],'Physical solver bytes altered')
 require(records[RP+'precomparison_plan.json']==records[ar+'precomparison_plan.json'],'Precomparison plan altered')
 code_sha=sha_bytes(records[RP+'conjugate_fin.py']);plan_sha=sha_bytes(records[RP+'precomparison_plan.json'])
 require(code_sha==f['code_sha256']==c['model_code_sha256']==replay['packaged_solver_sha256']==replay['original_solver_sha256'],'Solver identity chain differs')
 require(plan_sha==f['plan_sha256']==c['plan_sha256'],'Input plan identity differs')
 require(f['verification_sha256']==sha_bytes(records[EP+'verification.json']),'Frozen verification hash differs')
 require(c['freeze_sha256']==sha_bytes(records[EP+'frozen_numerics.json']),'Comparison/freeze chain differs')
 require(v['reused_mathematical_evidence_sha256']==sha_bytes(records[ar+v['reused_mathematical_evidence_file']]),'Rejected predecessor chain differs')
 rejected=data(ar+'verification_selected_mesh_rejected.json');require([k for k,x in rejected['gates'].items() if x is not True]==['velocity_selected_mesh_exact_mean'],'Original grid rejection lost')
 require(v['status']=='verified_precomparison' and len(v['gates'])==17 and all(x is True for x in v['gates'].values()),'Original mathematical gates not accepted')
 require(f['selected']=={'gap_cells':48,'height_cells':144,'axial_steps':1600,'method':'backward_euler','half_array_symmetry':True},'Frozen numerical choices changed')
 review=data(ar+'review/final_review_gate.json');require(review['independent_review_status']=='accepted_for_conditional_predeclared_comparison' and all(x is True for x in review['checks'].values()),'Independent review release invalid')
 for key,path in [('frozen_numerics_sha256','frozen_numerics.json'),('verification_sha256','verification.json'),('independent_limits_sha256','independent_limits.json'),('review_results_sha256','review/independent_review.json'),('review_script_sha256','review/independent_review.py')]:require(review[key]==sha_bytes(records[ar+path]),'Independent review hash chain differs')
 original_source=data(ar+'fonseca2024_vector_readout.json');require(source['count']==12 and len(source['rows'])==12 and len(r['rows'])==12 and len(c['results'])==24,'Marker count changed')
 require(len({x['marker_id'] for x in source['rows']})==12 and source['source_claimed_run_count']==13,'Missing/duplicate marker policy changed')
 require(source['original_vector_readout_sha256']==sha_bytes(records[ar+'fonseca2024_vector_readout.json'])==c['source_readout_sha256'],'Original source readout differs')
 require(source['original_extractor_sha256']==sha_bytes(records[ar+'read_fonseca_vectors.py'])==prov['original_extractor_sha256'],'Extractor provenance differs')
 require(source['source_pdf_sha256']==prov['source_pdf_sha256']==c['source_pdf_sha256'],'Source-byte identity differs')
 require(prov['offline_marker_transcription_sha256']==sha_bytes(records[RP+'inputs/figure8_markers.json']),'Marker transcription identity differs')
 require(source['excluded_targets']==['fitted curve paths','Figure7 fin-efficiency-derived h/Nu'],'Nonindependent target exclusion changed')
 counts={k:0 for k in r['scope_counts']};Dh=2*c['geometry']['interior_gap_m']*c['geometry']['height_m']/(c['geometry']['interior_gap_m']+c['geometry']['height_m']);nu=c['nominal_properties']['nu_m2_s']
 require(r['physical_validation_pass'] is None and r['aircraft_transfer_authorized'] is False and r['live_computation'] is False and r['model_forms_are_confidence_bounds'] is False,'Report overstates physical scope')
 require(r['provenance']['projection_script_sha256']==sha_bytes(records[RP+'build_display_records.py']) and index['report_sha256']==sha_bytes(records[EP+'plate_fin_report.json']),'Report projection identity differs')
 for i,(marker,row,scope,wrong) in enumerate(zip(source['rows'],r['rows'],a['rows'],counter['rows'])):
  orig=original_source['figure8_Rth'][i]
  require(marker['marker_index']==i and marker['drawing_index']==orig['drawing_index'] and row['id']==marker['marker_id'],'Marker identity/order differs')
  require(marker['center_pdf_points']==orig['center_pdf_points'],'PDF marker centres changed')
  V=marker['V_channel_inferred_m_s'];R=marker['Rth_K_W'];graph=marker['conservative_graphical_half_symbol_envelope'];same(V,orig['V_channel_inferred_m_s']);same(R,orig['Rth_K_W']);require(graph==orig['conservative_graphical_half_symbol_envelope'],'Graphical allowance changed')
  same(row['observed']['V_channel_inferred_m_s'],V);same(row['observed']['Rth_K_W'],R);same(row['observed']['G_W_K'],1/R)
  require(row['graphical_readout_allowance_separate']==graph and row['author_uncertainty_separate']['Rth_relative']==.012,'Uncertainty components lost')
  same(row['author_uncertainty_separate']['Rth_absolute_K_W'],.012*R)
  Re=V*Dh/nu;delta_graph=graph['V_m_s']*Dh/nu;upper=Re*1.052+delta_graph
  label='robustly_in_declared_laminar_scope' if upper<=2300 else 'nominally_laminar_boundary_uncertain' if Re<=2300 else 'nominally_outside_laminar_scope'
  require(scope['scope']==label==row['scope']['scope']==wrong['scope'],'Regime label differs');counts[label]+=1;same(scope['Re_nominal'],Re);same(scope['conservative_joint_corner_Re_interval'][1],upper)
  for profile in ['fd','plug']:
   saved=next(x for x in c['results'] if x['marker_index']==i and x['profile']==profile);pred=row['predictions'][profile]
   for key in ['G_W_K','Rth_K_W']:same(pred[key],saved['prediction'][key])
   same(pred['Rth_K_W'],1/pred['G_W_K']);same(pred['relative_Rth_discrepancy'],pred['Rth_K_W']/R-1);same(pred['relative_G_discrepancy'],pred['G_W_K']*R-1)
   for key in ['side_channels_G_fraction','naive_17_central_channels_relative_G_bias']:same(pred[key],saved[key])
  primary=row['predictions']['fd'];same(wrong['incorrect_17_interior_G_W_K'],primary['G_W_K']*(1+primary['naive_17_central_channels_relative_G_bias']));same(wrong['incorrect_17_interior_Rth_K_W'],1/wrong['incorrect_17_interior_G_W_K']);same(wrong['incorrect_relative_Rth_discrepancy'],wrong['incorrect_17_interior_Rth_K_W']/R-1)
 require(counts=={'robustly_in_declared_laminar_scope':3,'nominally_laminar_boundary_uncertain':1,'nominally_outside_laminar_scope':8}==r['scope_counts'],'Scope counts changed')
 require(counter['not_an_accepted_model'] is True and counter['physical_ownership']['interior_channels']==15 and counter['physical_ownership']['side_channels']==2 and counter['physical_ownership']['side_floor']=='adiabatic duct surface outside41.5mm base','Side-channel ownership/counterexample lost')
 require(replay['all_passed'] is True and all(x is True for x in replay['checks'].values()) and len(replay['cases'])==40,'Packaging numerical replay not accepted')
 require(replay['equations_grids_materials_properties_and_scenarios_changed'] is False and replay['physical_validation_pass'] is None and replay['aircraft_transfer_authorized'] is False,'Replay scope changed')
 require(replay['original_comparison_sha256']==sha_bytes(records[ar+'comparison.json']) and replay['original_precomparison_freeze_sha256']==sha_bytes(records[ar+'frozen_numerics.json']) and replay['replay_script_sha256']==sha_bytes(records[RP+'replay_numerics.py']),'Replay provenance differs')
 def rounded(x):
  if isinstance(x,float):return round(x,7)
  if isinstance(x,list):return [rounded(v) for v in x]
  if isinstance(x,dict):return {k:rounded(v) for k,v in x.items()}
  return x
 require(display['rounding_decimal_places']==7 and len(display['cases'])==4,'Display field contract changed')
 domains={d['channel_index_from_side']:d for d in display['channel_domains']}
 require(set(domains)=={0,1,8} and domains[0]['role']=='side_clearance_full_channel' and domains[1]['role']=='interior_full_channel' and domains[8]['role']=='central_interior_half_channel','Display channel roles missing')
 for i,width,fraction in [(0,c['geometry']['side_gap_m'],1.),(1,c['geometry']['interior_gap_m'],1.),(8,c['geometry']['interior_gap_m'],.5)]:
  same(domains[i]['physical_full_channel_width_m'],width);same(domains[i]['modeled_width_fraction'],fraction);same(domains[i]['modeled_width_m'],width*fraction)
 require(domains[8]['right_boundary']=='mirror symmetry plane; not a duct wall','Central channel symmetry lost')
 for item in display['cases']:
  name=item['original_sample_file'];require(name in records and item['original_sample_sha256']==sha_bytes(records[name]),'Field sample source differs');require(item['samples']==rounded(data(name)['fields']),'Display field rounding differs')
 checks={'manifest_inventory_hashes_and_caps':True,'original_freeze_and_rejected_grid_preserved':True,'original_independent_review_hash_chain':True,'solver_and_physical_plan_unchanged':True,'source_figure8_numeric_transcription':True,'all12_points_and_two_model_forms_retained':True,'robust_boundary_outside_labels_3_1_8':True,'author_and_graphical_allowances_separate':True,'source_to_display_arithmetic':True,'side_channel_counterexample_ownership':True,'small_field_samples_match_declared_rounding':True,'display_channel_roles_and_half_width_explicit':True,'size_preflight_and_bounded_reads':True,'all40_post_comparison_replay_cases_equivalent':True,'stdlib_only_no_model_execution':True,'offline_no_source_pdf_required':True,'no_validation_or_aircraft_transfer_claim':True}
 summary={'status':'passed','all_passed':True,'study_id':'plate_fin_2024','checks':checks,'listed_file_count':len(records),'listed_bytes':sum(sizes.values()),'max_json_bytes':max(len(b) for n,b in records.items() if n.endswith('.json')),'max_binary_bytes':max(len(b) for n,b in records.items() if n.endswith('.png')),'original_comparison_sha256':sha_bytes(records[ar+'comparison.json']),'numeric_payload_equivalence_maximum_absolute_difference':replay['maximum_absolute_payload_difference'],'physical_validation_pass':None,'aircraft_transfer_authorized':False}
 return (summary,records,manifest_sha) if return_verified_records else summary

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=pathlib.Path,default=ROOT);ap.add_argument('--expected-manifest-sha256');ap.add_argument('--output',type=pathlib.Path);args=ap.parse_args();out=audit(args.root,args.expected_manifest_sha256);text=json.dumps(out,indent=2)+'\n';args.output.write_text(text) if args.output else print(text)
if __name__=='__main__':main()
