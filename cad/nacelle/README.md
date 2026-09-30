# Mod II local nacelle reconstruction

This folder contains a newly generated, dimensionally inferred X-57 Mod II local-wing/nacelle assembly. It is **not recovered NASA CAD**, the Mod IV exterior, a manufacturing model, or validated CFD. The older 43-fin benchmark in the parent `cad/` folder remains a separate artifact.

## Evidence and representation

- Source topology: Borer, Bui and Smith, [2023 thermal analysis](https://ntrs.nasa.gov/api/citations/20230006888/downloads/Borer_Bui_Smith_X-57_thermal_analysis.pdf), figures 5–7, printed pages 7–8
- Historical scale anchors: [NASA cruise-motor/propeller overview](https://www.nasa.gov/centers-and-facilities/armstrong/x-57-maxwell/), 14-inch motor / 5-foot propeller. That specifications section describes Mod IV, so these are explicitly historical anchors rather than a dimensioned Mod II drawing
- All other dimensions, materials, local airfoil and propeller sections are inferred parameters
- The local host wing is installation context. Its volume is excluded from nacelle hardware mass and hardware-interference claims
- STEP contains named hardware components plus a named installation-context wing. There are no fictitious solid air boxes
- The browser's closed procedural loft meshes and the named OpenCascade solids use the same dimensional construction. Both carry a fingerprint bound to parameters and an immutable import-time construction-source digest

## What is modeled

Hollow split cowling with real upper scoop openings, a top-center external motor-exhaust aperture/louvers and lower outlet; hollow slotted spinner and three twisted blades; outrunner rotor, inner magnet annulus, segmented stator windings and axial slots; ventilated rear cup/flange; two tilted side-by-side CMC cases; separate HV fin arrays and LV backplates/electronic proxies; fresh-air ducts, baffles, routed tubular supports and explicit CMC mounting brackets.

## Validation

`manifest.json` records closed positive-volume BRep solids, procedural mesh closure, independent BRep/mesh volume comparison, STEP import roundtrip, every measured nonzero hardware interference, and named minimum-distance mechanical contacts. Designed blade-root, flange, duct-edge and frame/bracket attachment overlaps are explicitly enumerated. The gross component mass is a proxy sum: small permitted attachment overlaps are not subtracted and inferred densities are not measured hardware weights.

A successful cached STEP is served only when all full-audit gates, roundtrip, source identity and compressed/uncompressed checksums pass. Failed or incomplete development exports are never advertised as verified. Custom geometry is range and forward-cowling-clearance checked; its full collision/contact audit requires regeneration and is not inherited from the baseline.

## Transparent bounded chunk storage

The checked-in STEP is stored as ordered raw byte slices of **one gzip stream**, each at most **250,000 bytes**. These are not separate STEP files and must not be decompressed individually. `manifest.json → artifacts.step.chunks` records each zero-based index, basename, byte count and SHA-256. It also records total compressed/uncompressed sizes and SHA-256 values, the gzip compression type and the chunk-storage format.

The standard-library cache reader checks sequence, unique safe filenames, bounded sizes and every chunk hash, then checks the combined compressed hash before bounded decompression. Missing, reordered, truncated, duplicate or corrupted parts are rejected. Decompressed size, one complete gzip member and the final STEP hash are checked too. There is no unchecked single-file fallback.

The download API still returns one ordinary `x57-modii-nacelle.step` file; clients do not assemble parts themselves, and the verified baseline needs no CadQuery installation. The generator writes chunks and replaces the manifest only after an exact readback succeeds. `--verify-only` reassembles through the same strict reader before independently importing the complete STEP with OpenCascade. Chunking changes storage only: all physical geometry, named solids and audit requirements are unchanged.

## Flow/thermal boundary

Network sections are dimensional equivalents, **not volumes extracted from a solved air-domain CFD mesh**. Main inner cooling and outer motor bypass have distinct inlet sections. The stator slots and rotor gap are parallel paths. Each LV scoop has its own inlet section and a separate nominal backplate heat-exchange section. Lower and upper external outlets use specified projected aperture planes. Conduction paths state their inferred heat-flow direction separately from dimensional plate/sector measurements.

## Regenerate

    python scripts/generate_nacelle.py --out cad/nacelle
    python scripts/generate_nacelle.py --verify-only --out cad/nacelle
    python scripts/generate_nacelle.py --out output/custom-nacelle --params '{"hv_fin_count":28}'

Fresh STEP/BRep generation requires optional CadQuery 2.7.0. Runtime geometry, metrics and verified checked-in baseline download require only Python's standard library. Coordinates are millimetres: X aft, Y spanwise, Z up.
