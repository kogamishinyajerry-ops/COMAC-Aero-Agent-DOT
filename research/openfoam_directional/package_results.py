#!/usr/bin/env python3
"""Compact data and actual-field figures; no generated CFD pictures."""
import argparse, datetime, json, os, shutil
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/tmp/aerolab-directional-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator
import numpy as np
import study as d
import storage
s=d.s;HERE=d.HERE;REPO=d.REPO

def order_three(rows):
 if any(row is None for row in rows):return {'eligible':False,'not_estimated_reason':'A planned case did not converge within its frozen budget; no unconverged value used.'}
 g=np.array([r['pressure_gradient_Pa_m'] for r in rows]);diff=np.diff(g)
 original=json.loads((HERE.parent/'openfoam_3d/evidence/report.json').read_text())
 stationarity=max(abs(x['flow']['metrics']['pressure_gradient_relative_change']) for x in original['stationarity'])
 relative_noise=max(1e-8,100*stationarity)
 noise=relative_noise*max(abs(g))
 out={'cases':[r['name'] for r in rows],'gradients_Pa_m':g.tolist(),'successive_differences_Pa_m':diff.tolist(),'relative_noise_floor':relative_noise,'original_stationarity_max_relative':stationarity,'conditional_only':True,'GCI_or_uncertainty_bound':False}
 eligible=bool(diff[0]*diff[1]>0 and abs(diff[1])<abs(diff[0]) and np.min(abs(diff))>noise)
 out['eligible']=eligible
 if eligible:
  p=float(np.log(abs(diff[0]/diff[1]))/np.log(2));extrap=float(g[-1]+diff[-1]/(2**p-1))
  out.update(observed_order=p,conditional_richardson_gradient_Pa_m=extrap,conditional_extrapolation_error_to_fully_developed_target=extrap/rows[0]['continuum_pressure_gradient_Pa_m']-1)
 else:out['not_estimated_reason']='Non-contracting, sign-changing, or near-noise differences; no reliable positive-order estimate.'
 return out

def make_report(root,out):
 rows=json.loads((root/'all_metrics.json').read_text());r={v['name']:v for v in rows};summary=json.loads((root/'run_summary.json').read_text())
 b,a,t,f=[r[x]['pressure_gradient_Pa_m'] for x in ['B','axial_fine','transverse_fine','F']]
 dx=a-b;dt=t-b;interaction=f-a-t+b;full=f-b;frac=abs(dt)/(abs(dt)+abs(dx))
 directional=frac>=.9 and abs(interaction)<=.1*abs(full)
 operator=all(r[n]['operator_residual_to_total_bias_fraction']<=.1 for n in ['B','transverse_fine'])
 supplement=r.get('discrete_developed_inlet');delta=supplement['pressure_gradient_Pa_m']-b if supplement else None
 report={'schema':'aerolab-directional-pressure-diagnosis-evidence-v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'purpose':'Momentum discretization and boundary diagnosis only; fully developed reference is not exact finite-duct truth.',
 'original_validation':{'status':'FAILED_RETAINED','pressure_relative_change':d.PLAN['immutable_original_pressure_grid_gate']['relative_change'],'threshold':.01,'no_retroactive_override':True},
 'run':summary,'all_completed_case_execution_gates_passed':all(all(x['execution_gates'].values()) for x in rows),'all_planned_cases_completed_and_execution_gates_passed':summary['all_new_cases_completed'] and all(all(x['execution_gates'].values()) for x in rows),
 'directional_attribution':{'B_Pa_m':b,'A_axial_only_Pa_m':a,'T_transverse_only_Pa_m':t,'F_combined_Pa_m':f,'axial_change_Pa_m':dx,'transverse_change_Pa_m':dt,'combined_change_Pa_m':full,'interaction_Pa_m':interaction,'decomposition_closure_Pa_m':full-dx-dt-interaction,'axial_change_relative_B':dx/b,'transverse_change_relative_B':dt/b,'interaction_relative_full_change':interaction/full,'transverse_absolute_share_of_separate_changes':frac,'predeclared_transverse_dominance_supported':directional},
 'operator_attribution':{'predeclared_90_percent_explanation_supported':operator,'residual_to_total_bias_fraction_B':r['B']['operator_residual_to_total_bias_fraction'],'residual_to_total_bias_fraction_transverse_fine':r['transverse_fine']['operator_residual_to_total_bias_fraction'],'interpretation':'Discrete fully developed Poisson explains an algebraic portion; remaining primary-case bias includes inlet/end/axial/coupling effects. Supplement changes only inlet shape at fixed physical flow.'},
 'supplementary_inlet':{'pressure_change_from_B_Pa_m':delta,'pressure_change_relative_B':delta/b if supplement else None,'remaining_relative_error_to_discrete_target':supplement['discrete_pressure_relative_error'] if supplement else None,'removed_fraction_of_original_discrete_target_gap':delta/(r['B']['discrete_pressure_gradient_Pa_m']-b) if supplement else None,'not_in_primary_refinement_ladders':True,'accepted_causal_conclusion':False if supplement is None else 'requires interpretation','failure':summary.get('failed_planned_cases',[])},
 'orders':{'transverse_coarse_medium_fine':order_three([r[n] for n in ['transverse_coarse','B','transverse_fine']]),'transverse_medium_fine_extra':order_three([r.get(n) for n in ['B','transverse_fine','transverse_extra_fine']]),'axial_fixed_transverse':order_three([r[n] for n in ['axial_coarse','B','axial_fine']])},
 'new_transverse_2x_change':{'coarser':'transverse_fine','finer':'transverse_extra_fine','relative_change':abs(r['transverse_extra_fine']['pressure_gradient_Pa_m']/t-1) if 'transverse_extra_fine' in r else None,'reporting_limit':.01,'is_original_all_direction_gate':False},
 'rows':rows,'limitations':['No new thermal or solid-fluid conjugate calculation.','Prescribed pressure-zeroGradient inlet and a mesh-dependent sampled continuum velocity profile are not an exact finite-duct Poiseuille boundary problem.','Conditional Richardson estimates assume leading single-power error and do not establish GCI or physical uncertainty.','Fixed axial resolution in the transverse ladder cannot pass the original all-direction grid gate.','No actual aircraft, installation, experimental validation, device hotspot or converged total wall-heat claim.','Original discontinuous inlet/wall thermal corner remains singular; no new thermal evidence is asserted.']}
 if 'transverse_extra_fine' in r:
  qp=json.loads((root/'metrics/transverse_extra_fine_profiles.json').read_text());xx=np.array(qp['x_m'])/s.L;gg=np.array(qp['local_pressure_gradient_Pa_m'])
  entrance=(xx>.05)&(xx<.25);interior=(xx>.25)&(xx<.75)
  report['entrance_pressure_diagnostic']={'exploratory_not_preregistered_acceptance_gate':True,'case':'transverse_extra_fine','near_inlet_x_over_L':[.05,.25],'near_inlet_local_gradient_range_Pa_m':[float(gg[entrance].min()),float(gg[entrance].max())],'interior_x_over_L':[.25,.75],'interior_local_gradient_range_Pa_m':[float(gg[interior].min()),float(gg[interior].max())],'interpretation':'Saved pressure exhibits near-inlet mesh-scale oscillations; the cause among discretization, BC and pressure-velocity coupling is unresolved. Interior-fit accuracy does not establish globally smooth pressure.'}
  report['limitations'].append(report['entrance_pressure_diagnostic']['interpretation'])
 if not supplement:report['limitations'].append('The separately registered inlet-isolation control failed its frozen residual gate at1500iterations. Its final field is provisional only, excluded from accepted comparisons and causal conclusions.')
 s.write_json(out/'report.json',report)
 for p in sorted((root/'metrics').glob('*_profiles.json')):shutil.copy2(p,out/p.name)
 return report

def figures(report,out):
 r={v['name']:v for v in report['rows']};exact=r['B']['continuum_pressure_gradient_Pa_m']
 profiles={n:storage.read_json(out/(n+'_profiles.json')) for n in r}
 plt.rcParams.update({'font.size':10,'axes.grid':True,'grid.alpha':.2})
 fig,axs=plt.subplots(2,2,figsize=(13,9),constrained_layout=True)
 names=[n for n in ['transverse_coarse','B','transverse_fine','transverse_extra_fine'] if n in r];ns=np.array([r[n]['grid'][1] for n in names])
 axs[0,0].plot(ns,[100*r[n]['continuum_pressure_relative_error'] for n in names],'o-',label='Actual OpenFOAM, nx=80')
 axs[0,0].plot(ns,[100*r[n]['discrete_to_continuum_relative_error'] for n in names],'s--',label='Independent fully developed FV')
 axs[0,0].axhline(0,color='k',lw=.7);axs[0,0].set(xscale='log',xticks=ns,xticklabels=ns.astype(str),xlabel='Cross-section ny (nz=ny/2)',ylabel='Pressure bias to fixed-3 m/s target (%)',title='A. Matched-BC transverse ladder');axs[0,0].legend(fontsize=9);axs[0,0].xaxis.set_minor_locator(NullLocator())
 names=['axial_coarse','B','axial_fine'];ns=np.array([r[n]['grid'][0] for n in names])
 axs[0,1].plot(ns,[r[n]['pressure_gradient_Pa_m'] for n in names],'o-',label='Actual OpenFOAM')
 axs[0,1].set(xlabel='Axial cell count nx',ylabel='Interior gradient (Pa/m)',title='B. Axial ladder, cross-section fixed 32x16',xticks=ns)
 axs[0,1].ticklabel_format(useOffset=False,axis='y')
 for name,label in [('B','B: sampled continuum inlet'),(('discrete_developed_inlet' if 'discrete_developed_inlet' in r else 'transverse_extra_fine'),('B: discrete developed inlet' if 'discrete_developed_inlet' in r else 'Transverse extra fine: original inlet')),('transverse_fine','Transverse fine: original inlet')]:
  q=profiles[name];x=np.array(q['x_m'])/s.L;g=np.array(q['local_pressure_gradient_Pa_m']);mask=(x>.05)&(x<.95)
  axs[1,0].plot(x[mask],g[mask],label=label)
 axs[1,0].axhline(exact,ls=':',color='k',label='Fully developed continuum target')
 axs[1,0].axvspan(.25,.75,alpha=.06,color='black');axs[1,0].set(xlabel='x/L',ylabel='Section-mean local -dp/dx (Pa/m)',title='C. Actual saved pressure stations');axs[1,0].legend(fontsize=8)
 names=[n for n in ['B','transverse_fine','F','transverse_extra_fine','discrete_developed_inlet'] if n in r];labels=[{'B':'B','transverse_fine':'T','F':'F','transverse_extra_fine':'T2','discrete_developed_inlet':'B + discrete\ninlet'}[n] for n in names]
 op=np.array([100*r[n]['discrete_to_continuum_relative_error'] for n in names]);rem=np.array([100*(r[n]['pressure_gradient_Pa_m']-r[n]['discrete_pressure_gradient_Pa_m'])/exact for n in names])
 axs[1,1].bar(labels,op,label='Fully developed transverse FV bias');axs[1,1].bar(labels,rem,bottom=op,label='Remaining finite-duct influence');axs[1,1].axhline(0,color='k',lw=.7)
 axs[1,1].set(ylabel='Bias / continuum gradient (%)',title='D. Algebraic decomposition, not automatic causality');axs[1,1].legend(fontsize=8)
 fig.suptitle('Directional pressure diagnosis | original 1.120839% > 1% gate remains FAILED\nInlet-isolation control failed its frozen residual gate; excluded from accepted comparisons',fontsize=12)
 fig.savefig(out/'directional_comparison.png',dpi=160);plt.close(fig)
 fig,axs=plt.subplots(1,3,figsize=(13,4),constrained_layout=True)
 last='transverse_extra_fine' if 'transverse_extra_fine' in r else 'transverse_fine'
 middle='discrete_developed_inlet' if 'discrete_developed_inlet' in r else 'transverse_fine'
 for ax,name,title in zip(axs,['B',middle,last],['B: original inlet','B: discrete-developed inlet' if middle=='discrete_developed_inlet' else 'T: original inlet',('T2' if last=='transverse_extra_fine' else 'T')+': transverse refined']):
  q=profiles[name];ux=np.array(q['middle_Ux_m_s']);ref=np.array(q['discrete_Ux_m_s']);err=100*(ux-ref)/s.UM
  p=ax.imshow(err.T,origin='lower',extent=[0,s.W*1000,0,s.H*1000],aspect='equal',interpolation='nearest',cmap='coolwarm',vmin=-max(np.max(abs(err)),1e-12),vmax=max(np.max(abs(err)),1e-12))
  ax.set(title=title+'\nactual x='+f"{q['middle_plane_x_m']*1000:.4f}"+' mm',xlabel='y (mm)',ylabel='z (mm)');fig.colorbar(p,ax=ax,shrink=.7,label='(Ux - discrete FD Ux) / 3 m/s (%)')
 fig.suptitle('Actual OpenFOAM mid-duct cell fields; separate color scales; no thermal inference',fontsize=12)
 fig.savefig(out/'actual_velocity_difference.png',dpi=170);plt.close(fig)

def provenance(root,out):
 files=[]
 for p in sorted(root.rglob('*')):
  if not p.is_file():continue
  rel=p.relative_to(root)
  if any(x in rel.parts for x in ['metrics']):continue
  files.append({'path':str(rel),'bytes':p.stat().st_size,'sha256':s.sha(p)})
 s.write_json(out/'source_artifacts.json',{'source_root_relative_to_repository':str(root.relative_to(REPO)),'files':files})
 logs={}
 for name in [x['name'] for x in d.PLAN['new_primary_cases']+d.PLAN['new_supplementary_cases']]:
  case=root/name
  logs[name]={'checkMesh_tail':(case/'log.checkMesh').read_text()[-3500:],'simpleFoam_tail':(case/'log.simpleFoam').read_text()[-4500:],'completed_and_used':(case/'flow_final').is_dir()}
 s.write_json(out/'solver_log_extracts.json',logs)
 shutil.copy2(root/'run_lock.json',out/'run_lock.json');shutil.copy2(root/'run_summary.json',out/'run_summary.json')

def manifest():
 files=[]
 for p in sorted(HERE.rglob('*')):
  if p.is_file() and '__pycache__' not in str(p) and p.name!='manifest.json':files.append({'path':str(p.relative_to(REPO)),'bytes':p.stat().st_size,'sha256':s.sha(p)})
 for record in storage.records():
  path=HERE/record['path']
  if not path.is_file():files.append({'path':str(path.relative_to(REPO)),'bytes':record['bytes'],'sha256':record['sha256'],'storage':'exact-byte-gzip-parts'})
 files.sort(key=lambda item:item['path'])
 s.write_json(HERE/'evidence/manifest.json',{'schema':'aerolab-directional-package-v1','publication_storage':'storage.py resolves archived logical artifacts to the original bytes','files':files})

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--manifest-only',action='store_true');a=ap.parse_args()
 if a.manifest_only:manifest()
 else:
  out=HERE/'evidence';out.mkdir(exist_ok=True);report=make_report(a.output.resolve(),out);figures(report,out);provenance(a.output.resolve(),out);manifest()
