# COMAC-Aero-Agent-DOT

公开来源的航空工程演示：从冻结需求到真实原生助手工具闭环，再到独立留出复核。

> 个人研究与教学项目，不是官方飞机设计、原厂实现、适航声明或运行控制系统。仓库名称不代表任何组织背书。

## 从一条路线开始

首次使用请读 [START_HERE.md](START_HERE.md)。本地应用仅需 Python 3.10+ 和浏览器，无第三方 Python/Node 运行依赖、模型下载、API 密钥或私有输入。

在完整工程根目录运行：

```sh
python -m aerolab serve
```

打开 **http://127.0.0.1:8765/agent**，依次查看：**需求 → 失败基线 → 实际工具动作 → 设计迭代 → 复核结果/CAD → 独立留出**。三分钟讲解词见 [演示说明](docs/ENGINEERING_DEMO_RUNBOOK.md)。系统使用 `python3` 时替换 `python`；Windows 可用 `py -3`。服务仅监听本机，Ctrl+C 停止。

当前统一展示工作分支为 `feat/unified-native-agent-demo`；发布与 CI 状态以最终交付提交的实际记录为准。本文不声称该分支已发布或新展示流程已通过远端 CI，也不沿用旧 PR 的测试作为本次验收。

## 这里的 Agent 是什么

**原生助手已经实际执行了工程工具闭环；网页现在回放它的冻结证据。** 执行时，助手检查候选、调用单个 PDE 工具、拒绝失败方案、改选几何、细化网格，并生成和回读真实 STEP/STL。工具适配器不包含自动搜索或选型策略，也不是包装成助手的固定扫参脚本。

本地应用自身没有在线模型运行时；点击网页不会启动新一轮实时自主推理。记录的执行没有外部模型 API 调用，模型的具体身份未验证。无 API 调用和执行期无人工介入属于执行声明，不是独立身份或访问证明。重放、保存证据审计、重新求解以及新的原生助手试验是不同操作。

L3 指工程应用闭环，L4 指迁移与共享目标。这些是项目组织方式，不是航空安全、适航或自主运行认证等级。

## 已有的真实执行证据

| 冻结任务 | 实际选择与结果 | 工具与复核 |
|---|---|---|
| 开发：50 W、85°C、30 g、25/18 Pa，两工况 | 拒绝 37.783584 g 的 16 × 0.86 mm；改为 16 × 0.60 mm，26.36064 g；三网格最差 77.356556°C | 7 次实际 PDE、1 次 CAD、11 个工程工具动作；每工况数值关卡及 CAD 检查通过 |
| 独立留出：36 W、80°C、25 g、17/11 Pa，四工况 | 拒绝开发选型的 26.36064 g；改为 12 × 0.60 mm，19.77048 g；三网格最差 75.661059°C | 13 次实际 PDE、1 次 CAD、17 个工程工具动作；独立评分 23 项 PASS |

两任务均固定入口 25°C，封闭条件为第一个内部通道密封。所有通过结论均受冻结部件模型和适用范围约束，不是物理或飞机级验证。

- [试验协议、执行方式与审计边界](research/native_agent_trial/README.md)
- [开发结果及失败候选](research/native_agent_trial/DEVELOPMENT_RESULT.md)
- [留出执行结果](research/native_agent_trial/HELDOUT_RESULT.md)
- [独立评分报告](research/native_agent_trial/HELDOUT_EVALUATION.md)与[23 项机器可读检查](research/native_agent_trial/heldout_independent_grade.json)
- [可离线打开的完整过程报告与 CAD](research/native_agent_trial/report/native-agent-evidence.html)

**L4 证据边界：** 留出题在工具冻结后独立释放，但执行者已熟悉同一九候选几何家族。25 g 质量上限只留下一个质量合格候选，因此主要检验变化的约束处理、实际计算、复核和如实报告，不是困难组合优化、陌生任务族或广泛泛化证明。共享文件系统的隔离依靠协议与指令，并非强制访问隔离；独立参考重算也使用相同物理实现。模型级泛化与独立物理验证仍待完成。

## 不改变的失败与工程边界

原固定 **60 W、85°C、40 g、25/15 Pa** 的部件筛选仍保留完整失败结果：九候选中没有设计通过组合故障；16 × 0.60 mm 候选仍需约 93.56°C。开发任务与留出任务分别冻结了不同要求，它们的通过不能回写原失败。负荷预览也不能修改原设计要求。

质量只包含翅片，不含基底、风道或飞机系统。温度是模型要求的均匀基底温度，不是绕组或器件热点。原生试验 CAD 加了 3 mm 说明性基底：开发与留出的总固体质量分别为 56.61414 g 和 50.02398 g，不能与翅片预算混用；45.2 mm 风道为数学边界，不是导出实体。CAD 字节、实体和网格通过不等于制造就绪。

全负荷 X-57 热模型仍未完成物理验证。固定物性、充分发展直流道、理想共同压差和均匀基底等假设省略了入口/出口损失、风机曲线、接触热阻、基底扩散、轴向导热、湍流及温变物性等安装效应。不得用于真实飞机设计、认证或运行决策。

## 同一应用内的专家证据层

初次讲解不必跳转；按问题从主路线进入深入页面：

- **`/nacelle`：航空装配与来源。** 公开图文约束下的参数化 Mod II 短舱、机翼、电机和控制器；可去壳、剖切、爆炸并查看热节点。未公开尺寸明确推定；流动与温度是降阶模型。[来源](docs/NACELLE_SOURCES.md)、[网络方程](docs/NACELLE_MODEL.md)、[装配演示](docs/NACELLE_DEMO.md)、[可信度缺口](docs/NACELLE_CREDIBILITY.md)
- **`/experiments`：公开部件实测对照。** 保存全部 32 条矩形流道记录与 12 个板翅图点，包括缺失值、不利差异及超域点。数值验收、图形读取范围和实验不确定度分别呈现。[对照说明](docs/EXPERIMENTAL_COMPARISONS.md)
- **`/physics#tradeoff`：原始故障与减重研究。** 九几何、四状态和负荷预览保留原 60 W 失败；可追溯流量、热导、翅片质量及适用域。`/physics` 另含公开流量诊断与有限体积子问题。[物理证据](docs/PHYSICS_LAB.md)
- **`/`：旧版合成任务策略工作台。** 正常、热天、冷却衰减、电源隔离、指令丢失及硬件取舍基线仍独立保留。[模型](docs/MODEL.md)、[结果与反例](docs/RESULTS.md)、[旧版六步讲解](docs/demo-storyboard.md)

部件模型不能冒充满负荷飞机模型；公开 CFD/站位数据也不是飞行实测。下一步测量、校准与留出方案见 [验证计划](docs/VALIDATION_PLAN.md)。

## 保存证据审计与复现

下列操作只用标准库，检查已保存身份、记录、算术和关卡，不是新一次助手执行或数值求解：

```sh
python -S scripts/verify_native_agent_trial.py --session research/native_agent_trial/runs/development
python -S scripts/verify_native_agent_trial.py --session research/native_agent_trial/runs/heldout
```

应用与接口回归检查：

```sh
python -m unittest discover -s tests -v
python scripts/generate_nacelle_evidence.py --check
python scripts/generate_nacelle_credibility.py --check
```

原生试验阶段保存的本地记录为 246 项测试通过；这是当时版本的历史结果，不代表本次新增展示代码的完整验收。新提交应分别记录本地回归、实际浏览器检查、远端 CI 和未运行项；用户设备也需独立复现。本地哈希检查一致性，不是不可篡改签名。

### 可选的重新求解与 CAD 生成

普通展示直接读取已保存证据和 CAD，无需安装依赖。新的原生试验数值求解需要已有 NumPy/SciPy；真正重新生成 CAD 需要 CadQuery。单动作适配器入口为 `python -m aerolab.agent_trial --help`，具体协议、预算和安全重算方式见 [试验说明](research/native_agent_trial/README.md)。适配器不会自行安装依赖，也不会自行调用模型。

旧版自定义 CAD 的可选依赖为 `cadquery==2.7.0`，详见 [CAD 生成与验证](docs/CAD.md)和[CAD—热模型联动](docs/CAD_THERMAL.md)。所有研究重算按对应目录说明写入新的输出目录，不覆盖接受的冻结证据。

## 下一步与共享方式

1. 对最终统一展示提交分别完成跨设备、浏览器和 CI 验收，并保存同版本输入、依赖、测试及证据身份
2. 扩大真正独立的留出任务，包含多个可行几何、更困难取舍和陌生任务族；保留失败、超域、耗时和工具成本
3. 依验证计划取得匹配的压差、流量、热损失与温度测量，先验证部件，再扩大安装系统结论

仓库是代码和文档的版本来源；云端、Mac、Windows 使用各自工作副本并按同一提交复现。新环境可运行与新任务有效分别验收，不以演示流畅替代证据。

## 数据、安全与许可

只使用公开来源、原创代码和明确声明的合成参数；区分来源事实、假设与计算。公开可读不等于允许复制分发，未确认许可的材料只保留引用。不需要上传内部设计、非公开参数、凭证或个人数据；动作只作用于仿真，不连接真实设备控制系统。

A project license has not yet been selected. Public visibility alone does not grant a general reuse license. Third-party materials retain their respective licenses. 已核查的来源与许可边界见 [SOURCES.md](docs/SOURCES.md)。
