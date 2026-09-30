# Public experimental comparisons

Run `python -m aerolab serve` and open `/experiments`, linked from the physical-evidence journey. Two component studies sit in the same page. They preserve every recoverable measurement, failed numerical trial, declared model assumption and discrepancy. Neither is an aircraft-validation pass.

## 1. Isothermal rectangular duct, 32 recorded runs

The source is [P. Wibulswas's 1966 UCL thesis](https://discovery.ucl.ac.uk/1381757/1/388313.pdf), Appendix 7.6, printed pp 124–125. The 1 × 2 inch cross section has three heated lengths: 24 inches (12 rows), 13 inches (11 rows) and 7.5 inches (9 rows). Eight printed Reynolds entries remain missing. Printed temperature units are °F.

The finite-volume model solves the fully developed rectangular Poisson velocity and then thermally developing, constant-property, four-wall-isothermal energy transport. The reported Graetz number is a reduced flow/property condition. The observed target is the mixed outlet attenuation `(Tw−Tout)/(Tw−Tin)`, calculated from printed temperatures. This is a conditional dimensionless comparison, not a device-temperature prediction starting with independent raw flow measurements. Printed Nu is retained for provenance but is not used as a target, because it does not exactly reproduce from the printed Gz and temperature columns.

All 11 numerical gates passed on the refined 256 × 128 cross section before the experimental residuals were evaluated. A rejected grid remains preserved. Verification includes exact-series momentum and plug-flow limits, conservation and positivity, spatial and axial refinement, and a separately assembled continuum Galerkin reference. The observed maximum relative difference from that independent reference at the checked locations is 0.06361%, not an all-domain error bound or statistical uncertainty.

No coefficient or material adjustment was fitted to these 32 outcomes. Attenuation mean absolute differences are 2.6217, 4.6120 and 8.8197 percentage points by descending heated length, 5.0491 points overall. The maximum is 10.4378 points. In 31 of 32 cases, predicted attenuation is higher, meaning less predicted heat pickup. Shorter-channel discrepancies warrant inspection of entrance conditions and other model assumptions; residuals alone do not identify a unique cause.

The source does not provide a complete recoverable experimental uncertainty budget. Circuit accuracy, a ±0.05°F input perturbation and table rounding are not substitutes. Transition, mixed convection, variable properties and inlet development remain applicability concerns. The comparison reports `physical_validation_pass: null`.

## 2. Conjugate plate-fin heat sink, 12 recoverable graph markers

The source is [Pires-Fonseca and Carrasco-Altemani, 2024](https://doi.org/10.17533/udea.redin.20230417), publisher-version PDF available from [Zenodo record 10975619](https://zenodo.org/records/10975619). Figure 8 provides 12 recoverable black-square vector markers. The text states 13 experiments; no missing thirteenth marker is invented. The fitted plot curve is not treated as measurements. Figure 7's fin-efficiency-derived Nu is excluded as an independent target.

The comparison target is the approximate graph-read, heat-loss-corrected whole-sink resistance `(Tb−Tin)/Qconv`. It is not a raw temperature measurement. Author uncertainty (Rth 1.2%, speed 3.7–4.6%, Re 4.6–5.2%) and half-symbol graphical allowances (approximately ±0.257 m/s and ±0.0134 K/W) remain separate. Their coverage convention and per-run allocation are incomplete; the UI does not combine them into a confidence interval or automatic validation threshold.

The model solves 16 finite-conductivity fins coupled to 17 air channels. Fifteen interior channels have a heated floor and two fin faces; the two outer channels have an adiabatic floor and one fin face. Equal channel mass flow is a declared condition of this experimental subcase. Fin conduction is vertical, fluid conduction is cross-sectional, and thermal advection marches axially. The primary velocity is a fully developed rectangular Poisson solution. A prescribed plug velocity is a model-form sensitivity, not a no-slip developing-flow solution or a confidence bound.

All 17 numerical gates passed at 48 × 144 transverse cells and 1,600 axial steps before residual evaluation. The initial mesh failure was retained without loosening its threshold. Independent review checked generalized-eigen propagation, full-array versus mirrored symmetry, interface and fin balances, and analytic/vanishing-conductivity limits. Maximum spatial refinement change was 0.05046%; axial change was 0.01488%. These are convergence evidence, not physical uncertainty bounds.

The fixed Re 2300 applicability screen leaves three robustly in-scope points, one nominally in-scope but boundary-uncertain point and eight nominally out-of-scope points. The fourth point's nominal Re is approximately 2164; a conservative screening corner reaches approximately 2331. That corner is not a probabilistic combined uncertainty interval. Every point and both model forms remain available.

The primary model's Rth differences at the three robustly in-scope points are +0.507%, +2.966% and +5.132%. The boundary-uncertain point is +8.626%; the eight nominally out-of-scope differences range from +11.525% to +45.497%. Prescribed plug transport gives materially different results. Unknown material and per-run conditions, hydrodynamic entrance development, axial fin conduction, base/contact effects and heat-loss conventions prevent an uncertainty-backed validation conclusion.

The side-channel topology has a measurable effect: across the four nominally laminar points, the side channels carry 2/17 of stipulated mass flow but only 6.14–6.46% of heat. Replacing all 17 channels with heated interior-channel copies would overstate total conductance by 6.02–6.37%. That incorrect shortcut would hide much of the discrepancy and is shown only as a counterexample.

## Runtime and provenance

`GET /api/physics/experiment` and `GET /api/physics/fin-experiment` accept no tuning parameters. They use standard-library readers to verify pinned package manifests, original freezes, source transcription, complete artifact hashes and displayed arithmetic. Missing or stale evidence returns an explicit error. Each JSON response/export remains below 100,000 bytes.

The UI is an integrity-checked research replay. It does not run the optional NumPy/SciPy solver. The live analytic/FV subproblems remain on `/physics` with a separate execution label. Numerical verification, comparison to NASA CFD, and component experimental comparison are separate evidence levels.

Optional research reproduction uses the scripts and pinned research dependencies under `research/rectangular_duct/` and `research/plate_fin/`. The supported replay commands write to fresh ignored output directories; they do not overwrite pinned application evidence. A new reproduction is post-comparison evidence. Original chronology is preserved, not relabeled as a new blind experiment. Numerical outputs may reproduce exactly on the recorded environment while elapsed metadata hashes change. Promotion requires deliberate scientific review, a manifest-pin update, regression tests and fresh browser acceptance.

No source PDF or full-resolution NPZ is distributed. Source identities and optional local PDF audits remain available. New JSON artifacts are below 100 kB and binary artifacts below 250 kB. The application adds no scientific runtime dependency.

## Acceptance commands

```sh
python -m unittest discover -s tests -v
python -S research/rectangular_duct/audit_package.py
python -S research/plate_fin/audit_package.py
node --check web/experiments.js
node --check web/fin_experiment.js
python tests/ui_experiments_smoke.py
```

The final command requires an authorized Chromium environment. Browser screenshots, export identity, error/cancellation, navigation, mobile overflow and transformed font size belong to the exact published commit's CI result. This document does not substitute for those results.

Aircraft-level full-load credibility remains open. Neither package changes the X-57 nacelle's geometry, losses, flow coefficients, convection, contact properties or thermal margins.
