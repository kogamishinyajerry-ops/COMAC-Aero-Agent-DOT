# 独立数值验证：双壁不同热流的层流平行板流道

这个子模型真正计算横截面速度与沿程温度场，并分别核查守恒、网格收敛和独立解析解。它证明的是理想方程的数值实现，不是 X-57 电机的物理验证。**没有修改、拟合或补偿短舱 ROM 的换热系数。** 非对称加热的弱热壁可以低于混合平均空气温度，说明独立的 `Tw = Tb + q/h` 壁面模型可能遗漏横向热耦合。

## Reproduce and inspect

Python 3.10+, standard library only:

```bash
python -m unittest discover -s tests -p test_duct_finite_volume.py -v
python scripts/generate_duct_verification.py
python scripts/generate_duct_verification.py --check
```

```python
from aerolab.duct_finite_volume import solve_duct
equal = solve_duct()
unequal = solve_duct({"left_heat_flux_w_m2": 20, "right_heat_flux_w_m2": 200})
```

The checked `examples/duct_verification.json` is below 100 kB. It contains two spatially sampled demonstration cases, exact references, independent developing-flow comparisons, refinement sequences and executable acceptance gates. No external simulation service, mesh file, package installation or paid API is needed. The generator's full-file hash and the solver's import-time full-file hash bind the artifact to the exact code; canonical input hashes and all grid/settings/physical inputs are included. `--check` requires matching identities and checks floating results to relative `1e-10`, absolute `1e-9`. Cross-platform bit-for-bit equality is not promised.

## Boundary conditions and scope

- Infinite parallel plates, separation `2b`, reporting span `W`, heated length `L`. The span scales mass and heat flow, but **does not introduce sidewalls**
- Stationary no-slip walls and a prescribed signed mean velocity `U`. The hydrodynamically developed velocity is solved numerically, not injected as a parabola
- Constant density, viscosity, conductivity and heat capacity; incompressible laminar flow
- Independent constant inward heat fluxes `q_left` and `q_right`. Negative values extract heat. Equal fluxes are only one case; the full cross-section is solved without thermal symmetry
- The default inlet temperature is uniform. The optional `fully_developed` inlet imposes the discrete developed shape with the supplied inlet temperature interpreted as its mass-weighted bulk temperature
- No fluid axial conduction, transverse velocity, buoyancy, viscous dissipation, radiation, rotation, turbulence, compressibility or variable properties
- Solid temperatures follow exact **local 1D** through-thickness conduction, with interface continuity and the prescribed flux. This is a one-way reconstruction: under prescribed flux, changing wall conductivity changes the solid outer temperature but not the fluid solution. No axial/spreading/contact resistance is solved. Do not describe this as a general multidimensional conjugate CFD solver

The synthetic defaults are `2b=4 mm`, `W=80 mm`, `L=200 mm`, `U=1 m/s`, `Tin=25 C`; `rho=1.2 kg/m³`, `mu=1.8e-5 Pa s`, `k=0.026 W/(m K)`, `cp=1005 J/(kg K)`; both fluxes `200 W/m²`; solid thickness `2 mm`, conductivity `167 W/(m K)`. They are **not X-57 dimensions, calibrated properties or flight heat loads**.

Nonzero flows require `Re_Dh <= 2000`, `Pe_Dh >= 50`, `Pe_L >= 50`. These are declared screening restrictions for this idealization, not accuracy guarantees or universal transition thresholds. Constant properties are still an assumption over the resulting temperature range. The singular heated-inlet corner and the neglected axial conduction there are not physically resolved.

## Equations and conservative finite volumes

With `Dh=4b`, `eta=y/b` in `[-1,1]` and the pressure-drop magnitude per length `G`:

```
mu * d²u/dy² = -G,              u(-b)=u(+b)=0
rho cp u * dT/ds = k * d²T/dy²
k dT/dy(-b) = -q_left,          k dT/dy(+b) = q_right
Tb = integral(u T dy) / integral(u dy)
m_dot = rho U (2b W)
```

Here `u` in the differential equations is the downstream speed. The flow direction is absorbed into the downstream coordinate `s`; physical `x=s` for positive `U` and `x=L-s` for negative `U`. Returned velocity samples carry their physical axial sign. The returned pressure drop is `p(x=0)-p(x=L)` and reverses sign with `U`.

Momentum uses centred cell finite volumes and half-cell no-slip boundary distances. The linear tridiagonal system is solved by Thomas elimination and then scaled to the requested mean velocity. The inferred `G` and the face wall shear satisfy the momentum balance. Darcy friction is `f_D=2 G Dh/(rho U²)`; it is **four times** the Fanning definition.

For nonzero wall heat flux define `q_ref=max(|q_left|,|q_right|)`, `theta=k(T-Tin)/(q_ref b)`, `zeta=k s/(rho cp |U| b²)` and `v=u/|U|`. The thermal equation is `v theta_zeta=theta_eta_eta`. Each axial step uses backward Euler advection and centred transverse diffusive face fluxes. The uniform transverse cell width is `h=2/N`; axial faces are `s_j=L(j/Nx)^stretch`, default stretch 2. This concentrates cells near the inlet without changing the conservative balance. Axial marching is first order; transverse discretization is second order.

Adding the cell equations cancels every internal diffusive face. Consequently:

```
|m_dot| cp [Tb(s)-Tb(0)] = (q_left+q_right) W s
```

There is no energy-balance correction after the solve. Diagnostics expose the actual global residual, maximum cell-equation residual, maximum bulk-energy defect along the march and momentum residual. Direct linear solves do not need iterative convergence tolerances; the declared residual gates decide the returned `converged` flag.

## Independent exact limits, including cross-wall coupling

The continuum velocity and friction are:

```
u/U = (3/2)(1-eta²),            f_D Re_Dh = 96
```

Let `a=(q_left+q_right)/(2 q_ref)` and `d=(q_right-q_left)/(2 q_ref)`. Direct integration, followed by the mass-weighted zero-mean condition, gives the fully developed profile:

```
theta - theta_bulk = a [3 eta²/4 - eta⁴/8 - 39/280] + d eta
```

Its wall values give a coupled relation:

```
(k/Dh)(Tw_left - Tb)  = (13/70) q_left  - (9/140) q_right
(k/Dh)(Tw_right - Tb) = (13/70) q_right - (9/140) q_left
```

Therefore equal positive fluxes give `Nu_Dh=140/17=8.2352941176`; one heated wall with the other adiabatic gives `Nu_Dh=70/13=5.3846153846`. A positive weak-wall flux with `q_weak/q_strong < 9/26` produces a **negative wall-to-bulk temperature difference** in the developed limit. It does not reverse the prescribed wall heat flux: the local adjacent fluid is cooler than that wall while the mixed bulk is heated more strongly by the opposite wall. A signed local `q Dh/[k(Tw-Tb)]` can therefore be negative. It is reported, not clipped, and must not be interpreted as an independent positive Newton-cooling coefficient.

The synthetic developing 20/200 W/m² case returns, at 64×400 cells, approximately bulk **34.1211 C**, weak wall **31.4259 C**, strong wall **45.0345 C**. Both wall heat inputs remain positive and total removal is **3.52 W**. This is a mechanism demonstration, not a numerical estimate of either motor wall.

## Independent developing-flow benchmark

The evidence generator solves the continuum Sturm–Liouville problem separately from the FV module:

```
psi'' + (3/2) lambda (1-eta²) psi = 0
psi'(1)=0
even modes: psi(0)=1, psi'(0)=0
odd modes:  psi(0)=0, psi'(0)=1
```

The zero constant mode is excluded. A 180-term power series, 90-decimal-digit arithmetic, sign-bracketed roots and 180 bisections determine 12 modes of each parity. Weighted norms are integrated by exact polynomial-product integration, not the FV stencil. If `A_n=psi_n(1)²/[lambda_n integral_0^1 v psi_n² d eta]`, the even wall response is `17/35 - sum(A_n exp(-lambda_n zeta))`; the odd response is `1 - sum(A_n exp(-lambda_n zeta))`. Their symmetric/antisymmetric combination gives both wall temperatures. The first even and odd eigenvalues are approximately `12.25353182296` and `3.414446204916` in this specific zeta convention.

This is an independently implemented analytical-series reference, **not external CFD or an experiment**. No FV temperature, numerical velocity profile or fitted constant enters its evaluation. The evidence compares both equal and 0.1:1 wall fluxes at `zeta=0.02, 0.05, 0.1, 0.2, 1.0`. Comparing 8 with 12 modes checks truncation sensitivity over those points; it is not a rigorous all-zeta error bound and the reference API rejects `zeta<0.02`.

Checked results:

| Quantity | Numerical evidence | Independent target |
|---|---:|---:|
| Darcy f Re at 128 cells | 95.98828268 | 96 |
| Equal-flux Nu at 128 cells | 8.23564880 | 140/17 |
| Transverse Nu order, finest refinement | 1.99847 | second order |
| Axial order from successive differences | 0.99897 | first order |
| Maximum developed unequal-wall offset error | 2.10e-5 | exact polynomial |
| Maximum developing wall-offset error, 128×800 | 1.58e-4 | independent spectral solution |
| Maximum 8-versus-12-mode change | 5.41e-10 | disclosed truncation check |

Offsets in the last three rows are normalized by `q_ref b/k`. Refinement results do not imply those errors hold for arbitrary inputs. The executable artifact contains exact values and thresholds, including conservative signed heating/cooling cases. Numerical verification and aircraft physical validation are separate questions.

## API, zero flow and bounds

`solve_duct(mapping)` returns `provenance`, `status`, `hydraulics`, `thermal`, `diagnostics`. Fields useful for a visual:

- `thermal.axial_samples[]`: actual axial-face index, downstream `s`, physical `x`, `zeta`, bulk temperature, left/right wall and outer-solid temperatures, plus sampled `fluid_c[]`
- `thermal.sample_eta[]`: transverse fluid-cell locations matching every sampled fluid array
- `hydraulics.velocity_samples[]`: locations and signed computed velocities
- `thermal.outlet_profile[]` and `outlet_solid_profile.{left,right}[]`: final resolved fluid samples and explicit local solid reconstruction
- `provenance.case`, `grid`, `source_sha256`, `input_sha256`: reproducible inputs/identity, full mesh dimensions and scheme orders

Both flow directions and signed wall fluxes are supported. At zero velocity and nonzero net heat, the model has no steady energy balance: `no_steady_state_zero_flow`, null temperatures and `converged=false`. Balanced opposite nonzero fluxes at zero velocity admit transverse conduction but leave the absolute temperature undetermined without an additional datum: `undetermined_zero_flow_temperature`. Only zero flow with both wall fluxes zero returns the selected uniform isothermal datum. No epsilon flow or arbitrary temperature cap is inserted. At a uniform inlet, local Nu and the reconstructed solid outer temperature are null because the heated-inlet corner is singular.

Inputs are finite bounded scalars, validated integer mesh/sample counts and explicit inlet choices; booleans, unknown fields and non-finite values are rejected. Any computed temperature at or below **absolute zero, -273.15 C**, also raises `ValueError`: the case is inadmissible and no temperature is clipped. This guard checks **every fluid cell, both fluid-wall interfaces and both solid outer faces at every marched axial state**, not just returned samples. Because local solid conduction is linear through thickness, its endpoints bound all solid temperatures. The fully developed inlet is checked too; the uniform inlet's unresolved wall corner is excluded from solid reconstruction. Valid results report the minimum checked temperature/location and the number of checked axial states. This thermodynamic guard does not establish constant-property accuracy or material-temperature validity above absolute zero.

Bounds are 4–256 transverse cells, 4–8192 axial cells, at most 1,000,000 marched cells, at most 65 samples per axis. Work is `O(Nx N)` and samples are bounded; no hidden unbounded nonlinear iteration occurs. The analytical reference has a fixed eigenvalue search bound as well.

## Checked primary literature and relevance to the nacelle

1. [Cess & Shaffer, 1959, Heat transfer to laminar flow between parallel plates with a prescribed wall heat flux](https://link.springer.com/article/10.1007/BF00411758), Applied Scientific Research A8, 339–344. Publisher abstract and bibliographic record checked 2026-09-30; it describes the symmetric heat-flux eigenfunction problem. The paywalled full text/tables were not obtained or copied. Our series reference is derived from the equations above
2. [Lundberg, Reynolds & Kays, NASA TN D-1972, 1963](https://ntrs.nasa.gov/citations/19630010444). Primary report checked, including printed pp. 19–20 (Fanning friction and plane-gap limit) and p. 35, Table II.D.2 (one-wall forcing and negative cross-wall response). The plane limit has 0.185714 and -0.0642857 response coefficients, consistent with 13/70 and -9/140. NTRS marks this report public-use permitted; only a citation is included here
3. [Inman, Laminar slip flow in a flat duct or a round tube with uniform wall heat transfer](https://ntrs.nasa.gov/api/citations/19660009101/downloads/19660009101.pdf), NASA primary archive, checked 2026-09-30. It documents eigenfunction solutions and equal/one-wall heating, including the continuum limit. Slip effects are not included in this implementation

The existing [nacelle ROM](NACELLE_MODEL.md) uses circular-equivalent convection and separate patch offsets from mixed bulk air. Its annular gap has unequal heat fluxes and rotating/possibly turbulent flow. This verified planar subcase exposes why wall-to-bulk coupling deserves investigation; it **does not supply an applicable motor correction factor**, validate the ROM's gap/slot flow partition, reproduce NASA's geometry, or close its full-load temperature discrepancy. The next physical-validation steps remain geometry-appropriate stationary-annulus comparisons, rotating/turbulent or measured reference cases with matched boundary conditions, and documented uncertainty.
