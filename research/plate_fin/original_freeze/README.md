# Conservative conjugate plate-fin research subcase

This folder contains a research-only, untuned calculation for the plate-fin heat sink of Pires-Fonseca and Carrasco-Altemani, DOI [10.17533/udea.redin.20230417](https://doi.org/10.17533/udea.redin.20230417). It is isolated from production code. No fitted heat-transfer correlation, fitted material property, Figure7 derived coefficient, or fitted experimental curve enters the solver.

The model and numerical gates were saved before evaluating target residuals. The Figure8 measurements were already available in the task's source audit; this is a frozen-before-comparison workflow, not a claim of a formally blinded experiment. The separately stated source uncertainty and conservative graphical half-symbol allowances remain distinct.

## Physical problem and ownership

- 16 fins, length90mm, height11.3mm, thickness0.86mm
- Sink base width41.5mm; duct width45.2mm
- 15 interior gaps: `(41.5 − 16×0.86)/15 = 1.849333333mm`
- 2 side gaps: `(45.2 − 41.5)/2 = 1.85mm`
- Interior floors are the heated sink base. Side-channel floors are outside the sink base, and are adiabatic duct surfaces in this subcase
- Each fin exchanges heat with both adjacent fluid domains. Outer fins see one side and one interior channel, so their temperatures are solved distinctly
- Base and fin roots are isothermal, with perfect root contact. Fin tips and duct top/sidewalls are adiabatic. There is no top bypass
- Equal mass flow per channel follows the source's reduction assumption. Reported speed is applied to the arithmetic interior area; side speed is adjusted by `g_interior/g_side`. A separate printed1.86mm-area interpretation is reported, with no hidden geometry adjustment
- A mirror half-array contains8 fins,8 complete channels, and half the central channel; totals are doubled. The central symmetry plane has zero normal velocity/temperature gradient. No artificial no-slip wall is inserted there

The experimental sink starts10mm after the duct entrance. That upstream flow and the hydrodynamic entrance into the fin array are **not solved**. Fully developed rectangular laminar velocity and plug velocity are two explicitly prescribed model forms. They are neither measured inlet fields nor confidence bounds on a developing solution; the true solution need not lie between them. The plug case is a prescribed slip-like advective field: it does not satisfy viscous no-slip at the duct/fin walls and is not a solved momentum field.

## Equations and conservative discretization

Let `theta = (Tb − T)/(Tb − Tin)`, so inlet fluid has theta1 and the base has theta0.

Fluid cross-section energy:

`rho cp u(x,y) dT/dz = k_air (d²T/dx² + d²T/dy²)`

Each fin, at each axial slice:

`k_s t d²T_s/dy² + q_left_to_fin_per_height + q_right_to_fin_per_height = 0`

There is no axial fluid diffusion, cross-flow, turbulent transport, axial solid conduction, transient storage, or base spreading in these equations. The fin temperature is represented by a through-thickness average with a half-thickness conduction resistance on each face.

The coupled finite-volume system is `M theta_f' + K_ff theta_f + K_fs theta_s = 0`, `K_sf theta_f + K_ss theta_s = 0`. The fluid axial-capacity entries `rho cp u dA` have units W/K. Conductance entries have units W/(m K), per axial length. Shared internal faces have equal and opposite flux contributions:

- fluid/fluid: `k_air * face_length / centre_distance`
- fluid/fin: `dy / [dx/(2 k_air) + t/(2 k_s)]`
- fin/fin vertically: `k_s t / dy`
- fin/root: `2 k_s t / dy`
- exposed interior floor: `2 k_air dx / dy`

Only the accepted **backward-Euler** axial path is used in frozen evidence. The optional BDF2 research code path has not passed this acceptance suite and is excluded from all reported results. Backward Euler permits a maximum-principle check and an exact discrete equality between integrated base heat and fluid enthalpy gain; it does not remove spatial/axial truncation error.

Whole-sink conductance is `G = sum[rho cp u dA (1 − theta_out)]`; `Rth = 1/G`. The calculation is linearized and normalized by `Tb−Tin`. No missing per-run temperature or heater-power value is invented.

## Independently chosen properties and scope

Primary aluminum conductivity:205W/(m K); declared material cases167 and237W/(m K). These representative values do not identify the tested aluminum alloy, and their range is not a material confidence interval.

The nominal air properties are the source numerical assumptions:rho1.204kg/m³,cp1007J/(kg K),k0.02514W/(m K),nu1.516×10⁻⁵m²/s. They imply Pr0.73112206. The source's separately printed approximate Pr0.7 is not substituted into the energy equation. Air k and volumetric heat capacity are independently perturbed ±5% at the predeclared10m/s probe; these are illustrative sensitivities, not measured environmental bounds. At prescribed velocity, changing viscosity would change the Reynolds label, not this normalized fully developed velocity shape or energy equation.

The source's numerical section uses laminar flow through Re2300. That threshold was fixed before target comparison. Reynolds numbers are recomputed from the arithmetic physical gap and `Dh = 3.178483066mm`; no correction is made to force the article's rough Re-range text to agree. All12 recovered Figure8 markers remain in the comparison, and out-of-scope rows are explicitly marked. The author uncertainty range and graphical velocity allowance also have separate regime flags. A supplemental `applicability_audit.json` conservatively screens their joint rectangular corner without combining them into a statistical interval: three points are robustly in scope, the fourth is nominally laminar but boundary-uncertain, and eight are outside the laminar scope.

## Verification and reproducibility

Run from any working directory with the existing NumPy/SciPy environment. These are research-only dependencies; nothing is installed. Typical total runtime is several minutes.

1. `python verify_and_freeze.py` runs the original candidate suite and intentionally reproduces the36×108 grid rejection: its Poisson mean error0.200064% exceeds the unchanged0.2% gate. `python refine_and_freeze.py` consumes the preserved rejected evidence, checks48×144 against64×192 and its own axial refinement, and writes the accepted freeze only if all gates pass
2. `python verify_independent_limits.py` checks exact plug/isothermal-fluid continuum solutions, the actual assembled fin block against the analytic fin equation, and the low-flow capacity limit
3. `python review/independent_review.py` independently checks topology, local interface balances, the Schur-complement/eigenmode axial solution and the vanishing-fin-conductivity limit
4. `python compare_frozen_model.py` checks the accepted source/input hashes and independent-review gate before opening the Figure8 readout, then calculates the fixed comparisons and scenarios
5. `python audit_applicability.py` writes the separate uncertainty components and conservative regime screen
6. `python render_results.py` optionally writes static scientific PNGs from saved results; the plotting cache is kept inside this folder

Use `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1` to make small sparse solves predictable. The comparison runs independent cases in three local processes; all use the same frozen discretization. `conjugate_fin.py --help` exposes individual probes. No experimental target is passed to a model constructor or solver.

Key artifacts: `precomparison_plan.json`, `verification.json`, `frozen_numerics.json`, `independent_limits.json`, `review/independent_review.json`, `comparison.json`, and normalized `temperature_fields_*.json`. Every JSON is intentionally below100KB. The manifest records code/input hashes and dependency versions. The first verification attempt completed calculations but failed while serializing a NumPy boolean; the failed log is retained. The subsequent correctly serialized run rejected the36×108 grid, and the refinement is separately documented. Native booleans fixed that reporting defect, and the complete suite was rerun without changing the solver or numerical tolerances.

## Interpretation and exact-replication gaps

See `RESULTS.md` for the actual untuned discrepancies and sensitivity sizes. Mathematical verification establishes the equations as discretized, not the experiment's boundary conditions. In particular, omitted hydrodynamic entrance development and axial fin conduction remain unresolved model-form errors.

The Figure8 target is approximate **loss-corrected** `Rth = (Tb − Tin)/qcv`, where `qcv` is electrical power minus estimated losses. It is not a raw thermocouple/run array. Figure7's h/Nu is derived using a fin-efficiency model and is not an independent target. Twelve filled-square symbols are recoverable although the text mentions13 runs; no extra point is invented.

Exact run replication still needs the original nozzle-flow/run rows, inlet/base temperatures and their property reference state, heater power and loss corrections, the three below-surface base readings, actual aluminum conductivity/alloy and geometry tolerances, and an explanation of the missing/overlapping13th marker. Resolving the physical model additionally needs the developing velocity field, actual channel flow partition, axial solid conduction, and wall/base contact and spreading information. Nothing here certifies an aircraft design.

The independent reviewer’s recorded decision is a historical checkpoint. Reproduction recomputes hash-linked mathematical evidence and reruns the independent review script for the unchanged solver and plan; changing either requires fresh scientific review rather than editing the saved gate. Runtime metadata can change artifact hashes on reproduction even when numerical values remain reproducible.
