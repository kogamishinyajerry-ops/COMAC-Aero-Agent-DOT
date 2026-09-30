# Historical motor unit-cell/material benchmark

## Applicability comes first

This is a **dated component benchmark** based on [Chin, Tallerico and Smith, *X-57 Mod 2 Motor Thermal Analysis*, NTRS record 20190032520](https://ntrs.nasa.gov/api/citations/20190032520/downloads/20190032520.pdf). The archive date is 2019; this does not establish the final-2023 hardware configuration. The new module does **not** replace any current nacelle geometry, contact resistance, loss split or convection coefficient.

The useful question is: **what hydraulic, area, convection and material scales follow from a publicly specified narrow passage, and which assumptions prevent interpreting them as a complete motor?** No temperature target, measured calibration or actual channel count is used.

The source's p4 Eq(1) specifies a 2 × 17 mm rectangular passage, 105 mm long. Figure 4 on p5 shows a dense fin pack beneath the windings. The current ROM's 24 broad winding-sector gaps have a 9.425 mm hydraulic diameter and are not established as the same feature. The paper does not supply a trustworthy total fin count, fin thickness, heated-face inventory, contact geometry or solid volume. Consequently this benchmark does not predict a full-motor transient or winding hotspot.

## Reproduce and use

Only Python's standard library is required:

```bash
python3 scripts/generate_historical_motor.py
python3 scripts/generate_historical_motor.py --check
python3 -m unittest discover -s tests -p test_historical_motor.py -v
```

`aerolab.historical_motor.historical_motor_benchmark()` returns the deterministic JSON-ready report saved as `examples/historical_motor.json` (under 100 KB). Main sections:

- `geometry`: source dimensions; derived wetted and hypothetical heated areas
- `air_assumptions`, `fin_assumptions`: visibly separate unsourced choices
- `velocity_sweep`: pressure/convection, three heating boundaries and three fin thicknesses
- `materials`: constituent conservation, printed-table comparison and liner units
- `matched_condition_comparison`: equal-boundary comparison with the current broad slot
- `verification`: equation balance and independent quadrature diagnostics

The report embeds its module SHA-256, current comparison-geometry SHA-256 and source-station-data SHA-256. It marks experimental validation, calibration and final-2023 modification false. It makes no pass/fail claim about aircraft limits.

## Geometry and heat-transfer area

With full dimensions `a=0.002 m`, `b=0.017 m`, `L=0.105 m`:

```text
flow area             A = a b           = 0.000034 m²
wetted perimeter      P = 2(a+b)        = 0.038 m
hydraulic diameter   Dh = 4A/P          = 0.003578947368 m
aspect ratio            = a/b          = 0.1176471
length ratio            = L/Dh         = 29.3382353
all wetted area         = P L          = 0.003990 m²
```

The rounded printed Dh is 0.00358 m. Hydraulic perimeter is not automatically heated perimeter. The following are **three alternative idealized boundary conditions**, never recovered source face assignments:

| Heating assumption | Heated area per unit cell |
|---|---:|
| Two 17 mm side walls | `2bL = 0.003570 m²` |
| Two side walls plus 2 mm base | `(2b+a)L = 0.003780 m²` |
| All four walls | `PL = 0.003990 m²` |

All use the source's full rectangular wetted perimeter for hydraulic diameter. The fluid passage's actual top-wall construction is not reconstructed from the image.

## Transport equations, assumptions and sweep

Frozen representative near-room-temperature air constants are `ρ=1.225 kg/m³`, `μ=1.7894e−5 Pa s`, `k=0.0257 W/(m K)`, `cp=1006 J/(kg K)`. They are engineering assumptions, not recovered AirVolt conditions or a temperature-dependent property model. The paper estimates 12–40 m/s and Re≈3,000–10,000; air properties were not tabulated. Its viscosity symbols in Eqs(2)–(3) are dimensionally inconsistent, so the implementation explicitly uses **dynamic** viscosity μ:

```text
Re = ρ U Dh / μ                    Pr = μ cp / k
f_D = (0.79 ln(Re) − 1.64)^−2
Nu = [(f_D/8)(Re−1000)Pr] /
     [1 + 12.7 sqrt(f_D/8)(Pr^(2/3)−1)]
h = Nu k / Dh
Δp_friction = f_D (L/Dh) ρ U² / 2
m_dot = ρ U A                     C_air = m_dot cp
```

The NASA paper supplies the Gnielinski expression; the smooth-tube Darcy closure is also explicitly recorded in [DOE report DE-EE0009380, Eq(40)](https://www.osti.gov/servlets/purl/2375525). The friction factor is Darcy, not Fanning. These equations are a **formula benchmark using equivalent hydraulic diameter**, not validation for the real high-aspect-ratio/curved passages. The implemented nominal range check is Re=3,000–5,000,000 and Pr=0.5–2,000; satisfying those scalar bounds does not validate the geometry or entry length. Values below Re=4,000 remain transition-sensitive. No artificial transition interpolation is supplied.

| Imposed bulk speed (m/s) | Re | h (W/m²K) | Friction-only Δp (Pa) |
|---:|---:|---:|---:|
| 12 | 2940.1 | 70.22 | 118.70 |
| 16 | 3920.2 | 94.99 | 191.88 |
| 20 | 4900.2 | 117.22 | 279.34 |
| 24 | 5880.2 | 137.81 | 380.34 |
| 30 | 7350.3 | 166.58 | 556.07 |
| 40 | 9800.4 | 210.74 | 910.23 |

**The 12 m/s result is retained as flagged extrapolation below Re=3,000.** It is not silently presented as validated turbulence. The 16 m/s point also remains transition-sensitive. Pressure excludes contraction, entrance/exit, turning, roughness and rotor effects. No minor-loss coefficient is fitted. Length-to-Dh alone cannot establish fully developed flow. These are imposed local bulk speeds, not flight airspeed or a solved nacelle pressure/flow operating point.

## Fin conduction and finite air capacity

For a two-sided thin straight fin with constant k and h, an isothermal base and insulated tip, the one-dimensional conduction equation has the solution:

```text
d²θ/dy² − m²θ = 0,   m² = 2h/(k t)
θ(0)=θ_base,         dθ/dy(H)=0
θ(y)/θ_base = cosh[m(H−y)] / cosh(mH)
η_fin = tanh(mH)/(mH)
A_effective = aL + η_fin (2HL)
UA = h A_effective
```

Here `k=201 W/(m K)` follows the source's aluminum assumption. Interpreting the 17 mm dimension as fin height is explicit. Fin thicknesses **0.5, 1 and 2 mm are unfitted sensitivity scenarios**, since no source thickness was recovered. An interior cell receives one complete shared fin's two side faces, equivalent to one face from each adjacent fin; no total motor fin count is implied. Base heating is included, top/tips/axial end-face heating omitted.

At 24 m/s, these thicknesses give η=0.79922, 0.88595 and 0.93880 and per-cell UA=0.42215, 0.46482 and 0.49082 W/K. The open flow area stays fixed: this is **not a fixed-envelope design or mass/pressure optimization**. A thickness change in real hardware can change blockage, pitch, count, area and mass. Contacts, spreading, curvature, axial conduction, winding-to-fin resistance and inter-fin radiation are not resolved. Cross-thickness Biot numbers are disclosed; their small values support only that particular thin-fin simplification.

The fluid warms along the channel. For a constant wall or fin-base temperature and constant effective UA:

```text
C_air dT/d(x/L) = UA (T_base − T)
NTU = UA/C_air
Q = C_air (T_base−T_in) [1 − exp(−NTU)]
T_out = T_in + Q/C_air
G_inlet = Q/(T_base−T_in) = C_air [1 − exp(−NTU)]
```

The default inlet/base pair 25/26°C is just a **+1 K normalization**, not an aircraft temperature estimate. `G_inlet` is smaller than UA because finite-capacity air warms. For the 1 mm fin case at 24 m/s, UA=0.46482 W/K but `G_inlet=0.37219 W/K`. A separate midpoint integral of the local convection rate checks the exponential solution. Energy closure is `Q=C_air(T_out−T_in)`; the largest default residual is below 3e−15 W, and 256-interval independent quadrature differs by under 2.1e−7 relative. These verify the stated one-dimensional equations, not a complete conjugate motor model.

## Material arithmetic and uncertainty

The source's Table 1 and Eqs(6)–(7) allow constituent conservation to be checked. Copper `(ρ,cp,k)=(8960,385,400)` and epoxy `(1225,1000,1)` in SI, with copper volume fraction φ=0.45, give:

```text
ρ_mix = φρ_Cu + (1−φ)ρ_epoxy = 4705.75 kg/m³
(ρcp)_mix = φρ_Cu cp_Cu + (1−φ)ρ_epoxy cp_epoxy
          = 2,226,070 J/(m³ K)
cp_mix = (ρcp)_mix / ρ_mix = 473.0531796 J/(kg K)
k_series = 1/[φ/k_Cu + (1−φ)/k_epoxy] = 1.8144704 W/(m K)
k_parallel = φk_Cu + (1−φ)k_epoxy = 180.55 W/(m K)
```

The 45% volume fraction is inferred from the printed density and parallel conductivity, not a measured packing fraction. Series/parallel conduction are idealized directional mixture limits. They do not capture wires, voids, interfaces or manufacturing variation.

The printed bulk cp=723.25 equals the volume-fraction average `0.45×385 + 0.55×1000`. Specific heat per unit mass requires mass weighting. Printed density times printed cp instead gives **3,403,433.6875 J/(m³ K)**:

- Printed implied volumetric heat capacity is **52.8898% higher** than constituent-consistent capacity
- Constituent-consistent capacity is **34.5934% lower** than the printed implied value

The denominators differ; those percentages must not be interchanged. This is an arithmetic consistency issue in the printed table, **not proof that the actual NASA COMSOL material input was wrong**. No actual winding volume, thermal mass or fitted transient is inferred.

### Slot-liner unit check

The paper prints k=139 W/(m K) for a 0.25 mm liner. A [DuPont-authored historical Nomex 410 datasheet, p6 Table IV, preserved by a distributor](https://pronatindustries.com/wp-content/uploads/2014/07/Nomex_Tape410_technicaldatasheet.pdf#page=6) specifies **139 mW/(m K)=0.139 W/(m K)** for 0.25 mm at 150°C. Its table and footnote were visually inspected. Source bytes SHA-256: `ddd32f71661ac495062c76f91fa6aa2b3be9772ae0f4e82e9310191bcada5533`. The current official manufacturer link redirected during verification; the linked copy is manufacturer-authored but distributor-hosted, not a current manufacturer endpoint.

The area-normalized conduction resistance `R''=t/k` is 1.79856e−6 m²K/W using the printed value, or 0.00179856 m²K/W using the datasheet value: a factor of 1,000. This supports a possible milli-unit transcription issue. **Actual liner grade, operating-temperature conductivity and original solver inputs are unverified.** No silent material replacement is made. Contact and impregnation can change assembled thermal resistance.

## A matched comparison with the broad current ROM slot

This comparison freezes the following for both shapes:

- Identical air constants and prescribed speed at each sweep point
- Identical axial length **105 mm**, overriding the broad ROM's native 133 mm for this comparison only
- Identical total open area **0.009697524890333 m²**
- Two isothermal heated side walls, +1 K wall-to-inlet boundary, with no fin correction on either shape

The total area is the initial-climb **flux-equivalent area hypothesis** from the [source-station audit](NACELLE_SOURCE_AUDIT.md), derived from published mean values. It is not original CAD area. Dividing it by 34 mm² gives **285.2213203 equivalent cells**. This fractional diagnostic is never rounded into a channel count, never treated as real geometry, and never adjusted to meet a desired temperature. Broad-slot geometry is normalized to the same total open area without claiming it contains a new physical integer slot count. Comparison mass flow is 0.285107 kg/s at 24 m/s under the assumed properties; it is not the published station mass flow.

At **24 m/s**:

| Quantity | Historical narrow geometry hypothesis | Current broad slot, matched boundary |
|---|---:|---:|
| Dh (mm) | 3.57895 | 9.42485 |
| Two-side heated area (m²) | 1.01824 | 0.390759 |
| h (W/m²K) | 137.812 | 114.875 |
| UA (W/K) | 140.326 | 44.8885 |
| Finite-air-capacity inlet conductance (W/K) | 110.974 | 41.5521 |
| Friction-only Δp (Pa) | 380.341 | 109.851 |

The hypothetical narrow geometry supplies **3.126× UA while demanding 3.462× friction pressure** at equal flow and length. Much of the conductance difference comes from surface area per open flow area, not h alone. This is a useful geometry-scale explanation, **not evidence of a feasible retrofit or recovered motor topology**. At the same available pressure the velocities would differ; the nacelle network would need to be re-solved with confirmed geometry. No winding temperature can be concluded from this table.

## Independent verification and remaining work

The focused test suite includes independently rederived geometry/units; separate numerical Gnielinski sentinels; pressure-length scaling; mass/energy mixture rules; domain warnings; input rejection; and frozen-evidence regeneration. It also solves the fin ODE using independent cell-centered finite volumes and verifies second-order convergence on 16/32/64/128/256 cells. An independent RK4 solution of the air-energy ODE checks heated, cooled and zero-temperature-difference cases. These are stronger than checking only that a function reproduces its own output, but still constitute **verification of assumptions/equations**, not physical validation.

Unresolved prerequisites for a real motor submodel are actual fin dimensions/count/topology, heated-wall allocation, pressure and temperature fields, material packing/liner specification, contacts, loss deposition and transient solid volumes. Laminar rectangular and unequal-wall annular field benchmarks are separate work; they must not be substituted for validation of these transitional/turbulent passages. See the [physics research audit](research/NACELLE_THERMAL_PHYSICS_AUDIT_2026-09-30.md) for the evidence boundary and proposed next measurements.
