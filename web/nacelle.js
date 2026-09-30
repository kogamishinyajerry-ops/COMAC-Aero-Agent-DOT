/* X-57 Mod II: dependency-free triangle renderer and revision-safe API client.
   The viewport is a geometry reconstruction. It is never a CFD visualization. */
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const $$ = selector => [...document.querySelectorAll(selector)];
  const state = {revision: 0, request: 0, controller: null, geometry: null, result: null, catalog: null,
    mode: 'assembled', selected: 'motor_winding', dirty: false, busy: false, exportRevision: -1};
  const finite = x => typeof x === 'number' && Number.isFinite(x);
  const fixed = (x, n = 1) => finite(x) ? x.toFixed(n) : '—';
  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
  const escapeHTML = text => String(text).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const labels = {
    motor_winding: ['电机定子与冷却槽', 'CRUISE MOTOR / STATOR', '来流经过定子冷却槽，带走绕组损耗热，再与电机旁通空气混合。', '定子绕组节点温度'],
    motor_magnet: ['永磁转子与气隙', 'CRUISE MOTOR / ROTOR', '外转子围绕定子旋转。磁体节点单独记热，温度上限与绕组不同。', '转子磁体节点温度'],
    cmc_left_hv: ['左侧 CMC · 高压散热器', 'LEFT CMC / HIGH VOLTAGE', '倾斜布置的控制器，高压侧鳍片接收电机下游混合空气。流道尺寸同时影响分流和换热。', '高压侧 FET 代理温度'],
    cmc_right_hv: ['右侧 CMC · 高压散热器', 'RIGHT CMC / HIGH VOLTAGE', '并列的第二组控制器，有独立高压侧冷却支路。上下游压差共同决定通过鳍片的流量。', '高压侧 FET 代理温度'],
    cmc_left_lv: ['左侧 CMC · 低压背板', 'LEFT CMC / LOW VOLTAGE', '顶部耳形进气口引入独立新鲜空气，冷却低压侧背板。CPU 和 AC/DC 节点分别记热。', '低压背板节点温度'],
    cmc_right_lv: ['右侧 CMC · 低压背板', 'RIGHT CMC / LOW VOLTAGE', '独立新鲜空气支路冷却低压背板，不直接套用高压鳍片温度。', '低压背板节点温度'],
    cmc_left_cpu: ['左侧 CMC · CPU 代理节点', 'LEFT CMC / CPU', '电子板形状与位置为示意。CPU 到低压背板的热接触与损耗拆分为明确推定。', 'CPU 代理节点温度'],
    cmc_right_cpu: ['右侧 CMC · CPU 代理节点', 'RIGHT CMC / CPU', '电子板形状与位置为示意。CPU 到低压背板的热接触与损耗拆分为明确推定。', 'CPU 代理节点温度'],
    cmc_left_acdc: ['左侧 CMC · AC/DC 代理节点', 'LEFT CMC / AC–DC', 'AC/DC 板独立热节点连接低压背板，器件形状、接触热阻和损耗拆分均为推定。', 'AC/DC 代理节点温度'],
    cmc_right_acdc: ['右侧 CMC · AC/DC 代理节点', 'RIGHT CMC / AC–DC', 'AC/DC 板独立热节点连接低压背板，器件形状、接触热阻和损耗拆分均为推定。', 'AC/DC 代理节点温度']
  };
  const componentNames = {cowling_upper:'可拆上整流罩',cowling_lower:'下整流罩与排气口',cowling_tail:'后整流尾锥',local_wing:'机翼局部 · 示意翼型',propeller_spinner:'螺旋桨桨帽',propeller_hub:'三叶桨毂',motor_shaft:'电机轴',motor_rotor:'外转子杯形壳体',motor_stator:'定子齿与支撑',motor_front_bearing:'前轴承座',motor_rear_mount:'电机后安装法兰',motor_bypass_shroud:'电机环形旁通导流罩',main_inlet_lip:'主环形进气口',motor_upper_exhaust:'电机顶部排气罩',lv_inlet_left:'左侧耳形进气口',lv_inlet_right:'右侧耳形进气口',cmc_left_case:'左侧 CMC 机壳',cmc_right_case:'右侧 CMC 机壳'};
  const geometryControls = [
    {key:'main_inlet_height_mm', name:'外环进气高度', index:'01', note:'改变电机外侧旁通入口', unit:'mm'},
    {key:'upper_inlet_height_mm', name:'低压新风入口', index:'02', note:'独立冷却 CPU 与 AC/DC', unit:'mm'},
    {key:'hv_fin_count', name:'高压侧鳍片数', index:'03', note:'每组 CMC 的鳍片数量', unit:'片'},
    {key:'motor_bypass_gap_mm', name:'电机旁通间隙', index:'04', note:'改变冷却与旁通分配', unit:'mm'}
  ];
  const boundaryLabels = {airspeed_m_s:'来流速度 · m/s',ambient_c:'环境温度 · °C',density_kg_m3:'空气密度 · kg/m³',ram_recovery:'电机内部入口动压恢复',bypass_ram_recovery:'外环旁通入口动压恢复',lv_ram_recovery:'低压侧动压恢复',main_propeller_pressure_pa:'内入口桨诱导增压 · Pa',bypass_propeller_pressure_pa:'旁通入口桨诱导增压 · Pa',lv_propeller_pressure_pa:'低压入口桨诱导增压 · Pa',exhaust_suction_coefficient:'短舱排气抽吸系数',motor_exhaust_suction_coefficient:'电机排气抽吸系数',heat_scale:'热负荷比例',loss_multiplier:'支路阻力倍率',contact_multiplier:'接触热阻倍率'};

  function setError(message) { $('nacelle-error').textContent = message || ''; $('nacelle-error').hidden = !message; }
  async function api(path, body, signal) {
    const response = await fetch(path, {method: body ? 'POST' : 'GET', headers: body ? {'Content-Type':'application/json'} : {}, body: body ? JSON.stringify(body) : undefined, signal});
    if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(error.error || `请求失败 (${response.status})`); }
    return response.json();
  }
  const geometryFingerprint = g => g?.fingerprint || g?.metrics?.fingerprint || g?.geometry_fingerprint;
  const resultFingerprint = r => geometryFingerprint(r?.geometry) || r?.geometry_fingerprint || r?.metrics?.fingerprint || r?.provenance?.geometry_fingerprint;
  function payload() {
    const geometry = {...state.catalog.geometry.defaults};
    geometryControls.forEach(({key}) => { geometry[key] = Number($(`geom-${key}`).value); });
    const boundary = {...state.catalog.boundary.defaults};
    $$('#boundary-fields [data-boundary]').forEach(input => { boundary[input.dataset.boundary] = input.tagName === 'SELECT' ? input.value : Number(input.value); });
    return {geometry, boundary};
  }
  function renderFields(catalog) {
    geometryControls.forEach(info => {
      const spec = catalog.geometry.parameters.find(p => p.key === info.key);
      if (!spec) throw new Error(`几何目录缺少 ${info.key}`);
      const div = document.createElement('div'); div.className = 'geometry-field';
      div.innerHTML = `<label for="geom-${info.key}"><span>${info.name}</span><span>${info.index}</span></label><div class="field-value"><input id="geom-${info.key}" type="number" min="${spec.min}" max="${spec.max}" step="${spec.step}" value="${spec.default}" required><small>${info.unit}</small></div><input aria-label="${info.name}滑块" data-range="${info.key}" type="range" min="${spec.min}" max="${spec.max}" step="${spec.step}" value="${spec.default}"><small>${info.note}</small>`;
      $('geometry-fields').append(div);
      const input = $(`geom-${info.key}`), slider = div.querySelector('[type=range]');
      input.addEventListener('input', () => { slider.value = input.value; invalidate(); });
      slider.addEventListener('input', () => { input.value = slider.value; invalidate(); });
    });
    const fields = catalog.boundary.fields || catalog.boundary.parameters || [];
    const normalized = Array.isArray(fields) ? fields : Object.entries(fields).map(([key,v]) => ({key,...v}));
    const defaults = catalog.boundary.defaults || {};
    normalized.forEach(spec => {
      const key = spec.key || spec.id || spec.name;
      if (!key || key === 'heat_load') return;
      const label = document.createElement('label');
      if (spec.type === 'enum') {
        label.innerHTML = `<span>${escapeHTML(boundaryLabels[key] || spec.label || key)}</span><select id="boundary-${key}" data-boundary="${key}">${spec.options.map(option => `<option value="${escapeHTML(option)}">${escapeHTML(option)}</option>`).join('')}</select>`;
        $('boundary-fields').append(label); label.querySelector('select').value = defaults[key] ?? spec.default;
        label.querySelector('select').addEventListener('change', invalidate); return;
      }
      label.innerHTML = `<span>${escapeHTML(boundaryLabels[key] || spec.label || key)}</span><input id="boundary-${key}" data-boundary="${key}" type="number" step="${spec.step || 'any'}" ${finite(spec.min) ? `min="${spec.min}"` : ''} ${finite(spec.max) ? `max="${spec.max}"` : ''} value="${defaults[key] ?? spec.default ?? 0}" required>`;
      $('boundary-fields').append(label); label.querySelector('input').addEventListener('input', invalidate);
    });
    // Catalogs with only defaults still produce editable, schema-matched numeric fields.
    if (!normalized.length) Object.entries(defaults).forEach(([key,value]) => {
      if (!finite(value)) return;
      const label = document.createElement('label'); label.innerHTML = `<span>${escapeHTML(boundaryLabels[key] || key)}</span><input id="boundary-${key}" data-boundary="${key}" type="number" step="any" value="${value}" required>`;
      $('boundary-fields').append(label); label.querySelector('input').addEventListener('input', invalidate);
    });
    const heat = document.createElement('label'); heat.innerHTML = '<span>公开损耗工况</span><select id="boundary-heat_load" data-boundary="heat_load"><option value="peak">峰值功率 · PEAK</option><option value="mcp">最大连续功率 · MCP</option></select>';
    $('boundary-fields').append(heat); $('boundary-heat_load').value = defaults.heat_load || 'peak'; $('boundary-heat_load').addEventListener('change', invalidate);
    const names = {reduced_load_screening:'0.25×损耗 · 低负荷网络演示',initial_climb:'推定来流 · 初始爬升',source_pressure_initial_climb:'公开压力增量参考 · 初始爬升',cruise_climb:'推定来流 · 持续爬升',dash:'推定来流 · 高速工况',no_ram:'无强制流动 · 边界失效演示'};
    const preset = document.createElement('label'); preset.className = 'boundary-preset';
    preset.innerHTML = `<span>边界参考方案</span><select id="boundary-preset">${(catalog.boundary.presets || []).map(p => `<option value="${escapeHTML(p.id)}">${escapeHTML(names[p.id] || p.id)}</option>`).join('')}<option value="custom">自定义边界</option></select><small id="boundary-preset-note">所有工况都未做真实飞机校准</small>`;
    $('boundary-fields').prepend(preset);
    $$('#boundary-fields [data-boundary]').forEach(input => input.addEventListener('change',()=>{$('boundary-preset').value='custom';$('boundary-preset-note').textContent='自定义边界；未做真实飞机校准';}));
    $('boundary-preset').addEventListener('change',()=>{
      const selected=(catalog.boundary.presets || []).find(p=>p.id===$('boundary-preset').value);if(!selected)return;
      $$('#boundary-fields [data-boundary]').forEach(input=>{input.value=selected.boundary[input.dataset.boundary] ?? defaults[input.dataset.boundary];});
      $('boundary-preset-note').textContent=selected.id==='source_pressure_initial_climb'?'采用公开表 7 压力增量，含对称化与边界近似；未拟合温度，仍需检查适用域':selected.id==='reduced_load_screening'?'主动选择 0.25×公开损耗用于网络演示；不是 25% 飞机功率，未拟合真实损耗曲线':'推定边界下的研究工况；未做真实飞机校准';
      invalidate();
    });
  }
  function invalidate() {
    state.revision++; state.dirty = true; state.result = null; state.exportRevision = -1;
    $('thermal-results').hidden = true; $('result-warning').hidden = true; $('result-loading').hidden = false;
    $('result-loading').textContent = '输入已更改，等待新几何与热网络';
    $('stale-banner').hidden = !state.geometry; $('export-json').disabled = true; $('export-step').disabled = true;
    $('evidence-json').textContent = '输入已更改，旧证据已失效。重新计算后显示同一几何的证据。';
    $('fingerprint-status').textContent = '旧几何，等待重新计算'; $('compute-status').textContent = '参数已更改';
    $('thermal-legend').hidden = true; $('network-facts').replaceChildren(); updateInspector(); renderer.requestDraw();
  }
  function busy(on) {
    state.busy = on; $('evaluate-button').disabled = on || !state.catalog;
    $('evaluate-button').innerHTML = on ? '正在计算…' : '重建并计算 <span>↗</span>';
    $('cancel-button').hidden = !on;
  }
  function cancel() {
    state.request++; state.controller?.abort(); state.controller = null; busy(false); invalidate();
    $('compute-status').textContent = '本次计算已取消'; $('result-loading').textContent = '已取消，没有采用中途结果';
    $('scene-loading').hidden = true;
  }
  async function evaluate() {
    if (state.busy) return;
    if (!$('nacelle-form').reportValidity()) return;
    if ($$('#boundary-fields input').some(input => !input.reportValidity())) { $('boundary-details').open = true; return; }
    const revision = state.revision, request = ++state.request, data = payload();
    state.controller = new AbortController(); const signal = state.controller.signal;
    busy(true); setError(null); state.result = null; state.exportRevision = -1;
    $('thermal-results').hidden = true; $('result-loading').hidden = false; $('result-loading').textContent = '生成装配并求解稳态网络…';
    $('result-warning').hidden = true; $('export-json').disabled = true; $('export-step').disabled = true; $('compute-status').textContent = '几何 → 流量 → 温度';
    const current = () => request === state.request && revision === state.revision && !signal.aborted;
    try {
      const geometry = await api('/api/nacelle/geometry', {geometry:data.geometry}, signal);
      if (!current()) return;
      const result = await api('/api/nacelle/evaluate', data, signal);
      if (!current()) return;
      const a = geometryFingerprint(geometry), b = resultFingerprint(result);
      if (!a || !b || a !== b) throw new Error('几何与计算证据指纹不一致，本次结果未采用');
      state.geometry = geometry; state.result = result; state.dirty = false; state.exportRevision = revision;
      renderer.setGeometry(geometry); $('scene-loading').hidden = true; $('stale-banner').hidden = true;
      $('thermal-results').hidden = false; $('result-loading').hidden = true;
      $('geometry-fingerprint').textContent = a; $('fingerprint-status').textContent = '三维预览与求解证据一致';
      $('evidence-json').textContent = JSON.stringify({assembly_fingerprint:a, assembly_provenance:geometry.provenance, component_provenance:geometry.components.map(({id,thermal_node,source}) => ({id,thermal_node,source})), evaluation:result}, null, 2);
      $('export-json').disabled = false; const cad = geometry.cad || {}, kernel = state.catalog.geometry.kernel_available;
      $('export-step').disabled = !cad.step_available;
      $('step-status').textContent = cad.stored_step_available && cad.verification === 'verified_baseline_BRep' ? '当前几何匹配已验证缓存 STEP；无 CadQuery 也可下载' : cad.stored_step_available ? '缓存 STEP 未确认通过完整验证，请查看证据' : kernel ? '从当前参数生成具名实体，导出前再次核对输入版本' : '自定义 STEP 需 CadQuery；默认重建 STEP 可直接下载';
      $('compute-status').textContent = '几何与证据已同步';
      renderResult(); updateInspector(); renderer.requestDraw();
    } catch (error) {
      if (error.name === 'AbortError' || !current()) return;
      setError(error.message); $('result-loading').textContent = '本次计算未完成，请检查输入后重试';
      $('scene-loading').hidden = true; $('compute-status').textContent = '计算未完成'; state.dirty = true;
      $('stale-banner').hidden = !state.geometry;
    } finally {
      if (request === state.request) { state.controller = null; busy(false); if (revision !== state.revision) $('compute-status').textContent = '新输入尚未计算'; }
    }
  }
  function thermalNodes() { return state.result?.thermal?.components || {}; }
  function selectedComponent() { return state.geometry?.components.find(c => c.id === state.selected || c.thermal_node === state.selected); }
  function updateInspector() {
    const component = selectedComponent(), id = component?.thermal_node || state.selected;
    const entry = labels[id];
    $('part-name').textContent = entry?.[0] || componentNames[component?.id] || component?.label || '选择一个装配部件';
    $('part-type').textContent = entry?.[1] || `${(component?.group || 'ASSEMBLY').toUpperCase()} / RECONSTRUCTION`;
    $('part-description').textContent = entry?.[2] || '此结构件由公开外形与拓扑推定重建。未给它分配热节点，不显示虚构温度。';
    $('temperature-title').textContent = entry?.[3] || '此部件未分配热节点';
    $('selection-note').textContent = component ? `${component.id} · ${component.thermal_node ? '已连接热节点' : '结构 / 外形实体'}` : '点击三维部件可查看对应证据';
    $('part-source').title = component?.source?.note || '';
    $('part-source').textContent = component?.source?.classification === 'public_source' ? '公开来源拓扑 · 尺寸推定' : '公开结构参考 · 尺寸与实体推定';
    $$('#component-tabs button').forEach(button => { button.classList.toggle('active', button.dataset.select === id); button.setAttribute('aria-pressed', String(button.dataset.select === id)); });
    const value = thermalNodes()[id];
    const invalidDomain = state.result?.thermal?.summary?.within_model_limits === false && finite(value?.temperature_c);
    $('selected-temperature').textContent = invalidDomain ? '超范围' : fixed(value?.temperature_c);
    $('selected-temperature').classList.toggle('invalid-domain', invalidDomain);
    $('selected-temperature').nextElementSibling.hidden = invalidDomain;
    $('selected-margin').textContent = invalidDomain ? '全网未通过物理适用域筛查；原始诊断数值保留在 JSON，不作为温度预测' : value ? finite(value.margin_c) ? `距来源裕度参考线 ${fixed(value.margin_c)} °C · 参考 ${fixed(value.limit_c, 0)} °C` : '此节点没有公开允许温度，不推定安全裕度' : state.result ? '结构件保持材质色' : '等待同一几何计算';
    document.querySelector('.metric-primary').classList.toggle('hot', finite(value?.margin_c) && value.margin_c < 10);
  }
  function renderResult() {
    const r = state.result;
    $('cooling-flow').innerHTML = `${fixed(r.flow?.total_inlet_kg_s, 3)} <small>kg/s</small>`;
    const mass = ['cmc_left_hv','cmc_right_hv'].map(id => r.metrics?.components?.[id]?.mass_kg).reduce((sum,value) => finite(value) ? sum + value : NaN, 0);
    $('heatsink-mass').innerHTML = `${fixed(mass, 2)} <small>kg</small>`;
    const summary = r.thermal?.summary || {}, limiting = labels[summary.limiting_component]?.[0] || summary.limiting_component || '未判定';
    $('result-summary').textContent = summary.steady_state_exists === false ? '当前边界下无有限稳态，不能以温度数值判断可用。' : summary.within_model_limits === false ? '质量与能量守恒不等于预测有效。此工况超出低阶模型适用域，不能据此比较真实温度裕度。' : finite(summary.min_margin_c) ? `最小来源参考裕度 ${fixed(summary.min_margin_c)} °C · ${limiting}。仅为当前模型筛查，不代表设计验证。` : '集中参数模型筛查。公开数据不足，不能判断真实飞机安全裕度。';
    const warnings = Array.isArray(r.warnings) ? r.warnings : [];
    const severe = summary.steady_state_exists === false || (finite(summary.min_margin_c) && summary.min_margin_c < 0) || summary.within_model_limits === false;
    $('result-warning').hidden = !severe;
    const warningText = [];
    if (summary.steady_state_exists === false) warningText.push('当前没有有限强制流动稳态');
    if (finite(summary.max_temperature_c) && summary.max_temperature_c > 200) warningText.push('温度代理超过 200 °C，超出定物性近似的筛查范围');
    if (summary.within_model_limits === false) warningText.push('流动 / 传热相关式适用性检查未通过');
    if (finite(summary.min_margin_c) && summary.min_margin_c < 0) warningText.push('存在低于零的来源参考裕度');
    $('result-warning').textContent = severe ? warningText.join('；') + '。不构成适航判断。' : '';
    $('result-badge').textContent = severe ? '需关注边界' : '本次求解';
    renderer.colorUsesHeat = summary.within_model_limits === false;
    const values = Object.values(thermalNodes()).map(v => renderer.colorUsesHeat ? v.heat_w : v.temperature_c).filter(finite);
    const low = renderer.colorUsesHeat ? 0 : Math.min(r.boundary?.ambient_c ?? 20, ...values), high = Math.max(low + 20, ...values);
    const unit = renderer.colorUsesHeat ? 'W' : '°C';
    renderer.tempRange = [low, high]; $('legend-low').textContent = `${fixed(low, 0)} ${unit}`; $('legend-high').textContent = `${fixed(high, 0)} ${unit}`;
    $('color-mode-label').textContent = renderer.colorUsesHeat ? '热源功率着色' : '温度着色';
    $('color-legend-note').textContent = renderer.colorUsesHeat ? '来源损耗 / 推定拆分，温度预测不可用' : '节点代理温度，非 CFD 热场';
    $('thermal-legend').hidden = !$('show-thermal').checked || !values.length;
    const branches = Object.entries(r.flow?.branches || {});
    $('network-facts').innerHTML = branches.map(([id, branch]) => `<span>${escapeHTML(id)} <strong>${fixed(branch.mass_flow_kg_s, 4)}</strong> kg/s</span>`).join('') + (warnings.length ? `<span>模型提示：${warnings.length} 项，详见下方 JSON</span>` : '');
  }
  function select(id, reveal = false) {
    state.selected = id;
    if (reveal && state.mode === 'assembled') changeMode('open');
    updateInspector(); renderer.requestDraw();
  }
  const modes = {assembled:['完整装配','机翼与短舱，先建立空间关系'],open:['移除外壳','外壳与随壳入口移除，保留内部电机、CMC 与风道'],cutaway:['纵向剖视','外壳与电机外罩半剖，热部件保留完整'],exploded:['分解结构','沿推定装配方向展开，不改变热网络几何']};
  function changeMode(mode) {
    state.mode = mode; $$('.view-modes button').forEach(button => {button.classList.toggle('active', button.dataset.mode === mode);button.setAttribute('aria-pressed', String(button.dataset.mode === mode));});
    $('view-title').textContent = modes[mode][0]; $('view-caption').textContent = modes[mode][1];
    renderer.reset(mode); renderer.requestDraw();
  }
  function download(blob, filename) {
    const url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = filename; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  $('export-json').addEventListener('click', () => {
    if (!state.result || state.dirty || state.exportRevision !== state.revision || state.busy) return;
    download(new Blob([$('evidence-json').textContent], {type:'application/json'}), `x57-modii-${geometryFingerprint(state.geometry).slice(0,12)}.json`);
  });
  $('export-step').addEventListener('click', async () => {
    if (!state.result || state.dirty || state.exportRevision !== state.revision || state.busy || $('export-step').disabled) return;
    const revision = state.revision, fingerprint = geometryFingerprint(state.geometry), data = {geometry:{...state.geometry.parameters}};
    $('export-step').disabled = true; $('step-status').textContent = '正在由同一组参数构建 STEP 实体…';
    try {
      const response = await fetch('/api/nacelle/step', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
      if (!response.ok) {const error = await response.json();throw new Error(error.error || 'STEP 导出失败');}
      const blob = await response.blob();
      if (revision !== state.revision || state.dirty || fingerprint !== geometryFingerprint(state.geometry)) { $('step-status').textContent = '输入已改变，已丢弃旧版本 STEP；请重新计算'; return; }
      download(blob, `x57-modii-${fingerprint.slice(0,12)}.step`); $('step-status').textContent = '当前参数 STEP 已生成；具名实体为推定重建';
    } catch (error) {setError(error.message); $('step-status').textContent = 'STEP 未完成';}
    finally { $('export-step').disabled = state.dirty || !state.result || state.busy || !state.geometry?.cad?.step_available; }
  });

  /* Orthographic camera and crease-aware shading from the supplied triangles.
     Normals affect light only; vertices, clipping and picks remain actual mesh. */
  class AssemblyRenderer {
    constructor(canvas, overlay) {
      this.canvas=canvas; this.overlay=overlay; this.ctx=overlay.getContext('2d'); this.meshes=[]; this.tempRange=[20,120]; this.pending=false;
      this.gl=canvas.getContext('webgl', {alpha:true,antialias:true,preserveDrawingBuffer:true});
      if (!this.gl) throw new Error('浏览器未启用 WebGL，无法显示真实三维装配。请使用支持 WebGL 的浏览器。');
      const gl=this.gl;
      const vertex=`attribute vec3 aPosition;attribute vec3 aNormal;uniform mat4 uMatrix;uniform vec3 uOffset;varying vec3 vNormal;varying vec3 vWorld;void main(){vWorld=aPosition+uOffset;vNormal=aNormal;gl_Position=uMatrix*vec4(vWorld,1.0);}`;
      const fragment=`precision mediump float;uniform vec4 uColor;uniform float uClip;uniform float uSelected;varying vec3 vNormal;varying vec3 vWorld;void main(){if(uClip>0.5&&vWorld.y<0.0)discard;vec3 n=normalize(vNormal);float key=abs(dot(n,normalize(vec3(-0.5,-0.8,1.4))));float side=abs(dot(n,normalize(vec3(0.6,1.0,0.3))));float light=0.49+0.40*key+0.11*side;vec3 color=uColor.rgb*light;color=mix(color,vec3(0.97,0.87,0.60),uSelected*0.12);gl_FragColor=vec4(color,uColor.a);}`;
      const shader=(type,code)=>{const s=gl.createShader(type);gl.shaderSource(s,code);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(s));return s;};
      this.program=gl.createProgram();gl.attachShader(this.program,shader(gl.VERTEX_SHADER,vertex));gl.attachShader(this.program,shader(gl.FRAGMENT_SHADER,fragment));gl.linkProgram(this.program);
      if(!gl.getProgramParameter(this.program,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(this.program));
      this.locations={};['uMatrix','uOffset','uColor','uClip','uSelected'].forEach(n=>this.locations[n]=gl.getUniformLocation(this.program,n));this.position=gl.getAttribLocation(this.program,'aPosition');this.normal=gl.getAttribLocation(this.program,'aNormal');
      gl.enable(gl.DEPTH_TEST);gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);
      this.reset('assembled'); new ResizeObserver(()=>this.requestDraw()).observe(canvas.parentElement);
      let drag=null;
      canvas.parentElement.addEventListener('pointerdown',event=>{if(event.target.closest('button'))return;drag={x:event.clientX,y:event.clientY,moved:false};canvas.parentElement.setPointerCapture(event.pointerId);});
      canvas.parentElement.addEventListener('pointermove',event=>{if(!drag)return;const dx=event.clientX-drag.x,dy=event.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>1)drag.moved=true;this.yaw-=dx*.007;this.pitch=clamp(this.pitch+dy*.006,-.5,1.25);drag.x=event.clientX;drag.y=event.clientY;this.requestDraw();});
      canvas.parentElement.addEventListener('pointerup',event=>{if(drag&&!drag.moved){const rect=canvas.getBoundingClientRect();const id=this.pick(event.clientX-rect.left,event.clientY-rect.top);if(id)select(id);}drag=null;});
      canvas.parentElement.addEventListener('pointercancel',()=>drag=null);
      canvas.parentElement.addEventListener('wheel',event=>{event.preventDefault();this.zoom=clamp(this.zoom*Math.exp(-event.deltaY*.001),.5,3.5);this.requestDraw();},{passive:false});
      canvas.parentElement.addEventListener('keydown',event=>{const keys=['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','=','-','0'];if(!keys.includes(event.key))return;event.preventDefault();if(event.key==='ArrowLeft')this.yaw-=.12;if(event.key==='ArrowRight')this.yaw+=.12;if(event.key==='ArrowUp')this.pitch=clamp(this.pitch+.1,-.5,1.25);if(event.key==='ArrowDown')this.pitch=clamp(this.pitch-.1,-.5,1.25);if(['+','='].includes(event.key))this.zoom=clamp(this.zoom*1.15,.5,3.5);if(event.key==='-')this.zoom=clamp(this.zoom/1.15,.5,3.5);if(event.key==='0')this.reset(state.mode);this.requestDraw();});
    }
    reset(mode) {this.yaw=mode==='cutaway'?-Math.PI/2:-2.02;this.pitch=mode==='cutaway'?.15:.38;this.zoom=mode==='assembled'?1:mode==='exploded'?.95:1.28;this.target=[510,0,10];this.requestDraw();}
    setGeometry(geometry) {
      const gl=this.gl;this.meshes.forEach(m=>gl.deleteBuffer(m.buffer));
      this.meshes=geometry.components.map(component=>{
        const array=[],vertices=component.vertices,triangles=component.triangles,min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];
        for(let i=0;i<vertices.length;i+=3)for(let j=0;j<3;j++){min[j]=Math.min(min[j],vertices[i+j]);max[j]=Math.max(max[j],vertices[i+j]);}
        const normals=[],adjacent=Array.from({length:vertices.length/3},()=>[]),crease=Math.cos(Math.PI/6);
        for(let i=0;i<triangles.length;i+=3){
          const a=triangles[i]*3,b=triangles[i+1]*3,c=triangles[i+2]*3;
          const u=[vertices[b]-vertices[a],vertices[b+1]-vertices[a+1],vertices[b+2]-vertices[a+2]],v=[vertices[c]-vertices[a],vertices[c+1]-vertices[a+1],vertices[c+2]-vertices[a+2]];
          let n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];
          const length=Math.hypot(...n)||1;n=n.map(x=>x/length);normals.push(n);
          for(const vertex of triangles.slice(i,i+3))adjacent[vertex].push(i/3);
        }
        for(let i=0;i<triangles.length;i+=3)for(const vertex of triangles.slice(i,i+3)){
          const face=normals[i/3],sum=[0,0,0];
          for(const neighbor of adjacent[vertex]){const n=normals[neighbor];if(dot(n,face)>=crease)for(let axis=0;axis<3;axis++)sum[axis]+=n[axis];}
          const length=Math.hypot(...sum)||1,index=vertex*3;
          array.push(vertices[index],vertices[index+1],vertices[index+2],...sum.map(n=>n/length));
        }
        const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(array),gl.STATIC_DRAW);
        return {...component,buffer,count:array.length/6,min,max,center:min.map((v,i)=>(v+max[i])/2)};
      });
      $('mesh-count').textContent=`${this.meshes.length} 具名部件`; $('render-status').textContent='WebGL · PARAMETRIC MESH';
      this.canvas.dataset.geometryFingerprint=geometry.fingerprint; this.canvas.dataset.componentCount=this.meshes.length;this.requestDraw();
    }
    offset(mesh) {return state.mode==='exploded'?(mesh.explode||[0,0,0]):[0,0,0];}
    visible(mesh) {
      // Cowling-mounted lips/scoops leave with the shell; retain the internal
      // backplate passages, baffles and engine mounts in this service view.
      const onCowling=['main_inlet_lip','motor_upper_exhaust','lv_inlet_left','lv_inlet_right'];
      return !(state.mode==='open'&&(mesh.group==='shell'||onCowling.includes(mesh.id)));
    }
    clipped(mesh) {return state.mode==='cutaway'&&(mesh.group==='shell'||['motor_rotor','motor_stator','motor_bypass_shroud'].includes(mesh.id));}
    appearance(mesh) {
      let color=mesh.color||[.5,.6,.6],opacity=mesh.opacity??1;
      if(mesh.group==='shell')opacity=state.mode==='assembled'?.88:state.mode==='exploded'?.23:.8;
      if(mesh.group==='wing')opacity=.83;
      if(mesh.id==='motor_rotor'&&state.mode!=='assembled')opacity=.26;
      if(mesh.id==='motor_bypass_shroud')opacity=.13;
      const thermal=thermalNodes()[mesh.thermal_node];
      const quantity=this.colorUsesHeat?thermal?.heat_w:thermal?.temperature_c;
      if($('show-thermal').checked&&finite(quantity)){color=this.temperatureColor(quantity);opacity=1;}
      return [...color,opacity];
    }
    temperatureColor(value) {
      const t=clamp((value-this.tempRange[0])/(this.tempRange[1]-this.tempRange[0]),0,1),stops=[[.25,.49,.62],[.38,.68,.62],[.85,.7,.42],[.78,.39,.25]],pos=t*3,i=Math.min(2,Math.floor(pos)),f=pos-i;
      return stops[i].map((v,j)=>v+(stops[i+1][j]-v)*f);
    }
    basis() {
      const c=Math.cos(this.yaw),s=Math.sin(this.yaw),cp=Math.cos(this.pitch),sp=Math.sin(this.pitch);
      this.right=[-s,c,0];this.up=[-c*sp,-s*sp,cp];this.eye=[c*cp,s*cp,sp];
      this.scale=Math.min(this.height/1750,this.width/2650)*this.zoom;
    }
    project(point) {const p=point.map((v,i)=>v-this.target[i]);return [this.width/2+dot(p,this.right)*this.scale,this.height*.51-dot(p,this.up)*this.scale,dot(p,this.eye)];}
    matrix() {
      const r=this.right,u=this.up,e=this.eye,sx=2*this.scale/this.width,sy=2*this.scale/this.height,sz=-1/5000,t=this.target;
      return new Float32Array([r[0]*sx,u[0]*sy,e[0]*sz,0,r[1]*sx,u[1]*sy,e[1]*sz,0,r[2]*sx,u[2]*sy,e[2]*sz,0,-dot(t,r)*sx,-dot(t,u)*sy-.02,-dot(t,e)*sz,1]);
    }
    requestDraw() {if(this.pending)return;this.pending=true;requestAnimationFrame(()=>{this.pending=false;this.draw();});}
    draw() {
      if(!this.gl)return;const rect=this.canvas.getBoundingClientRect();this.width=rect.width;this.height=rect.height;if(!this.width||!this.height)return;
      const ratio=Math.min(devicePixelRatio||1,2);for(const canvas of [this.canvas,this.overlay]){if(canvas.width!==Math.round(this.width*ratio)||canvas.height!==Math.round(this.height*ratio)){canvas.width=Math.round(this.width*ratio);canvas.height=Math.round(this.height*ratio);}}
      this.basis();const gl=this.gl;gl.viewport(0,0,this.canvas.width,this.canvas.height);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.useProgram(this.program);gl.uniformMatrix4fv(this.locations.uMatrix,false,this.matrix());
      const ordered=this.meshes.filter(m=>this.visible(m)).map(m=>({mesh:m,color:this.appearance(m),depth:this.project(m.center.map((v,i)=>v+this.offset(m)[i]))[2]}));
      ordered.sort((a,b)=>(a.color[3]<.99)-(b.color[3]<.99)||(a.color[3]<.99?a.depth-b.depth:0));
      for(const {mesh,color} of ordered){gl.depthMask(color[3]>.97);gl.bindBuffer(gl.ARRAY_BUFFER,mesh.buffer);gl.enableVertexAttribArray(this.position);gl.vertexAttribPointer(this.position,3,gl.FLOAT,false,24,0);gl.enableVertexAttribArray(this.normal);gl.vertexAttribPointer(this.normal,3,gl.FLOAT,false,24,12);gl.uniform3fv(this.locations.uOffset,this.offset(mesh));gl.uniform4fv(this.locations.uColor,color);gl.uniform1f(this.locations.uClip,this.clipped(mesh)?1:0);gl.uniform1f(this.locations.uSelected,mesh.id===state.selected||mesh.thermal_node===state.selected?1:0);gl.drawArrays(gl.TRIANGLES,0,mesh.count);}
      gl.depthMask(true);this.ctx.setTransform(ratio,0,0,ratio,0,0);this.ctx.clearRect(0,0,this.width,this.height);this.drawGround();
      if($('show-flow').checked&&state.result)this.drawFlows();
      if($('show-labels').checked)this.drawLabels();
      this.canvas.dataset.mode=state.mode;this.canvas.dataset.rendered=String(this.meshes.length>0);this.canvas.dataset.camera=`${this.yaw.toFixed(3)},${this.pitch.toFixed(3)},${this.zoom.toFixed(3)}`;
    }
    drawGround() {
      // A small physical scale mark, rather than decorative simulation contours.
      const ctx=this.ctx;ctx.save();ctx.strokeStyle='#abc0b4';ctx.lineWidth=.7;ctx.globalAlpha=.55;
      const origin=[this.width*.4,this.height-34],length=250*this.scale;ctx.beginPath();ctx.moveTo(...origin);ctx.lineTo(origin[0]+length,origin[1]);ctx.moveTo(origin[0],origin[1]-3);ctx.lineTo(origin[0],origin[1]+3);ctx.moveTo(origin[0]+length,origin[1]-3);ctx.lineTo(origin[0]+length,origin[1]+3);ctx.stroke();ctx.fillStyle='#789689';ctx.font='8px monospace';ctx.textAlign='center';ctx.fillText('250 mm',origin[0]+length/2,origin[1]-5);ctx.restore();
    }
    drawLabels() {
      const labelsToDraw=state.mode==='assembled'?[['propeller_spinner','桨帽 / 巡航螺旋桨',-70,90],['lv_inlet_left','双耳形进气口',-60,-67],['local_wing','机翼局部',78,-10]]:[['motor_winding','电机 · 定子 / 转子',-65,-90],['cmc_left_hv','CMC · 高压鳍片',35,83],['cmc_right_lv','CMC · 低压背板',90,-58],['lv_inlet_left','新鲜空气进气口',-15,-128]];
      const ctx=this.ctx;ctx.save();ctx.font='10px sans-serif';
      for(const [id,text,dx,dy] of labelsToDraw){const mesh=this.meshes.find(m=>m.id===id);if(!mesh||!this.visible(mesh))continue;const p=this.project(mesh.center.map((v,i)=>v+this.offset(mesh)[i]));const textWidth=ctx.measureText(text).width,width=textWidth+18,height=24;const left=clamp(p[0]+dx-(dx<0?width:0),14,this.width-width-14),top=clamp(p[1]+dy,131,this.height-77);const endX=clamp(p[0],left+9,left+width-9),endY=top+(dy<0?height:0);ctx.strokeStyle='#8da9a0';ctx.lineWidth=.75;ctx.beginPath();ctx.moveTo(p[0],p[1]);ctx.lineTo((p[0]+endX)/2,endY);ctx.lineTo(endX,endY);ctx.stroke();ctx.fillStyle=id===state.selected?'#b16e37':'#438373';ctx.beginPath();ctx.arc(p[0],p[1],2.6,0,Math.PI*2);ctx.fill();ctx.fillStyle='#fdfefaf0';ctx.strokeStyle='#ccdad1';ctx.beginPath();ctx.roundRect(left,top,width,height,4);ctx.fill();ctx.stroke();ctx.fillStyle='#557367';ctx.textAlign='left';ctx.fillText(text,left+9,top+15);}
      ctx.restore();
    }
    drawFlows() {
      // Schematic network paths deliberately are not curved streamlines. Values
      // are read from solved branches; spatial offsets are explanatory only.
      const paths=[
        {keys:['main_inlet'],points:[[-360,0,25],[-30,0,25]],color:'#287f9e'},
        {keys:['motor_internal'],points:[[-30,0,25],[120,0,25],[290,0,55]],color:'#287f9e'},
        {keys:['motor_slots'],points:[[-30,0,25],[70,55,90],[160,55,90],[290,0,55]],color:'#3c8e99'},
        {keys:['motor_bypass'],points:[[-340,-195,25],[-20,-195,25],[200,-195,25],[290,0,55]],color:'#5d9b9f'},
        {keys:['motor_top_exhaust'],points:[[290,0,55],[270,0,225],[300,0,410]],color:'#69969a'},
        {keys:['cmc_hv_left'],points:[[290,0,55],[410,-110,-80],[600,-110,-180],[610,0,-180]],color:'#ce8343'},
        {keys:['cmc_hv_right'],points:[[290,0,55],[410,110,-80],[600,110,-180],[610,0,-180]],color:'#ce8343'},
        {keys:['cmc_bypass'],points:[[290,0,55],[350,0,-175],[500,0,-195],[610,0,-180]],color:'#9ea178'},
        {keys:['lv_fresh_left'],points:[[170,0,390],[290,-120,295],[450,-120,160],[610,0,-180]],color:'#2b94af'},
        {keys:['lv_fresh_right'],points:[[170,0,390],[290,120,295],[450,120,160],[610,0,-180]],color:'#2b94af'},
        {keys:['lower_outlet'],points:[[610,0,-180],[650,0,-300],[880,0,-360]],color:'#a98756'}];
      const branches=state.result.flow?.branches||{},ctx=this.ctx;ctx.save();
      for(const path of paths){const branch=path.keys.map(k=>branches[k]).find(Boolean);if(!branch || Math.abs(branch.mass_flow_kg_s)<1e-12)continue;const points=path.points.map(p=>this.project(p));if(branch.mass_flow_kg_s<0)points.reverse();ctx.strokeStyle=path.color;ctx.fillStyle=path.color;ctx.lineWidth=clamp(1.2+Math.abs(branch.mass_flow_kg_s)*1.5,1.2,3.3);ctx.setLineDash([7,4]);ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.stroke();ctx.setLineDash([]);const [a,b]=points.slice(-2),angle=Math.atan2(b[1]-a[1],b[0]-a[0]);ctx.beginPath();ctx.moveTo(b[0],b[1]);ctx.lineTo(b[0]-9*Math.cos(angle-.4),b[1]-9*Math.sin(angle-.4));ctx.lineTo(b[0]-9*Math.cos(angle+.4),b[1]-9*Math.sin(angle+.4));ctx.closePath();ctx.fill();}
      ctx.restore();
    }
    pick(x,y) {
      let best=null,depth=-Infinity;
      for(const mesh of this.meshes){if(!this.visible(mesh)||mesh.group==='shell'||mesh.group==='wing')continue;const o=this.offset(mesh),v=mesh.vertices,tri=mesh.triangles;
        for(let i=0;i<tri.length;i+=3){const points=[];let clipped=0;for(let j=0;j<3;j++){const k=tri[i+j]*3,p=[v[k]+o[0],v[k+1]+o[1],v[k+2]+o[2]];if(this.clipped(mesh)&&p[1]<0)clipped++;points.push(this.project(p));}if(clipped===3)continue;
          const [a,b,c]=points,den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1]);if(Math.abs(den)<.001)continue;const p=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/den,q=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/den,r=1-p-q;if(p<0||q<0||r<0)continue;const z=p*a[2]+q*b[2]+r*c[2];if(z>depth){depth=z;best=mesh.id;}
        }
      }return best;
    }
  }
  function dot(a,b){return a[0]*b[0]+a[1]*b[1]+a[2]*b[2];}
  let renderer;
  try {renderer=new AssemblyRenderer($('assembly-canvas'),$('annotation-canvas'));} catch(error){setError(error.message);$('scene-loading').hidden=true;$('evaluate-button').disabled=true;return;}
  $$('.view-modes button').forEach(button=>button.addEventListener('click',()=>changeMode(button.dataset.mode)));
  $$('#component-tabs button').forEach(button=>button.addEventListener('click',()=>select(button.dataset.select,true)));
  $('show-labels').addEventListener('change',()=>renderer.requestDraw());
  $('show-flow').addEventListener('change',()=>{if($('show-flow').checked&&state.mode==='assembled')changeMode('open');$('flow-disclaimer').hidden=!$('show-flow').checked;$('flow-disclaimer').textContent=state.result?'箭头仅表示集中参数网络的连接与方向，不代表 CFD 流线或局部速度场。':'当前输入未计算，暂不显示支路箭头；请先重建并计算。';renderer.requestDraw();});
  $('show-thermal').addEventListener('change',()=>{if($('show-thermal').checked&&state.mode==='assembled')changeMode('open');$('thermal-legend').hidden=!$('show-thermal').checked||!state.result;renderer.requestDraw();});
  $('zoom-in').addEventListener('click',()=>{renderer.zoom=clamp(renderer.zoom*1.18,.5,3.5);renderer.requestDraw();});
  $('zoom-out').addEventListener('click',()=>{renderer.zoom=clamp(renderer.zoom/1.18,.5,3.5);renderer.requestDraw();});
  $('reset-camera').addEventListener('click',()=>renderer.reset(state.mode));
  $('cancel-button').addEventListener('click',cancel);
  $('nacelle-form').addEventListener('submit',event=>{event.preventDefault();evaluate();});
  window.addEventListener('pagehide',()=>{if(state.busy)cancel();else{state.request++;state.controller?.abort();state.controller=null;}});
  window.addEventListener('pageshow',event=>{if(event.persisted){busy(false);renderer.requestDraw();}});
  async function initialize(){
    try{state.catalog=await api('/api/nacelle/catalog');renderFields(state.catalog);busy(false);await evaluate();}
    catch(error){setError(error.message);$('scene-loading').hidden=true;$('result-loading').textContent='目录加载失败，请刷新后重试';}
  }
  initialize();
})();
