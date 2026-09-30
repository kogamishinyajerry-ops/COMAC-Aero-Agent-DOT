#!/usr/bin/env python3
"""Prespecified paired-effect refinement, no experimental target reads."""
import gc,json,time
from axial_fin import AxialModel,HERE,sha,ResourceLimit

def main():
 verification=json.loads((HERE/'mathematical_verification.json').read_text());assert all(verification['gates'].values());assert verification['axial_code_sha256']==sha(HERE/'axial_fin.py')
 cases=[(12,36,nz,speed) for nz in [60,120,240] for speed in [4.,10.]]+[(nx,ny,240,speed) for nx,ny in [(24,72),(36,108),(48,144)] for speed in [4.,10.]]+[(48,144,480,speed) for speed in [4.,10.]]
 plan={'status':'numerical_refinement_only_after_mathematical_checks','source_targets_read':False,'case_sequence':[{'nx':x,'ny':y,'nz':z,'speed':s} for x,y,z,s in cases],'reason_for48_grid':'The very small paired effect merits a cross-section check at the original accepted48x144 resolution. The measured12x36x120 pilot needed0.55s and82MiB, so staged growth is justified within original resource caps. The original1600-slab coupled system remains outside this planned sequence.','continuation_guard':'Advance beyond36x108 only if that stage uses less than900MiB observed peak RSS and60s per case; maintain all original hard limits','paired_effect_outer_difference_gate':.0005,'interpretation':'Report actual differences and tolerance floor; the loose outer gate alone cannot resolve an effect smaller than itself','solver_sha256':sha(HERE/'axial_fin.py'),'mathematical_verification_sha256':sha(HERE/'mathematical_verification.json')}
 (HERE/'refinement_plan.json').write_text(json.dumps(plan,indent=2)+'\n');rows=[];start=time.monotonic();blocked=None
 for nx,ny,nz,speed in cases:
  if nx==48:
   previous=[r for r in rows if r['mesh']['gap_cells']==36]
   if previous and any(r['process_peak_RSS_MiB']>900 or r['elapsed_seconds']>60 for r in previous):blocked='Resource pilot guard prevents advancing to48-cell grid';break
  try:
   m=AxialModel(nx,ny,nz,speed,1.);r=m.solve(include_samples=False);del m;gc.collect()
   assert r['energy_relative_balance']<1e-8 and r['componentwise_backward_error_max']<1e-8
   assert r['minimum_normalized_temperature']>-1e-8 and r['maximum_normalized_temperature']<1+1e-8
   rows.append(r);print('case',nx,ny,nz,speed,'delta%',100*r['paired_relative_conductance_change'],'seconds',r['elapsed_seconds'],'MiB',r['process_peak_RSS_MiB'],flush=True)
   progress={'status':'refinement_running','source_targets_read':False,'rows':rows,'axial_code_sha256':sha(HERE/'axial_fin.py')};(HERE/'refinement_progress.json').write_text(json.dumps(progress,indent=2,allow_nan=False)+'\n')
  except ResourceLimit as e:blocked=str(e);print('LIMIT',blocked,flush=True);break
  if time.monotonic()-start>1800:blocked='Total study computation budget reached';break
 comparisons=[]
 for speed in [4.,10.]:
  for label,a,b in [('axial12_60_to120',(12,60),(12,120)),('axial12_120_to240',(12,120),(12,240)),('transverse12_to24',(12,240),(24,240)),('transverse24_to36',(24,240),(36,240)),('transverse36_to48',(36,240),(48,240)),('axial48_240_to480',(48,240),(48,480))]:
   find=lambda g:next((r for r in rows if r['mesh']['gap_cells']==g[0] and r['mesh']['axial_slabs']==g[1] and r['V_interior_m_s']==speed),None)
   aa,bb=find(a),find(b)
   if aa is not None and bb is not None:
    change=bb['paired_relative_conductance_change']-aa['paired_relative_conductance_change'];comparisons.append({'label':label,'speed':speed,'previous_delta':aa['paired_relative_conductance_change'],'refined_delta':bb['paired_relative_conductance_change'],'absolute_delta_change':abs(change),'absolute_delta_change_percentage_points':100*abs(change),'relative_change_in_absolute_baseline_G':bb['baseline_same_mesh_G_W_K']/aa['baseline_same_mesh_G_W_K']-1})
 final=[r for r in rows if r['mesh']['gap_cells']==48 and r['mesh']['axial_slabs']==480]
 gates={'complete_declared_sequence':len(rows)==len(cases),'energy':all(r['energy_relative_balance']<1e-8 for r in rows),'backward_error':all(r['componentwise_backward_error_max']<1e-8 for r in rows),'paired_refinement_outer_gate':all(r['absolute_delta_change']<=.0005 for r in comparisons),'final_pair_available':len(final)==2}
 out={'status':'paired_refinement_completed' if all(gates.values()) else 'incomplete_or_failed_refinement','gates':gates,'blocker':blocked,'source_targets_read':False,'rows':rows,'comparisons':comparisons,'elapsed_seconds':time.monotonic()-start,'plan_sha256':sha(HERE/'refinement_plan.json'),'axial_code_sha256':sha(HERE/'axial_fin.py'),'refinement_script_sha256':sha(__file__),'physical_validation_pass':None,'aircraft_transfer_authorized':False}
 (HERE/'refinement.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');print('FINAL',gates,flush=True);assert (HERE/'refinement.json').stat().st_size<100000
if __name__=='__main__':main()
