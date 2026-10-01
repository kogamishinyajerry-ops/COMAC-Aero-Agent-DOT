#!/usr/bin/env python3
"""Declared synthetic pressure-driven conjugate-fin screen, SI; no fitted h.
The original benchmark is imported read-only for its conservative primitives.
"""
from __future__ import annotations
import sys, pathlib, importlib.util, json, math, hashlib, time
sys.dont_write_bytecode=True
import numpy as np
from scipy.sparse import diags
from scipy.sparse.linalg import splu, spsolve
HERE=pathlib.Path(__file__).resolve().parent
SOURCE=HERE.parent/'fin-study'/'conjugate_fin.py'
spec=importlib.util.spec_from_file_location('original_conjugate_fin',SOURCE)
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
Assembler=base.Assembler; poisson=base.poisson; exact_poisson_mean=base.exact_poisson_mean
B=.0415; D=.0452; H=.0113; L=.09; RHO=1.204; CP=1007.; KA=.02514; NU=1.516e-5; MU=RHO*NU

def digest(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def save(name,j):
    p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True); s=json.dumps(j,indent=2,allow_nan=False,default=lambda x:x.item() if isinstance(x,np.generic) else (_ for _ in ()).throw(TypeError(type(x).__name__)))+'\n'
    if p.suffix=='.json' and len(s.encode())>=100000:raise ValueError(f'oversize JSON: {name}')
    p.write_text(s)

def case_list():return [('nominal',25.,()),('pressure_loss',15.,()),('asymmetric_blockage',25.,(1,)),('combined_fault',15.,(1,))]

class PressureFin:
    def __init__(self,N=16,t=.00086,nx=48,ny=144,ks=205.,ka=KA,heatcap=RHO*CP,mu=MU,profile='fd',grounded=True,isothermal=False):
        if N<2 or nx<2 or ny<2 or t<=0 or N*t>=B:raise ValueError('invalid geometry or grid')
        if min(ks,ka,heatcap,mu)<=0 or profile not in ('fd','plug'):raise ValueError('invalid physics')
        self.N=N;self.t=t;self.nx=nx;self.ny=ny;self.ks=ks;self.ka=ka;self.heatcap=heatcap;self.mu=mu;self.profile=profile;self.isothermal=isothermal
        self.gap=(B-N*t)/(N-1); self.dy=H/ny;self.channels=[];self.velocity_checks=[];count=0; cache={}
        for i,w in enumerate([(D-B)/2]+[self.gap]*(N-1)+[(D-B)/2]):
            ids=np.arange(count,count+nx*ny).reshape(ny,nx);count+=nx*ny
            if w not in cache:cache[w]=poisson(nx,ny,w,H)
            shape,ch=cache[w];self.velocity_checks.append(dict(ch,channel=i))
            c={'ids':ids,'width':w,'dx':w/nx,'side':i in (0,N),'shape':shape if profile=='fd' else np.ones_like(shape),'wmean':ch['mean_m2']}
            self.channels.append(c)
        self.nfluid=count;self.fins=[] if isothermal else [np.arange(count+i*ny,count+(i+1)*ny) for i in range(N)]
        self.n=count+N*ny*(not isothermal); a=Assembler(self.n);self.floor=np.zeros(self.n);self.root=np.zeros(self.n)
        def ground(ids,g,owner):a.ground(ids,g);np.add.at(owner,np.asarray(ids).ravel(),np.broadcast_to(g,np.asarray(ids).shape).ravel())
        for ch,c in enumerate(self.channels):
            ids=c['ids'];dx=c['dx'];dy=self.dy
            a.connect(ids[:,:-1],ids[:,1:],ka*dy/dx);a.connect(ids[:-1,:],ids[1:,:],ka*dx/dy)
            if grounded and not c['side']:ground(ids[0,:],2*ka*dx/dy,self.floor)
            for f,face in ([(ch-1,ids[:,0])] if ch>0 else [])+([(ch,ids[:,-1])] if ch<N else []):
                if isothermal:
                    if grounded:ground(face,2*ka*dy/dx,self.root)
                else:a.connect(face,self.fins[f],dy/(dx/(2*ka)+t/(2*ks)))
        for ids in self.fins:
            a.connect(ids[:-1],ids[1:],ks*t/self.dy)
            if grounded:ground(ids[0],2*ks*t/self.dy,self.root)
        self.K=a.matrix();self.bound=a.bound
    def hydraulic(self,pressure,blocked=()):
        if pressure<=0 or any(i<0 or i>self.N for i in blocked):raise ValueError('invalid pressure or branch')
        rows=[]
        for i,c in enumerate(self.channels):
            u=0. if i in blocked else pressure*c['wmean']/(self.mu*L)
            q=u*c['width']*H; dh=2*c['width']*H/(c['width']+H)
            exact=pressure*exact_poisson_mean(c['width'],H)/(self.mu*L)*c['width']*H if i not in blocked else 0.
            rows.append({'channel':i,'side':c['side'],'blocked':i in blocked,'gap_mm':c['width']*1000,'mean_speed_m_s':u,'volume_flow_m3_s':q,'mass_flow_kg_s':q*RHO,'Re_Dh':u*dh/(self.mu/RHO),'hydraulic_conductance_m3_s_Pa':q/pressure,'flow_relative_to_exact':q/exact-1 if exact else 0.})
        total=sum(r['volume_flow_m3_s'] for r in rows)
        for r in rows:r['flow_fraction']=r['volume_flow_m3_s']/total
        return rows
    def solve(self,pressure=25.,blocked=(),nz=800,details=False):
        ts=time.monotonic(); hydraulic=self.hydraulic(pressure,blocked);mass=np.zeros(self.n)
        for c,r in zip(self.channels,hydraulic):mass[c['ids']]=(self.heatcap*r['mean_speed_m_s']*c['shape']*c['dx']*self.dy)
        dz=L/nz;adv=mass/dz;A=self.K+diags(adv,format='csc');lu=splu(A);absA=abs(A)
        theta=np.ones(self.n);qsum=0.;err=0.;tmin=1.;tmax=1.;componentwise=0.
        for step in range(nz):
            rhs=adv*theta;theta=lu.solve(rhs);qsum+=dz*float(self.bound@theta)
            ent=float(mass@(1-theta));err=max(err,abs(qsum-ent)/max(abs(ent),1e-30));tmin=min(tmin,float(theta.min()));tmax=max(tmax,float(theta.max()))
            if step in (0,nz//2,nz-1):componentwise=max(componentwise,float(np.max(abs(A@theta-rhs)/np.maximum(absA@abs(theta)+abs(rhs),1e-20))))
        G=float(mass@(1-theta));capacity=float(mass.sum());totalq=sum(r['volume_flow_m3_s'] for r in hydraulic)
        out={'N_fins':self.N,'thickness_mm':self.t*1000,'interior_gap_mm':self.gap*1000,'fin_only_mass_kg':2700*self.N*self.t*H*L,'pressure_Pa':pressure,'blocked_channels':list(blocked),'G_W_K':G,'Rth_K_W':1/G if G>0 else None,'capacity_rate_W_K':capacity,'effectiveness':G/capacity,'volume_flow_m3_s':totalq,'mass_flow_kg_s':totalq*RHO,'max_Re_Dh':max(r['Re_Dh'] for r in hydraulic),'laminar_scope':max(r['Re_Dh'] for r in hydraulic)<2300,'pressure_dissipation_W':pressure*totalq,'energy_relative_balance_max':err,'integrated_base_heat_W_K':qsum,'componentwise_thermal_equation_residual_relative':componentwise,'min_normalized_T':1-tmax,'max_normalized_T':1-tmin,'mass_transport_closure_relative':abs(capacity/self.heatcap-totalq)/totalq,'pressure_closure_relative':max(abs(r['volume_flow_m3_s']/r['hydraulic_conductance_m3_s_Pa']-pressure)/pressure for r in hydraulic if not r['blocked']),'max_poisson_relative_residual':max(r['relative_residual'] for r in self.velocity_checks),'max_poisson_force_balance_relative':max(r['force_balance_relative'] for r in self.velocity_checks),'max_hydraulic_flow_exact_relative_error':max(abs(r['flow_relative_to_exact']) for r in hydraulic),'geometry_width_closure_m':abs(self.N*self.t+sum(c['width'] for c in self.channels)-D),'mesh':{'nx':self.nx,'ny':self.ny,'nz':nz,'unknowns':self.n},'profile':self.profile,'ks_W_m_K':self.ks,'ka_W_m_K':self.ka,'heatcap_J_m3_K':self.heatcap,'mu_Pa_s':self.mu,'elapsed_s':time.monotonic()-ts}
        if details:
            out['channels']=[dict(r,heat_transport_W_K=float(np.sum(mass[c['ids']]*(1-theta[c['ids']])))) for r,c in zip(hydraulic,self.channels)]
            ys=np.unique(np.linspace(0,self.ny-1,9,dtype=int));out['outlet_fin_profiles']=[{'fin_index':i,'y_mm':((ys+.5)*self.dy*1000).tolist(),'normalized_T':(1-theta[ids[ys]]).tolist()} for i,ids in enumerate(self.fins)]
        return out

def thermal_gates(r):
    gates={'energy':r['energy_relative_balance_max']<1e-8,'componentwise_residual':r['componentwise_thermal_equation_residual_relative']<1e-8,'maximum_principle':r['min_normalized_T']>=-1e-9 and r['max_normalized_T']<=1+1e-9,'capacity_upper_bound':r['G_W_K']<=r['capacity_rate_W_K']*(1+1e-9),'mass':r['mass_transport_closure_relative']<1e-12,'pressure':r['pressure_closure_relative']<1e-12,'momentum':r['max_poisson_force_balance_relative']<1e-9 and r['max_poisson_relative_residual']<1e-9,'hydraulic_exact':r['max_hydraulic_flow_exact_relative_error']<.002,'geometry':r['geometry_width_closure_m']<1e-14}
    return {k:bool(v) for k,v in gates.items()}

def oneD(length,alpha_z_u):
    n=np.arange(1,10000,2,dtype=float);return float(np.sum(8/(np.pi*n)**2*np.exp(-alpha_z_u*(n*np.pi/(2*length))**2)))
def analytic_isothermal_plug(m,pressure=25.):
    total=0.
    for c,r in zip(m.channels,m.hydraulic(pressure)):
        u=r['mean_speed_m_s']; a=m.ka/m.heatcap*L/u
        deficit=oneD(c['width'],a) if c['side'] else oneD(c['width']/2,a)*oneD(H,a)
        total+=m.heatcap*r['volume_flow_m3_s']*(1-deficit)
    return total

if __name__=='__main__':
    m=PressureFin();print(json.dumps(m.solve(details=True),indent=2))
