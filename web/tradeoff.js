"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const CASES = {nominal:"正常供压",pressure_loss:"供压下降",asymmetric_blockage:"单通道封闭",combined_fault:"组合故障"};
  const state = {report:null, controller:null, generation:0, fresh:false};
  const fmt=(v,d=2)=>Number.isFinite(v)?v.toLocaleString("zh-CN",{minimumFractionDigits:d,maximumFractionDigits:d}):"—";
  const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
  const svg=(tag,attrs={})=>{const e=document.createElementNS("http://www.w3.org/2000/svg",tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));return e;};
  const text=(p,x,y,t,a={})=>{const e=svg("text",{x,y,"font-size":11,...a});e.textContent=t;p.append(e);};
  const record=(design,caseId,heat)=>design.cases[caseId].heat_load_records.find(x=>x.heat_load_W===heat);
  const selection=()=>state.report?.selection||{design_id:"n16_t860",case_id:"combined_fault",heat_load_W:60};
  function busy(value) {
    $("tradeoff-refresh").disabled=value;
    $("tradeoff-cancel").hidden=!value;
    $("tradeoff-export").disabled=value||!state.report||!state.fresh;
    $("tradeoff-design").disabled=value||!state.report;
    document.querySelectorAll("[data-tradeoff-case],[data-tradeoff-load],#tradeoff-thin").forEach(b=>b.disabled=value||!state.report);
    $("panel-tradeoff").setAttribute("aria-busy",String(value));
  }
  function restoreSelection() {
    const s=selection();$("tradeoff-design").value=s.design_id;
    document.querySelectorAll("[data-tradeoff-case]").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.tradeoffCase===s.case_id)));
    document.querySelectorAll("[data-tradeoff-load]").forEach(b=>b.setAttribute("aria-pressed",String(Number(b.dataset.tradeoffLoad)===s.heat_load_W)));
  }
  function validate(r,wanted) {
    if(r.schema!=="aerolab-pressure-fin-replay-v1"||r.execution!=="verified_research_replay"||r.live_computation!==false)throw new Error("回放契约不一致");
    if(Object.keys(wanted).some(k=>r.selection?.[k]!==wanted[k]))throw new Error("返回的设计、工况或热负荷与请求不一致");
    if(!["package_manifest_sha256","selection_sha256","source_model_sha256","presweep_plan_sha256"].every(k=>/^[a-f0-9]{64}$/.test(r.provenance?.[k]||""))||r.candidates?.length!==9||r.numerical?.gate_count!==19)throw new Error("已核对证据身份不完整");
    if(r.declared_60W_summary.combined_conditional_screen_pass_design_ids.length!==0||r.physical_validation_pass!==null||r.aircraft_transfer_authorized!==false)throw new Error("回放边界或故障结论不一致");
    if(r.selected.design_id!==wanted.design_id||!record(r.selected,wanted.case_id,wanted.heat_load_W))throw new Error("已保存结果缺失");
    if(!["selected_heat_rejection_W","baseline_heat_rejection_W","selected_heat_shortfall_W"].every(k=>Number.isFinite(r.combined_capacity_at_synthetic_limit?.[k])))throw new Error("合成上限的排热量记录缺失");
  }
  function metric(label,value,unit) {const d=node("div",undefined,"tradeoff-metric");d.append(node("span",label));const strong=node("strong",value);strong.append(node("small",unit));d.append(strong);return d;}
  function comparison(r) {
    const s=r.selection,c=r.selected.cases[s.case_id],current=record(r.selected,s.case_id,s.heat_load_W),baseline=record(r.baseline,s.case_id,s.heat_load_W);
    const rows=[["基线 · 16 片 × 0.86 mm",r.baseline,baseline],[`当前 · ${r.selected.geometry.N_fins} 片 × ${fmt(r.selected.geometry.fin_thickness_m*1000)} mm`,r.selected,current]];
    $("tradeoff-comparison").replaceChildren(...rows.map(([label,d,h],i)=>{
      const row=node("article",undefined,`tradeoff-compare-row ${i?"selected":""}`);row.append(node("h3",label));const metrics=node("div",undefined,"tradeoff-metric-pair");
      metrics.append(metric("仅鳍片铝质量",fmt(d.fin_only_aluminum_mass_g),"g"),metric(`${CASES[s.case_id]} · 所需均匀基座温度`,fmt(h.required_uniform_base_temperature_C),"°C"));row.append(metrics);
      row.append(node("p",`${h.thermal_criterion_pass?"温度条件内":"超过合成温度上限"} · ${h.fin_only_mass_criterion_pass?"质量预算内":"超过合成质量预算"}`,h.selected_scenario_condition_pass?"tradeoff-conditional":"tradeoff-fail"));return row;
    }));
    const dm=r.selected.fin_only_aluminum_mass_g-r.baseline.fin_only_aluminum_mass_g,dt=current.required_uniform_base_temperature_C-baseline.required_uniform_base_temperature_C;
    $("tradeoff-delta").textContent=`相对基线：鳍片 ${dm>0?"+":""}${fmt(dm)} g，当前工况所需基座温度 ${dt>0?"+":""}${fmt(dt)} °C。仅对已探索九种几何比较。`;
    const combined=record(r.selected,"combined_fault",60),qualified=r.selected.all_cases_within_declared_Re_scope,capacity=r.combined_capacity_at_synthetic_limit;
    $("tradeoff-requirement").replaceChildren(node("strong",`声明的 60 W 组合故障仍不通过 · ${fmt(combined.required_uniform_base_temperature_C)} °C > 85 °C`),node("p",`在固定物性部件模型中，85 °C 合成上限允许当前组合故障排热 ${fmt(capacity.selected_heat_rejection_W)} W，距声明 60 W 还差 ${fmt(capacity.selected_heat_shortfall_W)} W；基线为 ${fmt(capacity.baseline_heat_rejection_W)} W。`),node("p",`九种候选中，60 W 正常筛选通过 3 个，组合故障通过 0 个。${s.heat_load_W!==60?`当前 ${s.heat_load_W} W 是敏感性预设，不替换 60 W 声明要求。`:""} ${qualified?"当前候选属于声明的 Reynolds 范围。":"当前候选的正常工况超出声明的 Reynolds 范围，不能被推荐为合格设计。"}`));
    $("tradeoff-scope").textContent=`当前工况 Re 最大值 ${fmt(c.max_channel_Re_Dh,0)} / 声明上限 2300 · ${c.within_declared_Re_scope?"工况在范围内":"工况超出范围"}。${r.selected.pareto_within_Re_scope?"此点是范围内有限集合的唯一质量 / 组合温度 Pareto 点；相对优势不代表故障可行。":"保留被支配或超范围候选，避免只展示较好结果。"}`;
    $("tradeoff-fault-summary").replaceChildren(metric("共同供压差",fmt(c.supply_pressure_drop_Pa,0),"Pa"),metric("总质量流量",fmt(c.mass_flow_kg_s*1000,3),"g/s"),metric("被动压降耗散",fmt(c.hydraulic_dissipation_W*1000,2),"mW"));
  }
  function scatter(r) {
    const container=$("tradeoff-scatter"),focused=container.contains(document.activeElement)?document.activeElement.closest(".tradeoff-point")?.dataset.design:null,w=Math.max(280,container.clientWidth||500),h=270,left=43,right=18,top=26,bottom=43;
    const rows=r.candidates,xmin=15,xmax=70,ymin=35,ymax=Math.ceil(Math.max(...rows.map(x=>x.combined_Tb_at_60W_C),95)/50)*50;
    const x=v=>left+(v-xmin)/(xmax-xmin)*(w-left-right),y=v=>h-bottom-(v-ymin)/(ymax-ymin)*(h-top-bottom);
    const p=svg("svg",{viewBox:`0 0 ${w} ${h}`,role:"img","aria-label":"九种候选的鳍片质量与声明60W组合故障所需基座温度，保留两个正常工况超范围点"});
    [40,85].forEach((v,i)=>p.append(svg("line",i?{x1:left,x2:w-right,y1:y(v),y2:y(v),stroke:"#ae553d","stroke-dasharray":"4 4"}:{x1:x(v),x2:x(v),y1:top,y2:h-bottom,stroke:"#9c835f","stroke-dasharray":"4 4"})));
    [50,100,200,300,400,450].filter(v=>v>=ymin&&v<=ymax).forEach(v=>{p.append(svg("line",{x1:left,x2:w-right,y1:y(v),y2:y(v),stroke:"#e5e8e5"}));text(p,left-6,y(v)+4,String(v),{"text-anchor":"end",fill:"#52616a"});});
    [20,40,60].forEach(v=>text(p,x(v),h-bottom+19,String(v),{"text-anchor":"middle",fill:"#52616a"}));
    text(p,left,13,"组合故障 · 固定 60 W · °C",{fill:"#43545c"});text(p,w-right,h-4,"仅鳍片质量 / g",{"text-anchor":"end",fill:"#43545c"});
    text(p,w-right,y(85)-6,"85 °C 合成上限",{"text-anchor":"end",fill:"#98472f","font-size":10});text(p,x(40)+5,top+13,"40 g",{fill:"#826c4e","font-size":10});
    rows.forEach(d=>{const active=d.design_id===r.selection.design_id,scope=d.all_cases_within_declared_Re_scope,cx=x(d.fin_only_aluminum_mass_g),cy=y(d.combined_Tb_at_60W_C);
      const g=svg("g",{"class":"tradeoff-point","data-design":d.design_id,"data-scope":String(scope),role:"button",tabindex:0,"aria-label":`${d.N_fins}片 ${d.thickness_mm}毫米，${fmt(d.fin_only_aluminum_mass_g)}克，${fmt(d.combined_Tb_at_60W_C)}度，${scope?d.pareto_within_Re_scope?"范围内Pareto点":"被支配候选":"正常工况超范围"}${active?"，已选中":""}`});
      const title=svg("title");title.textContent=g.getAttribute("aria-label");g.append(title);
      g.append(svg("circle",{cx,cy,r:12,fill:"transparent"}));
      if(active)g.append(svg("circle",{cx,cy,r:9,fill:"none",stroke:"#182e36","stroke-width":2}));
      if(!scope){g.append(svg("path",{d:`M${cx-5} ${cy-5}l10 10m0 -10l-10 10`,stroke:"#a77c3a","stroke-width":2.5}));}
      else g.append(svg("circle",{cx,cy,r:5,fill:d.pareto_within_Re_scope?"#167568":"#7692a2",stroke:"#fff","stroke-width":1.5}));
      const choose=()=>{if(!state.controller)load({...selection(),design_id:d.design_id});};g.addEventListener("click",choose);g.addEventListener("keydown",e=>{if(["Enter"," "].includes(e.key)){e.preventDefault();choose();}});p.append(g);
    });container.replaceChildren(p);if(focused)container.querySelector(`[data-design="${focused}"]`)?.focus();
  }
  function channels(r) {
    const c=r.selected.cases[r.selection.case_id],ref=r.selected.cases[c.supply_pressure_drop_Pa===25?"nominal":"pressure_loss"],max=Math.max(...ref.branches.map(b=>b.mass_flow_kg_s));
    $("tradeoff-channels").replaceChildren(...c.branches.map(b=>{
      const row=node("div",undefined,"tradeoff-channel"+(b.blocked?" blocked":""));row.dataset.index=b.index;row.dataset.blocked=String(b.blocked);row.dataset.massFlowKgS=String(b.mass_flow_kg_s);
      const label=b.index===0?"左侧":b.index===r.selected.geometry.N_fins?"右侧":`通道 ${b.index}`;
      row.append(node("span",label,"channel-label"));const track=node("span",undefined,"channel-track"),ghost=node("span",undefined,"channel-reference"),fill=node("span",undefined,"channel-fill");ghost.style.width=`${ref.branches[b.index].mass_flow_kg_s/max*100}%`;fill.style.width=`${b.mass_flow_kg_s/max*100}%`;track.append(ghost,fill);row.append(track,node("span",b.blocked?"封闭 · 0":`${fmt(b.mass_flow_kg_s*1000,3)}`,"channel-value"));return row;
    }));
    $("tradeoff-channel-note").textContent=`${r.selected.geometry.N_fins} 片鳍片 / ${r.selected.geometry.N_channels} 条并联通道，条长表示绝对质量流量（g/s），细框为同压力未封闭时的值。${c.blocked_channel_indices.length?"左侧第 1 条内部通道封闭；流体保留横向导热，平流为零。其他通道绝对流量不变，份额升高。":"两侧旁通的底面绝热；内部通道底面与鳍片根部为均匀温度。"} 示意条图，不是温度云图或几何比例图。`;
  }
  function provenance(r) {
    const p=r.provenance,plug=Object.fromEntries(r.model_form_sensitivity.rows.filter(x=>x.sensitivity_parameter==="profile"&&x.sensitivity_value==="plug").map(x=>[x.case_id,x.G_change_from_primary_percent]));
    $("tradeoff-evidence").replaceChildren(node("p",`19 / 19 数值门槛通过 · 36 个设计工况 / 18 个基线敏感性工况已审计。网格差异是离散化指标，不是不确定性界限。`),node("p",`模型形式敏感性单列：相同均值流量改为塞状平流，基线正常导热能力变化 +${fmt(plug.nominal)}%，组合故障 +${fmt(plug.combined_fault)}%。这不是有效无滑移动量解，也不是置信区间；不能用来改写筛选通过状态。`),node("p",`包清单 SHA-256：${p.package_manifest_sha256}`),node("p",`科学代码 SHA-256：${p.source_model_sha256}`),node("p",`预声明计划 SHA-256：${p.presweep_plan_sha256}`),node("p",`选择与版本身份 SHA-256：${p.selection_sha256}`));
  }
  function render(r) {
    $("tradeoff-design").replaceChildren(...r.candidates.map(d=>{const e=node("option",`${d.N_fins} 片 × ${fmt(d.thickness_mm)} mm · ${fmt(d.fin_only_aluminum_mass_g)} g${!d.all_cases_within_declared_Re_scope?" · 正常超范围":d.pareto_within_Re_scope?" · 范围内 Pareto":""}`);e.value=d.design_id;return e;}));
    comparison(r);scatter(r);channels(r);provenance(r);
  }
  async function load(wanted={...selection()}) {
    if(state.controller)return;
    restoreSelection();const generation=++state.generation;state.controller=new AbortController();state.fresh=false;busy(true);$("tradeoff-error").hidden=true;
    $("tradeoff-state").textContent="正在核对已保存研究包；未执行新的物理求解…";
    try {
      const response=await fetch(`/api/physics/tradeoff?${new URLSearchParams(wanted)}`,{signal:state.controller.signal,cache:"no-store"});
      const r=await response.json();if(!response.ok)throw new Error(r.error||`HTTP ${response.status}`);if(generation!==state.generation)return;
      validate(r,wanted);render(r);state.report=r;state.fresh=true;restoreSelection();
      $("tradeoff-state").textContent=`已核对保存回放 · ${r.provenance.package_manifest_sha256.slice(0,12)} · 非实时 CFD`;
    } catch(error) {
      if(generation!==state.generation)return;state.fresh=false;if(state.report)render(state.report);restoreSelection();
      if(error.name==="AbortError")$("tradeoff-state").textContent=state.report?"已取消等待；保留上次回放，重新核对后才能导出":"已取消等待；尚无已核对回放";
      else {$("tradeoff-error").textContent=`回放未更新：${error.message}。${state.report?"仍显示上次选择；请重新核对后导出。":"尚无已核对数据。"}`;$("tradeoff-error").hidden=false;$("tradeoff-state").textContent="证据不可用或已过期；不能声称本次已核对";}
    } finally {if(generation===state.generation){state.controller=null;busy(false);}}
  }
  $("tradeoff-refresh").addEventListener("click",()=>load());
  $("tradeoff-cancel").addEventListener("click",()=>state.controller?.abort());
  $("tradeoff-design").addEventListener("change",e=>load({...selection(),design_id:e.target.value}));
  $("tradeoff-thin").addEventListener("click",()=>load({...selection(),design_id:"n16_t600"}));
  document.querySelectorAll("[data-tradeoff-case]").forEach(b=>b.addEventListener("click",()=>load({...selection(),case_id:b.dataset.tradeoffCase})));
  document.querySelectorAll("[data-tradeoff-load]").forEach(b=>b.addEventListener("click",()=>load({...selection(),heat_load_W:Number(b.dataset.tradeoffLoad)})));
  $("tradeoff-export").addEventListener("click",()=>{
    if(!state.report||!state.fresh||state.controller)return;const r=state.report,url=URL.createObjectURL(new Blob([JSON.stringify(r)],{type:"application/json"})),a=node("a");a.href=url;a.download=`pressure-fin-${r.selection.design_id}-${r.selection.case_id}-${r.selection.heat_load_W}W-${r.provenance.selection_sha256.slice(0,12)}.json`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  function panelChange() {if($("panel-tradeoff").hidden){state.controller?.abort();return;} if(!$("panel-tradeoff").hidden){if(!state.report&&!state.controller)load();else if(state.report)scatter(state.report);}}
  document.addEventListener("physics-panel-change",panelChange);
  window.addEventListener("pagehide",()=>{state.controller?.abort();state.generation++;state.controller=null;state.fresh=false;busy(false);restoreSelection();if(state.report)$("tradeoff-state").textContent="恢复上次保存回放；重新核对后才能导出";});
  window.addEventListener("pageshow",e=>{if(e.persisted)panelChange();});
  let frame;window.addEventListener("resize",()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{if(state.report&&!$("panel-tradeoff").hidden)scatter(state.report);});});
  busy(false);panelChange();
})();
