#!/usr/bin/env python3
"""One resource-bounded process: six fixed reviewed main-root evaluations only."""
import sys
sys.dont_write_bytecode=True
import argparse,importlib.util,json,math,os,pathlib,resource,time
HERE=pathlib.Path(__file__).absolute().parent

def scalar_native(value):
 import numpy as np
 if isinstance(value,np.generic):return value.item()
 raise TypeError('unsupported result type: '+type(value).__name__)

def save(fd,name,value):
 b=(json.dumps(value,indent=2,allow_nan=False,default=scalar_native)+'\n').encode()
 if len(b)>=100000:raise ValueError('replay JSON exceeds strict100KB bound')
 file_fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
 with os.fdopen(file_fd,'wb') as f:f.write(b)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--expected-manifest-sha256',required=True);parser.add_argument('--output-fd',type=int,required=True);a=parser.parse_args()
 if sys.platform!='linux':raise ValueError('numerical replay is supported on Linux only')
 resource.setrlimit(resource.RLIMIT_CPU,(600,610));resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));resource.setrlimit(resource.RLIMIT_FSIZE,(99999,99999))
 spec=importlib.util.spec_from_file_location('snapshot_audit',HERE/'audit_package.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
 checked,records,pin=audit.audit(HERE.parents[1],a.expected_manifest_sha256,True)
 source=HERE/'study/pressure_requirement.py'
 spec=importlib.util.spec_from_file_location('unchanged_pressure_requirement',source);model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
 scalar_names=['G_W_K','volume_flow_m3_s','mass_flow_kg_s','pressure_dissipation_W','friction_dissipation_W','end_loss_dissipation_W','max_Re_Dh','max_peak_Mach','capacity_rate_W_K','effectiveness','required_uniform_base_at_60W_C','capacity_at_uniform_base_85C_W','fin_only_mass_kg','energy_relative_balance_max','componentwise_thermal_equation_residual_relative','pressure_closure_relative','mass_transport_closure_relative']
 start=time.monotonic();rows=[]
 for design,thickness in [('n16_t860',.00086),('n16_t600',.0006)]:
  data=audit.strict_json(records[audit.STUDY+'continuation/results/'+design+'.json'])
  for case in data['cases']:
   K=case['K'];root=case['roots']['main'];P=root['root_Pa']
   if root['mesh']!=[48,144,800]:raise ValueError('non-main mesh requested')
   expected=audit.strict_json(records[audit.STUDY+root['root_record']])
   m=model.EndLossFin(N=16,t=thickness,nx=48,ny=144,end_loss_K=K)
   domain=m.domain_state(P)
   if not all(s['within_domain'] for s in domain.values()):raise ValueError('nominal/combined domain failure')
   r=m.solve(.6*P,(1,),nz=800,details=True)
   differences={name:{'expected':expected[name],'replayed':r[name],'signed_absolute_difference':r[name]-expected[name],'relative_difference':(r[name]/expected[name]-1) if expected[name]!=0 else None} for name in scalar_names}
   reproduced=abs(r['G_W_K']/expected['G_W_K']-1)<1e-10
   passed=reproduced and all(r['gates'].values()) and abs(60*r['G_W_K']-60)<.001
   name=f'case_{design}_K{K}.json'
   save(a.output_fd,name,{'design_id':design,'K':K,'nominal_pressure_budget_Pa':P,'combined_pressure_budget_Pa':.6*P,'expected_record':root['root_record'],'package_manifest_sha256':pin,'domain_at_both_conditions':domain,'scalar_differences':differences,'all_passed':passed,'replayed_result':r})
   rows.append({'design_id':design,'K':K,'nominal_pressure_budget_Pa':P,'result_file':name,'relative_G_difference':differences['G_W_K']['relative_difference'],'root_heat_residual_W':60*r['G_W_K']-60,'all_passed':passed})
   del m
 if len(rows)!=6:raise ValueError('six-case replay count')
 result={'status':'passed' if all(r['all_passed'] for r in rows) else 'failed','all_passed':all(r['all_passed'] for r in rows),'thermal_evaluations':6,'root_searches':0,'new_parameter_or_geometry_sweep':False,'rows':rows,'elapsed_s':time.monotonic()-start,'source_model_sha256':audit.digest(records[audit.STUDY+'pressure_requirement.py']),'accepted_thermal_source_sha256':audit.digest(records['research/pressure_fin/original_freeze/study/pressure_fin.py']),'package_manifest_sha256':pin,'numerical_gates':'unchanged inherited gates; G agreement1e-10 relative; root heat residual0.001W','physical_validation_pass':None,'aircraft_transfer_authorized':False}
 save(a.output_fd,'numerical_replay.json',result);print(json.dumps(result,allow_nan=False,default=scalar_native))
 if not result['all_passed']:raise SystemExit(1)
if __name__=='__main__':main()
