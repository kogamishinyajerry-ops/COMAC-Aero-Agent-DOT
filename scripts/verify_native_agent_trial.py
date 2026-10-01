#!/usr/bin/env python3
"""Read-only standard-library audit of saved native-agent trial evidence.

This rechecks hashes and arithmetic; it does NOT execute a model or a new agent.
"""
from __future__ import annotations
import argparse
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from aerolab.agent_trial import check_session,events,read,geometry,MESHES,PROTOCOL_SHA


def verify(session):
    meta,task=check_session(session)
    chain=[read(p) for p in events(session)]
    assert chain[-1]['operation']=='finalize' and chain[-1]['status']=='ok','session is not finalized'
    final=read(session/chain[-1]['result_file']);chosen=final['selected_design_id']
    results=[];cad=[];errors=[]
    for event in chain:
        record=read(session/event['result_file'])
        if event['status']=='error': errors.append(event);continue
        if event['operation']=='cad':
            for artifact in record['artifacts'].values():
                data=b''
                for part in artifact['chunks']:
                    b=(session/part['file']).read_bytes()
                    assert len(b)==part['bytes']<=250000 and hashlib.sha256(b).hexdigest()==part['sha256']
                    data+=b
                assert hashlib.sha256(data).hexdigest()==artifact['gzip_sha256']
                raw=gzip.decompress(data)
                assert len(raw)==artifact['raw_bytes'] and hashlib.sha256(raw).hexdigest()==artifact['raw_sha256']
            assert record['parameters']['fin_count']==geometry(record['design_id'])['N_fins']
            assert abs(record['thermal_geometry_mapping']['kernel_fin_only_mass_g']-geometry(record['design_id'])['fin_only_mass_g'])<1e-8
            cad.append(record)
        if event['operation']!='evaluate':continue
        r=record['result'];c=next(c for c in task['cases'] if c['case_id']==record['case_id']);g=geometry(record['design_id'])
        assert record['execution']=='live_frozen_PDE_solve' and event['execution']['solver_started'] and event['execution']['solver_completed']
        assert [r['mesh'][x] for x in ('nx','ny','nz')]==list(MESHES[record['mesh_id']])
        assert r['pressure_Pa']==c['pressure_Pa'] and r['blocked_channels']==c['blocked_channels'] and record['requirements']==c
        assert r['N_fins']==g['N_fins'] and abs(r['thickness_mm']*1e-3-g['fin_thickness_m'])<1e-15
        assert abs(r['fin_only_mass_kg']*1000-g['fin_only_mass_g'])<1e-9
        temp=task['inlet_temperature_C']+c['heat_load_W']/r['G_W_K']
        assert abs(record['required_uniform_base_temperature_C']-temp)<1e-9
        numeric={'energy':r['energy_relative_balance_max']<1e-8,'componentwise_residual':r['componentwise_thermal_equation_residual_relative']<1e-8,
                 'maximum_principle':r['min_normalized_T']>=-1e-9 and r['max_normalized_T']<=1+1e-9,'capacity_upper_bound':r['G_W_K']<=r['capacity_rate_W_K']*(1+1e-9),
                 'mass':r['mass_transport_closure_relative']<1e-12,'pressure':r['pressure_closure_relative']<1e-12,
                 'momentum':r['max_poisson_force_balance_relative']<1e-9 and r['max_poisson_relative_residual']<1e-9,
                 'hydraulic_exact':r['max_hydraulic_flow_exact_relative_error']<.002,'geometry':r['geometry_width_closure_m']<1e-14}
        assert record['numerical_gates']==numeric
        conditions={'numerical_gates':all(numeric.values()),'Re_scope':r['max_Re_Dh']<2300,'fin_mass':g['fin_only_mass_g']<=task['max_fin_mass_g'],'base_temperature':temp<=task['max_base_temperature_C']}
        assert record['condition_gates']==conditions
        assert record['conditional_pass']==(all(conditions.values()) and not record.get('wall_clock_budget_exceeded',False))
        assert abs(sum(b['volume_flow_m3_s'] for b in r['channels'])-r['volume_flow_m3_s'])<1e-15
        assert all(b['volume_flow_m3_s']==0 for b in r['channels'] if b['blocked'])
        results.append(record)
    expected=True
    for c in task['cases']:
        selected={r['mesh_id']:r for r in results if r['design_id']==chosen and r['case_id']==c['case_id']}
        if set(selected)!=set(MESHES):expected=False;continue
        G=selected['primary']['result']['G_W_K']
        expected=expected and all(r['conditional_pass'] for r in selected.values()) and abs(selected['spatial']['result']['G_W_K']/G-1)<.005 and abs(selected['axial']['result']['G_W_K']/G-1)<.002
    feasible_primary=[]
    for d in {r['design_id'] for r in results}:
        case_rows={r['case_id']:r for r in results if r['design_id']==d and r['mesh_id']=='primary'}
        if set(case_rows)=={c['case_id'] for c in task['cases']} and all(r['conditional_pass'] for r in case_rows.values()): feasible_primary.append(d)
    objective_pass=task['objective']=='find_feasible' or not any(geometry(d)['fin_only_mass_g']<geometry(chosen)['fin_only_mass_g']-1e-9 for d in feasible_primary)
    assert final['objective_pass']==objective_pass
    expected=expected and any(r['design_id']==chosen and r['passed'] for r in cad) and objective_pass and final['rejection_retention_pass'] and final['wall_budget_pass']
    assert final['conditional_acceptance_pass']==expected
    assert final['solver_calls']==sum(e.get('execution',{}).get('solver_started',False) for e in chain)
    assert final['completed_solver_calls']==len(results)
    assert final['solver_calls']<=24 and len(chain)<=40
    elapsed=(datetime.datetime.fromisoformat(chain[-1]['utc'])-datetime.datetime.fromisoformat(meta['started_utc'])).total_seconds()
    if final['conditional_acceptance_pass']:assert elapsed<=3601 # logging after finish-time gate; <=1 second serialization tolerance
    for p in session.rglob('*.json'): assert p.stat().st_size<100000
    return {'status':'passed','task_id':task['task_id'],'task_sha256':meta['task_sha256'],'protocol_sha256':PROTOCOL_SHA,'adapter_sha256':meta['adapter_sha256'],
            'selected_design_id':chosen,'engineering_conditional_acceptance':final['conditional_acceptance_pass'],'saved_solver_records_checked':len(results),'errors_retained':len(errors),
            'audit_scope':'Saved evidence hashes, fixed requirements, arithmetic, gates, mesh changes and CAD byte restoration only. No new PDE or independent physical validation. No model identity attestation.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--session',required=True,type=Path);args=p.parse_args()
    print(json.dumps(verify(args.session.resolve()),indent=2))
