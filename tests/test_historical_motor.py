"""Independent component arithmetic/ODE checks, not aircraft validation."""
import json
import math
from pathlib import Path
import unittest

from aerolab.historical_motor import (
    AIR, SOURCE_CODE_SHA256, channel_transport, historical_channel_geometry,
    historical_motor_benchmark, isothermal_channel_response,
    straight_fin_efficiency, winding_material_audit,
)


def independently_discretized_fin_efficiency(h, k, thickness, height, cells):
    """Cell-centered finite-volume fin ODE; no tanh or analytic profile used.

    Unit axial span, base face theta=1, insulated tip, distributed 2h loss.
    Independent tridiagonal elimination checks the analytical production solver.
    """
    spacing = height / cells
    conductance = k * thickness / spacing
    sink = 2 * h * spacing
    diag = [2 * conductance + sink] * cells
    diag[0] = 3 * conductance + sink
    diag[-1] = conductance + sink
    rhs = [0.] * cells
    rhs[0] = 2 * conductance
    for index in range(1, cells):
        multiplier = -conductance / diag[index - 1]
        diag[index] += multiplier * conductance
        rhs[index] -= multiplier * rhs[index - 1]
    theta = [0.] * cells
    theta[-1] = rhs[-1] / diag[-1]
    for index in range(cells - 2, -1, -1):
        theta[index] = (rhs[index] + conductance * theta[index + 1]) / diag[index]
    heat_from_base = 2 * conductance * (1 - theta[0])
    heat_to_fluid = sink * sum(theta)
    return heat_to_fluid / (2 * h * height), heat_from_base - heat_to_fluid


class HistoricalMotorTests(unittest.TestCase):
    def test_source_dimensions_and_unit_conversions(self):
        g = historical_channel_geometry()
        self.assertAlmostEqual(g["flow_area_m2"], 34e-6, places=16)
        self.assertAlmostEqual(g["wetted_perimeter_m"], 38e-3, places=16)
        self.assertAlmostEqual(g["hydraulic_diameter_m"], (2 * 2 * 17 / 19) / 1000, places=16)
        self.assertAlmostEqual(g["all_wetted_area_m2"], 3990e-6, places=16)
        self.assertAlmostEqual(g["heating_hypotheses_m2"]["two_long_side_walls"], 3570e-6, places=16)
        self.assertAlmostEqual(g["heating_hypotheses_m2"]["three_walls_two_sides_plus_base"], 3780e-6, places=16)
        self.assertFalse(g["heated_perimeter_source_defined"])
        self.assertFalse(g["actual_fin_count_known"])

    def test_transport_against_independent_gnielinski_arithmetic(self):
        # Choose properties/Re independently of the default sweep. Re=10000
        # is a formula check, not a historical cooling-cart reconstruction.
        air = {"density_kg_m3": 1.02, "viscosity_pa_s": 1.9e-5,
               "conductivity_w_m_k": .027, "specific_heat_j_kg_k": 1007.}
        d = 2 * .002 * .017 / (.002 + .017)
        velocity = 10000 * 1.9e-5 / (1.02 * d)
        result = channel_transport(velocity, area_m2=34e-6, wetted_perimeter_m=.038,
                                   length_m=.105, heated_area_m2=.00357, air=air)
        # Independently tabulated values, also rederived by a research worker.
        self.assertAlmostEqual(result["reynolds"], 10000., places=10)
        self.assertAlmostEqual(result["darcy_friction_factor"], .0314798027567, places=12)
        self.assertAlmostEqual(result["nusselt"], 29.9991287596, places=9)
        self.assertAlmostEqual(result["h_w_m2_k"], 226.316956672, places=8)
        expected_dp = .0314798027567 * .105 / d * 1.02 * velocity * velocity / 2
        self.assertAlmostEqual(result["friction_pressure_drop_pa"], expected_dp, places=8)
        self.assertAlmostEqual(result["mass_flow_kg_s"], 1.02 * velocity * 34e-6, places=14)
        self.assertAlmostEqual(result["air_capacity_w_k"], result["mass_flow_kg_s"] * 1007, places=14)

    def test_transition_and_domain_extrapolation_are_not_hidden(self):
        report = historical_motor_benchmark()
        low, transition, higher = [r["transport"] for r in report["velocity_sweep"][:3]]
        self.assertTrue(2900 < low["reynolds"] < 3000)
        self.assertFalse(low["inside_nominal_gnielinski_re_pr_range"])
        self.assertEqual(low["correlation_status"], "extrapolation_not_validated")
        self.assertTrue(transition["inside_nominal_gnielinski_re_pr_range"])
        self.assertTrue(transition["transition_sensitive"])
        self.assertFalse(higher["transition_sensitive"])
        self.assertFalse(higher["actual_geometry_correlation_validated"])

    def test_pressure_scales_with_length_without_fake_minor_loss(self):
        kwargs = dict(area_m2=34e-6, wetted_perimeter_m=.038, heated_area_m2=.001)
        one = channel_transport(24., length_m=.105, **kwargs)
        two = channel_transport(24., length_m=.210, **kwargs)
        self.assertAlmostEqual(two["friction_pressure_drop_pa"], 2 * one["friction_pressure_drop_pa"], places=12)
        self.assertEqual(two["h_w_m2_k"], one["h_w_m2_k"])
        self.assertTrue(one["pressure_is_friction_only"])

    def test_fin_solution_against_independent_finite_volume_refinement(self):
        analytical = straight_fin_efficiency(150., 201., .001, .017)
        errors = []
        for cells in (16, 32, 64, 128, 256):
            numerical, residual = independently_discretized_fin_efficiency(150., 201., .001, .017, cells)
            errors.append(abs(numerical - analytical))
            self.assertLess(abs(residual), 1e-9)
        for coarser, finer in zip(errors, errors[1:]):
            self.assertTrue(3.95 < coarser / finer < 4.05)
        self.assertLess(errors[-1], 2e-6)

    def test_fin_limits_and_sensitivity(self):
        self.assertEqual(straight_fin_efficiency(0., 201., .001, .017), 1.)
        thin = straight_fin_efficiency(150., 201., .0005, .017)
        thick = straight_fin_efficiency(150., 201., .002, .017)
        self.assertTrue(0 < thin < thick < 1)
        self.assertAlmostEqual(straight_fin_efficiency(150., 1e20, .001, .017), 1.)
        self.assertLess(straight_fin_efficiency(300., 201., .001, .017),
                        straight_fin_efficiency(150., 201., .001, .017))

    def test_air_energy_equation_integral_and_limits(self):
        for wall in (5., 25., 26., 45.):
            result = isothermal_channel_response(.5, 1.3, inlet_c=25., wall_c=wall)
            # Solve dT/ds = UA/C*(wall-T) independently with small-step RK4.
            numerical = 25.
            ds = 1 / 1000
            for _ in range(1000):
                rate = lambda temperature: .5 / 1.3 * (wall - temperature)
                k1 = rate(numerical)
                k2 = rate(numerical + ds * k1 / 2)
                k3 = rate(numerical + ds * k2 / 2)
                k4 = rate(numerical + ds * k3)
                numerical += ds * (k1 + 2 * k2 + 2 * k3 + k4) / 6
            self.assertAlmostEqual(result["outlet_c"], numerical, places=11)
            self.assertLess(abs(result["energy_balance_residual_w"]), 1e-12)
            self.assertLess(result["quadrature_relative_error"], 1e-6)
        self.assertEqual(isothermal_channel_response(0, 1)["heat_w"], 0)
        self.assertAlmostEqual(isothermal_channel_response(1000., 1.)["heat_w"], 1.)
        self.assertLess(isothermal_channel_response(.5, 1.3)["effective_inlet_to_wall_conductance_w_k"], .5)

    def test_mass_heat_capacity_and_conductivity_rederived(self):
        result = winding_material_audit()
        # Explicit one-cubic-metre constituent masses; no helper mixing code.
        copper_mass, epoxy_mass = .45 * 8960, .55 * 1225
        total_heat = copper_mass * 385 + epoxy_mass * 1000
        self.assertAlmostEqual(copper_mass + epoxy_mass, 4705.75, places=12)
        self.assertAlmostEqual(total_heat, 2226070., places=9)
        self.assertAlmostEqual(result["mass_consistent_specific_heat_j_kg_k"], total_heat / (copper_mass + epoxy_mass), places=12)
        self.assertAlmostEqual(result["mass_consistent_specific_heat_j_kg_k"], 473.0531796206768, places=12)
        self.assertAlmostEqual(result["series_conductivity_w_m_k"], 400 / (.55 * 400 + .45), places=12)
        self.assertAlmostEqual(result["parallel_conductivity_w_m_k"], 180.55, places=12)
        self.assertAlmostEqual(result["volume_average_specific_heat_j_kg_k"], 723.25, places=12)
        self.assertAlmostEqual(result["printed_capacity_excess_percent_of_constituent_value"], 52.88978727084055, places=10)
        self.assertAlmostEqual(result["constituent_capacity_reduction_percent_of_printed_value"], 34.59340758787738, places=10)
        self.assertEqual(winding_material_audit(0)["mass_consistent_specific_heat_j_kg_k"], 1000)
        self.assertEqual(winding_material_audit(1)["mass_consistent_specific_heat_j_kg_k"], 385)

    def test_liner_units_and_area_normalized_resistance(self):
        liner = winding_material_audit()["slot_liner"]
        self.assertAlmostEqual(liner["manufacturer_nomex410_conductivity_at_150c_w_m_k"], 139 / 1000, places=14)
        self.assertAlmostEqual(liner["manufacturer_areal_resistance_m2_k_w"], .25e-3 / .139, places=14)
        self.assertAlmostEqual(liner["manufacturer_areal_resistance_m2_k_w"] / liner["printed_areal_resistance_m2_k_w"], 1000, places=10)
        self.assertFalse(liner["actual_grade_and_comsol_input_verified"])

    def test_matched_comparison_preserves_boundary_and_hypothesis(self):
        report = historical_motor_benchmark()
        comparison = report["matched_condition_comparison"]
        self.assertFalse(comparison["equivalent_count_is_actual_geometry"])
        self.assertNotEqual(comparison["equivalent_historical_channel_count"], round(comparison["equivalent_historical_channel_count"]))
        self.assertAlmostEqual(comparison["equivalent_historical_channel_count"] * 34e-6, comparison["flux_equivalent_area_m2"], places=15)
        self.assertEqual(comparison["boundary"]["length_m"], .105)
        self.assertEqual(comparison["boundary"]["air"], AIR)
        for row in comparison["rows"]:
            narrow, broad = row["historical_narrow"], row["current_broad_slot"]
            self.assertAlmostEqual(narrow["mass_flow_at_equivalent_flow_area_kg_s"], broad["mass_flow_at_equivalent_flow_area_kg_s"], places=14)
            self.assertAlmostEqual(narrow["heated_area_at_equivalent_flow_area_m2"], comparison["flux_equivalent_area_m2"] * 2 * .105 / .002, places=13)
            self.assertGreater(row["narrow_to_broad_ua_ratio"], 1)
            self.assertGreater(row["narrow_to_broad_friction_drop_ratio"], 1)
        # These scales are not manipulated to satisfy any winding temperature.
        row = comparison["rows"][3]
        self.assertAlmostEqual(row["narrow_to_broad_ua_ratio"], 3.1260992354567265, places=10)
        self.assertAlmostEqual(row["narrow_to_broad_friction_drop_ratio"], 3.4623325468358126, places=10)

    def test_invalid_inputs_fail_before_numeric_results(self):
        kwargs = dict(area_m2=34e-6, wetted_perimeter_m=.038, length_m=.105, heated_area_m2=.00357)
        for velocity in (True, None, 0., -1., float("nan"), float("inf"), 1.):
            with self.subTest(velocity=velocity), self.assertRaises(ValueError):
                channel_transport(velocity, **kwargs)
        with self.assertRaises(ValueError):
            channel_transport(24, **{**kwargs, "heated_area_m2": .1})
        with self.assertRaises(ValueError):
            channel_transport(24, air={**AIR, "viscosity_pa_s": 0}, **kwargs)
        for value in (-.1, 1.1, True, float("nan")):
            with self.assertRaises(ValueError):
                winding_material_audit(value)
        with self.assertRaises(ValueError):
            isothermal_channel_response(.5, 0)
        with self.assertRaises(ValueError):
            straight_fin_efficiency(150, 201, 0, .017)

    def test_report_never_claims_calibration_or_actual_full_motor(self):
        report = historical_motor_benchmark()
        self.assertFalse(report["experimental_validation"])
        self.assertFalse(report["calibration_performed"])
        self.assertFalse(report["modifies_final2023_rom"])
        self.assertLess(report["verification"]["maximum_energy_balance_residual_w"], 1e-12)
        self.assertLess(report["verification"]["maximum_independent_midpoint_quadrature_relative_error"], 1e-6)
        self.assertEqual(report["source_code_sha256"], SOURCE_CODE_SHA256)
        # Separate scalar material audit, not a mass chosen to fit a transient.
        self.assertNotIn("motor_thermal_mass", report)
        self.assertNotIn("predicted_winding_c", report)

    def test_saved_evidence_is_bounded_and_reproducible(self):
        from scripts.generate_nacelle_credibility import check
        path = Path(__file__).resolve().parents[1] / "examples" / "historical_motor.json"
        self.assertLess(path.stat().st_size, 100_000)
        check(historical_motor_benchmark(), json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
