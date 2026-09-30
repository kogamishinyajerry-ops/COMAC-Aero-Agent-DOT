"""Engineering story contract: coherent cases, actual tradeoffs, no greenwash."""
import copy
import unittest
from aerolab.nacelle_story import CASE_INPUTS, engineering_story
from aerolab.nacelle_thermal import evaluate_nacelle


class NacelleStoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.story = engineering_story()

    def test_full_source_heat_shown_before_explicit_teaching_cases(self):
        story=self.story
        self.assertEqual(list(story['cases']),['source_load','source_pressure','baseline','hot_day','more_fins','redistributed_cooling'])
        self.assertEqual(story['execution'],'computed')
        self.assertEqual(story['cases']['source_load']['boundary']['heat_scale'],1)
        self.assertFalse(story['cases']['source_load']['thermal']['summary']['physically_validated'])
        for name in ('baseline','hot_day','more_fins','redistributed_cooling'):
            self.assertEqual(story['cases'][name]['boundary']['heat_scale'],.25)
        self.assertFalse(any(story['claims'].values()))
        self.assertTrue(any('not 25 percent' in note for note in story['scope']))

    def test_hot_perturbation_changes_only_ambient(self):
        base=self.story['cases']['baseline'];hot=self.story['cases']['hot_day']
        self.assertEqual(base['geometry'],hot['geometry'])
        self.assertEqual([key for key in base['boundary'] if base['boundary'][key]!=hot['boundary'][key]],['ambient_c'])
        self.assertAlmostEqual(hot['boundary']['ambient_c']-base['boundary']['ambient_c'],10)
        for name in base['thermal']['components']:
            self.assertAlmostEqual(hot['thermal']['components'][name]['temperature_c']-base['thermal']['components'][name]['temperature_c'],10)

    def test_candidates_have_identical_boundaries_and_declared_geometry_changes(self):
        base=self.story['cases']['hot_day']
        for name,count in [('more_fins',36),('redistributed_cooling',12)]:
            run=self.story['cases'][name]
            self.assertEqual(run['boundary'],base['boundary'])
            self.assertEqual({key for key in run['geometry'] if run['geometry'][key]!=base['geometry'][key]}, {'hv_fin_count'} if name == 'more_fins' else {'hv_fin_count','motor_exhaust_area_mm2'})
            self.assertEqual(run['geometry']['hv_fin_count'],count)
            self.assertNotEqual(run['metrics']['fingerprint'],base['metrics']['fingerprint'])
            self.assertEqual(run['model_sha256'],base['model_sha256'])

    def test_real_local_versus_system_tradeoff_is_retained(self):
        more=self.story['deltas_vs_hot_day']['more_fins'];less=self.story['deltas_vs_hot_day']['redistributed_cooling']
        self.assertLess(more['hv_temperature_c'],0)
        self.assertGreater(more['motor_temperature_c'],0)
        self.assertGreater(more['mass_kg'],0)
        self.assertGreater(more['motor_mix_pressure_pa'],0)
        self.assertLess(more['motor_flow_kg_s'],0)
        self.assertGreater(less['hv_temperature_c'],0)
        self.assertLess(less['motor_temperature_c'],0)
        self.assertLess(less['mass_kg'],0)
        self.assertAlmostEqual(more['mass_kg'],more['hv_pair_mass_kg'])
        self.assertGreater(less['hydraulic_dissipation_w'],0)
        self.assertLess(less['motor_mix_pressure_pa'],0)
        self.assertGreater(less['motor_flow_kg_s'],0)
        self.assertGreater(self.story['summaries']['redistributed_cooling']['min_margin_c'],0)
        self.assertGreater(self.story['summaries']['redistributed_cooling']['in_domain_negative_reference_corner_count'],0)

    def test_actual_solver_evidence_supports_every_summary(self):
        for name,run in self.story['cases'].items():
            summary=self.story['summaries'][name]
            self.assertEqual(summary['geometry_fingerprint'],run['metrics']['fingerprint'])
            self.assertEqual(summary['input_hash'],run['input_hash'])
            self.assertTrue(run['diagnostics']['conservation_pass'])
            self.assertEqual(summary['motor_temperature_c'],run['thermal']['components']['motor_winding']['temperature_c'])
            self.assertEqual(summary['min_margin_c'],run['thermal']['summary']['min_margin_c'])
            self.assertEqual(summary['scenario_min_margin_c'],run['uncertainty']['min_margin_c'])
            self.assertEqual(summary['negative_reference_corner_count'],sum(s['min_margin_c'] < 0 for s in run['uncertainty']['scenarios']))
            self.assertEqual(summary['in_domain_negative_reference_corner_count'],sum(s['within_model_limits'] and s['min_margin_c'] < 0 for s in run['uncertainty']['scenarios']))
            self.assertEqual(summary['out_of_domain_corner_count'],sum(not s['within_model_limits'] for s in run['uncertainty']['scenarios']))
            # Recompute one candidate independently from the story orchestration.
        rerun=evaluate_nacelle(**CASE_INPUTS['redistributed_cooling'])
        self.assertEqual(rerun,self.story['cases']['redistributed_cooling'])

    def test_inputs_are_not_mutated_and_identity_is_deterministic(self):
        before=copy.deepcopy(CASE_INPUTS)
        result=engineering_story()
        self.assertEqual(CASE_INPUTS,before)
        self.assertEqual(result['story_hash'],self.story['story_hash'])
        self.assertEqual(result['summaries'],self.story['summaries'])
