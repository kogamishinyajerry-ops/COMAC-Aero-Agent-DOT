# Independent implementation review

Initial reviewed solver SHA256: `29174c5a2a3e0549541ac498e8cfc26387e3f54d94b5ddca5b12b76e949e5c4f`.

The fluid elimination and reduced solid operator agree with a separately assembled complete fluid/solid system. Eight cases span FD and plug transport, 4 and 10 m/s, and axial multipliers zero and one at 4×12×20. Maximum relative conductance difference is 1.11e-13 and maximum absolute normalized field difference is 1.74e-12. The full sixteen-fin case agrees with its mirrored half-array to 1.2e-16 in conductance and 3.0e-16 in fin temperature. These tests independently exercise the added axial coefficients, signs, insulated-end graph, fluid forcing and recovery.

The complete conservative equation uses transverse K*dz, fluid upstream mass terms and fin axial face conductance lambda*k_s*t*dy/dz. The solver's per-length reduced graph uses the equivalent coefficient divided by dz. Its final assessment reconstructs each fluid slab and uses the same root/floor quadrature. Interior axial flux cancels globally. Zero axial multiplier preserves finite vertical fin conduction and face resistance.

At 12×36×120 and 10 m/s, tightening relative GMRES tolerance from 1e-10 through 1e-11 to 1e-12 changes the paired conductance delta by only 3.89e-15. The last true Schur residual is 1.15e-13. An attempted 1e-13 tolerance failed the iteration limit and is explicitly retained; its small preconditioned callback was not accepted as convergence. This failure does not affect the independently observed accuracy at attainable tolerances.

The initial 62-file accepted source/display identity snapshot is unchanged. Numerical evidence is in `reduced_solver_comparison.json`; the independent complete-system check does not read experimental targets.

Two minor review notes were sent to the author: a full-array field sample needs a right-side-channel label rather than a central-half-channel label; and the all-insulated zero-heating test should use absolute heat error rather than divide roundoff by an almost-zero physical heat rate. Neither changes the equations.

Still pending: final code identity, analytic/limiting evidence, axial and transverse paired-effect convergence, pilot resource evidence and the final scientific scope statement. No source-residual release is granted by this intermediate note.
