#!/usr/bin/env python3
"""Presentation-only rendering from frozen numerical/source evidence."""
from pathlib import Path
import os,json
R=Path(__file__).resolve().parent
os.environ.setdefault('MPLCONFIGDIR',str(R/'.mplconfig'))
os.environ.setdefault('XDG_CACHE_HOME',str(R/'.cache'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.interpolate import PchipInterpolator
f=json.loads((R/'frozen_response.json').read_text())
data=np.load(R/'cross_section_fields.npz')
fig,axes=plt.subplots(1,3,figsize=(12,4))
fig.subplots_adjust(left=.065,right=.975,bottom=.18,top=.86,wspace=.42)
for ax,key,title,vmax in [(axes[0],'velocity','Velocity / mean',2),(axes[1],'theta_tau_0.032','Attenuation at tau = 0.032',1),(axes[2],'theta_tau_0.064','Attenuation at tau = 0.064',1)]:
    im=ax.imshow(data[key],origin='lower',extent=[0,2,0,1],aspect='equal',vmin=0,vmax=vmax)
    ax.set(title=title,xlabel='x/H',ylabel='y/H');fig.colorbar(im,ax=ax,shrink=.62,pad=.035)
fig.suptitle('Ideal aspect-2 rectangular duct: cross-sectional fields',y=.97,fontsize=14)
fig.savefig(R/'cross_section_fields.png',dpi=160,bbox_inches='tight');plt.close(fig)
cc=[p for p in f['curve'] if f['tau_min_comparison']<=p['tau']<=f['tau_max_comparison']]
fig,ax=plt.subplots(figsize=(7.2,4.8),layout='constrained')
ax.semilogx([p['Gz_Dh'] for p in cc],[p['bulk_theta'] for p in cc],lw=2)
ax.set(xlabel='Gz = Re Pr Dh / L',ylabel='Mixed outlet attenuation (Tw − Tout)/(Tw − Tin)',title='Frozen aspect-2 laminar response: verified axial range',ylim=(0,1));ax.grid(alpha=.25)
fig.savefig(R/'frozen_response.png',dpi=160,bbox_inches='tight');plt.close(fig)
c=json.loads((R/'experimental_comparison.json').read_text())
response=PchipInterpolator([p['tau'] for p in f['curve']],[p['bulk_theta'] for p in f['curve']])
fig,(ax,ar)=plt.subplots(2,1,figsize=(8.4,7.5),sharex=True,gridspec_kw={'height_ratios':[2,1]})
fig.subplots_adjust(left=.16,right=.97,top=.91,bottom=.13,hspace=.12)
gz=np.linspace(24,180,400);ax.plot(gz,response((4/3)**2/gz),'k-',label='Frozen ideal forced-laminar model',lw=1.8)
for length in (24,13,7.5):
    rows=[r for r in c['rows'] if r['length_inches']==length]
    color=next(ax._get_lines.prop_cycler)['color'] if hasattr(ax._get_lines,'prop_cycler') else {24:'#2878b5',13:'#ed8f27',7.5:'#469f5b'}[length]
    gg=[r['Gz'] for r in rows]
    ax.plot(gg,[r['observed_bulk_theta'] for r in rows],'o-',ms=4,lw=.8,color=color,label=f'{length:g} in historical measurements')
    ar.plot(gg,[100*r['residual_theta_prediction_minus_observation'] for r in rows],'o-',ms=4,lw=.9,color=color)
ax.set(ylabel='Outlet attenuation (Tw − Tout)/(Tw − Tin)',title='Untuned historical comparison: all 32 source rows');ax.legend(fontsize=9);ax.grid(alpha=.25)
ar.axhline(0,color='k',lw=.8);ar.set(xlabel='Reported Gz = Re Pr Dh / L',ylabel='Prediction − observation\n(attenuation percentage points)');ar.grid(alpha=.25)
fig.text(.5,.025,'No fitted coefficients. Incomplete experimental uncertainty; transition, buoyancy and property caveats apply.',ha='center',fontsize=8.5)
fig.savefig(R/'historical_comparison.png',dpi=160,bbox_inches='tight');plt.close(fig)
print('Three evidence plots rendered from frozen data')
