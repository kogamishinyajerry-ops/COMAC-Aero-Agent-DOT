#!/usr/bin/env python3
"""Extra direct continuum checks; no experimental arrays or residuals."""
import json,math,numpy as np
from scipy.sparse.linalg import spsolve
from conjugate_fin import *

def one_dirichlet_mean(length,alpha_z_over_u):
    odd=np.arange(1,10000,2,dtype=float)
    return float(np.sum(8/(np.pi**2*odd**2)*np.exp(-alpha_z_over_u*(odd*np.pi/(2*length))**2)))

def analytic_isothermal_plug(speed):
    a=KA/(RHO*CP); cap=RHO*CP*speed*WI*H
    # Interior x has two Dirichlet walls, equivalent to D/N half width.
    interior=one_dirichlet_mean(WI/2,a*L/speed)*one_dirichlet_mean(H,a*L/speed)
    uside=speed*WI/WS; side=one_dirichlet_mean(WS,a*L/uside)
    return cap*(15*(1-interior)+2*(1-side))

def main():
    rows=[]
    for speed in [4.,10.,20.]:
        r=Model(48,144,profile='plug',isothermal=True).solve(speed,nz=1600)
        exact=analytic_isothermal_plug(speed)
        rows.append({'speed_m_s':speed,'G_numerical_W_K':r['G_W_K'],'G_continuum_exact_W_K':exact,'relative_error':r['G_W_K']/exact-1,'energy_relative_balance':r['energy_relative_balance_max']})
    m=Model(48,144); fin=m.fins[1]; Kss=m.K[fin,:][:,fin]; rhs=m.fin_root_g[fin]; tau=spsolve(Kss,rhs)
    heff=1/((WI/48)/(2*KA)+T/(2*205.))
    exact=math.sqrt(2*heff*205*T)*math.tanh(H*math.sqrt(2*heff/(205*T)))
    q=2*205*T/(H/144)*(1-tau[0])
    fincheck={'assembled_fin_index':1,'bath_fluid_normalized_T':0,'base_normalized_T':1,'interface_h_eff_from_half_cell_resistance':heff,'analytic_Q_per_length':exact,'assembled_Q_per_length':q,'relative_Q_error':q/exact-1}
    slow=Model(12,36).solve(.001,nz=100)
    checks={'isothermal_plug_continuum':max(abs(r['relative_error']) for r in rows)<.005,'actual_assembled_fin_continuum':abs(fincheck['relative_Q_error'])<.002,'low_flow_capacity_limit':abs(slow['effectiveness']-1)<1e-8}
    checks={k:bool(v) for k,v in checks.items()}
    out={'status':'passed' if all(checks.values()) else 'failed','gates':checks,'plug_rows':rows,'assembled_fin':fincheck,'low_flow':{'speed_m_s':.001,'effectiveness':slow['effectiveness']},'source':'Analytic separation-of-variables heat equation and uniform-bath adiabatic-tip fin ODE, independently evaluated from discretized geometry','code_sha256':digest(HERE/'conjugate_fin.py'),'check_code_sha256':digest(__file__),'experimental_data_read':False}
    (HERE/'independent_limits.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
    if not all(checks.values()):raise SystemExit(1)
if __name__=='__main__':main()
