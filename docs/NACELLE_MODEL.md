# CAD-linked Mod II nacelle network

This path is a **new, uncalibrated reduced-order model**, separate from the older 43-fin heat-sink benchmark and the mission model. It is not NASA CFD, NASA's Integrated Cruise Propulsion Thermal model (ICPT), a spatial temperature field, a flight-qualified prediction, or an optimization certificate.

## Evidence and scope

The source is [Borer, Bui and Smith, X-57 Mod II thermal analysis](https://ntrs.nasa.gov/api/citations/20230006888/downloads/Borer_Bui_Smith_X-57_thermal_analysis.pdf): flow topology and hardware in printed pp. 7–8 / Figs. 5–7, heat loads in Table 4 (p. 5), and component reference limits in Table 1 (p. 3). The source itself states that its nacelle CFD was not experimentally validated because airflow test data were unavailable. Our software conservation checks provide still less physical validation than that study.

The CAD dimensions, materials, local pressure coefficients, minor losses, convection approximations, thermal contacts and LV board heat split are explicitly inferred. Detailed source facts and reconstruction provenance are in [NACELLE_SOURCES.md](NACELLE_SOURCES.md). No source heat map is relabeled as a newly computed result.

## One parameter contract

`parse_nacelle` in `aerolab/nacelle_geometry.py` validates canonical dimensions. `nacelle_metrics` supplies every flow section, perimeter, length, heated area, component conduction dimension and solid-volume mass to `aerolab/nacelle_thermal.py`. The same dimensional parameters drive the reconstruction mesh and optional named BRep/STEP assembly. Analytic hydraulic sections are **not** CFD volume extraction. Geometry fingerprint and solver-source SHA-256 accompany every result. Both modules capture whole-file source hashes at import; the model identity composes those immutable snapshots, so a later file edit cannot make an existing process falsely claim it executed the new source. The geometry fingerprint binds its own imported source snapshot too.

Important couplings are real calculations:

- The inner main intake is the spinner-to-inner-motor annulus; its dimensions change cooling-path loss. The existing `main_inlet_height_mm` knob names the separate outer bypass-inlet lip, matching its visible CAD aperture and series friction
- Rotor-stator gap and stator cooling slots are distinct parallel paths derived from the reconstructed segmented motor, rather than treating the gap as all motor cooling
- Motor bypass competes with both motor cooling paths, changes mixed CMC inlet temperature, and changes flow available to the two HV fin arrays
- Fin count, thickness and height alter solid volume/mass, open flow area, wetted perimeter, hydraulic diameter, heat-transfer area and fin efficiency
- LV scoop aperture sets inlet pressure losses; a separately reconstructed backplate passage sets the local heat-exchange velocity and hydraulic diameter
- Outlet and top-exhaust openings change upstream pressure, redistribution and thermal results

There is no universal monotonic “more fins is better” or “more bypass is better” rule. Numerical sensitivity is not proof that a simplified local convection assumption captures the real hardware.

## Pressure graph

All pressures are gauge pressures relative to freestream. Each passive branch is connected as follows:

| Branch | From | To |
|---|---|---|
| main_inlet | main_ram | inlet_plenum |
| motor_internal (rotor-stator gap) | inlet_plenum | motor_mix |
| motor_slots | inlet_plenum | motor_mix |
| motor_bypass (separate outer intake) | bypass_ram | motor_mix |
| motor_top_exhaust | motor_mix | top_exhaust |
| cmc_hv_left / cmc_hv_right | motor_mix | lower_mix |
| cmc_bypass | motor_mix | lower_mix |
| lv_fresh_left / lv_fresh_right | lv_ram | lower_mix |
| lower_outlet | lower_mix | lower_exhaust |

The inner spinner-to-motor intake feeds the gap and slots; the outer motor bypass has its own external intake reservoir. They do not share a fictitious intake plenum. The motor cooling and motor-bypass streams **mix before** the upper exhaust and downstream CMC split. This follows the source's p. 8 description; the top-center louver is an external exit. The LV scoops separately supply ambient air to the two backplates. The lower outlet mixes the HV, LV and CMC-bypass flows. Left/right asymmetry is not claimed by the symmetric default geometry.

Boundary dynamic pressure is `q_inf = rho V² / 2`. Main, bypass and LV reservoir pressures are their respective ram-recovery factors times `q_inf`, plus an explicit optional propeller-pressure addition for each intake. All additions default to zero. Exhaust pressures are negative suction coefficients times `q_inf`; a negative top-exhaust suction coefficient represents a positive external static pressure. These coefficients/additions are user-visible assumptions, not computed external aerodynamics. No fan curve, electrical blower or artificially imposed mass flow is added. Propeller aerodynamic work, swirl, rotation and aircraft installation effects are not solved.

The optional `source_pressure_initial_climb` sensitivity preset uses NASA Table 7 total-pressure increments **above freestream total pressure**, avoiding double-counting ram pressure: 1_c13.66−0_c13.53=.13 psi for motor cooling; 1_b13.61−0_b13.53=.08 psi for bypass. Left/right LV totals13.51/13.56 psi are averaged to13.535, giving a declared symmetric .005 psi addition above13.53. Recovery factors are1 in this preset. The top/lower exit static offsets use13.42/13.39 psi relative freestream static13.41 psi. Computed dynamic pressure still uses the selected speed/density, so the rounded source pressures are not reproduced exactly. This is a source-informed boundary scenario, not fitted hardware or a validated propeller model.

For each branch:

- `Dh = 4 A / P_wetted`
- `u = |m_dot| / (rho A)` and `Re = rho u Dh / mu`
- `delta_p = sign(m_dot) (f L / Dh + K) rho u² / 2`

For serial LV scoop/backplate sections, Darcy friction is summed section-by-section with each section's velocity/Dh; the inlet minor loss uses the scoop velocity. Positive inferred `K` makes inverse branch flow bounded. Laminar Darcy friction is `64/Re` for the explicitly approximate circular-equivalent duct. Smooth-duct friction and [Gnielinski convection](https://ansyshelp.ansys.com/public/Views/Secured/MotorCAD/v252/en/Motor-CAD_UG/MotorCAD/topics/enclosedchannelconvectioncorrelation.html) apply above Re 4000. A continuous smooth interpolation joins 2300–4000 and is explicitly unvalidated.

A damped Newton solve enforces zero signed mass residual at each unknown-pressure junction, with monotone coordinate bisection as a fallback. Results expose solver iterations, convergence, each branch flow/pressure loss, node pressure, and residuals. Reversed branches retain their signed flow; heat advection follows the actual high-to-low-pressure direction. A warning indicates when the intended inlet/outlet topology is lost.

Passive hydraulic dissipation is `sum(|delta_p m_dot| / rho)`. It is **not** blower electrical power or complete aircraft cooling drag.

## Heat and lumped solids

For one nacelle the source peak loads are winding 5237 W, magnets 582 W, and two HV sinks at 810 W each. MCP values are 4196 W, 466 W and 679 W each. Each LV backplate receives 30 W at either power setting. Peak total is 7499 W; MCP total is 6080 W. MDAU and FOBE in the aft region are excluded. A declared heat-scale input multiplies all loads. The optional `reduced_load_screening` teaching preset deliberately sets that multiplier to 0.25 while retaining the other default boundaries. This means one quarter of the Table 4 heat loads, **not** one quarter motor or aircraft power: the loss-versus-power relationship is not modeled. Users must explicitly choose it; the default remains the full source heat load. Passing the declared numerical/domain checks at reduced heat does not establish physical validation.

The winding source is apportioned to the gap and stator-slot surface patches in proportion to their CAD-derived exposed area, matching the source's surface-area-distributed loading assumption. Half the magnet heat enters the gap and half the motor bypass. It is not added a second time at mixing junctions.

For a simple isothermal exchange surface:

- `UA = h A_effective`
- `C = |m_dot| cp`
- `G = C (1 - exp(-UA/C))`
- `T_surface = T_in + Q/G`
- `T_out = T_in + Q/C`

Thus `G <= C` and `G <= UA`. HV fin efficiency is `tanh(mH)/(mH)` with `m = sqrt(2h/(k t))`; it is applied once to the fin-side area, with unfinned base area kept separate.

The motor gap has distinct winding and magnet walls, rather than forcing a low-power magnet to the winding's temperature. For constant wall temperatures sharing one axial stream, the exact common-air mean is:

`T_air_mean = T_in + (Q_total/C) [1/(1-exp(-NTU)) - 1/NTU]`, with `NTU = sum(h A_i)/C`.

Each wall is `T_i = T_air_mean + Q_i/(h A_i)`. A small-NTU series avoids subtraction cancellation. Slot and gap winding proxies and inner/outer magnet proxies are returned separately; the component report uses the hottest modeled patch. Cross-conduction between patches is omitted. This is not a reconstructed temperature distribution.

Solid temperature proxies add `Q R`, with `R_conduction = L/(k A)` from component geometry and an explicit inferred contact resistance. The winding's area-proportional heat/parallel-area resistance implies a common through-thickness/contact rise based on its total heat and aggregate resistance. Magnet conduction is evaluated separately for the inner and outer CAD cylindrical face areas: each half-load uses its own `L/(k A_patch)` resistance. Its declared inferred contact resistance is per patch; the reported aggregate-area resistance is informational and is not substituted for the patch resistances. Thermal resistances are not fitted to the published CFD temperatures.

The LV backplate rejects 30 W only once. Its illustrative source split is CPU 8 W, AC/DC 12 W and other electronics 10 W; these are **not** published board-level powers. CPU and AC/DC proxies add their own CAD footprint/path conduction and declared contact resistance above the backplate. The component `heat_w` fields sum to the complete source heat without counting the same LV heat twice. The LV plate has no invented published temperature limit.

The separate main intake and bypass reservoirs allow a different source-informed total pressure for each path; widening the bypass can still raise motor-mix backpressure and reduce gap/slot flow. Every junction mixes incoming enthalpy by mass-weighted temperature. Boundary outlet enthalpy minus inlet enthalpy is compared with all generated heat. Results expose external mass balance, internal mass residuals, pressure-equation residual, energy removed and energy residual.

## Margins, uncertainty and failure modes

NASA's margined limits are 124 C for winding, 83 C for magnet, 150 C for HV FET junction and 74 C for CPU/ACDC boards. Those labels do not turn a surrogate sink/contact temperature into a measured FET junction. The UI and returned provenance identify all values as lumped proxies. Hottest component and lowest reference margin are separate quantities; a cooler LV board can have less margin than a hotter power component.

Eight screening scenarios combine pressure-drive factors 0.75/1.25, minor-loss factors 0.5/2, and low/high thermal-resistance cases (`h` factors 1.4/0.6 and contact factors 0.5/2). Returned ranges include nominal. They are selected assumption corners, **not** confidence intervals, calibrated error bars, guaranteed extrema, dimensional uncertainty bounds, or certification margins. Heat-load and geometry tolerances are not sampled.

A temperature above 200 C, Mach at least 0.3, Reynolds number above 1e6, or pressure spread exceeding 10% of the fixed reference pressure marks a result outside the declared screening envelope. The speed of sound uses the ambient absolute temperature. These computational gates do not establish validity inside the envelope. Developing flow, sharp turns, jets, stator-slot complexity and rotation can remain dominant errors even for an in-range result.

At zero total pressure drive with nonzero heat (zero airspeed and zero explicit propeller additions), the model deliberately returns null temperatures and `steady_state_exists=false`, with the unrejected heat visible as a nonzero energy residual. Natural convection and radiation are not silently invented. Zero drive and zero heat uses an explicitly conventional uniform ambient temperature. Nonconverged pressure results are flagged and must not be interpreted as solutions.

## API and verification

- `nacelle_boundary_catalog()` returns declared defaults, finite bounds, source heat loads and illustrative operating presets
- `evaluate_nacelle(geometry=None, boundary=None)` returns canonical geometry, metrics, boundary, flow nodes/branches, thermal components/summary (including `result_status`), conservation diagnostics, screening ranges and provenance
- `compare_nacelle(geometry=None, boundary=None)` solves reference and candidate at the same heat and pressure-boundary assumptions; geometry-dependent branch flows are recomputed

Unknown keys, explicit nulls, booleans as numbers, nonfinite values and out-of-range inputs are rejected. A partial object intentionally uses the catalog's declared defaults for omitted fields. Missing geometric channels or required dimensions fail rather than falling back to fixed hidden dimensions.

The returned `source_flow_diagnostic` compares computed gap/slot/bypass flow with the published initial-climb Table7 CFD station values. `source_temperature_diagnostic` compares proxies with Table6 ICPT analysis temperatures, including winding 109.4 C, magnet 45.4 C, FET 104.9 C, CPU 75.1 C and AC/DC 75.6 C. These references are not measurements, the nodes are not fully equivalent, and no coefficient is fitted to them. A large mismatch is a validation gap, not evidence the real aircraft reaches our raw out-of-domain diagnostic temperatures.

Run `python -m unittest tests.test_nacelle_thermal -v`. Tests independently recompute incidence mass balances, branch pressure equations, source heat sums and outlet enthalpy, check reverse flow and zero-flow behavior, and exercise intake/fin/bypass/LV sensitivities. These are software/equation tests, not physical calibration or aircraft qualification.
