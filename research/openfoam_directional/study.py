#!/usr/bin/env python3
"""Pre-registered momentum-only directional refinement; historical bytes are read-only."""
from __future__ import annotations
import argparse, datetime, hashlib, importlib.util, json, os, re, subprocess, sys, time
from pathlib import Path
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
spec=importlib.util.spec_from_file_location('frozen_openfoam_study',HERE.parent/'openfoam_3d/study.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
PLAN=json.loads((HERE/'plan.json').read_text())

def discrete_profile(ny,nz):
 def one(n,h):
  diag=np.full(n,2.);diag[[0,-1]]=3.
  return sparse.diags([-np.ones(n-1),diag,-np.ones(n-1)],[-1,0,1],format='csr')/h**2
 a=sparse.kron(one(ny,s.W/ny),sparse.eye(nz))+sparse.kron(sparse.eye(ny),one(nz,s.H/nz))
 v=spsolve(a.tocsr(),np.ones(ny*nz));res=float(np.max(abs(a@v-1)))
 return (s.UM*v/v.mean()).reshape(ny,nz),float(s.MU*s.UM/v.mean()),res

def continuum_profile(ny,nz,average=False):
 y=(np.arange(ny)+.5)*s.W/ny;z=(np.arange(nz)+.5)*s.H/nz
 yy,zz=np.meshgrid(y,z,indexing='ij')
 if not average:return s.UM*s.velocity_shape(yy,zz)
 Y=yy/s.H;Z=zz/s.H;dy=s.W/ny/s.H;dz=1/nz
 out=Z*(1-Z)/2-dz**2/24
 for n in range(1,800,2):
  k=n*np.pi;lo=Y-dy/2;hi=Y+dy/2
  cy=(np.exp(k*(hi-2))-np.exp(k*(lo-2))+np.exp(-k*lo)-np.exp(-k*hi))/(k*dy*(1+np.exp(-2*k)))
  sz=np.sin(k*Z)*np.sinc(n*dz/2)
  out-=4/np.pi**3*sz*cy/n**3
 return s.UM*out/s.exact_mean()

def indices(mesh,grid):
 c=mesh['centers'];nx,ny,nz=grid
 ix=np.clip(np.floor(c[:,0]/s.L*nx).astype(int),0,nx-1)
 iy=np.clip(np.floor(c[:,1]/s.W*ny).astype(int),0,ny-1)
 iz=np.clip(np.floor(c[:,2]/s.H*nz).astype(int),0,nz-1)
 return ix,iy,iz

def supplement_inlet(case,mesh,grid):
 _,ny,nz=grid;profile,g,res=discrete_profile(ny,nz)
 fc=mesh['face_centers'][mesh['patches']['inlet']]
 iy=np.clip(np.floor(fc[:,1]/s.W*ny).astype(int),0,ny-1);iz=np.clip(np.floor(fc[:,2]/s.H*nz).astype(int),0,nz-1)
 ux=profile[iy,iz];v=np.column_stack((ux,np.zeros_like(ux),np.zeros_like(ux)))
 b={'inlet':('fixedValue',v),'outlet':('zeroGradient',None),**{w:('fixedValue',(0,0,0)) for w in s.WALLS}}
 s.scalar_field(case/'0/U','U','volVectorField','[0 1 -1 0 0 0 0]',(0,0,0),b)
 setup=json.loads((case/'setup.json').read_text());setup.update(inlet_kind='discrete_developed',discrete_reference_gradient_Pa_m=g,discrete_linear_residual=res)
 s.write_json(case/'setup.json',setup)

def analyse(case,name,output,reused=False):
 setup=json.loads((case/'setup.json').read_text());grid=setup['grid'];nx,ny,nz=grid
 mesh=s.read_mesh(case);c=mesh['centers'];n=len(c);ix,iy,iz=indices(mesh,grid)
 u,_=s.read_field(case/'flow_final/U',n);p,_=s.read_field(case/'flow_final/p',n);p=p*s.RHO
 ni=len(mesh['neighbour']);phi,phib=s.read_field(case/'flow_final/phi',ni)
 xs=(np.arange(nx)+.5)*s.L/nx
 pmean=np.bincount(ix,weights=p,minlength=nx)/(ny*nz);umean=np.bincount(ix,weights=u[:,0],minlength=nx)/(ny*nz)
 gradients={}
 for low,hi in [(.25,.75),(.1,.9),(.4,.6),(.6,.9)]:
  mask=(xs>low*s.L)&(xs<hi*s.L)
  fit=np.polyfit(xs[mask],pmean[mask],1)
  gradients[f'{low:.2f}_{hi:.2f}']={'gradient_Pa_m':float(-fit[0]),'max_fit_departure_Pa':float(np.max(abs(pmean[mask]-np.polyval(fit,xs[mask]))))}
 g=gradients['0.25_0.75']['gradient_Pa_m'];exact=s.MU*s.UM/(s.H**2*s.exact_mean())
 dp,gd,linres=discrete_profile(ny,nz);ref=continuum_profile(ny,nz);avg=continuum_profile(ny,nz,True)
 mask=(c[:,0]>.25*s.L)&(c[:,0]<.75*s.L)
 norm=setup['inlet_midpoint_quadrature_normalization']
 def l2(reference):return float(np.linalg.norm(u[mask,0]-reference[iy[mask],iz[mask]])/np.linalg.norm(reference[iy[mask],iz[mask]]))
 patchflux={k:float(np.sum(np.broadcast_to(phib[k],(len(ids),)))) for k,ids in mesh['patches'].items()}
 allphi=np.zeros(len(mesh['owner']));allphi[:ni]=phi
 for k,ids in mesh['patches'].items():allphi[ids]=np.broadcast_to(phib[k],(len(ids),))
 fx=np.abs(mesh['Sf'][:,0])>1e-16
 faceix=np.clip(np.rint(mesh['face_centers'][fx,0]/s.L*nx).astype(int),0,nx)
 flux=np.bincount(faceix,weights=allphi[fx]*np.sign(mesh['Sf'][fx,0]),minlength=nx+1)
 q=s.UM*s.W*s.H
 middle=np.abs(ix-nx//2)<1
 # Plane arrays use explicit cell indexing rather than reshape assumptions.
 plane_u=np.zeros((ny,nz));plane_p=np.zeros((ny,nz))
 plane_u[iy[middle],iz[middle]]=u[middle,0];plane_p[iy[middle],iz[middle]]=p[middle]
 log=(case/'log.checkMesh').read_text();residual=s.residuals(case/'log.simpleFoam')
 row={'name':name,'source_case':str(case.relative_to(REPO)),'reused_historical':reused,'grid':grid,'cells':n,'inlet_kind':setup.get('inlet_kind','continuum_midpoint_normalized'),
  'pressure_gradient_Pa_m':g,'continuum_pressure_gradient_Pa_m':exact,'continuum_pressure_relative_error':g/exact-1,'discrete_pressure_gradient_Pa_m':gd,'discrete_pressure_relative_error':g/gd-1,'discrete_to_continuum_relative_error':gd/exact-1,'operator_residual_to_total_bias_fraction':abs(g-gd)/abs(g-exact),
  'velocity_point_relative_L2':l2(ref),'velocity_cell_average_relative_L2':l2(avg),'velocity_discrete_relative_L2':l2(dp),'velocity_equivalent_mean_relative_L2':l2(ref/norm) if setup.get('inlet_kind')!='discrete_developed' else None,
  'inlet_midpoint_quadrature_normalization':norm,'equivalent_continuous_mean_m_s':s.UM/norm if setup.get('inlet_kind')!='discrete_developed' else None,'discrete_poisson_residual_max':linres,
  'pressure_fit_windows':gradients,'pressure_window_spread_relative':(max(v['gradient_Pa_m'] for v in gradients.values())-min(v['gradient_Pa_m'] for v in gradients.values()))/abs(g),
  'inlet_owner_to_outlet_pressure_drop_Pa':float(p[mesh['owner'][mesh['patches']['inlet']]].mean()),'nominal_continuum_drop_Pa':exact*s.L,
  'volume_flux_by_patch_m3_s':patchflux,'relative_mass_imbalance':abs(sum(patchflux.values()))/q,'max_station_flux_departure_relative':float(max(abs(flux-q))/q),
  'section_velocity_mean_min_m_s':float(umean.min()),'section_velocity_mean_max_m_s':float(umean.max()),'maximum_transverse_velocity_m_s':float(np.max(np.linalg.norm(u[:,1:],axis=1))),
  'mesh_ok':'Mesh OK.' in log,'three_dimensions':'Mesh has 3 solution (non-empty) directions (1 1 1)' in log,'flow_residuals':residual,'flow_runtime':json.loads((case/'flow_run.json').read_text())}
 row['execution_gates']={'mesh_ok_3d':row['mesh_ok'] and row['three_dimensions'],'residuals':max(v['initial'] for v in residual.values())<=1e-7,'mass':row['relative_mass_imbalance']<=1e-7,'station_flux':row['max_station_flux_departure_relative']<=1e-7}
 s.write_json(output/(name+'.json'),row)
 s.write_json(output/(name+'_profiles.json'),{'source_case':row['source_case'],'x_m':xs.tolist(),'pressure_mean_Pa':pmean.tolist(),'velocity_mean_m_s':umean.tolist(),'local_pressure_gradient_Pa_m':(-np.gradient(pmean,xs)).tolist(),'flux_station_x_m':np.linspace(0,s.L,nx+1).tolist(),'flux_m3_s':flux.tolist(),'middle_plane_x_m':float(xs[nx//2]),'middle_Ux_m_s':plane_u.tolist(),'middle_p_Pa':plane_p.tolist(),'continuum_point_Ux_m_s':ref.tolist(),'continuum_cell_average_Ux_m_s':avg.tolist(),'discrete_Ux_m_s':dp.tolist()})
 return row

def audit_old():
 subprocess.run([sys.executable,'-S',str(HERE.parent/'openfoam_3d/audit_package.py'),'--full-source'],cwd=REPO,check=True)
 if s.sha(HERE.parent/'openfoam_3d/study.py')!=PLAN['base_script_sha256']:raise RuntimeError('Original solver source changed')

def run_all(root):
 if root.exists():raise ValueError('Choose a fresh output namespace; prior output is never overwritten')
 audit_old();root.mkdir(parents=True);metrics=root/'metrics';metrics.mkdir()
 snapshot={str(p.relative_to(REPO)):s.sha(p) for p in sorted((HERE.parent/'openfoam_3d').rglob('*')) if p.is_file() and '__pycache__' not in str(p)}
 s.write_json(root/'historical_hashes_before.json',snapshot)
 lock={'registered_before_solver_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan_sha256':s.sha(HERE/'plan.json'),'study_sha256':s.sha(HERE/'study.py'),'baseline_commit':PLAN['baseline_commit']}
 s.write_json(root/'run_lock.json',lock)
 old=REPO/PLAN['reuse']['root'];rows=[]
 for name,i in [('historical_coarse',0),('B',1),('F',2),('historical_extra',3)]:
  print('Analyse existing '+name,flush=True);rows.append(analyse(old/f'grid_{i}',name,metrics,True))
 used=0.
 for entry in PLAN['new_primary_cases']+PLAN['new_supplementary_cases']:
  name=entry['name'];case=root/name;grid=entry['grid'];print('START '+name+' '+str(grid),flush=True)
  mesh=s.setup(case,grid)
  if name=='discrete_developed_inlet':supplement_inlet(case,mesh,grid)
  del mesh
  remaining=PLAN['budget']['maximum_new_solver_wall_seconds']-used
  if remaining<=0:raise RuntimeError('Preregistered solver budget exhausted')
  limit=min(remaining,PLAN['budget']['maximum_single_solver_wall_seconds'])
  started=time.monotonic()
  try:
   elapsed=s.run([s.FOAM,'simpleFoam','-case',case],case,'log.simpleFoam',timeout=limit)
  except Exception as exc:
   failed_seconds=time.monotonic()-started
   s.write_json(root/'failed_attempt.json',{'case':name,'exception':repr(exc),'failed_solver_wall_seconds':failed_seconds,'total_solver_wall_seconds_including_failed':used+failed_seconds,'original_evidence_untouched':True})
   raise
  used+=elapsed
  final=s.latest(case)
  if 'SIMPLE solution converged' not in (case/'log.simpleFoam').read_text():raise RuntimeError('Flow not converged: '+name)
  import shutil
  shutil.copytree(final,case/'flow_final')
  s.write_json(case/'flow_run.json',{'wall_seconds':elapsed,'iterations':float(final.name),'final_time':final.name,'solver':'simpleFoam'})
  row=analyse(case,name,metrics);rows.append(row)
  s.write_json(root/'progress.json',{'new_solver_wall_seconds':used,'completed':[r['name'] for r in rows]})
  print('DONE '+name+' '+json.dumps({k:row[k] for k in ['pressure_gradient_Pa_m','continuum_pressure_relative_error','discrete_pressure_relative_error','execution_gates']}),flush=True)
  size=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
  if size>PLAN['budget']['maximum_new_working_storage_GB']*1e9:raise RuntimeError('Storage budget reached')
 after={p:s.sha(REPO/p) for p in snapshot}
 if after!=snapshot:raise RuntimeError('Historical evidence changed')
 if s.sha(HERE/'plan.json')!=lock['plan_sha256'] or s.sha(HERE/'study.py')!=lock['study_sha256']:raise RuntimeError('Preregistered source changed during run')
 s.write_json(root/'all_metrics.json',rows);s.write_json(root/'run_summary.json',{'all_new_cases_completed':True,'new_solver_wall_seconds':used,'historical_bytes_unchanged':True,'new_working_bytes':size,'run_lock':lock})
 audit_old();print('ALL COMPLETED',flush=True)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();run_all(a.output.resolve())
