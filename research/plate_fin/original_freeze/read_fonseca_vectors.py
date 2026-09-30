"""Read plotted marker geometry, not raw experimental data. No model fitting.
Requires the already-installed PyMuPDF. Inputs bound to the archived publisher PDF.
"""
import hashlib,json,pathlib,sys
import fitz
src=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else '/tmp/fonseca2024_zenodo.pdf')
expected='c14571f635c5767ae3fc57f90fb18514595a54dc53918bc7454da084839c5a01'
assert hashlib.sha256(src.read_bytes()).hexdigest()==expected
page=fitz.open(src)[8]
ds=page.get_drawings()
# Coordinates inspected against PDF page 9, printed page94. Do not use fit curves.
# Fig7: x=500 at102.34118; x=4000 at264.92114; y=Nu4 at210.81248; y=Nu18 at83.992?
# Read actual major tick locations from path objects rather than assume image pixels.
def coord(d):
 r=d['rect']; return ((r.x0+r.x1)/2,(r.y0+r.y1)/2,r.width/2,r.height/2)
fig8=[]
x4=ds[99]['rect'].x0; x22=ds[117]['rect'].x0
yp2=ds[120]['rect'].y0; yp9=ds[134]['rect'].y0
sx=18/(x22-x4); sy=.7/(yp2-yp9)
for index in range(150,162):
 d=ds[index]; x,y,hx,hy=coord(d)
 assert d['fill']==(0.,0.,0.) and len(d['items'])==1 and d['items'][0][0]=='re'
 fig8.append({'drawing_index':index,'center_pdf_points':[x,y],
 'V_channel_inferred_m_s':4+(x-x4)*sx,'Rth_K_W':.2+(yp2-y)*sy,
 'conservative_graphical_half_symbol_envelope':{'V_m_s':hx*sx,'Rth_K_W':hy*sy}})
# Audited Fig7 major y ticks: inspect the line paths at x=102.34118 and width2.71356.
ticks=[d['rect'].y0 for d in ds[:34] if d['type']=='s' and abs(d['rect'].x0-102.34117889404297)<.001 and abs(d['rect'].width-2.71356)<.002]
assert len(ticks)==8
n4=max(ticks); n18=min(ticks)
xx500=ds[0]['rect'].x0; xx4000=ds[14]['rect'].x0
sx7=3500/(xx4000-xx500); sy7=14/(n4-n18)
fig7=[]
for index in range(34,46):
 d=ds[index]; x,y,hx,hy=coord(d)
 assert d['fill']==(0.,0.,0.) and d['items'][0][0]=='re'
 fig7.append({'drawing_index':index,'Re_channel_reduced':500+(x-xx500)*sx7,
 'Nu_inlet_reduced_with_fin_efficiency':4+(n4-y)*sy7,
 'conservative_graphical_half_symbol_envelope':{'Re':hx*sx7,'Nu':hy*sy7}})
result={'status':'approximate_vector_figure_readout_not_raw_data','source_url':'https://zenodo.org/records/10975619/files/8.%20343222.pdf?download=1',
 'source_sha256':expected,'pdf_page_1based':9,'printed_page':94,
 'source_figure_ids':['Figure7 plate-fin black-square series','Figure8 plate-fin black-square series'],
 'extractor_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
 'method':'Direct filled-square centers and axis tick positions from vector paths; linear axis mapping; curve paths explicitly excluded',
 'readout_uncertainty_policy':'Conservative half-symbol-width/height envelopes, separate from experimental uncertainty; these are graphical readout allowances, not confidence intervals',
 'warning':'12 plate-fin symbols recovered in each figure; text says13 tests. No missing point is invented. Run identity and per-run inputs absent.',
 'figure8_Rth':fig8,'figure7_Nu':fig7}
out=pathlib.Path(__file__).with_name('fonseca2024_vector_readout.json')
out.write_text(json.dumps(result,indent=2)+'\n')
for a,b in zip(fig8,fig7): print('V=%6.3f Rth=%7.4f Re=%7.1f Nu=%6.3f dV=%5.3f dR=%6.4f'%(a['V_channel_inferred_m_s'],a['Rth_K_W'],b['Re_channel_reduced'],b['Nu_inlet_reduced_with_fin_efficiency'],a['conservative_graphical_half_symbol_envelope']['V_m_s'],a['conservative_graphical_half_symbol_envelope']['Rth_K_W']))
print(out)
