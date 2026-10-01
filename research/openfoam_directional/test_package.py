import unittest
import package_results as p
class TestOrderDiagnostics(unittest.TestCase):
 def make(self,vals):
  return [dict(name=str(i),pressure_gradient_Pa_m=v,continuum_pressure_gradient_Pa_m=100.) for i,v in enumerate(vals)]
 def test_positive_second_order(self):
  q=p.order_three(self.make([96,99,99.75]));self.assertTrue(q['eligible']);self.assertAlmostEqual(q['observed_order'],2);self.assertAlmostEqual(q['conditional_richardson_gradient_Pa_m'],100)
 def test_expanding_differences_rejected(self):
  self.assertFalse(p.order_three(self.make([96,97,99]))['eligible'])
 def test_nonmonotone_rejected(self):
  self.assertFalse(p.order_three(self.make([96,99,98]))['eligible'])
 def test_missing_case_excluded(self):
  self.assertFalse(p.order_three([None,None,None])['eligible'])
 def test_noise_rejected(self):
  self.assertFalse(p.order_three(self.make([100-4e-9,100-1e-9,100-.25e-9]))['eligible'])
if __name__=='__main__':unittest.main()
