"""Original reduced-order educational model; no aircraft-calibrated parameters.

Units: seconds, kW, kWh, A, V, degC, kJ/K, kW/K, kg.
Both available battery feeders can supply either cruise channel. An essential
LV source must be alive to command propulsion. Electrical transients, contactor
switching, flight dynamics and certification behaviour are out of scope.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from . import __version__

TEMPERATURE_LIMIT_C = 95.0
PROTECTION_C = 88.0  # Policy planning target, NOT a second physical limit.
MIN_VOLTAGE_V = 300.0
MAX_CURRENT_A = 260.0
MOTOR_EFFICIENCY = 0.93
MOTOR_CAP_KW = 110.0
THERMAL_CAPACITANCE_KJ_K = 14.0
ESSENTIAL_KW = 0.8
FLEX_KW = 1.5
BACKUP_EFFICIENCY = 0.95
PACK_RESISTANCE_OHM = 0.09
MODEL_SHA256 = hashlib.sha256(Path(__file__).read_text(encoding="utf-8").encode("utf-8")).hexdigest()
MODEL_DISCLAIMER = "Synthetic educational model inspired by public architecture. Not an X-57 reconstruction, flight prediction or certification evidence."


@dataclass(frozen=True)
class Design:
    id: str
    name: str
    mass_kg: float
    traction_kwh: float
    backup_kwh: float
    cooling_scale: float
    description: str
    cad_geometry: Any = None


# Hardware accounting is an explicitly synthetic equal-mass-budget example.
# Base: 300 kg traction battery @ .16 kWh/kg, 10 kg cooler, 2 kg LV @ .12 kWh/kg.
# Options allocate 20 additional kg among traction, cooler and essential reserve.
DESIGNS = {
    "reference": Design("reference", "基准硬件 · 312 kg", 312, 48, .24, 1.0,
                        "300 kg traction + 10 kg cooling + 2 kg essential battery"),
    "endurance": Design("endurance", "增重 20 kg · 能量优先", 332, 51.2, .24, 1.0,
                        "Additional 20 kg traction battery; hardware fixed during mission"),
    "thermal": Design("thermal", "增重 20 kg · 散热优先", 332, 48.8, .48, 1.65,
                      "Additional 5 kg traction + 13 kg cooling + 2 kg essential battery"),
    "essential": Design("essential", "增重 20 kg · 指令供电优先", 332, 49.6, 1.2, 1.1,
                        "Additional 10 kg traction + 2 kg cooling + 8 kg essential battery"),
}

# Synthetic shaft-power mission, NOT NASA's composite Mod IV qualification profile.
MISSION = (
    (60, "taxi", "滑行", 10.0, .35),
    (90, "takeoff", "起飞", 180.0, .7),
    (240, "initial_climb", "初始爬升", 150.0, .8),
    (420, "climb", "爬升", 120.0, 1.0),
    (900, "cruise", "巡航", 75.0, 1.25),
    (1020, "descent", "下降", 30.0, 1.05),
    (1080, "landing", "着陆", 80.0, .6),
    (1200, "reserve", "备份航段", 60.0, .9),
)
SCENARIOS = {
    "nominal": {"id": "nominal", "name": "01 正常任务", "description": "正常电源与冷却，检查两种策略是否都能完成任务", "ambient_c": 25.0, "events": []},
    "hot_day": {"id": "hot_day", "name": "02 热天爬升", "description": "热天初始爬升，观察热裕度与风扇能耗", "ambient_c": 40.0, "events": []},
    "cooling_fault": {"id": "cooling_fault", "name": "03 单侧冷却衰减", "description": "150 s 左推进通道冷却效能降至 25%", "ambient_c": 35.0, "events": [{"t_s": 150, "type": "cooling_degraded", "channel": 0, "factor": .25}]},
    "bus_cooling": {"id": "bus_cooling", "name": "04 电源隔离 + 冷却衰减", "description": "150 s 左通道冷却衰减，210 s A 电源隔离；允许如实报告不可行", "ambient_c": 40.0, "events": [{"t_s": 150, "type": "cooling_degraded", "channel": 0, "factor": .25}, {"t_s": 210, "type": "pack_isolated", "channel": 0}]},
    "command_loss": {"id": "command_loss", "name": "05 主低压失效 + 后备衰减", "description": "180 s 主 DC/DC 失效；后备低压电池初始可用容量 50%，耗尽后无法维持推进指令", "ambient_c": 30.0, "backup_factor": .5, "events": [{"t_s": 180, "type": "dcdc_failed"}]},
    "inverter_loss": {"id": "inverter_loss", "name": "06 推进通道隔离", "description": "180 s 右侧逆变/电机通道失效，两路电源仍可供左通道", "ambient_c": 30.0, "events": [{"t_s": 180, "type": "motor_failed", "channel": 1}]},
}
POLICIES = {
    "baseline": {"id": "baseline", "name": "热感知固定规则", "description": "爬升预冷 + 温度阈值风扇 + 等分负荷 + 约束内再分配；与规划器使用相同保护器"},
    "planner": {"id": "planner", "name": "确定性有界预测搜索", "description": "18 个风扇/分配候选，30 s 保持当前需求和已观测故障的预测；非大模型，无未来故障信息"},
}
SOURCES = [
    {"title": "NASA final traction and command architecture (2024)", "url": "https://ntrs.nasa.gov/citations/20240009560"},
    {"title": "NASA Mod II thermal analysis (2023)", "url": "https://ntrs.nasa.gov/citations/20230006888"},
    {"title": "NASA mission profile power analysis", "url": "https://ntrs.nasa.gov/citations/20230015689"},
    {"title": "NASA avionics power analysis", "url": "https://ntrs.nasa.gov/citations/20230015625"},
]


def catalog() -> dict:
    return {"model_version": __version__, "scenarios": list(SCENARIOS.values()),
            "designs": [asdict(x) for x in DESIGNS.values()], "policies": list(POLICIES.values()),
            "limits": {"temperature_c": TEMPERATURE_LIMIT_C, "protection_c": PROTECTION_C,
                       "min_voltage_v": MIN_VOLTAGE_V, "max_current_a": MAX_CURRENT_A},
            "sources": SOURCES, "replay_url": "/api/replay", "disclaimer": MODEL_DISCLAIMER}


def phase_at(t_s: float, design: Design, demand_scale: float = 1.0) -> dict:
    for end, name, label, power, airflow in MISSION:
        if t_s < end:
            # Synthetic mass penalty; not a flight-performance calculation.
            return {"id": name, "name": label, "power_kw": power * (1 + .00035 * (design.mass_kg - 312)) * demand_scale,
                    "airflow": airflow, "end_s": end}
    raise ValueError("Time outside synthetic mission")


@dataclass
class State:
    energy: list[float]
    temperatures: list[float]
    backup: float
    controllers: list[float] | None = None

    def copy(self) -> State:
        return State(self.energy.copy(), self.temperatures.copy(), self.backup,
                     self.controllers.copy() if self.controllers is not None else None)


def fault_state(events: list[dict], t: float) -> dict:
    result = {"pack_available": [True, True], "motor_available": [True, True],
              "cooling_health": [1.0, 1.0], "dcdc_alive": True, "labels": []}
    for event in events:
        if event["t_s"] > t:
            continue
        kind = event["type"]
        if kind == "pack_isolated":
            result["pack_available"][event["channel"]] = False
        elif kind == "motor_failed":
            result["motor_available"][event["channel"]] = False
        elif kind == "cooling_degraded":
            result["cooling_health"][event["channel"]] = event["factor"]
        elif kind == "dcdc_failed":
            result["dcdc_alive"] = False
        result["labels"].append(kind + (f":{event['channel']}" if "channel" in event else ""))
    return result


def voltage_oc(energy: float, capacity: float) -> float:
    return 360.0 + 80.0 * max(0.0, min(1.0, energy / capacity))


def pack_limit(energy: float, capacity: float, dt: float, available: bool) -> tuple[float, float]:
    voc = voltage_oc(energy, capacity)
    if not available or energy <= 0:
        return 0.0, voc
    current = min(MAX_CURRENT_A, (voc - MIN_VOLTAGE_V) / PACK_RESISTANCE_OHM,
                  voc / (2 * PACK_RESISTANCE_OHM), energy * 3600000 / (voc * dt))
    return (voc * current - current * current * PACK_RESISTANCE_OHM) / 1000, voc


def thermal_next(temperature: float, ambient: float, heat_kw: float, conductance: float, dt: float) -> float:
    decay = math.exp(-conductance * dt / THERMAL_CAPACITANCE_KJ_K)
    return ambient + (temperature - ambient) * decay + heat_kw / conductance * (1 - decay)


def allocate(total: float, caps: list[float], share: float) -> list[float]:
    first = [min(caps[0], total * share), min(caps[1], total * (1 - share))]
    remaining = max(0, total - sum(first))
    # Redistribution prevents an intentionally weak baseline.
    for i in sorted(range(2), key=lambda j: caps[j] - first[j], reverse=True):
        extra = min(remaining, max(0, caps[i] - first[i]))
        first[i] += extra
        remaining -= extra
    return first


def transition(state: State, phase: dict, faults: dict, design: Design, ambient: float,
               dt: float, cooling: float, share: float) -> tuple[State, dict]:
    if design.cad_geometry is not None:
        from .cad_mission import transition as cad_transition
        return cad_transition(state, phase, faults, design, ambient, dt, cooling, share)
    if not (0 <= cooling <= 1 and 0 <= share <= 1):
        raise ValueError("Policy action outside admissible fan/share bounds")
    state = state.copy()
    capacity = design.traction_kwh / 2
    limits_voc = [pack_limit(state.energy[i], capacity, dt, faults["pack_available"][i]) for i in range(2)]
    source_caps = [x[0] for x in limits_voc]
    available = sum(source_caps)
    essential_from_hv = min(ESSENTIAL_KW, available) if faults["dcdc_alive"] else 0.0
    # Essential reserve automatically covers primary LV shortfall, including HV
    # exhaustion with a healthy converter; it is not restricted to a fault flag.
    backup_input_kw = min((ESSENTIAL_KW - essential_from_hv) / BACKUP_EFFICIENCY,
                          state.backup * 3600 / dt)
    essential_served = essential_from_hv + backup_input_kw * BACKUP_EFFICIENCY
    command_alive = essential_served >= ESSENTIAL_KW - 1e-9
    fan = cooling if command_alive else 0.0
    fan_kw = 2 * .65 * fan ** 3
    fan_kw = min(fan_kw, max(0, available - essential_from_hv))
    actual_fan = (fan_kw / 1.3) ** (1 / 3) if fan_kw else 0.0
    conductances = [(0.04 * phase["airflow"] + .055 * actual_fan) * design.cooling_scale * faults["cooling_health"][i] for i in range(2)]
    thermal_caps = []
    for i in range(2):
        g = conductances[i]
        decay = math.exp(-g * dt / THERMAL_CAPACITANCE_KJ_K)
        heat_cap = max(0, (TEMPERATURE_LIMIT_C - ambient - (state.temperatures[i] - ambient) * decay) * g / (1 - decay))
        shaft_cap = heat_cap / (1 / MOTOR_EFFICIENCY - 1)
        thermal_caps.append(min(MOTOR_CAP_KW, shaft_cap) if command_alive and faults["motor_available"][i] else 0.0)
    prop_cap = max(0, available - essential_from_hv - fan_kw) * MOTOR_EFFICIENCY
    target = min(phase["power_kw"], prop_cap, sum(thermal_caps))
    motors = allocate(target, thermal_caps, share)
    motor_input = sum(motors) / MOTOR_EFFICIENCY
    # Sheddable LV load is served only after required propulsion and essential load.
    flex_served = min(FLEX_KW, max(0, available - essential_from_hv - fan_kw - motor_input)) if faults["dcdc_alive"] else 0.0
    bus_kw = essential_from_hv + fan_kw + motor_input + flex_served
    packs = [bus_kw * cap / available if available else 0.0 for cap in source_caps]
    currents, voltages, losses, chemical = [], [], [], []
    for i, power in enumerate(packs):
        voc = limits_voc[i][1]
        # Rationalized low-current root avoids cancellation at small P.
        discriminant = max(0, voc * voc - 4 * PACK_RESISTANCE_OHM * power * 1000)
        current = 2 * power * 1000 / (voc + math.sqrt(discriminant)) if power else 0.0
        terminal = voc - current * PACK_RESISTANCE_OHM
        loss = current * current * PACK_RESISTANCE_OHM / 1000
        chem = voc * current / 1000
        state.energy[i] = max(0, state.energy[i] - chem * dt / 3600)
        currents.append(current)
        voltages.append(terminal)
        losses.append(loss)
        chemical.append(chem)
        state.temperatures[i] = thermal_next(state.temperatures[i], ambient,
                                              motors[i] * (1 / MOTOR_EFFICIENCY - 1), conductances[i], dt)
    state.backup = max(0, state.backup - backup_input_kw * dt / 3600)
    violations = []
    if max(state.temperatures) > TEMPERATURE_LIMIT_C + 1e-7:
        violations.append("temperature_limit")
    if max(currents) > MAX_CURRENT_A + 1e-7:
        violations.append("current_limit")
    if any(voltages[i] < MIN_VOLTAGE_V - 1e-7 for i in range(2) if packs[i] > 1e-9):
        violations.append("voltage_limit")
    unmet = max(0, phase["power_kw"] - sum(motors))
    row = {"phase": phase["name"], "phase_id": phase["id"], "demand_kw": phase["power_kw"],
           "served_propulsion_kw": sum(motors), "unmet_propulsion_kw": unmet,
           "essential_kw": ESSENTIAL_KW, "served_essential_kw": essential_served,
           "flex_kw": FLEX_KW, "served_flex_kw": flex_served, "pack_kw": packs,
           "pack_soc": [e / capacity for e in state.energy], "pack_voltage_v": voltages,
           "pack_current_a": currents, "pack_loss_kw": losses, "chemical_kw": chemical,
           "motor_shaft_kw": motors, "temperature_c": state.temperatures.copy(),
           "thermal_margin_c": [TEMPERATURE_LIMIT_C - t for t in state.temperatures],
           "cooling": [actual_fan, actual_fan], "fan_kw": fan_kw,
           "backup_kwh": state.backup, "battery_energy_kwh": sum(state.energy),
           "backup_input_kw": backup_input_kw, "command_alive": command_alive,
           "pack_available": faults["pack_available"].copy(), "motor_available": faults["motor_available"].copy(),
           "faults": faults["labels"].copy(), "violations": violations,
           "bus_balance_error_kw": sum(packs) - bus_kw,
           "battery_balance_error_kw": sum(chemical) - sum(packs) - sum(losses)}
    return state, row


def baseline_action(state: State, phase: dict, faults: dict) -> tuple[float, float, str]:
    maximum = max(state.temperatures + (state.controllers or []))
    fan = 1.0 if maximum >= 80 else .65 if maximum >= 65 else .3
    if phase["id"] in ("takeoff", "initial_climb", "climb"):
        fan = max(fan, .65)  # A credible phase-aware thermal baseline.
    if faults["labels"]:
        fan = 1.0
    return fan, .5, "阶段预冷 / 温度阈值；优先关键负载，约束内再分配"


def planner_action(state: State, phase: dict, faults: dict, design: Design, ambient: float,
                   dt: float) -> tuple[float, float, str]:
    candidates = []
    # Forecast uses current demand and observed faults only, identical sensing to baseline.
    # Three fan levels x six split choices = bounded finite search, not an LLM agent.
    for fan in (.3, .65, 1.0):
        for share in (.2, .35, .5, .65, .8, 1.0):
            projected = state.copy()
            unmet_energy = essential_shortfall = soft_exposure = energy = flex_shed = 0.0
            for _ in range(5):
                projected, row = transition(projected, phase, faults, design, ambient, 6.0, fan, share)
                unmet_energy += row["unmet_propulsion_kw"] * 6 / 3600
                essential_shortfall += (ESSENTIAL_KW - row["served_essential_kw"]) * 6 / 3600
                soft_exposure += sum(max(0, t - PROTECTION_C) ** 2 for t in row["temperature_c"])
                energy += (sum(row["chemical_kw"]) + row["backup_input_kw"]) * 6 / 3600
                flex_shed += (FLEX_KW - row["served_flex_kw"]) * 6 / 3600
            # Safety/service dominate; soft thermal target trades fan energy against heat.
            score = (round(essential_shortfall, 9), round(unmet_energy, 7),
                     energy + .004 * soft_exposure + .2 * flex_shed,
                     abs(share - .5), fan)
            candidates.append((score, fan, share))
    _, fan, share = min(candidates)
    return fan, share, "18 候选 / 30 s 预测；关键服务优先，权衡热目标与能耗"


def _finite_number(value: Any, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number in [{low}, {high}]")
    return float(value)


def simulate(scenario_id: str = "cooling_fault", policy: str = "baseline", design_id: str = "reference",
             ambient_c: float | None = None, dt_s: float = 2, demand_scale: float = 1.0,
             event_time_offset_s: float = 0, cad_geometry: dict | None = None) -> dict:
    if scenario_id not in SCENARIOS or policy not in POLICIES or design_id not in DESIGNS:
        raise ValueError("Unknown scenario, policy or design")
    dt = _finite_number(dt_s, "dt_s", .25, 10)
    ambient = SCENARIOS[scenario_id]["ambient_c"] if ambient_c is None else _finite_number(ambient_c, "ambient_c", -10, 50)
    demand_scale = _finite_number(demand_scale, "demand_scale", .5, 1.5)
    offset = _finite_number(event_time_offset_s, "event_time_offset_s", -120, 120)
    design = DESIGNS[design_id]
    if cad_geometry is not None:
        from .cad_mission import linked_design
        design = linked_design(design, cad_geometry)
    scenario = dict(SCENARIOS[scenario_id], ambient_c=ambient)
    scenario["events"] = [dict(e, t_s=e["t_s"] + offset) for e in scenario["events"]]
    inputs = {"scenario_id": scenario_id, "policy": policy, "design_id": design_id,
              "ambient_c": ambient, "dt_s": dt, "demand_scale": demand_scale,
              "event_time_offset_s": offset, "model_version": __version__, "model_sha256": MODEL_SHA256}
    if design.cad_geometry is not None:
        inputs["cad_geometry"] = asdict(design.cad_geometry)
        inputs["coupling_version"] = "controller-motor-split-v1"
        inputs["cad_model_sha256"] = hashlib.sha256(b"".join(Path(__file__).with_name(p).read_bytes() for p in ("geometry.py", "cad_thermal.py", "cad_mission.py"))).hexdigest()
    encoded = json.dumps(inputs, sort_keys=True, separators=(",", ":"))
    input_hash = hashlib.sha256(encoded.encode()).hexdigest()
    state = State([design.traction_kwh * .95 / 2] * 2, [ambient + 5] * 2,
                  design.backup_kwh * scenario.get("backup_factor", 1))
    if design.cad_geometry is not None:
        state.controllers = [ambient + 5] * 2
    initial_energy = sum(state.energy) + state.backup
    trace, actions = [], []
    previous_action = previous_faults = None
    t = 0.0
    totals = {"unmet_propulsion_kwh": 0.0, "unserved_essential_kwh": 0.0, "flex_shed_kwh": 0.0,
              "requested_propulsion_kwh": 0.0, "served_propulsion_kwh": 0.0,
              "fan_energy_kwh": 0.0, "chemical_energy_kwh": 0.0}
    while t < MISSION[-1][0] - 1e-9:
        phase = phase_at(t, design, demand_scale)
        next_events = [e["t_s"] for e in scenario["events"] if e["t_s"] > t + 1e-9]
        step = min(dt, phase["end_s"] - t, MISSION[-1][0] - t,
                   min(next_events) - t if next_events else dt)
        faults = fault_state(scenario["events"], t)
        if policy == "baseline":
            fan, share, reason = baseline_action(state, phase, faults)
        else:
            fan, share, reason = planner_action(state, phase, faults, design, ambient, step)
        action = (fan, share)
        if previous_faults != faults["labels"] and faults["labels"]:
            actions.append({"t_s": t, "type": "fault", "reason": "观测到场景故障", "details": {"active_faults": faults["labels"]}})
        if action != previous_action:
            actions.append({"t_s": t, "type": "dispatch", "reason": reason,
                            "details": {"fan_command": fan, "preferred_left_share": share,
                                        "design_id": design.id, "mass_kg": design.mass_kg}})
        old_energy = sum(state.energy) + state.backup
        state, row = transition(state, phase, faults, design, ambient, step, fan, share)
        row["t_s"] = round(t + step, 8)
        row["dt_s"] = step
        row["stored_energy_balance_error_kwh"] = old_energy - sum(state.energy) - state.backup - (sum(row["chemical_kw"]) + row["backup_input_kw"]) * step / 3600
        trace.append(row)
        totals["unmet_propulsion_kwh"] += row["unmet_propulsion_kw"] * step / 3600
        totals["unserved_essential_kwh"] += (ESSENTIAL_KW - row["served_essential_kw"]) * step / 3600
        totals["flex_shed_kwh"] += (FLEX_KW - row["served_flex_kw"]) * step / 3600
        totals["requested_propulsion_kwh"] += row["demand_kw"] * step / 3600
        totals["served_propulsion_kwh"] += row["served_propulsion_kw"] * step / 3600
        totals["fan_energy_kwh"] += row["fan_kw"] * step / 3600
        totals["chemical_energy_kwh"] += (sum(row["chemical_kw"]) + row["backup_input_kw"]) * step / 3600
        previous_action, previous_faults = action, faults["labels"]
        t += step
    validation = {"energy_balance_max_error_kw": max(abs(r["bus_balance_error_kw"]) for r in trace),
                  "battery_balance_max_error_kw": max(abs(r["battery_balance_error_kw"]) for r in trace),
                  "stored_energy_balance_max_error_kwh": max(abs(r["stored_energy_balance_error_kwh"]) for r in trace),
                  "finite_values": all(math.isfinite(v) for r in trace for v in r["temperature_c"] + r["pack_soc"] + r["pack_current_a"]),
                  "fixed_hardware": all(a["details"].get("mass_kg", design.mass_kg) == design.mass_kg for a in actions)}
    if design.cad_geometry is not None:
        validation["controller_finite"] = all(math.isfinite(v) for r in trace for v in r["controller_temperature_c"] + r["motor_temperature_c"])
        validation["drivetrain_balance_max_error_kw"] = max(abs(r["drivetrain_balance_error_kw"]) for r in trace)
        validation["finite_values"] = validation["finite_values"] and validation["controller_finite"]
    solver_valid = validation["finite_values"] and validation["energy_balance_max_error_kw"] < 1e-8 and validation["battery_balance_max_error_kw"] < 1e-8 and validation["stored_energy_balance_max_error_kwh"] < 1e-8
    if design.cad_geometry is not None:
        solver_valid = solver_valid and validation["drivetrain_balance_max_error_kw"] < 1e-8
    violation_count = sum(len(r["violations"]) for r in trace)
    summary = {**totals, "feasible": solver_valid and violation_count == 0 and totals["unmet_propulsion_kwh"] < 1e-6 and totals["unserved_essential_kwh"] < 1e-6,
               "solver_valid": solver_valid, "energy_used_kwh": initial_energy - sum(state.energy) - state.backup,
               "min_thermal_margin_c": min(min(r["thermal_margin_c"]) for r in trace),
               "max_temperature_c": max(max(r["temperature_c"]) for r in trace),
               "min_voltage_v": min(v for r in trace for v, p in zip(r["pack_voltage_v"], r["pack_kw"]) if p > 1e-9),
               "max_current_a": max(max(r["pack_current_a"]) for r in trace),
               "remaining_energy_kwh": sum(state.energy), "accessible_traction_energy_kwh": sum(e for e, alive in zip(state.energy, fault_state(scenario["events"], t)["pack_available"]) if alive), "backup_remaining_kwh": state.backup,
               "violation_count": violation_count, "duration_s": t,
               "thermal_target_exposure_s": sum(r["dt_s"] for r in trace if max(r["temperature_c"]) > PROTECTION_C),
               "first_propulsion_shortfall_s": next((r["t_s"] - r["dt_s"] for r in trace if r["unmet_propulsion_kw"] > 1e-6), None),
               "first_essential_shortfall_s": next((r["t_s"] - r["dt_s"] for r in trace if r["served_essential_kw"] < ESSENTIAL_KW - 1e-6), None)}
    if design.cad_geometry is not None:
        summary["max_motor_temperature_c"] = max(max(r["motor_temperature_c"]) for r in trace)
        summary["max_controller_temperature_c"] = max(max(r["controller_temperature_c"]) for r in trace)
        summary["controller_blower_energy_kwh"] = sum(r["controller_blower_kw"]*r["dt_s"]/3600 for r in trace)
    return {"meta": {"model_version": __version__, "run_id": input_hash[:16], "input_hash": input_hash,
                     "execution": "computed", "model_kind": "cad_controller_motor_split" if design.cad_geometry is not None else "synthetic", "dt_s": dt, "inputs": inputs, "model_sha256": MODEL_SHA256,
                     "disclaimer": MODEL_DISCLAIMER},
            "scenario": scenario, "design": {k: v for k, v in asdict(design).items() if k != "cad_geometry" or v is not None}, "policy": POLICIES[policy],
            "summary": summary, "trace": trace, "actions": actions, "validation": validation}


def compare(**kwargs: Any) -> dict:
    kwargs.pop("policy", None)
    return {p: simulate(policy=p, **kwargs) for p in ("baseline", "planner")}


def sweep(**kwargs: Any) -> dict:
    kwargs.pop("design_id", None)
    kwargs.pop("policy", None)
    runs = [simulate(design_id=d, policy="planner", **kwargs) for d in DESIGNS]
    return {"scenario": runs[0]["scenario"], "policy": POLICIES["planner"],
            "results": [{k: run[k] for k in ("design", "summary")} | {"run_id": run["meta"]["run_id"], "input_hash": run["meta"]["input_hash"]} for run in runs],
            "note": "Offline independent fixed-hardware runs. Hardware mass is never changed during dispatch. All mass and penalty coefficients are synthetic."}
