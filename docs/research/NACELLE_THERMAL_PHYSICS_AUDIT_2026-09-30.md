# Motor thermal physics audit and a defensible next benchmark

Research date: 2026-09-30. No production model coefficients or geometry were changed in this investigation. All new calculations below are diagnostics or independently specified verification problems, not calibration of the X-57 reconstruction.

## Decision

**Do not repair the full-load temperature discrepancy with an h multiplier. First separate the historical motor heat-sink unit cell, the reconstructed winding-sector passages, and the final nacelle station model. They are not established as the same geometry.**

The most useful next public-source subcase is the **2 × 17 × 105 mm stator heat-sink passage** reported in the earlier motor paper. Its hydraulic diameter, laminar resistance, material mixture laws and numerical convergence can be checked without original CAD. Preserve it as a dated historical subcase, rather than silently replacing the 2023 nacelle geometry.

The other immediate improvement is **two-wall thermal coupling**. An independently heated annulus cannot generally be represented by two positive scalar wall-to-bulk heat-transfer coefficients. A weakly heated wall can be cooler than the mixed-mean fluid because the other wall heats the fluid strongly. The current magnet comparison exposes this limitation.

## 1. What the 2023 source actually specifies

Primary source: [Borer, Bui and Smith, 2023](https://ntrs.nasa.gov/api/citations/20230006888/downloads/Borer_Bui_Smith_X-57_thermal_analysis.pdf), particularly pp. 3–6, 9, 12 and Tables 4–9.

- Heat is per **one motor and two CMCs**. Peak losses are 5,237 W winding/stator, 582 W magnets, 810 W per HV sink and 30 W per LV backplate: 7,499 W total. MCP total is 6,080 W. These W values are heat rates; shaft power is a separate quantity.
- The 90/10 winding/magnet split and 50/50 inner/outer magnet split are model assignments. The paper does not give a measured gap-versus-slot winding heat split. Its uniformly loaded winding surface description does not identify every surface or expose the original face-area inventory.
- The reported flight speeds distinguish equivalent and true airspeed. CFD table velocities are **ft/s**, mass rates **lbm/s**, pressures **psi**, and temperatures **°C**. Use 0.3048 m/ft, 0.45359237 kg/lbm and 6,894.757293168 Pa/psi.
- Tables 7–9 give separate static and total quantities. A total-pressure inlet must not acquire an additional ram term if it already includes it. Rounded pressure differences carry up to roughly ±0.01 psi (±68.95 Pa) worst-case quantization uncertainty from two independently rounded entries; their actual uncertainty is not established.
- ICPT is a collection of component metamodels, some informed by testing. Table 5 supplies motor inputs at **2a_g/2a_s**, and CMC inputs at **5b**. Table 6 is neither a CFD wall-temperature table nor a measurement table.
- The source explicitly lacks experimental validation of its complete Mod II nacelle airflow. Its component-model history must not be borrowed as validation of this reconstruction.

### Inlet states are already nonuniform and heated

| Condition | Ambient static T, °C | Gap inlet 2a_g, °C | Slot inlet 2a_s, °C | Gap inlet total T, °C | Slot inlet total T, °C |
|---|---:|---:|---:|---:|---:|
| Initial climb | 35.85 | 38.00 | 43.09 | 38.63 | 43.50 |
| Cruise climb | 35.85 | 37.62 | 41.49 | 38.26 | 41.96 |
| Dash | 23.25 | 26.54 | 29.92 | 27.58 | 30.99 |

Feeding both reconstructed channels with ambient air does not reproduce these boundaries. Imposing these hotter temperatures **and** depositing all upstream heat again would double-count energy. A source-state replay therefore needs an explicit control-volume boundary and must stay separate from the autonomous network.

The source's total-pressure changes from 1_c to 2a_g/2a_s are approximately **690/1,034 Pa, 690/1,034 Pa, and 1,103/1,379 Pa** across the three cases. The current common main-inlet branch drops only **7.43, 7.17 and 7.14 Pa** in source-pressure mode. These station intervals do not equal a single lumped minor-loss coefficient, but their scale shows that resolving external drive alone leaves the motor entrances unresolved. Separate entry streams and mixing planes matter.

### Temperature comparison has a concrete semantic failure

| Condition | ICPT magnet, °C | Gap outlet mean static air 2c_g, °C |
|---|---:|---:|
| Initial climb | 45.4 | 53.42 |
| Cruise climb | 43.1 | 49.03 |
| Dash | 31.9 | 37.45 |

The current law gives each positively heated wall `T_wall = T_bulk + q''/h`, then reports the hottest downstream magnet patch. It cannot produce these inequalities at an equivalent downstream plane. This does **not** make the source unphysical: its ICPT input is at 2a, its reported node differs, and asymmetric annular heating can put one wall below mixed-mean air temperature. Section 4 supplies the exact low-Re counterexample.

There is also a source editorial ambiguity: p. 9 prose associates 67.2°C with the HV analysis input, while Table 5 explicitly selects 5b_hv_L/R and Table 7 gives 59.40/57.92°C there. 67.24°C is the slot outlet 2c_s. Preserve the conflict and prefer explicit station mappings for reproducible comparisons; do not silently equate these quantities.

### Why printed station averages cannot identify heat partition

The paper says station properties are averaged across sections, without publishing the weighting operator or integrated enthalpy flux. Using arithmetic mean inlet/outlet mass and the printed total-temperature change only as a diagnostic gives:

| Condition | Gap `m̄ cp ΔT0`, W | Slots, W | Bypass, W | Sum / stated motor heat |
|---|---:|---:|---:|---:|
| Initial climb | 708.61 | 5,034.65 | 353.57 | 1.04775 |
| Cruise climb | 576.98 | 3,958.00 | 34.04 | 0.98006 |
| Dash | 736.18 | 4,802.86 | −76.21 | 0.93879 |

Here `cp=1007 J/(kg K)` is a diagnostic assumption. Inlet/outlet mass is not exactly equal; these are not closed streamtubes with known mass-weighted temperatures. In particular, the negative apparent bypass heat in dash cannot be imported as a negative prescribed magnet heat. No heat split or h should be fitted from these products. Required data would be the integral of `ρ u_n h_total` on matched control surfaces, plus wall heat flux, leakage and shaft-work accounting.

## 2. Geometry exposure: the missing distinction

The reconstructed cooling-slot branch consists of **24 angular gaps between winding sectors**, with a 49.2 mm radial depth, 133 mm length, 6,153.86 mm² aggregate flow area and 9.42485 mm hydraulic diameter. Its slot-side heated area is 0.314093 m². The extra 0.144953 m² labelled winding-to-gap area is a **stator outer-envelope proxy**, not the actual copper winding surface: the reconstructed winding outer radius is 145.8 mm, while the gap starts at 153.8 mm.

For comparison, the reconstructed sector surfaces have these ideal analytic areas:

| Surface class | Area, m² |
|---|---:|
| Two circumferential sides of every sector | 0.314093 |
| Winding outer curved faces | 0.101828 |
| Winding inner curved faces | 0.067466 |
| Both axial ends | 0.062626 |
| All of the above | 0.546013 |

These are **not all proven exposed convection area**. Solid contact, potting, supports, local air connectivity and the finite polygon representation must be classified first. Adding every surface to hA would be unjustified.

The earlier [Chin/Tallerico/Smith motor manuscript, NTRS 20190032520](https://ntrs.nasa.gov/api/citations/20190032520/downloads/20190032520.pdf), p. 4 Eq. (1) and p. 5 Fig. 4, describes a **dense stator heat-sink fin pack**, with **2 mm × 17 mm channels, length 105 mm, Dh=3.58 mm**. Figure 4 shows the fins beneath the windings and structural members. The 2023 Fig. 5 also visually shows fine cooling passages, but supplies no dimensions or count. This is strong evidence that the current broad sector-gap representation is not a demonstrated recovery of the real stator cooler.

The earlier record is dated and its detailed motor material/potting state differs from later builds. Its channel count, full face allocation and final-configuration applicability remain unknown. Do not multiply a guessed channel count until temperatures match.

At the current initial-climb source-pressure geometry, replacing only slot flow with the published 0.207745 kg/s while retaining current heat allocation, scalar correlation and solid paths produces a **168.18°C slot winding proxy**, versus 225.79°C at computed flow. Thus correcting slot flow alone does not close the discrepancy even in this deliberately frozen diagnostic. This is not a new network operating point or an ICPT-equivalent prediction.

## 3. Historical motor paper: useful evidence, unsafe wholesale import

The NTRS record dates the archived manuscript to 2019; NASA's later bibliography associates the title with AIAA-2018-3410. Use the exact record/PDF identity rather than treating its assumptions as final-2023 hardware.

### Experimental and model boundary conditions

- pp. 2–4: open-air AirVolt test stand, 255 N·m at 2,250 rpm, approximately 60 kW shaft power; three cooling carts, described as supplying up to 600 lb/min of 8°C air onto the spinner. Actual motor cooling velocity was uncertain. The 27°C starting winding temperature and 100°C stop criterion are test conditions, not the 2023 limits.
- Thermistors were placed between coils and steel, with variable contact; raw sensor offsets and EMI filtering were applied. Peak model temperature was calibrated to the highest recorded thermistor trace. Thus this is not a clean independent experimental heat-transfer coefficient measurement.
- pp. 4–6: a 30° stator segment included aluminum support/fins, steel, copper/epoxy and Nomex liners. Both loss and cooling were adjusted. Reported 2-D and 3-D model fits implied materially different efficiencies (94% versus 88%); the authors explicitly warn that increased dimensional fidelity did not make the result more accurate.
- pp. 7–10: the separate electromagnetic/mechanical loss model lists rounded values of 966 W core, 578 W magnets, 228 W winding eddy, 60 W mechanical and 947 W resistive loss, and reports 2,781 W total at its nominal point (the rounded components sum to 2,779 W). The authors call this an underestimate. Do not replace the later Table 4 loads with it.
- pp. 11–13: the older whole-nacelle network used CAD-derived hydraulic connections, lumped thermal masses and generic correlations. The authors explicitly limit the gap sweep to sensitivity, not actual component-temperature prediction. Its nominal external bypass clearance is 3/8 inch (9.525 mm), which must not be confused with the rotor–stator air gap or imported as the final design.

### Three independently checkable source-quality issues

1. **Specific heat mixing.** Table 1 gives copper `(ρ,cp,k)=(8960,385,400)` and epoxy `(1225,1000,1)` in SI. Bulk density 4705.75 kg/m³ and parallel conductivity 180.55 W/(m K) imply copper volume fraction 0.45. The printed bulk cp=723.25 J/(kg K) is a volume-fraction arithmetic average. Conservation of constituent sensible heat instead gives:

   `ρ_bulk cp_bulk = Σ φ_i ρ_i cp_i = 2,226,070 J/(m³ K)`

   `cp_bulk = 473.05318 J/(kg K)`

   The printed pair yields 3,403,433.6875 J/(m³ K), **52.89% larger**. This is a table-consistency finding, not proof that the actual COMSOL file used the wrong value or that it caused the reported transient discrepancy.

2. **Liner conductivity units.** The PDF visibly prints 139 under W/(m K) for a 0.25 mm liner. The manufacturer's [Nomex Type 410 data sheet, Table IV, p. 6 (distributor-hosted historical copy)](https://pronatindustries.com/wp-content/uploads/2014/07/Nomex_Tape410_technicaldatasheet.pdf#page=6) gives **139 mW/(m K)=0.139 W/(m K)** at 0.25 mm and 150°C. The PDF was downloaded and that table visually inspected. This strongly suggests a units transcription problem. The paper does not establish grade 410 or disclose its actual solver input, so do not silently correct and claim an exact historical reconstruction. Provenance caveat: the linked document is DuPont-authored but hosted by a distributor; current official manufacturer PDF URLs returned 404 or redirected during this audit. Indexed official copies independently show the same table.

3. **Viscosity notation.** Eqs. (2)–(3) use ν where their dimensions require dynamic viscosity μ, despite the nomenclature assigning ν kinematic units. Implement `Re=ρUDh/μ` and `Pr=μcp/k`; do not reproduce the symbol-level inconsistency.

The reported material bounds themselves are reproducible: at 45% copper volume, ideal series and parallel conductivity are **1.8144704 and 180.55 W/(m K)**. These are idealized directional mixture limits, not measured winding properties. A later [NASA failure-mode presentation, p. 24](https://ntrs.nasa.gov/api/citations/20240003366/downloads/3-X-57_traction_system_failures.pdf#page=24) says potting penetration and remaining void pockets affected the ICPT thermal analysis. An isotropic k=8 with one contact resistance cannot stand in for that documented manufacturing sensitivity.

## 4. Quantitative verification subcases

### A. Historical-size rectangular channel: ready now

Use the earlier paper's **single channel dimensions only**: full gap `a=0.002 m`, width `b=0.017 m`, length `L=0.105 m`. Select stationary, incompressible, fully developed laminar flow; this intentionally differs from the manuscript's operating Re≈3,000–10,000.

For imposed pressure gradient `G=−dp/dx>0`:

`U = G a²/(12μ) × [1 − 192a/(π⁵b) Σ(n odd) tanh(nπb/(2a))/n⁵]`

`Dh=2ab/(a+b)=0.00357894736842105 m`

`f_D Re_Dh = 83.0079715727522`

An independently documented version of the rectangular Poisson-flow series appears in [NASA/CR-2005-213799, printed p. 10, Eq. (41)](https://ntrs.nasa.gov/api/citations/20050187025/downloads/20050187025.pdf), using half-width/half-height notation. Keep that convention distinct from the full dimensions above.

An independent cell-centered 2-D finite-volume solution of `−∇²u=1`, with zero velocity at all four walls, was run here. Cell-center boundary distance was half a cell; no analytical velocity profile was inserted.

| Cells across gap × width | Computed f_D Re | Mean-velocity relative error |
|---|---:|---:|
| 8 × 68 | 80.388684 | +3.25828% |
| 16 × 136 | 82.335969 | +0.81617% |
| 32 × 272 | 82.838842 | +0.20417% |
| 64 × 544 | 82.965617 | +0.05105% |

Approximately fourfold error reduction per grid doubling verifies second-order convergence for this subproblem. With explicitly selected `ρ=1.02 kg/m³`, `μ=1.90e−5 Pa s`, `Re=500`, the independent exact target is **U=2.602364475 m/s, ṁ=9.025e−5 kg/s per channel, Δp=16.82248710 Pa**. Exclude entrance/minor losses for this benchmark.

The source's Gnielinski equation can be a separate **formula regression**: with `Re=10000`, `cp=1007`, `μ=1.90e−5`, `k=0.027`, smooth-wall `f_D=0.0314798027567`, `Nu=29.9991287596`, `h=226.316956672 W/(m² K)`. This chosen property set requires U≈52.05 m/s and is not the source test condition. Formula agreement is not experimental validation.

### B. Annulus with unequal wall heating: next thermal reference

For a stationary annulus, let `η=ri/ro`, `Dh=2(ro−ri)`. The exact laminar resistance is:

`f_D Re_Dh = 64(1−η)² / [1+η²−(1−η²)/ln(1/η)]`

This follows [NASA TN D-1972, pp. 19–20](https://ntrs.nasa.gov/api/citations/19630010444/downloads/19630010444.pdf). That source uses **Fanning**, not Darcy, friction: multiply its f by four. At current reconstructed `ri=0.1538 m`, `ro=0.1598 m`, the Darcy product is **95.9976568340**, not 64. For `Re=100`, the same fluid assumptions and L=0.15 m give **Δp=0.147463721 Pa**, versus 0.098311547 Pa with the circular approximation. This is only a low-Re limiting-case correction.

For fully developed constant-property thermal flow, define `θ_i=Tw_i−Tb`, `θ_o=Tw_o−Tb`, with `Tb` the velocity-weighted bulk temperature and positive q'' directed into the fluid. The exact radial energy equation is:

`(k/r) d/dr[r dT/dr] = ρcp u(r) dTb/dx`

`−k T'(ri)=q''i`, `k T'(ro)=q''o`, `∫ri^ro u(r) r [T(r)−Tb] dr=0`

Independent high-precision integration gives, at the same radius ratio:

`[θ_i, θ_o]^T = (Dh/k) [[0.184694150822405, −0.065515137687461], [−0.063055245158520, 0.186698857554630]] [q''i, q''o]^T`

With `k=0.027`, `q''i=100`, `q''o=20 W/m²`, the wall offsets are **+7.626272146 K and −1.142909940 K**. The outer wall is below bulk temperature while both walls add heat. A positive independent scalar h law cannot reproduce this cross-coupling.

Two checks anchor the calculation: at η=0.5, unilateral-heating Nu values are **6.181014666 and 5.036532966**, agreeing with rounded Table II.D.2 values 6.18102 and 5.03655. As η→1, the matrix approaches diagonal 13/70 and off-diagonal −9/140. Equal wall flux then gives **Nu=140/17**, while one heated/one insulated wall gives **Nu=70/13**. These are different boundary conditions.

Passing either benchmark verifies equations and implementation within its stated assumptions. It does not validate motor cooling, rotating flow, transition, real contacts, or the nacelle reconstruction.

## 5. Ranked implementable improvements and stopping gates

1. **Publish a historical motor unit-cell subcase.** Implement the independently specified rectangular pressure and sensible-heat mixture benchmarks; show expected numbers and convergence. Keep material-table inconsistencies visible. Stop at a verified subcase rather than a fabricated full-motor result.
2. **Correct the face/topology inventory before geometry tuning.** Distinguish winding sectors, actual stator heat-sink channels, gap wall, end turns, supports and solid contacts. Add an explicit source/date/inference label for each. A new fin-bank option needs independent count/area evidence; unknown count remains an input, not a fitted hidden constant.
3. **Add geometry-specific laminar transport and wall coupling.** Rectangular/annular friction and a two-wall response matrix are mathematically testable improvements. Use the already separate developing parallel-plate solver as another limiting case, not as an outer-rotor enhancement model.
4. **Separate source-state replay from autonomous prediction.** Preserve published station p/T/ṁ and weighting limitations. Replay supplied flow only as a boundary-controlled diagnostic; report its difference from a pressure-solved case and never call it prediction of that supplied quantity.
5. **Replace one isotropic winding resistance with explicit directional paths.** Begin with source-derived ideal series/parallel bounds and independent contact/liner layers. Conserve volumetric heat capacity correctly. Missing orientation, void distribution and contact areas prevent an actual X-57 transient claim.
6. **Only then assess turbulent/rotating transport.** [Gnielinski's stationary-annulus work](https://doi.org/10.1080/01457630802528661) addresses diameter ratio and heating boundaries; full equations/ranges still need direct review before implementation. [Kays and Leung's two-wall turbulent-annulus study](https://ntrs.nasa.gov/citations/19630024111) specifically treats asymmetric heating at air-like Pr. Neither supplies an outer-rotor motor correlation. [Outer-cylinder DNS](https://arxiv.org/abs/1604.00673) demonstrates different structures from inner-cylinder rotation, including possible turbulence; linear stability is not a license to assume rotation has no effect.

Do not use inner-rotor Taylor-vortex formulas, unspecified roughness, empirical multipliers chosen to recover a green margin, or low-Re benchmark Nu at the actual Re≈9,000–17,000. A correct benchmark can make the displayed answer less favorable and still represent real engineering progress.

## Reproducibility identity

Run `python docs/research/verify_thermal_subcase_references.py --check` from the repository root. This supplementary research script prints JSON and writes no files. It imports no production ROM modules. It reproduces the rectangular Fourier reference, independent finite-volume convergence, two-wall annular response matrix, dimensional test cases and constituent heat-capacity calculation. Dependencies when checked: NumPy 2.3.5, SciPy 1.17.0 and mpmath 1.3.0 (45 decimal digits for annular integration). All included reference, conservation-identity and convergence checks passed. Its values are frozen independent subcases; they do not automatically inherit later ROM changes.

Numbers from the existing ROM were evaluated at the default geometry and the three `source_pressure_*` presets, without uncertainty multipliers. Snapshot: git `7c17475ea05c27ab30dbcde8263624856527abfc`; `nacelle_thermal.py` SHA256 `5cc830dd5b224738c3797f0c8b593caae1ec4916a39654dfeabefcd0b69e4b23`; `nacelle_geometry.py` SHA256 `1aa07e99841b599918ba93774d23578cb8ef96856de022c196103e0859c44c39`.

Downloaded source PDF hashes: historical motor manuscript `dc2c95a3a5df5e478226e557923a32b75723c03cbd8d68f9d83549b30f209a44`; NASA TN D-1972 `fe335045dfcfdccb9e97dd7148d12b8dc0a7332dd3cf0b118f2fae10510ef18d`; distributor-hosted DuPont document `ddd32f71661ac495062c76f91fa6aa2b3be9772ae0f4e82e9310191bcada5533`. These hashes identify inspected source bytes; no original CAD or experimental datasets were obtained.
