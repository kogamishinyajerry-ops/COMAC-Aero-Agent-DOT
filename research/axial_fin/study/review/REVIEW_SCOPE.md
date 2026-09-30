# Axial solid conduction: independent review scope

This is a post-comparison model-form investigation. The accepted plate-fin source package and twelve source markers are frozen. Numerical verification below cannot establish hydrodynamic entrance development, experimental or aircraft validity, or identify the physical cause of the observed source-model discrepancy.

## Required before expensive comparison

1. State the fluid equation, thin-fin equation, material values, equal-channel-flow assumption, physical boundaries and discrete axial coordinate interpretation. Only the new fin axial diffusion term may change in the paired axial/no-axial comparison. An independent axial-conductivity multiplier must allow that term to vanish without changing vertical conduction or face resistance.
2. Preserve 15 heated interior floors, two unheated side floors, and 16 fins. A mirrored half-array owns eight fins, one full side channel, seven full interior channels and one central half-channel. The factor of two applies consistently to heat, flow capacity and fin/root area. A narrow subcase must identify which ownership it omits.
3. Demonstrate exact same-grid zero-axial recovery of the accepted algebra, direct small-system agreement, full-versus-mirror symmetry, component residuals, temperature bounds, and root/floor-to-outlet conservation. Fin inlet/outlet axial fluxes are zero at actual end faces, and interface flux appears once with each sign.
4. Exercise the axial operator independently using a nonconstant analytic/manufactured axial solution or independently assembled graph, plus a constant-axial solution invariant to axial conductivity. Checks that only exercise the zero-axial limit cannot verify the new term.
5. Report separate axial and cross-sectional convergence of both total conductance and the paired effect. The paired effect may be much smaller than the error in total conductance. Evidence need only support the stated scenario, not an impossible all-domain error bound. Iterative tolerance sensitivity must be negligible against the claimed effect.
6. Give matrix dimensions, measured resource use and per-matrix-vector pilot time. Limit Krylov storage, iterations, runtime and output size before large cases. A computational limit is a valid outcome; failed convergence is not a physical zero.
7. Freeze the numerical choices and release statement before computing any new source residuals. Existing residuals have already been observed, so do not use blind/holdout terminology. Keep source measurements unchanged and report numerical uncertainty separately from physical applicability.

## Independent check strategy

Reuse the frozen cross-section only to obtain its conservative transverse graph; independently assemble the complete small fluid/solid axial system. Each slab has the graph multiplied by its length, upstream fluid mass coupling, and fin axial face conductance k_z*t*dy/dz. Missing exterior axial graph edges implement zero end flux. Solve directly and compare against the fin-only reduction, including recovered fields and energy. This bypasses its fluid elimination, iteration and preconditioner.

Separately assemble a synthetic isolated fin with a separable sinusoidal manufactured source. Its exact solution has zero root value, zero tip derivative and zero axial-end derivatives, with nonzero axial curvature. This checks signs, coefficients, end ownership and refinement without source measurements or fitted convection coefficients.

Review working files are confined to this directory. Full large arrays are never publication artifacts. JSON must remain below 100 KB and binary artifacts below 250 KB.
