# Public experimental benchmark search — 2026-09-30

## Decision

**A genuine, independent experimental source with printed measurements was found, but no source inspected is a drop-in physical validation of the existing infinite-parallel-plate, constant-property, fully developed-velocity, prescribed-flux solver.** The most reproducible next comparison is a finite-width, isothermal rectangular-duct extension against measured outlet temperatures in Wibulswas (1966). Keep it a qualified historical experimental comparison until its input/property conventions and uncertainty have been audited. Do not tune the aircraft ROM from this comparison.

This was a read-only source investigation. No model, UI, coefficient, aircraft geometry, or publication was changed. Source PDFs are excluded from tracked documentation.

## 1. Best printed-data candidate: Wibulswas, UCL, 1966

Primary [repository record](https://discovery.ucl.ac.uk/id/eprint/1381757/) and [thesis PDF](https://discovery.ucl.ac.uk/1381757/1/388313.pdf): P. Wibulswas, *Laminar-flow heat-transfer in non-circular ducts*, University of London doctoral thesis. The scan has 150 PDF pages; the inspected printed/PDF page numbers agree.

Source facts:

- Atmospheric air; 1 × 2 in rectangular section; nominal Pr = 0.72. A 30 in divergent inlet followed by 36 in straight duct was used to develop velocity (pp21–24)
- Water-jacketed copper isothermal-wall test, 1/8 in wall, lengths 24, 13, 7.5 in (p27). Appendix 7.6, pp124–125, contains measured inlet, outlet, wall temperatures and reduced Re/Gz/Nu. The 24 in block has 12 runs, Re 655–1555
- Appendix 7.5, pp122–123, instead concerns electrical constant heat input per length, with wall stations 7.5, 12, 23.5 in in a 29.5 in section (pp64–67)
- Temperature-circuit capability is about 0.05°F (p30), not total experimental uncertainty. The velocity-profile check reports worst measurement accuracy about 14% (p24). A complete propagated uncertainty budget was not located
- The author discusses variable properties and buoyancy (pp111–113). The explicit flow-inversion test is for the flux apparatus; its percentages are not an isothermal uncertainty bound. No machine-readable measurements were located

### Measured-temperature sentinels, not digitized curves

These three rows were visually checked on p124. They are selected audit examples, not a new dataset or statistical sample. Temperatures are °F. `theta_out = (Tw − Tout)/(Tw − Tin)` is calculated here; Fahrenheit offsets cancel.

| Re | Gz | Tin | Tout | Tw | Calculated theta_out | Printed mean Nu |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 655 | 26 | 70.0 | 107.5 | 143.3 | 0.48840382 | 4.5 |
| 1060 | 42 | 69.0 | 102.5 | 149.2 | 0.58229426 | 5.4 |
| 1555 | 62 | 69.5 | 100.0 | 148.0 | 0.61146497 | 6.8 |

### Independent reduction audit

For a constant-property duct, using hydraulic diameter, `Gz = Re Pr Dh/L` and logarithmic-mean heat transfer implies:

`Nu_mean = −(Gz/4) ln(theta_out)`

The three printed-temperature/Gz pairs give 4.65798, 5.67818, and 7.62441, respectively, rather than the printed Nu column. This is a **reduction-convention/property-consistency warning**, not proof that the measurements are wrong. It prevents treating the author's Nu table as an exact interchangeable target. The existing solver must not be checked against that column without resolving the discrepancy.

Additional scan checks: Appendix 7.6 has 32 rows (12/11/9 for 24/13/7.5 in). Several p125 Re cells are genuinely blank and must remain null, rather than being interpolated. Page 124's 13 in, Re980 row prints Nu6.7, despite erroneous OCR. The source calls the flux-test range transitional on p64 and says the constant-temperature series used the same range on p68. Therefore no uncertainty-backed pure-forced laminar subset has been established, even though the tabulated Re values are conventionally low. This source caveat must accompany an ideal laminar comparison; it must not be used to discard inconvenient residuals.

### Concrete comparison to build next

1. Freeze a source transcription, input/output roles, property convention, and model version before calculating agreement. Double-enter all rows from the scan, preserving printed digits and recording ambiguities; OCR alone is insufficient
2. Extend the fluid calculation to a **finite 2:1 rectangle**, no-slip on all four sides, with all-four-wall Dirichlet temperature. Solve the rectangular Poisson velocity field and march the cross-sectional energy equation. Verify with independently derived fully developed and entrance references before using experiment
3. Use geometry, inlet temperature, imposed wall temperature and flow information as inputs. Compare **outlet attenuation**, not the imposed wall temperature. Nondimensional use of reported Gz avoids inventing a pressure or mass flow, but must be labeled a conditional comparison using the author's reduced flow/property input
4. Report the complete 24 in series first; assess shorter lengths separately. This is a predeclared analysis split, not a blinded holdout, because this audit has inspected the published results. Do not select only favorable low-Gz points
5. No fitted h multiplier, conductivity, entrance correction, buoyancy correction, or geometry is permitted. Independent property alternatives and idealized versus developing-inlet sensitivity cases must be specified before examining their residuals. With incomplete measurement uncertainty, report residuals and numerical/input sensitivities rather than a claimed confidence-level validation pass
6. For a later flux-boundary comparison, be explicit if net heat is inferred from measured inlet/outlet enthalpy: that outlet is then an input, and cannot also be counted as an independent energy-validation target. Constant electrical input per length is not automatically prescribed equal fluid-side flux on every wall

## 2. More relevant fin geometry, weaker public data: Pires-Fonseca & Carrasco-Altemani, 2024

Primary [journal article](https://revistas.udea.edu.co/public/journals/recursos_html/RFIUA-Html/rfiua-n110/n110a8.html), DOI [10.17533/udea.redin.20230417](https://doi.org/10.17533/udea.redin.20230417), pp86–98. Source facts: 16 aluminum fin lines; 90 mm length, 41.5 mm width, 11.3 mm fin height, 1.86 mm gap, 0.86 mm thickness; no top bypass, one-gap lateral clearances. Air, 13 thermal tests per sink, channel speeds 4–20 m/s, Re 810–3800; electrically heated base held near 40°C. Table 4 gives Nu uncertainty 2.9–3.0%, Re 4.6–5.2%, Rth 1.2%. Experimental results are plotted; no raw numerical supplement was located. Equations 13–20 are **fits to those measurements**, and Table 3 is a numerical mesh study. The printed pressure-fit labels also appear inconsistent with the discussion of which sink has higher loss; resolve from the original figure/data before use.

Recommendation: a useful future **conjugate, simultaneously developing channel** target if original test rows and flow/property values become available. Its geometry is closer to the historical motor passage than the UCL duct. A curve digitization could be an explicitly approximate comparison with added digitization uncertainty; it must not be labeled raw/exact data. Using its fitted Nu relation to predict its own experiments is circular validation. Any calibrated contact/loss term needs a separately designated calibration subset and untouched test conditions.

Follow-up: the publisher-version PDF in its Zenodo archive contains extractable vector experimental markers. A reproducible, **approximate Figure8 Rth readout**, its added graphical envelopes, and newly identified data-definition limits are documented in [the modern-fin readout audit](MODERN_FIN_EXPERIMENT_READOUT_2026-09-30.md). This improves access to plotted results, not access to raw runs.

## 3. Bypass evidence worth retaining, not a ready exact thermal table

Leonard, Teertstra, Culham & Zaghol, 2002, [author-laboratory PDF](https://www.mhtlab.uwaterloo.ca/pdf_papers/mhtl02-2.pdf), *Characterization of Heat Sink Flow Bypass in Plate Fin Heat Sinks*. Copper sinks have approximately 300 W/(m K) conductivity; 127 mm length, approximately 50 mm fins, 2.1/4.2 mm gaps, 1.2 mm fin thickness. Air approach speeds are 2–8 m/s; tip-clearance/fin-height ratios 0–1. Measurements include pressure and inter-fin profiles, but published comparison data are graphs. Table 2 gives maximum errors: thermal resistance 1.35%, Re 3.32%, inter-fin velocity 24.85%. Some reported flow is inferred from zero-bypass thermal-resistance curves, so distinguish it from direct pitot measurements. Full dimensions, property conditions and raw rows would need recovery before a reproducible no-fit network test.

## 4. Government-source exclusions and calibration traps

- [NASA TN D-6333, Presler, 1971](https://ntrs.nasa.gov/citations/19710014236): actual experiments, but **helium in a circular Inconel tube**, not an air slot. The tube is 0.089 in ID, 19 in heated length; Table I separates measured and numerical pressure columns. Local thermal results are plotted. Page 13 says emissivity 0.4 was selected through trial heat balances. Thus it is not an entirely unfitted heat-loss reference, and reproducing its radiation correction is not independent validation of radiation. Compressibility, properties and circular geometry require additional physics
- [NASA TN D-3039, Strite & Inman, 1965](https://ntrs.nasa.gov/citations/19650024645): rectangular-channel measurements, but an internally heat-generating aqueous electrolyte. Fluid-source heating and thermal boundaries differ from wall-heated air. Not a matched current-solver benchmark
- [NACA ARR 4F28, Drexel & McAdams, 1945](https://ntrs.nasa.gov/citations/19930090924): mixed review/new experimental material. Its analytical/correlated duct curves must not be promoted to independent measurements. It is a bibliography lead, not the selected validation dataset

### Further screened leads

- Hossain's [2006 Waterloo thesis](https://uwspace.uwaterloo.ca/items/8e68f5c8-e6e9-4dd4-9ccb-3170f5bda87e) supplies genuine experimental/model columns separately in Appendix C, including Rth at duct speeds1–3m/s, and detailed uncertainty in Appendix D. However, Appendix C's nominal28-fin,2.75mm-gap geometry differs from the sample inventory in Table3.1; TableC.1 also repeats duct dimensions while its pressure series differ. These need reconciliation before using a row as a fully specified case. Rth references six base sensors averaged together, and ambient is averaged from wind-tunnel inlet/exit sensors; it is not automatically source-to-inlet thermal resistance. Heater-loss estimate1.5% and radiation/heat-input treatment also need preserving. This is a stronger **tabulated fin-data lead**, not yet a cleaner accepted benchmark
- [Ragoowansi, Georgia Tech, 2025](https://repository.gatech.edu/server/api/core/bitstreams/8f2767d0-930d-4a26-8071-eaf03618bea1/content) concerns high-Pr fluids and conjugate liquid-to-liquid heat exchange. Its Appendix A has a sample data reduction; it is not an air-slot dataset
- [Benha thesis chapter5 extract](https://bu.edu.eg/portal/uploads/discussed_thesis/11151074/11151074_S.pdf) discusses a constant-flux flat-channel reference, but the retrieved extract did not provide enough geometry, uncertainty and measured numerical data to form a reproducible benchmark

## 5. Final-X-57 geometry/code check

No public final-2023 cruise-motor slot drawing, complete fin inventory, or released ICPT implementation was recovered in the inspected NASA/NTRS, NASA software-catalog and public-code searches. This is a bounded search result, **not a claim that no release exists**.

A useful newer primary constraint is Clarke & Terry's [2024 failure-modes presentation](https://ntrs.nasa.gov/citations/20240003366), [PDF](https://ntrs.nasa.gov/api/citations/20240003366/downloads/3-X-57_traction_system_failures.pdf), slides23–24: later motors used refabricated stators; new potting improved penetration from roughly 20% to 90%, with remaining voids included in the thermal analysis and reduced ICPT margin. This supports keeping historical material assumptions configuration-specific. It supplies neither final channel dimensions nor a void-distribution field. The [high-lift reference design](https://ntrs.nasa.gov/citations/20190029267) is separate hardware with skin cooling and no internal airflow, and cannot fill this cruise-motor gap.

## Source-byte provenance

Downloaded 2026-09-30; SHA-256 is over original PDF bytes, not OCR text. PDFs are working evidence, excluded from the publishable checkpoint.

| File / original primary source | Bytes SHA-256 | Local working copy |
| --- | --- | --- |
| [UCL 388313.pdf](https://discovery.ucl.ac.uk/1381757/1/388313.pdf) | `8fac58915fcb924f0fb0095f01e15c85de9af85b1f8a39405e71837e889c03ba` | `output/physics-campaign/source-bytes/ucl_388313.pdf` |
| [NASA 19710014236.pdf](https://ntrs.nasa.gov/api/citations/19710014236/downloads/19710014236.pdf) | `bfad047e952be75638e87caec4938338cc933c113a28f94cc460a0638e6d91d0` | `/tmp/nasa19710014236.pdf` |
| [NASA 19650024645.pdf](https://ntrs.nasa.gov/api/citations/19650024645/downloads/19650024645.pdf) | `d1d7dfa585ade867acefce782a849e89e25e66ca4eea294505e13a4294581179` | `/tmp/nasa19650024645.pdf` |
| [X-57 20240003366 PDF](https://ntrs.nasa.gov/api/citations/20240003366/downloads/3-X-57_traction_system_failures.pdf) | `e2acf166f59b2514f711b3896514aea317094462b7283550bab69a5519611c1f` | `/tmp/x57_failures2024.pdf` |
| [Modern-fin archived publisher PDF](https://zenodo.org/records/10975619/files/8.%20343222.pdf?download=1) | `c14571f635c5767ae3fc57f90fb18514595a54dc53918bc7454da084839c5a01` | `/tmp/fonseca2024_zenodo.pdf` |
| [Hossain thesis, Library and Archives Canada copy](https://www.collectionscanada.gc.ca/obj/s4/f2/dsk3/OWTU/TC-OWTU-856.pdf) | `a0e07642f5ef31cee76f4429d91fc08c2427189a368a0cb827df767afb20f79e` | `/tmp/hossain_heat_sink.pdf` |
| [Georgia Tech thesis](https://repository.gatech.edu/server/api/core/bitstreams/8f2767d0-930d-4a26-8071-eaf03618bea1/content) | `3aecf0a194f19a5ab1b06db95889f7237c663478763c1744f4ce6545c3b5696d` | `/tmp/gatech_channel_thesis.pdf` |
| [Benha chapter extract](https://bu.edu.eg/portal/uploads/discussed_thesis/11151074/11151074_S.pdf) | `e941d3aaa0912767d05975fe7d6010c088bfe09cceaf243f1b0e4c179df5b829` | `/tmp/benha11151074_S.pdf` |

The journal HTML and Leonard et al.'s Waterloo-laboratory PDF were inspected through the web reader, not retained as source-byte downloads; no byte hash is asserted for those reader representations. No raw author data, source-specific calibration permission, new test uncertainty, or final-aircraft validation is implied.
