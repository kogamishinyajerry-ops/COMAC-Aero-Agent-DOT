#!/usr/bin/env python3
"""Research-only conservative conjugate fin/channel model; no fitted correlations.

17 channels are solved on a mirror half-domain (8.5 channels, 8 fins).
The fully developed velocity is a rectangular Poisson solution; plug is a
separate declared model form. Neither is hydrodynamic entrance development.
Units are SI. Temperature unknowns are theta=(Tb-T)/(Tb-Tin).
"""
from __future__ import annotations
import argparse, hashlib, json, math, pathlib, time
import numpy as np
from scipy.sparse import coo_matrix, diags
from scipy.sparse.linalg import splu

HERE=pathlib.Path(__file__).resolve().parent
H=.0113; T=.00086; L=.09; WI=(.0415-16*T)/15; WS=(.0452-.0415)/2
RHO=1.204; CP=1007.; KA=.02514; NU=1.516e-5

def digest(path): return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
def exact_poisson_mean(width,height):
    a,b=sorted((width,height)); odd=np.arange(1,4000,2,dtype=float)
    return a*a/12*(1-192*a/(np.pi**5*b)*np.sum(np.tanh(odd*np.pi*b/(2*a))/odd**5))

class Assembler:
    def __init__(self,n): self.n=n; self.rows=[]; self.cols=[]; self.vals=[]; self.bound=np.zeros(n)
    def connect(self,a,b,g):
        a,b,g=np.broadcast_arrays(np.asarray(a),np.asarray(b),np.asarray(g)); a=a.ravel(); b=b.ravel(); g=g.ravel()
        self.rows.extend([a,a,b,b]); self.cols.extend([a,b,a,b]); self.vals.extend([g,-g,-g,g])
    def ground(self,a,g):
        a,g=np.broadcast_arrays(np.asarray(a),np.asarray(g)); a=a.ravel(); g=g.ravel()
        self.rows.append(a); self.cols.append(a); self.vals.append(g); np.add.at(self.bound,a,g)
    def matrix(self):
        return coo_matrix((np.concatenate(self.vals),(np.concatenate(self.rows),np.concatenate(self.cols))),shape=(self.n,self.n)).tocsc()

def poisson(nx,ny,width,height,sym_right=False):
    dx=width/nx; dy=height/ny; ids=np.arange(nx*ny).reshape(ny,nx)
    a=Assembler(nx*ny)
    a.connect(ids[:,:-1],ids[:,1:],dy/dx); a.connect(ids[:-1,:],ids[1:,:],dx/dy)
    a.ground(ids[:,0],2*dy/dx)
    if not sym_right: a.ground(ids[:,-1],2*dy/dx)
    a.ground(ids[0,:],2*dx/dy); a.ground(ids[-1,:],2*dx/dy)
    K=a.matrix(); source=np.full(nx*ny,dx*dy); raw=splu(K).solve(source)
    mean=float(raw.mean()); exact=exact_poisson_mean(width*(2 if sym_right else 1),height)
    checks={'mean_m2':mean,'exact_mean_m2':exact,'mean_relative_error':mean/exact-1,
            'relative_residual':float(np.linalg.norm(K@raw-source,np.inf)/np.linalg.norm(source,np.inf)),
            'force_balance_relative':float(abs(a.bound@raw-source.sum())/source.sum()),'min_raw_m2':float(raw.min())}
    return (raw/mean).reshape(ny,nx),checks

class Model:
    def __init__(self,nx=12,ny=72,ks=205.,ka=KA,heatcap=RHO*CP,profile='fd',full=False,nfins=16,grounded=True,isothermal=False):
        if nx<2 or ny<2 or nx%2: raise ValueError('nx even >=2; ny>=2')
        if nfins<2 or nfins%2: raise ValueError('nfins must be positive even >=2')
        if min(ks,ka,heatcap)<=0: raise ValueError('positive conductivities and heat capacity required')
        if profile not in ('fd','plug'): raise ValueError(profile)
        self.nx=nx; self.ny=ny; self.ks=ks; self.ka=ka; self.heatcap=heatcap; self.profile=profile; self.full=full; self.nfins=nfins; self.dy=H/ny; self.factor=1 if full else 2
        # For generic verification nfins, keep the same physical channel widths.
        nfin= nfins if full else nfins//2
        widths=([WS]+[WI]*(nfins-1)+[WS]) if full else ([WS]+[WI]*(nfin-1)+[WI/2])
        nxs=[nx]*len(widths)
        if not full: nxs[-1]=nx//2
        self.channels=[]; count=0; self.velocity_checks=[]
        velocity_cache={}
        for ch,(width,nxx) in enumerate(zip(widths,nxs)):
            sym=(not full and ch==len(widths)-1)
            ids=np.arange(count,count+nxx*ny).reshape(ny,nxx); count+=nxx*ny
            is_side= ch==0 or (full and ch==len(widths)-1)
            speedfactor=WI/(width*(2 if sym else 1))
            key=(width,nxx,sym)
            if key not in velocity_cache: velocity_cache[key]=poisson(nxx,ny,width,H,sym)
            v,check=velocity_cache[key]
            self.velocity_checks.append(dict(check,channel=ch,symmetry_plane=sym))
            self.channels.append({'ids':ids,'width':width,'dx':width/nxx,'side':is_side,'sym':sym,'v':v if profile=='fd' else np.ones_like(v),'speedfactor':speedfactor})
        self.nfluid=count
        self.fins=[] if isothermal else [np.arange(count+i*ny,count+(i+1)*ny) for i in range(nfin)]
        self.n=count+len(self.fins)*ny; a=Assembler(self.n); self.mass_unit=np.zeros(self.n)
        self.base_floor_g=np.zeros(self.n); self.fin_root_g=np.zeros(self.n); self.fin_surface_ground_g=np.zeros(self.n)
        def ground(ids,g,owner):
            a.ground(ids,g); np.add.at(owner,np.asarray(ids).ravel(),np.broadcast_to(g,np.asarray(ids).shape).ravel())
        for ch,c in enumerate(self.channels):
            ids=c['ids']; dx=c['dx']; dy=self.dy
            a.connect(ids[:,:-1],ids[:,1:],ka*dy/dx); a.connect(ids[:-1,:],ids[1:,:],ka*dx/dy)
            self.mass_unit[ids.ravel()]=(heatcap*c['v']*c['speedfactor']*dx*dy).ravel()
            if grounded and not c['side']: ground(ids[0,:],2*ka*dx/dy,self.base_floor_g)
            # left wall is fin ch-1 unless the channel touches the left duct.
            # right wall is fin ch unless right duct or centre symmetry.
            for fin_id,fluid_ids in ([(ch-1,ids[:,0])] if ch>0 else [])+ ([(ch,ids[:,-1])] if ch<nfin else []):
                if isothermal:
                    if grounded: ground(fluid_ids,2*ka*dy/dx,self.fin_surface_ground_g)
                else: a.connect(fluid_ids,self.fins[fin_id],dy/(dx/(2*ka)+T/(2*ks)))
        for ids in self.fins:
            a.connect(ids[:-1],ids[1:],ks*T/self.dy)
            if grounded: ground(ids[0],2*ks*T/self.dy,self.fin_root_g)
        self.K=a.matrix(); self.bound=a.bound; self.isothermal=isothermal
        self.channel_mass_unit=[float(self.mass_unit[c['ids']].sum()) for c in self.channels]

    def solve(self,speed,nz=400,length=L,samples=False,method='be'):
        if speed<=0 or nz<1 or length<=0: raise ValueError('positive speed,length,nz required')
        dz=length/nz; mass=self.mass_unit*speed
        # Solid inlet is algebraic; initial values do not affect backward Euler because solid mass is zero.
        theta=np.ones(self.n); theta_old=None
        be=splu(self.K+diags(mass/dz,format='csc'))
        bdf=splu(self.K+diags(1.5*mass/dz,format='csc')) if method=='bdf2' else None
        qsum=0.; qsumold=0.; min_theta=1.; max_theta=1.; maxbalance=0.; records=[]; qroot_last=0.
        sample_steps=set([1,max(1,nz//10),max(1,nz//2),nz])
        for step in range(1,nz+1):
            prev=theta
            if method=='bdf2' and step>1:
                theta=bdf.solve(mass/dz*(2*prev-.5*theta_old))
            else: theta=be.solve(mass/dz*prev)
            qroot=float(self.bound@theta)
            if method=='bdf2' and step>1: qnew=(4*qsum-qsumold+2*dz*qroot)/3
            else: qnew=qsum+dz*qroot
            qsumold,qsum=qsum,qnew; theta_old=prev
            enthalpy=float(mass@(1-theta)); maxbalance=max(maxbalance,abs(qsum-enthalpy)/max(enthalpy,1e-30))
            min_theta=min(min_theta,float(theta.min())); max_theta=max(max_theta,float(theta.max()))
            if samples and step in sample_steps:
                records.append(self.sample(theta,z_m=step*dz))
            qroot_last=qroot
        G=self.factor*float(mass@(1-theta)); capacity=self.factor*float(mass.sum())
        channel_G=[self.factor*float(mass[c['ids']]@(1-theta[c['ids']]).flatten()) if False else self.factor*float(np.sum(mass[c['ids']]*(1-theta[c['ids']]))) for c in self.channels]
        return {'V_interior_m_s':speed,'Re_Dh':speed*(2*WI*H/(WI+H))/NU,'G_W_K':G,'Rth_K_W':1/G if G>0 else None,
                'capacity_rate_W_K':capacity,'effectiveness':G/capacity,'energy_relative_balance_max':maxbalance,
                'integrated_base_heat_W_K':self.factor*qsum,'min_normalized_temperature':1-max_theta,'max_normalized_temperature':1-min_theta,
                'outlet_heat_per_length_W_m_K':self.factor*qroot_last,'outlet_floor_fraction_of_local_heat':float(self.base_floor_g@theta/qroot_last) if qroot_last else None,
                'mirrored_channel_contributions_W_K':channel_G,'mesh':{'gap_cells':self.nx,'height_cells':self.ny,'axial_steps':nz,'unknowns_half_or_full':self.n},
                'method':method,'temperature_field_samples':records}

    def sample(self,theta,z_m):
        ys=np.unique(np.linspace(0,self.ny-1,9,dtype=int)); channels=[]
        for ch in [0,1,len(self.channels)-1]:
            c=self.channels[ch]; xs=np.unique(np.linspace(0,c['ids'].shape[1]-1,5,dtype=int)); vals=(1-theta[c['ids']])[np.ix_(ys,xs)]
            channels.append({'channel_index_from_side':ch,'x_cell_centres_local_mm':((xs+.5)*c['dx']*1000).tolist(),'y_cell_centres_mm':((ys+.5)*self.dy*1000).tolist(),'normalized_T':vals.tolist()})
        fins=[{'fin_index_from_side':i,'normalized_T':(1-theta[self.fins[i][ys]]).tolist()} for i in sorted(set([0,len(self.fins)-1]))] if self.fins else []
        return {'z_m':z_m,'normalization':'(T-Tin)/(Tb-Tin)','channels':channels,'fins':fins}


def main():
    p=argparse.ArgumentParser(); p.add_argument('--nx',type=int,default=12); p.add_argument('--ny',type=int,default=72);p.add_argument('--nz',type=int,default=400);p.add_argument('--speed',type=float,default=4.);p.add_argument('--ks',type=float,default=205.);p.add_argument('--profile',choices=['fd','plug'],default='fd');p.add_argument('--method',choices=['be','bdf2'],default='be');p.add_argument('--output',type=pathlib.Path)
    a=p.parse_args(); t=time.monotonic(); m=Model(a.nx,a.ny,a.ks,profile=a.profile); r=m.solve(a.speed,a.nz,samples=True,method=a.method);r.update({'code_sha256':digest(__file__),'plan_sha256':digest(HERE/'precomparison_plan.json'),'elapsed_s':time.monotonic()-t,'velocity_checks':m.velocity_checks})
    out=json.dumps(r,indent=2)+'\n'; a.output.write_text(out) if a.output else print(out)
if __name__=='__main__':main()
