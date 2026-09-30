'use strict';

/* A CAD experiment owns its inputs and evidence. It never mutates the six-step
 * guide or silently substitutes a previous thermal/mission result after edits. */
(() => {
  const CAD_FIELDS = [
    { name: 'length_mm', label: '长度', unit: 'mm', min: 20, max: 1000, step: .1 },
    { name: 'width_mm', label: '宽度', unit: 'mm', min: 20, max: 500, step: .1 },
    { name: 'fin_height_mm', label: '翅高', unit: 'mm', min: 2, max: 150, step: .1 },
    { name: 'base_thickness_mm', label: '底板厚度', unit: 'mm', min: 1, max: 30, step: .1 },
    { name: 'fin_thickness_mm', label: '翅片厚度', unit: 'mm', min: .2, max: 10, step: .01 },
    { name: 'fin_count', label: '翅片数量', unit: '片', min: 2, max: 120, step: 1 }
  ];
  const BOUNDARY_FIELDS = [
    { name: 'heat_w', label: '热负荷', unit: 'W', min: 0, max: 10000, step: 1 },
    { name: 'inlet_c', label: '入口温度', unit: '°C', min: -10, max: 100, step: .1 },
    { name: 'mass_flow_kg_s', label: '给定流量', unit: 'kg/s', min: 0, max: .5, step: .001 }
  ];
  const PRESET_COPY = {
    reference: ['公开尺寸基准', '按 NASA 报告旧版尺寸重建的理想几何，并非官方 CAD。'],
    light: ['轻量候选', '减少翅片、高度与底板厚度；质量下降是否值得，需要计算。'],
    dense: ['加密翅片候选', '增加翅片也会收窄流道。散热面积与流阻一起比较。']
  };
  const c = { catalog: null, loading: null, revision: 0, request: 0, busy: false, result: null, resultRevision: -1, mission: null, missionRevision: 0, missionBusy: false, stepBusy: false };
  const byId = (id) => document.getElementById(id);
  const same = (a, b, keys) => keys.every((key) => Number(a?.[key]) === Number(b?.[key]));
  const error = (text = '') => { byId('cad-error').hidden = !text; byId('cad-error').textContent = text; };
  const read = (fields) => Object.fromEntries(fields.map((field) => [field.name, Number(byId(`cad-${field.name}`).value)]));
  const inputs = () => ({ geometry: read(CAD_FIELDS), boundary: read(BOUNDARY_FIELDS) });
  const current = () => c.result && c.resultRevision === c.revision && same(inputs().geometry, c.result.candidate.geometry, CAD_FIELDS.map((x) => x.name)) && same(inputs().boundary, c.result.candidate.thermal.boundary, BOUNDARY_FIELDS.map((x) => x.name));
  const missionInput = () => ({ scenario_id: byId('cad-mission-scenario').value, ambient_c: Number(byId('cad-mission-ambient').value), design_id: 'reference', cad_geometry: c.result?.candidate.geometry });
  const fieldMarkup = (field, value) => `<div class="cad-field"><label for="cad-${field.name}">${esc(field.label)} <span>${field.unit}</span></label><input id="cad-${field.name}" data-cad-field="${field.name}" type="number" min="${field.min}" max="${field.max}" step="${field.step}" value="${value}" required inputmode="decimal" aria-label="${esc(field.label)} / ${field.unit}"></div>`;

  function controls() {
    const ready = !!current();
    byId('cad-evaluate').disabled = c.busy || !c.catalog;
    byId('cad-evaluate').innerHTML = c.busy ? '正在计算同边界对比…' : '计算几何与热性能 <span>↗</span>';
    byId('cad-apply').disabled = !ready || c.missionBusy || !byId('cad-mission-scenario').value;
    byId('cad-apply').innerHTML = c.missionBusy ? '正在计算完整任务…' : '用此几何计算完整任务 <span>→</span>';
    byId('cad-export-json').disabled = !ready;
    byId('cad-export-step').disabled = !ready || c.stepBusy || c.result?.candidate.cad?.step_available !== true;
    byId('cad-export-step').textContent = c.stepBusy ? '正在生成 STEP…' : '↓ STEP 几何';
    byId('cad-export-step').title = ready && !c.result?.candidate.cad?.step_available ? '此自定义几何尚无可用 STEP；需要安装可选 CAD 内核，预设几何可使用已验证导出。' : '导出当前已计算的几何，单位 mm';
  }

  function open() {
    stopPlayback();
    document.body.classList.remove('mode-guided', 'mode-expert');
    document.body.classList.add('mode-cad');
    state.guide.mode = 'cad';
    byId('cad-view').hidden = false;
    ['guided', 'expert'].forEach((mode) => { byId(`${mode}-mode-button`).classList.remove('active'); byId(`${mode}-mode-button`).setAttribute('aria-pressed', 'false'); });
    document.querySelectorAll('.nav-tab').forEach((button) => { const active = button.dataset.view === 'cad'; button.classList.toggle('active', active); if (active) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current'); });
    window.scrollTo({ top: 0, behavior: 'instant' });
    byId('cad-title').focus({ preventScroll: true });
    if (!c.catalog && !c.loading) c.loading = initialize().finally(() => { c.loading = null; });
  }

  async function initialize() {
    byId('cad-loading').hidden = false; error();
    try {
      const [catalog, missions] = await Promise.all([api('/api/cad/catalog'), state.catalog ? Promise.resolve(state.catalog) : api('/api/catalog')]);
      if (!catalog.defaults || !catalog.boundary || !Array.isArray(catalog.presets)) throw new Error('几何目录不完整');
      c.catalog = catalog;
      byId('cad-preset').innerHTML = catalog.presets.map((item) => `<option value="${esc(item.id)}">${esc(PRESET_COPY[item.id]?.[0] || item.id)}</option>`).join('') + '<option value="custom" disabled>自定义尺寸</option>';
      byId('cad-geometry-fields').innerHTML = CAD_FIELDS.map((field) => fieldMarkup(field, catalog.defaults[field.name])).join('');
      byId('cad-boundary-fields').innerHTML = BOUNDARY_FIELDS.map((field) => fieldMarkup(field, catalog.boundary[field.name])).join('');
      byId('cad-preset-note').textContent = PRESET_COPY.reference[1];
      byId('cad-mission-scenario').innerHTML = missions.scenarios.map((scenario) => `<option value="${esc(scenario.id)}">${esc(scenario.name)}</option>`).join('');
      byId('cad-mission-scenario').value = missions.scenarios.some((scenario) => scenario.id === 'cooling_fault') ? 'cooling_fault' : missions.scenarios[0].id;
      const selected = missions.scenarios.find((scenario) => scenario.id === byId('cad-mission-scenario').value);
      byId('cad-mission-ambient').value = selected.ambient_c;
      byId('cad-mission-ambient').min = missions.ambient_range_c?.[0] ?? 15;
      byId('cad-mission-ambient').max = missions.ambient_range_c?.[1] ?? 50;
      byId('cad-mission-scenario').disabled = false; byId('cad-mission-ambient').disabled = false;
      if (catalog.source_url && /^https:\/\//.test(catalog.source_url)) byId('cad-source-link').innerHTML = `<a href="${esc(catalog.source_url)}" target="_blank" rel="noopener noreferrer">NASA/TM-20230011420 · Table 2 ↗</a>`;
      document.querySelectorAll('[data-cad-field]').forEach((input) => input.addEventListener('input', markDirty));
      byId('cad-preset').addEventListener('change', () => {
        const preset = c.catalog.presets.find((item) => item.id === byId('cad-preset').value);
        if (!preset) return;
        CAD_FIELDS.forEach((field) => { byId(`cad-${field.name}`).value = preset.geometry[field.name]; });
        markDirty();
      });
      byId('cad-mission-scenario').addEventListener('change', () => {
        const next = missions.scenarios.find((scenario) => scenario.id === byId('cad-mission-scenario').value);
        byId('cad-mission-ambient').value = next.ambient_c; markMissionDirty();
      });
      byId('cad-mission-ambient').addEventListener('input', markMissionDirty);
      byId('cad-content').hidden = false;
      drawDraft(catalog.defaults);
      // Initial values are evaluated by the real server, never invented replay data.
      await evaluate();
    } catch (failure) {
      error(`未能载入 CAD 设计：${failure.message}。可从顶部重新打开重试。`);
      if (!byId('cad-content').hidden) controls();
    } finally { byId('cad-loading').hidden = true; }
  }

  function markMissionDirty() {
    c.missionRevision++;
    byId('cad-mission-result').hidden = true;
    byId('cad-mission-status').textContent = c.missionBusy ? '输入已改变；正在运行的旧请求不会覆盖新输入。' : '任务输入已更改。重新计算后显示对应任务证据。';
    byId('cad-mission-status').classList.add('pending');
    renderEvidence(); controls();
  }

  function markDirty() {
    c.revision++; c.missionRevision++;
    const { geometry } = inputs();
    const preset = c.catalog.presets.find((item) => same(item.geometry, geometry, CAD_FIELDS.map((field) => field.name)));
    byId('cad-preset').value = preset?.id || 'custom';
    byId('cad-preset-note').textContent = preset ? (PRESET_COPY[preset.id]?.[1] || '') : '自定义尺寸属于设计假设；只有公开基准尺寸属于来源事实。';
    document.querySelectorAll('[data-cad-field]').forEach((input) => input.setAttribute('aria-invalid', String(!input.validity.valid)));
    byId('cad-results').hidden = true; byId('cad-mission-result').hidden = true; byId('cad-dirty').hidden = false;
    byId('cad-preview-state').textContent = '草图 · 尚未重算'; byId('cad-preview-state').className = 'cad-kind assumption';
    byId('cad-geometry-id').textContent = 'DRAFT / 未保存计算';
    byId('cad-fixed-hardware').textContent = '待计算后固定硬件';
    byId('cad-evidence-json').textContent = '输入已更改。尚无与当前输入匹配的计算证据。';
    byId('cad-mission-status').textContent = '几何或单点边界已更改。先计算几何，再重新运行任务。';
    byId('cad-mission-status').classList.add('pending');
    error(); drawDraft(geometry); controls();
  }

  // Rendering only: this projection makes no claims about heat, flow or BRep
  // verification. Evaluated previews are replaced with the server's same-input SVG.
  function drawDraft(g) {
    if (CAD_FIELDS.some((field) => !finite(g[field.name]) || g[field.name] < field.min || g[field.name] > field.max) || !Number.isInteger(g.fin_count) || g.width_mm - g.fin_count * g.fin_thickness_mm < .25 * (g.fin_count - 1)) {
      byId('cad-preview').innerHTML = '<div class="empty-state">尺寸无效或翅片相交<br><span>请检查输入；最小流道间隙为 0.25 mm</span></div>';
      byId('cad-preview-dimensions').textContent = '等待有效几何'; return;
    }
    const L = g.length_mm, W = g.width_mm, B = g.base_thickness_mm, H = g.fin_height_mm, T = g.fin_thickness_mm;
    const project = (x,y,z) => [x*.80+y*.70, -x*.35+y*.34-z];
    const corners = [[0,0,0],[L,0,0],[0,W,0],[L,W,0],[0,0,H+B],[L,0,H+B],[0,W,H+B],[L,W,H+B]].map((point) => project(...point));
    const xmin = Math.min(...corners.map((p) => p[0])), xmax = Math.max(...corners.map((p) => p[0]));
    const ymin = Math.min(...corners.map((p) => p[1])), ymax = Math.max(...corners.map((p) => p[1]));
    const margin = Math.max(xmax-xmin, ymax-ymin)*.085;
    const polygon = (points, fill) => `<polygon points="${points.map((p) => project(...p).map((n) => n.toFixed(3)).join(',')).join(' ')}" fill="${fill}" stroke="#65868f" stroke-width=".5" stroke-linejoin="round"/>`;
    let shapes = polygon([[0,0,B],[L,0,B],[L,W,B],[0,W,B]], '#28464f') + polygon([[0,0,0],[0,W,0],[0,W,B],[0,0,B]], '#36545b') + polygon([[0,W,0],[L,W,0],[L,W,B],[0,W,B]], '#243d46');
    const pitch = (W-T)/(g.fin_count-1);
    for (let i=0;i<g.fin_count;i++) {
      const y=i*pitch;
      shapes += polygon([[0,y,B],[L,y,B],[L,y,B+H],[0,y,B+H]], '#658b98');
      shapes += polygon([[0,y,B+H],[L,y,B+H],[L,y+T,B+H],[0,y+T,B+H]], '#bed9dd');
      shapes += polygon([[0,y+T,B],[L,y+T,B],[L,y+T,B+H],[0,y+T,B+H]], '#476771');
      shapes += polygon([[0,y,B],[0,y+T,B],[0,y+T,B+H],[0,y,B+H]], '#7fa6b0');
    }
    byId('cad-preview').innerHTML = `<svg viewBox="${xmin-margin} ${ymin-margin} ${xmax-xmin+2*margin} ${ymax-ymin+2*margin}" role="img" aria-label="当前草图：${g.fin_count} 片翅片，长度 ${L} mm，宽度 ${W} mm，翅高 ${H} mm"><title>由当前尺寸绘制的参数草图，未作实体校验</title>${shapes}</svg>`;
    byId('cad-preview-dimensions').textContent = `${fmt(L,1)} × ${fmt(W,1)} × ${fmt(H+B,1)} mm · ${g.fin_count} 片翅片`;
  }

  async function evaluate() {
    if (c.busy || !c.catalog || !byId('cad-form').reportValidity()) return;
    const revision = c.revision, request = ++c.request, input = inputs();
    c.busy = true; error(); controls();
    byId('cad-preview-state').textContent = '计算中';
    try {
      const result = await api('/api/cad/compare', input);
      if (request !== c.request || revision !== c.revision) return;
      const candidate = result.candidate;
      if (!candidate?.metrics || !candidate.thermal || !candidate.input_hash || !result.reference || !same(candidate.geometry, input.geometry, CAD_FIELDS.map((field) => field.name)) || !same(candidate.thermal.boundary, input.boundary, BOUNDARY_FIELDS.map((field) => field.name)) || !same(result.reference.thermal?.boundary, input.boundary, BOUNDARY_FIELDS.map((field) => field.name))) throw new Error('返回证据与本次输入不一致');
      c.result = result; c.resultRevision = revision; c.mission = null; c.missionRevision++;
      renderResult(); renderEvidence();
    } catch (failure) {
      if (request === c.request && revision === c.revision) {
        error(`几何与热计算未完成：${failure.message}。请检查输入后重试。`);
        byId('cad-preview-state').textContent = '计算未完成';
      }
    } finally {
      if (request === c.request) { c.busy = false; controls(); }
    }
  }

  function translateWarning(warning) {
    const copy = {
      'Covered no-bypass duct assumed; bare-fin solid is not a CFD fluid domain.': '假定带顶盖、无旁通的流道；裸翅片实体不是 CFD 流体域。',
      'Correlation boundary-condition mismatch: adiabatic roof / three heated walls approximated by standard duct correlations.': '关联式边界近似：三面受热、顶盖绝热，用标准流道关联式替代。',
      'Estimated thermal entrance length exceeds fin length; fully-developed approximation may be poor.': '估算热入口长度大于翅片长度，充分发展流动近似可能较差。',
      '2300 <= Re < 3000: transition interpolation is not a validated correlation.': '2300 ≤ Re < 3000：过渡区使用未经验证的插值。',
      'No finite forced-flow equilibrium or interface proxy exceeds 150 C: fixed-property reduced model is outside declared temperature applicability.': '没有有限强制流动稳态，或界面温度代理超过 150 °C：超出固定物性降阶模型的温度范围。',
      'Re > 1e6: outside selected Gnielinski correlation range.': 'Re > 10⁶：超出所用 Gnielinski 关联式范围。'
    };
    return copy[warning] || warning;
  }
  function valueOrNone(value, decimals, noValue = '无稳态') { return finite(value) ? fmt(value, decimals) : noValue; }
  function renderResult() {
    const { candidate: result, reference } = c.result, m = result.metrics, t = result.thermal;
    const applicable = t.within_model_limits !== false && reference.thermal.within_model_limits !== false;
    const applicabilityWarning = byId('cad-applicability-warning');
    applicabilityWarning.hidden = applicable;
    applicabilityWarning.textContent = applicable ? '' : '超出模型适用边界：候选或基准的温度 / 流动条件已超出当前关联式与固定物性范围。数值仅保留用于诊断，不能据此判断设计优劣。';
    byId('cad-dirty').hidden = true; byId('cad-results').hidden = false;
    const verified = result.cad?.verification !== 'analytic_only' && !!result.cad?.verification;
    byId('cad-preview-state').className = 'cad-kind calculated';
    byId('cad-preview-state').textContent = verified ? '参数投影 · 匹配实体' : '参数投影 · 解析计算';
    byId('cad-geometry-id').textContent = `INPUT / ${result.input_hash.slice(0,12)}`;
    drawDraft(result.geometry);
    const preview = byId('cad-preview').querySelector('svg');
    if (preview) {
      preview.setAttribute('data-geometry-fingerprint', m.fingerprint || '');
      preview.setAttribute('aria-label', `已计算尺寸的参数投影：${result.geometry.fin_count} 片翅片，长度 ${result.geometry.length_mm} mm，宽度 ${result.geometry.width_mm} mm`);
      preview.querySelector('title').textContent = '同一计算尺寸的几何投影；实体校验与热计算分别记录在证据中';
    }
    if (result.preview_svg) {
      const image = document.createElement('img'); image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(result.preview_svg)}`;
      image.alt = '服务器生成的同一几何尺寸图与流道剖面，非 CFD 图';
      byId('cad-server-preview').replaceChildren(image);
    }
    byId('cad-preview-dimensions').textContent = `${fmt(result.geometry.length_mm,1)} × ${fmt(result.geometry.width_mm,1)} × ${fmt(m.total_height_mm,1)} mm · ${result.geometry.fin_count} 片翅片`;
    const specs = [
      ['散热器质量', 'metrics', 'mass_kg', 'kg', 3, -1],
      ['流道受热面积', 'metrics', 'channel_heated_area_m2', 'm²', 3, 1],
      ['所需压降', 'thermal', 'pressure_drop_pa', 'Pa', 1, -1],
      ['底板平均温度代理', 'thermal', 'base_temperature_c', '°C', 1, -1]
    ];
    byId('cad-metrics').innerHTML = specs.map(([label, group, key, unit, decimals, desirable]) => {
      const value = result[group][key], ref = reference[group][key], delta = finite(value) && finite(ref) ? value-ref : null;
      const percent = finite(delta) && Math.abs(ref)>1e-12 ? delta/Math.abs(ref)*100 : null;
      const direction = !applicable || !finite(delta) || Math.abs(delta)<1e-9 ? '' : Math.sign(delta)===desirable ? 'improved' : 'increased';
      const change = finite(delta) ? Math.abs(delta)<1e-9 ? '与基准相同' : `${delta>0?'+':'−'}${fmt(Math.abs(delta),decimals)} ${unit}${finite(percent)?` · ${delta>0?'+':'−'}${fmt(Math.abs(percent),1)}%`:''}` : '无有限稳态结果';
      return `<article class="cad-metric" data-cad-metric="${key}"><div class="cad-metric-name">${label}</div><div class="cad-metric-value">${valueOrNone(value,decimals)} <small>${finite(value)?unit:''}</small></div><div class="cad-metric-reference">基准 ${valueOrNone(ref,decimals)} ${finite(ref)?unit:''}</div><div class="cad-metric-delta ${direction}">${change}</div></article>`;
    }).join('');
    const dm=m.mass_kg-reference.metrics.mass_kg, dt=t.base_temperature_c-reference.thermal.base_temperature_c, dp=t.pressure_drop_pa-reference.thermal.pressure_drop_pa;
    byId('cad-conclusion').textContent = !applicable ? '当前边界下，不能得出有效的设计比较结论' : !t.steady_state_exists ? '没有强制流量，当前热负荷下无有限稳态' : Math.abs(dm)<1e-9 && Math.abs(dt)<1e-9 && Math.abs(dp)<1e-9 ? '这是基准；改动尺寸，再看收益与代价' : `${dm<0?'质量减少':'质量增加'} ${fmt(Math.abs(dm),3)} kg，${dt<0?'温度降低':'温度升高'} ${fmt(Math.abs(dt),1)} °C`;
    byId('cad-boundary-caption').textContent = `同边界：${fmt(t.boundary.heat_w,0)} W 热负荷 · ${fmt(t.boundary.inlet_c,1)} °C 入口 · ${fmt(t.boundary.mass_flow_kg_s,3)} kg/s 给定流量。候选维持该流量需 ${fmt(t.blower_electrical_w,2)} W 电功率（基准 ${fmt(reference.thermal.blower_electrical_w,2)} W）。`;
    const flowFacts = [
      ['流道净间隙',m.gap_mm,'mm',3], ['流通面积',m.flow_area_m2,'m²',5], ['水力直径',m.hydraulic_diameter_m*1000,'mm',3],
      ['通道平均流速',t.velocity_m_s,'m/s',2], ['雷诺数',t.reynolds,'',0], ['翅片效率',t.fin_efficiency*100,'%',1],
      ['换热系数 h',t.h_w_m2_k,'W/(m²·K)',2], ['流体功率',t.fluid_power_w,'W',2], ['所需电功率',t.blower_electrical_w,'W',2],
      ['底板至入口热阻',t.base_to_inlet_resistance_k_w,'K/W',5], ['界面温度代理',t.interface_temperature_c,'°C',1], ['出口空气温度',t.air_outlet_c,'°C',1]
    ];
    byId('cad-flow-facts').innerHTML=flowFacts.map(([label,value,unit,decimals])=>`<div><dt>${label}</dt><dd>${valueOrNone(value,decimals)} ${finite(value)?unit:''}</dd></div>`).join('');
    const regimes={no_forced_flow:'无强制流动',laminar_fully_developed_approximation:'充分发展层流近似',transition_unvalidated_interpolation:'过渡区插值（未验证）',turbulent_gnielinski_hydraulic_diameter_approximation:'Gnielinski 湍流近似'};
    byId('cad-flow-note').textContent=`${regimes[t.regime]||t.regime}。假定封闭流道、无旁通，绝热顶盖不包含在裸翅片 CAD 内；换热系数由流量、物性与关联式计算。电功率按流体功率 / 50% 效率估计，不是风机工作点求解。`;
    byId('cad-warnings').innerHTML = [...new Set([...(t.warnings || []), ...(reference.thermal.warnings || [])])].map((warning) => `<li>${esc(translateWarning(warning))}</li>`).join('');
    byId('cad-fixed-hardware').textContent = `单件 ${fmt(m.mass_kg,3)} kg · 几何已固定`;
    byId('cad-mission-status').textContent='任务采用独立的流量策略与实际控制器损耗，不沿用上面的单点恒定热负荷。';
    byId('cad-mission-status').classList.remove('pending'); byId('cad-mission-result').hidden=true;
    let stepStatus=byId('cad-step-status');
    if(!stepStatus){stepStatus=document.createElement('p');stepStatus.id='cad-step-status';stepStatus.className='cad-mission-note';byId('cad-evidence').appendChild(stepStatus);}
    stepStatus.textContent=result.cad?.step_available ? (verified?'STEP 对应同一尺寸的实体；完整校验记录见 JSON 证据。':'此自定义几何的 STEP 将由可选 CAD 内核生成并校验。') : '当前自定义几何可计算与导出 JSON；任意尺寸 STEP 需要可选 CadQuery 内核。可选择已有实体导出的预设方案。';
  }

  async function applyMission() {
    if (!current() || c.missionBusy || !byId('cad-mission-ambient').reportValidity()) return;
    const revision=c.revision, missionRevision=c.missionRevision, snapshot=missionInput();
    c.missionBusy=true; error(); controls();
    byId('cad-mission-status').textContent='同一固定几何、同一任务，分别计算固定规则与受约束规划器…';byId('cad-mission-status').classList.add('pending');
    try {
      const result=await api('/api/compare',snapshot);
      if(revision!==c.revision || missionRevision!==c.missionRevision) return;
      [result.baseline,result.planner].forEach((run)=>{
        assertRun(run);
        if(run.scenario.id!==snapshot.scenario_id || runAmbient(run)!==snapshot.ambient_c || !same(run.meta.inputs?.cad_geometry,snapshot.cad_geometry,CAD_FIELDS.map((field)=>field.name))) throw new Error('任务结果与本次场景或几何不一致');
      });
      c.mission={result,revision,missionRevision,input:snapshot};renderMission();renderEvidence();
      byId('cad-mission-status').textContent='完整任务已计算；硬件尺寸和质量在两种策略、所有时间步中保持固定。';byId('cad-mission-status').classList.remove('pending');
    } catch(failure) {
      if(revision===c.revision&&missionRevision===c.missionRevision){error(`完整任务未完成：${failure.message}。可保留几何输入重试。`);byId('cad-mission-status').textContent='本次任务计算未完成，不显示其他输入的旧结果。';}
    } finally {c.missionBusy=false;controls();}
  }

  function renderMission() {
    const {baseline,planner}=c.mission.result;
    const card=(run,label)=>{
      const s=run.summary;
      const facts=[['控制器最高温度',s.max_controller_temperature_c,'°C',1],['电机最高温度',s.max_motor_temperature_c,'°C',1],['推进缺供',s.unmet_propulsion_kwh,'kWh',3],['任务能量',s.energy_used_kwh,'kWh',2],['控制器鼓风耗能',s.controller_blower_energy_kwh,'kWh',4]];
      return `<article class="cad-mission-policy ${run.policy.id==='planner'?'planner':''}"><h4>${label}</h4>${verdict(s)}<dl>${facts.map(([key,value,unit,decimals])=>`<div><dt>${key}</dt><dd>${fmt(value,decimals)} ${unit}</dd></div>`).join('')}</dl></article>`;
    };
    const graph=guideChart(planner,[{name:'控制器（两侧较高值）',color:COLORS.cyan,key:'cyan',value:row=>max(row.controller_temperature_c||[])},{name:'电机（两侧较高值）',color:COLORS.amber,key:'amber',value:row=>max(row.motor_temperature_c||[])}],{unit:'°C',label:'CAD 任务中控制器与电机分离温度节点'});
    byId('cad-mission-result').innerHTML=`<div class="cad-mission-result-heading"><h3>${esc(planner.scenario.name)} · ${fmt(runAmbient(planner),0)} °C</h3><span>固定系统质量 ${fmt(planner.design.mass_kg,3)} kg · 新增 CAD 降阶模型</span></div><div class="cad-mission-comparison">${card(baseline,'热感知固定规则')}${card(planner,'受约束规划器')}</div><div class="cad-mission-chart">${graph}</div><p class="cad-mission-note">图中为规划器完整任务。控制器与电机损耗分别进入各自热节点；鼓风电耗单独计入功率预算。系统质量保留原方案，加两件散热器、两块 0.6 kg 控制器底板和 1 kg 风道。质量仅作静态代理，不产生飞行性能结论；本分支不能与旧合并热节点模型直接归因对比。</p>`;
    byId('cad-mission-result').hidden=false;
  }

  function evidence() {
    if(!current()) return null;
    return {kind:'cad_geometry_thermal_mission_evidence',steady_state_comparison:c.result,mission:c.mission&&c.mission.revision===c.revision&&c.mission.missionRevision===c.missionRevision?c.mission.result:null};
  }
  function renderEvidence(){const data=evidence();byId('cad-evidence-json').textContent=data?JSON.stringify(data,null,2):'尚无与当前输入匹配的计算证据。';}
  function download(blob,filename){const url=URL.createObjectURL(blob),anchor=document.createElement('a');anchor.href=url;anchor.download=filename;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  function exportJson(){const data=evidence();if(data)download(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),`aerolab-cad-${c.result.candidate.input_hash.slice(0,12)}.json`);}
  async function exportStep(){
    if(!current()||c.stepBusy||!c.result.candidate.cad?.step_available)return;
    const revision=c.revision,geometry=c.result.candidate.geometry,hash=c.result.candidate.input_hash;
    c.stepBusy=true;error();controls();
    try{
      const response=await fetch('/api/cad/step',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({geometry})});
      if(!response.ok){const problem=await response.json();throw new Error(problem.error||`HTTP ${response.status}`);}
      const blob=await response.blob();
      if(revision!==c.revision)return;
      if(!blob.size)throw new Error('STEP 文件为空');
      download(blob,`aerolab-heatsink-${hash.slice(0,12)}.step`);
    }catch(failure){if(revision===c.revision)error(`STEP 导出未完成：${failure.message}`);}
    finally{c.stepBusy=false;controls();}
  }

  byId('cad-form').addEventListener('submit',(event)=>{event.preventDefault();evaluate();});
  byId('cad-apply').addEventListener('click',applyMission);
  byId('cad-export-json').addEventListener('click',exportJson);
  byId('cad-export-step').addEventListener('click',exportStep);
  window.cadWorkspace={open};
})();
