"""Regenerate committed evidence and its summary from the actual model."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aerolab.model import SCENARIOS, compare, simulate, sweep, MODEL_SHA256
from aerolab.__main__ import write_json
from aerolab.evidence import write_reference

root = Path(__file__).resolve().parent.parent
reference = compare()
write_reference(reference)
benchmark = []
for scenario in SCENARIOS:
    for policy in ("baseline", "planner"):
        run = simulate(scenario, policy)
        benchmark.append({"scenario": scenario, "policy": policy, "run_id": run["meta"]["run_id"], **run["summary"]})
write_json(root / "examples/benchmark.json", benchmark)
designs = sweep(scenario_id="command_loss")
write_json(root / "examples/command_loss_design_sweep.json", designs)
lines = ["# 可复现结果（合成模型）", "", f"模型源码 SHA-256：`{MODEL_SHA256}`", "",
         "生成命令：`python scripts/generate_evidence.py`；默认 2 s 时间步，无随机数。下列均为求解器输出，不是飞行测量。", "",
         "`可行` 要求全任务推进和关键低压服务足额且硬约束无违规；`求解有效` 仅证明本实现账目和数值检查通过。", "",
         "| 场景 | 策略 | 可行 | 推进缺供 kWh | 关键缺供 kWh | 最低热裕度 °C | 储能消耗 kWh |", "|---|---|---|---:|---:|---:|---:|"]
for r in benchmark:
    lines.append(f"| {r['scenario']} | {r['policy']} | {'是' if r['feasible'] else '否'} | {r['unmet_propulsion_kwh']:.4f} | {r['unserved_essential_kwh']:.4f} | {max(0,r['min_thermal_margin_c']):.3f} | {r['energy_used_kwh']:.4f} |")
lines += ["", "## 必须保留的反例", "",
          "单侧冷却衰减场景中，两种策略都通过硬保护避免越界，但都未满足完整推进需求。预测搜索可能推迟首次缺供，同时累计缺供比固定规则更多；这说明短时域策略不保证更好。不要将较低能耗当成效率提升，因为完成的推进服务也更少。", "",
          "单推进通道故障也可能出现规划器落后。正常与热天案例两种策略都可行；此时能耗和热裕度才具备更直接的同服务比较意义。", "",
          "## 主低压失效 + 后备衰减：离线硬件比较", "",
          "全部使用 planner；每行独立运行完整任务，硬件在运行中不变。后三行同为增重 20 kg。所有质量、储能和散热分配都是合成假设。", "",
          "| 设计 | 质量 kg | 推进缺供 kWh | 关键缺供 kWh | 可连接牵引余能 kWh | 后备余能 kWh |", "|---|---:|---:|---:|---:|---:|"]
for row in designs["results"]:
    d, s = row["design"], row["summary"]
    lines.append(f"| {d['id']} | {d['mass_kg']:.0f} | {s['unmet_propulsion_kwh']:.4f} | {s['unserved_essential_kwh']:.4f} | {s['accessible_traction_energy_kwh']:.4f} | {s['backup_remaining_kwh']:.4f} |")
lines += ["", "不能把有电量但无推进指令的状态写成可继续飞行；不能把模型测试通过写成 NASA 校准或适航认证。详见 [MODEL.md](MODEL.md) 和 [SOURCES.md](SOURCES.md)。", ""]
(root / "docs/RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
print("Generated reference replay, 12 scenario/policy results, 4-design sweep and docs/RESULTS.md")
