# Untuned plate-fin conjugate benchmark: results

## Finding

The frozen finite-conductivity, fully developed velocity model predicts thermal resistance +0.507% to +5.132% above the approximate experiment across the three robustly laminar points. The fourth point is nominally laminar and has +8.626% discrepancy, but its conservative regime-screen corner reaches Re 2331. This is an honest discrepancy report, not an experimental-validation pass.

The alternative prescribed plug profile predicts Rth 16.876% to 20.483% below the experiment across the three robustly in-scope points. These profiles are model-form cases, not confidence bounds; a physical developing flow has not been solved. The apparently close plug result at the highest speed cannot validate a laminar model at Re 4334.

No heat-transfer coefficient, conductivity, geometry, cutoff or inlet field was adjusted to improve these discrepancies. The only refinement was numerical: the initial 36×108 grid narrowly failed its predeclared Poisson criterion, so it was replaced by 48×144 before evaluating target residuals.

## All 12 recoverable Figure 8 markers

Values retain plotting-derived digits for reproducibility, not experimental precision. These are loss-corrected whole-sink resistance values. The 12 markers are not a recovered raw-run table; the source text mentions 13 experiments.

| V [m/s] | Re from arithmetic geometry | Figure 8 Rth [K/W] | FD model Rth [K/W] | FD difference | Plug model Rth [K/W] | Scope |
|---:|---:|---:|---:|---:|---:|:---|
| 4.370 | 916 | 0.8830 | 0.8874 | +0.507% | 0.7340 | Robust laminar |
| 6.355 | 1332 | 0.7293 | 0.7510 | +2.966% | 0.5897 | Robust laminar |
| 8.356 | 1752 | 0.6398 | 0.6726 | +5.132% | 0.5088 | Robust laminar |
| 10.323 | 2164 | 0.5711 | 0.6204 | +8.626% | 0.4559 | Nominal laminar; boundary uncertain |
| 12.274 | 2573 | 0.5216 | 0.5817 | +11.525% | 0.4174 | Outside laminar scope |
| 13.988 | 2933 | 0.4707 | 0.5545 | +17.807% | 0.3907 | Outside laminar scope |
| 14.510 | 3042 | 0.4621 | 0.5471 | +18.416% | 0.3836 | Outside laminar scope |
| 16.216 | 3400 | 0.4266 | 0.5256 | +23.198% | 0.3628 | Outside laminar scope |
| 17.322 | 3632 | 0.3980 | 0.5132 | +28.968% | 0.3510 | Outside laminar scope |
| 18.367 | 3851 | 0.3730 | 0.5026 | +34.751% | 0.3409 | Outside laminar scope |
| 19.237 | 4033 | 0.3620 | 0.4943 | +36.538% | 0.3332 | Outside laminar scope |
| 20.673 | 4334 | 0.3311 | 0.4818 | +45.497% | 0.3215 | Outside laminar scope |

## Separate uncertainty and applicability

- Author uncertainties: Rth 1.2%; inferred speed 3.7–4.6%; Re 4.6–5.2%. The per-run uncertainty allocation and statistical coverage convention are unavailable here
- Graphical allowances: approximately±0.257 m/s and±0.0134 K/W, from half-symbol dimensions. These remain separate from author uncertainty
- The cutoff Re 2300 was declared before comparison. The conservative joint-corner regime screen uses the maximum quoted author Re allowance plus the separate graphical speed allowance solely to identify possible threshold crossing. It is not a combined confidence interval, does not assume independence, and is not used to tune residuals
- There are 3 robustly in-scope points,1 nominally in-scope but boundary-uncertain point, and 8 out-of-scope points. The main JSON also retains author-only and graphical-only flags separately

## Side channels materially change the answer

The two side channels carry 2/17 of the stipulated mass flow, but receive only 6.14–6.46% of whole-sink heat in the nominally laminar primary cases. They have one fin face and no heated floor. Replacing the whole array with 17 copies of the central heated interior channel would overstate G by 6.02–6.37%. That shortcut would mask much of the disagreement and is excluded.

## Prespecified sensitivities

Material scenarios are representative k values, not identified alloys or confidence bounds. Sensitivities below use the primary FD model; material and area-mapping rows cover the four nominally laminar speeds.

| Scenario | Rth change relative to nominal 205 W/(m K) at the same speed |
|:---|---:|
| Aluminum k=167 W/(m K) | +0.323% to +0.476% |
| Aluminum k=237 W/(m K) | -0.282% to -0.192% |
| Infer flow using printed 1.86 mm area instead of arithmetic 1.849333 mm area | -0.275% to -0.216% |
| k_air ×0.95, at predeclared 10 m/s | +3.141% |
| k_air ×1.05, at predeclared 10 m/s | -2.885% |
| volumetric_heat_capacity ×0.95, at predeclared 10 m/s | +1.964% |
| volumetric_heat_capacity ×1.05, at predeclared 10 m/s | -1.820% |

The±5% air-property perturbations are illustrative one-at-a-time checks, not measured operating bounds. The source numerical dimensional properties imply Pr 0.73112206; the separately stated approximate 0.7 was not substituted.

## Mathematical acceptance, independently reviewed

- Accepted mesh:48 cells per full gap×144 vertically×1600 uniform axial BE steps; mirrored full-array topology
- Selected rectangular velocity Poisson mean error:0.112637% against the continuum series; unchanged gate 0.2%
- Maximum 48→64 spatial G change:0.050455%; maximum 800→1600 axial change:0.014877%
- Maximum integrated energy relative imbalance in refinement:2.2e-12
- Independent isothermal-fin plug continuum error:≤0.11953%; actual assembled fin-vs-analytic fin error:0.001271%
- A separate reviewer reproduced the coarse coupled system through a Schur complement and exact generalized eigenmodes, checked every-step interface/fin balances, compared all 16 fins against the mirrored half-array, and verified the vanishing-fin-conductivity limit with 15 heated floors and zero side heating
- All 17 mathematical gates passed before the independent reviewer released comparison; the rejected original mesh and serialization-failure log remain available
- Numerical refinement differences and Richardson indicators are convergence evidence, not statistical uncertainty bounds

## Limitations and next falsifiable step

The principal unresolved model-form questions are hydrodynamic entrance development and axial solid conduction. The source places the sink 10 mm after a plain-duct entrance; neither prescribed velocity profile reconstructs that flow. The plug field does not satisfy viscous wall no-slip and is only a deliberately different prescribed transport case. The source also does not establish the tested aluminum k or per-run fluid properties. Base spreading, root/contact resistance, duct-wall heat transfer and unequal channel mass flow remain outside this subcase. The observed discrepancy cannot be uniquely assigned to one omission.

A next defensible calculation would solve the simultaneously developing laminar momentum/energy field with axial fin conduction and independently verify it before revisiting these same data. Exact run replication additionally requires original nozzle-flow, electrical-power, loss-correction, inlet/base-temperature rows, material and tolerance records, and the 13 th-marker explanation. No aircraft-performance validation is claimed.

## Source and artifacts

- Source: [Pires-Fonseca and Carrasco-Altemani,2024](https://doi.org/10.17533/udea.redin.20230417), experimental geometry p 88, modeling/property assumptions pp 91–92, Figure 8 p 94; publisher-version PDF from [Zenodo 10975619](https://zenodo.org/records/10975619)
- `comparison.json`: complete frozen predictions, marker identities, separate uncertainty components, all material/property/mapping scenarios
- `applicability_audit.json`: reproducible conservative regime-screen arithmetic
- `temperature_fields_*.json`: normalized fluid and fin fields at 4 axial stations for two speeds and both model forms; these are not measured absolute temperatures
- `comparison.png` and `fin_temperature_profiles.png`: static figures rendered from saved numerical rows
- `manifest.json` and `artifact_audit.json`: source/input/code hashes, dependency versions, compact-artifact and consistency checks
- Solver SHA 256:`bdf9998a7f20cdd5d75fef2f5f0e49c9344ebc1e6f31a5ac955bff366d6c9d4c`
- Frozen numerical choices SHA 256:`db1c7ce73681dca1c327c43d29343db35d207fac1cf47488b86d8a3a424afb54`
- Figure readout SHA 256:`87bfcb8f105b07cd19fda9c2c9d1a9c2ea574eab655d00f5ee01a0f9d163a6c7`
