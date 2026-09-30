"""Opt-in CAD-linked mission transition; legacy benchmark remains a separate mode.

The controller/sink interface proxy and motor are distinct thermal nodes.
Total drivetrain efficiency remains .93: motor .95 × controller (.93/.95).
The two CAD solids are fixed hardware for an entire run.
"""
from __future__ import annotations
from dataclasses import replace
import math
from .cad_thermal import (flow_properties, MATERIAL, CONTROLLER_PLATE_MASS_KG,
                          DUCT_MASS_KG)
from .geometry import parse_geometry, geometry_metrics

MOTOR_ONLY_EFFICIENCY = .95
COMBINED_EFFICIENCY = .93
CONTROLLER_EFFICIENCY = COMBINED_EFFICIENCY / MOTOR_ONLY_EFFICIENCY
MOTOR_LOSS_PER_SHAFT = 1/MOTOR_ONLY_EFFICIENCY-1
CONTROLLER_LOSS_PER_SHAFT = 1/COMBINED_EFFICIENCY-1/MOTOR_ONLY_EFFICIENCY


def linked_design(design, geometry):
    geo = parse_geometry(geometry)
    if not flow_properties(geo, .085*1.25)["within_flow_limits"]:
        raise ValueError("Geometry exceeds incompressible-flow applicability at maximum mission command")
    mass = 2*geometry_metrics(geo)["mass_kg"] + 2*CONTROLLER_PLATE_MASS_KG + DUCT_MASS_KG
    return replace(design, mass_kg=design.mass_kg+mass, cad_geometry=geo,
                   name=design.name+" · CAD 控制器扩展",
                   description=design.description+f"; add two CAD sinks + 1.2 kg controller plates + 1.0 kg assumed duct: {mass:.6f} kg. Original synthetic motor-cooling hardware retained.")


def node_next(temperature, ambient, heat_kw, conductance_kw_k, capacity_kj_k, dt):
    if conductance_kw_k == 0:
        return temperature+heat_kw*dt/capacity_kj_k
    decay = math.exp(-conductance_kw_k*dt/capacity_kj_k)
    return ambient+(temperature-ambient)*decay+heat_kw/conductance_kw_k*(-math.expm1(-conductance_kw_k*dt/capacity_kj_k))


def admissible_heat(temperature, ambient, conductance, capacity, dt, limit):
    if conductance == 0:
        return max(0, (limit-temperature)*capacity/dt)
    one_minus_decay = -math.expm1(-conductance*dt/capacity)
    return max(0, (limit-ambient-(temperature-ambient)*(1-one_minus_decay))*conductance/one_minus_decay)


def cooling_load(geo, fan, phase_airflow, health):
    flows = [.085*fan*phase_airflow*h for h in health]
    props = [flow_properties(geo, flow) for flow in flows]
    motor_fan_kw = 1.3*fan**3
    return motor_fan_kw+sum(p["blower_electrical_w"] for p in props)/1000, props, motor_fan_kw


def transition(state, phase, faults, design, ambient, dt, cooling, share):
    from .model import (ESSENTIAL_KW, FLEX_KW, BACKUP_EFFICIENCY, MOTOR_CAP_KW,
                        THERMAL_CAPACITANCE_KJ_K, TEMPERATURE_LIMIT_C,
                        MAX_CURRENT_A, MIN_VOLTAGE_V, PACK_RESISTANCE_OHM,
                        pack_limit, allocate)
    if not (0 <= cooling <= 1 and 0 <= share <= 1):
        raise ValueError("Policy action outside admissible fan/share bounds")
    state = state.copy()
    if state.controllers is None:
        raise ValueError("CAD mission requires separate controller state")
    old_motor, old_controller = state.temperatures.copy(), state.controllers.copy()
    capacity = design.traction_kwh/2
    limits_voc = [pack_limit(state.energy[i], capacity, dt, faults["pack_available"][i]) for i in range(2)]
    source_caps = [x[0] for x in limits_voc]
    available = sum(source_caps)
    essential_hv = min(ESSENTIAL_KW, available) if faults["dcdc_alive"] else 0.0
    backup_input = min((ESSENTIAL_KW-essential_hv)/BACKUP_EFFICIENCY, state.backup*3600/dt)
    essential_served = essential_hv+backup_input*BACKUP_EFFICIENCY
    command_alive = essential_served >= ESSENTIAL_KW-1e-9
    fan = cooling if command_alive else 0.0
    cooling_budget = max(0, available-essential_hv)
    cooling_kw, props, motor_fan_kw = cooling_load(design.cad_geometry, fan, phase["airflow"], faults["cooling_health"])
    if cooling_kw > cooling_budget:
        low, high = 0.0, fan
        for _ in range(40):
            middle = (low+high)/2
            cost, _, _ = cooling_load(design.cad_geometry, middle, phase["airflow"], faults["cooling_health"])
            if cost <= cooling_budget:
                low = middle
            else:
                high = middle
        fan = low
        cooling_kw, props, motor_fan_kw = cooling_load(design.cad_geometry, fan, phase["airflow"], faults["cooling_health"])
    motor_g = [(0.04*phase["airflow"]+.055*fan)*design.cooling_scale*h for h in faults["cooling_health"]]
    controller_g = [p["interface_conductance_w_k"]/1000 for p in props]
    controller_c = props[0]["thermal_capacitance_j_k"]/1000
    thermal_caps = []
    for i in range(2):
        motor_cap = admissible_heat(state.temperatures[i], ambient, motor_g[i], THERMAL_CAPACITANCE_KJ_K, dt, TEMPERATURE_LIMIT_C)/MOTOR_LOSS_PER_SHAFT
        controller_cap = admissible_heat(state.controllers[i], ambient, controller_g[i], controller_c, dt, TEMPERATURE_LIMIT_C)/CONTROLLER_LOSS_PER_SHAFT
        thermal_caps.append(min(MOTOR_CAP_KW, motor_cap, controller_cap) if command_alive and faults["motor_available"][i] else 0.0)
    prop_cap = max(0, available-essential_hv-cooling_kw)*COMBINED_EFFICIENCY
    motors = allocate(min(phase["power_kw"], prop_cap, sum(thermal_caps)), thermal_caps, share)
    propulsion_input = sum(motors)/COMBINED_EFFICIENCY
    flex = min(FLEX_KW, max(0, available-essential_hv-cooling_kw-propulsion_input)) if faults["dcdc_alive"] else 0.0
    bus_kw = essential_hv+cooling_kw+propulsion_input+flex
    packs = [bus_kw*cap/available if available else 0.0 for cap in source_caps]
    currents, voltages, losses, chemical = [], [], [], []
    motor_heat = [power*MOTOR_LOSS_PER_SHAFT for power in motors]
    controller_heat = [power*CONTROLLER_LOSS_PER_SHAFT for power in motors]
    for i, power in enumerate(packs):
        voc = limits_voc[i][1]
        current = 2*power*1000/(voc+math.sqrt(max(0, voc*voc-4*PACK_RESISTANCE_OHM*power*1000))) if power else 0.0
        terminal = voc-current*PACK_RESISTANCE_OHM
        loss = current*current*PACK_RESISTANCE_OHM/1000
        chem = voc*current/1000
        state.energy[i] = max(0, state.energy[i]-chem*dt/3600)
        currents.append(current); voltages.append(terminal); losses.append(loss); chemical.append(chem)
        state.temperatures[i] = node_next(state.temperatures[i], ambient, motor_heat[i], motor_g[i], THERMAL_CAPACITANCE_KJ_K, dt)
        state.controllers[i] = node_next(state.controllers[i], ambient, controller_heat[i], controller_g[i], controller_c, dt)
    state.backup = max(0, state.backup-backup_input*dt/3600)
    combined = [max(state.temperatures[i], state.controllers[i]) for i in range(2)]
    violations = []
    if max(combined) > TEMPERATURE_LIMIT_C+1e-7:
        violations.append("temperature_limit")
    if max(currents) > MAX_CURRENT_A+1e-7:
        violations.append("current_limit")
    if any(voltages[i] < MIN_VOLTAGE_V-1e-7 for i in range(2) if packs[i] > 1e-9):
        violations.append("voltage_limit")
    motor_rejection = [motor_heat[i]-THERMAL_CAPACITANCE_KJ_K*(state.temperatures[i]-old_motor[i])/dt for i in range(2)]
    controller_rejection = [controller_heat[i]-controller_c*(state.controllers[i]-old_controller[i])/dt for i in range(2)]
    return state, {"phase": phase["name"], "phase_id": phase["id"], "demand_kw": phase["power_kw"],
        "served_propulsion_kw": sum(motors), "unmet_propulsion_kw": max(0, phase["power_kw"]-sum(motors)),
        "essential_kw": ESSENTIAL_KW, "served_essential_kw": essential_served,
        "flex_kw": FLEX_KW, "served_flex_kw": flex, "pack_kw": packs,
        "pack_soc": [e/capacity for e in state.energy], "pack_voltage_v": voltages,
        "pack_current_a": currents, "pack_loss_kw": losses, "chemical_kw": chemical,
        "motor_shaft_kw": motors, "temperature_c": combined,
        "motor_temperature_c": state.temperatures.copy(), "controller_temperature_c": state.controllers.copy(),
        "motor_loss_kw": motor_heat, "controller_loss_kw": controller_heat,
        "drivetrain_balance_error_kw": propulsion_input-sum(motors)-sum(motor_heat)-sum(controller_heat),
        "motor_rejected_heat_kw": motor_rejection, "controller_rejected_heat_kw": controller_rejection,
        "controller_thermal_capacity_kj_k": controller_c,
        "controller_flow_kg_s": [p["mass_flow_kg_s"] for p in props],
        "controller_pressure_drop_pa": [p["pressure_drop_pa"] for p in props],
        "controller_blower_kw": sum(p["blower_electrical_w"] for p in props)/1000,
        "motor_fan_kw": motor_fan_kw, "thermal_margin_c": [TEMPERATURE_LIMIT_C-t for t in combined],
        "cooling": [fan, fan], "fan_kw": cooling_kw, "backup_kwh": state.backup,
        "battery_energy_kwh": sum(state.energy), "backup_input_kw": backup_input,
        "command_alive": command_alive, "pack_available": faults["pack_available"].copy(),
        "motor_available": faults["motor_available"].copy(), "faults": faults["labels"].copy(),
        "violations": violations, "bus_balance_error_kw": sum(packs)-bus_kw,
        "battery_balance_error_kw": sum(chemical)-sum(packs)-sum(losses)}
