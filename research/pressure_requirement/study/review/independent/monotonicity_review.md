# Monotonicity of the declared finite-volume model

This argument applies to the accepted full-array transverse diffusion and finite-fin operator, the unchanged backward-Euler axial march, fixed geometry, fixed properties, fixed sealed set, and nonnegative prescribed end-loss coefficient. It is not evidence that real installed-cooler performance is monotone in a fan setting.

The assembled thermal matrix `A` is symmetric, grounded, and connected. Its diagonal entries are positive and off-diagonal entries nonpositive. `A*1=b>=0`, where `b` consists only of nonnegative base-floor and fin-root weights. Fin and sealed-fluid cells remain in `A`; they carry zero axial mass. For any nonnegative diagonal mass matrix `M`, `A+M/dz` is a nonsingular M-matrix, and its inverse is entrywise nonnegative.

Write the base-to-fluid temperature deficit as `theta`, initialized to one. The march is `(A+M/dz) theta_n = (M/dz) theta_(n-1)`. Initial values in massless cells are annihilated by `M` and impose no advected sealed-fluid inlet condition. Since `(A+M/dz)*1 >= (M/dz)*1`, the first deficit is at most one and nonnegative. Applying the nonnegative propagation matrix repeatedly gives `0 <= theta_n <= theta_(n-1) <= 1`.

Let two flow states have diagonal matrices `M2>=M1`, including the same zero entries for fins and sealed fluid. Subtraction gives

`(A+M2/dz) (theta2_n-theta1_n) = (M2/dz)(theta2_(n-1)-theta1_(n-1)) + ((M2-M1)/dz)(theta1_(n-1)-theta1_n)`.

Every term on the right is nonnegative by induction, so `theta2_n >= theta1_n`. Integrated normalized base heat is `G = dz * sum_n(b^T theta_n)` and therefore increases with mass capacity. Conservation identifies this with the reported outlet enthalpy. For strictly increasing velocity in active cells of this connected grounded array, the first-step difference and resulting boundary heat difference are strictly positive. Retaining sealed-fluid diffusion and full-array fin coupling is essential to this argument and to the intended model.

The hydraulic derivative is `dU/dP=1/(a+rho*K*U)>0` for positive resistance, positive pressure and `K>=0`. With normalized branch profiles fixed, every active diagonal mass entry rises with pressure. Thus `G(0.6P, sealed branch 1)` is continuous and strictly increasing for the declared model on its admissible interval. A verified negative/positive heat bracket has exactly one root; under these assumptions that root is the model's minimum nominal available pressure-loss budget meeting 60 W. All main and refined meshes require their own roots and brackets. Increasing K at fixed pressure reduces each velocity, and hence G, so a required root rises with K when roots remain in scope.

The searched `P` is a synthetic available mechanical pressure-loss budget across the modeled path. The straight-friction and chosen lumped end-loss terms sum to P and are counted once. This is not identified with a NASA station-averaged static or total pressure, nor with an actual fan's electrical requirement. `P*sum(Qv)` is mechanical hydraulic dissipation. The thermal PDE omits its conversion to heat; the reported fraction of the synthetic 60 W load is a model omission diagnostic.

A root meets the uniform-base target with zero mathematical thermal headroom. Monotonicity establishes a conditional boundary requirement, not a safety margin, model discrepancy bound, installed cooling requirement, or physical validation. The original 25 Pa nominal / 15 Pa combined-fault screen and all original failures remain unchanged.
