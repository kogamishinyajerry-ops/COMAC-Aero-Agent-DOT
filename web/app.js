'use strict';

// The UI only renders solver output. No synthetic fallback values or trajectories.
const $ = (id) => document.getElementById(id);
const state = { catalog: null, run: null, comparison: null, sweep: null, index: 0, chart: 'thermal', timer: null, busy: false, view: 'control' };
const COLORS = { cyan: '#78ddd6', amber: '#edba72', violet: '#bbb1d9', gray: '#c0d0d5', red: '#f19789' };
const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const fmt = (value, decimals = 1) => finite(value) ? (Math.abs(value) < 1e-8 ? 0 : value).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) : '—';
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
const sum = (values) => values.reduce((total, value) => total + (finite(value) ? value : 0), 0);
const max = (values) => values.length ? Math.max(...values.filter(finite)) : NaN;
const min = (values) => values.length ? Math.min(...values.filter(finite)) : NaN;
const policy = () => document.querySelector('input[name="policy"]:checked').value;
const time = (seconds) => `${String(Math.floor((seconds || 0) / 60)).padStart(2, '0')}:${String(Math.floor((seconds || 0) % 60)).padStart(2, '0')}`;
const safeId = (value) => String(value || '').replace(/[^a-z0-9_-]/gi, '');
const runAmbient = (run) => run?.scenario?.ambient_c ?? run?.meta?.inputs?.ambient_c;
const metric = (id, value, unit, decimals = 1) => { $(id).innerHTML = `${fmt(value, decimals)} <small>${esc(unit)}</small>`; };

async function api(path, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120000);
  try {
    const response = await fetch(path, { method: body ? 'POST' : 'GET', headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined, signal: controller.signal });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || data.message || `HTTP ${response.status}`);
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('计算请求超时。原有结果仍保留，可以稍后重试。');
    throw error;
  } finally { clearTimeout(timeout); }
}
function setError(message = '') { $('error-banner').hidden = !message; $('error-banner').textContent = message; }
function setBusy(busy, title) {
  state.busy = busy;
  $('loading-overlay').hidden = !busy;
  if (title) $('loading-title').textContent = title;
  ['run-button', 'compare-button', 'sweep-button', 'scenario', 'design', 'ambient'].forEach((id) => { $(id).disabled = busy || !state.catalog; });
  document.querySelectorAll('input[name="policy"]').forEach((input) => { input.disabled = busy; });
  document.body.setAttribute('aria-busy', String(busy));
}
function assertRun(run) {
  if (!run || !run.meta || !run.summary || !Array.isArray(run.trace) || !run.trace.length) throw new Error('计算服务返回的数据不完整，无法展示结果。');
  return run;
}
function selectedInputs() { return { scenario_id: $('scenario').value, ambient_c: Number($('ambient').value), design_id: $('design').value, policy: policy() }; }
function inputsMatch(run) {
  if (!run) return false;
  const input = selectedInputs();
  return input.scenario_id === run.scenario.id && input.design_id === run.design.id && (runAmbient(run) == null || input.ambient_c === runAmbient(run));
}
function dirty() { $('input-dirty').hidden = !state.run || (inputsMatch(state.run) && policy() === state.run.policy.id); }
function updateInputsDescription() {
  const scenario = state.catalog?.scenarios.find((item) => item.id === $('scenario').value);
  const design = state.catalog?.designs.find((item) => item.id === $('design').value);
  $('scenario-description').textContent = scenario?.description || '';
  $('design-description').textContent = design ? `${fmt(design.mass_kg, 0)} kg 质量代理 · ${fmt(design.traction_kwh, 0)} kWh 推进储能 · ${fmt(design.backup_kwh, 1)} kWh 备份` : '';
  $('ambient-output').textContent = `${$('ambient').value} °C`;
  document.querySelectorAll('.policy-option').forEach((label) => label.classList.toggle('selected', label.querySelector('input').checked));
  dirty();
}
function setControlsFromRun(run) {
  if (state.catalog.scenarios.some((item) => item.id === run.scenario.id)) $('scenario').value = run.scenario.id;
  if (state.catalog.designs.some((item) => item.id === run.design.id)) $('design').value = run.design.id;
  if (finite(runAmbient(run))) $('ambient').value = runAmbient(run);
  const input = document.querySelector(`input[name="policy"][value="${safeId(run.policy.id)}"]`);
  if (input) input.checked = true;
  updateInputsDescription();
}
function stopPlayback() { if (state.timer) clearInterval(state.timer); state.timer = null; $('play-button').textContent = '▷'; $('play-button').setAttribute('aria-label', '播放轨迹'); }
function loadRun(run, sync = false) {
  assertRun(run); stopPlayback(); state.run = run;
  // Begin at the first fault when available, making the causal event visible.
  const firstFault = run.trace.findIndex((row) => Array.isArray(row.faults) && row.faults.length);
  state.index = firstFault >= 0 ? firstFault : 0;
  if (sync) setControlsFromRun(run);
  $('time-scrubber').max = run.trace.length - 1;
  $('time-scrubber').value = state.index;
  $('time-scrubber').disabled = false; $('play-button').disabled = false; $('export-button').disabled = false;
  renderOverview(); renderPhases(); renderFrame(); renderActions(); renderComparison(); renderEvidence(); dirty();
}

function hardChecks(run) {
  const limits = state.catalog.limits;
  const summary = run.summary;
  return [
    { label: '温度硬上限', value: summary.max_temperature_c, limit: limits.temperature_c, unit: '°C', direction: 'max', decimals: 1 },
    { label: '最低母线电压', value: summary.min_voltage_v, limit: limits.min_voltage_v, unit: 'V', direction: 'min', decimals: 1 },
    { label: '最大支路电流', value: summary.max_current_a, limit: limits.max_current_a, unit: 'A', direction: 'max', decimals: 1 },
    { label: '关键负载缺供', value: summary.unserved_essential_kwh, limit: 0, unit: 'kWh', direction: 'max', decimals: 4 }
  ].map((check) => ({ ...check, pass: finite(check.value) && finite(check.limit) ? (check.direction === 'max' ? check.value <= check.limit + 1e-6 : check.value >= check.limit - 1e-6) : null }));
}
function essentialRate(run) {
  const fractions = run.trace.filter((row) => row.essential_kw > 0).map((row) => row.served_essential_kw / row.essential_kw);
  return fractions.length ? min(fractions) * 100 : NaN;
}
function verdict(summary) {
  if (summary.solver_valid === false) return '<span class="verdict-fail">! 求解校验未通过</span>';
  if (summary.feasible === true) return '<span class="verdict-pass">✓ 满足全部约束</span>';
  if (summary.feasible === false) return '<span class="verdict-fail">! 任务不可行</span>';
  return '<span class="verdict-unknown">未报告</span>';
}
function renderOverview() {
  const run = state.run, s = run.summary, replay = run.meta.execution === 'replay';
  $('provenance').className = `badge ${replay ? 'replay' : 'live'}`;
  $('provenance').textContent = replay ? '已存结果回放' : '本次实际计算';
  $('evidence-caption').textContent = `${run.scenario.name} · ${run.design.name} · ${finite(runAmbient(run)) ? `${fmt(runAmbient(run), 0)} °C · ` : ''}${run.policy.name}`;
  $('run-meta').textContent = `v${run.meta.model_version} / ${String(run.meta.run_id || run.meta.input_hash).slice(0, 12)}`;
  const checks = hardChecks(run), hardFailed = checks.some((check) => check.pass === false);
  const feasible = s.feasible === true && s.solver_valid !== false;
  $('outcome-banner').className = `outcome-banner ${s.solver_valid === false || hardFailed ? 'fail' : (!feasible ? 'warn' : '')}`;
  $('outcome-icon').textContent = feasible ? '✓' : '!';
  $('outcome-title').textContent = s.solver_valid === false ? '求解校验未通过，不能据此得出工程结论' : (feasible ? '当前任务满足模型中的全部约束' : (hardFailed ? '存在硬约束或关键负载缺口，性能收益不能抵消' : '任务仍不可行：硬约束检查与任务完成度分别看'));
  const protection = finite(state.catalog.limits.protection_c) ? ` · 规划温度目标 ${fmt(state.catalog.limits.protection_c, 0)} °C` : '';
  $('outcome-summary').textContent = `推进缺供 ${fmt(s.unmet_propulsion_kwh, 3)} kWh · 可削减负载损失 ${fmt(s.flex_shed_kwh, 3)} kWh · 约束违反 ${fmt(s.violation_count, 0)} 次${protection}`;
  $('outcome-tag').textContent = feasible ? 'MODEL FEASIBLE' : 'CHECK CONSTRAINTS';
  metric('metric-service', essentialRate(run), '%', 1);
  $('metric-service').classList.toggle('danger', s.unserved_essential_kwh > 1e-6);
  metric('metric-temperature', s.max_temperature_c, '°C', 1);
  $('metric-temperature').classList.toggle('danger', s.max_temperature_c > state.catalog.limits.temperature_c + 1e-7);
  $('metric-temperature-note').textContent = `合成热节点 · 裕度 ${fmt(s.min_thermal_margin_c, 1)} °C / 上限 ${fmt(state.catalog.limits.temperature_c, 0)} °C`;
  metric('metric-energy', s.energy_used_kwh, 'kWh', 2);
  $('metric-energy-note').textContent = `可接入推进储能 ${fmt(s.accessible_traction_energy_kwh, 2)} kWh`;
  metric('metric-actions', Array.isArray(run.actions) ? run.actions.length : NaN, '条', 0);
  $('metric-actions-note').textContent = '求解器实际返回的决策记录';
  $('duration').textContent = time(run.trace[run.trace.length - 1].t_s);
  $('constraint-list').innerHTML = checks.map((check) => `<div class="constraint-row"><span class="check-state ${check.pass === false ? 'fail' : check.pass == null ? 'warn' : ''}">${check.pass === true ? '✓' : check.pass === false ? '!' : '?'}</span><span class="check-label">${check.label}</span><span class="check-value ${check.pass === false ? 'fail' : ''}">${fmt(check.value, check.decimals)} ${check.unit} / ${check.direction === 'max' ? '≤' : '≥'} ${fmt(check.limit, check.decimals === 4 ? 0 : check.decimals)} ${check.unit}</span></div>`).join('');
}
function renderPhases() {
  const phases = [];
  state.run.trace.forEach((row, index) => { const last = phases[phases.length - 1]; if (last?.name === row.phase) last.end = index; else phases.push({ name: row.phase, start: index, end: index }); });
  $('phase-track').innerHTML = phases.map((phase) => `<div class="phase-segment" data-start="${phase.start}" data-end="${phase.end}" data-size="${phase.end - phase.start + 1}" title="${esc(phase.name)}">${esc(phase.name)}</div>`).join('');
  document.querySelectorAll('.phase-segment').forEach((element) => { element.style.flex = element.dataset.size; });
}
function formatCooling(value) { return finite(value) ? `${fmt(value * 100, 0)}%` : '—'; }
function renderFrame() {
  const row = state.run.trace[state.index];
  $('phase-pill').textContent = row.phase || '—';
  $('current-time').textContent = time(row.t_s);
  $('time-scrubber').value = state.index;
  ['a', 'b'].forEach((side, index) => {
    $(`source-${side}-power`).textContent = `${fmt(row.pack_kw?.[index], 1)} kW`;
    $(`source-${side}-meta`).textContent = `${fmt(row.pack_voltage_v?.[index], 0)} V · SOC ${fmt((row.pack_soc?.[index] ?? NaN) * 100, 0)}%`;
    // Zero source output alone does not prove a failure; use explicit fault tokens.
    const fault = row.pack_available?.[index] === false || (row.faults || []).includes(`pack_isolated:${index}`);
    $(`source-${side}-node`).classList.toggle('failed', fault);
    $(`route-${side}`).classList.toggle('failed', fault);
  });
  ['left', 'right'].forEach((side, index) => {
    $(`motor-${side}-power`).textContent = `${fmt(row.motor_shaft_kw?.[index], 1)} kW`;
    $(`motor-${side}-meta`).textContent = `热节点 ${fmt(row.temperature_c?.[index], 1)} °C`;
    $(`motor-${side}-node`).classList.toggle('failed', row.motor_available?.[index] === false || row.temperature_c?.[index] > state.catalog.limits.temperature_c + 1e-7 || (row.faults || []).includes(`cooling_degraded:${index}`));
  });
  $('cooling-meta').textContent = `${formatCooling(row.cooling?.[0])} · ${fmt(row.fan_kw, 2)} kW`;
  metric('instant-voltage', min((row.pack_voltage_v || []).filter((value, index) => row.pack_kw?.[index] > 1e-9)), 'V', 1);
  metric('instant-current', max(row.pack_current_a || []), 'A', 1);
  metric('instant-aux', (row.served_essential_kw ?? NaN) + (row.served_flex_kw ?? NaN), 'kW', 1);
  document.querySelectorAll('.phase-segment').forEach((element) => element.classList.toggle('active', state.index >= Number(element.dataset.start) && state.index <= Number(element.dataset.end)));
  document.querySelectorAll('.log-entry').forEach((element) => element.classList.toggle('current', Math.abs(Number(element.dataset.time) - row.t_s) < state.run.meta.dt_s));
  renderChart();
}
function chartDefinition() {
  const limits = state.catalog.limits;
  const defs = {
    thermal: { unit: '°C', series: [{ name: '左通道热节点', color: COLORS.cyan, value: (row) => row.temperature_c?.[0] }, { name: '右通道热节点', color: COLORS.amber, value: (row) => row.temperature_c?.[1] }], limits: [{ value: limits.temperature_c, label: '硬上限', shade: true }, { value: limits.protection_c, label: '规划目标', shade: false }], note: '温度是合成集总热节点；88°C 为规划目标，95°C 才是硬约束。' },
    power: { unit: 'kW', series: [{ name: '推进需求', color: COLORS.gray, dash: true, value: (row) => row.demand_kw }, { name: '实际推进', color: COLORS.cyan, value: (row) => row.served_propulsion_kw }, { name: '关键负载', color: COLORS.violet, value: (row) => row.served_essential_kw }], limits: [], note: '需求与实际供给之间的缺口是推进缺供，不作为节能收益。' },
    electrical: { unit: 'A', series: [{ name: '电源 A 电流', color: COLORS.cyan, value: (row) => row.pack_current_a?.[0] }, { name: '电源 B 电流', color: COLORS.amber, value: (row) => row.pack_current_a?.[1] }], limits: [{ value: limits.max_current_a, label: '电流上限', shade: true }], note: '曲线显示支路电流；全任务最低母线电压在下方独立检查。' },
    energy: { unit: 'kWh', series: [{ name: '总推进储能（含隔离）', color: COLORS.cyan, value: (row) => row.battery_energy_kwh }, { name: '备份剩余能量', color: COLORS.violet, value: (row) => row.backup_kwh }], limits: [], note: '总储能可能包含隔离电源中无法接入的能量，不等于可用储能。' }
  };
  return defs[state.chart];
}
function renderChart() {
  if (!state.run) return;
  const def = chartDefinition(), trace = state.run.trace;
  const values = def.series.flatMap((series) => trace.map(series.value)).filter(finite);
  if (!values.length) { $('trace-chart').innerHTML = '<div class="empty-state">该指标没有有效时序数据</div>'; return; }
  const allValues = values.concat(def.limits.map((item) => item.value).filter(finite));
  let yMin = Math.min(0, ...allValues), yMax = Math.max(...allValues);
  if (state.chart === 'thermal') yMin = Math.floor(Math.max(0, Math.min(...values) - 8) / 10) * 10;
  const spread = yMax - yMin || 1; yMax += spread * .12;
  const W = 520, H = 246, pad = { top: 26, right: 17, bottom: 31, left: 47 };
  const w = W - pad.left - pad.right, h = H - pad.top - pad.bottom;
  const first = trace[0].t_s, last = trace[trace.length - 1].t_s;
  const x = (value) => pad.left + ((value - first) / (last - first || 1)) * w;
  const y = (value) => pad.top + (1 - (value - yMin) / (yMax - yMin)) * h;
  const current = trace[state.index];
  let markup = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(def.series.map((series) => series.name).join('、'))}全任务时序曲线"><title>${esc(def.unit)} 时序，数据来自实际求解结果</title><defs><clipPath id="plot-clip"><rect x="${pad.left}" y="${pad.top}" width="${w}" height="${h}"/></clipPath></defs>`;
  def.limits.filter((item) => item.shade && finite(item.value)).forEach((item) => { markup += `<rect x="${pad.left}" y="${pad.top}" width="${w}" height="${Math.max(0, y(item.value) - pad.top)}" fill="#edba72" opacity=".045"/>`; });
  for (let tick = 0; tick <= 4; tick++) {
    const value = yMin + (yMax - yMin) * tick / 4;
    markup += `<line class="grid-line" x1="${pad.left}" x2="${W - pad.right}" y1="${y(value)}" y2="${y(value)}"/><text class="axis-label" text-anchor="end" x="${pad.left - 10}" y="${y(value) + 3}">${fmt(value, state.chart === 'energy' ? 1 : 0)}</text>`;
    const t = first + (last - first) * tick / 4;
    markup += `<text class="axis-label" text-anchor="middle" x="${x(t)}" y="${H - 8}">${time(t)}</text>`;
  }
  markup += `<text class="axis-label" x="${pad.left}" y="12">${def.unit}</text>`;
  def.limits.filter((item) => finite(item.value)).forEach((item) => { markup += `<line class="limit-line" x1="${pad.left}" x2="${W - pad.right}" y1="${y(item.value)}" y2="${y(item.value)}"/><text class="axis-label" text-anchor="end" x="${W - pad.right - 3}" y="${y(item.value) - 5}" fill="#b3946f" font-size="9px">${item.label} ${fmt(item.value, 0)}</text>`; });
  def.series.forEach((series) => {
    let move = true;
    const path = trace.map((row) => { const value = series.value(row); if (!finite(value)) { move = true; return ''; } const point = `${move ? 'M' : 'L'}${x(row.t_s).toFixed(2)},${y(value).toFixed(2)}`; move = false; return point; }).join(' ');
    markup += `<path class="data-line" d="${path}" stroke="${series.color}" ${series.dash ? 'stroke-dasharray="5 5"' : ''} clip-path="url(#plot-clip)"/>`;
  });
  markup += `<line class="time-cursor" x1="${x(current.t_s)}" x2="${x(current.t_s)}" y1="${pad.top}" y2="${H - pad.bottom}"/>`;
  def.series.forEach((series) => { const value = series.value(current); if (finite(value)) markup += `<circle cx="${x(current.t_s)}" cy="${y(value)}" r="3" fill="${series.color}" stroke="#142128" stroke-width="1.5"/>`; });
  markup += '</svg>';
  $('trace-chart').innerHTML = markup;
  $('chart-legend').innerHTML = def.series.map((series) => `<span><i data-color="${series.color}"></i>${series.name} ${fmt(series.value(current), 1)}</span>`).join('');
  document.querySelectorAll('#chart-legend i').forEach((element) => { element.style.backgroundColor = element.dataset.color; });
  $('chart-note').textContent = def.note;
}
function actionLabel(action) {
  const labels = { fault: '故障注入', control: '控制动作', decision: '控制决策', planner: '规划器决策', baseline: '固定规则动作', protection: '热保护动作', phase: '任务阶段切换', initial: '初始决策', action: '动作更新', dispatch: '风扇 / 功率分配' };
  return labels[action.type] || action.type || '决策记录';
}
function readable(value) { return typeof value === 'string' ? value : JSON.stringify(value); }
function renderActions() {
  const actions = state.run.actions || [];
  $('action-count').textContent = `${actions.length} 条记录`;
  $('action-log').innerHTML = actions.length ? actions.map((action) => `<article class="log-entry ${/fault|failure/i.test(action.type) ? 'fault' : ''}" data-time="${Number(action.t_s) || 0}"><div class="log-time">${time(action.t_s)}</div><div><h3>${esc(actionLabel(action))}</h3><p>${esc(action.reason || '未提供原因说明')}</p>${action.details ? `<div class="log-values">${esc(readable(action.details))}</div>` : ''}</div></article>`).join('') : '<div class="empty-state small">求解器没有返回动作记录</div>';
}
function renderComparison() {
  if (!state.comparison) {
    $('comparison-content').innerHTML = '<div class="comparison-placeholder"><span>⇄</span><div><h3>收益需要一个公平的参照</h3><p>点击「公平比较两种策略」，并列检查约束、关键负载与能量代价。</p></div></div>';
    return;
  }
  const { baseline, planner } = state.comparison, b = baseline.summary, p = planner.summary;
  const rows = [
    ['任务可行性', verdict(b), verdict(p), '独立判定，不用收益抵消'],
    ['关键负载缺供', `${fmt(b.unserved_essential_kwh, 4)} kWh`, `${fmt(p.unserved_essential_kwh, 4)} kWh`, '越小越好'],
    ['推进缺供', `${fmt(b.unmet_propulsion_kwh, 3)} kWh`, `${fmt(p.unmet_propulsion_kwh, 3)} kWh`, '越小越好'],
    ['首次推进缺供', finite(b.first_propulsion_shortfall_s) ? time(b.first_propulsion_shortfall_s) : '全程无缺供', finite(p.first_propulsion_shortfall_s) ? time(p.first_propulsion_shortfall_s) : '全程无缺供', '延后缺供不等于减少总缺供'],
    ['已交付推进轴功', `${fmt(b.served_propulsion_kwh, 2)} kWh`, `${fmt(p.served_propulsion_kwh, 2)} kWh`, '消耗更少也可能因为少做了功'],
    ['最低热裕度', `${fmt(b.min_thermal_margin_c, 1)} °C`, `${fmt(p.min_thermal_margin_c, 1)} °C`, '相对温度硬上限'],
    ['任务能量消耗', `${fmt(b.energy_used_kwh, 2)} kWh`, `${fmt(p.energy_used_kwh, 2)} kWh`, '需同时检查任务完成度'],
    ['风扇能量消耗', `${fmt(b.fan_energy_kwh, 3)} kWh`, `${fmt(p.fan_energy_kwh, 3)} kWh`, '合成强制风冷的电力代价'],
    ['可削减负载损失', `${fmt(b.flex_shed_kwh, 3)} kWh`, `${fmt(p.flex_shed_kwh, 3)} kWh`, '服务水平代价']
  ];
  const deltaProp = p.unmet_propulsion_kwh - b.unmet_propulsion_kwh;
  const deltaEnergy = p.energy_used_kwh - b.energy_used_kwh;
  const deltaFlex = p.flex_shed_kwh - b.flex_shed_kwh;
  let conclusion = p.feasible && !b.feasible ? '本次输入下，规划器满足任务约束，固定规则未满足。' : (!p.feasible && !b.feasible ? '本次输入下，两种策略都未满足任务约束，不能宣布优化成功。' : (b.feasible && !p.feasible ? '本次输入下，固定规则满足任务约束，规划器未满足。' : '本次输入下，两种策略都满足任务约束，应继续比较代价。'));
  conclusion += ` 相对固定规则，规划器的推进缺供${deltaProp < 0 ? '减少' : '增加'} ${fmt(Math.abs(deltaProp), 3)} kWh，能量消耗${deltaEnergy < 0 ? '减少' : '增加'} ${fmt(Math.abs(deltaEnergy), 3)} kWh，可削减负载损失${deltaFlex < 0 ? '减少' : '增加'} ${fmt(Math.abs(deltaFlex), 3)} kWh。`;
  if (deltaEnergy < -1e-6 && (p.served_propulsion_kwh < b.served_propulsion_kwh - 1e-6 || p.unserved_essential_kwh > b.unserved_essential_kwh + 1e-6 || p.flex_shed_kwh > b.flex_shed_kwh + 1e-6)) conclusion += ' 能耗较低同时伴随已交付服务减少，不能据此宣称节能优化成功。';
  if (b.solver_valid === false || p.solver_valid === false) conclusion = '至少一个结果的求解校验未通过，以下指标仅用于排查问题，不作优劣结论。';
  $('comparison-content').innerHTML = `<table class="comparison-table"><thead><tr><th>检查项</th><th class="policy-head">固定规则 <small>Baseline</small></th><th class="policy-head planner-column">受约束规划器</th><th>如何理解</th></tr></thead><tbody>${rows.map((row) => `<tr><td>${row[0]}</td><td>${row[1]}</td><td class="planner-column">${row[2]}</td><td>${row[3]}</td></tr>`).join('')}</tbody></table><p class="comparison-conclusion">${esc(conclusion)}</p>`;
}
function renderEvidence() {
  const run = state.run;
  const evidence = run ? { execution: run.meta.execution, meta: run.meta, scenario: run.scenario, design: run.design, policy: run.policy, summary: run.summary, validation: run.validation, limits: state.catalog.limits, sources: state.catalog.sources } : state.catalog;
  $('evidence-details').textContent = JSON.stringify(evidence, null, 2);
  const planner = state.catalog?.policies?.find((item) => item.id === 'planner');
  if (planner?.description) $('planner-explanation').textContent = `${planner.description} 它不是 LLM 智能体，不表示已完成陌生任务泛化验证。`;
}
async function compute(compare = false) {
  if (state.busy) return;
  stopPlayback(); setError(); setBusy(true, compare ? '正在用相同输入比较两种策略' : '正在调用确定性求解器');
  const input = selectedInputs();
  try {
    const response = await api(compare ? '/api/compare' : '/api/run', input);
    if (compare) { assertRun(response.baseline); assertRun(response.planner); state.comparison = response; loadRun(response[policy()]); }
    else { assertRun(response); state.comparison = null; loadRun(response); }
  } catch (error) { setError(`未能完成计算：${error.message}。页面保留最近一次成功结果。`); }
  finally { setBusy(false); }
}
function switchView(view) {
  state.view = view; $('control-view').hidden = view !== 'control'; $('design-view').hidden = view !== 'design';
  document.querySelectorAll('.nav-tab').forEach((button) => { const active = button.dataset.view === view; button.classList.toggle('active', active); if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current'); });
  $('workspace-title').textContent = view === 'design' ? '更好的控制，不能替代合理的设计。' : '供得上电，也要散得了热。';
  $('workspace-subtitle').textContent = view === 'design' ? '固定硬件逐项计算。让质量、储能和冷却能力的取舍变得可见。' : '同一任务、同一模型。看清控制动作如何改变系统结果。';
  if (view !== 'control') stopPlayback();
}
async function computeSweep() {
  if (state.busy) return;
  stopPlayback(); setError(); setBusy(true, '正在逐一计算固定硬件方案');
  try {
    const response = await api('/api/sweep', { scenario_id: $('scenario').value, ambient_c: Number($('ambient').value) });
    if (!Array.isArray(response.results) || !response.results.length) throw new Error('选型结果为空');
    state.sweep = response; renderSweep();
  } catch (error) { setError(`未能完成选型计算：${error.message}`); }
  finally { setBusy(false); }
}
function renderSweep() {
  const result = state.sweep, rows = result.results;
  const feasible = rows.filter((row) => row.summary.feasible && row.summary.solver_valid !== false);
  const lightest = feasible.length ? feasible.reduce((a, b) => a.design.mass_kg <= b.design.mass_kg ? a : b) : null;
  const intro = lightest ? `当前枚举的 ${rows.length} 个方案中，${feasible.length} 个满足任务约束；其中质量代理最低的是「${lightest.design.name}」(${fmt(lightest.design.mass_kg, 0)} kg)。这只是在已枚举方案与当前合成任务中的比较。` : `当前枚举的 ${rows.length} 个方案均未满足任务约束。应检查故障、任务需求与可用动作范围，不能在这些方案中宣布可行赢家。`;
  $('sweep-content').innerHTML = `<div class="panel sweep-message"><strong>${esc(result.scenario?.name || $('scenario').selectedOptions[0]?.textContent || '')}</strong> · ${fmt(result.scenario?.ambient_c ?? Number($('ambient').value), 0)} °C · 受约束规划器<br>${esc(intro)}</div><div class="sweep-grid">${rows.map((row) => `<article class="sweep-card ${row.design.id === $('design').value ? 'selected' : ''}"><div class="tiny-label">FIXED HARDWARE / ${esc(row.design.id)}</div><h3>${esc(row.design.name)}</h3><p class="design-caption">推进储能 ${fmt(row.design.traction_kwh, 0)} kWh · 备份 ${fmt(row.design.backup_kwh, 1)} kWh<br>冷却能力比例 ${fmt(row.design.cooling_scale, 2)}×</p>${verdict(row.summary)}<div class="design-mass">${fmt(row.design.mass_kg, 0)} <small>kg · 质量代理</small></div><dl class="sweep-facts"><div><dt>推进缺供</dt><dd>${fmt(row.summary.unmet_propulsion_kwh, 3)} kWh</dd></div><div><dt>任务能量消耗</dt><dd>${fmt(row.summary.energy_used_kwh, 2)} kWh</dd></div><div><dt>最低热裕度</dt><dd>${fmt(row.summary.min_thermal_margin_c, 1)} °C</dd></div><div><dt>关键负载缺供</dt><dd>${fmt(row.summary.unserved_essential_kwh, 4)} kWh</dd></div></dl><button class="button secondary choose-design" data-design="${esc(row.design.id)}">用此方案重新计算 <span>↗</span></button></article>`).join('')}</div><section class="panel sweep-chart-panel"><div class="panel-heading"><div><span class="section-index">TRADE-OFF /</span><h2>质量与任务缺供</h2></div><span class="tiny-label">每一点对应一次实际求解</span></div><div id="tradeoff-chart" class="tradeoff-chart"></div><p class="chart-note">横轴为简化质量代理；纵轴为推进缺供。青色：任务可行；红色：任务不可行。位置不代表全局最优。</p></section><section class="panel sweep-message sweep-note">${esc(result.note || '每个方案在单次运行中硬件固定。')}<br>质量代理只用于这个模型内部的相对比较，不代表真实装机质量、真实续航或适航性能。</section>`;
  document.querySelectorAll('.choose-design').forEach((button) => button.addEventListener('click', () => { $('design').value = button.dataset.design; document.querySelector('input[name="policy"][value="planner"]').checked = true; updateInputsDescription(); switchView('control'); compute(false); }));
  renderTradeoff(rows);
}
function renderTradeoff(rows) {
  const W = 900, H = 260, pad = { left: 65, right: 70, top: 30, bottom: 43 };
  const masses = rows.map((row) => row.design.mass_kg).filter(finite), shortfalls = rows.map((row) => row.summary.unmet_propulsion_kwh).filter(finite);
  if (!masses.length || !shortfalls.length) { $('tradeoff-chart').innerHTML = '<div class="empty-state">选型数据缺少质量或缺供指标</div>'; return; }
  const low = min(masses), high = max(masses), spread = high - low || 10;
  const xMin = low - spread * .14, xMax = high + spread * .14, yMax = Math.max(...shortfalls, .01) * 1.2;
  const x = (value) => pad.left + (value - xMin) / (xMax - xMin) * (W - pad.left - pad.right);
  const y = (value) => H - pad.bottom - value / yMax * (H - pad.top - pad.bottom);
  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="实际计算方案的质量与推进缺供对比"><title>质量代理与推进缺供，所有点均来自选型计算</title>`;
  for (let i = 0; i <= 4; i++) { const value = yMax * i / 4; svg += `<line x1="${pad.left}" x2="${W - pad.right}" y1="${y(value)}" y2="${y(value)}" stroke="#2b3a41"/><text text-anchor="end" x="${pad.left - 12}" y="${y(value) + 3}">${fmt(value, 2)}</text>`; const mass = xMin + (xMax - xMin) * i / 4; svg += `<text text-anchor="middle" x="${x(mass)}" y="${H - 20}">${fmt(mass, 0)}</text>`; }
  svg += `<text x="${pad.left}" y="14">推进缺供 / kWh</text><text text-anchor="end" x="${W - pad.right}" y="${H - 2}">质量代理 / kg</text>`;
  rows.forEach((row, index) => { if (!finite(row.design.mass_kg) || !finite(row.summary.unmet_propulsion_kwh)) return; const color = row.summary.feasible && row.summary.solver_valid !== false ? COLORS.cyan : COLORS.red; svg += `<circle cx="${x(row.design.mass_kg)}" cy="${y(row.summary.unmet_propulsion_kwh)}" r="7" fill="${color}" fill-opacity=".2" stroke="${color}" stroke-width="2"/><text x="${x(row.design.mass_kg)}" y="${y(row.summary.unmet_propulsion_kwh) - 14 - (index % 2) * 3}" text-anchor="middle" fill="${color}">${esc(row.design.name)}</text>`; });
  $('tradeoff-chart').innerHTML = svg + '</svg>';
}
function downloadEvidence() {
  const value = state.view === 'design' && state.sweep ? state.sweep : (state.comparison || state.run);
  if (!value) return;
  const data = JSON.stringify(value, null, 2), url = URL.createObjectURL(new Blob([data], { type: 'application/json' }));
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = `power-thermal-${state.view === 'design' ? 'design-sweep' : 'evidence'}-${safeId(state.run?.meta?.run_id || 'run')}.json`; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 500);
}
function bindEvents() {
  $('scenario').addEventListener('change', () => { const item = state.catalog.scenarios.find((scenario) => scenario.id === $('scenario').value); if (finite(item?.ambient_c)) $('ambient').value = item.ambient_c; updateInputsDescription(); });
  $('design').addEventListener('change', updateInputsDescription);
  $('ambient').addEventListener('input', updateInputsDescription);
  document.querySelectorAll('input[name="policy"]').forEach((input) => input.addEventListener('change', () => { updateInputsDescription(); if (state.comparison && inputsMatch(state.comparison[policy()])) loadRun(state.comparison[policy()]); }));
  $('run-button').addEventListener('click', () => compute(false));
  $('compare-button').addEventListener('click', () => compute(true));
  $('sweep-button').addEventListener('click', computeSweep);
  $('export-button').addEventListener('click', downloadEvidence);
  $('time-scrubber').addEventListener('input', () => { stopPlayback(); state.index = Number($('time-scrubber').value); renderFrame(); });
  $('play-button').addEventListener('click', () => {
    if (state.timer) { stopPlayback(); return; }
    if (!state.run) return;
    if (state.index >= state.run.trace.length - 1) state.index = 0;
    $('play-button').textContent = 'Ⅱ'; $('play-button').setAttribute('aria-label', '暂停轨迹');
    state.timer = setInterval(() => { state.index = Math.min(state.index + Math.max(1, Math.round(state.run.trace.length / 180)), state.run.trace.length - 1); renderFrame(); if (state.index >= state.run.trace.length - 1) stopPlayback(); }, 150);
  });
  document.querySelectorAll('[data-chart]').forEach((button) => button.addEventListener('click', () => { state.chart = button.dataset.chart; document.querySelectorAll('[data-chart]').forEach((item) => item.classList.toggle('active', item === button)); renderChart(); }));
  document.querySelectorAll('.nav-tab').forEach((button) => button.addEventListener('click', () => switchView(button.dataset.view)));
  $('model-details-link').addEventListener('click', () => { $('model-evidence').querySelector('details').open = true; $('model-evidence').scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' }); });
  window.addEventListener('pagehide', stopPlayback);
}
async function boot() {
  bindEvents();
  try {
    state.catalog = await api('/api/catalog');
    if (!Array.isArray(state.catalog.scenarios) || !Array.isArray(state.catalog.designs) || !state.catalog.limits) throw new Error('场景目录格式不完整');
    $('scenario').innerHTML = state.catalog.scenarios.map((item) => `<option value="${esc(item.id)}">${esc(item.name)}</option>`).join('');
    $('design').innerHTML = state.catalog.designs.map((item) => `<option value="${esc(item.id)}">${esc(item.name)}</option>`).join('');
    const range = state.catalog.ambient_range_c;
    if (Array.isArray(range) && range.length === 2) { $('ambient').min = range[0]; $('ambient').max = range[1]; }
    $('ambient-min').textContent = `${$('ambient').min} °C`; $('ambient-max').textContent = `${$('ambient').max} °C`;
    if (finite(state.catalog.scenarios[0]?.ambient_c)) $('ambient').value = state.catalog.scenarios[0].ambient_c;
    updateInputsDescription(); setBusy(false); renderEvidence();
    if (state.catalog.replay_url) {
      try { const replay = await api(state.catalog.replay_url); assertRun(replay.baseline); assertRun(replay.planner); state.comparison = replay; loadRun(replay[policy()], true); }
      catch (error) { setError(`预存回放暂不可用：${error.message}。可以点击计算按钮获取新结果。`); }
    }
  } catch (error) { state.catalog = null; setBusy(false); setError(`未连接到本地计算服务：${error.message}。请通过项目 Python 服务打开本页，不能仅双击 HTML 文件。`); }
}
boot();
