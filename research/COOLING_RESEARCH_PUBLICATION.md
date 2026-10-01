# Cooling research: repository publication scope

This addition publishes the completed synthetic 3D cooling-channel study and the subsequent directional pressure-error diagnosis alongside the existing native-agent demo. It changes no application physics, frozen native-agent trial, CAD asset or UI behavior. It is stacked on the unified-demo branch; it does not merge or deploy the project.

## What the evidence establishes

- Real serial Gmsh 4.15.2 → OpenFOAM v1912 mesh, flow and passive fluid-temperature calculations, with saved actual field plots, conservation checks, reference comparisons and source hashes.
- The original all-direction pressure-gradient change was **1.120839% > 1%**. That preregistered gate remains failed.
- The directional study attributes approximately **98.12%** of the separate axial/transverse pressure changes to transverse refinement. A later fixed-axial transverse doubling changes the pressure gradient by **0.278450%**; its fully developed continuum-target bias is approximately **−0.088963%**. This does not pass the original all-direction gate.
- The separately registered inlet-isolation control reaches 1500 iterations with final velocity residuals approximately 1.6–1.8e−7, above 1e−7. It is excluded from accepted comparisons and causal conclusions. Near-inlet local pressure oscillations remain unresolved.
- No solid/fluid conjugate heat transfer, measured-data validation, aircraft applicability, device hotspot or converged total wall-heat prediction is claimed.

The Chinese reports and recorded verification summaries describe the study at the time it was completed, before repository publication. Their historical “not published” status is not a claim about this later publication. The frozen solver scripts, preregistered plans, numerical reports, solver extracts, source-artifact identities and original field/figure bytes are retained; presentation wording and package readers are updated for publication. [Publication provenance](COOLING_PUBLICATION_PROVENANCE.json) records study-versus-publication hashes for those changed files. Hashes establish byte consistency, not independently trusted execution dates or reviewer identity.

## Audit from a clean clone

Python 3.10+ and the standard library are sufficient for these integrity and honest-status checks:

```sh
python -S research/openfoam_3d/audit_package.py
python -S research/openfoam_directional/audit_package.py
python -S research/openfoam_directional/storage.py
```

The new CI also runs the 8 original numerical-evidence tests and 12 directional algebra/bookkeeping tests, plus 4 lossless-storage tests. These checks do not execute CFD, and passing software tests does not erase either scientific failure. The existing cross-platform application, browser and CAD jobs remain enabled.

## Exact-byte archival representation

Four directional profile JSON files exceed the compact JSON size limit; one original plot exceeds the compact image size limit. They are encoded as deterministic gzip streams split into parts no larger than 60,000 bytes in `openfoam_directional/evidence/archive/`. `evidence/storage.json` records each original logical filename, byte count, SHA-256 and ordered part identities. `evidence/manifest.json` retains the original logical file identity and identifies the archival representation. No arrays are rounded or subsampled, and no image pixels are changed.

`storage.py` verifies every part, reconstructs the gzip stream, decompresses it and verifies the original byte count and SHA-256. `storage.read_json(path)` supports archived profiles directly. To inspect the full original plot and profiles in a fresh local folder:

```sh
python -S research/openfoam_directional/storage.py --extract-to output/directional-evidence
```

Open `output/directional-evidence/evidence/directional_comparison.png`. The other real-field PNGs remain ordinary viewable files. Extraction refuses an existing output directory. Generated files remain ignored under `output/`.

## Full calculation replay is a different operation

The compact repository is **not** the full native-field archive. Original native meshes, dictionaries, solved fields and complete logs remain in separate retained local output, with **220** original-source and **221** new directional-source hash records. Those hashes allow verification when the full source is present; they do not make absent files downloadable or prove an independent third-party reproduction.

The 3D replay needs the pinned research dependencies and already installed Gmsh/OpenFOAM tools described in its README. It creates a fresh output namespace. The exact registered directional replay additionally requires the original retained `output/openfoam-3d-v2` baseline with its frozen hashes. A clean clone cannot silently regenerate and substitute that baseline: fresh runtime/log hashes require registering a new baseline and a new study. The failed inlet-control case is expected to stop its strict replay at the unchanged residual criterion; follow-up scripts record that failure rather than accepting its unconverged field. No CFD replay was needed for publication.

## Decisions left open

The next engineering milestone should be a bounded component-design decision with multiple feasible CAD alternatives and a frozen tradeoff brief. Before using solid temperatures, add and verify one simple solid/fluid interface problem; before using entrance losses, resolve an appropriately bounded entrance-control test. Expanding to a complete motor or aircraft, or refining residuals indefinitely without a decision requirement, is not justified by this package.
