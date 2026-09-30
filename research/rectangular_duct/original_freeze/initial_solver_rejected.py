#!/usr/bin/env python3
"""Research-only conservative rectangular-duct Graetz calculation.

Coordinates x/H in [0,aspect], y/H in [0,1]; axial tau=alpha*z/(U*H^2).
The velocity is independent of temperature and axial position. All walls have
one common imposed temperature. No buoyancy, axial conduction or property
variation. SciPy/NumPy are research dependencies, not application dependencies.
"""
from __future__ import annotations
import argparse, hashlib, json, math, os, platform, sys, time
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).parent / '.mplconfig'))
import numpy as np
import scipy
from scipy.sparse import diags, eye, kron, csc_matrix
from scipy.sparse.linalg import splu

ROOT=Path(__file__).resolve().parent
MODEL='rectangular-isothermal-laminar-fv-v1'

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def provenance():
    return dict(model_id=MODEL, code_sha256=sha(__file__), plan_sha256=sha(ROOT/'numerical_plan.json'),
                python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__)
def save(path,obj):
    b=(json.dumps(obj,indent=2,allow_nan=False)+'\n').encode()
    if len(b)>=100000: raise ValueError(f'Compact evidence size limit exceeded: {path}: {len(b)}')
    Path(path).write_bytes(b)

def dirichlet_1d(n,h):
    d=np.full(n,2.0); d[[0,-1]]+=1
    return diags((-np.ones(n-1),d,-np.ones(n-1)),(-1,0,1),format='csc')/h**2

def exact_mean_velocity(aspect,terms=10000):
    """Exact separated-series solution for −laplacian(w)=1, H=1.
    <w>=[1−192/(pi^5 aspect) sum_odd tanh(n*pi*aspect/2)/n^5]/12.
    Direct separation-of-variables reference, independent of FV assembly.
    """
    n=np.arange(1,2*terms,2,dtype=float)
    return float((1-192/(np.pi**5*aspect)*np.sum(np.tanh(n*np.pi*aspect/2)/n**5))/12)

def exact_plug_bulk(tau,aspect,terms=2000):
    """Product of 1-D Dirichlet slab means for a uniform initial field."""
    if tau==0:return 1.0
    n=np.arange(1,2*terms,2,dtype=float)
    return float(64/np.pi**4*np.sum(np.exp(-np.pi**2*tau*n*n)/n**2)*np.sum(np.exp(-np.pi**2*tau*(n/aspect)**2)/n**2))

class Model:
    def __init__(self,ny=64,aspect=2.0,plug=False):
        self.ny=ny; self.nx=round(ny*aspect); self.aspect=aspect
        if not math.isclose(self.nx/ny,aspect):raise ValueError('Need square cells')
        self.h=1/ny; self.area=self.h**2; self.dh=2*aspect/(1+aspect)
        self.K=kron(eye(ny),dirichlet_1d(self.nx,self.h),format='csc')+kron(dirichlet_1d(ny,self.h),eye(self.nx),format='csc')
        self.raw=splu(self.K).solve(np.ones(self.nx*ny))
        self.mean=float(np.mean(self.raw))
        self.v=np.ones_like(self.raw) if plug else self.raw/self.mean
        self.mass=diags(self.v,format='csc'); self.mass_sum=float(self.v.sum())
        # K-column sums = outward wall conductance per cell area, exactly.
        self.wall=np.asarray(self.K.sum(axis=0)).ravel()
    def bulk(self,theta):return float(self.v@theta/self.mass_sum)
    def momentum_evidence(self):
        exact=exact_mean_velocity(self.aspect)
        return dict(aspect=self.aspect,nx=self.nx,ny=self.ny,mean_velocity=self.mean,
             exact_series_mean_velocity=exact,relative_mean_error=self.mean/exact-1,
             darcy_f_re=2*self.dh**2/self.mean,exact_darcy_f_re=2*self.dh**2/exact,
             forcing_residual_inf=float(np.max(np.abs(self.K@self.raw-1))),
             normalized_mass_flux=float(np.mean(self.v)),
             integrated_momentum_wall_balance_error=float(self.wall@self.raw/self.raw.size-1),
             minimum_velocity=float(self.v.min()),maximum_velocity=float(self.v.max()))
    def march(self,steps=512,last=.512,first=.001,sample_every=16,field_times=()):
        """BE steps on constant-step dyadic intervals; one sparse LU per interval.
        First [0,first] then [first,2first], etc. Halving dt doubles steps.
        No experimental measurements enter the equation or step placement.
        """
        theta=np.ones_like(self.v); tau=0.; heat=0.; max_res=0.; max_balance=0.
        minimum=1.; maximum=1.; max_increase=0.; curve=[dict(tau=0.,bulk_theta=1.)]
        endpoints=[];fields={};end=first
        while tau<last*(1-1e-12):
            end=min(end,last);dt=(end-tau)/steps
            A=self.mass+dt*self.K;lu=splu(csc_matrix(A))
            start=tau
            for i in range(1,steps+1):
                before=theta; rhs=self.v*before;theta=lu.solve(rhs)
                t=start+dt*i
                flux=float(self.wall@theta/self.mass_sum)
                heat+=dt*flux
                drop=float(self.v@(before-theta)/self.mass_sum)
                max_balance=max(max_balance,abs(drop-dt*flux))
                minimum=min(minimum,float(theta.min()));maximum=max(maximum,float(theta.max()))
                max_increase=max(max_increase,float(np.max(theta-before)))
                if i in (1,steps):
                    max_res=max(max_res,float(np.max(np.abs(A@theta-rhs)))/max(float(np.max(abs(rhs))),1e-300))
                if i%sample_every==0 or i==steps:
                    curve.append(dict(tau=float(t),bulk_theta=self.bulk(theta)))
            tau=end
            endpoints.append(dict(tau=float(tau),bulk_theta=self.bulk(theta),
                                  field_min=float(theta.min()),field_max=float(theta.max())))
            if any(math.isclose(tau,z,rel_tol=1e-10) for z in field_times):fields[str(tau)]=theta.reshape(self.ny,self.nx).copy()
            end*=2
        return dict(ny=self.ny,nx=self.nx,steps_per_interval=steps,
                    curve=curve,endpoints=endpoints,
                    checks=dict(inlet_bulk_theta=1.,minimum_field=minimum,maximum_field=maximum,
                      maximum_cellwise_axial_increase=max_increase,
                      maximum_linear_relative_residual=max_res,
                      maximum_step_energy_balance_abs=max_balance,
                      global_energy_closure_abs=abs(1-self.bulk(theta)-heat)),
                    fields=fields,last_field=theta)

def summary(run):return {k:v for k,v in run.items() if k not in ('fields','last_field','curve')}
def endpoint(run,t):return next(x['bulk_theta'] for x in run['endpoints'] if math.isclose(x['tau'],t))
def relative_diffs(coarse,fine,lo=.002,hi=.512):
    return [dict(tau=e['tau'],coarse_theta=e['bulk_theta'],fine_theta=endpoint(fine,e['tau']),relative_change=e['bulk_theta']/endpoint(fine,e['tau'])-1) for e in coarse['endpoints'] if lo<=e['tau']<=hi]

def verify():
    started=time.time();plan=json.loads((ROOT/'numerical_plan.json').read_text());tol=plan['acceptance']
    velocity=[]
    for aspect in (1.,2.,4.):
        for ny in (16,32,64,128):
            velocity.append(Model(ny,aspect).momentum_evidence())
    print('Momentum verification done',flush=True)
    meshes={}
    for ny in (16,32,64,128):
        print('Laminar space mesh',ny,flush=True)
        meshes[ny]=Model(ny).march(steps=512)
    times={512:meshes[64]}
    for steps in (256,1024):
        print('Laminar time refinement',steps,flush=True)
        times[steps]=Model(64).march(steps=steps)
    print('Plug-flow independent exact series test',flush=True)
    plug=Model(64,plug=True).march(steps=512,last=.128)
    plug_errors=[dict(tau=e['tau'],computed=e['bulk_theta'],exact=exact_plug_bulk(e['tau'],2.),relative_error=e['bulk_theta']/exact_plug_bulk(e['tau'],2.)-1) for e in plug['endpoints'] if e['tau']>=.002]
    print('Long duct limit',flush=True)
    long=Model(32).march(steps=128,last=8.)
    space_diffs=relative_diffs(meshes[64],meshes[128])
    time_diffs=relative_diffs(times[512],times[1024])
    orders=[]
    for e in meshes[64]['endpoints']:
        t=e['tau']
        if t<.002:continue
        q16,q32,q64,q128=[endpoint(meshes[n],t) for n in (16,32,64,128)]
        orders.append(dict(tau=t,coarse_order=math.log2(abs((q16-q32)/(q32-q64))),fine_order=math.log2(abs((q32-q64)/(q64-q128)))))
    checks=[x['checks'] for x in list(meshes.values())+list(times.values())+[plug,long]]
    gates=dict(
       velocity_exact_series=max(abs(x['relative_mean_error']) for x in velocity if x['ny']==64)<tol['exact_rectangular_series_mean_velocity_relative_error_max'],
       spatial_refinement=max(abs(x['relative_change']) for x in space_diffs)<tol['fine_grid_bulk_theta_relative_change_max_over_tau_0p002_to_0p512'],
       axial_refinement=max(abs(x['relative_change']) for x in time_diffs)<tol['fine_time_bulk_theta_relative_change_max_over_tau_0p002_to_0p512'],
       plug_flow_exact_series=max(abs(x['relative_error']) for x in plug_errors)<tol['plug_flow_exact_heat_series_bulk_theta_relative_error_max_over_tau_0p002_to_0p128'],
       energy_closure=max(x['global_energy_closure_abs'] for x in checks)<tol['normalized_global_energy_closure_abs_max'],
       momentum_residual=max(x['forcing_residual_inf'] for x in velocity)<tol['velocity_forcing_residual_inf_max'],
       linear_solve_residual=max(x['maximum_linear_relative_residual'] for x in checks)<tol['linear_solve_relative_residual_inf_max'],
       maximum_principle=all(x['minimum_field']>=-tol['maximum_principle_absolute_slack'] and x['maximum_field']<=1+tol['maximum_principle_absolute_slack'] and x['maximum_cellwise_axial_increase']<=tol['maximum_principle_absolute_slack'] for x in checks),
       inlet_limit=all(x['inlet_bulk_theta']==1 for x in checks),
       long_duct_limit=long['endpoints'][-1]['bulk_theta']<tol['long_duct_bulk_theta_at_tau_8_max'],
       spatial_order=min(x['fine_order'] for x in orders)>=tol['spatial_convergence_min_order_in_bulk_theta'])
    result=dict(provenance=provenance(),experiment_used_for_selection=False,
       gates=gates,all_passed=all(gates.values()),velocity=velocity,
       spatial_convergence=orders,production_to_doubled_grid=space_diffs,
       production_to_doubled_time=time_diffs,plug_flow_exact_series=plug_errors,
       thermal_mesh_runs={str(k):summary(v) for k,v in meshes.items()},
       thermal_time_runs={str(k):summary(v) for k,v in times.items()},long_duct=summary(long),
       elapsed_seconds=time.time()-started)
    save(ROOT/'verification.json',result)
    print(json.dumps(dict(gates=gates,elapsed_seconds=result['elapsed_seconds']),indent=2),flush=True)
    return result

def curve():
    verification=json.loads((ROOT/'verification.json').read_text())
    if not verification['all_passed']:raise ValueError('Mathematical gates not passed; cannot freeze')
    if verification['provenance']['code_sha256']!=sha(__file__):raise ValueError('Code changed since verification')
    m=Model(64);run=m.march(steps=512,field_times=(.001,.016,.032,.064,.256,.512))
    c=[dict(tau=p['tau'],Gz_Dh=None if p['tau']==0 else m.dh**2/p['tau'],bulk_theta=p['bulk_theta']) for p in run['curve']]
    freeze=dict(provenance=provenance(),verification_sha256=sha(ROOT/'verification.json'),
       all_mathematical_gates_passed=True,experiment_used_for_selection=False,
       ny=64,nx=128,steps_per_doubling_interval=512,first_interval_end_tau=.001,
       tau_min_comparison=.002,tau_max_comparison=.512,
       curve=c,checks=run['checks'],momentum=m.momentum_evidence())
    save(ROOT/'frozen_response.json',freeze)
    np.savez_compressed(ROOT/'cross_section_fields.npz',velocity=m.v.reshape(m.ny,m.nx),
             x=(np.arange(m.nx)+.5)*m.h,y=(np.arange(m.ny)+.5)*m.h,
             **{f'theta_tau_{k}':v for k,v in run['fields'].items()})
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(1,3,figsize=(12,3.6),layout='constrained')
    for ax,key,title in [(axs[0],'v','Velocity / mean'),(axs[1],'0.032','Theta at tau=0.032'),(axs[2],'0.064','Theta at tau=0.064')]:
        a=m.v.reshape(m.ny,m.nx) if key=='v' else run['fields'][key]
        im=ax.imshow(a,origin='lower',extent=[0,2,0,1],aspect='equal');ax.set(title=title,xlabel='x/H',ylabel='y/H');fig.colorbar(im,ax=ax,shrink=.7)
    fig.savefig(ROOT/'cross_section_fields.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(6.5,4.2),layout='constrained')
    nonzero=c[1:];ax.semilogx([p['Gz_Dh'] for p in nonzero],[p['bulk_theta'] for p in nonzero]);ax.set(xlabel='Gz = Re Pr Dh / L',ylabel='Mixed outlet theta = (Tw − Tout) / (Tw − Tin)',title='Untuned aspect-2 laminar rectangular response',ylim=(0,1));ax.grid(alpha=.25)
    fig.savefig(ROOT/'frozen_response.png',dpi=160);plt.close(fig)
    print('Frozen mathematical response saved; no experiment discrepancy computed',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['verify','curve']);a=p.parse_args()
    if a.command=='verify':verify()
    else:curve()
