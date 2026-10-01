"""Focused algebra, bookkeeping, and evidence checks for the directional study."""
import json, unittest
from pathlib import Path
import numpy as np
import study
class TestDirectional(unittest.TestCase):
 def test_discrete_poisson_residual(self):
  for ny,nz in [(16,8),(32,16),(64,32)]:
   u,g,r=study.discrete_profile(ny,nz)
   self.assertLess(r,1e-10);self.assertAlmostEqual(float(u.mean()),3.,places=13)
   self.assertTrue(np.all(u>0));self.assertTrue(np.allclose(u,u[::-1,:]));self.assertTrue(np.allclose(u,u[:,::-1]))
 def test_discrete_convergence(self):
  exact=study.s.MU*study.s.UM/(study.s.H**2*study.s.exact_mean())
  errs=[abs(study.discrete_profile(n,n//2)[1]/exact-1) for n in [16,32,64]]
  self.assertGreater(errs[0]/errs[1],3.7);self.assertGreater(errs[1]/errs[2],3.7)
 def test_exact_cell_average_mean(self):
  for ny,nz in [(16,8),(32,16),(64,32)]:
   v=study.continuum_profile(ny,nz,True)
   self.assertLess(abs(float(v.mean())-3),2e-9)
 def test_exact_cell_average_matches_gauss(self):
  ny,nz=16,8;v=study.continuum_profile(ny,nz,True)
  t,w=np.polynomial.legendre.leggauss(12)
  iy,iz=7,3;yy=(iy+.5+t[:,None]/2)*study.s.W/ny;zz=(iz+.5+t[None,:]/2)*study.s.H/nz
  ref=study.s.UM*np.sum(study.s.velocity_shape(*np.broadcast_arrays(yy,zz))*w[:,None]*w[None,:])/4
  self.assertAlmostEqual(v[iy,iz],ref,places=11)
 def test_frozen_original_gate(self):
  p=study.PLAN['immutable_original_pressure_grid_gate']
  self.assertGreater(p['relative_change'],p['maximum']);self.assertTrue(p['status'].startswith('FAILED'))
 def test_primary_ladder_is_equal_ratio(self):
  d={r['name']:r['grid'] for r in study.PLAN['new_primary_cases']}
  self.assertEqual(d['axial_coarse'],[40,32,16]);self.assertEqual(d['axial_fine'],[160,32,16])
  self.assertEqual(d['transverse_coarse'],[80,16,8]);self.assertEqual(d['transverse_fine'],[80,64,32]);self.assertEqual(d['transverse_extra_fine'],[80,128,64])
 def test_supplement_not_primary(self):
  self.assertEqual(len(study.PLAN['new_supplementary_cases']),1)
  self.assertNotIn('discrete_developed_inlet',[r['name'] for r in study.PLAN['new_primary_cases']])
if __name__=='__main__':unittest.main()
