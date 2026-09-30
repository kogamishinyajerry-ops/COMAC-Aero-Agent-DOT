"""Read-only independent hydraulic audit, with only ignored review output."""
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[5]
SOURCE = ROOT / "research/pressure_fin/original_freeze/study/pressure_fin.py"
spec = importlib.util.spec_from_file_location("accepted_pressure_fin_review", SOURCE)
accepted = importlib.util.module_from_spec(spec)
spec.loader.exec_module(accepted)


def scalar_speed(dp, resistance, coefficient):
    if coefficient == 0:
        return dp / resistance
    return brentq(lambda u: resistance*u + .5*accepted.RHO*coefficient*u*u-dp,
                  0, dp/resistance, xtol=1e-13, rtol=1e-14)


def exact_mean(width, height):
    thin, wide = sorted((width, height))
    odd = np.arange(1, 12000, 2, dtype=float)
    correction = np.sum(np.tanh(odd*math.pi*wide/(2*thin))/odd**5)
    return thin**2/12 * (1 - 192*thin/(math.pi**5*wide)*correction)


def main():
    rows = []
    sound = math.sqrt(1.4*287.05*(25+273.15))
    for thickness in (.00086, .0006):
        for nx, ny in ((48, 144), (64, 192)):
            model = accepted.PressureFin(t=thickness, nx=nx, ny=ny)
            for index in (0, 1):
                channel = model.channels[index]
                width, mean = channel['width'], channel['wmean']
                resistance = accepted.MU*accepted.L/mean
                exact_resistance = accepted.MU*accepted.L/exact_mean(width, accepted.H)
                dh = 2*width*accepted.H/(width+accepted.H)
                # Infinite parallel plates are a supersolution to the rectangular Poisson problem.
                peak_factor_bound = min(width, accepted.H)**2/(8*mean)
                u_limit = min(2300*accepted.NU/dh, .1*sound/peak_factor_bound)
                for coefficient in (0, 1, 2):
                    p_limit = resistance*u_limit + .5*accepted.RHO*coefficient*u_limit*u_limit
                    comparisons = []
                    for pressure in (15., 25., 50., min(200., .999*p_limit)):
                        speed = scalar_speed(pressure, resistance, coefficient)
                        exact_speed = scalar_speed(pressure, exact_resistance, coefficient)
                        stable = (pressure*mean/(accepted.MU*accepted.L) if coefficient == 0 else
                                  2*pressure/(resistance+math.sqrt(resistance**2+2*accepted.RHO*coefficient*pressure)))
                        doubled = scalar_speed(2*pressure, resistance, coefficient)
                        comparisons.append({'pressure_Pa':pressure, 'mean_speed_m_s':speed,
                            'stable_root_relative':stable/speed-1,
                            'raw_vs_exact_flow_relative':speed/exact_speed-1,
                            'pressure_closure_relative':(resistance*speed+.5*accepted.RHO*coefficient*speed**2)/pressure-1,
                            'double_pressure_speed_ratio':doubled/speed,
                            'Re':speed*dh/accepted.NU,
                            'Mach_conservative_bound':speed*peak_factor_bound/sound})
                    rows.append({'thickness_mm':thickness*1000, 'mesh':[nx,ny], 'channel':index,
                        'K':coefficient,'raw_mean_m2':mean, 'exact_mean_m2':exact_mean(width,accepted.H),
                        'linear_resistance_Pa_s_m':resistance,
                        'sampled_peak_factor':float(channel['shape'].max()),
                        'conservative_peak_factor':peak_factor_bound,'branch_scope_pressure_limit_Pa':p_limit,
                        'comparisons':comparisons})
    comparisons = [comparison for row in rows for comparison in row['comparisons']]
    checks = {'stable_formula_matches_scalar_root':all(abs(c['stable_root_relative'])<1e-10 for c in comparisons),
        'pressure_closure':all(abs(c['pressure_closure_relative'])<1e-12 for c in comparisons),
        'raw_vs_exact_flow':all(abs(c['raw_vs_exact_flow_relative'])<.002 for c in comparisons),
        'conservative_peak_exceeds_sampled':all(r['conservative_peak_factor']>=r['sampled_peak_factor'] for r in rows),
        'doubling_law':all((abs(c['double_pressure_speed_ratio']-2)<1e-12 if r['K']==0 else
                           math.sqrt(2)<c['double_pressure_speed_ratio']<2)
                          for r in rows for c in r['comparisons'])}
    result = {'status':'passed' if all(checks.values()) else 'failed', 'checks':checks, 'rows':rows,
        'accepted_model_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'review_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scope':'Independent scalar-root and rectangular-series checks; no thermal roots or physical validation'}
    output = json.dumps(result,indent=2,allow_nan=False)+'\n'
    assert len(output.encode())<100000
    Path(__file__).with_suffix('.json').write_text(output)
    print(json.dumps({'status':result['status'],'checks':checks,'max_raw_flow_error':max(abs(c['raw_vs_exact_flow_relative']) for c in comparisons),
        'main_nominal_pressure_limits':[{'thickness_mm':r['thickness_mm'],'K':r['K'],'channel':r['channel'],
        'limit_Pa':r['branch_scope_pressure_limit_Pa']} for r in rows if r['mesh']==[48,144]]},indent=2))


if __name__ == '__main__':
    main()
