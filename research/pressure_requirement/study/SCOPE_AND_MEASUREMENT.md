# Conditional pressure requirement: meaning and falsification

This is inverse design of one declared boundary variable in a synthetic, constant-property component model. It is not fitting, physical validation, an installed cooler requirement, an aircraft operating limit, or an engineering safety margin. The two existing geometries and all existing accepted packages stay unchanged.

## What the pressure means

For each branch, the synthetic available mechanical pressure-loss budget is

    deltaP = (mu L / wmean_i) U_i + 0.5 rho K U_i^2.

The first term is straight-channel Poisson friction. The second is one uniform, nonnegative, illustrative aggregate end-loss coefficient. The same total deltaP is imposed across every active parallel branch. Its terms are counted once; an additional inlet/exit allowance must not be silently added to or subtracted from a result already using K. This pressure variable is not a NASA station static pressure, a total-pressure recovery measurement, a fan curve, or electrical fan power.

The nominal available budget is P. The synthetic combined fault supplies 0.6 P and seals branch 1, the first interior channel from the left. Ideal reservoirs keep all other branch absolute flows fixed when a branch is sealed at a fixed pressure; this does not represent redistribution under a real fan/feeder curve. The sealed fluid keeps transverse thermal conduction and has exactly zero axial enthalpy transport. Interior floors remain heated; the two real side-channel floors remain adiabatic.

The inverse condition is G(0.6 P, sealed branch 1) = 60 W / (85−25) K = 1 W/K. The output temperature is a required uniform base temperature. It is not a local hot spot. Fin-only masses stay 37.783584 g (0.86 mm) and 26.360640 g (0.60 mm), below the unchanged 40 g fin-only budget. Base, duct, fan, fittings and power-system mass are excluded.

K = 0, 1 and 2 are separate illustrative synthetic model forms. They do not form a probability distribution, measured uncertainty interval, confidence band, or hardware-calibrated range. A K=0 root is the accepted model with its pressure boundary varied. K>0 reduces branch speed at fixed pressure while retaining the normalized fully developed Poisson profile; it does not resolve entry development, separation or actual end geometry.

A root gives exactly the declared 60 W at an 85°C base. The 40% pressure reduction is an imposed scenario, not 40% spare cooling capability. The sign bracket separates numerical failure and numerical success for the selected discrete model. Neither its upper endpoint nor the largest root among three meshes is a guaranteed engineering margin. Spatial and axial root differences are discretization indicators, not physical uncertainty bounds.

Pressure-drop dissipation is deltaP times total volume flow, with friction and end-loss components reported separately. It has units of watts and is passive mechanical dissipation. Its ratio to 60 W quantifies heating omitted from the thermal equation; neither this quantity nor its reciprocal supplies motor efficiency or electrical fan demand.

## What would test or invalidate the result

1. Measure device and branch pressure–flow curves using pressure stations whose kinetic-energy and reservoir assumptions match the declared mechanical budget. Check common branch pressure, flow partition, actual entrance/exit losses, flow development and the laminar applicability range. The illustrative K values cannot substitute for these measurements.
2. Establish the actual supply/fan operating points at the nominal and combined-flow rates, including feeder/plenum losses. Verify whether a 40% loss in available pressure is a relevant fault and whether that boundary can be maintained with a sealed branch. A finite fan curve can change every open branch flow after closure.
3. Test the actual sealed branch for leakage, recirculation, altered solid contact and thermal conduction. The numerical sealed entrance is an ideal limiting condition, not a resolved physical obstruction.
4. Measure thermal rejection using inlet/outlet enthalpy and heat input while accounting for parasitic loss. Compare at a known base temperature and matched flow. Check fin conduction, base spreading, contact resistance, axial solid conduction, nonuniform heat input and actual peak temperatures; the present uniform-base model cannot certify a hot-spot limit.
5. Check temperature-dependent properties and the omission of viscous/end-loss heating. The dissipation-to-60 W ratio is only an accounting diagnostic, not an experimental error bound.
6. Confirm total cooler/system mass, mechanical packaging, manufacturing tolerances, and the relevant operating environment before selecting hardware. No aircraft transfer follows from passing these synthetic equations.

## Model monotonicity

For each fixed K≥0, branch U increases with pressure. In the discrete thermal equations, eliminate the fixed massless fin and sealed-fluid states to obtain a grounded M-matrix K_eff with K_eff 1≥0. Its backward-Euler resolvent is nonnegative and temperature deficits decrease downstream from a uniform inlet deficit of one. For diagonal advection matrices M2≥M1, the difference w_n = theta2_n−theta1_n satisfies

    (K_eff + M2/dz) w_n = (M2/dz) w_(n−1)
                            + ((M2−M1)/dz)(theta1_(n−1)−theta1_n) ≥ 0.

Massless-state reconstruction is nonnegative. Integrated base heat has nonnegative boundary weights, so G cannot decrease when branch velocities increase. This supports a least qualifying pressure in the declared discrete model when a root is bracketed. The saved fine-bracket slopes also check local monotonicity numerically. This argument does not validate the omitted physical effects or establish a hardware-safe margin.
