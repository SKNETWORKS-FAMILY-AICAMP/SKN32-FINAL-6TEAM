import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('soak',Path(__file__).with_name('app_schema_soak_20261011.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class SoakGate(unittest.TestCase):
 def test_partial_or_failed_predecessor_cannot_start(self):
  for rows in [[dict(parsed=True,correct=True)]*47,[dict(parsed=True,correct=True)]*47+[dict(parsed=False,correct=False)]]:
   with self.assertRaises(ValueError):module.gate(rows)
 def test_exact_successful_predecessor_is_required(self):
  module.gate([dict(parsed=True,correct=True)]*48)
 def test_failures_remain_in_denominator(self):
  r=module.aggregate([dict(correct=True),dict(correct=False,error='timeout'),dict(correct=False)])
  self.assertEqual((r['attempted'],r['correct'],r['failed'],r['transport_errors']),(3,1,2,1))
if __name__=='__main__':unittest.main()
