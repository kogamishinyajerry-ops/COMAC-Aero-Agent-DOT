# Independent scientific review / 独立科学复核

## Scope and provenance

The review covered the preregistered plan before execution, the frozen driver, native pressure/velocity/flux fields, residual logs, independent transverse Poisson stencil, cell-average reference, directional arithmetic, budget accounting and both final figures. No solver settings or physical parameters were changed by the reviewer.

- The frozen plan and driver match `evidence/run_lock.json`.
- All 26 original compact-file hashes and 220 original full-source hashes still pass. All 221 new retained-source hashes were independently checked, including the failed supplementary attempt.
- Native section-pressure fits reproduce the seven primary comparison cases (five new cases plus B and F). The T2 gradient independently evaluates to 235.92602791151126 Pa/m, within 3e-13 Pa/m of its reported value.
- The independent half-cell-wall Poisson operator reproduces the reported discrete reference; exact integrated continuum profiles retain a 3 m/s mean. Actual pressure-corrected phi is used for conservation, rather than cell-velocity section means.
- Both figures were visually inspected. The revised log-axis labels are readable; velocity panels explicitly use separate symmetric color scales. Only accepted primary cases appear in accepted comparisons.

## Supported findings

1. The original all-direction pressure-grid change remains **1.120839438% > 1%: FAILED**. This study cannot retroactively pass it.
2. All five new primary cases meet the frozen execution checks. Transverse refinement contributes 98.121619% of the sum of separate absolute axial/transverse changes; interaction is 1.048429% of the combined B-to-F change. This supports transverse *mesh sensitivity*, including the changing sampled inlet representation, not exclusive attribution to interior viscous truncation.
3. The fixed-axial T-to-T2 doubling changes the interior gradient by 0.278450327%. T2's fully developed continuum-target pressure bias is -0.0889634%; the last transverse three-level observed order is 2.00555. These are separate directional results, not the original all-direction gate, a GCI or a physical uncertainty bound.
4. The hypothesis that the fully developed transverse operator alone explains at least 90% of the pressure bias fails. The remaining fractions are 34.163485% at B and 32.816682% at T. Inlet, end, axial and pressure-velocity-coupling effects are not causally separated by the accepted runs.

## Failures and remaining cautions

- The discrete-developed-inlet supplementary case reaches the fixed 1500-iteration limit without satisfying the fixed 1e-7 residual requirement: final initial residuals are Uy=1.587092e-7 and Uz=1.780511e-7. It remains **failed and unaccepted**. Its saved provisional pressure is consistent with an inlet influence, but cannot establish an accepted causal conclusion. It is excluded from accepted ladders, orders and plots; no threshold relaxation or rerun occurred.
- The B pressure-window spread is 0.265847%, exceeding the preregistered 0.1% reporting limit. Pressure stations matter even though all completed-case execution checks pass.
- T2 has near-inlet oscillations in the numerical local pressure gradient. Independent native-pressure differentiation gives 228.341–240.571 Pa/m over 0.05<x/L<0.25, compared with 235.879–235.950 Pa/m in the primary 0.25<x/L<0.75 window. Adjacent-section differences confirm the entrance pattern; it is not a plotting artifact. Its precise numerical/BC/coupling cause is unresolved. An accepted interior fit is not evidence of globally smooth pressure.
- Five converged subprocesses total 1276.945487 s. The failed supplement's exact subprocess timer was not persisted; its solver log reports integer ClockTime=57 s. Charging its entire preallocated 1200 s gives a conservative aggregate bound of 2476.945487 s, below 2700 s, without inventing a precise total. The planned study is not entirely successful.

No blocker remains to delivering this explicitly qualified local diagnostic package after the final manifest is refreshed and audited. The remaining failures prevent an all-green validation claim or a closed inlet-causality claim. No new thermal, conjugate, experimental, device-hotspot or aircraft validation is established.

## 中文结论

复核确认：原始1.120839438%大于1%的全向网格门槛仍为失败，旧证据未改变。五个新增主算例通过执行检查，横截面加密占独立方向变化绝对值之和的98.121619%，但这同时包含入口离散表示的变化，不能等同于“纯横向黏性算子解释了全部误差”。算子单独解释90%误差的假设未通过，B和T仍分别有34.16%和32.82%的偏差尚未分离。

固定轴向网格的最后一次横向2倍加密变化为0.278450327%，只属于本次定向证据。入口隔离补充算例在1500次迭代时仍超出原定残差门槛，保持失败，不进入已接受的图表或因果结论。B的压力窗口敏感度超过报告限值；T2入口附近的局部压力梯度振荡也由原生场复核确认，尚需解释。守恒和内部拟合通过不代表整个压力场已充分验证。

两张图均来自保留的真实求解场。保守求解时间上界2476.945487秒低于2700秒；失败算例的精确子进程计时缺失已明确披露。此包可作为有明确边界的局部数值诊断成果交付，不构成全部验证通过、入口因果闭环、共轭传热或真实飞机适用性证明。
