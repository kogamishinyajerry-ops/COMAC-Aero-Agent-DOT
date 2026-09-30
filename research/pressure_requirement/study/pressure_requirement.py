#!/usr/bin/env python3
"""Conditional inverse-pressure study; inherited operator is imported read-only."""
from __future__ import annotations
import sys, pathlib, importlib.util, json, hashlib, math, time, os
sys.dont_write_bytecode = True
import numpy as np
from scipy.optimize import brentq
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = ROOT/'research/pressure_fin/original_freeze/study/pressure_fin.py'
spec = importlib.util.spec_from_file_location('accepted_pressure_fin', SOURCE)
pf = importlib.util.module_from_spec(spec); spec.loader.exec_module(pf)
PLAN = json.loads((HERE/'plan.json').read_text())
PLAN_HASH = hashlib.sha256((HERE/'plan.json').read_bytes()).hexdigest()
assert PLAN_HASH == (HERE/'plan.sha256').read_text().split()[0]
SOUND_SPEED = math.sqrt(1.4*287.05*298.15)
MAX_SOLVES = PLAN['resource_plan']['max_new_thermal_solves']

def digest(path): return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
def save(path, data):
    path=HERE/path; path.parent.mkdir(parents=True,exist_ok=True)
    s=json.dumps(data,indent=2,allow_nan=False,default=lambda v:v.item() if isinstance(v,np.generic) else str(v))+'\n'
    if path.suffix=='.json' and len(s.encode())>=100000: raise ValueError('JSON limit: '+str(path))
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(s);tmp.replace(path)

def shape_upper(c, nx, ny):
    width=c['width'];h=pf.H;n=nx if width<=h else ny
    return min(width,h)**2/8*(1+1/n**2)/min(c['wmean'],pf.exact_poisson_mean(width,h))

def velocity(dp,a,K):
    return dp/a if K==0 else 2*dp/(a+math.sqrt(a*a+2*pf.RHO*K*dp))

class EndLossFin(pf.PressureFin):
    def __init__(self, *, end_loss_K=0, **kwargs):
        if end_loss_K not in PLAN['scenario_K']: raise ValueError('undeclared K')
        super().__init__(**kwargs); self.end_loss_K=end_loss_K
    def hydraulic(self,pressure,blocked=()):
        # Exact original arithmetic path is retained for K=0.
        rows=super().hydraulic(pressure,blocked)
        K=self.end_loss_K
        for r,c in zip(rows,self.channels):
            a=self.mu*pf.L/c['wmean']
            if K and not r['blocked']:
                u=velocity(pressure,a,K);q=u*c['width']*pf.H
                exact_a=self.mu*pf.L/pf.exact_poisson_mean(c['width'],pf.H)
                exact=velocity(pressure,exact_a,K)*c['width']*pf.H
                r.update(mean_speed_m_s=u,volume_flow_m3_s=q,mass_flow_kg_s=q*pf.RHO,
                         Re_Dh=u*(2*c['width']*pf.H/(c['width']+pf.H))/(self.mu/pf.RHO),
                         hydraulic_conductance_m3_s_Pa=q/pressure,flow_relative_to_exact=q/exact-1)
            u=r['mean_speed_m_s'];q=r['volume_flow_m3_s']
            friction=a*u;end=.5*pf.RHO*K*u*u
            r.update(a_Pa_s_m=a,friction_pressure_Pa=friction,end_loss_pressure_Pa=end,
                     reconstructed_pressure_Pa=friction+end,
                     constitutive_pressure_relative_error=abs(friction+end-pressure)/pressure if not r['blocked'] else None,
                     peak_velocity_m_s=u*float(c['shape'].max()),
                     sampled_peak_Mach=u*float(c['shape'].max())/SOUND_SPEED,
                     peak_velocity_upper_bound_m_s=u*shape_upper(c,self.nx,self.ny),
                     peak_Mach=u*shape_upper(c,self.nx,self.ny)/SOUND_SPEED,
                     friction_dissipation_W=friction*q,end_loss_dissipation_W=end*q,
                     hydraulic_conductance_semantics='secant Qv/deltaP; nonlinear for K>0',
                     sealed_pressure_semantics='sealed branch has no throughflow law; reservoir differential supported by closure' if r['blocked'] else None)
        total=sum(r['volume_flow_m3_s'] for r in rows)
        for r in rows:r['flow_fraction']=r['volume_flow_m3_s']/total
        return rows
    def domain(self):
        out=[]
        for i,c in enumerate(self.channels):
            dh=2*c['width']*pf.H/(c['width']+pf.H);a=self.mu*pf.L/c['wmean']
            ur=2300*(self.mu/pf.RHO)/dh
            um=.1*SOUND_SPEED/shape_upper(c,self.nx,self.ny);u=min(ur,um)
            out.append({'channel':i,'Re_speed_limit_m_s':ur,'Mach_speed_limit_m_s':um,
                        'limiting_guard':'Re' if ur<=um else 'peak_Mach',
                        'nominal_pressure_limit_Pa':a*u+.5*pf.RHO*self.end_loss_K*u*u})
        upper=min(200,.999*min(r['nominal_pressure_limit_Pa'] for r in out))
        return {'lower_Pa':25.,'upper_Pa':upper,'branches':out}
    def domain_state(self,P):
        out={}
        for name,dp,blocked in [('nominal',P,()),('combined',.6*P,(1,))]:
            rr=self.hydraulic(dp,blocked)
            re=max(r['Re_Dh'] for r in rr);ma=max(r['peak_Mach'] for r in rr)
            out[name]={'max_Re_Dh':re,'max_peak_Mach':ma,'within_domain':re<2300 and ma<.1}
        return out
    def solve(self,pressure=25.,blocked=(),nz=800,details=True):
        r=super().solve(pressure,blocked,nz,details)
        rr=r['channels'] if details else self.hydraulic(pressure,blocked)
        # Original Q/(Q/P) diagnostic is supplemented and replaced by real constitutive closure.
        r['legacy_secant_pressure_identity_relative']=r['pressure_closure_relative']
        r['pressure_closure_relative']=max(x['constitutive_pressure_relative_error'] for x in rr if not x['blocked'])
        r['max_peak_Mach']=max(x['peak_Mach'] for x in rr)
        r['end_loss_K']=self.end_loss_K
        r['friction_dissipation_W']=sum(x['friction_dissipation_W'] for x in rr)
        r['end_loss_dissipation_W']=sum(x['end_loss_dissipation_W'] for x in rr)
        r['dissipation_split_relative_error']=abs(r['pressure_dissipation_W']-r['friction_dissipation_W']-r['end_loss_dissipation_W'])/r['pressure_dissipation_W']
        r['omitted_mechanical_heating_fraction_of_60W']=r['pressure_dissipation_W']/60
        r['capacity_at_uniform_base_85C_W']=60*r['G_W_K']
        r['required_uniform_base_at_60W_C']=25+60/r['G_W_K']
        r['gates']=pf.thermal_gates(r)
        r['gates'].update(dissipation_split=r['dissipation_split_relative_error']<1e-12,
                          peak_Mach=r['max_peak_Mach']<.1,Re_domain=r['max_Re_Dh']<2300,
                          branch_fraction=abs(sum(x['flow_fraction'] for x in rr)-1)<1e-12,
                          sealed_zero_enthalpy=all(x['heat_transport_W_K']==0 and x['volume_flow_m3_s']==0 for x in rr if x['blocked']) if details else True)
        return r

class Study:
    def __init__(self,design):
        self.design=design;self.t={'n16_t860':.00086,'n16_t600':.0006}[design]
        self.count=0;self.start=time.monotonic();self.cache={};self.models={}
    def model(self,K,mesh):
        key=(K,*mesh[:2])
        if key not in self.models:self.models[key]=EndLossFin(N=16,t=self.t,nx=mesh[0],ny=mesh[1],end_loss_K=K)
        return self.models[key]
    def evaluation(self,K,mesh,P,condition='combined'):
        key=(K,*mesh,float(P),condition)
        if key in self.cache:return self.cache[key]
        # Half the global budget per geometry; two geometry processes have disjoint outputs.
        if self.count>=MAX_SOLVES//2:raise RuntimeError('predeclared thermal-solve resource cap reached')
        if time.monotonic()-self.start>90*60:raise RuntimeError('predeclared wall-time resource cap reached')
        m=self.model(K,mesh);ds=m.domain_state(P)
        if not all(x['within_domain'] for x in ds.values()):raise ValueError('Re/Mach guard blocks thermal solve')
        dp=.6*P if condition=='combined' else P
        blocked=(1,) if condition=='combined' else ()
        r=m.solve(dp,blocked,nz=mesh[2],details=True)
        r.update(design_id=self.design,nominal_pressure_budget_Pa=P,condition=condition,domain_at_both_conditions=ds,
                 plan_sha256=PLAN_HASH,model_sha256=digest(__file__),accepted_operator_sha256=digest(SOURCE))
        self.count+=1
        path=pathlib.Path('runs')/self.design/f'K{K}_{mesh[0]}_{mesh[1]}_{mesh[2]}_{condition}_{self.count:03d}.json'
        save(path,r);r['record_file']=str(path);self.cache[key]=r
        print(json.dumps({'design':self.design,'K':K,'mesh':mesh,'P':P,'Q85':r['capacity_at_uniform_base_85C_W'],'condition':condition,'all_gates':all(r['gates'].values()),'seconds':r['elapsed_s'],'count':self.count}),flush=True)
        if not all(r['gates'].values()):raise RuntimeError('numerical gate failed; retained '+str(path))
        return r
    def f(self,K,mesh,P):return self.evaluation(K,mesh,P)['capacity_at_uniform_base_85C_W']-60
    def bracket(self,K,mesh,centre,halfwidth,domain):
        for attempt in range(9):
            lo=max(domain['lower_Pa'],centre-halfwidth);hi=min(domain['upper_Pa'],centre+halfwidth)
            flo=self.f(K,mesh,lo);fhi=self.f(K,mesh,hi)
            if flo<=0<=fhi:return lo,hi,flo,fhi
            halfwidth*=2
        raise RuntimeError('no sign bracket after predeclared widening')
    def root(self,K,mesh,seed=None):
        domain=self.model(K,mesh).domain();lo=domain['lower_Pa'];hi=domain['upper_Pa']
        if hi<=lo:return {'status':'no_admissible_pressure_interval','domain':domain}
        if seed is None:
            flo=self.f(K,mesh,lo);fhi=self.f(K,mesh,hi)
            initial=(lo,hi,flo,fhi)
        else:
            try:initial=self.bracket(K,mesh,seed,.01*seed,domain)
            except RuntimeError:initial=(lo,hi,self.f(K,mesh,lo),self.f(K,mesh,hi))
        if initial[2]>0 or initial[3]<0:
            return {'status':'unable_to_bracket_within_domain','domain':domain,'initial_bracket':initial}
        if seed is None:
            coarse=brentq(lambda P:self.f(K,mesh,P),initial[0],initial[1],xtol=.001,rtol=1e-10,maxiter=20)
            cb=self.bracket(K,mesh,coarse,.002,domain)
            fine=brentq(lambda P:self.f(K,mesh,P),cb[0],cb[1],xtol=.00005,rtol=1e-12,maxiter=20)
            coarse_record={'root_Pa':coarse,'bracket':cb,'coarse_to_fine_relative':abs(coarse/fine-1)}
        else:
            fine=brentq(lambda P:self.f(K,mesh,P),initial[0],initial[1],xtol=.00005,rtol=1e-12,maxiter=20)
            coarse_record=None
        fb=self.bracket(K,mesh,fine,.0001,domain)
        r=self.evaluation(K,mesh,fine)
        return {'status':'root_bracketed','K':K,'mesh':list(mesh),'domain':domain,'initial_bracket':initial,'coarse_tolerance_check':coarse_record,
                'root_Pa':fine,'root_combined_pressure_Pa':.6*fine,'fine_bracket':[{'P_Pa':x,'capacity_W':60+fx,'file':self.evaluation(K,mesh,x)['record_file']} for x,fx in [(fb[0],fb[2]),(fb[1],fb[3])]],
                'local_capacity_slope_W_Pa':(fb[3]-fb[2])/(fb[1]-fb[0]),
                'root_heat_residual_W':r['capacity_at_uniform_base_85C_W']-60,'root_record':r['record_file'],'root_domain_state':r['domain_at_both_conditions'],
                'gates':{'heat_residual':abs(r['capacity_at_uniform_base_85C_W']-60)<.001,'bracket_width':fb[1]-fb[0]<.002,'bracket_sign':fb[2]<=0<=fb[3],'local_monotonic_slope':fb[3]>fb[2],'tolerance_sensitivity':coarse_record is None or coarse_record['coarse_to_fine_relative']<.0001}}
    def run(self):
        results={'design_id':self.design,'scope':PLAN['scope'],'plan_sha256':PLAN_HASH,'status':'running','cases':[]}
        # Reproduce original failures first, retaining both accepted baseline/combined outputs.
        repro=[]
        for cond,src in [('nominal','nominal'),('combined','combined_fault')]:
            r=self.evaluation(0,(48,144,800),25,cond)
            accepted=json.loads((ROOT/'research/pressure_fin/original_freeze/study/runs'/f'{self.design}_{src}.json').read_text())
            keys=['G_W_K','volume_flow_m3_s','mass_flow_kg_s','max_Re_Dh','pressure_dissipation_W']
            errs={k:abs(r[k]/accepted[k]-1) for k in keys}
            repro.append({'condition':cond,'record':r['record_file'],'relative_differences':errs,'pass':max(errs.values())<1e-12})
        results['K0_reproduction']=repro;save(pathlib.Path('results')/(self.design+'.json'),results)
        if not all(x['pass'] for x in repro):raise RuntimeError('K0 original reproduction failed')
        for K in PLAN['scenario_K']:
            case={'K':K,'status':'running','roots':{}}
            results['cases'].append(case)
            try:
                main=self.root(K,(48,144,800));case['roots']['main']=main
                save(pathlib.Path('results')/(self.design+'.json'),results)
                if main['status']!='root_bracketed':case['status']=main['status'];continue
                P=main['root_Pa'];r=self.evaluation(K,(48,144,800),P)
                case['nominal_at_main_root_record']=self.evaluation(K,(48,144,800),P,'nominal')['record_file']
                # Values at same P isolate mesh changes in G from inverse-boundary changes.
                for name,mesh,tol,ptol in [('spatial',(64,192,800),.005,.01),('axial',(48,144,1600),.002,.005)]:
                    probe=self.evaluation(K,mesh,P)
                    refined=self.root(K,mesh,seed=P);case['roots'][name]=refined
                    case[name+'_sensitivity']={'G_relative_at_main_pressure':abs(probe['G_W_K']/r['G_W_K']-1),'record_at_main_pressure':probe['record_file'],
                        'root_P_relative':abs(refined['root_Pa']/P-1) if refined['status']=='root_bracketed' else None,
                        'G_gate_pass':abs(probe['G_W_K']/r['G_W_K']-1)<tol,
                        'root_gate_pass':refined['status']=='root_bracketed' and abs(refined['root_Pa']/P-1)<ptol}
                    save(pathlib.Path('results')/(self.design+'.json'),results)
                case['status']='numerically_verified_conditional_root' if all(x['status']=='root_bracketed' and all(x['gates'].values()) for x in case['roots'].values()) and all(case[n+'_sensitivity']['G_gate_pass'] and case[n+'_sensitivity']['root_gate_pass'] for n in ['spatial','axial']) else 'verification_failed_or_incomplete'
            except Exception as e:
                case['status']='failed_or_resource_limited';case['error']=str(e)
            save(pathlib.Path('results')/(self.design+'.json'),results)
        results.update(status='complete_pending_independent_review',new_thermal_solve_count=self.count,elapsed_s=time.monotonic()-self.start)
        save(pathlib.Path('results')/(self.design+'.json'),results)
        print('DONE '+self.design+' '+str(self.count),flush=True)

if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('design',choices=['n16_t860','n16_t600']);args=a.parse_args()
    Study(args.design).run()
