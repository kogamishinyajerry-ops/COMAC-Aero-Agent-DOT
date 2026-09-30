"use strict";
(() => {
  const $=id=>document.getElementById(id), NS="http://www.w3.org/2000/svg";
  const colors={"24":"#467c9d","13":"#087d78","7.5":"#c58a3b"};
  const state={data:null,valid:false,controller:null,generation:0,filter:"all"};
  const f=(v,n=2)=>Number.isFinite(v)?v.toLocaleString("zh-CN",{minimumFractionDigits:n,maximumFractionDigits:n}):"未给出";
  const sign=(v,n=2)=>(v>0?"+":"")+f(v,n);
  function el(tag,text,className){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(className)n.className=className;return n;}
  function s(tag,attributes={}){const n=document.createElementNS(NS,tag);Object.entries(attributes).forEach(([k,v])=>n.setAttribute(k,String(v)));return n;}
  function label(root,x,y,text,attrs={}){const n=s("text",{x,y,"font-family":"system-ui,sans-serif","font-size":11,fill:"#697a82",...attrs});n.textContent=text;root.append(n);return n;}
  function metric(title,value,unit=""){const n=el("div",undefined,"metric");n.append(el("span",title));const v=el("strong",value);v.append(el("small",unit));n.append(v);return n;}
  function a(title,url){const n=el("a",title);n.href=url;n.target="_blank";n.rel="noopener noreferrer";return n;}

  function chart(){
    if(!state.data)return;
    const all=state.data.comparison.rows,rows=state.filter==="all"?all:all.filter(r=>String(r.length_inches)===state.filter);
    const width=$("comparison-chart").clientWidth||620,height=$("comparison-chart").clientHeight||350;
    const left=46,top=22,w=width-left-18,h=height-top-48;
    const values=all.flatMap(r=>[r.observed_bulk_theta,r.predicted_bulk_theta]);
    const low=Math.floor(Math.min(...values)*10)/10,high=Math.ceil(Math.max(...values)*10)/10;
    const x=v=>left+(v-low)/(high-low)*w,y=v=>top+h-(v-low)/(high-low)*h;
    const picture=s("svg",{viewBox:`0 0 ${width} ${height}`,role:"img","aria-label":`显示 ${rows.length} 条记录的实测与模型出口衰减，完整数据仍保留`});
    for(let i=0;i<=5;i++){
      const v=low+(high-low)*i/5;
      picture.append(s("line",{x1:x(v),x2:x(v),y1:top,y2:top+h,stroke:"#e9eeee"}));
      picture.append(s("line",{x1:left,x2:left+w,y1:y(v),y2:y(v),stroke:"#e9eeee"}));
      label(picture,x(v),top+h+18,f(v*100,0),{"font-size":10,"text-anchor":"middle"});
      label(picture,left-8,y(v)+3,f(v*100,0),{"font-size":10,"text-anchor":"end"});
    }
    picture.append(s("line",{x1:x(low),y1:y(low),x2:x(high),y2:y(high),stroke:"#88999f","stroke-width":1.2,"stroke-dasharray":"5 4"}));
    label(picture,left+w-4,top+h-8,"虚线：模型与实测一致",{"font-size":10,"text-anchor":"end"});
    rows.forEach(r=>{
      const description=`${r.id}，加热长度 ${r.length_inches} 英寸，实测衰减 ${f(r.observed_bulk_theta*100)}%，模型 ${f(r.predicted_bulk_theta*100)}%，差异 ${sign(r.residual_theta_prediction_minus_observation*100)} 个百分点`;
      const point=s("circle",{cx:x(r.observed_bulk_theta),cy:y(r.predicted_bulk_theta),r:4.5,fill:colors[String(r.length_inches)],stroke:"white","stroke-width":1,tabindex:0,"aria-label":description,"data-run-id":r.id});
      const title=s("title");title.textContent=description;point.append(title);picture.append(point);
    });
    label(picture,left+w/2,height-7,"实测出口衰减 / %",{"text-anchor":"middle"});
    label(picture,12,top+h/2,"模型出口衰减 / %",{"text-anchor":"middle",transform:`rotate(-90 12 ${top+h/2})`});
    $("comparison-chart").replaceChildren(picture);
    const legend=Object.entries(colors).map(([length,color])=>{const row=el("span"),dot=el("i",undefined,"swatch");dot.style.background=color;row.append(dot,document.createTextNode(`${length} 英寸`));return row;});
    legend.push(el("span",`当前图形 ${rows.length} / ${all.length} 条`));$("comparison-legend").replaceChildren(...legend);
  }

  function render(data){
    const c=data.comparison,n=data.numerical;
    $("run-count").textContent=String(c.count);
    $("fitted-count").textContent=String(data.calibration_records);
    $("mean-residual").textContent=f(c.all_rows_mean_absolute_residual_theta*100);
    $("max-residual").textContent=f(c.all_rows_maximum_absolute_residual_theta*100);
    const maximum=Math.max(...c.groups.map(g=>g.mean_absolute_residual_theta));
    $("length-comparison").replaceChildren(...c.groups.map(g=>{
      const row=el("div",undefined,"length-residual-row"),heading=el("div"),value=el("strong",f(g.mean_absolute_residual_theta*100));value.append(el("small","百分点"));heading.append(el("span",`${g.length_inches} 英寸 · ${g.count} 条`),value);
      const track=el("div",undefined,"bar-track"),bar=el("div",undefined,"bar");bar.style.background=colors[String(g.length_inches)];bar.style.width=`${g.mean_absolute_residual_theta/maximum*100}%`;track.append(bar);
      row.append(heading,track,el("p",`有符号差异范围 ${sign(g.minimum_residual_theta*100)} 至 ${sign(g.maximum_residual_theta*100)} 个百分点`));return row;
    }));
    const count=c.rows.filter(r=>r.residual_theta_prediction_minus_observation>0).length;
    $("residual-meaning").textContent=`${count} / ${c.count} 条记录中，模型的出口衰减更高，也就是预测的空气吸热更少。图形筛选不会改变这些完整数据统计。`;
    const gates=Object.values(n.gates);
    $("numerical-summary").replaceChildren(metric("数学验收关卡",`${gates.filter(Boolean).length} / ${gates.length}`),metric("独立参考最大相对差异",f(n.independent_reference.maximum_absolute_relative_difference*100,4),"%"),metric("横截面网格",`${n.grid.nx} × ${n.grid.ny}`),metric("独立参考最大绝对差异",f(n.independent_reference.maximum_absolute_theta_difference*100,4),"百分点"));
    $("source-rows").replaceChildren(...c.rows.map(r=>{const row=el("tr");[r.id,f(r.length_inches,1),f(r.Gz,1),r.Re===null?"未给出":f(r.Re,0),f(r.observed_bulk_theta*100),f(r.predicted_bulk_theta*100),sign(r.residual_theta_prediction_minus_observation*100)].forEach(v=>row.append(el("td",v)));return row;}));
    $("experiment-provenance").replaceChildren(
      el("p","来源为 Wibulswas 的 1966 年 UCL 博士论文，附录 7.6，第 124–125 页。32 行均保留；8 个原文未给出的 Reynolds 数未填补。"),
      a(data.source.title,data.source.url),
      el("p","输入角色：来源报告的 Graetz 数作为流动和物性组合条件；入口温度与壁温用于归一化。这不是从独立原始流量出发的设备温度预测。"),
      el("p","不确定度：未取得完整测量误差预算。±0.05°F 的温度扰动仅作输入敏感性检查，不能当成实验误差界或置信区间。"),
      el("p","标准库应用只核对与展示保存记录。完整数值重算使用 research/rectangular_duct/reproduce.sh，需要该目录列出的研究依赖。原始 PDF 不随包分发；可另行审计其来源哈希。"),
      el("p",`原始冻结响应 ${data.provenance.original_precomparison_frozen_response_sha256}`),
      el("p",`当前研究包清单 ${data.provenance.package_manifest_sha256}`),
      el("p",`本次核对 ${data.provenance.verified_file_count} 个文件；读取器源码 ${data.provenance.reader_source_sha256}`)
    );
  }

  function busy(value){$("verify-record").disabled=value;$("cancel-record").hidden=!value;$("export-record").disabled=value||!state.valid;$("length-filter").disabled=value||!state.data;}
  function validate(data){
    if(data.schema!=="aerolab-experiment-replay-v1"||data.execution!=="verified_research_replay"||data.live_computation!==false)throw new Error("研究回放类型不匹配");
    if(data.calibration_records!==0||data.comparison.physical_validation_pass!==null)throw new Error("数据的拟合或验证声明不符合此研究范围");
    if(data.comparison.count!==32||data.comparison.rows.length!==32||!data.numerical.all_passed||!data.numerical.packaging_replay_verified)throw new Error("研究证据不完整或未通过独立核对");
    if(!/^[a-f0-9]{64}$/.test(data.provenance.package_manifest_sha256))throw new Error("研究包指纹无效");
  }
  async function verify(){
    const generation=++state.generation;state.controller?.abort();state.controller=new AbortController();state.valid=false;busy(true);$("experiment-error").hidden=true;$("experiment-status").classList.remove("calculation-stale");$("experiment-status").textContent="正在核对研究记录与代码指纹…";
    try{
      const response=await fetch("/api/physics/experiment",{signal:state.controller.signal});const data=await response.json();if(!response.ok)throw new Error(data.error||`HTTP ${response.status}`);if(generation!==state.generation)return;
      validate(data);render(data);state.data=data;state.valid=true;chart();$("experiment-status").textContent=`已核对的研究回放 · ${data.provenance.package_manifest_sha256.slice(0,12)} · 此页没有重新求解`;
    }catch(error){
      if(generation!==state.generation)return;$("experiment-status").classList.add("calculation-stale");
      if(error.name==="AbortError")$("experiment-status").textContent=state.data?"已取消核对，当前显示上次研究回放":"已取消核对，尚无有效研究记录";
      else{$("experiment-error").textContent=`研究记录核对失败：${error.message}。${state.data?"下方保留上次回放；导出已停用。":"请检查研究包后重试。"}`;$("experiment-error").hidden=false;$("experiment-status").textContent=state.data?"当前记录未通过核对；显示上次回放":"尚无已核对的研究回放";}
    }finally{if(generation===state.generation){state.controller=null;busy(false);}}
  }
  $("verify-record").addEventListener("click",verify);$("cancel-record").addEventListener("click",()=>state.controller?.abort());
  $("length-filter").addEventListener("change",event=>{state.filter=event.target.value;chart();});
  $("export-record").addEventListener("click",()=>{if(!state.valid||!state.data)return;const blob=new Blob([JSON.stringify(state.data)],{type:"application/json"}),url=URL.createObjectURL(blob),link=el("a");link.href=url;link.download=`historical-experiment-${state.data.provenance.package_manifest_sha256.slice(0,12)}.json`;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  let frame;window.addEventListener("resize",()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(chart);});
  window.addEventListener("pagehide",()=>{if(state.controller){$("experiment-status").classList.add("calculation-stale");$("experiment-status").textContent=state.data?"核对已中断；显示上次回放":"核对已中断，尚无有效研究记录";}state.controller?.abort();state.generation++;state.controller=null;busy(false);});
  window.addEventListener("pageshow",event=>{if(event.persisted&&!state.valid&&!state.controller)verify();});
  verify();
})();
