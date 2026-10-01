#!/usr/bin/env python3
"""Independent pre-existing FV and sine-Galerkin Graetz comparators.
Only fresh output is written. No frozen application evidence is changed.
"""
import argparse, hashlib, importlib.util, json, os, sys, time
from pathlib import Path
import numpy as np
from scipy.linalg import eigh
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]

def galerkin(tau,count,q=100):
 a=2.;g,gw=np.polynomial.legendre.leggauss(q);x,y=(g+1)*a/2,(g+1)/2;quadrature=np.outer(gw/2,gw*a/2)
 n=np.arange(1,4000,2,dtype=float);z=n[:,None]*np.pi*abs(x-a/2);c=n[:,None]*np.pi*a/2
 ratio=np.exp(z-c)*(1+np.exp(-2*z))/(1+np.exp(-2*c))
 w=y[:,None]*(1-y[:,None])/2-4/np.pi**3*(np.sin(np.pi*y[:,None]*n)/n**3)@ratio
 mean_w=np.sum(w*quadrature)/a;vmass=(w/mean_w*quadrature).ravel();modes=np.arange(1,2*count,2)
 sx=np.sin(np.pi*np.outer(x/a,modes));sy=np.sin(np.pi*np.outer(y,modes))
 F=(2/np.sqrt(a)*np.einsum('yn,xm->yxnm',sy,sx)).reshape(q*q,count*count)
 M=F.T@(vmass[:,None]*F);K=np.diag((np.pi**2*(modes[:,None]**2+(modes[None,:]/a)**2)).ravel())
 eig,V=eigh(K,M);weights=(V.T@(F.T@vmass))**2/a
 return {'odd_modes_per_direction':count,'quadrature_order':q,'bulk_theta':float(weights@np.exp(-eig*tau)),'fundamental_eigenvalue':float(eig[0]),'mean_raw_velocity':float(mean_w),'captured_inlet_norm':float(sum(weights))}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 os.environ['RECTANGULAR_OUTPUT_DIR']=str(a.output/'unused_existing_solver_outputs')
 source=REPO/'research/rectangular_duct/rectangular_graetz.py';spec=importlib.util.spec_from_file_location('existing_rectangular',source);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 alpha=.026/(1.2*1005);tau=alpha*.03/(3*.002**2);started=time.time();results=[]
 for ny,steps in [(64,1024),(128,2048)]:
  print('Existing FVM reference',ny,steps,flush=True);m=mod.Model(ny);r=m.march(steps=steps,last=tau,first=tau,cap_dt=False)
  results.append({'ny':ny,'nx':ny*2,'axial_steps':steps,'bulk_theta':m.bulk(r['last_field']),'checks':r['checks'],'momentum':m.momentum_evidence()})
 continuum=[]
 for count in [16,24]:
  print('Independent Galerkin',count,flush=True);continuum.append(galerkin(tau,count))
 result={'tau':tau,'Gz_Dh':(4/3)**2/tau,'existing_solver_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'existing_independent_galerkin_source_sha256':hashlib.sha256((REPO/'research/rectangular_duct/independent_galerkin_reference.py').read_bytes()).hexdigest(),'execution':'New synthetic model-to-model comparison; existing frozen evidence untouched; no experimental data used','model_difference':'Both Graetz references omit axial fluid diffusion; OpenFOAM retains it and uses a finite zero-gradient outlet','finite_volume':results,'galerkin':continuum,'elapsed_seconds':time.time()-started}
 (a.output/'references.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
