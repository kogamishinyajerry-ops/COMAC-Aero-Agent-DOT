import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aerolab import agent_trial as a

TASK=json.loads((a.ROOT/'research/native_agent_trial/development_task.json').read_text())

class AgentTrialTests(unittest.TestCase):
    def test_protocol_hash_and_frozen_sources(self):
        self.assertEqual(a.sha(a.PROTOCOL.read_bytes()),a.PROTOCOL_SHA)
        for path,digest in zip(a.MODEL_PATHS,a.MODEL_SHAS): self.assertEqual(a.sha((a.ROOT/path).read_bytes()),digest)

    def test_task_schema_validation(self):
        self.assertEqual(a.validate_task(copy.deepcopy(TASK)),TASK)
        mutations=[('max_base_temperature_C',float('nan')),('max_fin_mass_g',True),('inlet_temperature_C',30),('objective','optimize_global')]
        for key,value in mutations:
            t=copy.deepcopy(TASK);t[key]=value
            with self.assertRaises(ValueError): a.validate_task(t)
        for casefield,value in [('blocked_channels',[True]),('pressure_Pa',26),('heat_load_W',9),('blocked_channels',[2])]:
            t=copy.deepcopy(TASK);t['cases'][0][casefield]=value
            with self.assertRaises(ValueError): a.validate_task(t)
        t=copy.deepcopy(TASK);t['cases'][1]['case_id']=t['cases'][0]['case_id']
        with self.assertRaises(ValueError): a.validate_task(t)

    def test_geometry_hydraulic_screen(self):
        result=a.inspect_tool(Path('.'),TASK)
        rows={r['design_id']:r for r in result['candidates']}
        self.assertAlmostEqual(rows['n16_t600']['fin_only_mass_g'],26.36064)
        self.assertFalse(rows['n16_t860']['mass_requirement_pass'])
        self.assertFalse(rows['n12_t600']['hydraulic_screen'][0]['within_Re_scope'])
        self.assertFalse(result['thermal_results_computed'])
        with self.assertRaises(ValueError): a.design('n14_t600')

    def test_append_only_json_and_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'a.json';a.write(p,{'a':1})
            with self.assertRaises(ValueError): a.write(p,{'a':2})
            with self.assertRaises(ValueError): a.write(Path(tmp)/'b.json',{'a':'x'*100000})

    def test_session_initialization_and_task_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=Path(tmp)/'run'
            a.init_session(session,a.ROOT/'research/native_agent_trial/development_task.json','Initialize a disclosed development task.')
            meta,task=a.check_session(session)
            self.assertEqual(task,TASK)
            self.assertEqual(len(a.events(session)),1)
            (session/'task.json').write_text(json.dumps({**TASK,'max_fin_mass_g':40}))
            with self.assertRaisesRegex(ValueError,'task bytes changed'): a.check_session(session)

    def test_result_tamper_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=Path(tmp)/'run'
            a.init_session(session,a.ROOT/'research/native_agent_trial/development_task.json','Initialize the audit test.')
            p=session/'results/001_init.json';p.write_text('{}')
            with self.assertRaisesRegex(ValueError,'session metadata differs|result bytes changed'): a.check_session(session)

    def test_objective_and_counts_are_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=Path(tmp)/'run'
            a.init_session(session,a.ROOT/'research/native_agent_trial/development_task.json','Initialize objective gate test.')
            for d in ('n12_t600','n16_t600'):
                for c in TASK['cases']:
                    result={'design_id':d,'case_id':c['case_id'],'mesh_id':'primary','conditional_pass':True,'condition_gates':{'example':True}}
                    a.log(session,'evaluate',{},'Synthetic unit-test fixture; no real solve.',result,a.time.monotonic(),execution={'solver_started':False,'solver_completed':False})
            result=a.finalize(session,TASK,'n16_t600')
            self.assertFalse(result['objective_pass'])
            self.assertEqual(result['lighter_primary_feasible_candidates'],['n12_t600'])
            self.assertEqual(result['solver_calls'],0)
            self.assertEqual(result['evaluate_requests'],4)

    def test_metadata_tamper_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=Path(tmp)/'run'
            a.init_session(session,a.ROOT/'research/native_agent_trial/development_task.json','Initialize metadata test.')
            t={**TASK,'max_fin_mass_g':40};raw=a.dumps(t);(session/'task.json').write_bytes(raw)
            meta=a.read(session/'session.json');meta['task_sha256']=a.sha(raw);(session/'session.json').write_bytes(a.dumps(meta))
            with self.assertRaisesRegex(ValueError,'session metadata differs'): a.check_session(session)

    def test_incomplete_finalization_cannot_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=Path(tmp)/'run'
            a.init_session(session,a.ROOT/'research/native_agent_trial/development_task.json','Initialize an incomplete finalization test.')
            result=a.finalize(session,TASK,'n16_t600')
            self.assertFalse(result['conditional_acceptance_pass'])
            self.assertEqual(result['outcome'],'not_demonstrated_feasible')
            self.assertFalse(result['global_optimum_established'])

if __name__=='__main__': unittest.main()
