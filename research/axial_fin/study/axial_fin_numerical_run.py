#!/usr/bin/env python3
"""Axial-fin-only extension of the immutable accepted FV cross-section model."""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,pathlib,resource,sys,time
sys.dont_write_bytecode=True
import numpy as np
from scipy.sparse import diags,eye,kron
from scipy.sparse.linalg import LinearOperator,gmres,splu
HERE=pathlib.Path(__file__).resolve().parent; ROOT=HERE.parents[2]
CORE=ROOT/'research/plate_fin/conjugate_fin.py'
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
EXPECTED_CORE='bdf9998a7f20cdd5d75fef2f5f0e49c9344ebc1e6f31a5ac955bff366d6c9d4c'
if sha(CORE)!=EXPECTED_CORE:raise RuntimeError('Accepted physical core identity changed')
spec=importlib.util.spec_from_file_location('accepted_plate_fin_core',CORE);base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
class ResourceLimit(RuntimeError):pass

def axial_graph(nz,ns,g):
    degree=np.full(nz,2.);degree[0]=degree[-1]=1.
    line=diags([-np.ones(nz-1),degree,-np.ones(nz-1)],[-1,0,1],format='csc')
    return kron(line,eye(ns,format='csc'),format='csc')*g

class AxialModel:
    def __init__(self,nx=12,ny=36,nz=120,speed=4.,lambda_z=1.,ks=205.,profile='fd',full=False,nfins=16,grounded=True,wall_seconds=300.,max_sweeps=350,rtol=1e-10,atol=1e-12):
        self.start=time.monotonic();self.limit_seconds=wall_seconds;self.max_sweeps=max_sweeps;self.sweeps=0
        if not (0<rtol<=1e-10 and 0<=atol<=1e-12):raise ValueError('Only baseline or stricter tolerances are permitted')
        self.rtol=rtol;self.atol=atol
        if nz<2 or not np.isfinite(lambda_z) or lambda_z<0:raise ValueError('nz>=2 and nonnegative finite axial multiplier required')
        self.model=base.Model(nx,ny,ks=ks,profile=profile,full=full,nfins=nfins,grounded=grounded)
        self.nx=nx;self.ny=ny;self.nz=nz;self.speed=speed;self.lambda_z=lambda_z;self.ks=ks;self.profile=profile;self.full=full;self.nfins=nfins;self.grounded=grounded
        m=self.model;self.nf=m.nfluid;self.ns=m.n-self.nf;self.dz=base.L/nz;self.mass=m.mass_unit[:self.nf]*speed;self.D=self.mass/self.dz
        self.Kff=m.K[:self.nf,:self.nf].tocsc();self.Kfs=m.K[:self.nf,self.nf:].tocsc();self.Ksf=m.K[self.nf:,:self.nf].tocsc();self.Kss=m.K[self.nf:,self.nf:].tocsc()
        estimate=(self.ns*nz*8*45+self.nf*8*20+self.ns*nz*8*60)
        if estimate>1.2*1024**3:raise ResourceLimit('Conservative work-array estimate exceeds1.2GiB before factorization')
        self.A=self.Kff+diags(self.D,format='csc');self.fluid_lu=splu(self.A)
        self.gz=lambda_z*ks*base.T*m.dy/self.dz**2
        self.Z=axial_graph(nz,self.ns,self.gz);self.P=kron(eye(nz,format='csc'),self.Kss,format='csc')+self.Z
        self.solid_lu=splu(self.P);self.factorization_seconds=time.monotonic()-self.start
        self.bf=m.base_floor_g[:self.nf];self.bs=m.fin_root_g[self.nf:];self.check_resources()
    def check_resources(self):
        if time.monotonic()-self.start>self.limit_seconds:raise ResourceLimit('Per-case wall limit reached')
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>1.5*1024**3:raise ResourceLimit('Observed process peak RSS exceeds1.5GiB')
        if self.sweeps>self.max_sweeps:raise ResourceLimit('Fluid-sweep limit reached')
    def accepted_baseline(self):
        m=self.model;mass=m.mass_unit*self.speed;lu=splu(m.K+diags(mass/self.dz,format='csc'));state=np.ones(m.n);solid=np.empty((self.nz,self.ns))
        for i in range(self.nz):state=lu.solve(mass/self.dz*state);solid[i]=state[self.nf:]
        return solid, m.factor*float(self.mass@(1-state[:self.nf]))
    def fluid_coupling(self,solid,inlet=0.):
        self.sweeps+=1;self.check_resources();solid=np.asarray(solid).reshape(self.nz,self.ns);out=np.empty_like(solid);prev=np.full(self.nf,inlet)
        for i in range(self.nz):
            prev=self.fluid_lu.solve(self.D*prev-self.Kfs@solid[i]);out[i]=self.Ksf@prev
            if i%32==0:self.check_resources()
        return out.ravel()
    def matvec(self,solid):return self.P@solid+self.fluid_coupling(solid,0.)
    def solve(self,include_samples=True):
        s0,G0=self.accepted_baseline();rhs=-self.fluid_coupling(np.zeros(self.ns*self.nz),1.)
        A=LinearOperator((len(rhs),len(rhs)),matvec=self.matvec,dtype=float);M=LinearOperator(A.shape,matvec=self.solid_lu.solve,dtype=float);history=[]
        sol,info=gmres(A,rhs,x0=s0.ravel(),M=M,rtol=self.rtol,atol=self.atol,restart=30,maxiter=10,callback=lambda r:history.append(float(r)),callback_type='pr_norm')
        if info!=0:raise ResourceLimit(f'GMRES did not converge, info={info}, last residual={history[-1] if history else None}')
        true_res=self.matvec(sol)-rhs;self.solid=sol.reshape(self.nz,self.ns)
        result=self.assess(self.solid)
        result.update({'status':'computed_pending_verification','lambda_z':self.lambda_z,'V_interior_m_s':self.speed,'ks_W_m_K':self.ks,'profile':self.profile,'full_array':self.full,'geometry_fin_count':self.nfins,'grounded':self.grounded,'baseline_same_mesh_G_W_K':G0,'paired_relative_conductance_change':result['G_W_K']/G0-1 if abs(G0)>1e-12 else None,'zero_recovery_solid_max_absolute_difference':float(np.max(abs(self.solid-s0))) if self.lambda_z==0 else None,'true_schur_relative_residual':float(np.linalg.norm(true_res)/max(np.linalg.norm(rhs),1e-30)),'linear_solver_tolerance':{'rtol':self.rtol,'atol':self.atol},'GMRES_inner_iterations':len(history),'fluid_sweeps':self.sweeps,'factorization_seconds':self.factorization_seconds,'elapsed_seconds':time.monotonic()-self.start,'process_peak_RSS_MiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,'mesh':{'gap_cells':self.nx,'height_cells':self.ny,'axial_slabs':self.nz,'fluid_unknowns_per_slice':self.nf,'solid_global_unknowns':self.ns*self.nz,'equivalent_global_fluid_solid_unknowns':self.model.n*self.nz},'provenance':{'core_sha256':sha(CORE),'axial_code_sha256':sha(__file__),'plan_sha256':sha(HERE/'PLAN.md')},'physical_validation_pass':None,'aircraft_transfer_authorized':False})
        if include_samples:result['samples']=self.samples()
        self.result=result;return result
    def assess(self,solid):
        prev=np.ones(self.nf);base_heat=0.;smin=float(solid.min());smax=float(solid.max());min_theta=smin;max_theta=smax;max_backward=0.;zterm=(self.Z@solid.ravel()).reshape(self.nz,self.ns)
        pscale=(abs(self.P)@abs(solid.ravel())).reshape(self.nz,self.ns)
        for i in range(self.nz):
            fluid=self.fluid_lu.solve(self.D*prev-self.Kfs@solid[i]);rf=self.A@fluid-self.D*prev+self.Kfs@solid[i];rs=self.Kss@solid[i]+zterm[i]+self.Ksf@fluid
            scale_f=abs(self.A)@abs(fluid)+abs(self.D*prev)+abs(self.Kfs)@abs(solid[i]);scale_s=pscale[i]+abs(self.Ksf)@abs(fluid)
            max_backward=max(max_backward,float(np.max(abs(rf)/np.maximum(scale_f,1e-30))),float(np.max(abs(rs)/np.maximum(scale_s,1e-30))))
            base_heat+=self.dz*(self.bf@fluid+self.bs@solid[i]);min_theta=min(min_theta,float(fluid.min()));max_theta=max(max_theta,float(fluid.max()));prev=fluid
        self.fluid_outlet=prev;G=self.model.factor*float(self.mass@(1-prev));root=self.model.factor*base_heat
        qz=self.model.factor*self.lambda_z*self.ks*base.T*self.model.dy/self.dz*np.sum(np.diff(solid,axis=0),axis=1)
        return {'G_W_K':G,'Rth_K_W':1/G if G>1e-12 else None,'integrated_base_heat_W_K':root,'energy_relative_balance':abs(root-G)/max(abs(G),1e-12),'energy_absolute_balance_W_K':abs(root-G),'componentwise_backward_error_max':max_backward,'minimum_normalized_temperature':1-max_theta,'maximum_normalized_temperature':1-min_theta,'net_internal_axial_heat_W_K':self.model.factor*self.dz*float(zterm.sum()),'imposed_external_axial_end_heat_W_K':[0.,0.],'maximum_absolute_net_axial_heat_across_internal_section_W_K':float(max(abs(qz),default=0.))}
    def samples(self):
        yi=np.unique(np.linspace(0,self.ny-1,9,dtype=int));zi=np.unique(np.linspace(0,self.nz-1,7,dtype=int));fins=[]
        for fi in [0,len(self.model.fins)-1]:
            ids=np.arange(fi*self.ny,(fi+1)*self.ny);fins.append({'fin_index_from_side':fi,'normalized_T':(1-self.solid[np.ix_(zi,ids[yi])]).tolist()})
        combined=np.r_[self.fluid_outlet,self.solid[-1]];fluid=self.model.sample(combined,base.L)['channels']
        return {'normalization':'(T-Tin)/(Tb-Tin)','solid_z_slab_centres_m':((zi+.5)*self.dz).tolist(),'solid_y_cell_centres_m':((yi+.5)*self.model.dy).tolist(),'fins':fins,'fluid_outgoing_face_z_m':base.L,'fluid_outlet_is_first_order_upwind_face_state':True,'fluid_outlet_channels':fluid,'central_channel_notice':'Last sampled fluid channel is half a physical interior channel; its right boundary is symmetry, not a wall.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--nx',type=int,default=12);p.add_argument('--ny',type=int,default=36);p.add_argument('--nz',type=int,default=120);p.add_argument('--speed',type=float,default=4.);p.add_argument('--lambda-z',type=float,default=1.);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
    try:r=AxialModel(a.nx,a.ny,a.nz,a.speed,a.lambda_z).solve()
    except ResourceLimit as e:r={'status':'resource_or_iterative_limit','message':str(e),'case':vars(a)|{'output':str(a.output)},'axial_code_sha256':sha(__file__),'physical_validation_pass':None}
    a.output.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');print({k:v for k,v in r.items() if k!='samples'});assert a.output.stat().st_size<100000
if __name__=='__main__':main()
