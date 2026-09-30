# Finite-width rectangular Graetz study (isolated research)

This directory contains a research-only conservative finite-volume solver and an untuned, conditional comparison with the 32 isothermal-wall runs in Appendix 7.6 of P. Wibulswas's 1966 UCL thesis. It is separate from the runtime infinite-parallel-plate solver, the aircraft reduced-order model, and all committed application files. NumPy/SciPy are pre-existing research dependencies; no application dependency was added.

The experimental comparison is **not a physical-validation pass**. The source does not establish an uncertainty-backed, pure-forced-laminar subset, and its reported flow/property reduction is not completely recoverable. Buoyancy, variable properties and transition are plausible applicability problems, not fitted explanations of a residual. No actual-aircraft temperature, heat-transfer coefficient or validity conclusion follows from this study.

## Completed result

The accepted 256×128-cell calculation passes all 11 preregistered mathematical gates. Exact-series aspect-2 mean-flow error is 0.01544%; mesh doubling changes attenuation by at most 0.01930%, axial step halving by at most 0.04467%, and observed spatial convergence order is at least 1.992. Production normalized energy closure is 9.9e-14. An independent, numerically converged continuum thermal calculation differs by at most 0.06361% relative, or 3.646e-5 absolute attenuation. Refinement differences are not total uncertainty bounds.

All 32 experimental rows were then compared without tuning or filtering:

| Source heated length | Runs | Mean absolute attenuation error | Residual range, prediction minus observation |
|---|---:|---:|---:|
| 24 in, primary group | 12 | 2.62 percentage points | −0.46 to +7.03 points |
| 13 in | 11 | 4.61 percentage points | +1.02 to +8.64 points |
| 7.5 in | 9 | 8.82 percentage points | +5.91 to +10.44 points |

Overall mean absolute attenuation error is 5.05 percentage points; the largest error is 10.44 points. Larger predicted attenuation means less heat pickup than reported in the source. The retained discrepancy is far larger than the observed numerical-reference differences, but the incomplete measurement uncertainty and model applicability prevent a quantitative validation pass or a unique causal diagnosis.

The machine-readable comparison explicitly stores physical_validation_pass=null. Source Re values remain null in eight originally blank cells. All JSON files are below 100kB. Plot pixels were inspected, and the 23-file artifact hash/consistency audit passed. `reproduce.sh` is the one-command reproduction entry point; it takes roughly ten minutes for the broad refined FV verification on this executor, plus plotting and comparison.

## Formulation and conventions

Let the rectangular short side be H and long side W=2H. The full cross-section uses coordinates X=x/H in [0,2], Y=y/H in [0,1]. Dh/H=2WH/((W+H)H)=4/3.

1. Solve −(∂²w/∂X²+∂²w/∂Y²)=1, with w=0 at all four walls. Set v=w/area_mean(w); hence area_mean(v)=1.
2. Define theta=(Tw−T)/(Tw−Tin), tau=alpha*z/(Umean*H²). Solve v ∂theta/∂tau=∇²theta. The thermal inlet is theta=1; all four walls are theta=0.
3. The mixed-mean attenuation is theta_bulk=sum(v_i theta_i)/sum(v_i), **not** the unweighted area mean.
4. Gz_Dh=Re_Dh Pr Dh/L, so tau_out=(Dh/H)²/Gz_Dh=16/(9Gz_Dh). Reported source Gz is a reduced input. Tin and Tw condition the normalization. This is not an independent prediction of raw device temperatures from a measured mass flow.

Uniform cell-centered square control volumes cover the full section. For every wall-adjacent face, the prescribed value is a half-cell distance from the cell center. The wall conductance is consequently 2/h², versus 1/h² for an interior neighbor. A one-dimensional edge diagonal is 3/h², and corner cells receive both wall contributions. No cell center is silently treated as the wall.

Let K be the positive Dirichlet negative-Laplacian matrix and M=diag(v). Every axial step solves (M+dt K) theta_new=M theta_old with SciPy sparse LU. This is backward Euler: conservative, first-order in axial time and unconditionally positivity preserving in exact arithmetic because its system matrix is an M-matrix. Spatial consistency is second order. The initially uniform inlet has an instantaneous wall-temperature jump; it is not claimed smooth at the inlet corners.

The model is steady, incompressible, hydrodynamically developed and constant-property. It omits buoyancy/secondary flow, hydrodynamic entrance effects, turbulence/transition, axial fluid or solid conduction, variable properties, radiation and viscous heating. Cross-sectional temperature fields are dimensionless ideal-fluid fields, not reconstructed aircraft fields.

## Independent mathematical references

Separation of variables for −∇²w=1 gives

mean(w) = (1/12) [1 − 192/(pi^5 a) sum over positive odd n of tanh(n*pi*a/2)/n^5],

where a=W/H. The corresponding Darcy friction product is f_D Re_Dh = 2(Dh/H)²/mean(w); the Fanning product is one quarter of this. The reference is evaluated independently of FV assembly using 10,000 odd terms. It checks aspects 1, 2 and 4. These are an exact analytical-series reference, not an empirical duct correlation.

For a uniform plug velocity, the heat equation separates into independent slabs. Its exact area/mixed attenuation is

(64/pi^4) [sum over odd m exp(−pi² tau m²)/m²] [sum over odd n exp(−pi² tau n²/a²)/n²].

This independent thermal reference checks diffusion sign, aspect scaling, all-four-wall Dirichlet treatment and inlet normalization; it does not prove the Poiseuille weighted-advection operator by itself. The laminar thermal calculation separately receives 4-level spatial convergence and axial refinement tests.

## Conservation and limits

- With a unidirectional z-invariant velocity, continuity is satisfied identically; the normalized area mass flux is checked against one. This is a steady developed-flow mass check, not a compressible mass solver.
- Momentum forcing equals integrated viscous wall force, using the assembled wall conductances.
- For every axial step, the mixed-energy decrease is compared with dt times the sum of all four wall fluxes, and wall energy is accumulated independently over the full duct. Interior-face fluxes cancel pairwise.
- Every marched cell is checked for 0≤theta≤1 and nonincreasing theta. Velocity positivity, a uniform thermal inlet, and a long-duct wall-temperature limit are checked.
- Sparse linear residuals are sampled at the first and last step of every constant-step interval. They are explicitly labeled sampled residuals; the energy and maximum-principle checks inspect every step.

## Numerical selection and evidence ordering

`numerical_plan.json` was written before any experimental residual was computed. The initial 128×64 candidate failed two mathematical gates: mean-flow series error and the broad long-duct axial-refinement tolerance. Its unmodified code and numerical evidence are preserved in `initial_solver_rejected.py` and `initial_verification_rejected.json`.

`refinement_plan.json` records the response to these mathematical failures. It uses 256×128 cells, 512 steps in each initial doubling interval, and an axial time-step cap of 0.0000625. Refinement uses 512×256 cells and twice as many time steps. The acceptance thresholds were not relaxed, and experimental residuals were never a selection input. The actual accepted results and code/input hashes are in `verification.json` and `frozen_response.json`. Published measurements had already been inspected, so this is not a blinded holdout; no model-to-measurement discrepancy was computed until the mathematical freeze.

A second script checks interpolation at three preselected mathematical axial times before allowing measurement comparison. It reports source groups separately, including the complete 24-inch series as the primary group and 13- and 7.5-inch groups as additional conditions. No rows are dropped on the basis of agreement. Blank source Re cells remain null.

## Experimental provenance and uncertainty

Primary source: [UCL thesis PDF](https://discovery.ucl.ac.uk/1381757/1/388313.pdf), printed pp124–125 (Appendix 7.6). All 32 rows were visually audited and the machine-readable transcription separately checked against that audit. Original PDF SHA-256 is `8fac58915fcb924f0fb0095f01e15c85de9af85b1f8a39405e71837e889c03ba`.

The target is theta_out from the printed Tin/Tout/Tw, in Fahrenheit; the ratio is invariant under conversion to Celsius or Kelvin. Printed Nu is retained only for traceability, since −Gz*ln(theta_out)/4 does not exactly reproduce that column. No Nu-based correction, fitted conductivity, heat-transfer multiplier, flow adjustment or temperature offset is used.

The source's approximately 0.05°F circuit precision is not a complete uncertainty budget. Any independent ±0.05°F temperature perturbation in the comparison is an explicitly illustrative sensitivity assumption, not a confidence interval, propagated experimental uncertainty or acceptance band. The approximately 14% worst stated velocity-measurement accuracy is also not a complete propagated error budget. The source's explicit flow-inversion percentages concern its separate constant-heat-input apparatus and are not transferred to these isothermal runs.

## Reproduction

Run from this directory with the already installed research packages:

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python rectangular_graetz.py verify
python independent_galerkin_reference.py > independent_galerkin_reference.jsonl
python compare_independent_reference.py
python rectangular_graetz.py curve
python compare_experiment.py
python render_plots.py
python audit_artifacts.py
```

The comparison deliberately refuses to run without a mathematically accepted frozen response, verifies that solver bytes still match, and verifies the original source PDF hash. `experimental_source.json` is the exact comparison input. Every JSON is constrained to less than 100 kB. Fields use compressed NPZ, and plots are PNG; no huge arrays are embedded into reports.

Expected artifacts:

- `verification.json`: numerical gates, exact-reference errors, mesh/time tables and conservation checks
- `frozen_response.json`: dimensionless response with exact solver/plan/verification hashes
- `cross_section_fields.npz` / `.png`: velocity and selected dimensionless temperature fields
- `experimental_comparison.json`: all 32 unfiltered rows, grouped residuals, conditioning and limitations
- `historical_comparison.png`: source groups and ideal-model residuals
- `interpolation_verification.json`: precomparison mathematical curve check

## Review notes and supported research scope

Independent review found agreement of the aspect-2 velocity field with a separately implemented continuum sine/cosh series: at 256×128 cells, maximum pointwise error divided by the exact peak is approximately 6.68e-5 and relative L2 error is approximately 9.52e-5. Separate dense generalized-eigen propagation of the ny=16 semidiscrete system reproduced marched backward-Euler endpoints within 3e-14. These are independent review results, separate from this script's automated gates.

The axial gate controls the **difference on step halving**, not the total time error. With first-order backward Euler, production error can be roughly twice that difference; it must not be presented as a total numerical uncertainty bound. The spatial difference also is not a statistical uncertainty.

The fixed research CLI uses only transverse grids with at least 16 cells per short side. The low-level one-cell Dirichlet helper is unsupported (its repeated-index edge would give3/h² instead of4/h² when n=1). Add an explicit minimum-size guard or correct that edge and reverify before any generalized/runtime API promotion. It does not affect any calculation reported here.

The independently numerically converged continuum thermal reference is preserved in `independent_galerkin_reference.py` and compared in `independent_continuum_comparison.json`. It uses exact axial exponential evolution of sine-Galerkin modes with analytical Poiseuille velocity. At order160 quadrature, 32→40 odd modes per direction change attenuation by about1.11e-9 relative; a separate review quadrature120→160 check changed it by at most1.4e-14. The converged fundamental decay eigenvalue is7.6326551437, giving fully developed Nu_Dh=3.3922911750. The largest production FV difference over tau0.002–0.512 is0.063606%, distinct from step-halving differences. The finite thermal basis is a numerical continuum reference, not an exact analytical thermal solution.

No file in this directory is a production runtime change, deployment, publication or permission to calibrate the aircraft model.
