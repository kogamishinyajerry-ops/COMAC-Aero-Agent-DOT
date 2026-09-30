"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const svgNS = "http://www.w3.org/2000/svg";
  const tabs = ["flow", "channel", "coupling", "tradeoff"];
  const names = {main_inlet:"主进气口",motor_internal:"转子–定子间隙",motor_slots:"定子冷却槽",motor_bypass_inlet:"电机旁通入口"};
  const state = {report:null, requestedCase:"asymmetric", controller:null, generation:0};
  const fmt = (value, digits=2) => Number.isFinite(value) ? value.toLocaleString("zh-CN", {minimumFractionDigits:digits,maximumFractionDigits:digits}) : "—";
  const signed = (value, digits=2) => Number.isFinite(value) ? (value > 0 ? "+" : "") + fmt(value,digits) : "—";
  const node = (tag, text, className) => {const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(className)n.className=className;return n;};
  const svg = (tag, attrs={}) => {const n=document.createElementNS(svgNS,tag);Object.entries(attrs).forEach(([key,value])=>n.setAttribute(key,String(value)));return n;};
  const text = (parent,x,y,value,attrs={}) => {const n=svg("text",{x,y,"font-family":"system-ui,sans-serif",...attrs});n.textContent=value;parent.append(n);return n;};
  function replace(id, ...children) {$(id).replaceChildren(...children);}
  function metric(label,value,unit="") {const n=node("div",undefined,"metric");n.append(node("span",label));const v=node("strong",value);v.append(node("small",unit));n.append(v);return n;}
  function paragraph(value) {return node("p",value);}
  function bulletList(values) {const list=node("ul");values.forEach(v=>list.append(node("li",v)));return list;}
  function link(label,url) {const n=node("a",label);n.href=url;n.target="_blank";n.rel="noopener noreferrer";return n;}
  function bar(value,max,color) {const track=node("div",undefined,"bar-track"),fill=node("div",undefined,`bar ${color}`);fill.style.width=`${Math.max(0,Math.min(100,value/max*100))}%`;track.append(fill);return track;}

  function chooseTab(name, writeHistory=true) {
    name=tabs.includes(name)?name:"flow";
    tabs.forEach(item=>{const active=item===name;$("tab-"+item).setAttribute("aria-selected",String(active));$("tab-"+item).tabIndex=active?0:-1;$("panel-"+item).hidden=!active;});
    $("live-toolbar").hidden=name==="tradeoff";
    if(name!=="tradeoff"&&!state.report&&!state.controller)calculate();
    $("error").hidden=name==="tradeoff" || !$("error").textContent;
    document.dispatchEvent(new CustomEvent("physics-panel-change",{detail:{tab:name}}));
    // Rebuild SVG coordinates after the formerly hidden container is laid out.
    // Fonts stay in CSS pixels instead of shrinking with a fixed desktop viewBox.
    if(state.report && name==="channel")renderHistorical(state.report);
    if(state.report && name==="coupling")renderDuct(state.report);
    if(writeHistory && location.hash!=="#"+name) history.pushState({tab:name},"","#"+name);
  }
  document.querySelectorAll("[data-tab]").forEach(button=>{
    button.addEventListener("click",()=>chooseTab(button.dataset.tab));
    button.addEventListener("keydown",event=>{
      const i=tabs.indexOf(button.dataset.tab);let next;
      if(event.key==="ArrowRight")next=tabs[(i+1)%tabs.length];
      if(event.key==="ArrowLeft")next=tabs[(i+tabs.length-1)%tabs.length];
      if(event.key==="Home")next=tabs[0];if(event.key==="End")next=tabs[tabs.length-1];
      if(next){event.preventDefault();chooseTab(next);$("tab-"+next).focus();}
    });
  });
  window.addEventListener("popstate",()=>chooseTab(location.hash.slice(1),false));
  window.addEventListener("hashchange",()=>chooseTab(location.hash.slice(1),false));
  chooseTab(location.hash.slice(1),false);

  function renderSource(report) {
    const audit=report.source_audit, areas=audit.flow_area_constraints;
    const keys=Object.keys(names),max=Math.max(...keys.flatMap(k=>[areas[k].current_rom_area_m2,areas[k].inferred_flux_equivalent_area_m2]));
    const rows=keys.map(key=>{
      const d=areas[key],row=node("div",undefined,"area-row"),label=node("div",undefined,"area-label");
      label.append(node("span",names[key]),node("small",`来源站位 ${d.station}`));row.append(label);
      const pair=node("div",undefined,"bar-pair");
      [[d.current_rom_area_m2,"blue"],[d.inferred_flux_equivalent_area_m2,"ochre"]].forEach(([value,color])=>{
        const line=node("div",undefined,"bar-line");line.append(bar(value,max,color),node("span",fmt(value*1e6,0),"bar-value"));pair.append(line);
      });row.append(pair);return row;
    });replace("area-chart",...rows);
    const cases=audit.conditional_resistance_checks.main_to_slots.cases;
    const labels={cruise_climb:"巡航爬升",dash:"高速巡航"},pressure=node("div",undefined,"pressure-row");
    Object.entries(labels).forEach(([key,label])=>{
      const d=cases[key],box=node("div",undefined,"pressure-value");
      box.append(node("span",label),node("strong",`${signed(d.relative_error_percent)}%`),node("small",`舍入范围 ${signed(d.error_printed_rounding_percent[0],1)}% 至 ${signed(d.error_printed_rounding_percent[1],1)}%`));pressure.append(box);
    });replace("pressure-check",paragraph("主进气口 1_c → 电机后混合区 4；用冷却槽 2a_s 流量做对照"),paragraph("流量相对偏差 =（预测 − 来源）/ 来源。负号表示低估。"),pressure);
    replace("source-details",paragraph("仅以初始爬升做推定；另两组数据是同一 CFD 构型的回顾性对照，不是盲测或试验验证。"),
      link("NASA 2023 · 表 7–9 与第 9 页平均定义",audit.source_url),
      bulletList(keys.map(key=>`${names[key]}：三组等效面积的全跨度为初始推定的 ${fmt(areas[key].three_case_span_percent_of_inferred,3)}%。重复性提示几何差异，但不能约束未知平均误差。`)),
      paragraph(`数据指纹 ${audit.source_data_sha256}`),paragraph(`当前几何指纹 ${audit.geometry_fingerprint}`));
  }

  function renderHistorical(report) {
    const h=report.historical_motor,compare=h.matched_condition_comparison;
    const matched=compare.rows.find(r=>r.velocity_m_s===24) || compare.rows[0];
    const width=$("channel-sketch").clientWidth||540,half=(width-26)/2,right=half+26;
    const picture=svg("svg",{viewBox:`0 0 ${width} 160`,role:"img","aria-label":"宽绕组间隙代理与历史窄散热通道示意，非同比例"});
    text(picture,5,17,"当前宽通道代理",{"font-size":12,fill:"#467c9d"});
    text(picture,right,17,"历史散热器单元",{"font-size":12,fill:"#9b662b"});
    for(let i=0;i<4;i++)picture.append(svg("rect",{x:6+i*(half-6)/4,y:36,width:Math.max(8,half*.09),height:60,fill:"#c0d3dd",rx:2}));
    for(let i=0;i<12;i++)picture.append(svg("rect",{x:right+i*(half-5)/12,y:36,width:Math.max(3,half*.023),height:60,fill:"#dec497",rx:1}));
    text(picture,5,116,`Dh ${fmt(compare.current_rom_native_hydraulic_diameter_m*1000,3)} mm`,{"font-size":11,fill:"#697a82"});
    text(picture,right,116,"2 × 17 mm",{"font-size":11,fill:"#697a82"});
    text(picture,right,132,`Dh ${fmt(h.geometry.hydraulic_diameter_m*1000,3)} mm`,{"font-size":11,fill:"#697a82"});
    text(picture,width/2,154,"截面示意 · 非同比例 / 非实际槽数",{"font-size":10,fill:"#697a82","text-anchor":"middle"});
    replace("channel-sketch",picture);
    replace("channel-comparison",
      metric("换热能力 UA 比值",fmt(matched.narrow_to_broad_ua_ratio,2),"×"),
      metric("摩擦压降比值",fmt(matched.narrow_to_broad_friction_drop_ratio,2),"×"),
      metric("宽通道 UA",fmt(matched.current_broad_slot.ua_at_equivalent_flow_area_w_k,1),"W/K"),
      metric("窄通道 UA",fmt(matched.historical_narrow.ua_at_equivalent_flow_area_w_k,1),"W/K"));
    const m=h.materials,values=[["由组分质量守恒计算",m.constituent_volumetric_capacity_j_m3_k,"blue"],["论文打印密度 × 打印比热",m.printed_bulk.implied_volumetric_capacity_j_m3_k,"ochre"]];
    replace("material-chart",...values.map(([label,value,color])=>{const row=node("div",undefined,"material-row"),head=node("div");head.append(node("span",label),node("span",`${fmt(value/1e6,3)} MJ/(m³·K)`));row.append(head,bar(value,values[1][1],color));return row;}));
    const summary=node("div",undefined,"material-summary");summary.append(node("strong",`+${fmt(m.printed_capacity_excess_percent_of_constituent_value,1)}%`),paragraph("以组分守恒值为基准，打印表格组合出的体积热容更高。铜的体积分数与质量分数不能混用。"));replace("material-summary",summary);
    replace("historical-details",paragraph(`匹配条件：${fmt(matched.velocity_m_s,0)} m/s，长度 ${fmt(compare.boundary.length_m*1000,0)} mm，总等效流通面积 ${fmt(compare.flux_equivalent_area_m2*1e6,1)} mm²。两侧壁面等温，比入口高 1 K；两组均不施加鳍片效率。`),
      paragraph(`窄通道摩擦压降 ${fmt(matched.historical_narrow.friction_pressure_drop_pa,1)} Pa；宽通道 ${fmt(matched.current_broad_slot.friction_pressure_drop_pa,1)} Pa。此比较固定速度，未重新求解整机气流，不能直接当作安装后的改善。`),
      paragraph(`等面积单元数 ${fmt(compare.equivalent_historical_channel_count,3)} 是分数型等效量，绝不是实际 CAD 槽数。非圆通道中的关联式适用性仍未验证。`),
      link("历史电机热分析 · NTRS 20190032520",h.sources.historical_nasa),
      paragraph(`材料守恒比热 ${fmt(m.mass_consistent_specific_heat_j_kg_k,3)} J/(kg·K)，打印值 ${fmt(m.printed_bulk.specific_heat_j_kg_k,2)} J/(kg·K)。未据此推断 NASA 实际模型的输入。`),
      paragraph(`历史单元代码指纹 ${h.source_code_sha256}`));
  }

  function heatColor(t,min,max) {
    const stops=[[231,244,243],[125,182,178],[230,181,111],[191,105,69]],v=Math.max(0,Math.min(2.999999,(t-min)/Math.max(1e-9,max-min)*3)),i=Math.floor(v),f=v-i;
    return `rgb(${stops[i].map((c,j)=>Math.round(c+(stops[i+1][j]-c)*f)).join(",")})`;
  }
  function renderHeatMap(duct) {
    const samples=duct.thermal.axial_samples;
    if(!samples.length){replace("heat-map",node("div","零流量下没有强迫对流稳态。\n不生成虚假的温度场。","heat-empty"));replace("heat-scale");return;}
    const ordered=[...samples].sort((a,b)=>a.x_physical_m-b.x_physical_m),eta=duct.thermal.sample_eta;
    const all=ordered.flatMap(s=>s.fluid_c).concat(Object.values(duct.thermal.outlet_wall_c));
    const min=Math.min(...all),max=Math.max(...all),L=duct.provenance.case.length_m;
    const width=$("heat-map").clientWidth||620,height=$("heat-map").clientHeight||244;
    const p=svg("svg",{viewBox:`0 0 ${width} ${height}`});
    const x0=45,y0=34,w=width-65,h=height-82;
    ordered.forEach((s,i)=>{
      const left=i?(.5*(s.x_physical_m+ordered[i-1].x_physical_m)):0;
      const right=i+1<ordered.length?.5*(s.x_physical_m+ordered[i+1].x_physical_m):L;
      eta.forEach((y,j)=>{
        const bottom=j?.5*(y+eta[j-1]):-1,top=j+1<eta.length?.5*(y+eta[j+1]):1;
        p.append(svg("rect",{x:x0+w*left/L,y:y0+h*(1-top)/2,width:w*(right-left)/L+.25,height:h*(top-bottom)/2+.25,fill:heatColor(s.fluid_c[j],min,max)}));
      });
    });
    p.append(svg("rect",{x:x0,y:y0,width:w,height:h,fill:"none",stroke:"#cad8d9","stroke-width":1}));
    const reverse=duct.hydraulics.flow_direction<0;
    text(p,x0,20,`上壁 ${fmt(duct.thermal.wall_flux_w_m2.right,0)} W/m²`,{"font-size":11,fill:"#697a82"});
    text(p,x0+w,20,reverse?"← 气流方向":"气流方向 →",{"font-size":11,fill:"#087d78","text-anchor":"end"});
    const halfGap=fmt(duct.provenance.case.gap_m*500,0);
    text(p,x0-7,y0+5,`+${halfGap}mm`,{"font-size":10,fill:"#697a82","text-anchor":"end"});
    text(p,x0-7,y0+h,`−${halfGap}mm`,{"font-size":10,fill:"#697a82","text-anchor":"end"});
    text(p,x0,y0+h+19,"0",{"font-size":10,fill:"#697a82"});
    text(p,x0+w,y0+h+19,`${fmt(L*1000,0)} mm`,{"font-size":10,fill:"#697a82","text-anchor":"end"});
    text(p,x0+w/2,height-10,`下壁 ${fmt(duct.thermal.wall_flux_w_m2.left,0)} W/m² · 实际位置 x`,{"font-size":10,fill:"#697a82","text-anchor":"middle"});
    replace("heat-map",p);
    const gradient=node("div",undefined,"heat-scale-gradient");replace("heat-scale",node("span",`${fmt(min,1)} °C`),gradient,node("span",`${fmt(max,1)} °C`));
  }
  function renderDuct(report) {
    const d=report.duct,t=d.thermal;
    $("grid-label").textContent=`${d.provenance.grid.transverse_full_gap_cells} × ${d.provenance.grid.axial_cells} 单元`;
    renderHeatMap(d);
    const values=[["下壁",t.outlet_wall_c.left,"#467c9d"],["流量加权平均空气",t.outlet_bulk_c,"#087d78"],["上壁",t.outlet_wall_c.right,"#c58a3b"]];
    replace("wall-comparison",...values.map(([label,value,color])=>{const row=node("div",undefined,"wall-row"),name=node("span"),dot=node("i",undefined,"wall-dot");dot.style.background=color;name.append(dot,document.createTextNode(label));row.append(name,node("strong",fmt(value,2)));return row;}));
    let answer;
    if(d.status!=="solved")answer="有热负荷却没有气流，当前对流模型不给出稳态温度。自然对流等机制不在这个子问题内。";
    else if(t.wall_flux_w_m2.left>0 && t.outlet_wall_c.left<t.outlet_bulk_c)answer=`下壁仍向流体加热，却比平均空气低 ${fmt(t.outlet_bulk_c-t.outlet_wall_c.left,2)} °C。上壁把另一侧流体加热得更多；一个独立的正换热系数不能描述这种耦合。`;
    else if(t.wall_flux_w_m2.left===t.wall_flux_w_m2.right)answer="两面均匀加热，温度分布恢复对称。充分发展极限可与解析 Nu = 140/17 单独对照。";
    else if(t.wall_flux_w_m2.left<0)answer="一侧吸热、一侧放热，总热流为零。平均空气温度可以不变，横向温度梯度仍真实存在。";
    else answer="绝热壁不直接给空气加热，但仍受另一壁的热量影响。壁温不能由它自身的热流单独决定。";
    $("coupling-answer").textContent=answer;
    replace("balance-metrics",metric("能量残差",Number.isFinite(d.diagnostics.energy_residual_w)?d.diagnostics.energy_residual_w.toExponential(1):"—","W"),metric("Reynolds 数",fmt(d.hydraulics.reynolds_dh,0)));
    const v=report.verification,finest=v.fully_developed_grid_convergence.at(-1);
    const order=v.transverse_nusselt_observed_orders.at(-1),axial=v.axial_observed_orders_from_successive_differences.at(-1);
    const cards=[
      ["横向网格收敛阶",fmt(order,3),"目标约 2 阶；独立加密检查"],
      ["轴向步进收敛阶",fmt(axial,3),"目标约 1 阶；不掩盖离散误差"],
      ["充分发展 Nu",fmt(finest.nusselt_dh,5),`解析值 ${fmt(v.analytical_equal_flux_nusselt,5)}`],
      ["方程验证关卡",`${Object.values(v.gates).filter(Boolean).length} / ${Object.keys(v.gates).length}`,"含独立入口段参考、摩擦与热平衡"],
    ];
    replace("verification-grid",...cards.map(([label,value,note])=>{const n=node("div",undefined,"verification-item");n.append(node("p",label),node("strong",value),node("small",note));return n;}));
    replace("duct-details",paragraph(`本次求解：间隙 ${fmt(d.provenance.case.gap_m*1000,1)} mm，长度 ${fmt(d.provenance.case.length_m*1000,0)} mm，入口 ${fmt(d.provenance.case.inlet_c,1)} °C，平均速度 ${fmt(d.provenance.case.mean_velocity_m_s,1)} m/s。`),
      paragraph("范围：层流、充分发展的速度场、固定物性、两壁指定热流。省略轴向导热、浮力、辐射、旋转和湍流；不用于电机工况预测。"),
      paragraph("图中下壁对应求解器横坐标 η = −1，上壁对应 η = +1；流向坐标 x 独立，反向气流不交换两壁。"),
      paragraph("温度场为本次计算；网格收敛和独立高精度入口段比较为已复现的保存记录，已检查与当前模型及参考程序指纹一致。"),
      paragraph(`本次输入 ${d.provenance.input_sha256}`),paragraph(`数值模型 ${d.provenance.source_sha256}`),paragraph(`验证记录 ${v.artifact_sha256}`),
      ...v.sources.map(s=>link(s.title,s.url)));
  }

  function busy(active) {
    $("refresh").disabled=active;$("cancel").hidden=!active;$("export").disabled=active||!state.report;
    document.querySelectorAll("[data-case]").forEach(b=>b.disabled=active);
  }
  function validateReport(report,chosen) {
    if(report.schema!=="aerolab-physics-lab-v1"||report.execution!=="computed")throw new Error("计算响应格式不匹配");
    if(report.case!==chosen)throw new Error("请求与响应工况不一致");
    if(!report.verification.numerical_source_matches||report.verification.model_source_sha256!==report.duct.provenance.source_sha256)throw new Error("数值模型与验证记录指纹不一致");
    if(Object.values(report.claims).some(Boolean)||report.historical_motor.experimental_validation)throw new Error("响应的物理验证声明与此页面范围不一致");
    if(!/^[a-f0-9]{64}$/.test(report.duct.provenance.input_sha256))throw new Error("计算输入指纹无效");
    const last=report.verification.fully_developed_grid_convergence.at(-1);
    if(!Number.isFinite(last.nusselt_dh))throw new Error("数值验证记录缺少结果");
    if(chosen!=="zero_flow"&&(report.duct.status!=="solved"||!report.duct.diagnostics.converged))throw new Error("本次求解未通过数值守恒检查");
  }
  async function calculate(chosen=state.requestedCase) {
    const generation=++state.generation;state.controller?.abort();state.controller=new AbortController();state.requestedCase=chosen;
    busy(true);$("error").hidden=true;$("error").textContent="";$("run-state").classList.remove("calculation-stale");$("run-state").textContent=state.report?"正在重新求解；下方保留上次结果…":"正在计算并检查证据版本…";
    try {
      const response=await fetch("/api/physics/evaluate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({case:chosen}),signal:state.controller.signal});
      const report=await response.json();if(!response.ok)throw new Error(report.error||`HTTP ${response.status}`);
      if(generation!==state.generation)return;
      validateReport(report,chosen);
      renderSource(report);renderHistorical(report);renderDuct(report);state.report=report;
      document.querySelectorAll("[data-case]").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.case===report.case)));
      $("run-state").textContent=`本次计算 · 输入 ${report.duct.provenance.input_sha256.slice(0,12)} · 数值验证记录版本已核对`;
    } catch(error) {
      if(generation!==state.generation)return;
      if(error.name==="AbortError"){$("run-state").textContent=state.report?"已取消等待，保留上次计算结果":"已取消等待，可以重新计算";}
      else{$("error").textContent=`本次计算未完成：${error.message}。${state.report?"下方仍为上次结果。":"请稍后重新计算。"}`;$("error").hidden=!$("panel-tradeoff").hidden;$("run-state").textContent=state.report?"显示上次计算，当前请求未完成":"尚无有效计算结果";}
      $("run-state").classList.add("calculation-stale");
    } finally {if(generation===state.generation){busy(false);state.controller=null;}}
  }
  $("refresh").addEventListener("click",()=>calculate());
  $("cancel").addEventListener("click",()=>state.controller?.abort());
  document.querySelectorAll("[data-case]").forEach(button=>button.addEventListener("click",()=>calculate(button.dataset.case)));
  $("export").addEventListener("click",()=>{
    if(!state.report)return;const blob=new Blob([JSON.stringify(state.report)],{type:"application/json"}),url=URL.createObjectURL(blob),a=node("a");a.href=url;a.download=`physics-evidence-${state.report.case}-${state.report.duct.provenance.input_sha256.slice(0,12)}.json`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  window.addEventListener("pagehide",()=>{
    state.controller?.abort();state.generation++;state.controller=null;busy(false);
    if(state.report){$("run-state").textContent="恢复上次计算结果；可重新计算";$("run-state").classList.add("calculation-stale");}
  });
  window.addEventListener("pageshow",event=>{if(event.persisted&&$("panel-tradeoff").hidden&&!state.report&&!state.controller)calculate();});
  let resizeFrame;
  window.addEventListener("resize",()=>{
    cancelAnimationFrame(resizeFrame);
    resizeFrame=requestAnimationFrame(()=>{
      if(!state.report)return;
      if(!$("panel-channel").hidden)renderHistorical(state.report);
      if(!$("panel-coupling").hidden)renderDuct(state.report);
    });
  });
})();
