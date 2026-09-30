/* A live, bounded teaching sequence. It never changes expert-workbench inputs. */
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const number = (value, digits=1) => finite(value) ? value.toFixed(digits) : '—';
  const signed = (value, digits=1) => finite(value) ? `${value > 0 ? '+' : ''}${value.toFixed(digits)}` : '—';
  const safe = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const story = {active:false, busy:false, request:0, controller:null, data:null, index:0, meshes:new Map()};
  const steps = [
    {caseId:'source_load', mode:'assembled', question:'我们到底重建了什么？', answer:'一个 Mod II 单侧短舱：前部外转子电机，后部并排双控制器，上方独立低压新风口。几何、气路与热节点使用同一组参数。'},
    {caseId:'source_pressure', mode:'cutaway', flow:true, question:'公开满负荷，能直接当作温度预测吗？', answer:'不能。先看模型与公开分析的差距，再谈设计。通过质量、能量守恒，只证明这组方程解得自洽。'},
    {caseId:'hot_day', mode:'open', thermal:true, selected:'motor_winding', question:'环境升温 10°C，哪个约束先变紧？', answer:'用明确降低的损耗做教学，保持密度与压力假设不变，只抬高环境温度。比较同一硬件在两组输入下的电机节点。'},
    {caseId:'more_fins', mode:'open', flow:true, thermal:true, selected:'cmc_left_hv', question:'多加鳍片，会不会让整套系统更凉？', answer:'局部改进不等于系统改进。36 片鳍片增加换热面积，也改变下游阻力、混合腔压力和电机冷却分流。'},
    {caseId:'redistributed_cooling', mode:'open', flow:true, thermal:true, selected:'motor_winding', question:'减鳍片、扩排气，究竟拿什么换什么？', answer:'把每组 CMC 改为 12 片鳍片，并将电机顶部排气从 9000 扩至 16000 mm²。电机冷却与重量改善，但高压侧变热，排气压损功率增加。两项修改仍在同一热天边界下计算。'},
    {caseId:'redistributed_cooling', mode:'open', question:'现在可以批准这个设计了吗？', answer:'还不可以。当前结果只支持下一轮研究的候选取舍；未标定误差、尺寸推定和相关式限制仍可能改变判断。'}
  ];
  const teachingBoundary = '教学输入：0.25×公开损耗，不是 25% 飞机功率；未做物理验证。热天扰动固定密度与压力假设，不能代表完整天气变化。';
  const metric = (label,value,unit='',note='',kind='') => `<div class="story-metric ${kind}"><span>${safe(label)}</span><strong>${safe(value)}<small>${safe(unit)}</small></strong><p>${safe(note)}</p></div>`;
  const nodeTemp = (summary,key) => summary.within_model_limits ? number(summary[key]) : '超范围';
  async function requestJSON(path, body, signal) {
    const response = await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal});
    if (!response.ok) {const failure=await response.json().catch(()=>({}));throw new Error(failure.error || `计算失败 (${response.status})`);}
    return response.json();
  }
  function controls() {
    $('story-prev').disabled = story.busy || story.index===0 || !story.data;
    $('story-next').disabled = story.busy || !story.data;
    $('story-next').textContent = story.index===steps.length-1 ? '从头再看 ↺' : '下一步 →';
    $('story-dots').innerHTML = steps.map((_,i)=>`<button data-story-step="${i}" aria-label="第 ${i+1} 步" aria-current="${i===story.index?'step':'false'}" ${story.busy||!story.data?'disabled':''}>${i+1}</button>`).join('');
    $('story-dots').querySelectorAll('button').forEach(button=>button.addEventListener('click',()=>go(Number(button.dataset.storyStep))));
  }
  function exposeError(error) {
    $('story-request-status').textContent = `${error.message}。可返回工作台后重试，未采用中途结果。`;
    $('story-execution').textContent = '本次讲解未完成';
    window.NacelleLab.loading(false);
  }
  function showEvidence(run, summary) {
    const diagnostics=run.diagnostics;
    $('story-evidence-content').innerHTML = `<p>本次求解 · 输入 ${safe(run.input_hash.slice(0,16))} · 几何 ${safe(run.metrics.fingerprint.slice(0,16))}</p><p>质量残差 ${safe(diagnostics.max_mass_residual_kg_s.toExponential(2))} kg/s；能量残差 ${safe(diagnostics.energy_residual_w.toExponential(2))} W。守恒检查 ${diagnostics.conservation_pass?'通过':'未通过'}；物理验证：未完成。</p><p>${summary.corner_count} 个假设角点中，${summary.negative_reference_corner_count} 个最小参考裕度低于零（其中 ${summary.in_domain_negative_reference_corner_count} 个仍在筛查域内），${summary.out_of_domain_corner_count} 个超出筛查域；范围不是置信区间或保证的上下界。未覆盖尺寸公差、旋转效应及全部热负荷误差。</p><a href="https://ntrs.nasa.gov/api/citations/20230006888/downloads/Borer_Bui_Smith_X-57_thermal_analysis.pdf" target="_blank" rel="noopener">NASA 原始分析：图 5–7、表 4、表 6–7 ↗</a>`;
  }
  function visual(index) {
    const data=story.data, all=data.summaries, current=all[steps[index].caseId];
    if(index===0) return metric('公开来源约束','Mod II','','拓扑与历史尺度有出处；未公开尺寸仍为推定')+metric('同一参数贯穿','CAD → 热网','','每个候选独立重算流量与热量，没有贴上旧热图');
    if(index===1) {
      const diagnostic=data.cases.source_pressure.source_flow_diagnostic;
      const total=diagnostic.computed_kg_s.motor_internal_total, source=diagnostic.published_kg_s.motor_internal_total;
      return metric('满负荷可信度',current.within_model_limits?'域内但未验证':'超出筛查域','','不以原始诊断温度判断真实飞机','caution')+metric('电机总冷却流量',number(total,3),'kg/s',`公开 CFD 参考 ${number(source,3)} kg/s；节点与边界未完全匹配`)+metric('槽道占内部流量',number(diagnostic.computed_kg_s.motor_slots/total*100),'%',`公开 CFD 参考 ${number(diagnostic.published_kg_s.motor_slots/source*100)}%；总量接近仍不能验证分路与换热`);
    }
    if(index===2) return metric('基线环境 35.9°C',nodeTemp(all.baseline,'motor_temperature_c'),'°C','电机绕组代理；24 片鳍片')+metric('热天环境 45.9°C',nodeTemp(all.hot_day,'motor_temperature_c'),'°C',`相对来源 124°C 参考线：${signed(all.hot_day.min_margin_c)}°C 最小节点裕度`,'caution')+metric('唯一输入变化','+10','°C','同样 0.25×损耗、几何、密度与压力假设');
    if(index===3||index===4) {
      const delta=data.deltas_vs_hot_day[steps[index].caseId];
      const valid=current.within_model_limits&&all.hot_day.within_model_limits;
      return metric('电机绕组变化',valid?signed(delta.motor_temperature_c):'超范围',valid?'°C':'',`电机流量变化 ${signed(delta.motor_flow_kg_s*1000,2)} g/s`,delta.motor_temperature_c>0?'caution':'')+metric('CMC 高压侧变化',valid?signed(delta.hv_temperature_c):'超范围',valid?'°C':'',`混合腔压力变化 ${signed(delta.motor_mix_pressure_pa)} Pa`,delta.hv_temperature_c>0?'caution':'')+metric('双 CMC 散热器质量',signed(delta.hv_pair_mass_kg,3),'kg',`相对热天 24 片基线；总重建硬件变化 ${signed(delta.mass_kg,3)} kg`)+metric('被动压损功率变化',signed(delta.hydraulic_dissipation_w),'W','不是风扇电耗，也不是飞机总冷却阻力');
    }
    return `<div class="story-comparison">${[['hot_day','24 片基线'],['more_fins','36 片候选'],['redistributed_cooling','12 片 + 扩排气']].map(([id,label])=>{
      const s=all[id],range=s.scenario_min_margin_c;
      return `<article><h3>${label}</h3><dl><div><dt>电机代理</dt><dd>${nodeTemp(s,'motor_temperature_c')} °C</dd></div><div><dt>CMC 高压代理</dt><dd>${nodeTemp(s,'hv_temperature_c')} °C</dd></div><div><dt>双散热器质量</dt><dd>${number(s.hv_pair_mass_kg,3)} kg</dd></div><div><dt>被动压损功率</dt><dd>${number(s.hydraulic_dissipation_w)} W</dd></div><div><dt>名义最小参考裕度</dt><dd>${s.within_model_limits?signed(s.min_margin_c):'超范围'} °C</dd></div></dl><p class="story-corner-warning">${s.negative_reference_corner_count}/${s.corner_count} 角点参考裕度低于零，其中 ${s.in_domain_negative_reference_corner_count} 个在筛查域内。域内角点最小裕度 ${number(s.in_domain_corner_min_margin_c)}°C。</p><p>另有 ${s.out_of_domain_corner_count}/${s.corner_count} 角点超出域。全部原始诊断范围 ${number(range.min)}～${number(range.max)}°C，含域外值，不能证明设计安全。</p></article>`;
    }).join('')}</div><div class="story-decision"><strong>结论：保留候选，暂不做飞机设计决策</strong><span>下一步应获取实际通道尺寸、分路流量与旋转换热/接触数据，检查独立工况；软件测试通过不替代这些证据。</span><button id="export-story" class="secondary-button">下载完整推演证据 JSON ↓</button></div>`;
  }
  async function go(index) {
    if(!story.active || !story.data || story.busy) return;
    const token=++story.request, step=steps[index], run=story.data.cases[step.caseId];
    story.busy=true;controls();window.NacelleLab.loading(true);
    $('story-request-status').textContent='核对当前步骤的几何与求解指纹…';
    story.controller=new AbortController();
    try {
      let geometry=story.meshes.get(run.metrics.fingerprint);
      if(!geometry) {geometry=await requestJSON('/api/nacelle/geometry',{geometry:run.geometry},story.controller.signal);story.meshes.set(run.metrics.fingerprint,geometry);}
      if(!story.active||token!==story.request)return;
      window.NacelleLab.show(geometry,run,{...step,caseId:step.caseId});
      story.index=index;
      $('story-panel').dataset.step=String(index);
      document.body.dataset.storyStep=String(index);
      $('story-kicker').textContent=`ENGINEERING STORY / ${String(index+1).padStart(2,'0')} OF 06`;
      $('story-question').textContent=step.question;$('story-answer').textContent=step.answer;
      $('story-visual').innerHTML=visual(index);
      $('story-boundary').textContent=index===0?'公开峰值损耗 · 默认推定来流边界；来源分析与本模型都不是实验真值。':index===1?'公开峰值损耗 · 表 7 压力增量近似，含对称化与密度假设；仍不是完全匹配的 NASA CFD 工况，未拟合温度。':teachingBoundary;
      $('story-execution').textContent=`本次计算 · 6 组输入 · ${story.data.story_hash.slice(0,10)}`;
      showEvidence(run,story.data.summaries[step.caseId]);
      $('story-evidence').open=false;
      $('story-request-status').textContent='';
      if($('export-story')) $('export-story').addEventListener('click',()=>{
        const blob=new Blob([JSON.stringify(story.data,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');
        link.href=url;link.download=`x57-design-story-${story.data.story_hash.slice(0,12)}.json`;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
      });
    } catch(error) {if(error.name!=='AbortError'&&token===story.request) exposeError(error);}
    finally {if(token===story.request){story.busy=false;story.controller=null;window.NacelleLab.loading(false);controls();}}
  }
  async function start() {
    if(story.active||!window.NacelleLab?.start())return;
    story.active=true;story.busy=true;story.index=0;story.data=null;story.meshes.clear();
    const token=++story.request;story.controller=new AbortController();
    document.body.dataset.experience='story';$('story-panel').hidden=false;$('start-story').hidden=true;$('open-workbench').hidden=false;
    $('story-visual').replaceChildren();$('story-question').textContent='先核对同一模型的六组输入';$('story-answer').textContent='公开满负荷及压力参考、低损耗基线、热天扰动和两个鳍片候选，全部重新求解。';$('story-boundary').textContent=teachingBoundary;
    $('story-request-status').textContent='正在计算，可随时返回工作台取消这次讲解';$('story-execution').textContent='正在本地求解';controls();
    try {
      const data=await requestJSON('/api/nacelle/story',{},story.controller.signal);
      if(!story.active||token!==story.request)return;
      if(data.execution!=='computed'||!data.story_hash)throw new Error('讲解结果缺少执行身份');
      story.data=data;story.busy=false;await go(0);
    } catch(error) {if(error.name!=='AbortError'&&token===story.request)exposeError(error);}
    finally {if(token===story.request){story.busy=false;story.controller=null;controls();}}
  }
  function leave() {
    if(!story.active)return;
    story.request++;story.controller?.abort();story.controller=null;story.active=false;story.busy=false;
    delete document.body.dataset.experience;delete document.body.dataset.storyStep;
    $('story-panel').hidden=true;$('start-story').hidden=false;$('open-workbench').hidden=true;
    window.NacelleLab.loading(false);window.NacelleLab.restore();
    $('start-story').disabled=!window.NacelleLab.ready();
  }
  $('start-story').addEventListener('click',start);$('open-workbench').addEventListener('click',leave);
  $('story-prev').addEventListener('click',()=>go(story.index-1));$('story-next').addEventListener('click',()=>go((story.index+1)%steps.length));
  window.addEventListener('nacelle-ready',()=>{$('start-story').disabled=!window.NacelleLab.ready();});
  window.addEventListener('pagehide',leave);
})();
