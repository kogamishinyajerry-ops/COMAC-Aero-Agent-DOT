"""Independent equation/conservation checks for the uncalibrated nacelle ROM."""
import copy
import json
import math
import unittest
from unittest.mock import patch

from aerolab.nacelle_geometry import parse_nacelle, nacelle_metrics
from aerolab.nacelle_thermal import (
    AIR, BRANCHES, HEAT_LOADS, DEFAULT_BOUNDARY, evaluate_nacelle,
    compare_nacelle, nacelle_boundary_catalog, parse_nacelle_boundary,
    _pressure_drop, _flow_for_pressure, _run, _validate_metrics,
    _uniform_flux_solution, _friction_nusselt, _branch_transport, SOURCE_CASES,
)


class NacelleBoundaryTests(unittest.TestCase):
    def test_partial_defaults_explicit_invalid_and_unknown(self):
        self.assertEqual(parse_nacelle_boundary(), DEFAULT_BOUNDARY)
        self.assertEqual(parse_nacelle_boundary({"heat_load": "mcp"})["heat_load"], "mcp")
        for boundary in ([], "peak", {"unknown": 2}, {"airspeed_m_s": None},
                         {"heat_load": "unknown"}, {"heat_load": []},
                         {"heat_scale": True}, {"ambient_c": float("nan")},
                         {"density_kg_m3": float("inf")}, {"loss_multiplier": 0},
                         {"airspeed_m_s": -1}, {"ambient_c": 10**1000}):
            with self.subTest(boundary=boundary), self.assertRaises(ValueError):
                parse_nacelle_boundary(boundary)
        for field in nacelle_boundary_catalog()["fields"]:
            if field["type"] == "number":
                for value in (field["min"], field["max"]):
                    self.assertEqual(parse_nacelle_boundary({field["name"]: value})[field["name"]], value)

    def test_missing_channel_and_invalid_metric_rejected(self):
        metrics = nacelle_metrics(None)
        _validate_metrics(metrics)
        missing = copy.deepcopy(metrics)
        del missing["channels"]["motor_internal"]
        with self.assertRaisesRegex(ValueError, "missing channel"):
            _validate_metrics(missing)
        bad = copy.deepcopy(metrics)
        bad["channels"]["motor_internal"]["area_m2"] = float("nan")
        with self.assertRaises(ValueError):
            _validate_metrics(bad)
        bad = copy.deepcopy(metrics)
        bad["channels"]["motor_internal"]["hydraulic_diameter_m"] *= 2
        with self.assertRaisesRegex(ValueError, "hydraulic diameter"):
            _validate_metrics(bad)

    def test_contracted_serial_section_is_in_mach_and_reynolds_guards(self):
        channel = {"area_m2": .1, "wetted_perimeter_m": 1.0, "hydraulic_diameter_m": .4,
                   "length_m": 1.0, "heated_area_m2": .5}
        channel["segments"] = [dict(channel, area_m2=.001, wetted_perimeter_m=.2, hydraulic_diameter_m=.02)]
        result = _branch_transport(channel, 2, 1)
        self.assertLess(result["velocity_m_s"], 30)
        self.assertGreater(result["mach_approx"], .3)
        self.assertGreater(result["max_section_reynolds"], 1e6)
        self.assertLess(result["reynolds"], 1e6)


class AnalyticalThermalBenchmarks(unittest.TestCase):
    def test_uniform_flux_two_wall_closed_form_and_independent_march(self):
        # 150 W / 10 W/K = 15 K air rise; each wall has its own Q/(h A).
        result = _uniform_flux_solution(20, 10, 100, {"a": 1, "b": 2}, {"a": 100, "b": 50})
        self.assertEqual(result["air_mean_c"], 27.5)
        self.assertEqual(result["surface_mean_c"], {"a": 28.5, "b": 27.75})
        self.assertEqual(result["surface_max_c"], {"a": 36, "b": 35.25})
        for cells in (1, 4, 16, 64):
            # Independent finite-volume balance uses local heat and local area.
            air, wall_integral = 20.0, 0.0
            for _ in range(cells):
                next_air = air + (100 / cells + 50 / cells) / 10
                wall_integral += (.5 * (air + next_air) + (100 / cells) / (100 / cells)) / cells
                air = next_air
            self.assertAlmostEqual(air, 35)
            self.assertAlmostEqual(wall_integral, result["surface_mean_c"]["a"])
            self.assertAlmostEqual(air + 100 / (100 * 1), result["surface_max_c"]["a"])
        for sample in result["samples"]:
            self.assertEqual(sample["air_c"], 20 + 15 * sample["flow_fraction"])

    def test_exact_circular_uniform_flux_laminar_limit(self):
        # Independent Simpson integration of the analytical parabolic-velocity
        # pipe solution: (Tw-T(r))*k/(q''R) = 3/4-r^2+r^4/4, r in [0,1].
        n = 200
        def integrate(fn):
            return sum((1 if i in (0, n) else 4 if i % 2 else 2) * fn(i / n) for i in range(n + 1)) / (3 * n)
        bulk_deficit = integrate(lambda r: (.75 - r*r + r**4 / 4) * (1-r*r) * r) / integrate(lambda r: (1-r*r) * r)
        independent_nu = 2 / bulk_deficit
        friction, nu, _ = _friction_nusselt(1000, .71, uniform_flux=True)
        self.assertAlmostEqual(independent_nu, nu, places=7)
        self.assertEqual(friction, .064)
        self.assertEqual(_friction_nusselt(1000, .71)[1], 3.66)

    def test_gnielinski_hand_calculated_equation_case(self):
        # Re=10000, Pr=0.71, smooth f=0.0314798027567467; this checks
        # equation implementation only, never applicability to an X-57 motor.
        f, nu, regime = _friction_nusselt(10000, .71)
        self.assertAlmostEqual(f, .0314798027567467, places=13)
        expected = (.0314798027567467 / 8) * 9000 * .71 / (1 + 12.7 * math.sqrt(.0314798027567467 / 8) * (.71**(2/3)-1))
        self.assertAlmostEqual(nu, expected, places=11)
        self.assertEqual(regime, "turbulent_equivalent_duct")


class NacelleNetworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metrics = nacelle_metrics(None)
        cls.base = evaluate_nacelle()

    def run_case(self, geometry=None, boundary=None):
        return _run(nacelle_metrics(geometry), parse_nacelle_boundary(boundary))

    def test_source_loads_and_matching_cad_ids(self):
        self.assertEqual(HEAT_LOADS["peak"], {"winding_w": 5237., "magnet_w": 582., "hv_each_w": 810., "lv_each_w": 30.})
        self.assertEqual(self.base["thermal"]["summary"]["total_heat_w"], 7499.)
        self.assertEqual(sum(c["heat_w"] for c in self.base["thermal"]["components"].values()), 7499.)
        self.assertEqual(self.base["geometry"], parse_nacelle().to_dict())
        self.assertEqual(self.base["metrics"]["fingerprint"], self.metrics["fingerprint"])
        for name, node in self.base["thermal"]["components"].items():
            self.assertEqual(node["thermal_node"], name)
            self.assertIn(name, self.metrics["components"])
        self.assertIsNone(self.base["thermal"]["components"]["cmc_left_lv"]["limit_c"])

    def test_pressure_equations_and_internal_mass_balance(self):
        result = self.base
        branches = result["flow"]["branches"]
        for name, branch in branches.items():
            m = branch["mass_flow_kg_s"]
            q = _pressure_drop(m, self.metrics["channels"][name], result["boundary"]["density_kg_m3"], branch["minor_loss_k"])
            self.assertAlmostEqual(q, branch["pressure_drop_pa"], places=6)
            # Independently sum incidence at each unknown-pressure node.
        for node in ("inlet_plenum", "motor_mix", "lower_mix"):
            balance = sum((1 if b["to_node"] == node else -1 if b["from_node"] == node else 0) * b["mass_flow_kg_s"] for b in branches.values())
            self.assertLess(abs(balance), 1e-8)
        self.assertAlmostEqual(result["flow"]["total_inlet_kg_s"], result["flow"]["total_outlet_kg_s"], places=8)
        self.assertTrue(result["diagnostics"]["converged"])

    def test_pressure_monotonic_inverse_and_no_fan(self):
        ch = self.metrics["channels"]["motor_internal"]
        drops = [_pressure_drop(m, ch, 1.02, 2.5) for m in (.001, .01, .1, .5)]
        self.assertEqual(drops, sorted(drops))
        for m in (-.5, -.01, 0, .001, .1):
            self.assertAlmostEqual(_flow_for_pressure(_pressure_drop(m, ch, 1.02, 2.5), ch, 1.02, 2.5), m, places=10)
        self.assertNotIn("blower_electrical_w", self.base["flow"])
        self.assertGreater(self.base["flow"]["hydraulic_dissipation_w"], 0)

    def test_heat_capacity_and_heat_energy_mixing(self):
        result = self.base
        cp = AIR["specific_heat_j_kg_k"]
        for branch in result["flow"]["branches"].values():
            self.assertAlmostEqual(abs(branch["mass_flow_kg_s"]) * cp * (branch["outlet_c"] - branch["inlet_c"]), branch["heat_w"], places=7)
            self.assertLessEqual(branch["convective_conductance_w_k"], branch["air_capacity_w_k"])
            self.assertLessEqual(branch["convective_conductance_w_k"], branch["ua_w_k"] + 1e-12)
        branches = result["flow"]["branches"]
        internal, bypass = branches["motor_internal"], branches["motor_bypass"]
        self.assertAlmostEqual(bypass["heat_w"], 582 / 2)
        slots = branches["motor_slots"]
        self.assertAlmostEqual(internal["heat_w"] + slots["heat_w"], 5237 + 582 / 2)
        mixed = sum(b["mass_flow_kg_s"] * b["outlet_c"] for b in (internal, slots, bypass)) / sum(b["mass_flow_kg_s"] for b in (internal, slots, bypass))
        self.assertAlmostEqual(result["flow"]["nodes"]["motor_mix"]["temperature_c"], mixed, places=8)
        self.assertAlmostEqual(branches["cmc_hv_left"]["inlet_c"], mixed)
        self.assertEqual(branches["lv_fresh_left"]["inlet_c"], result["boundary"]["ambient_c"])
        self.assertAlmostEqual(result["diagnostics"]["energy_removed_w"], 7499., places=5)
        self.assertTrue(result["diagnostics"]["conservation_pass"])

    def test_geometry_intake_fin_and_bypass_sensitivity(self):
        base = self.base
        intake = self.run_case({"main_inlet_height_mm": 36})
        fins = self.run_case({"hv_fin_count": 34})
        bypass = self.run_case({"motor_bypass_gap_mm": 40})
        self.assertGreater(intake["flow"]["total_inlet_kg_s"], base["flow"]["total_inlet_kg_s"])
        self.assertNotAlmostEqual(fins["flow"]["branches"]["cmc_hv_left"]["mass_flow_kg_s"], base["flow"]["branches"]["cmc_hv_left"]["mass_flow_kg_s"])
        self.assertNotAlmostEqual(fins["thermal"]["components"]["cmc_left_hv"]["temperature_c"], base["thermal"]["components"]["cmc_left_hv"]["temperature_c"])
        self.assertNotEqual(nacelle_metrics({"hv_fin_count": 34})["mass_kg"], self.metrics["mass_kg"])
        self.assertGreater(bypass["flow"]["branches"]["motor_bypass"]["mass_flow_kg_s"], base["flow"]["branches"]["motor_bypass"]["mass_flow_kg_s"])
        self.assertNotAlmostEqual(bypass["flow"]["branches"]["motor_internal"]["mass_flow_kg_s"], base["flow"]["branches"]["motor_internal"]["mass_flow_kg_s"])
        for result in (intake, fins, bypass):
            self.assertTrue(result["diagnostics"]["conservation_pass"])

    def test_airspeed_sensitivity_and_lv_is_separately_cooled(self):
        fast = self.run_case(boundary={"airspeed_m_s": 60})
        self.assertGreater(fast["flow"]["total_inlet_kg_s"], self.base["flow"]["total_inlet_kg_s"])
        self.assertLess(fast["thermal"]["components"]["motor_winding"]["temperature_c"], self.base["thermal"]["components"]["motor_winding"]["temperature_c"])
        small_lv = self.run_case({"upper_inlet_height_mm": 16})
        self.assertLess(small_lv["flow"]["branches"]["lv_fresh_left"]["mass_flow_kg_s"], self.base["flow"]["branches"]["lv_fresh_left"]["mass_flow_kg_s"])
        self.assertGreater(small_lv["thermal"]["components"]["cmc_left_cpu"]["temperature_c"], self.base["thermal"]["components"]["cmc_left_cpu"]["temperature_c"])
        self.assertEqual(small_lv["flow"]["branches"]["lv_fresh_left"]["heat_exchange_hydraulic_diameter_m"], self.base["flow"]["branches"]["lv_fresh_left"]["heat_exchange_hydraulic_diameter_m"])

    def test_zero_flow_never_fabricates_equilibrium(self):
        result = self.run_case(boundary={"airspeed_m_s": 0})
        self.assertEqual(result["flow"]["total_inlet_kg_s"], 0)
        self.assertFalse(result["thermal"]["summary"]["steady_state_exists"])
        self.assertIsNone(result["thermal"]["summary"]["max_temperature_c"])
        self.assertFalse(result["diagnostics"]["steady_energy_balance_evaluable"])
        self.assertEqual(result["diagnostics"]["energy_residual_w"], 7499)
        for component in result["thermal"]["components"].values():
            self.assertIsNone(component["temperature_c"])
        cold = self.run_case(boundary={"airspeed_m_s": 0, "heat_scale": 0})
        self.assertTrue(cold["thermal"]["summary"]["steady_state_exists"])
        self.assertEqual(cold["thermal"]["summary"]["max_temperature_c"], 35.9)
        self.assertTrue(cold["diagnostics"]["conservation_pass"])
        json.dumps(result, allow_nan=False)

    def test_reverse_flow_is_signed_and_conserves(self):
        result = self.run_case(boundary={"lv_ram_recovery": 0, "exhaust_suction_coefficient": 0})
        self.assertLess(result["flow"]["branches"]["lv_fresh_left"]["mass_flow_kg_s"], 0)
        self.assertTrue(any("reverse" in w for w in result["warnings"]))
        self.assertTrue(result["diagnostics"]["conservation_pass"])
        self.assertGreater(result["flow"]["branches"]["lv_fresh_left"]["inlet_c"], 35.9)

    def test_motor_axial_coordinate_follows_reversed_flow(self):
        result = self.run_case(boundary={"ram_recovery": 0, "bypass_propeller_pressure_pa": 1000})
        for name in ("motor_internal", "motor_slots"):
            branch = result["flow"]["branches"][name]
            self.assertLess(branch["mass_flow_kg_s"], 0)
            self.assertEqual(branch["axial_heat_balance"]["flow_direction"], "reversed")
            self.assertEqual(branch["actual_from_node"], "motor_mix")
            self.assertEqual(branch["axial_heat_balance"]["samples"][0]["air_c"], branch["inlet_c"])
            self.assertEqual(branch["axial_heat_balance"]["samples"][-1]["air_c"], branch["outlet_c"])
        self.assertTrue(result["diagnostics"]["conservation_pass"])

    def test_motor_slots_and_multiwall_energy_are_distinct(self):
        branches = self.base["flow"]["branches"]
        self.assertGreater(branches["motor_slots"]["mass_flow_kg_s"], 0)
        self.assertEqual(branches["motor_slots"]["from_node"], branches["motor_internal"]["from_node"])
        self.assertEqual(branches["motor_slots"]["to_node"], branches["motor_internal"]["to_node"])
        q_winding = self.base["thermal"]["components"]["motor_winding"]["heat_by_branch_w"]
        for name in ("motor_internal", "motor_slots"):
            branch = branches[name]
            surfaces = self.metrics["channels"][name]["heated_surfaces_m2"]
            wall_heat = {key: branch["h_w_m2_k"] * area * (branch["heated_surface_temperatures_c"][key] - branch["outlet_c"]) for key, area in surfaces.items()}
            self.assertAlmostEqual(wall_heat["motor_winding"], q_winding[name], places=7)
            self.assertAlmostEqual(sum(wall_heat.values()), branch["heat_w"], places=7)
            self.assertEqual(branch["heat_boundary"], "uniform_axial_heat_flux")
            axial = branch["axial_heat_balance"]
            for sample in axial["samples"]:
                expected_air = branch["inlet_c"] + sample["flow_fraction"] * branch["heat_w"] / branch["air_capacity_w_k"]
                self.assertAlmostEqual(sample["air_c"], expected_air)
                self.assertAlmostEqual(sum(branch["h_w_m2_k"] * area * (sample["wall_c"][key] - expected_air) for key, area in surfaces.items()), branch["heat_w"], places=7)
        gap_walls = branches["motor_internal"]["heated_surface_temperatures_c"]
        self.assertNotAlmostEqual(gap_walls["motor_winding"], gap_walls["motor_magnet"])

    def test_source_diagnostic_is_not_a_fitted_boundary(self):
        source = self.base["source_flow_diagnostic"]
        self.assertAlmostEqual(source["published_kg_s"]["motor_internal_total"], (.100 + .458) * .45359237)
        self.assertFalse(source["used_to_fit_coefficients"])
        self.assertFalse(source["validation"])
        self.assertNotAlmostEqual(source["computed_kg_s"]["motor_internal_total"], source["published_kg_s"]["motor_internal_total"])
        self.assertEqual(source["computed_kg_s"]["motor_slots"], self.base["flow"]["branches"]["motor_slots"]["mass_flow_kg_s"])

    def test_source_pressure_preset_has_separate_feeds_and_no_double_count(self):
        preset = next(p for p in nacelle_boundary_catalog()["presets"] if p["id"] == "source_pressure_initial_climb")
        b = parse_nacelle_boundary(preset["boundary"])
        result = self.run_case(boundary=b)
        psi = 6894.757293168
        dynamic = .5 * b["density_kg_m3"] * b["airspeed_m_s"] ** 2
        nodes = result["flow"]["nodes"]
        self.assertAlmostEqual(nodes["main_ram"]["pressure_pa"], dynamic + .13 * psi)
        self.assertAlmostEqual(nodes["bypass_ram"]["pressure_pa"], dynamic + .08 * psi)
        self.assertAlmostEqual(nodes["lv_ram"]["pressure_pa"], dynamic + .005 * psi)
        self.assertEqual(result["flow"]["branches"]["motor_bypass"]["from_node"], "bypass_ram")
        self.assertTrue(result["diagnostics"]["conservation_pass"])
        boost = self.run_case(boundary={"airspeed_m_s": 0, "main_propeller_pressure_pa": 500, "bypass_propeller_pressure_pa": 500, "lv_propeller_pressure_pa": 500})
        self.assertGreater(boost["flow"]["total_inlet_kg_s"], 0)
        self.assertTrue(boost["diagnostics"]["conservation_pass"])

    def test_three_source_cases_are_unfitted_context_and_boundary_modes(self):
        for preset in nacelle_boundary_catalog()["presets"]:
            if not preset["id"].startswith("source_pressure_"):
                continue
            result = evaluate_nacelle(boundary=preset["boundary"])
            source = result["source_flow_diagnostic"]
            case = SOURCE_CASES[source["reference_case"]]
            self.assertTrue(source["matched_nominal_flight_inputs"])
            self.assertFalse(source["matched_geometry_or_thermal_nodes"])
            self.assertFalse(source["validation"])
            self.assertEqual(source["boundary_mode"], "source_pressure_sensitivity")
            self.assertEqual(source["published_kg_s"]["motor_gap"], case["motor_flow_lbm_s"][0] * .45359237)
            self.assertEqual(result["source_temperature_diagnostic"]["published_analysis_c"]["motor_winding"], case["temperature_c"][0])
            # Resolve each source static exit independently; source data rounded.
            psi = 6894.757293168
            for node, offset in zip(("top_exhaust", "lower_exhaust"), case["exit_static_offsets_psi"]):
                self.assertAlmostEqual(result["flow"]["nodes"][node]["pressure_pa"], offset * psi)
        modified = evaluate_nacelle(boundary={"heat_scale": .25})
        self.assertFalse(modified["source_temperature_diagnostic"]["matched_nominal_flight_inputs"])

    def test_patch_resistance_budget_and_required_ua_are_algebraic_only(self):
        result = self.base
        for budget in result["thermal"]["motor_patch_budget"].values():
            self.assertAlmostEqual(budget["inlet_c"] + sum(budget["rise_c"].values()), budget["temperature_c"])
            wall = result["flow"]["branches"][budget["branch_id"]]["heated_surface_temperatures_c"][budget["component"]]
            self.assertAlmostEqual(wall + budget["rise_c"]["solid_conduction"] + budget["rise_c"]["contact"], budget["temperature_c"])
            for closure in budget["fixed_flow_target_closure"].values():
                if closure["possible_by_convection_alone_at_fixed_flow"]:
                    self.assertAlmostEqual(budget["infinite_h_temperature_floor_c"] + budget["heat_w"] / closure["required_patch_ua_w_k"], closure["target_c"])
                else:
                    self.assertIsNone(closure["required_patch_ua_w_k"])
        slot = result["thermal"]["motor_patch_budget"]["motor_winding:motor_slots"]
        self.assertGreater(slot["rise_c"]["convection"], slot["rise_c"]["solid_conduction"] + slot["rise_c"]["contact"])
        # An optimistic contact-free model cannot remove its convection deficit.
        self.assertGreater(slot["temperature_c"] - slot["rise_c"]["solid_conduction"] - slot["rise_c"]["contact"], 200)

    def test_thermal_guard_is_a_fixed_property_heat_scale_not_a_power_limit(self):
        scale = self.base["diagnostics"]["heat_scale_to_200c_guard_at_fixed_flow"]
        result = self.run_case(boundary={"heat_scale": scale})
        self.assertAlmostEqual(result["thermal"]["summary"]["max_temperature_c"], 200, places=8)
        self.assertFalse(result["diagnostics"]["correlation_applicability"]["actual_geometry_validated"])
        quarter = self.run_case(boundary={"heat_scale": .25})
        for name, node in self.base["thermal"]["components"].items():
            self.assertAlmostEqual(quarter["thermal"]["components"][name]["temperature_c"] - 35.9, .25 * (node["temperature_c"] - 35.9))

    def test_real_lv_transition_speed_exceeds_inlet_and_exchange(self):
        # Reviewer reproduction: a loft-section throat can be faster than both
        # the scoop aperture and backplate. It must invalidate the Mach guard.
        geometry = {"upper_inlet_height_mm": 15, "backplate_gap_mm": 10, "cmc_tilt_deg": 60}
        boundary = {"density_kg_m3": .3, "airspeed_m_s": 80, "lv_propeller_pressure_pa": 3000, "heat_scale": 0}
        result = self.run_case(geometry, boundary)
        branch = result["flow"]["branches"]["lv_fresh_left"]
        sound = math.sqrt(1.4 * 287.05 * (35.9 + 273.15))
        metrics = nacelle_metrics(geometry)["channels"]["lv_fresh_left"]
        speeds = [abs(branch["mass_flow_kg_s"]) / (.3 * section["area_m2"])
                  for section in metrics["segments"] + metrics["section_stations"]]
        self.assertGreater(max(speeds) / sound, .3)
        self.assertLess(max(branch["velocity_m_s"], branch["heat_exchange_velocity_m_s"]) / sound, .3)
        self.assertAlmostEqual(branch["mach_approx"], max(speeds) / sound)
        self.assertEqual(len(branch["section_transport"]), 1 + len(metrics["segments"]) + len(metrics["section_stations"]) + 1)
        self.assertFalse(result["thermal"]["summary"]["within_model_limits"])
        self.assertEqual(result["thermal"]["summary"]["result_status"], "out_of_domain_diagnostic")

    def test_reduced_load_is_optional_heat_fraction_not_power_claim(self):
        catalog = nacelle_boundary_catalog()
        preset = next(p for p in catalog["presets"] if p["id"] == "reduced_load_screening")
        self.assertEqual(catalog["defaults"]["heat_scale"], 1)
        self.assertEqual(preset["boundary"]["heat_scale"], .25)
        result = self.run_case(boundary=preset["boundary"])
        summary = result["thermal"]["summary"]
        self.assertAlmostEqual(summary["total_heat_w"], .25 * 7499)
        self.assertTrue(result["diagnostics"]["conservation_pass"])
        self.assertTrue(summary["within_model_limits"])
        self.assertFalse(summary["physically_validated"])
        self.assertEqual(summary["result_status"], "uncalibrated_screening_result")
        self.assertIn("not one quarter aircraft/motor power", preset["note"])

    def test_magnet_conduction_uses_each_heated_patch_area(self):
        magnet = self.base["thermal"]["components"]["motor_magnet"]
        geometry = self.metrics["components"]["motor_magnet"]
        for patch, wall in (("inner", self.base["flow"]["branches"]["motor_internal"]["heated_surface_temperatures_c"]["motor_magnet"]),
                            ("outer", self.base["flow"]["branches"]["motor_bypass"]["exchange_surface_c"])):
            resistance = geometry["conduction_length_m"] / (8 * geometry["conduction_patch_areas_m2"][patch])
            self.assertAlmostEqual(magnet["patch_conduction_resistance_k_w"][patch], resistance)
            expected = wall + .5 * 582 * (resistance + magnet["patch_contact_resistance_k_w"][patch])
            self.assertAlmostEqual(magnet[patch + "_surface_c"], expected)
        self.assertAlmostEqual(sum(geometry["conduction_patch_areas_m2"].values()), geometry["conduction_area_m2"])

    def test_near_reversal_pressure_corner_retains_precision(self):
        boundary = {"airspeed_m_s": 95.66951893533287, "ambient_c": -27.52314197559522,
            "density_kg_m3": .3020024544768474, "ram_recovery": .32966927352260567,
            "bypass_ram_recovery": .7438869254892153, "lv_ram_recovery": .27296258101365223,
            "main_propeller_pressure_pa": 1322.1632527033707, "bypass_propeller_pressure_pa": 1422.047559935405,
            "lv_propeller_pressure_pa": 2708.847827410445, "exhaust_suction_coefficient": .18442506702231332,
            "motor_exhaust_suction_coefficient": -.18468037997687625, "heat_scale": .1736873104794845,
            "loss_multiplier": .6717565537538452, "contact_multiplier": 2.762784924197469}
        result = self.run_case(boundary=boundary)
        self.assertTrue(result["diagnostics"]["converged"])
        self.assertLess(result["diagnostics"]["max_mass_residual_kg_s"], 1e-11)
        self.assertTrue(result["diagnostics"]["conservation_pass"])
        json.dumps(result, allow_nan=False)

    def test_identity_uses_imported_source_snapshots(self):
        from aerolab.nacelle_geometry import GEOMETRY_SOURCE_SHA256
        from aerolab.nacelle_thermal import THERMAL_SOURCE_SHA256, MODEL_SOURCE_SHA256
        self.assertEqual(self.base["module_source_sha256"]["nacelle_geometry.py"], GEOMETRY_SOURCE_SHA256)
        self.assertEqual(self.base["module_source_sha256"]["nacelle_thermal.py"], THERMAL_SOURCE_SHA256)
        with patch("aerolab.nacelle_thermal.Path.read_bytes", side_effect=AssertionError("Must not reread possibly changed source during evaluation")):
            result = evaluate_nacelle()
        self.assertEqual(result["model_sha256"], MODEL_SOURCE_SHA256)
        self.assertEqual(result["input_hash"], self.base["input_hash"])
        self.assertEqual(result["metrics"]["fingerprint"], self.base["metrics"]["fingerprint"])

    def test_uncertainty_and_compare_identity_are_honest(self):
        uncertainty = self.base["uncertainty"]
        self.assertEqual(uncertainty["scenario_count"], 8)
        self.assertEqual(uncertainty["kind"], "uncalibrated_screening_scenario_range")
        self.assertFalse(self.base["provenance"]["calibrated"])
        for name, node in self.base["thermal"]["components"].items():
            span = uncertainty["component_temperature_c"][name]
            self.assertLessEqual(span["min"], node["temperature_c"])
            self.assertGreaterEqual(span["max"], node["temperature_c"])
        comparison = compare_nacelle({"hv_fin_count": 34}, {"heat_load": "mcp"})
        self.assertEqual(comparison["candidate"]["boundary"], comparison["reference"]["boundary"])
        self.assertNotEqual(comparison["candidate"]["input_hash"], comparison["reference"]["input_hash"])
        self.assertNotEqual(comparison["delta"]["mass_kg"], 0)
        json.dumps(comparison, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
