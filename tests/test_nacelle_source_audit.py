"""Independent algebra/identity checks, not physical validation of NASA or ROM."""
from copy import deepcopy
import json
import math
from pathlib import Path
import unittest

from aerolab.nacelle_source_audit import (
    SOURCE_DATA, SOURCE_DATA_SHA256, station_properties, source_station_data,
    conditional_resistance_check, source_audit, PSI_PA, LBM_KG, FT_M, R_AIR,
)


class SourceStationAuditTests(unittest.TestCase):
    def test_exact_printed_transcription_sentinels(self):
        cases = SOURCE_DATA["cases"]
        self.assertEqual({k: len(v) for k, v in cases.items()},
                         {"initial_climb": 33, "cruise_climb": 33, "dash": 33})
        self.assertEqual(cases["initial_climb"]["2a_s"], [13.45, 13.51, 43.09, 43.5, 68.8, .458])
        self.assertEqual(cases["cruise_climb"]["5b_hv_L"], [13.40, 13.41, 53.67, 53.79, 46.2, .222])
        self.assertEqual(cases["dash"]["7"], [10.89, 10.90, 38.71, 38.81, 39.5, .958])
        for rows in cases.values():
            for row in rows.values():
                station_properties(row)

    def test_unit_conversion_against_independent_mass_equation(self):
        row = [14.0, 14.01, 26.85, 27.0, 20.0, .1]
        result = station_properties(row)
        p = 14 * 6894.757293168
        rho = p / (287.05 * 300)
        expected = (.1 * .45359237) / (rho * (20 * .3048))
        self.assertAlmostEqual(result["flux_equivalent_area_m2"], expected, places=14)
        self.assertAlmostEqual(result["density_ideal_gas_kg_m3"], rho, places=14)

    def test_rounding_intervals_cover_all_independent_corner_combinations(self):
        import itertools
        row = SOURCE_DATA["cases"]["initial_climb"]["2a_g"]
        result = station_properties(row)
        lo, hi = result["area_printed_rounding_m2"]
        for sp, st, sv, sm in itertools.product((-1, 1), repeat=4):
            p = (row[0] + sp * .005) * PSI_PA
            t = row[2] + st * .005 + 273.15
            v = (row[4] + sv * .05) * FT_M
            m = (row[5] + sm * .0005) * LBM_KG
            area = m * R_AIR * t / (p * v)
            self.assertGreaterEqual(area, lo - 1e-15)
            self.assertLessEqual(area, hi + 1e-15)

    def test_isentropic_energy_inversion_and_static_stream_are_distinct(self):
        r = station_properties(SOURCE_DATA["cases"]["initial_climb"]["1_c"])
        self.assertGreater(r["pressure_energy_to_streamwise_ratio"], 3)
        self.assertGreater(r["temperature_energy_to_streamwise_ratio"], 3)
        self.assertAlmostEqual(r["pressure_energy_velocity_m_s"], r["temperature_energy_velocity_m_s"], delta=1.)
        pressure = SOURCE_DATA["cases"]["initial_climb"]["1_c"][0] * PSI_PA
        rho = r["density_ideal_gas_kg_m3"]
        mach = r["pressure_energy_velocity_m_s"] / math.sqrt(1.4 * pressure / rho)
        ratio = (1 + .2 * mach ** 2) ** 3.5
        self.assertAlmostEqual(ratio, 13.66 / 13.54, places=13)

    def test_invalid_or_unresolved_station_rejected(self):
        row = [14., 14.1, 25., 25.1, 20., .1]
        invalid = [None, [], row[:5]]
        for index, value in ((0, 0), (1, 13), (2, -274), (3, 24), (4, 0), (5, 0), (2, True), (4, float("nan"))):
            trial = row.copy()
            trial[index] = value
            invalid.append(trial)
        for trial in invalid:
            with self.subTest(trial=trial), self.assertRaises(ValueError):
                station_properties(trial)

    def test_only_inference_case_affects_fitted_conductance(self):
        baseline = conditional_resistance_check()
        changed = deepcopy(SOURCE_DATA["cases"])
        changed["dash"]["2a_s"][5] *= 1.1
        recomputed = conditional_resistance_check(changed)
        for name in baseline:
            self.assertEqual(baseline[name]["fixed_effective_area_over_sqrt_k_m2"],
                             recomputed[name]["fixed_effective_area_over_sqrt_k_m2"])
        self.assertNotEqual(baseline["main_to_slots"]["cases"]["dash"]["relative_error_percent"],
                            recomputed["main_to_slots"]["cases"]["dash"]["relative_error_percent"])

    def test_calibration_matches_itself_but_whole_motor_check_fails(self):
        checks = conditional_resistance_check()
        for item in checks.values():
            self.assertAlmostEqual(item["cases"]["initial_climb"]["relative_error_percent"], 0, places=12)
        dash = checks["main_to_slots"]["cases"]["dash"]
        self.assertLess(dash["relative_error_percent"], -15)
        self.assertLess(dash["error_printed_rounding_percent"][1], 0)
        # Local slot-only relation transports better, but uses internal pressures.
        self.assertLess(abs(checks["slot_core"]["cases"]["cruise_climb"]["relative_error_percent"]), 1)

    def test_source_copy_cannot_mutate_fixture(self):
        copy = source_station_data()
        copy["cases"]["initial_climb"]["2a_g"][5] = 99
        self.assertEqual(SOURCE_DATA["cases"]["initial_climb"]["2a_g"][5], .1)

    def test_audit_does_not_claim_physical_or_blind_validation(self):
        report = source_audit()
        self.assertFalse(report["experimental_validation"])
        self.assertFalse(report["blind_holdout"])
        self.assertEqual(report["source_data_sha256"], SOURCE_DATA_SHA256)
        self.assertLess(report["flow_area_constraints"]["motor_internal"]["three_case_span_percent_of_inferred"], .6)
        self.assertLess(report["flow_area_constraints"]["motor_slots"]["three_case_span_percent_of_inferred"], .6)
        self.assertGreater(report["flow_area_constraints"]["motor_internal"]["current_rom_area_relative_to_inference_percent"], 150)
        self.assertTrue(2 < report["geometry_hypotheses"]["concentric_gap_mm"] < 2.2)
        self.assertTrue(all(not x["is_integrated_control_volume_balance"] for x in report["station_enthalpy_diagnostic"].values()))

    def test_saved_evidence_reproduces_current_code_and_source(self):
        from scripts.generate_nacelle_credibility import check
        path = Path(__file__).resolve().parents[1] / "examples" / "nacelle_source_audit.json"
        self.assertLess(path.stat().st_size, 100_000)
        check(source_audit(), json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
