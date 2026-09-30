# Pressure-driven conjugate-fin screening study

Research only. This is a **declared synthetic screening exercise**, prepared after the existing experimental work. It is not a blinded or unseen requirements test, and does not establish aircraft performance.

## Scope and evidence

The source geometry and thermal discretization are inherited from the verified `../fin-study/` model. The original public geometry source is Pires-Fonseca and Carrasco-Altemani, [Experimental and numerical investigation of flat plate fins and inline strip fins heat sinks](https://revistas.udea.edu.co/index.php/ingenieria/article/view/343222), DOI 10.17533/udea.redin.20230417. That citation identifies provenance, not a validation target for this new study. That original model, its equal-channel-flow experimental reduction, its experimental targets, and its freeze are not changed. This study has a new hydraulic boundary condition and new synthetic geometry/operating variants. Experimental agreement of the original model cannot be transferred to these variants.

Only full-height fins are varied: count 12/16/20 and thickness 0.60/0.86/1.20 mm. The base width is 41.5 mm; duct width 45.2 mm; length 90 mm; height 11.3 mm. Height is deliberately fixed because shorter fins require an explicit over-tip bypass model. Interior gap is `(41.5 mm - N*t)/(N-1)`. Each of the two 1.85 mm side channels has an adiabatic floor; the `N-1` interior floors are heated. The full `N`-fin thermal array preserves asymmetric coupling under a fault.

The declared synthetic target is 60 W from a 25°C inlet with an 85°C uniform-base ceiling and a 40 g **fin-only** aluminum mass budget. Load displays at 40/60/80 W use linear superposition. The limits do not come from an aircraft, customer, or certification requirement. Fin mass is `2700*N*t*H*L`, with no base, duct, motor, fan, or aircraft mass included.

## Pressure and conservation

Every active parallel channel sees an ideal common reservoir pressure difference of 25 Pa nominal or 15 Pa under the supply-pressure fault. The raw finite-volume rectangular Poisson solution satisfies `-laplacian(w)=1` and zero velocity at all walls. Velocity is `u=deltaP*w/(mu*L)` and volume flow is its area integral. The integrated pressure force equals the integrated discrete wall shear force. A separate exact rectangular-series mean checks hydraulic discretization error; the velocity is not rescaled to make that check pass.

A sealed interior branch is represented by **zero throughflow**, while its fluid still conducts across the channel between its floor and its two fins. The resulting stagnant fluid temperature is algebraic at each axial slice; no uniform inlet temperature or evolving axial transport is claimed for that sealed fluid. Obstruction conduction, recirculation, fluid axial conduction, and a developing inlet are absent. All open-channel inlets have the same temperature.

**Closing a branch under this ideal fixed-pressure supply changes flow fractions and reduces total flow. It does not increase the unblocked branches' absolute flow.** There is no inferred fan curve, common-feeder pressure coupling, or fixed-total-flow constraint. The blocked channel is channel 1, the first heated-floor interior branch from the left duct side. Nominal, reduced pressure, blockage alone, and their combination are all retained.

The fluid solves transverse diffusion and axial advection; each fin solves vertical conduction with conservative coupling to both adjacent channels. The base is isothermal, tips and external duct walls adiabatic. Integrated root-plus-floor heat is checked against outlet enthalpy rise at every axial step. The separately reported componentwise linear-equation residual is sampled at the first, middle, and final axial steps. The temperature equation has no empirical heat-transfer coefficient. A uniform velocity sensitivity uses the same pressure-derived mean flow but is only an alternate thermal-advection shape, not another solved momentum model. For that sensitivity, the momentum gate refers to the retained Poisson hydraulic conductance, not to the artificial plug velocity profile.

## Reading outputs honestly

- `G_W_K` is whole-array heat conductance from the fixed-temperature base to inlet air
- `Tb_at_60W_C = 25 + 60/G` is the required uniform-base temperature, not a local hot spot or an independently solved nonuniform base. Large failed-case temperatures are constant-property linear-model extrapolations, not credible high-temperature performance predictions
- `pressure_dissipation_W = deltaP*volume_flow` is passive frictional dissipation, not electrical fan power. Viscous dissipation is not added as a heat source in the decoupled thermal PDE; its size relative to the synthetic load is reported so thermal-model conservation is not confused with a complete installed-system energy balance
- `laminar_scope` means only that every active channel is below the declared Reynolds cutoff of 2300. It does not verify that the inlet velocity is fully developed
- The imposed pressure difference covers only fully developed straight-channel friction. Inlet, outlet, entrance, and installed-system losses are omitted
- Thermal entrance behavior is resolved by marching from uniform inlet temperature; hydrodynamic development is not resolved
- Material/property/profile variations are scenarios, not measured uncertainty or confidence intervals. Sensitivities are performed on the baseline only, so they do not establish robust ordering of all nine designs
- Fin vertical conduction is resolved; base spreading, contact resistance, axial solid conduction, temperature-dependent properties, radiation, and external losses are omitted
- Out-of-scope, failed-requirement, and dominated points remain visible. A conditional screen pass must not be read as validated aircraft feasibility

## Files and regeneration

`presweep_plan.json` records the equations, synthetic targets, complete finite study, and unchanged acceptance thresholds before new numerics. `pressure_fin.py` is the new model. `verify_tradeoff.py` checks analytical limits, network identities, conservation, and mesh convergence before `run_sweep.py` will execute the study. `check_inherited_operator.py` independently checks exact equality of the assembled thermal operator and base boundary vector at the inherited geometry; the hydraulic mass operator is deliberately different. `verification_runs/` and `runs/` preserve per-run evidence. Compact aggregate `design_results.json` and `sensitivity_results.json` are suitable for a separate engineering-demo interface.

Run from this directory with the existing Python/NumPy/SciPy installation:

```
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python verify_tradeoff.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python run_sweep.py
```

No software installation, external data upload, API spend, deployment, or original experimental-model mutation is part of this workflow. Every JSON file must stay below 100 kB and every binary below 250 kB.
