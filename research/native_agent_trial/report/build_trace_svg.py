#!/usr/bin/env python3
from pathlib import Path
import json,html,re,argparse
P=Path(__file__).resolve().parent
ROOT=P.parent
p=ROOT/'runs'/'development'
a=argparse.ArgumentParser();a.add_argument('--terminal-run');arg=a.parse_args()
load=lambda f:json.loads(f.read_text())
f=load(p/'results'/'011_finalize.json');c=load(p/'results'/'010_cad.json')
ht=None
if arg.terminal_run:
 hp=ROOT/'runs'/arg.terminal_run
 hfs=sorted((hp/'results').glob('*_finalize.json'));assert len(hfs)==1
 hf=load(hfs[0]);ht=load(hp/'task.json')
 ev=[load(x) for x in sorted((hp/'results').glob('*_evaluate.json'))]
H=1308 if ht else 1060
s=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{H}" viewBox="0 0 1200 {H}" role="img" aria-labelledby="title desc"><title id="title">原生助手工程试验：从固定约束到真实 CAD</title><desc id="desc">基于终态记录的中文证据摘要，保留超重失败、几何变化、实时求解、网格验证及真实实体结果。SVG 渲染图，不是浏览器截图。</desc><rect width="1200" height="{H}" fill="#f7faf6"/>']
def rect(x,y,w,h,color,stroke=None,r=9):s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{color}"'+(f' stroke="{stroke}"' if stroke else '')+'/>')
def text(x,y,t,size=15,color='#203d33',weight=400):s.append(f'<text x="{x}" y="{y}" font-family="Noto Sans CJK SC, sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}">{html.escape(str(t))}</text>')
def line(x,y,x2,y2,col='#d7e2d8'):s.append(f'<line x1="{x}" y1="{y}" x2="{x2}" y2="{y2}" stroke="{col}"/>')
text(40,38,'NATIVE ENGINEERING TRIAL  /  2026.10.01',12,'#6d8476',700)
text(40,86,'从固定约束，走到真实 CAD',35,weight=700)
text(40,118,'当前原生助手编排 + 确定性单步工具 · 条件性部件筛选',17,'#5c7165')
rect(949,47,207,45,'#ddecdf');text(971,77,'开发试验：条件性通过',16,'#246145',700)
rect(40,145,1120,74,'#eaf0e6')
for x,b,l in [(60,'26.361 g','鳍片质量 / 上限 30 g'),(345,'77.357 °C','最坏网格温度 / 上限 85 °C'),(640,'7 次 / 11 步','实时 PDE 求解 / 工具动作'),(939,'424.7 秒','全程墙钟时间')]:
 text(x,178,b,25,weight=700);text(x,203,l,12,'#647b6b')
text(40,253,'01  完整执行链：失败必须保留',20,weight=700)
steps=[('固定要求','50 W / 25 °C 入口','85 °C / 30 g 上限'),('检查排除','9 个离散候选','8 个质量 / Re 排除'),('实时求解','0.86 mm 方案','超重 → 保留失败'),('改变几何','0.86 → 0.60 mm','两工况重新求解'),('网格检查','截面 + 轴向加密','每个工况均核对'),('真实 CAD','STEP / STL 导出','往返 + 水密检查'),('最终接受','0.60 mm 鳍片','数值门槛均通过')]
for i,(name,l1,l2) in enumerate(steps):
 x=40+i*161;rect(x,271,154,106,'#fbeee6' if i==2 else ('#e7f2e8' if i in [3,6] else '#ffffff'),'#d7e3d5')
 text(x+11,293,f'{i+1:02}',11,'#839080',700);text(x+11,317,name,16,weight=700);text(x+11,340,l1,12,'#607467');text(x+11,360,l2,12,'#607467')
 if i<6:text(x+155,330,'›',15,'#618870',700)
rect(40,395,545,293,'#ffffff','#d7e3d5');rect(604,395,556,293,'#ffffff','#d7e3d5')
text(60,424,'保留的失败  →  改薄后的选择',19,weight=700)
text(60,452,'鳍片质量（g）',13,'#63796b')
for y,l,m,col in [(485,'0.86 mm',37.783584,'#c98467'),(523,'0.60 mm',26.36064,'#427c5b')]:
 text(60,y,l,13);rect(150,y-18,m*8,24,col,r=3);text(150+m*8+8,y,m and f'{m:.3f}',13,col,700)
s.append('<line x1="390" y1="457" x2="390" y2="534" stroke="#96593e" stroke-dasharray="4 3"/>');text(393,550,'30 g 上限',11,'#96593e')
text(60,578,'同一故障工况 · 主网格均匀底温',13,'#63796b')
text(61,614,'84.900 °C',26,'#a26246',700);text(224,613,'→',27,'#819685');text(274,614,'77.336 °C',26,'#427c5b',700)
text(60,642,'原方案温度勉强过关，但超重 7.784 g；没有改低要求',12,'#876046')
text(60,667,'16 片不变，内部间隙从 1.849 增至 2.127 mm',12,'#63796b')
text(624,424,'选定实体：16 片 × 0.60 mm',19,weight=700)
svg=(p/c['preview_file']).read_text();polygons=re.findall(r'<polygon[^>]+/>',svg)
s.append('<g transform="translate(633 390) scale(0.60)">'+''.join(polygons)+'</g>')
text(1040,466,'90 mm',15,weight=700);text(1040,486,'长',11,'#63796b');text(1040,520,'41.5 mm',15,weight=700);text(1040,540,'宽',11,'#63796b');text(1040,574,'11.3 mm',15,weight=700);text(1040,594,'鳍片高',11,'#63796b')
text(624,641,'✓ STEP 重导入   ✓ STL 水密 / 连通   ✓ 1 个有效实体',12,'#427c5b',700)
text(624,667,'同参数几何预览；含 3 mm 支撑底板的总质量 56.614 g',12,'#63796b')
text(40,723,'02  两个工况 × 三组网格：全部数值门槛通过',20,weight=700)
rect(40,739,1120,33,'#eaf0e6',r=0)
cols=[60,325,488,651,819,1030]
for x,t in zip(cols,['50 W 工况','主网格','截面加密','轴向加密','ΔG 截面 / 轴向','判定']):text(x,762,t,12,'#617768',700)
for yy,case,label in [(800,'nominal','正常 25 Pa'),(839,'combined_fault','18 Pa + 封闭首个内通道')]:
 cv=next(x for x in f['case_verification'] if x['case_id']==case)
 vals={d['mesh_id']:d['required_uniform_base_temperature_C'] for q in (p/'results').glob('*_evaluate.json') if (d:=load(q))['case_id']==case and d['design_id']=='n16_t600'}
 row=[label]+[f'{vals[m]:.3f} °C' for m in ['primary','spatial','axial']]+[f'{cv["spatial_G_relative"]*100:.4f}% / {cv["axial_G_relative"]*100:.4f}%','通过']
 for x,t in zip(cols,row):text(x,yy,t,12,'#2d6149' if x==1030 else '#344e3f')
 line(40,yy+12,1160,yy+12)
text(40,878,'所选方案最大 Re ≈ 1195 · 最坏温度裕度 7.643 °C · 全局最优未建立 · 实验物理验证未建立',13,'#617768')
if ht:
 rect(40,902,1120,286,'#e7f2e8','#b9d0ba')
 text(60,932,'03  保留测试终态：'+('条件性通过' if hf.get('conditional_acceptance_pass') else str(hf['outcome'])),20,weight=700)
 m=max(d['result']['fin_only_mass_kg']*1000 for d in ev if d['design_id']==hf['selected_design_id'])
 maxt=max(d['worst_mesh_temperature_C'] for d in hf['case_verification'])
 text(60,963,f'新要求：36 W · 80 °C · 25 g · 正常/降压/封闭/叠加四工况',15,'#2d6149',700)
 text(60,992,'上轮 16 片方案：26.361 g 超重 → 改为 12 片 × 0.60 mm',14,'#9b694b',700)
 text(60,1030,f'{m:.3f} g  /  {maxt:.3f} °C  /  13 次实时求解  /  17 步工具动作',22,'#2d6149',700)
 text(60,1060,'四工况最坏网格温度（°C）：64.370 / 71.383 / 67.990 / 75.661',13,'#617768')
 text(60,1088,'四工况 × 三网格均通过；真实 STEP / STL 检查通过',13,'#617768')
 text(60,1116,'518.64 秒墙钟 · 保留 1 条超重失败 · 温度裕度 4.339 °C',13,'#617768')
 s.append('<a href="../heldout_independent_grade.json">')
 text(60,1154,'独立证据评分 23/23 通过；同一熟悉家族的一次新要求测试。',13,'#796f42')
 hc=load(hp/'results'/'016_cad.json')
 hpv=(hp/hc['preview_file']).read_text();hpoly=re.findall(r'<polygon[^>]+/>',hpv)
 s.append('<g transform="translate(854 932) scale(0.49)">'+''.join(hpoly)+'</g>')
 text(879,1160,'12 片同参数 CAD 预览',12,'#617768')
 s.append('</a>')
 text(60,1178,'25 g 仅余一个质量合格候选；不是困难组合优化或广泛泛化验证。',12,'#796f42')
 y=1218
else:
 rect(40,902,1120,76,'#f1f1e6','#d5d6bf');text(60,932,'03  保留测试：等待终态证据',19,weight=700);text(60,959,'尚未纳入局部结果，不预判成败。当前图只展示已完成的开发试验。',13,'#798069');y=1004
text(40,y,'范围：质量限额只计鳍片（开发 30 g / 保留测试 25 g）；底板热扩散与风道实体不在验证范围。',12,'#6c7d6e')
text(40,y+23,'会话声明：外部模型 API 0 次、执行中人工干预 0 次；模型身份未核验。开发已见几何族结果。',12,'#6c7d6e')
s.append('<a href="native-agent-evidence.html">')
text(40,y+44,'源：native-agent-evidence.html / heldout_independent_grade.json · 28 条事件/结果哈希核对通过',11,'#809080')
s.append('</a>')
s.append('</svg>');(P/'native-agent-trace.svg').write_text(''.join(s));print(P/'native-agent-trace.svg')
