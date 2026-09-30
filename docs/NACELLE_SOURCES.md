# Mod II 局部短舱：来源、构型与重建边界

核查日期：2026-09-30。该演示是原创参数化重建和未标定降阶网络，不是 NASA 原始 CAD、制造图、数字孪生或适航验证。

## 采用的对象

主场景是 **X-57 Mod II 单侧巡航短舱 + 局部机翼安装语境**。前部电机、后部并排且倾斜的双 CMC、上方两个独立低压电子冷气入口、上部电机排热口及底部短舱出口，依据同一时期 Mod II 图和文字重建。局部机翼只为说明安装关系；原 NASA 热论文的 CFD 用的是隔离短舱，不包含机翼。

部件数量不是精度的证明。缺失的尺寸、壁厚、紧固件位置、安装容差、材料和阻力/热接触参数须标为推定；可计算、可导出也不意味着可制造。

## 来源清单

### N1 · 主装配与冷却拓扑

[Cruise Propulsion System Thermal Analysis for NASA’s X-57 “Maxwell” Mod II Configuration](https://ntrs.nasa.gov/api/citations/20230006888/downloads/Borer_Bui_Smith_X-57_thermal_analysis.pdf)

- NTRS：[20230006888](https://ntrs.nasa.gov/citations/20230006888)，2023
- PDF 第 7 页图 5：去外壳后的转子、定子冷却槽、转/定子间隙、安装支架、CMC 连接器、散热翅片与挡板
- PDF 第 8 页图 6：两个 CMC 的高压/低压两面、顶部双“耳”入口和前部电机
- PDF 第 8 页图 7 及同页正文：电机内部与旁通流，电机后混合，上部排热，CMC 高压与旁通，独立低压新鲜空气，底部排气
- PDF 第 3 页表 1：绕组、磁体、FET 结、FPGA/驱动板、CPU/ACDC 板的硬限制和项目裕度线不同。不可拿散热器平均温度冒充 FET 结温，亦不可拿外壳温度直接证明 CPU 板安全
- PDF 第 5 页表 4：最大连续功率下绕组 4196 W、磁体 466 W，每个 CMC 高压侧 679 W；峰值工况分别 5237 W、582 W、810 W；每个低压侧 30 W。磁体热量的一半送向外部流道，另一半送向电机内部流道
- PDF 第 6 页：论文说明缺少短舱空气流量实验数据，未能实验验证该 CFD；本项目更不能借用该论文的图、温度或软件测试通过声明已校准
- NTRS 权利标注：Public / Work of the US Gov. Public Use Permitted。仓库仅保留链接与原创转述，不复制原图或 PDF

### N2 · CMC 重设计的时期边界

[X-57 Cruise Motor Controller (CMC) Presentation](https://ntrs.nasa.gov/api/citations/20230006883/downloads/AIAA%20EATS%20X-57%20CMC%20Presentation%20.pdf#page=4)，2023，第 4 页对比旧控制器与重设计控制器。

[X-57 Traction Power and Command Systems Development](https://ntrs.nasa.gov/api/citations/20240009560/downloads/X-57%20Traction%20Power%20and%20Command%20Sys%20Dev%20ICAS%202024.pdf)，2024，第 12 页图 11、第 14 页关于一体化铝壳/散热器的说明。

两份资料说明控制器经历封装更新。该演示不声称恢复最终 CMC 的未公开内部尺寸、PCB、电路连接器针脚或制造细节。

### N3 · 有年代的尺度锚点

[NASA X-57 Maxwell 概览](https://www.nasa.gov/centers-and-facilities/armstrong/x-57-maxwell/)

公开规格含 14 英寸巡航电机直径（355.6 mm）、5 英尺螺旋桨直径（1524 mm）。这些是历史公开尺度锚点；不能据此推导所有最终内部几何。叶片气动截面、扭转分布及真实性能未恢复，演示叶片为外形示意。

### N4 · 本次明确不混用的两组资料

- [NASA 原生 X-57 模型](https://science.nasa.gov/3d-resources/x-57-maxwell/)：X-57.vsp3 含高展弦比翼、增升推进器和翼尖巡航装置。它是另一构型语境，**未用于本场景外形，更不存在从 Mod IV 翼尖连续放大进入 Mod II 内部的混合展示**
- [HeaTSSPy 报告](https://ntrs.nasa.gov/api/citations/20230011420/downloads/TM-20230011420.pdf)：表 2 的 388.6 × 179.5 mm、43 翅片参数明确是较早版本散热器。原有 CAD 热设计页保留为独立数值基准，**不是本次双 CMC 的最终实物尺寸**
- [2017 冷却研究](https://ntrs.nasa.gov/api/citations/20170007957/downloads/20170007957.pdf)：60 翅片等早期尺寸与 43 翅片基准及最终包装属于不同阶段，未拼接为一个伪精确装配

## 三类证据必须分开

| 分类 | 此次可表达的内容 | 不能由此声称的内容 |
| --- | --- | --- |
| 来源事实 | 构型、流路关系、公开损耗、不同器件温度边界 | 全部几何尺寸都来自 NASA |
| 重建/设计假设 | 未公开长度、角度、壁厚、流道近似、材质、局部阻力、接触热阻 | OEM 精度、可制造容差、真实飞机裕度 |
| 本模型计算 | 输入指纹对应的体积/质量、流量分配、平均节点温度、守恒残差与敏感性 | CFD 场、风洞验证、飞行性能、适航符合性 |

所有箭头是网络拓扑示意。固体上的温度色代表其关联降阶节点；未求解体素/表面连续温度场。视觉剖切不等于重新生成并验证一个切削零件。机翼和推进器外形只提供装配语境，不参与气动载荷、推力或结构有限元。
