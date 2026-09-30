#!/usr/bin/env python3
"""Static scientific figures made from saved, hash-stamped results only."""
import os,pathlib,json,argparse
SCRIPT=pathlib.Path(__file__).resolve().parent
ROOT=SCRIPT.parents[1];DATA=ROOT/'examples/plate_fin_experiment';SOURCE=SCRIPT/'original_freeze'
parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=pathlib.Path,required=True);args=parser.parse_args()
HERE=args.output_dir.resolve()
if HERE.is_relative_to(SCRIPT) or HERE.is_relative_to(DATA) or HERE.exists():raise ValueError('Plot output must be fresh and outside pinned publication directories')
HERE.mkdir(parents=True,exist_ok=False)
os.environ.setdefault('MPLCONFIGDIR',str(HERE/'.mplconfig'))
os.environ.setdefault('XDG_CACHE_HOME',str(HERE/'.cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

def main():
    data=json.loads((DATA/'experimental_comparison.json').read_text())
    fig,(ax,err)=plt.subplots(2,1,figsize=(10,7),sharex=True,gridspec_kw={'height_ratios':[2.3,1]})
    fd=[r for r in data['results'] if r['profile']=='fd'];x=np.array([r['prediction']['V_interior_m_s'] for r in fd]);y=np.array([r['observed_approx_Rth_K_W'] for r in fd]);inside=np.array([r['laminar_nominal_scope'] for r in fd])
    ygraph=[r['graphical_readout_envelope_separate']['Rth_K_W'] for r in fd];xgraph=[r['graphical_readout_envelope_separate']['V_m_s'] for r in fd]
    ax.errorbar(x,y,xerr=xgraph,yerr=ygraph,fmt='none',ecolor='.6',elinewidth=3,alpha=.5,label='Graphical half-symbol allowances (separate)')
    ax.errorbar(x,y,yerr=.012*y,fmt='none',ecolor='black',elinewidth=1.2,capsize=3,label='Author Rth uncertainty 1.2% (separate)')
    ax.scatter(x[:3],y[:3],s=28,c='black',marker='s',zorder=5,label='Figure8 markers, robust laminar scope')
    ax.scatter(x[3:4],y[3:4],s=38,c='#b38313',marker='D',zorder=5,label='Nominal laminar point; regime uncertain')
    ax.scatter(x[~inside],y[~inside],s=28,facecolors='white',edgecolors='black',marker='s',zorder=5,label='Figure8 markers, outside laminar scope')
    for profile,color,label in [('fd','#1565a0','Prescribed fully developed velocity'),('plug','#c96c13','Prescribed plug velocity')]:
        rows=[r for r in data['results'] if r['profile']==profile]
        ax.plot(x,[r['prediction']['Rth_K_W'] for r in rows],color=color,ls='-' if profile=='fd' else '--',label=label)
        err.plot(x,100*np.array([r['relative_Rth_discrepancy'] for r in rows]),'o-',color=color,ms=3)
    vmax=2300*data['nominal_properties']['nu_m2_s']/data['geometry']['hydraulic_diameter_m']
    for a in [ax,err]:
        a.axvline(vmax,color='.35',ls='--',lw=1);a.axvspan(vmax,x.max()+.8,color='.92',zorder=-3);a.grid(alpha=.15)
    ax.text(vmax+.2,.94,'Outside predeclared\nlaminar scope',fontsize=9,va='top')
    ax.set_ylabel('Whole-sink thermal resistance [K/W]');ax.set_ylim(.25,.98);ax.legend(fontsize=8,loc='upper right')
    err.axhline(0,color='black',lw=.8);err.set_ylabel('Rth discrepancy [%]');err.set_xlabel('Figure-inferred nominal channel speed [m/s]');err.set_xlim(3.5,x.max()+.8)
    fig.suptitle('Untuned conjugate fin/channel subcase vs approximate Figure8 data\n16 fins; 15 interior + 2 thermally distinct side channels; aluminum k = 205 W/(m K)',fontsize=12)
    fig.text(.5,.008,'Prescribed profiles are not confidence bounds or developing-inlet solutions. No axial solid conduction. Uncertainty coverage is unspecified.',ha='center',fontsize=8)
    fig.tight_layout(rect=[0,.035,1,.94]);fig.savefig(HERE/'comparison.png',dpi=180);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(9,5),sharey=True)
    for ax,profile in zip(axs,['fd','plug']):
        field=json.loads((SOURCE/f'temperature_fields_{profile}_marker_00.json').read_text());f=field['fields'][-1]
        for fin in f['fins']:
            y=np.array(f['channels'][0]['y_cell_centres_mm']);ax.plot(fin['normalized_T'],y,'o-',label=f"Fin {fin['fin_index_from_side']} from sidewall")
        ax.set_xlabel('(Tfin − Tin) / (Tbase − Tin)');ax.set_xlim(.983,1.0005);ax.grid(alpha=.2);ax.legend(fontsize=8);ax.set_title(('Fully developed' if profile=='fd' else 'Plug')+' prescribed velocity')
    axs[0].set_ylabel('Height above base [mm]');fig.suptitle('Conjugate outlet fin temperatures, nominal V = '+str(round(field['V_interior_m_s'],3))+' m/s\nNormalized field samples, no recovered absolute temperature runs');fig.tight_layout(rect=[0,0,1,.88]);fig.savefig(HERE/'fin_temperature_profiles.png',dpi=180)
if __name__=='__main__':
    main()
    # Font discovery cache is regenerable, not a scientific JSON artifact.
    for cache in (HERE/'.mplconfig').glob('fontlist*.json'): cache.unlink()
