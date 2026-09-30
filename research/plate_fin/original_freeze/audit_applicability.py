#!/usr/bin/env python3
"""Separate author/graphical uncertainty components and conservative regime screen."""
import json
from conjugate_fin import HERE,WI,H,NU,digest

def main():
    source=HERE.parent/'figure-readout'/'fonseca2024_vector_readout.json'; data=json.loads(source.read_text()); rows=[]; factor=(2*WI*H/(WI+H))/NU
    for i,p in enumerate(data['figure8_Rth']):
        v=p['V_channel_inferred_m_s']; re=v*factor; dg=p['conservative_graphical_half_symbol_envelope']['V_m_s']*factor
        rows.append({'marker_index':i,'V_m_s':v,'Re_nominal':re,'author_Re_upper_relative_allowance':.052,'graphical_Re_absolute_allowance':dg,'author_only_Re_interval':[re*(1-.052),re*(1+.052)],'graphical_only_Re_interval':[re-dg,re+dg],'conservative_joint_corner_Re_interval':[re*(1-.052)-dg,re*(1+.052)+dg],'scope':('robustly_in_declared_laminar_scope' if re*(1+.052)+dg<=2300 else 'nominally_laminar_boundary_uncertain' if re<=2300 else 'nominally_outside_laminar_scope')})
    out={'status':'applicability_audit_not_a_combined_confidence_interval','fixed_laminar_cutoff':2300,'method':'Retain author and graphical components separately. For scope screening only, inspect the worst-case rectangular corner obtained by adding the maximum quoted author Re allowance and the separately converted graphical V allowance. No coverage probability, independence assumption or RSS uncertainty is asserted.','source_readout_sha256':digest(source),'model_code_sha256':digest(HERE/'conjugate_fin.py'),'input_plan_sha256':digest(HERE/'precomparison_plan.json'),'audit_code_sha256':digest(__file__),'rows':rows}
    (HERE/'applicability_audit.json').write_text(json.dumps(out,indent=2)+'\n'); print([(r['marker_index'],r['scope']) for r in rows])
if __name__=='__main__': main()
