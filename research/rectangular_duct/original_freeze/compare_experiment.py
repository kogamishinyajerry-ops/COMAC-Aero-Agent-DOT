#!/usr/bin/env python3
"""Untuned conditional historical comparison; never a validation pass/fail."""
from pathlib import Path
import hashlib, itertools, json, math, os
import numpy as np
from scipy.interpolate import PchipInterpolator
from rectangular_graetz import ROOT, Model, sha, save, provenance

def main():
    frozen=json.loads((ROOT/'frozen_response.json').read_text())
    source=json.loads((ROOT/'experimental_source.json').read_text())
    assert frozen['all_mathematical_gates_passed'] and not frozen['experiment_used_for_selection']
    assert frozen['provenance']['code_sha256']==sha(ROOT/'rectangular_graetz.py')
    assert source['source']['pdf_sha256']==sha(ROOT/source['source']['pdf_relative_path'])
    xs=np.array([p['tau'] for p in frozen['curve']]);ys=np.array([p['bulk_theta'] for p in frozen['curve']])
    response=PchipInterpolator(xs,ys,extrapolate=False)
    # Fixed mathematical holdout points, chosen before comparing any measurement.
    checks=[]
    for t in (.012,.048,.192):
        print('Mathematical interpolation check',t,flush=True)
        direct=Model(128).march(steps=512,last=t)['endpoints'][-1]['bulk_theta']
        checks.append(dict(tau=t,curve_prediction=float(response(t)),direct_march=direct,
                           absolute_difference=abs(float(response(t))-direct)))
    interpolation=dict(points=checks,absolute_acceptance=2e-5,
                       caveat='Includes the small BE path change from a shortened final interval, not interpolation error alone.',
                       all_passed=all(c['absolute_difference']<2e-5 for c in checks))
    save(ROOT/'interpolation_verification.json',interpolation)
    if not interpolation['all_passed']:raise ValueError('Mathematical interpolation check failed; comparison withheld')
    rows=[];summaries=[]
    for group in source['groups']:
        grouped=[]
        for index,row in enumerate(group['rows'],1):
            re,gz,tin,tout,tw,printed_nu=row
            theta=(tw-tout)/(tw-tin)
            tau=(4/3)**2/gz
            assert frozen['tau_min_comparison']<=tau<=frozen['tau_max_comparison']
            pred=float(response(tau))
            # These are illustrative temperature-input perturbations, not an
            # uncertainty estimate, confidence interval or acceptance criterion.
            perturbed=[((tw+ew)-(tout+eo))/((tw+ew)-(tin+ei)) for ew,eo,ei in itertools.product((-.05,.05),repeat=3)]
            result=dict(id=f'L{group["length_inches"]:g}_run{index:02d}',
                        source_pages=group['pages'],length_inches=group['length_inches'],
                        source_L_over_Dh=group['source_L_over_Dh'],Re=re,Gz=gz,
                        Tin_F=tin,Tout_F=tout,Tw_F=tw,printed_Nu=printed_nu,
                        tau=tau,observed_bulk_theta=theta,predicted_bulk_theta=pred,
                        residual_theta_prediction_minus_observation=pred-theta,
                        relative_residual=(pred-theta)/theta,
                        illustrative_temperature_perturbation_theta_min=min(perturbed),
                        illustrative_temperature_perturbation_theta_max=max(perturbed),
                        Nu_recomputed_from_temperatures_and_Gz=-gz/4*math.log(theta))
            rows.append(result);grouped.append(result)
        residual=np.array([r['residual_theta_prediction_minus_observation'] for r in grouped])
        summaries.append(dict(length_inches=group['length_inches'],count=len(grouped),
                              mean_residual_theta=float(residual.mean()),
                              mean_absolute_residual_theta=float(np.mean(abs(residual))),
                              minimum_residual_theta=float(residual.min()),maximum_residual_theta=float(residual.max()),
                              root_mean_square_residual_theta=float(np.sqrt(np.mean(residual**2)))))
    residual=np.array([r['residual_theta_prediction_minus_observation'] for r in rows])
    result=dict(provenance=provenance(),comparison_code_sha256=sha(__file__),
        frozen_response_sha256=sha(ROOT/'frozen_response.json'),source_transcription_sha256=sha(ROOT/'experimental_source.json'),
        original_source_pdf_sha256=source['source']['pdf_sha256'],interpolation_verification=interpolation,
        interpretation='Qualified, untuned, conditional historical experimental comparison. Not a physical-validation pass and not aircraft validation.',
        input_roles=dict(model='Aspect2; constant properties; developed forced laminar velocity; all four walls common isothermal temperature; uniform thermal inlet.',
                         source_conditioning='Reported Gz is the reduced flow/property input. Measured Tin and Tw define normalization. This is not an end-to-end prediction of device temperatures or raw outlet temperatures from an independently measured mass flow.',
                         target='Mixed outlet attenuation calculated from the printed Tin, Tout, Tw.',
                         excluded='Printed Nu is not used by the model, mesh selection or acceptance. No fitted coefficient, correction factor or residual-based filtering.'),
        source_limitations=source['limitations'],
        uncertainty='No complete measurement uncertainty was established. The ±0.05°F independent temperature perturbation is illustrative sensitivity only; it is neither a physical uncertainty bound nor a confidence interval. Numerical errors are separately verified.',
        physical_validation_pass=None,physical_validation_pass_reason='No uncertainty-backed matched pure-forced laminar subset was established.',
        groups=summaries,count=len(rows),
        all_rows_mean_absolute_residual_theta=float(np.mean(abs(residual))),
        all_rows_maximum_absolute_residual_theta=float(np.max(abs(residual))),rows=rows)
    save(ROOT/'experimental_comparison.json',result)
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,(ax,ar)=plt.subplots(2,1,figsize=(8,7),sharex=True,layout='constrained',gridspec_kw={'height_ratios':[2,1]})
    gz=np.geomspace(24,180,300);ax.plot(gz,response((4/3)**2/gz),'k-',label='Frozen ideal forced-laminar model',lw=1.8)
    for group in source['groups']:
        rr=[r for r in rows if r['length_inches']==group['length_inches']]
        gg=[r['Gz'] for r in rr];tt=[r['observed_bulk_theta'] for r in rr]
        ax.plot(gg,tt,'o',ms=4,label=f'Historical {group["length_inches"]:g} in measurements')
        ar.plot(gg,[100*r['residual_theta_prediction_minus_observation'] for r in rr],'o-',ms=3)
    ax.set(ylabel='Outlet attenuation (Tw − Tout)/(Tw − Tin)',title='Aspect-2 rectangular duct: qualified historical comparison')
    ax.legend(fontsize=8);ax.grid(alpha=.25);ar.axhline(0,color='k',lw=.7)
    ar.set(xlabel='Reported Gz = Re Pr Dh / L',ylabel='Prediction − observation\n(attenuation percentage points)');ar.grid(alpha=.25)
    fig.text(.5,.005,'No fitted coefficients. Incomplete measurement uncertainty; transition, buoyancy and property caveats apply.',ha='center',fontsize=8)
    fig.savefig(ROOT/'historical_comparison.png',dpi=160,bbox_inches='tight');plt.close(fig)
    print(json.dumps(dict(groups=summaries,all_rows_MAE=result['all_rows_mean_absolute_residual_theta'],maximum_abs_residual=result['all_rows_maximum_absolute_residual_theta']),indent=2),flush=True)

if __name__=='__main__':main()
