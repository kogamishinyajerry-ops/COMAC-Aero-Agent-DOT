# Conditional cooling-pressure requirement

Conditional inverse boundary design in an existing constant-property synthetic model; no empirical fitting, physical validation, installed pressure specification or guaranteed engineering margin.

All original failures remain: at the unchanged original 25 Pa nominal / 15 Pa combined boundary, neither geometry rejects 60 W at an 85°C uniform base. The inverse calculation asks what new synthetic available mechanical pressure-loss budget P would be required if the combined state receives 0.6 P with the same branch sealed. The 60 W / 85°C / 25°C / 40 g requirements remain fixed.

| Geometry | Fin-only mass (g) | Original combined base (°C) | Capacity at 85°C (W) | Deficit (W) |
|---|---:|---:|---:|---:|
| 16 fins × 0.86 mm | 37.78358 | 105.45280 | 44.74673 | 15.25327 |
| 16 fins × 0.60 mm | 26.36064 | 93.55992 | 52.50881 | 7.49119 |

## Pressure roots

K is a uniform illustrative end-loss coefficient. K=0 recovers the accepted model exactly. K=1 and K=2 are synthetic model-form scenarios, not measured uncertainty bounds. Results below are conditional and pending the independent review recorded separately.

| Geometry | K | Original K=0, 15 Pa capacity / 60 W | Main P bracket, rounded outward (Pa) | Main P (Pa) | Combined 0.6P (Pa) | Spatial root P (Pa) | Axial root P (Pa) | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 16 fins × 0.86 mm | 0 | 44.747 / 60 | [41.77, 41.78] | 41.77 | 25.06 | 41.80 | 41.76 | Numerical gates passed |
| 16 fins × 0.86 mm | 1 | 44.747 / 60 | [57.06, 57.07] | 57.07 | 34.24 | 57.11 | 57.04 | Numerical gates passed |
| 16 fins × 0.86 mm | 2 | 44.747 / 60 | [72.35, 72.36] | 72.36 | 43.42 | 72.41 | pending | Incomplete; resource limit |
| 16 fins × 0.60 mm | 0 | 52.509 / 60 | [33.17, 33.18] | 33.18 | 19.91 | 33.21 | 33.17 | Numerical gates passed |
| 16 fins × 0.60 mm | 1 | 52.509 / 60 | [49.04, 49.05] | 49.05 | 29.43 | 49.09 | 49.03 | Numerical gates passed |
| 16 fins × 0.60 mm | 2 | 52.509 / 60 | [64.87, 64.88] | 64.88 | 38.93 | 64.93 | pending | Incomplete; resource limit |

The JSON retains exact directly evaluated pressure endpoints and capacities below/above 60 W. The table rounds those brackets outward to 0.01 Pa for readability, using the verified monotonic model; no extra endpoint evaluations are implied. Root tolerance is 0.00005 Pa. Mesh differences are numerical indicators, not physical uncertainty bounds. No endpoint supplies guaranteed engineering headroom.

## Domain and omitted mechanical heating

Re is based on mean channel speed and hydraulic diameter. Mach uses the conservative upper-envelope local speed and inlet-based sound speed. Both the nominal all-open P state and the combined 0.6P sealed state must pass Re<2300 and Mach<0.1 before any thermal solve.

| Geometry | K | Nominal max Re | Combined max Re | Nominal max Mach bound | Combined max Mach bound | Combined dissipation (mW) | Nominal dissipation (mW) | Combined/nominal omitted heating (% of 60W) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 fins × 0.86 mm | 0 | 1365.588 | 819.353 | 0.03148 | 0.01889 | 32.7205 | 96.5701 | 0.05453 / 0.16095 |
| 16 fins × 0.86 mm | 1 | 1210.235 | 819.130 | 0.02790 | 0.01888 | 44.6996 | 116.9557 | 0.07450 / 0.19493 |
| 16 fins × 0.86 mm | 2 | 1160.466 | 819.039 | 0.02675 | 0.01888 | 56.6790 | 142.2152 | 0.09446 / 0.23703 |
| 16 fins × 0.60 mm | 0 | 1585.895 | 951.537 | 0.03304 | 0.01982 | 29.5715 | 87.4979 | 0.04929 / 0.14583 |
| 16 fins × 0.60 mm | 1 | 1372.365 | 945.376 | 0.02859 | 0.01969 | 43.8989 | 113.3217 | 0.07316 / 0.18887 |
| 16 fins × 0.60 mm | 2 | 1315.303 | 942.912 | 0.02740 | 0.01964 | 58.1795 | 144.2230 | 0.09697 / 0.24037 |

Dissipation is passive pressure-drop dissipation, not electrical fan power. The JSON reports friction/end-loss contributions and conservation separately. Viscous and end-loss heating are omitted from the thermal PDE. Temperatures are required uniform-base values, not hot spots.

## Evidence and interpretation

- Frozen plan: plan.json and plan.sha256; pre-run reviewer clarification: pre_numerics_clarification.json
- All full-array numerical records: runs/; all three roots and exact sign brackets per scenario: results/
- Equations, monotonicity argument, mechanical boundary meaning and falsifiable measurement needs: SCOPE_AND_MEASUREMENT.md
- Immutable-source and aggregate numerical checks: audit.json when available; independent reviewer evidence: review/

This compares only the two declared fin geometries. It does not establish a system optimum: pressure-source electrical power, base/duct/installation mass, structural limits and manufacturing constraints remain unmodeled. The original model assumes ideal common-pressure reservoirs, fully developed laminar velocity, finite fin conduction with real floor ownership, sealed-fluid transverse conduction, constant properties and a uniform fixed-temperature base. It omits base spreading/contact resistance, axial solid/fluid conduction, actual fan/feeder coupling, hydrodynamic development, radiation and installed-system geometry. Measure matched pressure–flow and thermal performance, fault leakage and supply operating points before using these roots as hardware requirements.
