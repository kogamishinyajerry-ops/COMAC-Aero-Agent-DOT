# Three-dimensional cooling-channel numerical verification

This research package runs a real, local **Gmsh → gmshToFoam → checkMesh → OpenFOAM** workflow. Its deliberately small synthetic rectangular fluid duct links to the existing aspect-2 Graetz model in `research/rectangular_duct/`. It does not claim experimental validation, aircraft applicability, a recovered motor geometry, conjugate solid/fluid heat transfer, or a device-temperature prediction.

## Scope and honest status

The initial three-grid study **did not pass every preregistered gate**: its medium-to-fine pressure-gradient change was 1.120839%, exceeding the 1% limit. This failure is preserved. A separately registered 1.25× grid adds accuracy evidence; its smaller raw adjacent change cannot retroactively pass the original 2× refinement gate. The extra pressure diagnostic scales the observed change by 5.3333 under an explicitly conditional second-order assumption. It is not a measured doubling, a GCI or a physical uncertainty bound.

All displayed fields are actual saved OpenFOAM cell data. No model-generated pictures or fabricated CFD contours are used. The primary outputs include the mixed outlet temperature, pressure gradient, analytical field errors, mass and energy balances, solver residuals, mesh quality and runtimes.

## Geometry, physics and boundaries

- Synthetic dimensions: length 30 mm, width 4 mm, height 2 mm
- Synthetic constant air properties: rho 1.2 kg/m³, mu 1.8e-5 Pa s, k 0.026 W/(m K), cp 1005 J/(kg K)
- Nominal inlet area-mean speed: 3 m/s; Re based on Dh = 533.333
- Thermal inlet 300 K; all four physical walls 310 K
- Gmsh generates hexahedra with 40×16×8, 80×32×16 and 160×64×32 cells; the additional grid has 200×80×40
- All three solution directions are active. Four sidewalls have no-slip velocity. No empty or symmetry faces replace the spanwise solution
- `simpleFoam`: Newtonian laminar incompressible flow, steady SIMPLEC, initial velocity and pressure zero, analytical rectangular inlet profile, inlet pressure zeroGradient, outlet kinematic pressure zero, outlet velocity zeroGradient
- Each inlet profile is normalized by its face midpoint quadrature to exactly 3 m/s numerical mean. The corresponding continuous-profile mean varies slightly by grid. Both that reference and the fixed nominal 3 m/s reference are reported; they must not be mixed
- `scalarTransportFoam`: frozen converged U **and pressure-corrected phi**, DT=k/(rho cp), steadyState, full isotropic fluid diffusion, upwind convection, fixed temperature inlet/walls and zeroGradient outlet
- No buoyancy, solid conduction, conjugate wall interface, temperature feedback, turbulence, radiation, viscous heat generation, rotation or compressibility

The fluid-temperature equation is a passive constant-property heat model. A solid material or fin-conduction capability is not implied.

## Exact and independent references

### Momentum

The rectangular Poisson separated series gives u(y,z) and the fully developed pressure gradient. The pressure fit uses cross-sectional means over x/L=0.25–0.75, avoiding endpoint pressure-boundary artifacts. The inlet-to-outlet pressure drop is reported separately; it is not silently substituted for this interior gradient.

### Smooth three-dimensional thermal sentinel

A separate unit-amplitude scalar uses prescribed uniform plug velocity 0.05 m/s, not a solved no-slip cooling flow. On the same 3D meshes:

`theta = sin(pi*y/W) sin(pi*z/H) exp(r*x)`

`r = -2 alpha lambda / (U + sqrt(U² + 4 alpha² lambda))`

`lambda = (pi/W)² + (pi/H)²`

Substitution satisfies `U dtheta/dx = alpha laplacian(theta)` exactly. Exact Dirichlet data are imposed at both ends and zero on four sides. The scalar is stored as OpenFOAM's T field with unit temperature amplitude; the reported error is relative to this zero-wall normalized amplitude, never to an absolute 300 K background. Centered convection is used only for this smooth low-Peclet sentinel. Axial diffusion is material: r²/lambda≈0.2895, and omitting it produces about 22% field error. Relative L2 compares analytical point values and numerical cell-center samples on uniform equal-volume cells.

### Existing reduced models

`references.py` imports the unchanged existing conservative rectangular Graetz FVM into an isolated new output directory. It also repeats the independent sine-Galerkin reference with analytical velocity and exact modal axial propagation. These models omit axial fluid diffusion. Their agreement with OpenFOAM is a model-to-model comparison, not an exact same-equation benchmark or a new blind experiment. No experimental points or fitted coefficient entered case selection or the solver.

## Singular inlet corner and conservation

The uniform cold inlet meets hot walls discontinuously. With full diffusion, local gradients near those edges scale as 1/r. Separately integrated wall heat and inlet conductive loss are therefore logarithmically mesh-sensitive. **Do not use total wall heat as a converged physical heat-transfer prediction.** Mixed outlet temperature and signed discrete closure remain useful outputs.

The boundary energy residual includes actual upwind convective fluxes and inlet, outlet and wall conduction. It uses the 300 K enthalpy datum and normalizes signed net watts by `rho cp U W H (Tw−Tin) = 0.28944 W`; it is not divided by a growing singular wall heat. Twenty additional iterations test field and QoI stationarity without replacing the primary reported fields. A medium-grid 45 mm extension checks the original 30 mm outlet-plane sensitivity with unchanged cell spacing; it re-solves flow as well as temperature.

## Reproduction and environment

Use the already installed isolated Gmsh 4.15.2 and OpenFOAM Debian v1912 patch 200626 at `/workspace/shared/cfd-tools`. This package does not install software, change security settings, use MPI, or call an external simulation service/API. Research Python dependencies are in `dependencies.json`; they are not application requirements.

From the repository root:

```sh
mkdir -p output
# Wall-clock bound on the complete replay; original CFD solver budget is 2700 s.
timeout 2700 bash research/openfoam_3d/reproduce.sh
```

Audit the compact candidate with `python -S research/openfoam_3d/audit_package.py`. Where the retained full run exists, add `--full-source` to verify all 220 native source-artifact hashes as well.

The default creates a fresh ignored output directory and never overwrites frozen evidence. An explicit `OPENFOAM_STUDY_OUTPUT` must also be fresh. Full generated `.geo`, `.msh`, OpenFOAM dictionaries, mesh, fields, logs and local NumPy archives stay there. Compact reviewed evidence and actual-field images are distributed separately. Source scripts regenerate the long nonuniform inlet boundary arrays; they are not hand-edited mesh-specific data.

Execution is serial. OpenFOAM time-directory numbers are steady-iteration indices, not elapsed physical time; its printed Courant number does not impose a transient CFL restriction here. Harmless UCX VFS socket warnings also occur in the prior verified tool installation; no security workaround is applied. Report a nonzero solver exit or absent convergence rather than suppressing it.

## Chronology and limits

`plan.json` was registered before solver runs, including independent-review fixes for the inlet singularity and a diffusion-sensitive sentinel. An initial setup attempt called checkMesh before writing fvSchemes and failed without solving. A strict numerical stop of 1e-9 for near-zero transverse velocity then reached 1500 iterations although it met the frozen 1e-7 acceptance limit; the stop was aligned with that existing limit. Old attempt data are kept in the working output, not reused. A fresh output directory prevents accidentally choosing an older time directory as a new solution.

`supplemental_plan.json` defines stationarity and outlet checks before their execution. `additional_refinement_plan.json` records the later, bounded extra grid and the original failed gate. No physical parameters, measured targets or error thresholds were fitted. Existing rectangular/plate-fin experiments and pinned demo outputs remain unchanged.

## Primary documentation

- [OpenCFD simpleFoam equations and kinematic-pressure inputs](https://doc.openfoam.com/2306/tools/processing/solvers/rtm/incompressible/simpleFoam/)
- [OpenCFD scalarTransportFoam transport equation](https://doc.openfoam.com/2212/tools/processing/solvers/rtm/basic/scalarTransportFoam/)
- [OpenCFD SIMPLE/SIMPLEC and solution controls](https://www.openfoam.com/documentation/user-guide/6-solving/6.3-solution-and-algorithm-control)
- Installed v1912 solver help, tutorials and dictionaries establish the actual syntax used; newer online documentation describes the equations, not a substituted runtime version
