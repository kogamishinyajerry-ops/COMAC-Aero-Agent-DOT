"""Historical (2019) X-57 narrow-channel and material arithmetic benchmark.

A dated component subcase, not a replacement/calibration of the final-nacelle
ROM. Source dimensions fix a rectangular flow unit cell. Its heated perimeter,
fin thickness, air properties and normalized boundary conditions are separate
assumptions. All runtime calculations use the Python standard library.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

SOURCE_URL = "https://ntrs.nasa.gov/api/citations/20190032520/downloads/20190032520.pdf"
NOMEX_URL = "https://pronatindustries.com/wp-content/uploads/2014/07/Nomex_Tape410_technicaldatasheet.pdf"
FRICTION_URL = "https://www.osti.gov/servlets/purl/2375525"
MODEL_ID = "x57-2019-historical-motor-unit-cell-v1"
SOURCE_CODE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
# Frozen engineering assumptions, not recovered NASA test properties. These are
# representative near-room-temperature dry-air constants, not a property model.
AIR = {"density_kg_m3": 1.225, "viscosity_pa_s": 1.7894e-5,
       "conductivity_w_m_k": .0257, "specific_heat_j_kg_k": 1006.0}
VELOCITIES_M_S = (12.0, 16.0, 20.0, 24.0, 30.0, 40.0)
FIN_THICKNESSES_M = (.0005, .001, .002)


def _number(value, name, *, minimum=0.0, strict=True):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or (value <= minimum if strict else value < minimum)):
        raise ValueError(f"{name} must be a finite number {'>' if strict else '>='} {minimum}")
    return float(value)


def historical_channel_geometry():
    """Return source dimensions and derived areas with separate heating hypotheses."""
    a, b, length = .002, .017, .105
    area, perimeter = a * b, 2 * (a + b)
    return {
        "source_location": "2019 paper p4 Eq(1); Fig4 p5 only establishes qualitative fin-pack topology",
        "source_dimensions_m": {"a": a, "b": b, "length": length},
        "flow_area_m2": area,
        "wetted_perimeter_m": perimeter,
        "hydraulic_diameter_m": 4 * area / perimeter,
        "source_rounded_hydraulic_diameter_m": .00358,
        "aspect_ratio_small_over_large": a / b,
        "length_to_hydraulic_diameter": length * perimeter / (4 * area),
        "all_wetted_area_m2": perimeter * length,
        "heating_hypotheses_m2": {
            "two_long_side_walls": 2 * b * length,
            "three_walls_two_sides_plus_base": (2 * b + a) * length,
            "all_four_walls": perimeter * length,
        },
        "base_area_m2": a * length,
        "fin_side_area_per_cell_m2": 2 * b * length,
        "heated_perimeter_source_defined": False,
        "actual_fin_count_known": False,
        "actual_fin_thickness_known": False,
    }


def channel_transport(velocity_m_s, *, area_m2, wetted_perimeter_m, length_m,
                      heated_area_m2, air=None):
    """Smooth equivalent-duct arithmetic; explicitly expose domain warnings.

    f=(0.79 ln Re-1.64)^-2 is the Darcy, not Fanning, convention. Gnielinski
    uses that same f. Values below Re=3000 are labelled extrapolations, not
    hidden by a laminar/turbulent interpolation. Re<=1000 is not evaluated.
    Minor losses, roughness, entrance effects and rotation are not modelled.
    """
    speed = _number(velocity_m_s, "velocity_m_s")
    area = _number(area_m2, "area_m2")
    perimeter = _number(wetted_perimeter_m, "wetted_perimeter_m")
    length = _number(length_m, "length_m")
    heated = _number(heated_area_m2, "heated_area_m2", strict=False)
    if heated > perimeter * length * (1 + 1e-12):
        raise ValueError("heated_area_m2 cannot exceed this duct's wetted area")
    properties = dict(AIR if air is None else air)
    for key in AIR:
        properties[key] = _number(properties.get(key), key)
    rho, mu = properties["density_kg_m3"], properties["viscosity_pa_s"]
    k, cp = properties["conductivity_w_m_k"], properties["specific_heat_j_kg_k"]
    diameter = 4 * area / perimeter
    reynolds, prandtl = rho * speed * diameter / mu, mu * cp / k
    if reynolds <= 1000:
        raise ValueError("This turbulent-form benchmark requires Re > 1000; no laminar extrapolation is supplied")
    friction = (0.79 * math.log(reynolds) - 1.64) ** -2
    nu = ((friction / 8) * (reynolds - 1000) * prandtl
          / (1 + 12.7 * math.sqrt(friction / 8) * (prandtl ** (2 / 3) - 1)))
    h = nu * k / diameter
    pressure = friction * length / diameter * .5 * rho * speed ** 2
    mass = rho * speed * area
    within = 3000 <= reynolds <= 5e6 and .5 <= prandtl <= 2000
    return {
        "velocity_m_s": speed, "reynolds": reynolds, "prandtl": prandtl,
        "darcy_friction_factor": friction, "nusselt": nu, "h_w_m2_k": h,
        "hydraulic_diameter_m": diameter, "heated_area_m2": heated,
        "length_to_hydraulic_diameter": length / diameter,
        "friction_pressure_drop_pa": pressure,
        "hydraulic_dissipation_w": pressure * speed * area,
        "mass_flow_kg_s": mass, "air_capacity_w_k": mass * cp,
        "isothermal_wall_ua_w_k": h * heated,
        "inside_nominal_gnielinski_re_pr_range": within,
        "transition_sensitive": reynolds < 4000,
        "correlation_status": "nominal_range_but_geometry_unvalidated" if within else "extrapolation_not_validated",
        "actual_geometry_correlation_validated": False,
        "pressure_is_friction_only": True,
    }


def straight_fin_efficiency(h_w_m2_k, conductivity_w_m_k, thickness_m, height_m):
    """Two-side thin straight fin, uniform h, insulated tip, constant k.

    Solve theta''=m² theta, theta(0)=theta_base, theta'(H)=0 with
    m²=2h/(kt). Side-edge/tip heat and cross-thickness gradients are neglected.
    The source supplies k=201 W/mK but not the thickness or this exact boundary.
    """
    h = _number(h_w_m2_k, "h_w_m2_k", strict=False)
    k = _number(conductivity_w_m_k, "conductivity_w_m_k")
    t = _number(thickness_m, "thickness_m")
    height = _number(height_m, "height_m")
    mh = height * math.sqrt(2 * h / (k * t))
    return math.tanh(mh) / mh if mh else 1.0


def isothermal_channel_response(ua_w_k, air_capacity_w_k, inlet_c=25.0, wall_c=26.0):
    """Exact plug-flow energy equation at uniform wall/base temperature.

    The default +1 K response is a conductance normalization. It is not a
    prediction of actual winding, fin, test-cart or aircraft temperature.
    """
    ua = _number(ua_w_k, "ua_w_k", strict=False)
    capacity = _number(air_capacity_w_k, "air_capacity_w_k")
    inlet = _number(inlet_c, "inlet_c", minimum=-273.15)
    wall = _number(wall_c, "wall_c", minimum=-273.15)
    ntu = ua / capacity
    effectiveness = -math.expm1(-ntu)
    heat = capacity * (wall - inlet) * effectiveness
    outlet = inlet + heat / capacity
    # Independent integration of the local heat-transfer rate over x/L by
    # composite midpoint quadrature. This is not a second CFD/CHT model.
    intervals = 256
    quadrature = sum(ua * (wall - inlet) * math.exp(-ntu * (i + .5) / intervals)
                     / intervals for i in range(intervals))
    return {
        "inlet_c": inlet, "wall_or_fin_base_c": wall, "outlet_c": outlet,
        "ntu": ntu, "effectiveness": effectiveness, "heat_w": heat,
        "effective_inlet_to_wall_conductance_w_k": capacity * effectiveness,
        "air_enthalpy_gain_w": capacity * (outlet - inlet),
        "energy_balance_residual_w": heat - capacity * (outlet - inlet),
        "integrated_local_convection_w": quadrature,
        "midpoint_quadrature_intervals": intervals,
        "quadrature_relative_error": abs(quadrature - heat) / abs(heat) if heat else 0.0,
    }


def winding_material_audit(copper_volume_fraction=.45):
    """Constituent-consistent mixture arithmetic, not recovered COMSOL inputs."""
    fraction = _number(copper_volume_fraction, "copper_volume_fraction", strict=False)
    if fraction > 1:
        raise ValueError("copper_volume_fraction must be <= 1")
    rho_c, cp_c, k_c = 8960., 385., 400.
    rho_e, cp_e, k_e = 1225., 1000., 1.
    density = fraction * rho_c + (1 - fraction) * rho_e
    capacity = fraction * rho_c * cp_c + (1 - fraction) * rho_e * cp_e
    mass_cp = capacity / density
    volume_average_cp = fraction * cp_c + (1 - fraction) * cp_e
    series_k = 1 / (fraction / k_c + (1 - fraction) / k_e)
    parallel_k = fraction * k_c + (1 - fraction) * k_e
    printed_rho, printed_cp = 4705.75, 723.25
    printed_capacity = printed_rho * printed_cp
    return {
        "source_location": "2019 paper Table1 and Eqs(6)-(7), p5",
        "copper": {"density_kg_m3": rho_c, "specific_heat_j_kg_k": cp_c, "conductivity_w_m_k": k_c},
        "epoxy": {"density_kg_m3": rho_e, "specific_heat_j_kg_k": cp_e, "conductivity_w_m_k": k_e},
        "copper_volume_fraction": fraction,
        "fraction_status": "0.45 is inferred from the printed density/conductivity, not measured packing",
        "density_kg_m3": density,
        "copper_mass_fraction": fraction * rho_c / density,
        "mass_consistent_specific_heat_j_kg_k": mass_cp,
        "volume_average_specific_heat_j_kg_k": volume_average_cp,
        "constituent_volumetric_capacity_j_m3_k": capacity,
        "series_conductivity_w_m_k": series_k,
        "parallel_conductivity_w_m_k": parallel_k,
        "radial_diffusivity_m2_s": series_k / capacity,
        "axial_diffusivity_m2_s": parallel_k / capacity,
        "printed_bulk": {"density_kg_m3": printed_rho, "specific_heat_j_kg_k": printed_cp,
                         "radial_conductivity_w_m_k": 1.8145, "axial_conductivity_w_m_k": 180.55,
                         "implied_volumetric_capacity_j_m3_k": printed_capacity},
        "printed_capacity_excess_percent_of_constituent_value": 100 * (printed_capacity / capacity - 1),
        "constituent_capacity_reduction_percent_of_printed_value": 100 * (1 - capacity / printed_capacity),
        "interpretation": "Arithmetic consistency issue in the printed table; the actual NASA COMSOL material input and physical packing are not known.",
        "slot_liner": {
            "thickness_m": .00025,
            "printed_conductivity_w_m_k": 139.,
            "manufacturer_nomex410_conductivity_at_150c_w_m_k": .139,
            "manufacturer_original_units": "139 mW/(m K), 0.25 mm Nomex 410, Table IV",
            "printed_areal_resistance_m2_k_w": .00025 / 139,
            "manufacturer_areal_resistance_m2_k_w": .00025 / .139,
            "resistance_ratio_manufacturer_to_printed": 1000.,
            "actual_grade_and_comsol_input_verified": False,
            "interpretation": "Possible milli-unit transcription issue; grade, temperature dependence, contact and actual model input remain unverified.",
        },
    }


def _historical_transport(speed):
    geometry = historical_channel_geometry()
    return channel_transport(speed, area_m2=geometry["flow_area_m2"],
                             wetted_perimeter_m=geometry["wetted_perimeter_m"], length_m=.105,
                             heated_area_m2=geometry["heating_hypotheses_m2"]["two_long_side_walls"])


def _velocity_case(speed):
    geometry = historical_channel_geometry()
    transport = _historical_transport(speed)
    h, capacity = transport["h_w_m2_k"], transport["air_capacity_w_k"]
    heating = {}
    for label, area in geometry["heating_hypotheses_m2"].items():
        heating[label] = {"heated_area_m2": area, "ua_w_k": h * area,
                         "unit_temperature_response": isothermal_channel_response(h * area, capacity)}
    fin_cases = []
    for thickness in FIN_THICKNESSES_M:
        efficiency = straight_fin_efficiency(h, 201., thickness, .017)
        effective_area = geometry["base_area_m2"] + efficiency * geometry["fin_side_area_per_cell_m2"]
        fin_cases.append({
            "assumed_fin_thickness_m": thickness, "assumed_fin_height_m": .017,
            "source_aluminum_conductivity_w_m_k": 201.,
            "fin_efficiency": efficiency,
            "cross_thickness_biot": h * thickness / (2 * 201.),
            "effective_heated_area_m2": effective_area,
            "ua_w_k": h * effective_area,
            "unit_temperature_response": isothermal_channel_response(h * effective_area, capacity),
        })
    return {"transport": transport, "heating_hypotheses": heating, "fin_thickness_sensitivity": fin_cases}


def _matched_comparison():
    # Read-only comparison: import metrics only here. No historical parameters
    # are injected into final-nacelle CAD, contacts, losses or temperatures.
    from .nacelle_geometry import nacelle_metrics, GEOMETRY_SOURCE_SHA256
    from .nacelle_source_audit import SOURCE_DATA, SOURCE_DATA_SHA256, station_properties
    broad = nacelle_metrics()["channels"]["motor_slots"]
    geometry = historical_channel_geometry()
    length = .105
    equivalent_area = station_properties(SOURCE_DATA["cases"]["initial_climb"]["2a_s"])["flux_equivalent_area_m2"]
    equivalent_count = equivalent_area / geometry["flow_area_m2"]
    broad_heated = broad["heated_area_m2"] * length / broad["length_m"]
    rows = []
    for speed in VELOCITIES_M_S:
        historic = _historical_transport(speed)
        wide = channel_transport(speed, area_m2=broad["area_m2"],
                                 wetted_perimeter_m=broad["wetted_perimeter_m"],
                                 length_m=length, heated_area_m2=broad_heated)
        results = {}
        for label, transport, area in (("historical_narrow", historic, geometry["flow_area_m2"]),
                                       ("current_broad_slot", wide, broad["area_m2"])):
            ua = transport["isothermal_wall_ua_w_k"] * equivalent_area / area
            capacity = transport["air_capacity_w_k"] * equivalent_area / area
            response = isothermal_channel_response(ua, capacity)
            results[label] = {"hydraulic_diameter_m": transport["hydraulic_diameter_m"],
                              "reynolds": transport["reynolds"], "h_w_m2_k": transport["h_w_m2_k"],
                              "heated_area_at_equivalent_flow_area_m2": transport["heated_area_m2"] * equivalent_area / area,
                              "ua_at_equivalent_flow_area_w_k": ua,
                              "effective_inlet_conductance_w_k": response["effective_inlet_to_wall_conductance_w_k"],
                              "friction_pressure_drop_pa": transport["friction_pressure_drop_pa"],
                              "mass_flow_at_equivalent_flow_area_kg_s": capacity / AIR["specific_heat_j_kg_k"],
                              "correlation_status": transport["correlation_status"]}
        rows.append({"velocity_m_s": speed, **results,
                     "narrow_to_broad_ua_ratio": results["historical_narrow"]["ua_at_equivalent_flow_area_w_k"] / results["current_broad_slot"]["ua_at_equivalent_flow_area_w_k"],
                     "narrow_to_broad_friction_drop_ratio": historic["friction_pressure_drop_pa"] / wide["friction_pressure_drop_pa"]})
    return {
        "purpose": "Hypothetical geometry scale comparison at equal flow area, bulk speed, properties, axial length and heated-side boundary; not a hardware upgrade or pressure-network solution.",
        "boundary": {"length_m": length, "heated_surface": "two long/straight side walls, isothermal; base and top unheated; fin efficiency omitted for both", "wall_minus_inlet_k": 1., "air": dict(AIR)},
        "flux_equivalent_area_m2": equivalent_area,
        "flux_area_source": "2023 Table7 station2a_s; initial-climb mean-property area hypothesis only",
        "source_data_sha256": SOURCE_DATA_SHA256,
        "current_geometry_source_sha256": GEOMETRY_SOURCE_SHA256,
        "equivalent_historical_channel_count": equivalent_count,
        "equivalent_count_is_actual_geometry": False,
        "equivalent_count_note": "Fractional A_equivalent/(a*b); never rounded, fitted, or interpreted as actual fin/channel count.",
        "current_rom_actual_parameter_slot_count": broad["slot_count"],
        "current_rom_native_length_m": broad["length_m"],
        "current_rom_native_flow_area_m2": broad["area_m2"],
        "current_rom_native_heated_area_m2": broad["heated_area_m2"],
        "current_rom_native_hydraulic_diameter_m": broad["hydraulic_diameter_m"],
        "rows": rows,
    }


def historical_motor_benchmark():
    """Compact, deterministic JSON-ready historical component evidence."""
    sweep = [_velocity_case(speed) for speed in VELOCITIES_M_S]
    responses = [item["unit_temperature_response"] for row in sweep
                 for item in list(row["heating_hypotheses"].values()) + row["fin_thickness_sensitivity"]]
    return {
        "schema": "aerolab-historical-motor-benchmark-v1", "model_id": MODEL_ID,
        "source_code_sha256": SOURCE_CODE_SHA256,
        "experimental_validation": False, "calibration_performed": False,
        "modifies_final2023_rom": False,
        "applicability": [
            "Dated 2019 narrow motor heat-sink channel/material component subcase; not final2023 geometry or an aircraft temperature prediction.",
            "No source-defined channel count, fin thickness, heated-wall allocation, contact geometry or solid volume; no full-motor transient or hotspot is inferred.",
            "The rectangular hydraulic diameter is source-defined. Two-, three- and four-wall heating are explicit idealizations, not recovered NASA boundary conditions.",
            "Smooth developed-flow friction/Gnielinski with hydraulic diameter is unvalidated for the noncircular real channels; source 12-40m/s and Re3000-10000 are uncertain estimates.",
            "The 12m/s point falls slightly below Re3000 with our declared constants and is retained only as flagged extrapolation; transition-sensitive points are not smoothed or fitted.",
            "Friction-only pressure excludes entrance/exit, turning, contraction, roughness and rotating flow. Fin corrections omit contact, spreading, end faces, curvature and axial solid conduction.",
            "Finite air capacity is included analytically. The +1K response and fin-thickness sweep establish equation scales, not actual motor temperatures or an optimization.",
        ],
        "sources": {"historical_nasa": SOURCE_URL, "nomex_manufacturer_authored_distributor_copy": NOMEX_URL,
                    "smooth_friction_reference": FRICTION_URL},
        "source_access_notes": {"nomex": "Manufacturer-authored primary datasheet, distributor-hosted historical copy, p6 TableIV visually checked; current official URL redirected", "nomex_pdf_sha256": "ddd32f71661ac495062c76f91fa6aa2b3be9772ae0f4e82e9310191bcada5533", "historical_date": "2019 NTRS archive record; not evidence of final2023 hardware configuration"},
        "geometry": historical_channel_geometry(),
        "air_assumptions": {**AIR, "status": "Frozen representative near-room-temperature constants; NASA test-air properties were not tabulated", "source_reported_velocity_range_m_s": [12, 40], "source_reported_reynolds_range": [3000, 10000]},
        "fin_assumptions": {"conductivity_w_m_k": 201., "height_m": .017,
                            "thickness_scenarios_m": list(FIN_THICKNESSES_M),
                            "open_flow_area_held_fixed": True, "not_fixed_envelope_design_sweep": True,
                            "status": "17mm dimension interpreted as fin height; thicknesses are unfitted illustrative sensitivities, not recovered dimensions",
                            "boundary": "isothermal base; two-side thin straight-fin conduction; insulated tips; no top-wall heating; base area aL"},
        "velocity_sweep": sweep,
        "materials": winding_material_audit(),
        "matched_condition_comparison": _matched_comparison(),
        "verification": {
            "scope": "Equation/algebra/numerical verification only; does not validate source geometry, material grade or physical temperatures",
            "maximum_energy_balance_residual_w": max(abs(item["energy_balance_residual_w"]) for item in responses),
            "maximum_independent_midpoint_quadrature_relative_error": max(item["quadrature_relative_error"] for item in responses),
            "test_coverage": ["independent geometry units", "independent f/Re/Pr/Nu/pressure arithmetic", "fin ODE finite-volume refinement", "differential air-energy integral", "constituent mass/energy mixing", "matched flow/length/boundary", "input rejection", "reproducible JSON"],
        },
    }
