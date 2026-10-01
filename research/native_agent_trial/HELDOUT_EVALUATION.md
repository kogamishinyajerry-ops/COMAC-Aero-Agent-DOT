# Independent heldout evaluation

## Result: PASS, conditional on the frozen component model

The native assistant changed its selected design from the development run's 16 fins × 0.60 mm to **12 fins × 0.60 mm** for the separately committed task. The independent grader passed **23 checks**, including reconstruction and independent reading of the actual CAD bytes. No task, source, adapter or acceptance changes were needed.

This is one **withheld-configuration feasibility-transfer trial in a familiar nine-candidate family**. It is not a blind-family benchmark or evidence of broad engineering generalization. The new 25 g cap leaves only one mass-eligible candidate, so the trial primarily tests changed constraints, applicability, live computation, verification and honest reporting rather than a difficult optimization search.

## Fixed task and result

- 36 W in every case; inlet 25°C; required uniform-base temperature at most 80°C; fin-only aluminum mass at most 25 g
- Four cases: 17 Pa open, 11 Pa open, 17 Pa with channel 1 sealed, 11 Pa with channel 1 sealed
- Fixed 41.5 mm base width, 90 mm length and 11.3 mm fin height; mathematical duct width 45.2 mm
- Selected mass: **19.77048 g**, leaving **5.22952 g**
- Worst temperature across all twelve selected-design runs: **75.661059°C**, leaving **4.338941°C**
- Highest computed Reynolds number: **2235.502**, below the fixed 2300 cutoff
- A real computation of the former 16-fin selection was retained as a rejected alternative: **26.36064 g**, exceeding the new limit by **1.36064 g**

| Condition | Primary G, W/K | Primary base temperature, °C | Worst of three meshes, °C |
|---|---:|---:|---:|
| 17 Pa, open | 0.914945 | 64.346629 | 64.369719 |
| 11 Pa, open | 0.776538 | 71.359630 | 71.382521 |
| 17 Pa, channel 1 sealed | 0.837888 | 67.965172 | 67.990310 |
| 11 Pa, channel 1 sealed | 0.710955 | 75.636117 | 75.661059 |

Every selected-design condition was actually solved on 48×144×800, 64×192×800 and 48×144×1600. Maximum spatial conductance difference was **0.0586495%**, below 0.5%; maximum axial difference was **0.00891093%**, below 0.2%. All residual, energy, geometry, capacity and applicability gates passed. The grader independently checked the temperature and mass arithmetic, sums of branch flows, zero enthalpy transport in the closed branch, unchanged open-branch flow under equal-pressure closure, and 11/17 pressure-flow scaling.

## Native execution and budget

The public action trace records initialization, an analytic inspection, a failed 16-fin alternative, twelve selected-design solves, CAD generation, and finalization. Each evaluate action addresses one design/case/mesh; the frozen adapter contains no search or selection policy.

- **13 actual PDE solves / 24 allowed**
- **1 CAD call / 3 allowed**
- **17 engineering-tool actions / 40 allowed**
- **518.64 seconds / 3600 allowed**
- **0 recorded runtime errors**
- **0 execution-stage human interventions and 0 external model API calls declared**

The two pre-exposure adapter limitations in [ADAPTER_REVIEW.md](ADAPTER_REVIEW.md) did not affect this task: analytic rejections exist, and its objective is feasibility rather than ranking a heavier candidate against a lighter one. Their existence does limit claims about arbitrary task instances.

## Actual CAD verification

The grader reconstructed STEP and STL from the saved gzip chunks and verified byte hashes before opening them.

- STEP: one valid closed solid, **18,527.4 mm³**; bounding box **41.5 × 90 × 14.3 mm**
- **23 independent occupancy probes** confirmed all 12 fin centers are solid and all 11 intervening gap centers are empty
- Independently recovered fin mass: **19.77048 g**
- STL: **188 triangles**, 96 vertices and 282 edges; connected, watertight and consistently oriented
- STL relative volume error: **2.20×10⁻⁷**

The 14.3 mm total CAD height includes a **3 mm illustrative support base** under the 11.3 mm fins. That base is excluded from the task's fin-only mass and is not modeled as a spreading resistance. The 45.2 mm mathematical duct boundary is not an exported solid.

## Commitment chronology and integrity

- Protocol committed before the heldout task
- Task and grading criteria committed at **2026-10-01 04:29:49 UTC**, before any new heldout reference solves
- Private reference computation: **04:30:53–04:35:29 UTC**, using byte-identical staged frozen sources; no task or reference values were given to the developer/executor during development
- Adapter freeze independently verified before release; development terminated at **04:41:50 UTC**
- Parent-authorized exact-byte task release: **04:42:25 UTC**
- Heldout execution terminated at **04:51:57 UTC**
- Independent grading: **04:52:14 UTC**

The task and grading were not tuned after seeing reference or executor outcomes. All twelve selected-design results agree with the post-commitment private reference rerun, within floating-point tolerance. Those reference runs are outside the executor's budget and were not available to it.

Key identities:

- Task SHA-256: `52d8222b71afa2fb1d4e9584286e92d060c51e4044a0b4df20f0b45e5712274d`
- Preregistration SHA-256: `786c85518beec32e7057c1b860450475a77cf5ecdec6a8c39968df7e72769ae8`
- Protocol SHA-256: `7637f775ae3f670589b8abc7ab4e96abfe8b44f809fbe17b8fcc9ee40604e8ae`
- Adapter SHA-256: `0898baa98b80b0217bf7a435a5f2aa0cf8f30f1f4ba6ec924564145a8ecec262`
- Grader source SHA-256, prepared before terminal output: `5278ad427c9f3384daeeb5825fa944c26a0bf0f757df7bb5a623abe65cacd3a0`
- Terminal result SHA-256: `2d3cc9fb91bebc41472f2a7ddee3928d0d7f7412f48196692bd0bf80d88d1f09`
- Terminal event-chain SHA-256: `c5a72facb1a75007a8c8b2b17c8e0fc1b491c08e61dca78f65032154b41d01d7`

## Executor exposure declaration

After the terminal result, the executor explicitly stated that it never read evaluator-private files; first saw the heldout task only after authorized public release; made no off-adapter heldout PDE calls; received no heldout candidate selection; and changed no requirements, model, protocol or adapter. It reported one additional read-only arithmetic check of saved branch flows, rather than a new solve. This is recorded in [the executor declaration](heldout_executor_declaration.json). It is a declaration, not an instrumented access attestation.

## What remains unproven

The agents share a filesystem: isolation relied on instructions and withheld messages, not an enforced access boundary. Local hashes are consistency evidence, not signatures or proof against rewriting all evidence. The grader checks saved public actions, numbers and CAD bytes, and does not independently attest the runtime model's identity, absence of every possible off-protocol read, or absence of every possible external API call. The runtime model identity remains unverified.

The solver uses fixed properties, a uniform base temperature, fully developed straight-channel friction and ideal common pressure. It omits important installed-system effects, including entrance/exit losses, fan curves, base spreading, contact resistance, axial conduction, turbulence and temperature-dependent properties. A sealed branch retains transverse conduction and has zero throughflow; resolved obstruction flow is not modeled. This is a numerical and model-conditional requirement pass, **not physical, manufacturing, aircraft or flight validation**. The private reference uses the same physics implementation and is not an independent model-form validation.

## Evidence

- [Frozen heldout task](heldout_task.json)
- [Machine-readable independent grade](heldout_independent_grade.json)
- [Public chronological events](runs/heldout/events/)
- [Terminal result](runs/heldout/results/017_finalize.json)
- [CAD checks and artifact identities](runs/heldout/results/016_cad.json)
- [Frozen protocol](protocol.json)
