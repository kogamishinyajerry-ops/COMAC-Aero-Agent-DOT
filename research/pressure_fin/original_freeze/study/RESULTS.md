# Declared synthetic pressure/mass/fault screening results

declared synthetic component-scale screening exercise; not aircraft validation.

Numerical verification: **passed**. All 36 design-scenario gates: **True**. All 18 sensitivity gates: **True**.

## Baseline and combined fault

The baseline has 16 fins, 0.86 mm thickness, and 37.784 g of fin-only aluminum. Under the declared 60 W load, the required uniform-base temperature is 81.36°C at 25 Pa and 105.45°C at 15 Pa with the first interior branch sealed. The synthetic ceiling is 85°C. This is not a local hot-spot calculation. High failed-case temperatures below are constant-property linear extrapolations, not validated high-temperature predictions.

| Case | Pressure (Pa) | G (W/K) | Required base at 60 W (°C) | Total flow (g/s) | Dissipation (mW) |
|---|---:|---:|---:|---:|---:|
| nominal | 25 | 1.06458 | 81.36 | 1.66592 | 34.591 |
| pressure_loss | 15 | 0.79467 | 100.50 | 0.99955 | 12.453 |
| asymmetric_blockage | 25 | 0.99874 | 85.08 | 1.56794 | 32.557 |
| combined_fault | 15 | 0.74578 | 105.45 | 0.94076 | 11.720 |

At fixed common pressure, branch closure changes mass fractions; open-branch absolute flows stay unchanged. The sealed fluid retains transverse conduction but has no advected inlet state. Dissipation is not electrical fan power.

Viscous heat generation is omitted from the thermal PDE. Across this sweep, the reported hydraulic dissipation is at most 0.171% of the 60 W load. Conservation gates apply to the stated thermal model, not a complete installed-system energy balance.

## All nine designs retained

| N | Thickness (mm) | Fin mass (g) | Nominal base (°C) | Combined-fault base (°C) | Maximum nominal Re | Status |
|---:|---:|---:|---:|---:|---:|---|
| 12 | 0.60 | 19.770 | 81.96 | 100.02 | 3287.5 | outside declared Re scope; combined temperature fails |
| 12 | 0.86 | 28.338 | 83.92 | 102.92 | 2567.3 | outside declared Re scope; combined temperature fails |
| 12 | 1.20 | 39.541 | 87.46 | 108.46 | 1773.6 | nominal temperature fails; combined temperature fails; dominated within Re scope |
| 16 | 0.60 | 26.361 | 76.05 | 93.56 | 1195.0 | combined temperature fails; on Re-scope Pareto set |
| 16 | 0.86 | 37.784 | 81.36 | 105.45 | 817.3 | combined temperature fails; dominated within Re scope |
| 16 | 1.20 | 52.721 | 101.08 | 147.54 | 817.3 | mass fails; nominal temperature fails; combined temperature fails; dominated within Re scope |
| 20 | 0.60 | 32.951 | 81.93 | 113.72 | 817.3 | combined temperature fails; dominated within Re scope |
| 20 | 0.86 | 47.229 | 110.36 | 167.16 | 817.3 | mass fails; nominal temperature fails; combined temperature fails; dominated within Re scope |
| 20 | 1.20 | 65.902 | 215.30 | 329.83 | 817.3 | mass fails; nominal temperature fails; combined temperature fails; dominated within Re scope |

Conditional nominal passes: n16_t600, n16_t860, n20_t600. Conditional combined-fault passes: none.

The mass/combined-temperature Pareto set within the declared Reynolds scope is n16_t600. Pareto status is a relative geometric screening result, not proof of feasibility, robustness, or validation. All dominated and nonlaminar extrapolation results remain in the JSON.

## Numerical evidence

The maximum declared spatial-pair G difference is 0.0689%, below 0.5%. The maximum axial-pair difference is 0.0169%, below 0.2%. These differences are discretization indicators, not uncertainty bounds.

Independent limits include exact rectangular hydraulic conductance, an isothermal-fin/uniform-velocity continuum heat-equation series, a uniform-bath analytical fin, adiabatic walls, low-flow heat-capacity saturation, reflection symmetry, and pressure/branch network identities. Strict mass, pressure, wall-force, componentwise thermal, temperature-bound, and energy checks apply to the saved runs.

## Baseline sensitivities

| Case | Perturbation | G change (%) | Required base at 60 W (°C) |
|---|---|---:|---:|
| combined_fault | heatcap_multiplier = 0.95 | -3.298 | 108.20 |
| combined_fault | heatcap_multiplier = 1.05 | +3.163 | 102.99 |
| combined_fault | ka_multiplier = 0.95 | -1.797 | 106.92 |
| combined_fault | ka_multiplier = 1.05 | +1.665 | 104.14 |
| combined_fault | ks = 167.0 | -0.190 | 105.61 |
| combined_fault | ks = 237.0 | +0.113 | 105.36 |
| combined_fault | mu_multiplier = 0.95 | +3.326 | 102.86 |
| combined_fault | mu_multiplier = 1.05 | -3.138 | 108.06 |
| combined_fault | profile = plug | +10.818 | 97.60 |
| nominal | heatcap_multiplier = 0.95 | -2.587 | 82.86 |
| nominal | heatcap_multiplier = 1.05 | +2.467 | 80.00 |
| nominal | ka_multiplier = 0.95 | -2.470 | 82.79 |
| nominal | ka_multiplier = 1.05 | +2.350 | 80.07 |
| nominal | ks = 167.0 | -0.300 | 81.53 |
| nominal | ks = 237.0 | +0.179 | 81.26 |
| nominal | mu_multiplier = 0.95 | +2.593 | 79.94 |
| nominal | mu_multiplier = 1.05 | -2.461 | 82.78 |
| nominal | profile = plug | +18.974 | 72.37 |

These are illustrative baseline-only sensitivity scenarios, not confidence bounds. Plug flow holds the pressure-derived mean flux fixed and changes only the thermal advection profile; it is not a valid no-slip momentum solution. Its sensitivity cannot be used to declare uncertain alternatives physically validated.

## Limits and provenance

Read README.md and presweep_plan.json for the full boundary/omission ledger. Key limits are the fixed-temperature base, assumed fully developed laminar velocity, omitted inlet/outlet/development losses, no contact/base/axial-solid conduction, constant properties, and the ideal branch-sealing fault. No aircraft validation or new experimental comparison is claimed.

The plan precedes these new numerical runs but follows the earlier experimental campaign. No requirements or coefficients were chosen after inspecting this sweep. The original experimental model and freeze were not changed.

Every JSON is below 100 kB and every binary is checked below 250 kB. Original source-input hashes and all study artifact hashes are recorded in manifest.json.
