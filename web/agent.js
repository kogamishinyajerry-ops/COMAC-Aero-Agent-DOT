/* Read-only presentation of frozen native-assistant engineering tool records. */
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = (value, digits = 2) => Number(value).toFixed(digits);
  const names = ['固定需求','保留失败','调用工具','修改设计','交付结果','新要求再试'];
  const caseName = id => id.startsWith('nominal') ? '名义工况' : id.startsWith('pressure_loss') ? '压差下降' : id.startsWith('closure') ? '通道封闭' : '组合故障';
  const geometry = candidate => `${candidate.N_fins} 片 × ${fmt(candidate.fin_thickness_m * 1000, 2)} mm`;
  const operationNames = {init:'固定任务',inspect:'检查候选',evaluate:'PDE 求解',cad:'生成 CAD',finalize:'汇总验收'};
  let data = null, trial = 'development', step = 0, loading = false;
  function selectionFromHash() {
    const match = /^#(development|heldout)\/([0-5])$/.exec(location.hash);
    return match ? {trial:match[1],step:Number(match[2])} : {trial:'development',step:0};
  }
  function select(nextTrial, nextStep, focus = true) {
    const hash = `#${nextTrial}/${nextStep}`;
    if (location.hash !== hash) history.pushState(null, '', hash);
    trial = nextTrial; step = nextStep; render();
    if (focus) {
      const stage = $('agent-stage');
      stage.focus({preventScroll:true});
      if (stage.getBoundingClientRect().top < 0) stage.scrollIntoView({block:'start'});
    }
  }
  function context(id = trial) {
    const run = data.runs[id];
    const selected = run.candidates.find(c => c.design_id === run.final.selected_design_id);
    const rejected = run.evaluations.find(e => e.design_id !== selected.design_id);
    const baseline = run.candidates.find(c => c.design_id === rejected.design_id);
    const selectedCases = run.final.case_verification;
    const worst = Math.max(...selectedCases.map(c => c.worst_mesh_temperature_C));
    return {run,selected,rejected,baseline,worst};
  }
  const title = (kicker, text, intro, id) => `<div class="stage-kicker"><span>${esc(kicker)}</span><span class="source-id">RECORD / ${esc(id)}</span></div><h2 class="stage-title" id="agent-title">${text}</h2><p class="stage-intro">${intro}</p>`;
  const takeaway = (text) => `<div class="takeaway"><span>这一幕看什么</span><p>${text}</p></div>`;
  function schematic(run) {
    const task = run.task;
    return `<div class="visual-board"><svg viewBox="0 0 490 265" role="img" aria-label="热量经均匀基底与翅片进入气流的示意，包含压差下降和一条内部通道封闭"><defs><marker id="flow-arrow" markerWidth="7" markerHeight="7" refX="5" refY="3.5" orient="auto"><path d="M0,0 L6,3.5 L0,7" fill="#5b9698"/></marker></defs><text x="26" y="32" fill="#6b8790" font-size="10" font-family="system-ui">冷却部件 / 热与流动边界示意</text><path d="M91 72H410V191H91" fill="#edf5f7" stroke="#c3d5df" stroke-dasharray="4 5"/><g fill="#9bbfcb" stroke="#5f8e9c" stroke-width="1"><rect x="101" y="182" width="291" height="15" rx="1"/>${Array.from({length:11},(_,i)=>`<rect x="${108+i*26}" y="86" width="6" height="96"/>`).join('')}</g><rect x="115" y="84" width="17" height="98" fill="#d08769" opacity=".7"/><g fill="none" stroke="#5b9698" stroke-width="2" marker-end="url(#flow-arrow)"><path d="M28 125H87"/><path d="M416 125H465"/></g><text x="28" y="112" fill="#4c767e" font-size="11" font-family="system-ui">${esc(task.inlet_temperature_C)}°C</text><path d="M180 234V208 M239 234V208 M298 234V208" stroke="#c88957" stroke-width="2"/><path d="m177 214 3-7 3 7m53 0 3-7 3 7m53 0 3-7 3 7" fill="none" stroke="#c88957" stroke-width="2"/><text x="321" y="225" fill="#936d4e" font-size="11" font-family="system-ui">热载荷 ${esc(task.cases[0].heat_load_W)} W</text><path d="M122 85V61H171" fill="none" stroke="#b57359"/><text x="178" y="64" fill="#a36c54" font-size="10" font-family="system-ui">故障：第一个内部通道封闭</text></svg><div class="visual-caption">示意图不代表 CFD 温度场。温度约束指所需均匀基底温度，质量约束仅计翅片铝材。</div></div>`;
  }
  function stepRequirements(c) {
    const t = c.run.task, pressures = [...new Set(t.cases.map(x=>x.pressure_Pa))];
    return title('01 / REQUIREMENTS', '先固定要求，再允许改设计。', trial === 'development' ? '助手收到的是一个带质量约束的散热任务。几何可以换，负荷、故障和温度上限必须保留。' : '工具与协议冻结后，独立出题者才释放这组新要求。较低热载荷，伴随更紧的质量上限和更低供气压差。', t.task_id) + `<div class="stage-columns">${schematic(c.run)}<div><dl class="requirement-list"><div><dt>每个工况热载荷</dt><dd>${t.cases[0].heat_load_W}<small>W</small></dd></div><div><dt>均匀基底温度上限</dt><dd>${t.max_base_temperature_C}<small>°C</small></dd></div><div><dt>翅片铝质量上限</dt><dd>${t.max_fin_mass_g}<small>g</small></dd></div><div><dt>名义 / 故障供气压差</dt><dd>${pressures.join(' / ')}<small>Pa</small></dd></div></dl><p class="requirement-note">检查 ${t.cases.length} 个指定工况，候选来自固定的 9 种几何。先检查质量与 Reynolds 适用范围，再进行 PDE 求解与网格复核。</p></div></div>` + takeaway('任务文件在执行前固定。后续“通过”只能针对这组部件筛选要求，不能改写原 60 W 案例的失败。');
  }
  function comparisonCard(candidate, temperature, massLimit, rejected, note) {
    return `<article class="comparison-card ${rejected?'rejected':'accepted'}"><div class="card-top"><span>${rejected?'已计算的失败方案':'经过复核的候选'}</span><span class="badge ${rejected?'fail':''}">${rejected?'质量不满足':'有条件通过'}</span></div><p class="design-name">${esc(geometry(candidate))}</p><div class="metric-line ${rejected?'fail':'pass'}"><span>翅片质量 / 上限 ${massLimit} g</span><strong>${fmt(candidate.fin_only_mass_g)}<small>g</small></strong></div><div class="metric-line"><span>${rejected?'失败方案主网格温度':'所选方案最差网格温度'}</span><strong>${fmt(temperature)}<small>°C</small></strong></div><p class="card-note">${note}</p></article>`;
  }
  function stepFailure(c) {
    const t = c.run.task, over = c.baseline.fin_only_mass_g - t.max_fin_mass_g;
    return title('02 / REJECTED BASELINE', '温度过关，方案仍然要被拒绝。', trial === 'development' ? '助手没有隐藏起始方案：先实际计算组合故障，再将质量超标作为拒绝依据。' : '直接沿用开发任务的成功设计并不行。助手重新求解旧方案，保留质量超标的失败记录。', `${t.task_id} / action ${String(c.rejected.sequence).padStart(3,'0')}`) + `<div class="stage-columns">${comparisonCard(c.baseline,c.rejected.required_uniform_base_temperature_C,t.max_fin_mass_g,true,'此温度来自失败方案的一次主网格求解，未对该失败方案做完整网格验收。')}<div class="rule-panel"><h3>同时满足，缺一不可</h3><div class="rule-item"><span>✓</span><div><strong>这一次热计算低于 ${t.max_base_temperature_C}°C</strong><small>只说明这个网格、这个工况的数值结果</small></div></div><div class="rule-item fail"><span>×</span><div><strong>翅片质量超出 ${fmt(over)} g</strong><small>不能用温度表现抵消质量约束</small></div></div><div class="rule-item"><span>→</span><div><strong>保留要求，改变几何</strong><small>失败记录、工具输入与返回值全部保留</small></div></div><a class="button secondary" href="${esc(c.rejected.source_href)}" target="_blank" rel="noopener">查看这次失败求解 ↗</a></div></div>` + takeaway('有说服力的工程闭环，要能解释为什么拒绝一个看起来表现不错的方案。');
  }
  function eventDescription(event) {
    const r = event.request || {};
    if(event.operation === 'evaluate') return `${r.design || ''} · ${caseName(r.case_id || '')} · ${r.mesh || ''} 网格`;
    if(event.operation === 'inspect') return '解析检查九种候选的质量与流动适用范围';
    if(event.operation === 'cad') return '生成 STEP / STL，并执行实体与质量回读检查';
    if(event.operation === 'finalize') return '汇总固定要求、网格门槛、失败保留与 CAD 验收';
    return '建立不可变任务与版本指纹';
  }
  function stepTools(c) {
    const r = c.run, counts = r.final, events = r.events;
    const inspect = events.find(e=>e.operation==='inspect'), first = events.find(e=>e.operation==='evaluate'), cad = events.find(e=>e.operation==='cad'), final = events.find(e=>e.operation==='finalize');
    return title('03 / ACTUAL TOOL TRACE', '选择之后，真的调用工具。', '以下按保存的动作记录整理。每次求解都带几何、工况、网格和结果指纹；这里没有模拟“正在思考”的动画。', r.task.task_id) + `<div class="timeline"><article class="tool-block"><span class="tool-no">01 / INSPECT</span><h3>先看可选范围</h3><p>质量与流动适用性分开检查，不能只选最轻的。</p><a href="${esc(inspect.result_href)}" target="_blank" rel="noopener">${String(inspect.sequence).padStart(3,'0')} / 原始检查 ↗</a></article><article class="tool-block"><span class="tool-no">02 / EVALUATE</span><h3>失败也要求解</h3><p>实际计算旧方案，再为改选方案完成各工况与三组网格。</p><a href="${esc(first.result_href)}" target="_blank" rel="noopener">${String(first.sequence).padStart(3,'0')} / 原始求解 ↗</a></article><article class="tool-block"><span class="tool-no">03 / CAD</span><h3>生成并读回实体</h3><p>输出真实 STEP / STL，核对体积、拓扑和翅片质量。</p><a href="${esc(cad.result_href)}" target="_blank" rel="noopener">${String(cad.sequence).padStart(3,'0')} / CAD 记录 ↗</a></article><article class="tool-block"><span class="tool-no">04 / FINALIZE</span><h3>逐项做最终检查</h3><p>按固定协议汇总数值门槛与任务约束，给出限定结论。</p><a href="${esc(final.result_href)}" target="_blank" rel="noopener">${String(final.sequence).padStart(3,'0')} / 验收记录 ↗</a></article></div><div class="counts-line"><span><strong>${counts.solver_calls}</strong> 次真实 PDE 求解</span><span><strong>${counts.cad_calls}</strong> 次 CAD 调用</span><span><strong>${counts.tool_calls_including_this}</strong> 个工具动作</span><span>记录执行期 <strong>${fmt(counts.wall_seconds/60,1)}</strong> 分钟</span></div><details class="trace-details"><summary>展开全部 ${events.length} 个顺序动作与原文依据</summary><ol class="event-list">${events.map(e=>`<li><span class="sequence">${String(e.sequence).padStart(3,'0')}</span><strong>${esc(operationNames[e.operation]||e.operation)}</strong><div><p>${esc(eventDescription(e))}</p><p class="event-original">${esc(e.decision_summary)}</p></div><a href="${esc(e.result_href)}" target="_blank" rel="noopener">结果 ↗</a></li>`).join('')}</ol></details>` + takeaway('原生助手负责选择与编排，工具负责可检查的计算。浏览器仅回放这次真实执行，不是独立自主运行的模型产品。');
  }
  function caseChart(c) {
    const t = c.run.task, lo = t.inlet_temperature_C, hi = t.max_base_temperature_C;
    return `<div class="case-chart"><h3>所选方案 · 各工况三组网格中的最差温度</h3>${c.run.final.case_verification.map(row=>`<div class="case-row"><span>${caseName(row.case_id)}</span><svg viewBox="0 0 300 15" role="img" aria-label="${caseName(row.case_id)} ${fmt(row.worst_mesh_temperature_C)} 摄氏度，上限 ${hi}"><rect width="300" height="9" y="3" rx="3" fill="#e2e9ed"/><rect width="${Math.max(0,Math.min(300,300*(row.worst_mesh_temperature_C-lo)/(hi-lo)))}" height="9" y="3" rx="3" fill="#4c9690"/><path d="M299 0V15" stroke="#b47452" stroke-width="2"/></svg><strong>${fmt(row.worst_mesh_temperature_C)} °C</strong></div>`).join('')}<p class="case-caption">条形范围 ${lo}–${hi}°C，右端为上限；所有指定工况各有主网格、空间细化、轴向细化三组求解。此图不表示局部热点或实验测量。</p></div>`;
  }
  function stepDesign(c) {
    const t = c.run.task, saving = c.baseline.fin_only_mass_g-c.selected.fin_only_mass_g;
    return title('04 / GEOMETRY ITERATION', trial==='development'?'保留 16 片，减薄到 0.60 mm。':'新要求下，换成 12 片薄翅片。', `实际改选后，翅片减重 ${fmt(saving)} g。${trial==='development'?'更轻的 12 片候选在该任务的供气条件下超出声明 Reynolds 范围，不能直接选用。':'原开发方案超出新质量上限；在更低供气压差下，新候选通过声明的 Reynolds 范围检查。'}`, c.selected.design_id) + `<div class="stage-columns">${comparisonCard(c.baseline,c.rejected.required_uniform_base_temperature_C,t.max_fin_mass_g,true,'保留失败主网格，未改动原任务。')}${comparisonCard(c.selected,c.worst,t.max_fin_mass_g,false,`最差温度余量 ${fmt(t.max_base_temperature_C-c.worst)}°C；数值检查与物理有效性不是同一件事。`)}</div>${caseChart(c)}` + takeaway('选型依据是同一任务下的质量、温度与模型适用性。这里报告有限候选中的条件可行结果，不宣称全局最优。');
  }
  function stepDeliver(c) {
    const cad = c.run.cad, mass = cad.thermal_geometry_mapping.kernel_fin_only_mass_g, total = cad.step_roundtrip.mass_kg*1000;
    return title('05 / VERIFIED DELIVERABLE', '结果，要能成为可打开的工程文件。', '几何参数同时进入热模型与 CAD。STEP 生成后实际读回，STL 检查封闭性，翅片质量与模型独立核对。', c.selected.design_id) + `<div class="stage-columns wide-left"><div class="visual-board"><img src="${esc(cad.preview_href)}" alt="${esc(geometry(c.selected))}散热部件参数预览，与已导出 CAD 使用相同几何参数"><div class="visual-caption">冻结执行记录中的参数化预览；不是 CAD 回读截图，也不是制造图纸。</div></div><div class="cad-proof"><h3>${esc(geometry(c.selected))}<br>真实 STEP + STL</h3><p class="card-note">${cad.parameters.length_mm} × ${cad.parameters.width_mm} mm 基底轮廓 · ${cad.parameters.fin_height_mm} mm 翅高</p><div class="metric-line pass"><span>验收使用的翅片质量</span><strong>${fmt(mass)}<small>g</small></strong></div><div class="metric-line"><span>含说明性基底的总固体质量</span><strong>${fmt(total)}<small>g</small></strong></div><p class="card-note">3 mm 基底不属于翅片质量要求；45.2 mm 风道是数学边界，未导出为风道实体。</p><div class="download-group"><a id="agent-step-download" class="button primary" href="${esc(cad.downloads.step.href)}" download>↓ STEP</a><a id="agent-stl-download" class="button secondary" href="${esc(cad.downloads.stl.href)}" download>↓ STL</a><a class="button secondary" href="${esc(cad.source_href)}" target="_blank" rel="noopener">回读检查 ↗</a></div></div></div>` + takeaway('可核查的交付包括几何字节、回读结果和对应任务。部件数值筛选通过，不代表飞机散热、制造可行性或适航已经通过。');
  }
  function stepHeldout(c) {
    const dev = context('development'), h = context('heldout'), grade = data.independent_grade, checks = Object.entries(grade.checks), passed = checks.filter(([,value])=>value===true).length;
    return title('06 / INDEPENDENT HELDOUT', '换一组要求，旧答案还够用吗？', '协议与工具冻结后，由独立出题者释放新要求。执行者拒绝旧方案，重新求解并交付另一种几何。', h.run.task.task_id) + `<div class="grade-banner"><span class="grade-seal">✓</span><div><strong>独立证据检查 ${passed} / ${checks.length} 通过</strong><p>包括动作链、固定任务、数值门槛、CAD 实际字节与独立几何回读。不是对物理模型的实验验证。</p></div></div><div class="transfer"><article class="transfer-card"><span class="label">DEVELOPMENT / 开发任务</span><h3>${esc(geometry(dev.selected))}</h3><p>50 W · 85°C · 30 g · 25 / 18 Pa<br>翅片 ${fmt(dev.selected.fin_only_mass_g)} g · 最差 ${fmt(dev.worst)}°C</p></article><span class="transfer-arrow" aria-hidden="true">→</span><article class="transfer-card"><span class="label">HELDOUT / 新要求</span><h3>${esc(geometry(h.selected))}</h3><p>36 W · 80°C · 25 g · 17 / 11 Pa<br>翅片 ${fmt(h.selected.fin_only_mass_g)} g · 最差 ${fmt(h.worst)}°C</p></article></div><div class="boundary-note"><strong>这次证明到哪里：</strong>熟悉的九种几何中，25 g 上限只留下一个质量合格候选。本次主要验证新约束处理、实际求解、复核与诚实报告，不能称为广泛工程泛化。最大 Re 约 2235.5，距声明上限仅约 2.8%，不是物理鲁棒性保证。</div><details class="trace-details"><summary>查看独立评分的 ${checks.length} 项检查与范围限制</summary><ul class="check-list">${checks.map(([name,value])=>`<li>${esc(name)}: ${value===true?'PASS':'FAIL'}</li>`).join('')}</ul><p class="card-note">逻辑隔离不等于强制信息屏障；独立参考重算使用同一冻结求解器。评分不能独立证明运行模型身份、所有外部 API 的缺席或所有协议外访问的缺席。</p><a class="button secondary" href="${esc(data.links.independent_grade || '/agent/evidence/heldout_independent_grade.json')}" target="_blank" rel="noopener">打开机器可读评分 ↗</a></details>` + takeaway('能处理同一家族里的新要求，是可见的一步。下一步能力的主张，仍须由更丰富的独立任务与物理证据支撑。');
  }
  function render() {
    if(!data) return;
    const c = context();
    document.querySelectorAll('[data-trial]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.trial===trial)));
    document.querySelectorAll('[data-step]').forEach(b=>{if(Number(b.dataset.step)===step)b.setAttribute('aria-current','step');else b.removeAttribute('aria-current');});
    $('agent-stage').innerHTML = [stepRequirements,stepFailure,stepTools,stepDesign,stepDeliver,stepHeldout][step](c);
    $('agent-prev').disabled=step===0;
    $('agent-next').textContent = step<5?`${names[step+1]} →`:(trial==='development'?'查看留出任务全过程 →':'回到留出任务起点 ↺');
    $('agent-progress').textContent = `${String(step+1).padStart(2,'0')} / 06`;
    $('agent-evidence-content').innerHTML = `<div class="evidence-links"><a href="${esc(c.run.links.task)}" target="_blank" rel="noopener">固定任务 ↗</a><a href="${esc(c.run.links.session)}" target="_blank" rel="noopener">运行声明 ↗</a><a href="${esc(c.run.links.final)}" target="_blank" rel="noopener">最终验收 ↗</a><a href="${esc(data.links.report)}" target="_blank" rel="noopener">完整中文报告 ↗</a></div><dl class="fingerprints"><dt>任务 ID</dt><dd>${esc(c.run.task.task_id)}</dd><dt>任务 SHA-256</dt><dd>${esc(c.run.session.task_sha256)}</dd><dt>冻结协议 SHA-256</dt><dd>${esc(c.run.session.protocol_sha256)}</dd><dt>工具适配器 SHA-256</dt><dd>${esc(c.run.session.adapter_sha256)}</dd><dt>STEP SHA-256</dt><dd>${esc(c.run.cad.downloads.step.sha256)}</dd></dl><p class="card-note">此页面读取的证据经本地标准库校验；不会因此新增一次 PDE 或 CAD 运行。具体运行模型身份未验证，外部模型 API 调用数来自执行声明。</p>`;
    document.title = `${names[step]} · 工程智能体 · 航空电热实验室`;
  }
  async function load() {
    if(loading) return;
    loading=true; data=null;
    $('agent-loading').hidden=false; $('agent-error').hidden=true; $('agent-workspace').hidden=true; $('agent-evidence').hidden=true;
    document.querySelectorAll('[data-trial], #agent-reset, #agent-export').forEach(b=>b.disabled=true);
    const controller = new AbortController();
    const timeout = setTimeout(()=>controller.abort(),30000);
    try {
      const response = await fetch('/api/agent/replay',{cache:'no-store',signal:controller.signal});
      if(!response.ok) throw new Error(`证据服务返回 ${response.status}。请确认当前工程完整，且从同一个本地服务打开此页。`);
      const value = await response.json();
      if(value.execution!=='recorded_native_assistant_trial'||value.live_computation!==false||!value.runs?.development||!value.runs?.heldout) throw new Error('证据格式不匹配，未显示任何未经核对的结果。');
      data=value;
      ({trial,step}=selectionFromHash());
      if(!/^#(development|heldout)\/[0-5]$/.test(location.hash)) history.replaceState(null,'',`#${trial}/${step}`);
      render();
      $('agent-workspace').hidden=false; $('agent-evidence').hidden=false;
      document.querySelectorAll('[data-trial], #agent-reset, #agent-export').forEach(b=>b.disabled=false);
    } catch(error) {
      data=null; $('agent-error-text').textContent=error.name==='AbortError'?'读取超时。当前没有新的计算在后台运行，可以重试读取。':error.message;
      $('agent-error').hidden=false;
    } finally {clearTimeout(timeout);loading=false;$('agent-loading').hidden=true;}
  }
  document.querySelector('.skip-link').addEventListener('click', event => {
    event.preventDefault();
    $('agent-stage').focus({preventScroll:true});
    $('agent-stage').scrollIntoView({block:'start'});
  });
  document.querySelectorAll('[data-step]').forEach(b=>b.addEventListener('click',()=>select(trial,Number(b.dataset.step))));
  document.querySelectorAll('[data-trial]').forEach(b=>b.addEventListener('click',()=>select(b.dataset.trial,0)));
  $('agent-prev').addEventListener('click',()=>{if(step>0) select(trial,step-1);});
  $('agent-next').addEventListener('click',()=>step<5?select(trial,step+1):select('heldout',0));
  $('agent-reset').addEventListener('click',()=>select(trial,0));
  $('agent-retry').addEventListener('click',load);
  $('agent-export').addEventListener('click',()=>{
    if(!data) return;
    const exported={schema:'native_agent_demo_export_v1',execution:data.execution,live_computation:false,selection:{trial,step},provenance:data.provenance,protocol:data.protocol,run:data.runs[trial],independent_grade:data.independent_grade,links:data.links};
    const url=URL.createObjectURL(new Blob([JSON.stringify(exported,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download=`native-agent-${trial}-evidence.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  window.addEventListener('popstate',()=>{({trial,step}=selectionFromHash());render();});
  window.addEventListener('hashchange',()=>{({trial,step}=selectionFromHash());render();});
  load();
})();
