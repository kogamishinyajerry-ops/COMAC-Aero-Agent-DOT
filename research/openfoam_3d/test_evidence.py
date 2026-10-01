"""Run python -m unittest discover -s research/openfoam_3d -p 'test_*.py'."""
import copy,math,unittest
from pathlib import Path
from audit_package import load,validate_report

class TestEvidence(unittest.TestCase):
 def setUp(self):self.r=load(Path(__file__).parent/'evidence/report.json')
 def test_honest_status_and_balances(self):self.assertTrue(validate_report(self.r))
 def test_reject_false_overall_pass(self):
  r=copy.deepcopy(self.r);r['initial_all_passed']=not r['initial_all_passed']
  with self.assertRaises(AssertionError):validate_report(r)
 def test_reject_hidden_pressure_failure(self):
  r=copy.deepcopy(self.r);r['initial_gates']['medium_to_fine_pressure_gradient_change']=True;r['initial_all_passed']=all(r['initial_gates'].values())
  with self.assertRaises(AssertionError):validate_report(r)
 def test_reject_changed_energy_normalization(self):
  r=copy.deepcopy(self.r);r['meshes'][0]['relative_energy_imbalance']+=1e-5
  with self.assertRaises(AssertionError):validate_report(r)
 def test_analytic_pressure_independently_recomputed(self):
  mean=(1-96/math.pi**5*sum(math.tanh(n*math.pi)/n**5 for n in range(1,20000,2)))/12
  exact=1.8e-5*3/(.002**2*mean)
  self.assertAlmostEqual(exact,236.1361027759,places=7)
  for r in self.r['meshes']:self.assertAlmostEqual(r['nominal_mean_analytic_pressure_gradient_Pa_m'],exact,places=8)
 def test_low_speed_sentinel_has_material_axial_diffusion(self):
  alpha=.026/(1.2*1005);lam=(math.pi/.004)**2+(math.pi/.002)**2;u=.05
  r=-2*alpha*lam/(u+math.sqrt(u*u+4*alpha*alpha*lam))
  self.assertLess(abs(alpha*r*r-u*r-alpha*lam),1e-10)
  self.assertGreater(r*r/lam,.25)
 def test_three_dimensional_cell_counts(self):
  for r in self.r['meshes']:self.assertEqual(r['cells'],math.prod(r['grid']));self.assertTrue(r['three_dimensions'])
 def test_no_physical_or_conjugate_claim(self):
  self.assertIsNone(self.r['physical_experimental_validation']);self.assertEqual(self.r['conjugate_solid_fluid'],'not_solved')
if __name__=='__main__':unittest.main()
