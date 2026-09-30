"use strict";
(() => {
  const $=id=>document.getElementById(id), NS="http://www.w3.org/2000/svg";
  const state={data:null,valid:false,controller:null,generation:0,allowance:"none"};
  const f=(v,n=2)=>Number.isFinite(v)?v.toLocaleString("zh-CN",{minimumFractionDigits:n,maximumFractionDigits:n}):"未给出";
  const sign=(v,n=2)=>(v>0?"+":"")+f(v,n);
  const scopes={robustly_in_declared_laminar_scope:["稳健范围内","robust"],nominally_laminar_boundary_uncertain:["边界不确定","boundary"],nominally_outside_laminar_scope:["名义超域","outside"]};
  function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
  function s(tag,attrs={}){const n=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,String(v)));return n;}
  function label(root,x,y,text,attrs={}){const n=s("text",{x,y,"font-family":"system-ui,sans-serif","font-size":10,fill:"#697a82",...attrs});n.textContent=text;root.append(n);return n;}
  function metric(title,value,unit=""){const n=el("div",undefined,"metric");n.append(el("span",title));const v=el("strong",value);v.append(el("small",unit));n.append(v);return n;}

  function plot(){
    if(!state.data||$("benchmark-fin").hidden)return;
    const rows=state.data.rows,box=$("fin-comparison-chart"),width=box.clientWidth||600,height=box.clientHeight||350;
    const left=47,top=27,w=width-left-15,h=height-top-46,x=v=>left+(v-3)/19*w,y=v=>top+h-(v-.2)/.8*h;
    const svg=s("svg",{viewBox:`0 0 ${width} ${height}`,role:"img","aria-label":"全部12个图点的热阻对照；灰色区域超过声明的名义层流范围"});
    const boundary=state.data.scope_boundary_speed_m_s;
    svg.append(s("rect",{x:x(boundary),y:top,width:x(22)-x(boundary),height:h,fill:"#f0f2f2"}));
    label(svg,(x(boundary)+x(22))/2,top+13,"名义超出层流范围",{"text-anchor":"middle","font-size":9.8});
    for(const v of [4,8,12,16,20]){svg.append(s("line",{x1:x(v),x2:x(v),y1:top,y2:top+h,stroke:"#e5eaea"}));label(svg,x(v),top+h+17,String(v),{"text-anchor":"middle"});}
    for(const v of [.2,.4,.6,.8,1]){svg.append(s("line",{x1:left,x2:left+w,y1:y(v),y2:y(v),stroke:"#e5eaea"}));label(svg,left-8,y(v)+3,f(v,1),{"text-anchor":"end"});}
    for(const [key,color,dash] of [["fd_Rth_K_W","#467c9d",""],["plug_Rth_K_W","#c58a3b","5 3"]]){
      svg.append(s("polyline",{points:rows.map(r=>`${x(r.V_m_s)},${y(r[key])}`).join(" "),fill:"none",stroke:color,"stroke-width":1.6,"stroke-dasharray":dash}));
      rows.forEach(r=>svg.append(s("circle",{cx:x(r.V_m_s),cy:y(r[key]),r:2.6,fill:color,"data-model":key})));
    }
    rows.forEach(r=>{
      let dy=0,dx=0;
      if(state.allowance==="graphical"){dy=r.graphical_Rth_allowance_K_W;dx=r.graphical_V_allowance_m_s;}
      if(state.allowance==="author")dy=r.author_Rth_absolute_uncertainty_K_W;
      if(dy){svg.append(s("line",{x1:x(r.V_m_s),x2:x(r.V_m_s),y1:y(r.observed_Rth_K_W-dy),y2:y(r.observed_Rth_K_W+dy),stroke:"#83949b","stroke-width":1,"data-allowance":state.allowance}));for(const v of [-dy,dy])svg.append(s("line",{x1:x(r.V_m_s)-3,x2:x(r.V_m_s)+3,y1:y(r.observed_Rth_K_W+v),y2:y(r.observed_Rth_K_W+v),stroke:"#83949b"}));}
      if(dx)svg.append(s("line",{x1:x(r.V_m_s-dx),x2:x(r.V_m_s+dx),y1:y(r.observed_Rth_K_W),y2:y(r.observed_Rth_K_W),stroke:"#83949b"}));
      const color=r.scope=== "robustly_in_declared_laminar_scope"?"#087d78":r.scope==="nominally_laminar_boundary_uncertain"?"#8d591d":"#697a82";
      const point=s("rect",{x:x(r.V_m_s)-3.5,y:y(r.observed_Rth_K_W)-3.5,width:7,height:7,fill:"#182e3b",stroke:color,"stroke-width":1.5,"data-marker-index":r.marker_index,tabindex:0,"aria-label":`图点 ${r.marker_index+1}，速度 ${f(r.V_m_s,3)} 米每秒，实测热阻 ${f(r.observed_Rth_K_W,4)}，主模型 ${f(r.fd_Rth_K_W,4)}，${scopes[r.scope][0]}`});
      const title=s("title");title.textContent=point.getAttribute("aria-label");point.append(title);svg.append(point);
    });
    label(svg,left+w/2,height-6,"通道名义速度 / m/s",{"text-anchor":"middle","font-size":11});
    label(svg,12,top+h/2,"损失修正后的热阻 / K/W",{"text-anchor":"middle","font-size":11,transform:`rotate(-90 12 ${top+h/2})`});
    box.replaceChildren(svg);
    $("fin-allowance-explanation").textContent=state.allowance==="graphical"?"当前线段仅表示图中符号尺寸产生的读取范围，约 ±0.257 m/s、±0.0134 K/W；不是测量置信区间，也未与作者不确定度合并。":state.allowance==="author"?"当前线段仅表示作者给出的热阻不确定度 1.2%；覆盖概率及逐次分配方式未恢复。图形读取分量另列，未合并为总误差棒。":"未绘制范围。作者不确定度和图形读取范围保持分开，均未作为“验证通过”的自动阈值。";
  }
  function geometry(){
    if(!state.data||$("benchmark-fin").hidden)return;
    const box=$("fin-channel-diagram"),width=box.clientWidth||440,height=box.clientHeight||190;
    const scale=(width-34)/45.2,x0=17,baseY=height-43,top=baseY-11.3*scale,side=1.85*scale,thick=.86*scale,gap=(41.5-16*.86)/15*scale;
    const svg=s("svg",{viewBox:`0 0 ${width} ${height}`,role:"img","aria-label":"16片翅片的真实边界结构示意；侧通道无加热底面"});
    svg.append(s("rect",{x:x0,y:top,width:45.2*scale,height:11.3*scale,fill:"#e6f0f4",stroke:"#9babb2","stroke-width":1}));
    svg.append(s("rect",{x:x0+side,y:baseY,width:41.5*scale,height:6,fill:"#c58a3b"}));
    for(let i=0;i<16;i++)svg.append(s("rect",{x:x0+side+i*(thick+gap),y:top,width:thick,height:baseY-top,fill:"#c58a3b"}));
    label(svg,width/2,top-13,"16 片翅片 / 15 条内部通道",{"text-anchor":"middle","font-size":11});
    label(svg,x0,baseY+23,"侧通道",{"text-anchor":"start"});label(svg,width-x0,baseY+23,"侧通道",{"text-anchor":"end"});
    label(svg,width/2,baseY+23,"恒温底面 · 41.5 mm",{"text-anchor":"middle"});
    box.replaceChildren(svg);
  }
  function render(data){
    $("fin-point-count").textContent="12";$("fin-scope-count").textContent="3 / 12";
    const robust=data.rows.filter(r=>r.scope==="robustly_in_declared_laminar_scope"),errs=robust.map(r=>r.relative_Rth_discrepancy*100);
    $("fin-discrepancy-range").textContent=`${sign(Math.min(...errs),1)}–${sign(Math.max(...errs),1)}`;
    const gates=Object.values(data.numerical.gates);$("fin-gates-count").textContent=`${gates.filter(Boolean).length} / ${gates.length}`;
    $("fin-topology-metrics").replaceChildren(metric("侧通道质量流量占比",f(2/17*100,2),"%"),metric("侧通道热量占比",`${f(data.side_channel_heat_fraction_range[0]*100,2)}–${f(data.side_channel_heat_fraction_range[1]*100,2)}`,"%"),metric("错误复制中心通道的总换热热导高估",`${f(data.naive_channel_G_bias_range[0]*100,2)}–${f(data.naive_channel_G_bias_range[1]*100,2)}`,"%"));
    $("fin-source-rows").replaceChildren(...data.rows.map(r=>{const row=el("tr");[String(r.marker_index+1),f(r.V_m_s,3),f(r.Re_nominal,0),f(r.observed_Rth_K_W,4),f(r.fd_Rth_K_W,4),sign(r.relative_Rth_discrepancy*100,3),f(r.plug_Rth_K_W,4)].forEach(v=>row.append(el("td",v)));const td=el("td"),scope=scopes[r.scope];td.append(el("span",scope[0],`fin-scope ${scope[1]}`));row.append(td);return row;}));
    const source=el("a",data.source.title);source.href=data.source.url;source.target="_blank";source.rel="noopener noreferrer";
    $("fin-provenance").replaceChildren(source,el("p","来源 Figure 8 的 12 个黑色方形图点经矢量坐标读取；没有使用图中拟合曲线。原文称 13 次试验，现有图点不足以恢复缺失记录。"),el("p","数学验收在实验残差评估前完成。初始网格未满足原定 Poisson 精度阈值，其失败记录保留；只加密网格，没有放宽阈值。独立审查包括谱传播、全阵列与镜像对称性、界面/翅片守恒和导热极限。"),el("p","充分发展和均匀速度是两种预先声明的模型形式，不是上下置信界。材料取值与空气物性来自声明场景，未恢复成逐次实测条件。不存在空气适航性或飞机全功率温度验证结论。"),el("p","离线重算使用 research/plate_fin/reproduce.sh 和该目录列出的可选研究依赖。默认生成独立结果目录，不覆盖应用所用的接受记录；原始 PDF 不随包分发。"),el("p",`原始数值冻结 ${data.provenance.original_numerical_freeze_sha256}`),el("p",`研究包清单 ${data.provenance.package_manifest_sha256}`),el("p",`本次核对 ${data.provenance.verified_file_count} 个文件；读取器源码 ${data.provenance.reader_source_sha256}`));
  }
  function busy(value){$("verify-fin").disabled=value;$("cancel-fin").hidden=!value;$("export-fin").disabled=value||!state.valid;$("fin-allowance").disabled=value||!state.data;}
  function validate(data){
    if(data.schema!=="aerolab-fin-experiment-replay-v1"||data.execution!=="verified_research_replay"||data.live_computation!==false)throw new Error("板翅研究回放类型不匹配");
    if(data.physical_validation_pass!==null||data.calibration_records!==0)throw new Error("板翅拟合或验证声明不符合研究范围");
    if(data.rows.length!==12||new Set(data.rows.map(r=>r.marker_index)).size!==12||!data.numerical.all_passed||Object.values(data.numerical.gates).some(v=>v!==true))throw new Error("板翅研究记录不完整");
    for(const [name,count] of [["robustly_in_declared_laminar_scope",3],["nominally_laminar_boundary_uncertain",1],["nominally_outside_laminar_scope",8]])if(data.rows.filter(r=>r.scope===name).length!==count)throw new Error("适用性分组不符合研究记录");
  }
  async function verify(){
    const generation=++state.generation;state.controller?.abort();state.controller=new AbortController();state.valid=false;busy(true);$("fin-error").hidden=true;$("fin-status").classList.remove("calculation-stale");$("fin-status").textContent="正在核对板翅研究记录与原始冻结…";
    try{const response=await fetch("/api/physics/fin-experiment",{signal:state.controller.signal}),data=await response.json();if(!response.ok)throw new Error(data.error||`HTTP ${response.status}`);if(generation!==state.generation)return;validate(data);render(data);state.data=data;state.valid=true;plot();geometry();$("fin-status").textContent=`已核对的板翅研究回放 · ${data.provenance.package_manifest_sha256.slice(0,12)} · 此页没有重新求解`;}
    catch(error){if(generation!==state.generation)return;$("fin-status").classList.add("calculation-stale");if(error.name==="AbortError")$("fin-status").textContent=state.data?"已取消核对，显示上次板翅回放":"已取消核对，尚无板翅研究记录";else{$("fin-error").textContent=`板翅研究记录核对失败：${error.message}。${state.data?"显示上次回放，导出已停用。":"请检查研究包后重试。"}`;$("fin-error").hidden=false;$("fin-status").textContent=state.data?"当前记录未通过核对；显示上次板翅回放":"尚无已核对的板翅研究回放";}}
    finally{if(generation===state.generation){state.controller=null;busy(false);}}
  }
  $("verify-fin").addEventListener("click",verify);$("cancel-fin").addEventListener("click",()=>state.controller?.abort());
  $("fin-allowance").addEventListener("change",event=>{state.allowance=event.target.value;plot();});
  $("export-fin").addEventListener("click",()=>{if(!state.valid||!state.data)return;const blob=new Blob([JSON.stringify(state.data)],{type:"application/json"}),url=URL.createObjectURL(blob),link=el("a");link.href=url;link.download=`plate-fin-experiment-${state.data.provenance.package_manifest_sha256.slice(0,12)}.json`;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  function select(kind,push=false){kind=kind==="fin"?"fin":"rectangular";for(const name of ["rectangular","fin"]){const chosen=name===kind;$("benchmark-"+name).hidden=!chosen;$("experiment-tab-"+name).setAttribute("aria-selected",String(chosen));$("experiment-tab-"+name).tabIndex=chosen?0:-1;}if(push)history.pushState(null,"","#"+kind);if(kind==="fin"&&!state.data&&!state.controller)verify();requestAnimationFrame(()=>{plot();geometry();window.dispatchEvent(new Event("resize"));});}
  for(const name of ["rectangular","fin"]){$("experiment-tab-"+name).addEventListener("click",()=>select(name,true));$("experiment-tab-"+name).addEventListener("keydown",event=>{let next;if(event.key==="Home")next="rectangular";if(event.key==="End")next="fin";if(event.key==="ArrowLeft"||event.key==="ArrowRight")next=name==="fin"?"rectangular":"fin";if(next){event.preventDefault();select(next,true);$("experiment-tab-"+next).focus();}});}
  window.addEventListener("popstate",()=>select(location.hash.slice(1)));let frame;window.addEventListener("resize",()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{plot();geometry();});});
  window.addEventListener("pagehide",()=>{if(state.controller){$("fin-status").classList.add("calculation-stale");$("fin-status").textContent=state.data?"核对已中断；显示上次板翅回放":"板翅核对已中断";}state.controller?.abort();state.generation++;state.controller=null;busy(false);});
  window.addEventListener("pageshow",event=>{if(event.persisted&&!state.valid&&!state.controller&&!$("benchmark-fin").hidden)verify();});
  select(location.hash.slice(1));
})();
