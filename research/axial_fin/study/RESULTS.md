# Axial fin conduction: bounded model-form result

The isolated axial-solid-conduction extension produces a small conductance **decrease** at both declared probe speeds. This is conditional on the unchanged prescribed fully developed velocity, equal channel flow and insulated axial fin ends. It is not a new experimental-validation or aircraft-transfer claim.

| Speed | G without axial conduction, same mesh | G with axial conduction | Change in G | Change in Rth |
|---:|---:|---:|---:|---:|
| 4m/s | 1.078744923W/K | 1.078563175W/K | -0.016848% | +0.016851% |
| 10m/s | 1.592280670W/K | 1.592072892W/K | -0.013049% | +0.013051% |

## What was actually resolved

| Speed | Last axial change in paired effect | Last transverse change in paired effect | Effect / axial change | Effect / transverse change |
|---:|---:|---:|---:|---:|
| 4m/s | 0.00010463percentage points | 0.00002737percentage points | 161× | 616× |
| 10m/s | 0.00006589percentage points | 0.00003867percentage points | 198× | 337× |

The loose predeclared 0.05-percentage-point outer gate alone would not resolve an effect this small. The actual final mesh changes are much smaller: the effect exceeds them by roughly 161–198× axially and 337–616× transversely. Default-versus-tighter solver tolerance changes the paired effect by approximately 1e−15 at the checked pilot, far below these mesh differences. These are numerical convergence observations, not confidence intervals or certified physical bounds.

**Absolute conductance is less accurate than the paired difference.** The 36→48 transverse change in baseline G is about 0.0255% at 4m/s and 0.0562% at 10m/s; the 240→480 axial change is about 0.0496% and 0.0302%, respectively. Each exceeds the small axial-conduction effect. The paired calculation controls both cases on the same grid; it does not justify mixing a 480-slab axial result with the original 1600-slab baseline.

## Physics held fixed

Only the axial term in the fin equation was added: `k_s t (d²T_s/dy² + lambda_z d²T_s/dz²)` with lambda_z 0 for recovery and 1 for the isotropic case. Vertical conductivity, finite fin thickness/interface resistance, isothermal roots, adiabatic tips,15 heated interior floors,2 adiabatic side floors and equal per-channel mass flow remain unchanged. New axial fin end faces are insulated. No frontal/end-face convection or hydrodynamic entrance development is added.

The solid unknowns are slab centers; the outgoing fluid value is the first-order upwind face state. Both cases use the same dz-weighted energy balance. Adding a conductive path to this convection-coupled system was not assumed to improve heat removal; the observed sign is verified against the independent direct system.

## Verification and practical feasibility

- All 15 mathematical checks pass, including exact zero-axial recovery, independent monolithic reference, full/half symmetry, energy, maximum principle, analytic uniform-bath fin, a nonconstant axial manufactured solution, insulated and high-k limits
- Independent direct comparisons give relative conductance differences no larger than approximately 1.1e−13 and all-field differences below 1.8e−12 on the checked tiny grids
- Maximum energy imbalance across the refinement cases:1.76e-12relative
- Largest executed grid:48×144×480,552,960 global solid unknowns, with fluid eliminated by a forward march; peak process RSS 934.0MiB and slowest case 95.5s
- The 95.8-million equivalent unknown estimate for the original 48×144×1600 discretization refers to the **mirrored computational half-domain** representing the complete array. An explicitly unmirrored assembly would be about 191.7million. Neither global matrix was assembled
- A deliberately tighter rtol 1e−13 stress test hit its iteration limit despite a tiny preconditioned callback residual; a roundoff floor was suspected, not established. The failed attempt is retained by the reviewer. The accepted default 1e−10 and attainable 1e−12 results agree; a tiny preconditioned callback residual was not treated as proof of convergence

## Scope and provenance

No experimental residuals were recomputed, no known marker was selected or discarded, and no physical parameter was retuned. The twelve original measurements and the published accepted package remain byte-for-byte unchanged. This closes one defined omission at two declared synthetic probe speeds. It does not resolve inlet development, actual material/property uncertainty, end-face heat transfer or aircraft transfer.

The exact source used for the full numerical run is `axial_fin_numerical_run.py`. The current `axial_fin.py` corrects only the full-array sample notice. `label_patch_verification.json` proves AST identity after replacing that one notice value, and independently checks the full/half labels. No equations, numerical operations, grids or tolerances changed. This avoids pretending that a display-only correction required or constituted another physical experiment.

Small field files `fields_V04.json` and `fields_V10.json` use the explicitly labeled 24×72×240 grid. They show baseline/axial temperature differences and signed axial solid heat flow, and reproduce their saved scalar conductance exactly. They are illustrative samples, not full-resolution fields and not the final scalar refinement mesh.

Read `PLAN.md`, `mathematical_verification.json`, `refinement.json`, `review/`, `study_summary.json` and `accepted_package_immutability.json` for the full definitions and audit trail. All authored outputs stay in this ignored study folder.
