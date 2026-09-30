# Bounded axial-solid-conduction investigation

## Status and purpose

This is a **post-comparison model-form investigation**, not a blind holdout, a parameter fit, a new physical-validation pass, or an aircraft-transfer claim. The accepted plate-fin package remains immutable. Only this ignored folder is writable. The twelve original Figure8 measurements, their uncertainties, and source bytes are unchanged.

The question is narrow: with the already prescribed fluid velocity field and thermal boundaries held fixed, how much does axial conduction within the fins change whole-sink conductance? A small resolved change, an unresolved change below demonstrated numerical resolution, or a reproducible computational limit are all valid outcomes.

## Equations and ownership

Keep the existing fluid energy equation and transverse material/interface conductances:

`rho cp u(x,y) dT_f/dz = k_air (d²T_f/dx² + d²T_f/dy²)`

Replace only the slice-wise fin equation by:

`k_s t d²T_s/dy² + lambda_z k_s t d²T_s/dz² + q_left_to_fin_per_height + q_right_to_fin_per_height = 0`

Use `lambda_z=0` solely as the exact discrete recovery test, and `lambda_z=1` as the physical isotropic-fin case. Varying this multiplier must not change vertical conductivity, the half-thickness face resistance, root conductance, properties, or the imposed fluid velocity. It is not a fitted coefficient.

The baseline geometry is unchanged:16 fins;15 interior gaps1.849333333mm;2 side gaps1.85mm; fin height11.3mm, thickness0.86mm, length90mm. Interior floors and every fin root have isothermal base temperature. Side floors are outside the41.5mm sink base and remain adiabatic. Fin tips, duct top and sides are adiabatic. Each outer fin exchanges heat with both its side channel and its interior neighbor. Equal mass flow per channel remains the source reduction assumption. The mirrored half-array contains8 fins,8 full channels and half the central channel.

**New axial solid end condition:** zero axial conductive flux through fin faces at z=0 and z=L. Frontal/end-face convection remains excluded, consistently in both lambda cases. This is a declared boundary assumption, not recovered experimental evidence. The base stays isothermal along z; base axial conduction/spreading is not newly solved.

No hydrodynamic entrance development, fluid axial diffusion, turbulent transport, cross-flow or new wall/contact physics is added. FD velocity is primary. The pre-existing plug transport field may be used as a verification/model-form diagnostic, not as an actual no-slip flow solution.

## Conservative axial discretization

Retain backward-upwind fluid slabs at uniform dz. Solid temperatures are slab-center unknowns at z=(n+1/2)dz, with solid end faces at0 andL. The last fluid slab value supplies the first-order upwind outgoing face state. These conventions must not be relabeled as identical physical right-endpoint coordinates.

Let M be the original fluid axial capacity diagonal and K the accepted per-unit-length cross-section conductance matrix. For each slab:

`(K_ff + M/dz) theta_f[n] + K_fs theta_s[n] − (M/dz) theta_f[n−1] = 0`

`K_sf theta_f[n] + K_ss theta_s[n] + K_z theta_s = 0`

Here theta=(Tb−T)/(Tb−Tin), inlet fluid theta=1 and base theta=0. Between adjacent solid slabs at a given fin-height cell, the actual axial face conductance is `lambda_z k_s t dy/dz` [W/K]. After dividing the slab equation by dz, its graph coefficient is `lambda_z k_s t dy/dz²` [W/(m K)]. Every shared axial face has equal/opposite flux and the end graph has degree1, implementing zero external end flux.

Compute total base heat using exactly the same dz-weighted root/floor quadrature as the discrete equations. Compare it independently with outlet enthalpy gain. Internal axial solid flux must cancel in that sum.

## Solver and feasible resolution

A fully assembled48×144×1600 array would contain about95.8 million fluid/solid unknowns, so it is not the default. Eliminate the fluid by a forward march with a single factored cross-section fluid matrix per speed. Solve the remaining coupled solid system with matrix-free GMRES. Precondition with the directly factored vertical/axial solid operator including interface diagonal terms. Fluid history need not be stored: each operator application carries one cross-section and produces the solid residual for all slabs.

Initial resource/verification pilots:

- Tiny direct-reference mesh: full-gap4×height12,20 axial slabs, the actual mirrored16-fin array; also full-array symmetry checks
- Pilot:12×36×120,34,560 solid unknowns and3,672 fluid unknowns per marched slice
- Candidate sequences: axial60/120/240 at12×36; transverse12×36 →24×72, with a possible36×108 check if resource and convergence gates justify it
- Moderate24×72×240 case:138,240 solid unknowns,14,688 fluid unknowns per slice; about3.66 million equivalent global fluid/solid unknowns are never assembled
- The original48×144×1600 accepted grid is a reference identity, not an automatic computational requirement for this bounded effect study

Start with declared probe speeds4 and10m/s, primary ks205W/(m K), and the unchanged source air properties. No experimental resistance is used for selection. Other existing material/property cases and the20m/s diagnostic are deferred unless needed to falsify a demonstrated numerical limitation.

A lower-resolution **paired effect** may converge even when the absolute baseline is less accurate. Report both facts. Do not call coarse absolute Rth independently converged merely because the difference between lambda1 and lambda0 is stable.

## Resource limits and stopping conditions

- No installation, external compute, spending, credentials, publication or accepted-package edits
- Single numerical worker initially; existing NumPy/SciPy only
- GMRES rtol1e−10, atol1e−12; restart30, at most10 restart cycles; monitor true residual separately
- Per-case wall limit300s and at most350 matrix-vector fluid sweeps; pilot first, then estimate larger work from measured timings
- Target peak RSS below1GiB, hard study ceiling1.5GiB; estimate allocations before a larger run and record observed peak RSS after factorization/solve
- Initial investigation wall budget30min of computation; do not grow meshes indefinitely. Record an explicit inconclusive/resource-limit result if acceptance is not achieved
- JSON<100KB; binary<250KB. Save small labeled field/flux samples, convergence/iteration summaries and code/input hashes. Do not publish full fluid histories, full-resolution arrays, caches or logs

## Verification gates before residuals

1. **Exact zero-axial recovery:** same mesh, speed, properties and boundaries must reproduce the accepted slice solver at lambda0. Relative G discrepancy<1e−9; field max absolute difference<1e−8
2. **Independent tiny monolithic reference:** separately assemble the complete fluid/solid system with direct sparse solution. Compare Schur/matrix-free G and temperature fields within1e−8; do not share the new axial graph assembly routine between implementations
3. **Energy:** integrated root+floor heat versus outlet enthalpy relative error<1e−8. All internal axial face fluxes cancel; zero external solid end flux
4. **Symmetry:** full16-fin array versus mirrored half-array G relative difference<1e−8, with sampled paired fields agreeing within1e−8
5. **Maximum principle and algebraic residuals:** normalized temperature remains within[0,1] up to1e−8; independently evaluated componentwise backward error<1e−8
6. **Uniform-bath fin limit:** constant bath/Robin coefficient with insulated axial ends has a z-independent analytic adiabatic-tip fin solution. Verify heat and shape with spatial refinement; final relative heat error<0.2%
7. **Axially varying manufactured solution:** use a known cosine axial mode with Neumann end conditions and prescribed root/source forcing to exercise the new z operator independently, including its units and end stencil. Observe approximately second-order solid spatial convergence, with finest normalized error<0.2%
8. **Insulated and highly conducting limits:** no grounded surfaces gives zero heating and inlet temperature preservation; very large fin conductivity approaches the same isothermal-fin transport limit. Do not use changing ks as a substitute for lambda0
9. **Paired-effect refinement:** for `delta_G=G(lambda1)/G(lambda0)−1`, require successive axial and transverse changes≤0.0005 (0.05 percentage point), and show their values rather than treating them as confidence bounds. If the effect is comparable with these changes, label it unresolved at this numerical resolution. Any quantitative bound must be described as a demonstrated numerical envelope, not a proven physical bound

Only after these gates and independent review should the four originally nominally laminar marker speeds be considered. All twelve known measurements must remain visible and untouched, with the existing3 robust/1 boundary-uncertain/8 out-of-scope labels. Uncomputed or inapplicable axial predictions remain explicitly absent; no point is silently dropped. The first deliverable is the verified paired effect at the declared4 and10m/s probes, or a precise falsifiable numerical/resource limit.
