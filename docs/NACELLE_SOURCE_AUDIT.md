# Source-station audit: what can actually be inferred?

The current full-load nacelle does not reproduce the published X-57 temperatures. Before changing a convection coefficient, this audit tests the reconstructed flow geometry and the assumption that one fixed scalar pressure resistance transfers between operating conditions.

It uses [Borer, Bui and Smith, NTRS 20230006888](https://ntrs.nasa.gov/api/citations/20230006888/downloads/Borer_Bui_Smith_X-57_thermal_analysis.pdf), Tables 7–9, printed pages 15–17. All 99 rows and 594 numbers have been transcribed into `data/nasa_x57_modii_stations.json` and independently checked against the source. These are published CFD results, not flow measurements.

## Reproduce

```sh
python scripts/generate_source_audit.py --check
python -m unittest tests.test_nacelle_source_audit -v
```

The bounded `examples/nacelle_source_audit.json` contains the source-data and audit-code hashes, geometry identity, calculations and printed-rounding intervals. This diagnostic does not change the CAD, the existing nacelle model or its saved evidence.

## 1. A strong geometry clue, with an important limit

For each station, form a density proxy from the printed static pressure and temperature, then an equivalent area:

```text
rho_proxy = p_static / (R_air T_static)
A_flux_equivalent = mass_flow / (rho_proxy u_streamwise)
```

The source says station properties are averaged over the entire flow cross-section (printed page 9). It does not specify the weighting operator for each variable. In a nonuniform flow, a product of these averages need not equal the corresponding integrated flux. Thus this calculation is an **effective flow-area hypothesis**, not a recovered CAD section or an independent geometry measurement.

Nevertheless, repeatability over the three published conditions is informative. The same CFD geometry underlies those cases, so they are not three independent geometric measurements.

| Path / source station | Initial-climb equivalent area, m² | Current ROM area, m² | Three-case span / initial inference |
| --- | ---: | ---: | ---: |
| Main inlet / 1_c | 0.0202520 | 0.0559425 | 0.069% |
| Motor gap / 2a_g | 0.0021171 | 0.0059112 | 0.428% |
| Stator cooling slots / 2a_s | 0.0096975 | 0.0061539 | 0.427% |
| Bypass inlet / 1_b | 0.0108550 | 0.0248456 | 0.442% |

The reconstructed motor gap is about 2.79 times the initial-climb equivalent area, while its slot area is about 0.63 times it. This is consistent with the ROM sending too much of its motor flow through the gap and too little through the slots. It is not enough to identify which real dimensions, losses or profile effects are responsible.

If, additionally, the ROM's own concentric annulus and outer radius are assumed, the initial gap area inverts to a 2.123 mm gap. This is only a geometric hypothesis inside that assumed topology. It is not a NASA dimension, an authorized change to the baseline, or a design recommendation.

Every numerical interval in this audit covers the printed rounding alone: ±0.005 psi, ±0.005 °C, ±0.05 ft/s and ±0.0005 lbm/s. Those intervals do not cover source model error, unresolved profiles, dimensional uncertainty or unknown averaging.

## 2. A single fitted resistance fails a cross-condition check

Use only initial climb to infer each conditional effective conductance:

```text
G = mass_flow / sqrt(2 rho_inlet (p_total_inlet - p_total_outlet))
predicted_mass_flow = fixed_G sqrt(2 rho_inlet delta_p_total)
```

`G` has the dimensions of area and represents `A/sqrt(K)` in a quadratic model. It does not identify area and loss coefficient separately. For the main-to-gap and main-to-slot diagnostics, station 1_c and station 4 supply the pressure drop, while station 2a_g or 2a_s supplies the comparison mass flow.

Cruise climb and dash are **retrospective cross-condition checks**, using no refitting. They are not blinded holdouts. They also supply their internal downstream pressure as an input, so this is not a predictive network validation.

| Conditional path | Cruise-climb flow error | Dash flow error | Dash error interval from printed rounding only |
| --- | ---: | ---: | ---: |
| Main inlet to gap | −7.11% | −19.64% | [−23.09%, −16.00%] |
| Main inlet to slots | −6.96% | −19.20% | [−22.15%, −16.08%] |
| Bypass inlet to mix | −3.48% | −9.27% | [−13.17%, −5.08%] |

Even after fitting initial climb exactly, the whole-motor scalar relation misses the dash flow well beyond the table-rounding interval. This rejects that simple transfer assumption; it does not establish the unique missing physics.

The local slot-core relation (2a_s to 2c_s) appears to transfer better: the nominal cruise error is approximately −0.0024%. But its rounding interval is approximately **[−16.87%, +21.06%]** because the pressure difference is only 0.05–0.06 psi. Reporting the tiny nominal error without this interval would overstate the evidence. Similarly, the local gap-core dash result remains rounding-compatible with zero error. Those local tests do not validate convection or motor rotation.

## 3. Streamwise speed is not total kinetic energy

At initial-climb station 1_c, the source reports a streamwise speed of about 11.92 m/s. A compressible isentropic inversion of its printed total/static pressure implies an energy-equivalent speed near 39.6 m/s; total/static temperature provides a similar scale.

These calculations do not recover a velocity vector. Transverse or rotational motion and the different averaging operators can contribute. The source explicitly resolves rotating walls and propeller-induced flow, whereas the ROM uses one-dimensional ducts. The discrepancy is a warning against silently interpreting the total pressure as exclusively streamwise kinetic head, or adding an unverified rotation multiplier.

## 4. Do not infer exact heat partition from products of station means

Using the printed mass flows and total temperatures at 1_c/1_b and 2c_g/2c_s/2c_b gives apparent motor heat gains of about 7.94, 6.14 and 7.76 kW. Table 4's corresponding motor heat loads are 5.819, 4.662 and 5.819 kW.

This calculation uses inlet total temperature as the enthalpy reference so a small mass mismatch does not multiply an arbitrary temperature datum. It is still **not an integrated control-volume energy balance**. The source reports section averages, and station coverage, velocity/temperature correlations, rotating-wall work and other details remain unresolved. The discrepancy does not demonstrate a NASA conservation failure and cannot be used to fit exact wall heat fractions.

## What this changes in the engineering decision

1. Characterize the main inlet, gap, cooling-slot bank and bypass restriction separately; aggregate motor flow agreement is insufficient
2. Check whether the current winding-sector gaps represent the actual stator cooling passage bank at all, before fitting their losses
3. Preserve source node semantics: Table 5 feeds component models at selected inlet/midstream stations, not at the ROM's hottest downstream wall patch
4. Use independently verified subcases to study cross-wall coupling and actual channel dimensions; do not call their success an aircraft-level validation
5. Keep any future source-informed reconstruction distinct from the current baseline and show its pre/post results, calibration inputs, cross-condition errors and still-missing validation data
