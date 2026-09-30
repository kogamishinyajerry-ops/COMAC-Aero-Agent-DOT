#!/usr/bin/env python3
"""Mathematical checks only; never reads Figure8 targets."""
import gc,importlib.util,json,time
import numpy as np
from scipy.sparse import diags,eye,kron
from scipy.sparse.linalg import splu
from axial_fin import AxialModel,axial_graph,base,HERE,sha
spec=importlib.util.spec_from_file_location('independent_axial_reference',HERE/'review/independent_axial_review.py');review=importlib.util.module_from_spec(spec);spec.loader.exec_module(review)

def full_states(m):
 out=np.empty((m.nz,m.model.n));f=np.ones(m.nf)
 for i in range(m.nz):
  f=m.fluid_lu.solve(m.D*f-m.Kfs@m.solid[i]);out[i]=np.r_[f,m.solid[i]]
 return out

def main():
 start=time.monotonic();rows=[];direct=[]
 for speed in [4.,10.]:
  for lam in [0.,1.]:
   m=AxialModel(4,12,20,speed,lam);r=m.solve(False);ref,diag=review.direct_reference(m.model,speed,20,lam)
   actual=full_states(m);direct.append({'speed':speed,'lambda_z':lam,'relative_G_difference':r['G_W_K']/diag['G_W_K']-1,'maximum_field_absolute_difference':float(np.max(abs(actual-ref))),'reference_componentwise_backward_error':diag['maximum_componentwise_backward_error']});rows.append(r);print('direct',direct[-1],flush=True)
   del m;gc.collect()
 h=AxialModel(4,12,20,10.,1.);hr=h.solve(False);f=AxialModel(4,12,20,10.,1.,full=True);fr=f.solve(False)
 symmetry={'relative_G_difference':hr['G_W_K']/fr['G_W_K']-1,'maximum_left_fin_field_difference':float(np.max(abs(h.solid.reshape(20,8,12)-f.solid.reshape(20,16,12)[:,:8,:])))}
 rows.extend([hr,fr]);del h,f;gc.collect()
 baths=[]
 for ny in [12,24,48]:
  m=AxialModel(12,ny,24,4.,1.);tau=m.solid_lu.solve(np.tile(m.bs,m.nz)).reshape(m.nz,m.ns);one=tau[:,ny:2*ny];dy=base.H/ny
  heff=1/((base.WI/12)/(2*base.KA)+base.T/(2*205.));wave=np.sqrt(2*heff/(205.*base.T));y=(np.arange(ny)+.5)*dy;exact=np.cosh(wave*(base.H-y))/np.cosh(wave*base.H)
  q=2*205.*base.T/dy*float(np.sum(1-one[:,0]))*m.dz;qexact=np.sqrt(2*heff*205.*base.T)*np.tanh(wave*base.H)*base.L
  baths.append({'ny':ny,'relative_heat_error':q/qexact-1,'maximum_profile_error':float(np.max(abs(one-exact))),'axial_temperature_spread':float(np.max(np.ptp(one,axis=0)))})
  del m;gc.collect()
 mms=[];ky=205.;kz=73.;beta=100.
 for ny,nz in [(12,24),(24,48),(48,96)]:
  dy=base.H/ny;dz=base.L/nz;diag=np.full(ny,2.);diag[0]=3.;diag[-1]=1.;Ky=diags([-np.ones(ny-1),diag,-np.ones(ny-1)],[-1,0,1],format='csc')*(ky*base.T/dy)
  A=kron(eye(nz,format='csc'),Ky+eye(ny,format='csc')*beta*dy,format='csc')+axial_graph(nz,ny,kz*base.T*dy/dz**2)
  y=(np.arange(ny)+.5)*dy;z=(np.arange(nz)+.5)*dz;exact=np.cos(np.pi*z[:,None]/base.L)*np.sin(np.pi*y[None,:]/(2*base.H));coef=ky*base.T*(np.pi/(2*base.H))**2+kz*base.T*(np.pi/base.L)**2+beta
  actual=splu(A).solve(coef*dy*exact.ravel()).reshape(nz,ny);err=float(np.linalg.norm(actual-exact)/np.linalg.norm(exact));row={'ny':ny,'nz':nz,'relative_L2_error':err,'maximum_absolute_error':float(np.max(abs(actual-exact)))}
  if mms:row['observed_order']=float(np.log2(mms[-1]['relative_L2_error']/err))
  mms.append(row)
 m=AxialModel(4,12,20,4.,1.,grounded=False);insulated=m.solve(False);del m;gc.collect()
 m=AxialModel(4,12,20,4.,1.,ks=1e7);high=m.solve(False);iso=base.Model(4,12,isothermal=True).solve(4.,nz=20);highk={'finite_ks':1e7,'relative_G_difference_from_isothermal':high['G_W_K']/iso['G_W_K']-1};rows.append(high);del m;gc.collect()
 tolerance=[]
 for rt,at in [(1e-10,1e-12),(1e-12,1e-14)]:
  m=AxialModel(12,36,120,4.,1.,rtol=rt,atol=at);r=m.solve(False);tolerance.append(r);rows.append(r);del m;gc.collect()
 td=abs(tolerance[0]['paired_relative_conductance_change']-tolerance[1]['paired_relative_conductance_change'])
 gates={'zero_axial_G_recovery':max(abs(r['paired_relative_conductance_change']) for r in rows if r['lambda_z']==0)<1e-9,'zero_axial_solid_recovery':max(r['zero_recovery_solid_max_absolute_difference'] for r in rows if r['lambda_z']==0)<1e-8,'independent_direct_reference_G':max(abs(r['relative_G_difference']) for r in direct)<1e-8,'independent_direct_reference_fields':max(r['maximum_field_absolute_difference'] for r in direct)<1e-8,'energy':max(r['energy_relative_balance'] for r in rows)<1e-8,'componentwise_backward_error':max(r['componentwise_backward_error_max'] for r in rows)<1e-8,'maximum_principle':min(r['minimum_normalized_temperature'] for r in rows)>-1e-8 and max(r['maximum_normalized_temperature'] for r in rows)<1+1e-8,'full_half_symmetry_G':abs(symmetry['relative_G_difference'])<1e-8,'full_half_symmetry_fields':symmetry['maximum_left_fin_field_difference']<1e-8,'uniform_bath_fin_heat':abs(baths[-1]['relative_heat_error'])<.002,'uniform_bath_fin_shape':baths[-1]['maximum_profile_error']<.002 and baths[-1]['axial_temperature_spread']<1e-10,'manufactured_axial_mode':mms[-1]['relative_L2_error']<.002 and mms[-1]['observed_order']>1.9,'insulated_limit':max(abs(insulated['minimum_normalized_temperature']),abs(insulated['maximum_normalized_temperature']))<1e-8 and abs(insulated['G_W_K'])<1e-10,'high_conductivity_limit':abs(highk['relative_G_difference_from_isothermal'])<1e-5,'tolerance_change_negligible_for_pilot_effect':td<1e-9}
 gates={k:bool(v) for k,v in gates.items()};out={'status':'mathematical_checks_passed_before_refinement' if all(gates.values()) else 'mathematical_checks_failed','gates':gates,'independent_direct':direct,'symmetry':symmetry,'uniform_bath_fin':baths,'manufactured_axial_mode':mms,'manufactured_notice':'Synthetic beta100 forcing and kz73 exercise the operator; neither is an experimental fit or production material choice','insulated_limit':insulated,'high_conductivity_limit':highk,'pilot_tolerance_absolute_delta_difference':td,'runs':rows,'elapsed_seconds':time.monotonic()-start,'source_targets_read':False,'axial_code_sha256':sha(HERE/'axial_fin.py'),'verification_code_sha256':sha(__file__),'independent_reference_code_sha256':sha(HERE/'review/independent_axial_review.py'),'plan_sha256':sha(HERE/'PLAN.md'),'physical_validation_pass':None,'aircraft_transfer_authorized':False}
 (HERE/'mathematical_verification.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');print(gates,flush=True);assert (HERE/'mathematical_verification.json').stat().st_size<100000;assert all(gates.values())
if __name__=='__main__':main()
