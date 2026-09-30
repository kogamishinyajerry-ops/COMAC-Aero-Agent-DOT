"""Mathematical verification and adversarial API checks; not hardware validation."""
import copy
import hashlib
import json
import math
from pathlib import Path
import unittest

from aerolab.duct_finite_volume import (
    DEFAULT_CASE, SOURCE_SHA256, fully_developed_reference, parse_case, solve_duct,
)
from scripts.generate_duct_verification import check, generate, graetz_reference


class DuctFiniteVolumeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = solve_duct()

    def test_poisson_velocity_pressure_and_shear(self):
        result = solve_duct({"transverse_cells": 128, "axial_cells": 4})
        flow = result["hydraulics"]
        p = result["provenance"]["case"]
        self.assertLess(abs(flow["darcy_f_re"] / 96 - 1), .00013)
        b = p["gap_m"] / 2
        exact_dp = 3 * p["viscosity_pa_s"] * p["mean_velocity_m_s"] * p["length_m"] / b**2
        self.assertLess(abs(flow["signed_pressure_drop_pa"] / exact_dp - 1), .00013)
        for row in flow["velocity_samples"]:
            exact = 1.5 * (1 - row["eta"]**2)
            self.assertLess(abs(row["velocity_m_s"] - exact), .0001)
        self.assertAlmostEqual(flow["wall_shear_pa"]["left"], flow["signed_pressure_drop_pa"] * b / p["length_m"], places=12)
        self.assertAlmostEqual(flow["wall_shear_pa"]["left"], flow["wall_shear_pa"]["right"], places=12)

    def test_energy_at_every_sample(self):
        for fluxes in ((200, 200), (20, 200), (-200, 200), (-200, -200)):
            result = solve_duct({"left_heat_flux_w_m2": fluxes[0], "right_heat_flux_w_m2": fluxes[1]})
            p = result["provenance"]["case"]
            capacity = abs(result["hydraulics"]["mass_flow_kg_s"]) * p["specific_heat_j_kg_k"]
            for row in result["thermal"]["axial_samples"]:
                expected = sum(fluxes) * p["span_m"] * row["s_from_inlet_m"]
                self.assertAlmostEqual(capacity * (row["bulk_c"] - p["inlet_c"]), expected, places=10)
            self.assertLess(abs(result["diagnostics"]["energy_residual_w"]), 1e-10)
            self.assertTrue(result["diagnostics"]["converged"])

    def test_equal_flux_exact_quartic_profile_and_nusselt(self):
        result = solve_duct({"transverse_cells": 128, "axial_cells": 4, "inlet_profile": "fully_developed"})
        for row in result["thermal"]["outlet_profile"]:
            eta = row["eta"]
            expected = .75 * eta**2 - .125 * eta**4 - 39 / 280
            self.assertLess(abs(row["temperature_minus_bulk_over_qref_b_k"] - expected), 1e-4)
        self.assertLess(abs(result["thermal"]["outlet_nusselt"]["right"] - 140 / 17), .0004)

    def test_one_wall_heated_exact_limit(self):
        result = solve_duct({"transverse_cells": 128, "axial_cells": 4,
                             "left_heat_flux_w_m2": 0, "inlet_profile": "fully_developed"})
        self.assertLess(abs(result["thermal"]["outlet_nusselt"]["right"] - 70 / 13), .0001)
        self.assertIsNone(result["thermal"]["outlet_nusselt"]["left"])

    def test_unequal_wall_can_be_below_bulk(self):
        result = solve_duct({"left_heat_flux_w_m2": 20})
        thermal = result["thermal"]
        self.assertLess(thermal["outlet_wall_c"]["left"], thermal["outlet_bulk_c"])
        self.assertGreater(thermal["outlet_wall_c"]["right"], thermal["outlet_bulk_c"])
        self.assertLess(thermal["outlet_nusselt"]["left"], 0)
        self.assertGreater(result["diagnostics"]["energy_removed_w"], 0)

    def test_unequal_flux_superposition(self):
        params = {"axial_cells": 100, "axial_samples": 5}
        a = solve_duct(dict(params, left_heat_flux_w_m2=200, right_heat_flux_w_m2=0))
        b = solve_duct(dict(params, left_heat_flux_w_m2=0, right_heat_flux_w_m2=200))
        both = solve_duct(dict(params, left_heat_flux_w_m2=20, right_heat_flux_w_m2=200))
        inlet = DEFAULT_CASE["inlet_c"]
        for sa, sb, sc in zip(a["thermal"]["axial_samples"], b["thermal"]["axial_samples"], both["thermal"]["axial_samples"]):
            for side in ("left", "right"):
                expected = inlet + .1 * (sa["wall_c"][side] - inlet) + sb["wall_c"][side] - inlet
                self.assertAlmostEqual(sc["wall_c"][side], expected, places=10)

    def test_wall_swap_mirrors_temperature(self):
        left = solve_duct({"left_heat_flux_w_m2": 20})["thermal"]
        right = solve_duct({"right_heat_flux_w_m2": 20})["thermal"]
        for side, other in (("left", "right"), ("right", "left")):
            self.assertAlmostEqual(left["outlet_wall_c"][side], right["outlet_wall_c"][other], places=10)

    def test_reversed_flow_preserves_heat_and_maps_physical_coordinates(self):
        reverse = solve_duct({"mean_velocity_m_s": -1})
        self.assertEqual(reverse["hydraulics"]["flow_direction"], -1)
        for key in ("mass_flow_kg_s", "signed_pressure_drop_pa"):
            self.assertEqual(reverse["hydraulics"][key], -self.base["hydraulics"][key])
        self.assertEqual(reverse["thermal"]["outlet_bulk_c"], self.base["thermal"]["outlet_bulk_c"])
        for a, b in zip(self.base["thermal"]["axial_samples"], reverse["thermal"]["axial_samples"]):
            self.assertAlmostEqual(a["x_physical_m"] + b["x_physical_m"], DEFAULT_CASE["length_m"])
            self.assertEqual(a["wall_c"], b["wall_c"])
        self.assertGreater(reverse["hydraulics"]["hydraulic_dissipation_w"], 0)

    def test_cooling_is_signed_and_conservative(self):
        cool = solve_duct({"left_heat_flux_w_m2": -200, "right_heat_flux_w_m2": -200})
        hot = self.base["thermal"]
        for side in ("left", "right"):
            self.assertAlmostEqual(cool["thermal"]["outlet_wall_c"][side] + hot["outlet_wall_c"][side], 50, places=10)
            self.assertGreater(cool["thermal"]["outlet_nusselt"][side], 0)
        self.assertLess(cool["diagnostics"]["energy_removed_w"], 0)

    def test_zero_flow_no_artificial_temperature(self):
        hot = solve_duct({"mean_velocity_m_s": 0})
        self.assertEqual(hot["status"], "no_steady_state_zero_flow")
        self.assertIsNone(hot["thermal"]["outlet_bulk_c"])
        self.assertFalse(hot["diagnostics"]["converged"])
        self.assertEqual(hot["diagnostics"]["energy_residual_w"], -6.4)
        balanced = solve_duct({"mean_velocity_m_s": 0, "left_heat_flux_w_m2": -200})
        self.assertEqual(balanced["status"], "undetermined_zero_flow_temperature")
        self.assertIsNone(balanced["thermal"]["outlet_wall_c"]["left"])
        cold = solve_duct({"mean_velocity_m_s": 0, "left_heat_flux_w_m2": 0, "right_heat_flux_w_m2": 0})
        self.assertEqual(cold["status"], "isothermal_zero_flow")
        self.assertEqual(cold["thermal"]["outlet_bulk_c"], 25)

    def test_zero_heat_has_no_fictitious_nusselt(self):
        result = solve_duct({"left_heat_flux_w_m2": 0, "right_heat_flux_w_m2": 0})
        self.assertEqual(result["thermal"]["outlet_bulk_c"], 25)
        self.assertEqual(result["thermal"]["outlet_nusselt"], {"left": None, "right": None})
        self.assertEqual(result["diagnostics"]["energy_residual_w"], 0)

    def test_extreme_cooling_rejects_absolute_zero_violation(self):
        with self.assertRaisesRegex(ValueError, "nonphysical absolute temperature"):
            solve_duct({"left_heat_flux_w_m2": -10000, "right_heat_flux_w_m2": -10000})

    def test_absolute_zero_guard_checks_unsampled_interior_axial_states(self):
        # The long-channel outlet is positive, but the negatively heated wall
        # has a sub-absolute-zero dip upstream. Only two output samples must
        # not conceal that physically impossible interior state.
        p = DEFAULT_CASE
        heat = (-8000 + 10000) * p["span_m"] * 2
        capacity = p["density_kg_m3"] * p["gap_m"] * p["span_m"] * p["mean_velocity_m_s"] * p["specific_heat_j_kg_k"]
        wall_offset = 2 * p["gap_m"] / p["conductivity_w_m_k"] * (13 / 70 * -8000 - 9 / 140 * 10000)
        self.assertGreater(p["inlet_c"] + heat / capacity + wall_offset, 0)
        with self.assertRaisesRegex(ValueError, "nonphysical absolute temperature"):
            solve_duct({"left_heat_flux_w_m2": -8000, "right_heat_flux_w_m2": 10000,
                        "length_m": 2, "axial_samples": 2, "transverse_samples": 3})

    def test_absolute_zero_guard_checks_solid_even_when_fluid_is_admissible(self):
        params = {"left_heat_flux_w_m2": -1200, "right_heat_flux_w_m2": 1200}
        fluid = solve_duct(params)
        self.assertGreater(min(fluid["thermal"]["outlet_wall_c"].values()), -273.15)
        with self.assertRaisesRegex(ValueError, "solid outer face"):
            solve_duct(dict(params, wall_conductivity_w_m_k=.01))

    def test_absolute_zero_guard_checks_fully_developed_inlet(self):
        with self.assertRaisesRegex(ValueError, "axial face 0"):
            solve_duct({"left_heat_flux_w_m2": -10000, "right_heat_flux_w_m2": 10000,
                        "inlet_profile": "fully_developed"})

    def test_absolute_temperature_diagnostics_cover_every_marched_state(self):
        diagnostics = self.base["diagnostics"]
        self.assertTrue(diagnostics["absolute_temperature_admissible"])
        self.assertEqual(diagnostics["absolute_temperature_checked_axial_states"], DEFAULT_CASE["axial_cells"] + 1)
        self.assertEqual(diagnostics["minimum_computed_temperature_c"], DEFAULT_CASE["inlet_c"])

    def test_local_solid_conduction_interface(self):
        result = solve_duct({"left_heat_flux_w_m2": 20})
        p, thermal = result["provenance"]["case"], result["thermal"]
        for side, q in (("left", 20), ("right", 200)):
            points = thermal["outlet_solid_profile"][side]
            self.assertEqual(points[0]["temperature_c"], thermal["outlet_wall_c"][side])
            for point in points:
                expected = thermal["outlet_wall_c"][side] + q * point["depth_from_fluid_m"] / p["wall_conductivity_w_m_k"]
                self.assertEqual(point["temperature_c"], expected)
        insulated_model = solve_duct({"wall_conductivity_w_m_k": .1})
        self.assertEqual(insulated_model["thermal"]["outlet_wall_c"], self.base["thermal"]["outlet_wall_c"])
        self.assertGreater(insulated_model["thermal"]["outlet_solid_outer_c"]["left"], self.base["thermal"]["outlet_solid_outer_c"]["left"])

    def test_inlet_corner_is_labeled_without_fabricated_infinite_nu(self):
        sample = self.base["thermal"]["axial_samples"][0]
        self.assertEqual(sample["bulk_c"], 25)
        self.assertEqual(sample["wall_c"], {"left": 25, "right": 25})
        self.assertEqual(sample["nusselt_dh"], {"left": None, "right": None})
        self.assertEqual(sample["solid_outer_c"], {"left": None, "right": None})

    def test_reject_invalid_and_unbounded_inputs(self):
        bad = ({"extra": 1}, {"gap_m": 0}, {"mean_velocity_m_s": float("nan")},
               {"length_m": float("inf")}, {"inlet_c": True}, {"transverse_cells": 32.0},
               {"transverse_cells": True}, {"axial_cells": 0}, {"axial_cells": 8193},
               {"transverse_cells": 256, "axial_cells": 8192}, {"axial_samples": 66},
               {"inlet_profile": "unrecognized"}, {"mean_velocity_m_s": 10},
               {"mean_velocity_m_s": .001}, {"density_kg_m3": "1.2"},
               {"gap_m": 10**400}, {"length_m": .001, "mean_velocity_m_s": .2})
        for params in bad:
            with self.subTest(params=params), self.assertRaises(ValueError):
                solve_duct(params)
        for value in ([], 3, "x"):
            with self.assertRaises(ValueError):
                parse_case(value)

    def test_source_identity_input_identity_and_no_mutation(self):
        case = {"left_heat_flux_w_m2": 20, "axial_cells": 100}
        original = copy.deepcopy(case)
        a = solve_duct(case)
        b = solve_duct(dict(reversed(list(case.items()))))
        self.assertEqual(a, b)
        self.assertEqual(case, original)
        self.assertNotEqual(a["provenance"]["input_sha256"], self.base["provenance"]["input_sha256"])
        path = Path(__file__).resolve().parents[1] / "aerolab" / "duct_finite_volume.py"
        self.assertEqual(SOURCE_SHA256, hashlib.sha256(path.read_bytes()).hexdigest())
        json.dumps(a, allow_nan=False)

    def test_compact_samples_have_locations_and_grid_indices(self):
        result = solve_duct({"axial_cells": 4, "transverse_cells": 4, "axial_samples": 65, "transverse_samples": 65})
        samples = result["thermal"]["axial_samples"]
        self.assertEqual(len(samples), 5)
        self.assertEqual(len({row["axial_face_index"] for row in samples}), 5)
        self.assertEqual(len(result["thermal"]["sample_eta"]), 4)
        for row in samples:
            self.assertEqual(len(row["fluid_c"]), 4)
        self.assertEqual(result["provenance"]["grid"]["total_marched_cells"], 16)

    def test_continuum_reference_domain_and_cross_wall_limit(self):
        value = fully_developed_reference(-1, .1, 1)["temperature_minus_bulk_over_qref_b_k"]
        self.assertAlmostEqual(value, (26 * .1 - 9) / 35)
        for bad in (float("nan"), float("inf"), True, -1.1, 1.1):
            with self.assertRaises(ValueError):
                fully_developed_reference(bad)

    def test_transverse_second_order_grid_convergence(self):
        errors = []
        for n in (16, 32, 64):
            result = solve_duct({"transverse_cells": n, "axial_cells": 4, "inlet_profile": "fully_developed"})
            errors.append(abs(result["thermal"]["outlet_nusselt"]["right"] - 140 / 17))
        for i in range(2):
            self.assertGreater(math.log(errors[i] / errors[i + 1], 2), 1.9)

    def test_independent_developing_reference_truncation(self):
        for zeta in (.02, .05, .1, .2, 1):
            reference = graetz_reference(zeta, .1, 1)
            short = graetz_reference(zeta, .1, 1, count=8)
            self.assertLess(max(abs(reference[side] - short[side]) for side in reference), 1e-8)
        self.assertAlmostEqual(graetz_reference(20)["right"], 17 / 35)
        self.assertAlmostEqual(graetz_reference(20, .1, 1)["left"], (26 * .1 - 9) / 35)

    def test_saved_evidence_reproduces_and_all_gates_pass(self):
        path = Path(__file__).resolve().parents[1] / "examples" / "duct_verification.json"
        self.assertLess(path.stat().st_size, 100000)
        report = generate()
        self.assertTrue(all(report["gates"].values()))
        check(report, json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
