#!/usr/bin/env python3
"""Supplementary outlet-location and post-convergence stationarity checks."""
import argparse, json, os, re, shutil
from pathlib import Path
import numpy as np
import study as s

def clone_settings(src,dst):
 (dst/'0').mkdir(parents=True)
 shutil.copytree(src/'constant',dst/'constant',copy_function=os.link)
 shutil.copytree(src/'system',dst/'system')

def stationarity(base,root,levels):
 results=json.loads((root/'stationarity.json').read_text()) if (root/'stationarity.json').exists() else []
 for i in levels:
  case=base/f'grid_{i}';mesh=s.read_mesh(case);n=len(mesh['centers']);out=root/f'grid_{i}';out.mkdir(parents=True)
  row={'grid_level':i,'extra_iterations':20}
  for kind,source,state,app,fields in [('flow',case,case/'flow_final','simpleFoam',['U','p']),('thermal',case/'thermal',s.latest(case/'thermal'),'scalarTransportFoam',['T'])]:
   dest=out/kind;clone_settings(source,dest)
   for f in state.iterdir():
    if f.is_file():shutil.copy2(f,dest/'0'/f.name)
   if kind=='thermal':
    for f in ['U','phi']:shutil.copy2(source/'0'/f,dest/'0'/f)
   d=dest/'system/fvSolution';d.write_text(re.sub(r'residualControl\s*\{[^}]*\}', '',d.read_text()))
   s.control(dest,app,20,interval=20)
   elapsed=s.run([s.FOAM,app,'-case',dest],dest,'log.'+app,timeout=600)
   metrics={}
   for f in fields:
    before,_=s.read_field(state/f,n);after,_=s.read_field(s.latest(dest)/f,n)
    metrics[f]={'relative_L2_change':float(np.linalg.norm(after-before)/max(np.linalg.norm(before),1e-30)),'maximum_absolute_change':float(np.max(abs(after-before)))}
   if kind=='flow':
    x=mesh['centers'][:,0];mid=(x>.25*s.L)&(x<.75*s.L);before,_=s.read_field(state/'p',n);after,_=s.read_field(s.latest(dest)/'p',n)
    oldg=np.polyfit(x[mid],before[mid],1)[0];newg=np.polyfit(x[mid],after[mid],1)[0]
    metrics['pressure_gradient_relative_change']=float(newg/oldg-1)
   else:
    t,tb=s.read_field(s.latest(dest)/'T',n);_,phib=s.read_field(source/'0/phi',len(mesh['neighbour']));idx=mesh['patches']['outlet'];tout=float(np.sum(phib['outlet']*t[mesh['owner'][idx]])/np.sum(phib['outlet']));old=json.loads((case/'metrics.json').read_text())['outlet_mixed_temperature_K']
    metrics['outlet_mixed_temperature_change_K']=tout-old
   row[kind]={'wall_seconds':elapsed,'metrics':metrics,'final_residuals':s.residuals(dest/('log.'+app))}
  results.append(row)
 s.write_json(root/'stationarity.json',results)
 return results

def extension(base,root):
 s.L=.045;case=root/'extended_medium';case.mkdir(parents=True)
 mesh=s.setup(case,[120,32,16]);s.solve_flow(case);s.solve_heat(case)
 n=len(mesh['centers']);t,tb=s.read_field(s.latest(case/'thermal')/'T',n);phi,_=s.read_field(case/'flow_final/phi',len(mesh['neighbour']));fc=mesh['face_centers'];ip=np.where(np.isclose(fc[:len(phi),0],.03,rtol=0,atol=1e-12)&(np.abs(mesh['Sf'][:len(phi),0])>1e-15))[0]
 flux=phi[ip]*np.sign(mesh['Sf'][ip,0]);upwind=np.where(phi[ip]>=0,t[mesh['owner'][ip]],t[mesh['neighbour'][ip]])
 tm=float(np.sum(flux*upwind)/np.sum(flux));original=json.loads((base/'grid_1/metrics.json').read_text())['outlet_mixed_temperature_K']
 result={'grid':[120,32,16],'length_m':.045,'comparison_plane_m':.03,'comparison_faces':len(ip),'numerical_flux_weighted_temperature_at_plane_K':tm,'original_medium_outlet_temperature_K':original,'relative_temperature_rise_change':(tm-original)/(original-s.TIN),'reporting_threshold':.002,'below_reporting_threshold':abs((tm-original)/(original-s.TIN))<=.002,'flow_runtime':json.loads((case/'flow_run.json').read_text()),'thermal_runtime':json.loads((case/'thermal/run.json').read_text()),'note':'Medium-grid outlet-location diagnostic only; full upstream velocity re-solved; face temperature is actual upwind numerical flux value, not an interpolated physical temperature'}
 s.write_json(root/'outlet_sensitivity.json',result);return result

def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=['extension','stationarity']);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--levels',default='0,1,2');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 r=extension(a.base,a.output) if a.command=='extension' else stationarity(a.base,a.output,map(int,a.levels.split(',')))
 print(json.dumps(r,indent=2))
if __name__=='__main__':main()
