# Independent plan review

Decision: proceed with the bounded verification/resource pilot. New experimental-residual calculations remain gated on review of the implementation and numerical evidence.

Reviewed plan: `../PLAN.md`, SHA256 `672540c89ce15d0302f7edc81624d654429004eb43ba6fc257d77b404bf35723`.

The plan changes only fin axial conduction. Its separate multiplier allows zero-axial recovery without reducing vertical fin conductivity, interface half-thickness resistance, or root conduction. The insulated fin-end conditions belong at axial control-volume faces 0 and L, with slab-center fin values. Backward-upwind fluid values carry the numerical outgoing face state. These are compatible conservative first-order fluid and centered solid approximations when the stated equal-dz heat quadrature is used.

The finite array ownership and mirror factor are preserved. The stated 4 and 10 m/s FD cases, ks=205 W/(m K), and unchanged air properties are a clear, limited physical subcase. Insulated fin ends isolate the added axial term. They do not reconstruct experimental frontal/end-face convection. The study still prescribes velocity and omits hydrodynamic entrance development.

The plan's resource and residual limits are appropriate for pilot admission. A finite paired-difference convergence tolerance is evidence at tested parameters, not a physical or all-domain error bound. If the effect is comparable with numerical refinement changes, report it as unresolved. Absolute conductance accuracy and accuracy of the difference must remain separate.

Independent reference self-checks are saved in `independent_reference_self_checks.json`. The small complete fluid/solid matrix independently assembled in `independent_axial_review.py` closes energy below 8.2e-16 and agrees between full and mirrored arrays below 2.3e-16. The manufactured nonconstant-axial fin solution has observed order 2.00022 on the final pair. These verify the reference, not the not-yet-reviewed implementation.

Pending: reduced-solver/direct-reference field comparison; zero-axial recovered fields; actual component residual and conservation checks; limits; tolerance sensitivity; measured resource pilot; axial/transverse paired-effect refinement; frozen package identity check; and final scope statement.
