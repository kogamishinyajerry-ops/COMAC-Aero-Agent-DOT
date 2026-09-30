#!/usr/bin/env python3
"""Independent direct-versus-reduced comparison; writes only review evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
import numpy as np
from scipy.sparse import diags
from scipy.sparse.linalg import splu

HERE=Path(__file__).resolve().parent
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

ind=load("independent_axial_reference",HERE/"independent_axial_review.py")
new=load("reduced_axial_to_review",HERE.parent/"axial_fin.py")
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reconstruct_from_frozen(model,solid,speed,nz):
    nfluid=model.nfluid
    mass=model.mass_unit[:nfluid]*speed
    D=mass/(ind.base.L/nz)
    cross=model.K[:nfluid,nfluid:]
    lu=splu(model.K[:nfluid,:nfluid]+diags(D,format="csc"))
    alltheta=np.empty((nz,model.n))
    fluid=np.ones(nfluid)
    for i in range(nz):
        fluid=lu.solve(D*fluid-cross@solid[i])
        alltheta[i,:nfluid]=fluid
        alltheta[i,nfluid:]=solid[i]
    return alltheta


def comparison_cases():
    rows=[]
    for profile in ("fd","plug"):
        for speed in (4.0,10.0):
            for axial_multiplier in (0.0,1.0):
                m=new.AxialModel(4,12,20,speed,lambda_z=axial_multiplier,profile=profile)
                r=m.solve(include_samples=False)
                fields=reconstruct_from_frozen(m.model,m.solid,speed,20)
                direct,ref=ind.direct_reference(m.model,speed,20,axial_multiplier)
                rows.append({"profile":profile,"speed":speed,"axial_multiplier":axial_multiplier,
                             "relative_G_error":r["G_W_K"]/ref["G_W_K"]-1,
                             "maximum_all_theta_absolute_difference":float(np.max(abs(fields-direct))),
                             "reduced_diagnostics":r,"direct_diagnostics":ref})
    return rows


def full_mirror():
    half=new.AxialModel(4,12,20,10.0)
    full=new.AxialModel(4,12,20,10.0,full=True)
    rh=half.solve(include_samples=False)
    rf=full.solve(include_samples=False)
    direct,ref=ind.direct_reference(full.model,10.,20,1.)
    sf=full.solid.reshape(20,16,12)
    sh=half.solid.reshape(20,8,12)
    return {"relative_G_half_to_full":rh["G_W_K"]/rf["G_W_K"]-1,
            "maximum_left_fin_absolute_difference":float(np.max(abs(sh-sf[:,:8]))),
            "maximum_full_fin_mirror_difference":float(np.max(abs(sf-sf[:,::-1]))),
            "full_reduced_vs_direct_relative_G":rf["G_W_K"]/ref["G_W_K"]-1,
            "full_reduced_vs_direct_solid_max_difference":float(np.max(abs(full.solid-direct[:,full.nf:]))),
            "half":rh,"full":rf}


def tolerance_sensitivity():
    rows=[]
    failures=[{"rtol":1e-13,"atol":1e-15,"mesh":[12,36,120],"speed":10.0,
               "status":"GMRES iteration limit", "message":"GMRES did not converge, info=10, last callback residual=1.2712526137862068e-32",
               "interpretation":"An unattainable true-residual tolerance is suspected; a tiny preconditioned callback does not establish convergence. The failure is retained, not accepted as a solution."}]
    for rtol,atol in ((1e-10,1e-12),(1e-11,1e-13),(1e-12,1e-14)):
        m=new.AxialModel(12,36,120,10.0,rtol=rtol,atol=atol)
        try:
            rows.append(m.solve(include_samples=False))
        except new.ResourceLimit as error:
            failures.append({"rtol":rtol,"atol":atol,"message":str(error)})
    return {"runs":rows,"failures":failures,"absolute_delta_change":abs(rows[-1]["paired_relative_conductance_change"]-rows[0]["paired_relative_conductance_change"]),
            "relative_G_change":rows[-1]["G_W_K"]/rows[0]["G_W_K"]-1}


def package_identity():
    expected=json.loads((HERE/"independent_reference_self_checks.json").read_text())["frozen_package_file_hashes"]
    changed=[p for p,digest in expected.items() if sha(ind.REPO/p)!=digest]
    return {"checked_source_and_display_files":len(expected),"changed_files":changed}


if __name__=="__main__":
    result={"status":"reduced solver independent checks", "code_sha256":sha(HERE.parent/"axial_fin.py"),
            "plan_sha256":sha(HERE.parent/"PLAN.md"),"review_script_sha256":sha(__file__),
            "direct_reference_script_sha256":sha(HERE/"independent_axial_review.py"),
            "direct_comparisons":comparison_cases(),"symmetry":full_mirror(),
            "tolerance_sensitivity":tolerance_sensitivity(),"accepted_package_identity":package_identity()}
    text=json.dumps(result,indent=2,allow_nan=False)+"\n"
    assert len(text.encode())<100000
    out=HERE/"reduced_solver_comparison.json"
    out.write_text(text)
    print(json.dumps({"path":str(out),"bytes":len(text.encode()),
                      "max_relative_G_error":max(abs(r["relative_G_error"]) for r in result["direct_comparisons"]),
                      "max_field_error":max(r["maximum_all_theta_absolute_difference"] for r in result["direct_comparisons"]),
                      "tolerance_delta_change":result["tolerance_sensitivity"]["absolute_delta_change"],
                      "package":result["accepted_package_identity"]}))
