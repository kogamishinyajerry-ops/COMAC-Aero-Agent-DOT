# 参数化 CAD 与热模型的共同几何

这是从公开尺寸新建的均匀翅片、平底散热器理想化模型。**不是 NASA 原始 CAD、最终 X-57 Mod II 零件、制造发布或经过试验验证的散热设计。** CAD 单位为 mm；热模型接收显式换算后的 SI 参数。

## 来源事实与假设

来源：[NASA/TM-20230011420, August 2023](https://ntrs.nasa.gov/citations/20230011420)，Table 2 / Figure 9，报告印刷页 13。NTRS 标为美国政府作品、允许公众使用。本仓库只引用报告并自行按尺寸建模；不重新发布报告。

| 项目 | 参考值 | 类型 |
|---|---:|---|
| 长度 L | 388.6 mm | 来源尺寸 |
| 宽度 W | 179.5 mm | 来源尺寸 |
| 翅片数 N | 43 | 来源尺寸 |
| 翅片高度 H（基板以上） | 41 mm | 来源尺寸 |
| 基板厚度 b | 6 mm | 来源尺寸 |
| 翅片厚度 t | 1.11 mm | 来源平均值，被理想化为均匀厚度 |
| 间距 g | 3.137380952 mm | 由总宽推导 |
| 来源平均间距 | 3.14 mm | 四舍五入值，不作为独立约束 |
| 密度 | 2700 kg/m³ | 假定铝材密度，未识别具体合金 |

采用 g = (W − N t) / (N − 1)。直接用 3.14 mm 会得到 179.61 mm 总宽，比来源宽度多 0.11 mm。平底、矩形等厚翅片、无倒角/孔/曲面等均为假设。计算范围检查是软件边界，不是可制造或物理有效范围。

热分析假定通道上方存在独立绝热盖板/风道，因此水力直径包括盖板的湿周；该盖板**未导出到 STEP/STL，也未计入散热器质量**。加热面积只包括内侧通道壁与裸露基板；不包含两侧外表面、翅片顶面和端面。附加风道、连接件或器件的质量需要由系统模型另计。

## 单一参数对象与接口

`aerolab/geometry.py` 中不可变 `Geometry` 含六个字段：`length_mm`、`width_mm`、`fin_height_mm`、`base_thickness_mm`、`fin_thickness_mm`、`fin_count`。不保存可彼此矛盾的独立间距。部分参数字典通过 `parse_geometry()` 验证，其余值使用参考尺寸。

- `geometry_metrics(params, density_kg_m3=2700)`：矩形几何的解析量，**不冒充 BRep 实测**
- `geometry_fingerprint(params)`：规范化参数和几何 schema 的 SHA-256；预览、导出及证据使用相同指纹
- `geometry_preview_svg(params)`：同一参数驱动的轴测图与端面图；不是 CFD 或 BRep 校验图
- `generate_step(params)`：返回可编辑的真实实体 STEP BRep 字节
- `generate_stl(params)`：返回封闭三角面网格字节，原始坐标单位 mm
- `cad_status(params)`：只有匹配参数指纹且文件校验通过的预存独立验证证据才显示 `verified_brep`；任意其他参数显示 `analytic_only`
- `kernel_status()`：可选 CadQuery 内核的加载状态

任意自定义 STEP 导出会执行实体构建与 STEP 再导入校验；这些即时生成不会悄悄改写受版本控制的证据。自定义几何即使刚导出成功，`cad_status` 仍只描述现有 manifest 是否有匹配的持久验证记录。

## 单位与推导

以下尺寸先统一使用 mm：

- 体积 V = L (W b + N t H)，mm³；转换到 m³ 乘 10⁻⁹
- 质量 m = ρ V，ρ 为明确的假定密度，kg/m³
- 通道数 n = N − 1
- 通道内翅片面积 A_fin = 2 n H L，mm²；转 m² 乘 10⁻⁶
- 裸露基板面积 A_base = n g L
- 通道加热面积 A_heat = A_fin + A_base
- 自由流通截面 A_flow = n g H
- 封闭矩形通道总湿周 P_wet = 2 n (g + H)
- 加热湿周 P_heat = n (g + 2 H)；不含绝热盖板
- 水力直径 D_h = 4 A_flow / P_wet = 2 g H / (g + H)
- 固体所有外表面面积 A_solid = 2 W L + 2 b (W + L) + 2 N H (L + t)

`channel_heated_area_m2` 不等于 `all_solid_surface_area_m2`。`wetted_perimeter_m` 不等于 `heated_perimeter_m`。热层必须使用加热面积做换热、水力直径做流动关联，不能把缺失盖板的 CAD 周长误认为封闭通道湿周。

## 已生成与独立验证的三种几何

| 方案 | N / H / b (mm) | 解析质量 @2700 kg/m³ | 独立 BRep 面数 | 封闭 STL 三角面数 |
|---|---|---:|---:|---:|
| reference | 43 / 41 / 6 | 3.183260035 kg | 174 | 684 |
| light | 31 / 32 / 5 | 2.096992076 kg | 126 | 492 |
| dense | 57 / 41 / 6 | 3.851760065 kg | 230 | 908 |

light / dense 是用于比较的合成设计变体，非 NASA 报告中的方案。三者的 L / W / t 相同。增加翅片使换热面积和质量增加，但间隙/流通面积减小；不能由面积更大直接推断实际散热更好。

参考实体独立测得体积 1,178,985.198 mm³，外包络 x/y/z = 179.5 / 388.6 / 47 mm。通道加热面积为 1.389544222 m²，自由流通面积为 0.00540257 m²，所有固体外表面面积为 1.520442060 m²。该体积、质量、面积与恢复的原始 proof STEP 的独立再导入结果相符。

`cad/manifest.json` 分开记录：

1. 解析几何量
2. OpenCascade 实体测量：有效实体数、封闭壳体、V/E/F 拓扑、Euler 特征数、体积、面积、质量、包围盒与误差
3. STEP 导出后再次导入的同等检查
4. 二进制 STL 的独立标准库检查：顶点焊接、每边恰有两个反向使用、连通性、非退化三角面、Euler=2、带符号体积及包围盒
5. 未压缩文件与 gzip 文件各自的 SHA-256、长度、工具版本、生成器和几何代码指纹

每个方案必须为一个有效实体、一个闭合壳体、Euler=2；BRep 体积和面积相对误差 <10⁻⁹，包围盒误差 <10⁻⁷ mm。STL 以 float32 坐标保存，允许体积相对误差 <10⁻⁵、包围盒误差 <10⁻³ mm。软件一致性验证不能代替实验、CFD、制造或适航验证。

## 使用与复现

基础应用和三种预设的 STEP/STL 下载不需要第三方依赖。仓库存储 `.step.gz` / `.stl.gz`，接口会解压为标准文件；`cad/*.svg` 是可独立打开的预览。

```bash
# 基础测试（若未安装 CadQuery，只跳过独立内核再生成测试）
python -m unittest discover -s tests -p test_geometry.py -v

# 解压参考文件，无需 CAD 内核
python -c "from pathlib import Path; from aerolab.geometry import generate_step; Path('reference.step').write_bytes(generate_step())"

# 可选：在单独环境安装已核查生成版本
python -m venv .venv-cad
# macOS/Linux: source .venv-cad/bin/activate
# Windows PowerShell: .venv-cad\\Scripts\\Activate.ps1
python -m pip install cadquery==2.7.0

# 重建全部三种真实 CAD 与证据
python scripts/generate_cad.py --out output/cad

# 单独核查已提交的压缩 CAD 文件
python scripts/generate_cad.py --verify-only --out cad

# 导出任意合法的自定义几何
python scripts/generate_cad.py --params '{"fin_count":39,"fin_height_mm":36}' --out output/custom-cad
```

Windows 命令行的 JSON 引号规则依 shell 而异，可使用 Python API 传入字典。STEP 文件头包含 OpenCascade 生成时间，且内核版本可能改变实体编号或三角剖分，因此独立运行的文件 SHA-256 不要求字节完全一致；几何指纹和量测容差才是跨运行的一致性条件。`--verify-only` 必须对所检查的那一套文件满足 manifest 的精确 SHA-256。

本次验证使用 CadQuery 2.7.0 / cadquery-ocp 7.8.1.1.post1；没有声称在用户的 Mac 或 Windows 上实际运行过可选 CAD 内核。
