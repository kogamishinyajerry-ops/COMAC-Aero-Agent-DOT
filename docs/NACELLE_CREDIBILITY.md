# What this nacelle model can support

**The refined model is useful for tracing geometry → pressure redistribution → heat balances → system tradeoffs. It does not reproduce the X-57 component temperatures at full source load.** Passing conservation or a temperature guard does not change that conclusion.

Evidence is reproducible with:

```sh
python -m unittest tests.test_nacelle_thermal -v
python scripts/generate_nacelle_credibility.py --check
```

The [six-case JSON](../examples/nacelle_credibility.json) retains canonical boundaries, geometry fingerprint, imported model-source hash, exact results, numerical residuals, source differences and inverse-UA budgets. Regenerate it after a model/geometry change with the same command without `--check`. Values below are rounded views of that evidence, not fitted targets.

## Three separate kinds of evidence

1. **Equation/software verification:** independent mass/energy balances; signed-pressure residuals; zero/reversed-flow behavior; analytical uniform-flux wall balances checked against an independent finite-volume march; the circular laminar limit checked by integrating its radial solution; smooth-duct Gnielinski equation regression. These checks test implementation.
2. **Source-analysis comparison:** [NASA Borer/Bui/Smith (2023)](https://ntrs.nasa.gov/api/citations/20230006888/downloads/Borer_Bui_Smith_X-57_thermal_analysis.pdf), Tables 4 and 6–9. Source flows are CFD outputs; source temperatures are CFD-driven ICPT estimates. Three operating points are compared without fitting any coefficient. There is no calibration/training split or validated holdout claim.
3. **Physical validation:** not performed. No nacelle airflow or component-temperature measurements validate this reconstruction. NASA also reports the absence of experimental airflow validation for its higher-fidelity Mod II CFD. The ROM additionally lacks the original dimensions, rotating boundary conditions, detailed passage/jet fields and component-specific thermal models.

## The boundary condition matters, but does not close the discrepancy

All cases below use full Table 4 heat: 7499 W per nacelle at peak, 6080 W at MCP. The inferred-pressure cases use declared ram-recovery/suction assumptions and no propeller-pressure addition. Source-pressure cases use rounded Table 7/8/9 external pressure differences, including propeller influence, without imposing source mass flows. Density remains inferred, LV left/right pressures are symmetrically averaged, and the reconstructed geometry/internal nodes remain different.

| Condition | Published ICPT winding, C | ROM winding: inferred pressure, C | ROM winding: source-pressure sensitivity, C | Source-pressure total motor flow error |
|---|---:|---:|---:|---:|
| Initial climb | 109.4 | 385.912 | 225.792 | −4.47% |
| Cruise climb | 92.2 | 282.403 | 189.973 | −14.54% |
| Dash | 85.6 | 244.376 | 224.976 | −39.48% |

The ROM value is a downstream one-dimensional winding patch plus inferred solid/contact rises. It is not a node-equivalent ICPT output. Values above 200 C are deliberately retained as **out-of-domain diagnostics**, not believable hardware temperatures. The source-pressure cruise-climb case falls below that computational guard yet is still about 97.8 C above the source estimate. This is a concrete counterexample to treating the guard as validation.

At initial climb, source pressure brings total motor flow close to the published sum while leaving its distribution wrong:

| Flow | Published CFD, kg/s | ROM source-pressure case, kg/s | Relative difference |
|---|---:|---:|---:|
| Rotor–stator gap | 0.045359 | 0.119275 | +162.96% |
| Stator slots | 0.207745 | 0.122522 | −41.02% |
| Combined motor cooling | 0.253105 | 0.241797 | −4.47% |
| Separate motor bypass | 0.107501 | 0.464153 | +331.76% |

The ROM assigns roughly 50.7% of motor cooling flow to slots, versus roughly 82.1% in the source; that split discrepancy persists across the three conditions. Incorrect bypass and local flow partition also alter downstream mixing. A near-match in one aggregate flow does not establish correct local cooling. Unknown passage dimensions and losses must be characterized before assigning the error solely to convection or rotation.

## A transparent resistance budget

Version 2 uses the source's uniformly applied winding heat as a uniform-axial-flux boundary, with exact 1-D air heating and distinct winding/magnet walls. It reports five analytical stations, not a 3-D temperature field. Uniform flux makes downstream walls hotter than their axial average. The earlier isothermal-wall approximation understated that distinction; replacing it is a fidelity correction even though the mismatch becomes larger.

At source-pressure initial climb, the limiting slot winding patch is:

| Contribution | Temperature or rise, C |
|---|---:|
| Inlet air | 35.900 |
| Axial air heating | +29.043 |
| Wall-to-air convection | +134.085 |
| Inferred solid conduction | +18.908 |
| Inferred contact | +7.856 |
| Downstream component proxy | **225.792** |

The slot's current `hA` is 26.724 W/K. At the **same flow, heat split and solid resistances**, meeting the 124 C winding reference would require 110.962 W/K, or 4.15 times current h. Reaching the 109.4 C published context value would require 202.527 W/K, or 7.58 times current h. These are inverse algebraic diagnostics, never applied enhancement factors. Removing all winding solid/contact resistance would still leave about 199.0 C at source pressure, far above the source value.

Under the default inferred pressure, the slot budget instead has +63.105 C of air heating and +260.143 C of convection rise. Its infinite-h floor is already 125.768 C because the air heating plus retained solid/contact paths exhaust the available temperature difference. No finite convection multiplier alone can bring that fixed-flow model below 124 C. This distinguishes a flow/solid-path limitation from the source-pressure case's dominant convective resistance.

## Why there is no automatic rotation multiplier

The implemented turbulent equation is the smooth-duct [Gnielinski relation](https://doi.org/10.1007/BF02559682), with an inspectable equation in the [Motor-CAD documentation](https://ansyshelp.ansys.com/public/Views/Secured/MotorCAD/v252/en/Motor-CAD_UG/MotorCAD/topics/enclosedchannelconvectioncorrelation.html). Hydraulic diameter does not make short slots, rotating annuli or LV impingement jets equivalent to fully developed circular ducts. The 2300–4000 interpolation is numerical smoothing, not a validated transition model for these passages.

The NASA motor is an **outrunner**, with the outer part rotating. NASA's CFD explicitly includes rotating walls and propeller-induced flow. Applying an inner-rotating-cylinder Taylor-vortex enhancement by analogy would be unjustified. [Aghor and Atif's outer-cylinder stability study](https://arxiv.org/abs/2303.16415) demonstrates that rotation effects depend on which wall rotates and the imposed thermal/flow conditions; it is not an X-57 heat-transfer correlation and supplies no coefficient here. No matched correlation/data for the reconstructed geometry have been established.

The API therefore separates numerical guards from correlation applicability and explicitly reports unresolved rotation, entrance development and LV jet behavior. Fixed air properties and omitted radiation, natural convection, axial/cross-patch conduction and transient storage remain additional limitations. The selected uncertainty scenarios do not bound these missing physics.

## A supportable teaching scenario

Keep all inferred pressure coefficients and materials fixed, deliberately select **0.25 of the Table 4 heat loads**, and change only the stated condition/geometry. This is a synthetic heat-load fraction, not 25% shaft power or an aircraft operating recommendation. The default remains full source heat.

| Step | Ambient, C | HV fins / top vent, mm² | Winding proxy, C | HV proxy, C | Gross geometry mass, kg |
|---|---:|---|---:|---:|---:|
| Baseline | 35.9 | 24 / 9000 | 123.403 | 54.068 | 108.204 |
| Hot-air perturbation | 45.9 | 24 / 9000 | 133.403 | 64.068 | 108.204 |
| Local HV-only change | 45.9 | 36 / 9000 | 136.524 | 62.410 | 108.939 |
| Fewer fins alone, diagnostic | 45.9 | 12 / 9000 | 130.627 | 71.094 | 107.469 |
| Combined redesign | 45.9 | 12 / 16000 | 117.508 | 71.553 | 107.466 |

More HV fins cool the HV proxy by 1.66 C but worsen the motor winding by 3.12 C, demonstrating shared backpressure. The combined redesign recovers a **nominal** +6.49 C minimum reference margin while allowing the HV proxy to warm by 7.49 C relative to the hot baseline. Motor cooling flow increases from 0.111483 to 0.141375 kg/s. Passive hydraulic dissipation rises from 300.08 to 368.59 W; this is not a blower electrical load or complete aircraft cooling-drag estimate. Gross mass is an inferred material-volume proxy.

The combined redesign's selected assumption-corner minimum margin still reaches −81.76 C, with some corners outside the thermal guard. Its apparent nominal recovery is **not robust, physically validated, flight-qualified or globally optimized**. The engineering lesson is coupled tradeoffs plus an explicit next validation step: obtain measured or adequately resolved branch splits, local h/flow behavior and component path resistances before making a hardware margin claim.
