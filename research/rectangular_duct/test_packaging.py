#!/usr/bin/env python3
"""Guard tests and supported-grid identity against preserved precomparison code."""
import ast, importlib.util, json, tempfile
from pathlib import Path
from compare_experiment import audit_source_pdf
import numpy as np
from rectangular_graetz import CODE_DIR, ORIGINAL_DIR, ROOT, Model, dirichlet_1d, sha, save
spec=importlib.util.spec_from_file_location('preserved_original_solver',ORIGINAL_DIR/'rectangular_graetz.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
checks=[]
for n in (-1,0,1):
    for name,call in [('dirichlet_1d',lambda:dirichlet_1d(n,1.0)),('Model',lambda:Model(n))]:
        try:call()
        except ValueError as e:
            assert 'at least two cells' in str(e)
            checks.append({'target':name,'short_side_cells':n,'correctly_rejected':True})
        else:raise AssertionError(f'{name} did not reject{n}')
identity=[]
for aspect in (1.,2.,4.):
    for ny in (2,4,16,32):
        a,b=old.Model(ny,aspect),Model(ny,aspect)
        assert np.array_equal(a.K.toarray(),b.K.toarray()) if ny<=4 else (a.K!=b.K).nnz==0
        assert np.array_equal(a.raw,b.raw) and np.array_equal(a.v,b.v)
        identity.append({'aspect':aspect,'ny':ny,'operators_and_velocity_bitwise_equal':True})
for ny in (4,16):
    a,b=old.Model(ny).march(steps=32,last=.032),Model(ny).march(steps=32,last=.032)
    assert a['curve']==b['curve'] and a['checks']==b['checks']
# Prove that the entire accepted marching method's syntax is unchanged.
def method(path,cls,name):
    root=ast.parse(path.read_text());node=next(x for x in root.body if isinstance(x,ast.ClassDef) and x.name==cls)
    return ast.dump(next(x for x in node.body if isinstance(x,ast.FunctionDef) and x.name==name),include_attributes=False)
assert method(CODE_DIR/'rectangular_graetz.py','Model','march')==method(ORIGINAL_DIR/'rectangular_graetz.py','Model','march')
with tempfile.TemporaryDirectory(dir=ROOT) as temp:
    toy=Path(temp)/'audit-test-bytes';toy.write_bytes(b'local test bytes, not a source document')
    source={'source':{'pdf_sha256':sha(toy)}}
    assert audit_source_pdf(source,None)['status']=='not_requested'
    assert audit_source_pdf(source,toy)['status']=='passed'
    toy.write_bytes(b'different local bytes')
    try:audit_source_pdf(source,toy)
    except ValueError:pass
    else:raise AssertionError('Mismatched optional source bytes were accepted')
result={'phase':'postcomparison_packaging_tests','original_solver_sha256':sha(ORIGINAL_DIR/'rectangular_graetz.py'),'packaged_solver_sha256':sha(CODE_DIR/'rectangular_graetz.py'),
        'one_cell_guard_tests':checks,'supported_grid_identity_tests':identity,
        'supported_grid_short_marches_bitwise_identical':True,'march_method_ast_identical':True,'optional_source_audit_none_match_mismatch_tests_pass':True,
        'scope':'Only the unsupported one-cell case is newly rejected; accepted equations, meshes and tolerances are unchanged.'}
save(ROOT/'packaging_tests.json',result)
print('Guard tests pass; supported operators, velocity and short marches are bitwise identical')
