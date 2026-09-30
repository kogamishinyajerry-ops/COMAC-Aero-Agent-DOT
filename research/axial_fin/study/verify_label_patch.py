#!/usr/bin/env python3
"""Prove the post-run correction changes only the full/half sample notice."""
import ast,difflib,json
from axial_fin import AxialModel,HERE,sha
class NormalizeNotice(ast.NodeTransformer):
 def visit_Dict(self,node):
  self.generic_visit(node)
  for i,k in enumerate(node.keys):
   if isinstance(k,ast.Constant) and k.value=='central_channel_notice':node.values[i]=ast.Constant(value='OWNERSHIP_NOTICE_REDACTED_FOR_AST_COMPARISON')
  return node
old=HERE/'axial_fin_numerical_run.py';new=HERE/'axial_fin.py'
equal=ast.dump(NormalizeNotice().visit(ast.parse(old.read_text())))==ast.dump(NormalizeNotice().visit(ast.parse(new.read_text())))
rows=[]
for full in [False,True]:
 m=AxialModel(4,12,20,4.,1.,full=full);r=m.solve(True);rows.append({'full_array':full,'notice':r['samples']['central_channel_notice'],'G_W_K':r['G_W_K']})
checks={'all_AST_except_notice_unchanged':equal,'half_domain_notice_correct':'half a physical interior' in rows[0]['notice'],'full_domain_notice_correct':'right-side full clearance' in rows[1]['notice'],'symmetry_unchanged':abs(rows[0]['G_W_K']/rows[1]['G_W_K']-1)<1e-8}
out={'status':'passed' if all(checks.values()) else 'failed','checks':checks,'numerical_run_solver_sha256':sha(old),'current_solver_sha256':sha(new),'scope':'Display-label-only correction after completed numerical refinement; no numerical operation, equation, grid, parameter or tolerance changed','rows':rows,'reviewable_diff':list(difflib.unified_diff(old.read_text().splitlines(),new.read_text().splitlines(),fromfile=old.name,tofile=new.name)),'physical_validation_pass':None}
(HERE/'label_patch_verification.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['checks']);assert all(checks.values())
