"""Bound K>0 roots from K=0 brackets and coordinatewise thermal monotonicity.

No hydraulic PDE, thermal march, or additional root search is performed.
"""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
STUDY=HERE.parents[1]
load=lambda p:json.loads(p.read_text())


def main():
    rows=[]
    for design in ('n16_t860','n16_t600'):
        results=load(STUDY/'results'/f'{design}.json')
        cases={case['K']:case for case in results['cases']}
        reference=cases[0]['roots']['main']
        lower=load(STUDY/reference['fine_bracket'][0]['file'])
        upper=load(STUDY/reference['fine_bracket'][1]['file'])
        for coefficient in (1,2):
            candidate=cases[coefficient]['roots']['main']
            # At the minimum transformed pressure every active branch flows no
            # faster than the lower K0 bracket, so its heat is <= 60 W. At the
            # maximum transformed pressure every branch is no slower than the
            # upper K0 bracket, so its heat is >= 60 W.
            transforms_lo=[lower['nominal_pressure_budget_Pa']+.5*1.204*coefficient*r['mean_speed_m_s']**2/.6
                           for r in lower['channels'] if not r['blocked']]
            transforms_hi=[upper['nominal_pressure_budget_Pa']+.5*1.204*coefficient*r['mean_speed_m_s']**2/.6
                           for r in upper['channels'] if not r['blocked']]
            lo,hi=min(transforms_lo),max(transforms_hi)
            bracket=candidate['fine_bracket']
            rows.append({'design':design,'K':coefficient,'independent_lower_Pa':lo,'independent_upper_Pa':hi,
                         'bound_width_Pa':hi-lo,'reported_root_Pa':candidate['root_Pa'],
                         'whole_reported_bracket_within_bound':lo<=bracket[0]['P_Pa']<bracket[1]['P_Pa']<=hi})
    result={'status':'passed' if all(r['whole_reported_bracket_within_bound'] for r in rows) else 'failed',
            'method':'Map each active branch speed at the K0 heat-sign endpoints through the K>0 pressure law. The minimum lower mapping and maximum upper mapping enclose the root by coordinatewise thermal monotonicity.',
            'scope':'Independent analytic bounds conditional on the K0 brackets and the verified discrete thermal monotonicity; no physical uncertainty interpretation.',
            'rows':rows,'new_thermal_solves':0,'new_Poisson_solves':0,'review_code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
