# Physics evidence: an explanation with three distinct levels

Run `python -m aerolab serve`, then open `http://127.0.0.1:8765/physics`. The nacelle navigation also links to this page. No API key, network request or third-party runtime package is required. The page is served only by the existing local-loopback application.

The page answers three engineering questions without conflating their evidence:

1. **Where is the air going?** Published CFD stations constrain effective flow areas. An initial-climb-only conditional conductance fit is checked retrospectively against cruise and dash, including table-rounding intervals. This is source/model discrepancy analysis
2. **What is the cooling passage?** A historical 2 × 17 × 105 mm heat-sink unit cell is compared with the current broad passage at matched area, velocity, length and heating boundary. This is an explicitly hypothetical component-scale comparison, not a replacement of final-2023 CAD
3. **How do the walls exchange heat through the air?** A finite-volume parallel-plate solution exposes asymmetric thermal coupling. This is a verified numerical subproblem, not turbulent rotating-motor CFD or an experimental validation

## What is newly computed?

`POST /api/physics/evaluate` accepts only an optional `case` selected from `asymmetric`, `equal`, `one_wall`, `balanced`, `reversed` and `zero_flow`. The server rejects all other parameters, preserves same-origin/one-calculation-at-a-time safeguards, and bounds its response below 100,000 bytes.

The source audit, historical arithmetic and chosen finite-volume case are computed in that process. The spatial fluid-cell samples, wall temperatures, outlet bulk temperature, residuals and input fingerprint are returned from the solver. The graphic uses those samples, not a painted field. Its displayed cell patches are a downsampled representation rather than a CFD mesh. Flow reversal changes physical inlet/outlet coordinates. Zero forced flow with heat returns a no-steady-state status and no plotted temperatures.

The grid-convergence and independent spectral-reference comparisons are a **saved verification record**. Before displaying their status, the server checks the numerical-model and reference-generator source fingerprints and all saved acceptance gates. A stale record causes an explicit error, not a pass badge. CI additionally regenerates and compares the complete record.

## Interaction and evidence

- Keyboard-accessible tabs support Left/Right, Home/End and browser Back/Forward
- A new calculation temporarily disables repeat actions and exports
- Cancelling or encountering an error retains the previous result with an explicit old-result label; it does not relabel the old temperature as the newly requested case
- Navigating away aborts the wait and does not leave a restored page permanently busy
- Native JSON download contains the actually displayed case, source identities and limitations; the filename binds its input hash
- Desktop/mobile browser tests exercise all six cases, failure/cancellation, export identity, navigation and overflow, and save actual Chromium screenshots

## Verification commands

```sh
python -m unittest discover -s tests -v
python scripts/generate_source_audit.py --check
python scripts/generate_duct_verification.py --check
python scripts/generate_historical_motor.py --check
python scripts/generate_nacelle_evidence.py --check
python scripts/generate_nacelle_credibility.py --check
python tests/ui_physics_smoke.py
```

The last command needs an authorized Playwright/Chromium environment. A blocked or never-run browser test is not a pass. The project CI runs it alongside the existing mission, CAD and nacelle browser tests. Acceptance belongs to the exact published commit and its CI/pixel review, not merely this document.

## Scientific limits that stay visible

Full-load X-57 temperature validation remains unresolved. The current nacelle CAD and thermal model are unchanged by this page. No fitted coefficient, historical material assumption, effective channel count or laminar correlation is transferred into the production nacelle model. No actual fin count, final motor dimensions, physical uncertainty interval or airworthiness margin is newly asserted.

Further work needs final-configuration passage geometry/face exposure, directional winding and potting/contact properties, component-node definitions, and matched test boundaries with pressure, flow and temperature measurements. Useful public subproblems can be verified while those aircraft-level gaps remain open.

Details: [source audit](NACELLE_SOURCE_AUDIT.md), [historical unit-cell benchmark](HISTORICAL_MOTOR_BENCHMARK.md), [finite-volume formulation](DUCT_SUBMODEL.md), [physics research and independent references](research/NACELLE_THERMAL_PHYSICS_AUDIT_2026-09-30.md).
