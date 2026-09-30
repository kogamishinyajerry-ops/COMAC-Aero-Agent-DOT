# Final independent axial-fin review

Accepted for reporting the defined two-probe numerical result. Adding axial fin conduction decreases conductance by approximately 0.01685% at 4 m/s and 0.01305% at 10 m/s, under the same prescribed fully developed velocity, equal channel flow, k=205 W/(m K), isothermal base and insulated fin end faces. No experimental residual was recalculated and no physical or aircraft validation is established.

The new term, signs, units and end stencils agree with an independently assembled complete fluid/solid system. On eight small tests covering FD/plug flow, both probe speeds and zero/unit axial conductivity, maximum relative conductance difference is 1.12e-13 and maximum normalized field difference is 1.74e-12. Full/mirrored heat agrees to 1.2e-16; fin fields agree to 3e-16. The zero-axial limit retains vertical conductivity, root conduction and face resistance and recovers the accepted baseline.

The finite array still has fifteen heated interior floors, two adiabatic side floors and sixteen fins. Axial solid end faces lie at 0 and L; root/floor heat uses the same slab weights as fluid enthalpy. Conservation, component residuals, temperature bounds, analytic uniform-bath, nonconstant-axial manufactured, all-insulated and high-conductivity checks pass. The independent manufactured solution converges at second order.

At the final 48×144×480 grid, the last axial changes in the paired effect are 0.0001046 and 0.0000659 percentage points; last transverse changes are 0.0000274 and 0.0000387 points. The effects are therefore well resolved relative to these observed changes. A 100-fold attainable tolerance tightening changes the 10 m/s pilot delta by 3.9e-15. The attempted 1e-13 tolerance hit its iteration limit; a roundoff floor is only suspected. That failed attempt is retained and its tiny callback residual was not treated as convergence.

Absolute conductance changes more under refinement than the small paired effect. This limits absolute-G precision; it does not erase the separately demonstrated matched-grid difference. The study does not authorize mixing the 480-slab axial G with the original 1600-slab baseline or treating mesh differences as physical confidence bounds. Entrance development, real end-face convection and experimental property/flow uncertainties remain unresolved.

The largest executed solid system has 552,960 unknowns; observed peak memory is about 934 MiB and maximum case time 95.5 s. Fluid histories were eliminated rather than globally assembled. The 95.8-million unknown estimate is for the mirrored computational domain at the original axial resolution.

The exact scalar-run source is retained as `axial_fin_numerical_run.py`. The current solver changes only the full-array field notice; its numerical AST is unchanged. Moderate-grid field illustrations are explicitly labeled and reproduce their saved scalar G exactly. The final narrative accurately separates facts from the suspected solver roundoff explanation.

All 62 frozen source/display files checked independently remain unchanged, including the original twelve measurements. Compact artifact identities and sizes passed review. The machine-readable acceptance and pinned scientific identities are in `final_review_gate.json`. This final review supersedes the pending statuses in the earlier plan and implementation review notes.
