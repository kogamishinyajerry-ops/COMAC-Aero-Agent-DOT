#!/usr/bin/env python3
"""Bounded, offline Gmsh -> OpenFOAM -> independent numerical verification.
No application dependencies. Full meshes/fields remain in ignored output/.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
PLAN=json.loads((HERE/'plan.json').read_text())
TOOLS=Path('/workspace/shared/cfd-tools')
FOAM=TOOLS/'bin/foam'
L,W,H=.03,.004,.002
RHO,MU,K,CP=1.2,1.8e-5,.026,1005.
NU=MU/RHO; ALPHA=K/(RHO*CP); UM=3.; TIN=300.; TW=310.
WALLS=['floor','side_right','ceiling','side_left']

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_json(p,v): Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def header(obj,cls='dictionary'):
 return f'FoamFile\n{{ version 2.0; format ascii; class {cls}; object {obj}; }}\n'
def run(cmd,case,log,timeout=900):
 start=time.monotonic()
 with (case/log).open('w') as f:
  p=subprocess.run(list(map(str,cmd)),stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
 elapsed=time.monotonic()-start
 if p.returncode: raise RuntimeError(f'{cmd[0]} failed: {case/log}')
 return elapsed

def control(case,app='simpleFoam',end=1500,start='startTime',interval=1500):
 (case/'system/controlDict').write_text(header('controlDict')+f'''
application {app}; startFrom {start}; startTime 0; stopAt endTime; endTime {end};
deltaT 1; writeControl timeStep; writeInterval {interval}; purgeWrite 1;
writeFormat ascii; writePrecision 13; writeCompression off; timeFormat general;
timePrecision 10; runTimeModifiable false;
''')

def setup(case,grid):
 for d in ['0','constant','system']: (case/d).mkdir(parents=True,exist_ok=True)
 control(case)
 nx,ny,nz=grid
 geo=f'''SetFactory("Built-in");
Point(1)={{0,0,0}}; Point(2)={{0,{W},0}}; Point(3)={{0,{W},{H}}}; Point(4)={{0,0,{H}}};
Line(1)={{1,2}}; Line(2)={{2,3}}; Line(3)={{3,4}}; Line(4)={{4,1}};
Curve Loop(1)={{1,2,3,4}}; Plane Surface(1)={{1}};
Transfinite Curve {{1,3}}={ny+1}; Transfinite Curve {{2,4}}={nz+1};
Transfinite Surface {{1}}; Recombine Surface {{1}};
out[]=Extrude {{{L},0,0}} {{ Surface{{1}}; Layers{{{nx}}}; Recombine; }};
Physical Surface("inlet")={{1}}; Physical Surface("outlet")={{out[0]}};
Physical Surface("floor")={{out[2]}}; Physical Surface("side_right")={{out[3]}};
Physical Surface("ceiling")={{out[4]}}; Physical Surface("side_left")={{out[5]}};
Physical Volume("fluid")={{out[1]}};
Mesh.MshFileVersion=2.2;
'''
 (case/'duct.geo').write_text(geo)
 run([TOOLS/'bin/gmsh',case/'duct.geo','-3','-format','msh2','-o',case/'duct.msh'],case,'log.gmsh')
 run([FOAM,'gmshToFoam',case/'duct.msh','-case',case],case,'log.gmshToFoam')
 b=case/'constant/polyMesh/boundary';s=b.read_text()
 for name in WALLS:
  s=re.sub(r'('+name+r'\s*\{[^}]*?type\s+)patch;',r'\1wall;',s)
 b.write_text(s)
 (case/'constant/transportProperties').write_text(header('transportProperties')+f'transportModel Newtonian;\nnu [0 2 -1 0 0 0 0] {NU:.16g};\nDT [0 2 -1 0 0 0 0] {ALPHA:.16g};\n')
 (case/'constant/turbulenceProperties').write_text(header('turbulenceProperties')+'simulationType laminar;\n')
 (case/'system/fvSchemes').write_text(header('fvSchemes')+'''
ddtSchemes { default steadyState; }
gradSchemes { default Gauss linear; }
divSchemes { default none; div(phi,U) bounded Gauss linear; div(phi,T) Gauss upwind; div((nuEff*dev2(T(grad(U))))) Gauss linear; }
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes { default corrected; }
fluxRequired { default no; p; }
''')
 (case/'system/fvSolution').write_text(header('fvSolution')+'''
solvers {
p { solver GAMG; tolerance 1e-11; relTol 0.01; smoother GaussSeidel; }
U { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-11; relTol 0.01; }
T { solver PBiCGStab; preconditioner DILU; tolerance 1e-12; relTol 0; }
}
SIMPLE { nNonOrthogonalCorrectors 0; consistent yes; residualControl { p 1e-9; U 1e-7; T 1e-10; } }
relaxationFactors { equations { U 0.9; T 1; } }
''')
 run([FOAM,'checkMesh','-case',case,'-allTopology','-allGeometry'],case,'log.checkMesh')
 if 'Mesh OK.' not in (case/'log.checkMesh').read_text():raise RuntimeError('Mesh failed quality check')
 mesh=read_mesh(case)
 inlet=mesh['patches']['inlet']; c=mesh['face_centers'][inlet]
 v=velocity_shape(c[:,1],c[:,2]); norm=float(np.mean(v));u=UM*v/norm
 vector=np.column_stack((u,np.zeros_like(u),np.zeros_like(u)))
 ub={'inlet':('fixedValue',vector),'outlet':('zeroGradient',None),**{w:('fixedValue',(0,0,0)) for w in WALLS}}
 scalar_field(case/'0/U','U','volVectorField','[0 1 -1 0 0 0 0]',(0,0,0),ub)
 scalar_field(case/'0/p','p','volScalarField','[0 2 -2 0 0 0 0]',0,{'inlet':('zeroGradient',None),'outlet':('fixedValue',0),**{w:('zeroGradient',None) for w in WALLS}})
 scalar_field(case/'0/T','T','volScalarField','[0 0 0 1 0 0 0]',TIN,{'inlet':('fixedValue',TIN),'outlet':('zeroGradient',None),**{w:('fixedValue',TW) for w in WALLS}})
 write_json(case/'setup.json',{'grid':grid,'cells':len(mesh['centers']),'inlet_midpoint_quadrature_normalization':norm,'analytic_equivalent_mean_velocity_m_s':UM/norm,'mean_inlet_velocity_m_s':UM,'plan_sha256':sha(HERE/'plan.json')})
 return mesh

def value(v,vector=False):
 if isinstance(v,np.ndarray):
  arr=v.reshape(-1,3) if vector else v.reshape(-1)
  lines=['('+' '.join(f'{x:.15g}' for x in row)+')' for row in arr] if vector else [f'{x:.15g}' for x in arr]
  return f'nonuniform List<{"vector" if vector else "scalar"}>\n{len(arr)}\n(\n'+ '\n'.join(lines)+'\n)'
 if isinstance(v,tuple):return 'uniform ('+' '.join(map(str,v))+')'
 return f'uniform {v}'
def scalar_field(path,obj,cls,dims,internal,bcs):
 vector=cls=='volVectorField';s=header(obj,cls)+f'dimensions {dims};\ninternalField '+value(internal,vector)+';\nboundaryField\n{\n'
 for name,(typ,v) in bcs.items():
  s+=name+'\n{ type '+typ+';\n'
  if v is not None:s+='value '+value(v,vector)+';\n'
  s+='}\n'
 Path(path).write_text(s+'}\n')

def content_list(path):
 s=Path(path).read_text();s=re.sub(r'/\*.*?\*/','',s,flags=re.S);s=re.sub(r'//[^\n]*','',s)
 # Lists begin after FoamFile's closing brace.
 s=s[s.index('}')+1:];m=re.search(r'\b(\d+)\s*\(',s)
 start=m.end();return int(m.group(1)),s[start:s.rfind(')')]
def read_mesh(case):
 p=case/'constant/polyMesh'
 n,s=content_list(p/'points');pts=np.fromstring(s.replace('(',' ').replace(')',' '),sep=' ').reshape(n,3)
 nf,s=content_list(p/'faces'); faces=np.fromstring(s.replace('(',' ').replace(')',' '),sep=' ',dtype=int).reshape(nf,5)
 assert np.all(faces[:,0]==4);faces=faces[:,1:]
 _,s=content_list(p/'owner'); owner=np.fromstring(s,sep=' ',dtype=int)
 ni,s=content_list(p/'neighbour'); nei=np.fromstring(s,sep=' ',dtype=int)
 fc=pts[faces].mean(axis=1)
 # Each Cartesian hexahedron has six equal-weight face centers.
 centers=np.zeros((int(owner.max())+1,3)); np.add.at(centers,owner,fc);np.add.at(centers,nei,fc[:ni]);centers/=6
 sf=.5*np.cross(pts[faces[:,2]]-pts[faces[:,0]],pts[faces[:,3]]-pts[faces[:,1]])
 # Ensure owner outward normals (Gmsh import normally already does this).
 sign=np.einsum('ij,ij->i',sf,fc-centers[owner]);sf[sign<0]*=-1
 patches={}
 for name,n,start in re.findall(r'(\w+)\s*\{[^{}]*?nFaces\s+(\d+);\s*startFace\s+(\d+);', (p/'boundary').read_text()):
  if int(n):patches[name]=np.arange(int(start),int(start)+int(n))
 return dict(points=pts,faces=faces,owner=owner,neighbour=nei,face_centers=fc,centers=centers,Sf=sf,area=np.linalg.norm(sf,axis=1),patches=patches)

def parse_value(s,vector=False,n=None):
 m=re.search(r'\buniform\s+([^;]+);',s)
 if m:
  vals=np.fromstring(m.group(1).strip().strip('()'),sep=' ')
  if n is None:return vals if vector else vals[0]
  return np.tile(vals,(n,1)) if vector else np.full(n,vals[0])
 m=re.search(r'nonuniform\s+List<\w+>\s+(\d+)\s*\((.*?)\)\s*;',s,re.S)
 if not m:raise ValueError('Cannot parse field value')
 arr=np.fromstring(m.group(2).replace('(',' ').replace(')',' '),sep=' ')
 return arr.reshape(-1,3) if vector else arr

def read_field(path,n):
 s=Path(path).read_text();vector='volVectorField' in s
 data=parse_value(s[s.index('internalField')+13:s.index('boundaryField')],vector,n)
 b={}
 for name,body in re.findall(r'(\w+)\s*\{([^{}]*)\}',s[s.index('boundaryField'):],re.S):
  if 'value' in body: b[name]=parse_value(body[body.index('value')+5:],vector)
 return data,b

def velocity_shape(y,z):
 # dimensionless Poisson solution on y/H in [0,2], z/H in [0,1].
 Y=y/H;Z=z/H;out=Z*(1-Z)/2
 for n in range(1,800,2):
  a=n*np.pi*np.abs(Y-1);b=n*np.pi
  ratio=np.exp(a-b)*(1+np.exp(-2*a))/(1+np.exp(-2*b))
  out-=4/np.pi**3*np.sin(n*np.pi*Z)/n**3*ratio
 return out/exact_mean()
def exact_mean():
 n=np.arange(1,20000,2,dtype=float)
 return (1-96/np.pi**5*np.sum(np.tanh(n*np.pi)/n**5))/12

def latest(case):
 return max((p for p in case.iterdir() if p.is_dir() and re.fullmatch(r'\d+(?:\.\d+)?',p.name)),key=lambda p:float(p.name))

def solve_flow(case):
 elapsed=run([FOAM,'simpleFoam','-case',case],case,'log.simpleFoam',timeout=1200)
 final=latest(case);s=(case/'log.simpleFoam').read_text()
 if 'SIMPLE solution converged' not in s: raise RuntimeError(f'Flow not converged: {case}')
 shutil.copytree(final,case/'flow_final',dirs_exist_ok=True)
 write_json(case/'flow_run.json',{'wall_seconds':elapsed,'iterations':float(final.name),'final_time':final.name,'solver':'simpleFoam'})
 return final

def solve_heat(case,exact=False):
 mesh=read_mesh(case); n=len(mesh['centers']);flow=case/'flow_final'
 heat=case/('analytic' if exact else 'thermal'); heat.mkdir(exist_ok=True)
 for d in ['constant','system']:shutil.copytree(case/d,heat/d,dirs_exist_ok=True)
 (heat/'0').mkdir(exist_ok=True)
 if not exact:
  for name in ['U','phi']:shutil.copy2(flow/name,heat/'0'/name)
  shutil.copy2(case/'0/T',heat/'0/T')
 else:
  us=PLAN['analytic_thermal_plug_velocity_m_s']
  scalar_field(heat/'0/U','U','volVectorField','[0 1 -1 0 0 0 0]',(us,0,0),{name:('fixedValue',(us,0,0)) for name in mesh['patches']})
  schemes=heat/'system/fvSchemes';schemes.write_text(schemes.read_text().replace('div(phi,T) Gauss upwind;', 'div(phi,T) Gauss linear;'))
  us=PLAN['analytic_thermal_plug_velocity_m_s'];lam=(np.pi/W)**2+(np.pi/H)**2;r=-2*ALPHA*lam/(us+np.sqrt(us**2+4*ALPHA**2*lam))
  bcs={}
  for name,idx in mesh['patches'].items():
   c=mesh['face_centers'][idx];theta=np.sin(np.pi*c[:,1]/W)*np.sin(np.pi*c[:,2]/H)*np.exp(r*c[:,0]);bcs[name]=('fixedValue',theta)
  scalar_field(heat/'0/T','T','volScalarField','[0 0 0 1 0 0 0]',0,bcs)
 control(heat,'scalarTransportFoam',200,interval=200)
 elapsed=run([FOAM,'scalarTransportFoam','-case',heat],heat,'log.scalarTransportFoam',timeout=600)
 final=latest(heat)
 write_json(heat/'run.json',{'wall_seconds':elapsed,'iterations':float(final.name),'final_time':final.name,'solver':'scalarTransportFoam'})
 return heat

def residuals(log):
 vals={}
 for name,initial,final in re.findall(r'Solving for (\w+), Initial residual = ([\deE+.\-]+), Final residual = ([\deE+.\-]+)',Path(log).read_text()):
  vals[name]={'initial':float(initial),'final':float(final)}
 return vals

def analyse(case):
 mesh=read_mesh(case);n=len(mesh['centers']);c=mesh['centers'];owner=mesh['owner'];fc=mesh['face_centers'];area=mesh['area'];patches=mesh['patches'];ni=len(mesh['neighbour'])
 u,ub=read_field(case/'flow_final/U',n);p,pb=read_field(case/'flow_final/p',n)
 setup=json.loads((case/'setup.json').read_text());ueq=setup['analytic_equivalent_mean_velocity_m_s']
 ref=ueq*velocity_shape(c[:,1],c[:,2]);mask=(c[:,0]>.25*L)&(c[:,0]<.75*L)
 velerr=float(np.linalg.norm(u[mask,0]-ref[mask])/np.linalg.norm(ref[mask]))
 xs=np.unique(np.round(c[:,0],12));pm=np.array([np.mean(p[np.isclose(c[:,0],x,atol=1e-12)]) for x in xs]); fit=(xs>.25*L)&(xs<.75*L);slope=np.polyfit(xs[fit],pm[fit],1)[0]
 gexact=MU*ueq/(H**2*exact_mean())
 # Actual pressure-corrected OpenFOAM flux from SIMPLE, used unchanged by thermal solve.
 _,phib=read_field(case/'flow_final/phi',ni)
 flow_flux={name:float(np.sum(np.broadcast_to(phib[name],(len(idx),)))) for name,idx in patches.items()}
 heat=case/'thermal';t,tb=read_field(latest(heat)/'T',n)
 for name,idx in patches.items():
  if name not in tb:tb[name]=t[owner[idx]]
 fluxes={};heat_power=0
 for name,idx in patches.items():
  vals=np.broadcast_to(tb[name],(len(idx),));phi=np.broadcast_to(phib[name],(len(idx),));d=np.linalg.norm(fc[idx]-c[owner[idx]],axis=1)
  # On orthogonal Cartesian mesh the boundary snGrad uses half-cell distance.
  conduction=-K*np.sum((vals-t[owner[idx]])/d*area[idx]);advection=RHO*CP*np.sum(phi*(vals-TIN))
  fluxes[name]={'convective_outward_W_reference_300K':float(advection),'conductive_outward_W':float(conduction),'total_outward_W':float(advection+conduction)}
  heat_power+=abs(conduction)+abs(advection)
 Tout=float(np.sum(phib['outlet']*tb['outlet'])/np.sum(phib['outlet']))
 exact_case=case/'analytic';a,ab=read_field(latest(exact_case)/'T',n)
 us=PLAN['analytic_thermal_plug_velocity_m_s'];lam=(np.pi/W)**2+(np.pi/H)**2;r=-2*ALPHA*lam/(us+np.sqrt(us**2+4*ALPHA**2*lam));a_ref=np.sin(np.pi*c[:,1]/W)*np.sin(np.pi*c[:,2]/H)*np.exp(r*c[:,0])
 mc=(case/'log.checkMesh').read_text()
 result={'grid':setup['grid'],'cells':n,'mesh_ok':'Mesh OK.' in mc,'three_dimensions':'Mesh has 3 solution (non-empty) directions (1 1 1)' in mc,'maximum_nonorthogonality':float(re.search(r'Mesh non-orthogonality Max: ([\deE+.\-]+)',mc).group(1)),
 'analytic_equivalent_mean_velocity_m_s':ueq,'analytic_pressure_gradient_Pa_m':gexact,'solved_pressure_gradient_Pa_m':float(-RHO*slope),'pressure_gradient_relative_error':float(-RHO*slope/gexact-1),'velocity_relative_L2_error_middle_half':velerr,'nominal_mean_analytic_pressure_gradient_Pa_m':MU*UM/(H**2*exact_mean()),'nominal_mean_pressure_gradient_relative_error':float(-RHO*slope/(MU*UM/(H**2*exact_mean()))-1),'nominal_mean_velocity_relative_L2_error_middle_half':float(np.linalg.norm(u[mask,0]-UM*velocity_shape(c[mask,1],c[mask,2]))/np.linalg.norm(UM*velocity_shape(c[mask,1],c[mask,2]))),'inlet_outlet_pressure_drop_Pa':float(RHO*np.mean(p[owner[patches['inlet']]])),
 'max_transverse_velocity_m_s':float(np.max(np.linalg.norm(u[:,1:],axis=1))),
 'volume_flux_by_patch_m3_s':flow_flux,'relative_mass_imbalance':abs(sum(flow_flux.values()))/abs(flow_flux['inlet']),
 'outlet_mixed_temperature_K':Tout,'outlet_bulk_theta':(TW-Tout)/(TW-TIN),'temperature_min_K':float(t.min()),'temperature_max_K':float(t.max()),
 'boundary_heat_fluxes':fluxes,'energy_imbalance_W':sum(v['total_outward_W'] for v in fluxes.values()),'relative_energy_imbalance':abs(sum(v['total_outward_W'] for v in fluxes.values()))/(RHO*CP*UM*W*H*(TW-TIN)),
 'analytic_thermal_relative_L2_error':float(np.linalg.norm(a-a_ref)/np.linalg.norm(a_ref)),
 'flow_residuals':residuals(case/'log.simpleFoam'),'thermal_residuals':residuals(heat/'log.scalarTransportFoam'),'analytic_residuals':residuals(exact_case/'log.scalarTransportFoam'),
 'flow_runtime':json.loads((case/'flow_run.json').read_text()),'thermal_runtime':json.loads((heat/'run.json').read_text()),'analytic_runtime':json.loads((exact_case/'run.json').read_text())}
 write_json(case/'metrics.json',result)
 np.savez_compressed(case/'fields.npz',centers=c,U=u,p_Pa=p*RHO,T=t,analytic=a,analytic_reference=a_ref)
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('command',choices=['run','analyse']);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--levels',default='0,1,2');args=ap.parse_args()
 args.output.mkdir(parents=True,exist_ok=True)
 for idx in map(int,args.levels.split(',')):
  grid=PLAN['grids'][idx];case=args.output/f'grid_{idx}'
  if args.command=='run' and case.exists():raise ValueError('Choose a fresh output directory; prior attempts are preserved')
  case.mkdir(exist_ok=True)
  if args.command=='run':
   print(f'Starting {grid}',flush=True);setup(case,grid);solve_flow(case);solve_heat(case);solve_heat(case,exact=True)
  result=analyse(case);print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
