import json
import math
from pathlib import Path
import unittest
from aerolab.evidence import read_reference
from aerolab.model import (
    BACKUP_EFFICIENCY, DESIGNS, ESSENTIAL_KW, MAX_CURRENT_A, MIN_VOLTAGE_V,
    MOTOR_EFFICIENCY, SCENARIOS, TEMPERATURE_LIMIT_C, State, allocate, compare,
    fault_state, pack_limit, phase_at, simulate, sweep, thermal_next, transition,
)


class ComponentTests(unittest.TestCase):
    def setUp(self):
        self.design = DESIGNS["reference"]
        self.faults = fault_state([], 0)
        self.phase = phase_at(100, self.design)

    def test_thermal_zero_heat_relaxes_to_ambient(self):
        result = thermal_next(80, 25, 0, .1, 20)
        self.assertAlmostEqual(result, 25 + 55 * math.exp(-.1 * 20 / 14))
        self.assertGreater(result, 25)
        self.assertLess(result, 80)

    def test_thermal_exact_subdivision(self):
        full = thermal_next(40, 25, 4, .1, 20)
        half = thermal_next(40, 25, 4, .1, 10)
        self.assertAlmostEqual(full, thermal_next(half, 25, 4, .1, 10), places=12)

    def test_empty_or_isolated_pack_cannot_supply(self):
        self.assertEqual(pack_limit(0, 24, 2, True)[0], 0)
        self.assertEqual(pack_limit(20, 24, 2, False)[0], 0)

    def test_depletion_cap_respects_chemical_energy(self):
        state, row = transition(State([.0001, 0], [25, 25], .24), self.phase,
                                self.faults, self.design, 25, 2, 1, .5)
        self.assertGreaterEqual(min(state.energy), 0)
        self.assertLessEqual(sum(row["chemical_kw"]) * 2 / 3600, .0001 + 1e-12)

    def test_lv_backup_covers_healthy_converter_without_hv(self):
        state, row = transition(State([0, 0], [25, 25], .24), self.phase,
                                self.faults, self.design, 25, 2, 1, .5)
        self.assertAlmostEqual(row["served_essential_kw"], ESSENTIAL_KW)
        self.assertAlmostEqual(state.backup, .24 - ESSENTIAL_KW / BACKUP_EFFICIENCY * 2 / 3600)
        self.assertEqual(row["served_propulsion_kw"], 0)

    def test_lv_depletion_removes_command_even_with_hv(self):
        faults = fault_state([{"t_s": 0, "type": "dcdc_failed"}], 0)
        state, row = transition(State([20, 20], [25, 25], 0), self.phase,
                                faults, self.design, 25, 2, 1, .5)
        self.assertFalse(row["command_alive"])
        self.assertEqual(row["served_propulsion_kw"], 0)
        self.assertEqual(row["served_essential_kw"], 0)
        self.assertEqual(sum(state.energy), 40)

    def test_a_or_b_can_feed_both_channels(self):
        for pack in (0, 1):
            faults = fault_state([{"t_s": 0, "type": "pack_isolated", "channel": pack}], 0)
            state, row = transition(State([20, 20], [25, 25], .24), phase_at(500, self.design),
                                    faults, self.design, 25, 2, .65, .5)
            self.assertEqual(row["pack_kw"][pack], 0)
            self.assertTrue(all(p > 0 for p in row["motor_shaft_kw"]))
            self.assertEqual(state.energy[pack], 20)

    def test_motor_fault_blocks_channel(self):
        faults = fault_state([{"t_s": 0, "type": "motor_failed", "channel": 1}], 0)
        _, row = transition(State([20, 20], [25, 25], .24), self.phase,
                            faults, self.design, 25, 2, 1, .5)
        self.assertEqual(row["motor_shaft_kw"][1], 0)
        self.assertGreater(row["unmet_propulsion_kw"], 0)

    def test_protection_caps_shaft_instead_of_overheating(self):
        _, row = transition(State([20, 20], [95, 95], .24), self.phase,
                            self.faults, self.design, 45, 2, .3, .5)
        self.assertLessEqual(max(row["temperature_c"]), TEMPERATURE_LIMIT_C + 1e-10)
        self.assertGreater(row["unmet_propulsion_kw"], 0)

    def test_actions_cannot_change_hardware(self):
        with self.assertRaises(ValueError):
            transition(State([20, 20], [25, 25], .24), self.phase,
                       self.faults, self.design, 25, 2, 1.5, .5)
        with self.assertRaises(Exception):
            self.design.mass_kg = 1

    def test_redistribution_is_not_rigid_equal_split(self):
        self.assertEqual(allocate(100, [20, 110], .5), [20, 80])

    def test_future_fault_does_not_leak(self):
        events = [{"t_s": 150, "type": "pack_isolated", "channel": 0}]
        self.assertEqual(fault_state(events, 149)["labels"], [])
        self.assertFalse(fault_state(events, 150)["pack_available"][0])


class MissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runs = {(scenario, policy): simulate(scenario, policy)
                    for scenario in SCENARIOS for policy in ("baseline", "planner")}

    def test_all_scenarios_have_valid_accounting_and_safe_bounds(self):
        for key, run in self.runs.items():
            with self.subTest(run=key):
                self.assertTrue(run["summary"]["solver_valid"])
                self.assertEqual(run["summary"]["violation_count"], 0)
                self.assertLessEqual(run["summary"]["max_temperature_c"], TEMPERATURE_LIMIT_C + 1e-7)
                self.assertLessEqual(run["summary"]["max_current_a"], MAX_CURRENT_A + 1e-7)
                self.assertGreaterEqual(run["summary"]["min_voltage_v"], MIN_VOLTAGE_V - 1e-7)
                self.assertTrue(run["validation"]["fixed_hardware"])
                for row in run["trace"]:
                    self.assertTrue(all(0 <= soc <= 1 for soc in row["pack_soc"]))
                    self.assertGreaterEqual(row["backup_kwh"], 0)
                    self.assertGreaterEqual(row["unmet_propulsion_kw"], 0)
                    self.assertLessEqual(row["served_propulsion_kw"], row["demand_kw"] + 1e-8)
                s = run["summary"]
                self.assertAlmostEqual(s["requested_propulsion_kwh"], s["served_propulsion_kwh"] + s["unmet_propulsion_kwh"])
                self.assertAlmostEqual(s["energy_used_kwh"], s["chemical_energy_kwh"])

    def test_nominal_and_hot_day_are_feasible_for_both(self):
        for scenario in ("nominal", "hot_day"):
            for policy in ("baseline", "planner"):
                self.assertTrue(self.runs[scenario, policy]["summary"]["feasible"])

    def test_protected_infeasible_distinct_from_invalid_solver(self):
        for policy in ("baseline", "planner"):
            s = self.runs["bus_cooling", policy]["summary"]
            self.assertFalse(s["feasible"])
            self.assertTrue(s["solver_valid"])
            self.assertGreater(s["unmet_propulsion_kwh"], 0)
            self.assertEqual(s["violation_count"], 0)

    def test_backups_can_expire_with_stranded_traction_energy(self):
        run = self.runs["command_loss", "baseline"]
        self.assertGreater(run["summary"]["unserved_essential_kwh"], 0)
        self.assertGreater(run["summary"]["remaining_energy_kwh"], 0)
        self.assertEqual(run["summary"]["backup_remaining_kwh"], 0)
        self.assertFalse(run["trace"][-1]["command_alive"])

    def test_repeatability_identical_full_run(self):
        self.assertEqual(self.runs["cooling_fault", "planner"], simulate("cooling_fault", "planner"))

    def test_compared_external_inputs_identical(self):
        for scenario in SCENARIOS:
            a, b = self.runs[scenario, "baseline"], self.runs[scenario, "planner"]
            self.assertEqual(a["scenario"], b["scenario"])
            self.assertEqual(a["design"], b["design"])
            self.assertEqual([r["demand_kw"] for r in a["trace"]], [r["demand_kw"] for r in b["trace"]])
            self.assertEqual([r["faults"] for r in a["trace"]], [r["faults"] for r in b["trace"]])

    def test_events_and_phase_boundaries_split_nondividing_dt(self):
        run = simulate("cooling_fault", dt_s=7, event_time_offset_s=3)
        endpoints = [r["t_s"] for r in run["trace"]]
        for value in (60, 90, 153, 240, 420, 900, 1020, 1080, 1200):
            self.assertIn(value, endpoints)
        self.assertEqual(sum(r["dt_s"] for r in run["trace"]), 1200)

    def test_timestep_sensitivity_small_for_nominal_energy(self):
        a = simulate("nominal", dt_s=1)["summary"]
        b = simulate("nominal", dt_s=2)["summary"]
        self.assertLess(abs(a["energy_used_kwh"] - b["energy_used_kwh"]), .02)
        self.assertLess(abs(a["max_temperature_c"] - b["max_temperature_c"]), .5)

    def test_parameter_variants_are_configuration_only(self):
        run = simulate("cooling_fault", "planner", ambient_c=37, demand_scale=1.04, event_time_offset_s=17)
        self.assertTrue(run["summary"]["solver_valid"])
        self.assertEqual(run["scenario"]["events"][0]["t_s"], 167)
        self.assertNotEqual(run["meta"]["input_hash"], self.runs["cooling_fault", "planner"]["meta"]["input_hash"])

    def test_invalid_inputs_rejected(self):
        for kwargs in ({"ambient_c": float('nan')}, {"ambient_c": 70}, {"dt_s": 0}, {"dt_s": True}, {"demand_scale": 4}, {"policy": "llm"}, {"design_id": "lighter_midflight"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                simulate(**kwargs)

    def test_exported_reference_is_reproducible(self):
        reference = read_reference()
        def assert_close(a, b):
            if isinstance(a, dict):
                self.assertEqual(set(a), set(b))
                for key in a:
                    assert_close(a[key], b[key])
            elif isinstance(a, list):
                self.assertEqual(len(a), len(b))
                for left, right in zip(a, b):
                    assert_close(left, right)
            elif isinstance(a, float):
                self.assertTrue(math.isclose(a, b, rel_tol=1e-11, abs_tol=1e-9), (a, b))
            else:
                self.assertEqual(a, b)
        assert_close(reference["baseline"], self.runs["cooling_fault", "baseline"])
        assert_close(reference["planner"], self.runs["cooling_fault", "planner"])

    def test_controllers_do_not_use_future_faults(self):
        for policy in ("baseline", "planner"):
            nominal = simulate("nominal", policy, ambient_c=35)
            faulted = self.runs["cooling_fault", policy]
            self.assertEqual(nominal["trace"][:75], faulted["trace"][:75])


if __name__ == "__main__":
    unittest.main()
