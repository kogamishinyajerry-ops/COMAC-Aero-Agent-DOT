# Independent scientific review

Read-only numerical review covered the pre-run plan, solver setup, actual field extraction, boundary flux accounting, later diagnostic plans and final measured values. The review did not tune model coefficients or modify experimental data.

## Corrections incorporated before or during verification

- Kept the cold-inlet/hot-wall corner singularity explicit; excluded converged physical total-wall-heat claims
- Lowered the analytical sentinel's prescribed speed before any solver run so axial diffusion materially affects the answer
- Used normalized scalar amplitude for thermal error, not absolute 300 K temperature
- Preserved pressure-corrected phi for the heat solve and used its actual upwind face values in energy accounting
- Normalized energy imbalance by the fixed 0.28944 W reference
- Reported both nominal 3 m/s and grid-quadrature-adjusted analytical momentum references
- Added 20-iteration stationarity and a same-spacing downstream-extension diagnostic
- Kept the original pressure-refinement failure and labeled later 1.25x evidence separately
- Added full-resolution source-artifact hashes and explicit supplemental gates

## Final independently checked results

- Original 2x pressure-gradient refinement change: 1.120839438%, exceeding 1%
- Additional 1.25x raw pressure change: 0.135525915%
- Conditional second-order equivalent-doubling diagnostic: 0.722804878%; not a measured 2x change or GCI
- Additional-grid nominal pressure error: −0.241125813%
- Additional-grid nominal velocity L2 error: 0.085042182%
- Additional-grid analytical thermal L2 error: 0.175547301%
- Additional-grid mixed outlet temperature: 304.540329999 K
- Pressure analytical-error orders across successive grid pairs: 1.96579,1.97663,1.99265
- Additional 20-iteration velocity L2 change: 1.1454e−10; temperature field changes remain about 1e−10 K
- Medium-grid outlet-location temperature-rise change: 0.0096879%

The actual orthogonal-mesh/upwind boundary-energy extraction and extended-domain plane orientation were checked. The low-speed sentinel's axial/transverse diffusion ratio is approximately 0.2895; omitting axial diffusion produces roughly 22% field error, making this a meaningful equation check. The report keeps `initial_all_passed=false`, with supplemental results separately recorded.

No remaining scientific blocker was identified for publishing this carefully qualified **numerical research evidence package**. This review does not turn it into experimental validation, aircraft applicability, conjugate heat-transfer validation, or an unconditional all-green result. Application integration remains outside this research package. Publication chronology and compact-data storage are documented in ../COOLING_RESEARCH_PUBLICATION.md.
