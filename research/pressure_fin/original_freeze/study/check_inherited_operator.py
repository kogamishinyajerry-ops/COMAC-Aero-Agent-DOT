#!/usr/bin/env python3
"""Read-only structural regression against the inherited thermal model."""
from pressure_fin import *
new=PressureFin(nx=12,ny=36)
old=base.Model(nx=12,ny=36,full=True)
delta=new.K-old.K
out={'status':'passed' if (delta.nnz==0 or max(abs(delta.data))<1e-13) and np.array_equal(new.bound,old.bound) else 'failed','scope':'thermal-operator equivalence at inherited geometry; hydraulic mass matrix is deliberately different; no experimental targets read','maximum_thermal_matrix_difference':float(max(abs(delta.data))) if delta.nnz else 0.,'maximum_base_boundary_difference':float(max(abs(new.bound-old.bound))),'new_code_sha256':digest(HERE/'pressure_fin.py'),'original_code_sha256':digest(SOURCE),'check_code_sha256':digest(__file__)}
save('inherited_operator_check.json',out)
print(json.dumps(out,indent=2))
