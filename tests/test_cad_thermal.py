import json
import math
import unittest
from unittest.mock import patch
from dataclasses import asdict
from aerolab.geometry import Geometry, parse_geometry, geometry_metrics, GEOMETRY_PRESETS
from aerolab.cad_thermal import (thermal_benchmark, flow_properties, compare_geometry,
                                MATERIAL, AIR, parse_boundary, evaluate)
from aerolab.cad_mission import (linked_design, node_next, cooling_load,
                                MOTOR_LOSS_PER_SHAFT, CONTROLLER_LOSS_PER_SHAFT)
from aerolab.model import State, DESIGNS, phase_at, fault_state, transition, simulate, compare


class ThermalGeometryTests(unittest.TestCase):
    def test_reference_geometry_and_units(self):
        g = geometry_metrics(None)
        self.assertAlmostEqual(g['volume_mm3'], 1178985.198, places=5)
        self.assertAlmostEqual(g['mass_kg'], g['volume_mm3']*1e-9*2700)
        self.assertAlmostEqual(g['channel_heated_area_m2'], 1.389544222, places=8)
        self.assertAlmostEqual(g['flow_area_m2'], .00540257, places=8)

    def test_capacity_bound_and_fin_efficiency_once(self):
        t = thermal_benchmark()
        self.assertGreater(t['fin_efficiency'], 0)
        self.assertLess(t['fin_efficiency'], 1)
        self.assertLess(t['convective_conductance_w_k'], t['air_capacity_w_k'])
        self.assertLess(t['convective_conductance_w_k'], t['ua_w_k'])
        self.assertAlmostEqual(t['air_capacity_w_k'], .085*1007)
        self.assertLess(t['air_outlet_c'], t['base_temperature_c'])
        self.assertAlmostEqual(t['interface_temperature_c']-t['base_temperature_c'], 1.08)
        self.assertAlmostEqual(t['thermal_capacitance_j_k'], (geometry_metrics(None)['mass_kg']+.6)*900)

    def test_geometry_tradeoff_is_real_and_not_monotone_claim(self):
        results = {key: thermal_benchmark(g) for key, g in GEOMETRY_PRESETS.items()}
        self.assertEqual(len({round(t['base_temperature_c'], 4) for t in results.values()}), 3)
        self.assertGreater(results['dense']['pressure_drop_pa'], results['reference']['pressure_drop_pa'])
        self.assertGreater(results['dense']['blower_electrical_w'], results['reference']['blower_electrical_w'])
        delta = compare_geometry(asdict(parse_geometry(GEOMETRY_PRESETS['light'])))['delta']
        self.assertLess(delta['mass_kg'], 0)
        self.assertNotEqual(delta['base_temperature_c'], 0)

    def test_zero_flow_and_zero_heat(self):
        t = thermal_benchmark(boundary={'mass_flow_kg_s': 0})
        self.assertEqual(t['interface_conductance_w_k'], 0)
        self.assertEqual(t['pressure_drop_pa'], 0)
        self.assertEqual(t['blower_electrical_w'], 0)
        self.assertFalse(t['steady_state_exists'])
        self.assertIsNone(t['base_temperature_c'])
        self.assertFalse(t['within_model_limits'])
        self.assertEqual(thermal_benchmark(boundary={'mass_flow_kg_s': 0, 'heat_w': 0})['base_temperature_c'], 63)
        json.dumps(t, allow_nan=False)

    def test_low_flow_energy_balance(self):
        t = thermal_benchmark(boundary={'mass_flow_kg_s': .0001, 'heat_w': 1})
        self.assertAlmostEqual(t['air_capacity_w_k']*(t['air_outlet_c']-63), 1)
        self.assertLessEqual(t['convective_conductance_w_k'], t['air_capacity_w_k'])

    def test_pressure_power_and_flow_sensitivity(self):
        low, high = (thermal_benchmark(boundary={'mass_flow_kg_s': x}) for x in (.04, .08))
        self.assertGreater(high['pressure_drop_pa'], low['pressure_drop_pa'])
        self.assertLess(high['base_temperature_c'], low['base_temperature_c'])
        self.assertAlmostEqual(high['fluid_power_w'], high['pressure_drop_pa']*.08/AIR['density_kg_m3'])
        self.assertAlmostEqual(high['blower_electrical_w'], 2*high['fluid_power_w'])

    def test_transition_endpoints_continuous_and_explicit(self):
        reference = flow_properties(Geometry(), .085)
        for reynolds in (2300, 3000):
            flow = .085*reynolds/reference['reynolds']
            a, b = (flow_properties(Geometry(), flow*x) for x in (1-1e-8, 1+1e-8))
            self.assertLess(abs(a['nusselt']-b['nusselt']), 1e-5)
            self.assertLess(abs(a['darcy_friction_factor']-b['darcy_friction_factor']), 1e-7)
        mid = flow_properties(Geometry(), .085*2600/reference['reynolds'])
        self.assertIn('unvalidated', mid['regime'])
        self.assertTrue(any('transition' in x for x in mid['warnings']))

    def test_invalid_and_outside_physics_domain(self):
        for boundary in ({'heat_w': float('nan')}, {'mass_flow_kg_s': -.1}, {'extra': 2}, {'inlet_c': True}):
            with self.assertRaises(ValueError):
                parse_boundary(boundary)
        tiny = Geometry(width_mm=20, fin_count=2, fin_thickness_mm=9.875, fin_height_mm=2)
        result = thermal_benchmark(tiny, {'mass_flow_kg_s': .01})
        self.assertFalse(result['within_model_limits'])
        self.assertTrue(any('Mach' in w for w in result['warnings']))
        self.assertFalse(thermal_benchmark(boundary={'mass_flow_kg_s': 1e-5})['within_model_limits'])
        with self.assertRaises(ValueError):
            linked_design(DESIGNS['reference'], tiny)

    def test_large_pressure_fraction_rejected_for_mission(self):
        g=Geometry(length_mm=1000,width_mm=54,fin_height_mm=150,fin_thickness_mm=.2,fin_count=120)
        t=flow_properties(g,.10625)
        self.assertGreater(t['pressure_drop_fraction'],.1)
        self.assertFalse(t['within_flow_limits'])
        with self.assertRaises(ValueError):
            linked_design(DESIGNS['reference'],g)

    def test_evidence_input_and_model_identity(self):
        a = evaluate()
        b = evaluate({'fin_count': 40})
        self.assertNotEqual(a['input_hash'], b['input_hash'])
        self.assertEqual(a['model_sha256'], b['model_sha256'])
        self.assertEqual(a['metrics']['fingerprint'], a['cad']['geometry_fingerprint'])
        self.assertTrue(a['thermal']['nasa_reference']['not_validation'])
        self.assertFalse(b['thermal']['nasa_reference']['applicable_geometry_and_boundary'])


class CoupledMissionTests(unittest.TestCase):
    def test_split_losses_and_thermal_energy(self):
        design = linked_design(DESIGNS['reference'], {})
        state = State([20,20],[40,40],.24,[45,45])
        end, row = transition(state, phase_at(100,design), fault_state([],0), design,25,2,.65,.5)
        for i, shaft in enumerate(row['motor_shaft_kw']):
            self.assertAlmostEqual(row['motor_loss_kw'][i]+row['controller_loss_kw'][i], shaft*(1/.93-1))
            self.assertAlmostEqual((row['motor_loss_kw'][i]-row['motor_rejected_heat_kw'][i])*2, 14*(end.temperatures[i]-40))
            self.assertAlmostEqual((row['controller_loss_kw'][i]-row['controller_rejected_heat_kw'][i])*2, row['controller_thermal_capacity_kj_k']*(end.controllers[i]-45))
            self.assertEqual(row['temperature_c'][i], max(end.controllers[i], end.temperatures[i]))
        self.assertAlmostEqual(row['drivetrain_balance_error_kw'], 0)
        self.assertAlmostEqual(row['fan_kw'], row['controller_blower_kw']+row['motor_fan_kw'])

    def test_no_hv_has_no_powered_flow(self):
        design = linked_design(DESIGNS['reference'], {})
        state = State([0,0],[30,30],.24,[30,30])
        _, row = transition(state, phase_at(100,design), fault_state([],0),design,25,2,1,.5)
        self.assertEqual(row['fan_kw'],0)
        self.assertEqual(row['controller_flow_kg_s'],[0,0])
        self.assertEqual(row['served_propulsion_kw'],0)

    def test_limited_hv_clips_flow_with_power(self):
        design = linked_design(DESIGNS['reference'], {})
        state = State([.00023,.00023],[30,30],.24,[30,30])
        _, row = transition(state, phase_at(100,design), fault_state([],0),design,25,2,1,.5)
        self.assertLess(row['cooling'][0], 1)
        self.assertLessEqual(row['fan_kw']+row['served_essential_kw'],sum(row['pack_kw'])+1e-9)
        self.assertAlmostEqual(row['controller_flow_kg_s'][0], .085*.8*row['cooling'][0])

    def test_closed_form_node_zero_flow_and_subdivision(self):
        self.assertEqual(node_next(25,25,1,0,2,10),30)
        full = node_next(40,25,2,.05,3.4,20)
        half = node_next(40,25,2,.05,3.4,10)
        self.assertAlmostEqual(full,node_next(half,25,2,.05,3.4,10),places=12)

    def test_reference_and_variant_change_mission_fixed_hardware(self):
        ref = simulate('nominal', cad_geometry={})
        light = simulate('nominal',cad_geometry=asdict(parse_geometry(GEOMETRY_PRESETS['light'])))
        self.assertTrue(ref['validation']['fixed_hardware'])
        self.assertTrue(light['summary']['solver_valid'])
        self.assertNotEqual(ref['meta']['input_hash'], light['meta']['input_hash'])
        self.assertNotEqual(ref['summary']['max_controller_temperature_c'],light['summary']['max_controller_temperature_c'])
        self.assertNotEqual(ref['summary']['controller_blower_energy_kwh'],light['summary']['controller_blower_energy_kwh'])
        self.assertAlmostEqual(ref['design']['mass_kg'],312+2*geometry_metrics(None)['mass_kg']+2.2)
        for run in (ref,light):
            self.assertAlmostEqual(run['summary']['energy_used_kwh'],run['summary']['chemical_energy_kwh'])
            self.assertEqual(run['summary']['violation_count'],0)
            self.assertEqual(run['meta']['model_kind'],'cad_controller_motor_split')

    def test_split_model_faults_and_timestep(self):
        for scenario in ('cooling_fault','bus_cooling','command_loss','inverter_loss'):
            result = simulate(scenario,cad_geometry={})
            self.assertTrue(result['summary']['solver_valid'])
            self.assertEqual(result['summary']['violation_count'],0)
        a,b=(simulate('nominal',dt_s=dt,cad_geometry={}) for dt in (1,2))
        self.assertLess(abs(a['summary']['energy_used_kwh']-b['summary']['energy_used_kwh']),.05)
        self.assertLess(abs(a['summary']['max_controller_temperature_c']-b['summary']['max_controller_temperature_c']),1)

    def test_legacy_is_separate_and_invalid_cad_rejected(self):
        legacy=simulate('nominal')
        self.assertEqual(legacy['meta']['model_kind'],'synthetic')
        self.assertNotIn('controller_temperature_c',legacy['trace'][0])
        with self.assertRaises(ValueError):
            simulate(cad_geometry={'fin_count':3.5})
