#!/usr/bin/env python3
"""Compact, provenance-bound evidence from saved real OpenFOAM fields."""
import argparse, hashlib, json, math, os, platform, shutil
from pathlib import Path
import numpy as np
os.environ.setdefault('MPLCONFIGDIR','/tmp/openfoam-3d-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
import study as s

def plots(base,out,rows):
 level=len(rows)-1;f=np.load(base/f'grid_{level}/fields.npz');c=f['centers'];rounded=np.round(c,10);idx=np.lexsort((rounded[:,2],rounded[:,1],rounded[:,0]));nx,ny,nz=rows[-1]['grid']
 assert tuple(len(np.unique(rounded[:,d])) for d in range(3))==(nx,ny,nz)
 C=c[idx].reshape(nx,ny,nz,3);U=f['U'][idx].reshape(nx,ny,nz,3);T=f['T'][idx].reshape(nx,ny,nz)
 xs=C[:,0,0,0]*1000;ys=C[0,:,0,1]*1000;zs=C[0,0,:,2]*1000
 fig,ax=plt.subplots(1,3,figsize=(13,3.8),layout='constrained')
 a=ax[0].imshow(U[nx//2,:,:,0].T,origin='lower',extent=[0,4,0,2],aspect='equal',cmap='viridis');fig.colorbar(a,ax=ax[0],label='u_x [m/s]',shrink=.65);ax[0].set(title='Solved velocity at x≈15 mm',xlabel='y [mm]',ylabel='z [mm]')
 a=ax[1].imshow(T[:,:,nz//2].T,origin='lower',extent=[0,30,0,4],aspect='auto',vmin=300,vmax=310,cmap='inferno');fig.colorbar(a,ax=ax[1],label='T [K]',shrink=.65);ax[1].set(title='Axial heating at z≈1 mm',xlabel='x [mm]',ylabel='y [mm]')
 a=ax[2].imshow(T[-1].T,origin='lower',extent=[0,4,0,2],aspect='equal',vmin=300,vmax=310,cmap='inferno');fig.colorbar(a,ax=ax[2],label='T [K]',shrink=.65);ax[2].set(title='Last-cell temperature cross-section',xlabel='y [mm]',ylabel='z [mm]')
 fig.suptitle(f'Actual OpenFOAM cells: {nx}×{ny}×{nz} | inlet 300 K, four no-slip walls 310 K, mean speed 3 m/s',fontsize=11)
 fig.savefig(out/'actual_fields.png',dpi=130);plt.close(fig)
 fig=plt.figure(figsize=(8,5.5),layout='constrained');ax=fig.add_subplot(projection='3d');norm=Normalize(300,310);cmap=plt.get_cmap('inferno')
 # Decimate real cell-center slices only; never used for acceptance.
 ix=np.linspace(0,nx-1,min(nx,45)).astype(int);iy=np.linspace(0,ny-1,min(ny,33)).astype(int);iz=np.linspace(0,nz-1,min(nz,21)).astype(int)
 X,Y=np.meshgrid(xs[ix],ys[iy],indexing='ij');ax.plot_surface(X,Y,np.full_like(X,zs[nz//2]),facecolors=cmap(norm(T[np.ix_(ix,iy,[nz//2])][:,:,0])),shade=False)
 X,Z=np.meshgrid(xs[ix],zs[iz],indexing='ij');ax.plot_surface(X,np.full_like(X,ys[ny//2]),Z,facecolors=cmap(norm(T[np.ix_(ix,[ny//2],iz)][:,0,:])),shade=False)
 Y,Z=np.meshgrid(ys[iy],zs[iz],indexing='ij');ax.plot_surface(np.full_like(Y,xs[-1]),Y,Z,facecolors=cmap(norm(T[-1][np.ix_(iy,iz)])),shade=False)
 ax.set(xlabel='x [mm]',ylabel='y [mm]',zlabel='z [mm]',title='Actual 3D temperature slices, T(x,y,z)\nSynthetic duct; aspect visually compressed along x')
 ax.set_box_aspect((4,2,1));ax.view_init(25,-125);fig.colorbar(ScalarMappable(norm=norm,cmap=cmap),ax=ax,label='Temperature [K]',shrink=.55)
 fig.savefig(out/'actual_three_dimensional_slices.png',dpi=125);plt.close(fig)
 fig,ax=plt.subplots(1,2,figsize=(10.5,4.3),layout='constrained');h=[2/r['grid'][2] for r in rows]
 for key,label in [('nominal_mean_pressure_gradient_relative_error','Pressure gradient vs nominal exact'),('nominal_mean_velocity_relative_L2_error_middle_half','Velocity L2 vs nominal exact'),('analytic_thermal_relative_L2_error','Smooth thermal sentinel L2')]:
  ax[0].loglog(h,[100*abs(r[key]) for r in rows],'o-',label=label)
 ax[0].axhline(1,color='gray',ls='--',lw=.7);ax[0].axhline(.5,color='gray',ls=':',lw=.7);ax[0].invert_xaxis();ax[0].set(xlabel='Transverse cell height [mm] (refining →)',ylabel='Analytical error [%]',title='Known-reference errors');ax[0].grid(alpha=.2);ax[0].legend(fontsize=7)
 ax[1].plot([r['cells'] for r in rows],[r['outlet_mixed_temperature_K'] for r in rows],'o-',label='3D OpenFOAM mixed outlet')
 ref=json.loads((base/'references.json').read_text());tg=310-10*ref['galerkin'][-1]['bulk_theta'];ax[1].axhline(tg,color='black',ls='--',label='Graetz reference (different PDE)')
 ax[1].set(xlabel='3D fluid cells',ylabel='Mixed outlet temperature [K]',title='Outlet-temperature convergence');ax[1].grid(alpha=.2);ax[1].legend(fontsize=7);ax[1].ticklabel_format(axis='x',style='sci',scilimits=(0,0))
 fig.suptitle('Original 2× pressure refinement gate FAILED: 1.12084% > 1%; extra-grid evidence stays separate',fontsize=10,color='#9d4015')
 fig.savefig(out/'convergence.png',dpi=135);plt.close(fig)
 display={'purpose':'Display-only nearest cell-center samples, rounded; never used for acceptance','source_grid':rows[-1]['grid'],'units':{'coordinates':'m','velocity':'m/s','temperature':'K','pressure':'Pa'},'x_m':np.round(xs[ix]/1000,10).tolist(),'y_m':np.round(ys[iy]/1000,10).tolist(),'z_m':np.round(zs[iz]/1000,10).tolist(),'outlet_cell_temperature_K':np.round(T[-1][np.ix_(iy,iz)],6).tolist(),'middle_x_velocity_x_m_s':np.round(U[nx//2,:,:,0][np.ix_(iy,iz)],7).tolist(),'middle_z_temperature_K':np.round(T[np.ix_(ix,iy,[nz//2])][:,:,0],6).tolist()}
 s.write_json(out/'display_fields.json',display)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True);ap.add_argument('--diagnostics',type=Path,required=True);ap.add_argument('--stationarity',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 rows=[json.loads(p.read_text()) for p in sorted(a.base.glob('grid_*/metrics.json'))];assert len(rows)>=3
 b=rows[:3];fine=b[-1];medium=b[-2];tol=s.PLAN['acceptance'];pressure_change=abs(fine['solved_pressure_gradient_Pa_m']/medium['solved_pressure_gradient_Pa_m']-1);tchange=abs((fine['outlet_mixed_temperature_K']-300)/(medium['outlet_mixed_temperature_K']-300)-1)
 gates={'all_meshes_quality_and_3d':all(r['mesh_ok'] and r['three_dimensions'] for r in b),'flow_residuals':max(v['initial'] for r in b for v in r['flow_residuals'].values())<=tol['maximum_flow_final_initial_residual'],'scalar_residuals':max(r[k]['T']['initial'] for r in b for k in ['thermal_residuals','analytic_residuals'])<=tol['maximum_scalar_final_initial_residual'],'mass_conservation':max(r['relative_mass_imbalance'] for r in b)<=tol['relative_mass_imbalance_max'],'energy_conservation':max(r['relative_energy_imbalance'] for r in b)<=tol['relative_total_thermal_flux_imbalance_max'],'fine_nominal_and_quadrature_velocity_error':max(fine['velocity_relative_L2_error_middle_half'],fine['nominal_mean_velocity_relative_L2_error_middle_half'])<=tol['fine_velocity_relative_L2_error_max'],'fine_nominal_and_quadrature_pressure_error':max(abs(fine['pressure_gradient_relative_error']),abs(fine['nominal_mean_pressure_gradient_relative_error']))<=tol['fine_pressure_gradient_relative_error_max'],'analytic_thermal_error':fine['analytic_thermal_relative_L2_error']<=tol['fine_analytic_scalar_relative_L2_error_max'],'analytic_thermal_error_decreases':all(b[i+1]['analytic_thermal_relative_L2_error']<b[i]['analytic_thermal_relative_L2_error'] for i in [0,1]),'medium_to_fine_temperature_rise_change':tchange<=tol['fine_to_medium_bulk_temperature_rise_relative_change_max'],'medium_to_fine_pressure_gradient_change':pressure_change<=tol['fine_to_medium_pressure_gradient_relative_change_max'],'maximum_principle':all(r['temperature_min_K']>=300-tol['main_temperature_range_slack_K'] and r['temperature_max_K']<=310+tol['main_temperature_range_slack_K'] for r in b)}
 ref=json.loads((a.base/'references.json').read_text());extra=None
 if len(rows)==4:
  f=rows[-1];change=abs(f['solved_pressure_gradient_Pa_m']/fine['solved_pressure_gradient_Pa_m']-1);extra={'grid':f['grid'],'pressure_relative_change_from_previous_fine':change,'second_order_equivalent_doubling_relative_change':change*16/3,'conditional_diagnostic_below_1_percent':change*16/3<=.01,'nominal_pressure_error_order_last_pair':math.log(abs(fine['nominal_mean_pressure_gradient_relative_error']/f['nominal_mean_pressure_gradient_relative_error']))/math.log(1.25),'nominal_velocity_error_order_last_pair':math.log(fine['nominal_mean_velocity_relative_L2_error_middle_half']/f['nominal_mean_velocity_relative_L2_error_middle_half'])/math.log(1.25),'thermal_sentinel_error_order_last_pair':math.log(fine['analytic_thermal_relative_L2_error']/f['analytic_thermal_relative_L2_error'])/math.log(1.25),'note':'Separate post-result evidence. Conditional second-order diagnostic is not a measured2x test, GCI, uncertainty bound or override of original failure.'}
 if extra is not None:
  f=rows[-1];prev=rows[-2]
  extra['gates']={'mesh_quality_and_3d':f['mesh_ok'] and f['three_dimensions'],'flow_residuals':max(x['initial'] for x in f['flow_residuals'].values())<=1e-7,'scalar_residuals':max(f[k]['T']['initial'] for k in ['thermal_residuals','analytic_residuals'])<=1e-9,'mass_conservation':f['relative_mass_imbalance']<=1e-7,'energy_conservation':f['relative_energy_imbalance']<=1e-6,'nominal_and_quadrature_velocity_accuracy':max(f['velocity_relative_L2_error_middle_half'],f['nominal_mean_velocity_relative_L2_error_middle_half'])<=.01,'nominal_and_quadrature_pressure_accuracy':max(abs(f['pressure_gradient_relative_error']),abs(f['nominal_mean_pressure_gradient_relative_error']))<=.01,'analytic_thermal_accuracy':f['analytic_thermal_relative_L2_error']<=.005,'all_analytic_errors_decreased':all(abs(f[k])<abs(prev[k]) for k in ['pressure_gradient_relative_error','nominal_mean_pressure_gradient_relative_error','velocity_relative_L2_error_middle_half','nominal_mean_velocity_relative_L2_error_middle_half','analytic_thermal_relative_L2_error']),'temperature_range':f['temperature_min_K']>=299.999 and f['temperature_max_K']<=310.001,'conditional_second_order_pressure_diagnostic':extra['conditional_diagnostic_below_1_percent']}
  extra['all_supplemental_gates_passed']=all(extra['gates'].values())
 last=rows[-1];report={'schema':'aerolab-real-3d-cooling-evidence-v1','status':'initial_preregistered_pressure_refinement_gate_failed_supplemental_evidence_separate','initial_all_passed':all(gates.values()),'physical_experimental_validation':None,'aircraft_applicability':'not_established','conjugate_solid_fluid':'not_solved','case_kind':'synthetic_true_3d_laminar_flow_with_passive_constant_property_heat','initial_gates':gates,'initial_pressure_refinement_relative_change':pressure_change,'initial_temperature_rise_refinement_relative_change':tchange,'additional_refinement':extra,'meshes':rows,'references':ref,'finest_to_galerkin_bulk_attenuation_relative_difference':last['outlet_bulk_theta']/ref['galerkin'][-1]['bulk_theta']-1,'finest_to_existing_fvm_bulk_attenuation_relative_difference':last['outlet_bulk_theta']/ref['finite_volume'][-1]['bulk_theta']-1,'outlet_sensitivity':json.loads((a.diagnostics/'outlet_sensitivity.json').read_text()),'stationarity':json.loads((a.stationarity/'stationarity.json').read_text()),'limitations':['Synthetic boundary-value problem, no experimental validation or aircraft prediction','Passive fluid temperature only; no conjugate solid or thermal feedback','Singular hot-wall/cold-inlet edges: total wall heat is not a converged physical quantity','Main Graetz references omit axial diffusion; agreement is not a same-PDE exact verification','Original pressure refinement criterion failed and is never relabeled as passed','Supplemental1.25x diagnostic assumes second-order pressure error; not a GCI or uncertainty bound'],'provenance':{'baseline_tree':s.PLAN['baseline_tree'],'plan_sha256':s.sha(s.HERE/'plan.json'),'supplemental_plan_sha256':s.sha(s.HERE/'supplemental_plan.json'),'additional_refinement_plan_sha256':s.sha(s.HERE/'additional_refinement_plan.json'),'solver_script_sha256':s.sha(s.HERE/'study.py'),'reference_script_sha256':s.sha(s.HERE/'references.py'),'tools_lock_sha256':s.sha(s.TOOLS/'packages.lock.json')}}
 s.write_json(a.output/'report.json',report);plots(a.base,a.output,rows)
 chinese=f'''# 真实三维冷却通道计算：局部数值验证

已实际打通参数化 Gmsh 建模、三维网格导入、网格检查、OpenFOAM 流动与被动传热、场数据后处理。

- 当前最细网格：{last['cells']:,} 个六面体单元，三个空间方向均求解，四面无滑移热壁
- 合成通道：30×4×2 mm；平均入口速度 3 m/s，入口 300 K、壁面 310 K；Re≈533
- 混合出口温度：{last['outlet_mixed_temperature_K']:.6f} K
- 压力梯度：{last['solved_pressure_gradient_Pa_m']:.6f} Pa/m；相对固定3 m/s解析解误差 {100*last['nominal_mean_pressure_gradient_relative_error']:.4f}%
- 速度场相对解析解 L2 误差：{100*last['nominal_mean_velocity_relative_L2_error_middle_half']:.4f}%
- 独立低速三维解析传热检验 L2 误差：{100*last['analytic_thermal_relative_L2_error']:.4f}%
- 与已有独立 Graetz 参考的出口衰减差：{100*report['finest_to_galerkin_bulk_attenuation_relative_difference']:.4f}%（方程假设不同，不能当同方程精确误差）

## 保留的失败

原三档网格的压力梯度变化为 {100*pressure_change:.6f}%，超过事先固定的1%门槛；原验证包没有全部通过。之后追加的1.25倍网格只作为独立补充证据，不能把较容易通过的相邻变化冒充原2倍加密通过。若使用二阶等效加密诊断，必须同时展示其假设和原失败。

## 能证明什么

这是可重跑的真实三维流体有限体积数值验证，能够检查求解链路、解析场误差、质量/热量守恒、迭代稳定性及网格敏感性。图像来自真实保存的 OpenFOAM 单元数据，不是生成式CFD图片。

## 不能证明什么

没有真实试验或飞机适用性验证，没有共轭固体导热，也没有绕组热点或实际器件温度预测。冷入口和热壁的交角存在数学奇异性，因此不把总壁面热量称为网格收敛的物理预测。当前研究保留原失败，尚未集成或发布到应用。
'''
 (s.HERE/'REPORT_ZH.md').write_text(chinese)
 # Store compact final log tails and mesh diagnostics; full fields/logs remain local.
 logs={}
 for i,r in enumerate(rows):
  case=a.base/f'grid_{i}';logs[str(i)]={'mesh_check':(case/'log.checkMesh').read_text(),'flow_last_lines':'\n'.join((case/'log.simpleFoam').read_text().splitlines()[-24:]),'thermal_last_lines':'\n'.join((case/'thermal/log.scalarTransportFoam').read_text().splitlines()[-14:]),'analytic_last_lines':'\n'.join((case/'analytic/log.scalarTransportFoam').read_text().splitlines()[-14:])}
 s.write_json(a.output/'solver_log_extracts.json',logs)
 source_records=[]
 for i in range(len(rows)):
  case=a.base/f'grid_{i}'
  selected=[case/'duct.geo',case/'duct.msh',case/'setup.json',case/'fields.npz',case/'metrics.json',case/'flow_run.json']
  selected+=list((case/'flow_final').glob('*'))
  for folder in [case,case/'thermal',case/'analytic']:
   for relative in ['system/controlDict','system/fvSchemes','system/fvSolution','constant/transportProperties','constant/turbulenceProperties','constant/polyMesh/points','constant/polyMesh/faces','constant/polyMesh/owner','constant/polyMesh/neighbour','constant/polyMesh/boundary']:
    selected.append(folder/relative)
   selected+=list(folder.glob('log.*'))
   selected+=list((folder/'0').glob('*'))
   if folder!=case:selected.append(s.latest(folder)/'T')
  for path in sorted(set(selected)):
   if path.is_file():source_records.append({'path':str(path.relative_to(a.base)),'bytes':path.stat().st_size,'sha256':s.sha(path)})
 s.write_json(a.output/'source_artifacts.json',{'purpose':'Integrity records for retained full-resolution inputs, generated mesh, solved fields and complete logs; these large artifacts are not distributed in the compact package','source_root_relative_to_repository':str(a.base.relative_to(s.REPO) if a.base.is_absolute() else a.base),'files':source_records})
 manifest={'schema':'aerolab-openfoam-3d-package-v1','publication':'Numerical research evidence; application integration is not included. See ../COOLING_RESEARCH_PUBLICATION.md for publication scope.','files':[]}
 for p in sorted(s.HERE.rglob('*')):
  if not p.is_file() or '__pycache__' in str(p) or p.name=='manifest.json':continue
  limit=250000 if p.suffix=='.png' else 100000
  if p.stat().st_size>=limit:raise ValueError(f'Package size limit: {p}')
  manifest['files'].append({'path':str(p.relative_to(s.REPO)),'bytes':p.stat().st_size,'sha256':s.sha(p)})
 s.write_json(a.output/'manifest.json',manifest);print(json.dumps({'initial_all_passed':report['initial_all_passed'],'initial_gates':gates,'additional_refinement':extra,'files':len(manifest['files'])},indent=2))
if __name__=='__main__':main()
