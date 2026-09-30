"""Budget-bounded independent hydraulic-root/accepted-thermal root evaluations.

Run only after the implementation's numerical processes have finished, and only
if evaluations fit within the predeclared global 180-solve allowance. Prioritize
the two K=2 roots, then K=1, then K=0; retain all unrun checks explicitly.
"""
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('review_hydraulic',HERE/'hydraulic_review.py')
h=importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
STUDY=HERE.parents[1]


class ScalarRootHydraulics(h.accepted.PressureFin):
    def __init__(self,coefficient,**kwargs):
        super().__init__(**kwargs)
        self.coefficient=coefficient

    def hydraulic(self,pressure,blocked=()):
        rows=super().hydraulic(pressure,blocked)
        for flow,channel in zip(rows,self.channels):
            if flow['blocked'] or self.coefficient==0:
                continue
            width,mean=channel['width'],channel['wmean']
            resistance=self.mu*h.accepted.L/mean
            speed=h.scalar_speed(pressure,resistance,self.coefficient)
            exact_speed=h.scalar_speed(pressure,self.mu*h.accepted.L/h.exact_mean(width,h.accepted.H),self.coefficient)
            q=speed*width*h.accepted.H
            flow.update(mean_speed_m_s=speed,volume_flow_m3_s=q,mass_flow_kg_s=q*h.accepted.RHO,
                        Re_Dh=speed*2*width*h.accepted.H/((width+h.accepted.H)*h.accepted.NU),
                        hydraulic_conductance_m3_s_Pa=q/pressure,flow_relative_to_exact=speed/exact_speed-1)
        total=sum(row['volume_flow_m3_s'] for row in rows)
        for row in rows:
            row['flow_fraction']=row['volume_flow_m3_s']/total
        return rows


def main():
    summaries=[json.loads((STUDY/'results'/f'{name}.json').read_text()) for name in ('n16_t860','n16_t600')]
    assert all(r['status']=='complete_pending_independent_review' for r in summaries),'Workers not complete'
    implementation_count=sum(r['new_thermal_solve_count'] for r in summaries)
    available=max(0,min(6,180-implementation_count))
    assert len(list((STUDY/'runs').rglob('*.json')))==implementation_count
    selected=[]
    for coefficient in (2,1,0):
        for summary in summaries:
            for scenario in summary['cases']:
                if scenario['K']==coefficient and scenario['roots'].get('main',{}).get('status')=='root_bracketed':
                    selected.append((summary,scenario))
    deferred=[{'design_id':summary['design_id'],'K':scenario['K'],'reason':'Frozen global thermal-solve budget'} for summary,scenario in selected[available:]]
    selected=selected[:available]
    rows=[]
    for summary,scenario in selected:
        thickness={'n16_t860':.00086,'n16_t600':.0006}[summary['design_id']]
        root=scenario['roots']['main']
        assert root['status']=='root_bracketed'
        pressure=root['root_Pa']
        model=ScalarRootHydraulics(scenario['K'],t=thickness,nx=48,ny=144)
        domain_rows=[]
        for name,dp,blocked in [('nominal',pressure,()),('combined',.6*pressure,(1,))]:
            hydraulic=model.hydraulic(dp,blocked)
            conservative_mach=max(flow['mean_speed_m_s']*min(ch['width'],h.accepted.H)**2/8*(1+1/48**2)
                /min(ch['wmean'],h.exact_mean(ch['width'],h.accepted.H))/math.sqrt(1.4*287.05*298.15)
                for flow,ch in zip(hydraulic,model.channels))
            re=max(flow['Re_Dh'] for flow in hydraulic)
            assert re<2300 and conservative_mach<.1
            domain_rows.append({'condition':name,'max_Re':re,'max_peak_Mach_bound':conservative_mach})
        independently_solved=model.solve(.6*pressure,(1,),nz=800,details=True)
        original=json.loads((STUDY/root['root_record']).read_text())
        relative_G=independently_solved['G_W_K']/original['G_W_K']-1
        heat_residual=60*independently_solved['G_W_K']-60
        numerical_gates=h.accepted.thermal_gates(independently_solved)
        checks={'reproduced_G':abs(relative_G)<1e-10,'root_heat_residual':abs(heat_residual)<.001,
                'numerical_gates':all(numerical_gates.values()),
                'sealed_zero_flow_and_enthalpy':independently_solved['channels'][1]['volume_flow_m3_s']==0 and
                independently_solved['channels'][1]['heat_transport_W_K']==0}
        rows.append({'design_id':summary['design_id'],'K':scenario['K'],'nominal_root_pressure_Pa':pressure,
                    'combined_pressure_Pa':.6*pressure,'independent_G_W_K':independently_solved['G_W_K'],
                    'relative_G_difference':relative_G,'heat_residual_W':heat_residual,'checks':checks,
                    'energy_relative_balance':independently_solved['energy_relative_balance_max'],
                    'equation_relative_residual':independently_solved['componentwise_thermal_equation_residual_relative'],
                    'domain_checks':domain_rows})
        print(json.dumps(rows[-1]),flush=True)
        evidence={'status':'running','rows':rows,'implementation_thermal_solve_count':implementation_count,
                  'review_thermal_solve_count':len(rows),'total_thermal_solve_count':implementation_count+len(rows),
                  'accepted_model_sha256':hashlib.sha256(h.SOURCE.read_bytes()).hexdigest(),
                  'review_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        Path(__file__).with_suffix('.json').write_text(json.dumps(evidence,indent=2,allow_nan=False)+'\n')
    if not rows:
        evidence={'rows':[],'implementation_thermal_solve_count':implementation_count,'review_thermal_solve_count':0,
                  'total_thermal_solve_count':implementation_count,
                  'accepted_model_sha256':hashlib.sha256(h.SOURCE.read_bytes()).hexdigest(),
                  'review_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    evidence['not_run']=deferred
    evidence['status']=('passed' if len(rows)==6 else 'passed_selected_checks_with_explicit_budget_limit') if rows and all(all(r['checks'].values()) for r in rows) else ('not_run_budget_exhausted' if not rows else 'failed')
    Path(__file__).with_suffix('.json').write_text(json.dumps(evidence,indent=2,allow_nan=False)+'\n')
    notes_path=HERE/'execution_notes.json'
    notes=json.loads(notes_path.read_text())
    notes['review_thermal_march_count']=len(rows)
    notes_path.write_text(json.dumps(notes,indent=2)+'\n')
    print(json.dumps({'status':evidence['status'],'total_thermal_solves':evidence['total_thermal_solve_count']}),flush=True)


if __name__=='__main__':
    main()
