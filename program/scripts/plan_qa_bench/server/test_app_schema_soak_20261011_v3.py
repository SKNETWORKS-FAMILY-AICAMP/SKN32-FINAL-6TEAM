import importlib.util,json,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('v3',Path(__file__).with_name('app_schema_soak_20261011_v3.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class BudgetGate(unittest.TestCase):
 def rows(self):return [dict(case=str(c),history='h',repeat=n,budget=b,parsed=True,correct=True) for c in range(12) for n in [1,2] for b in [400,800]]
 def test_budget_profile_separate_from_failed_other_profile(self):
  r=self.rows();r[0]['correct']=False;self.assertEqual(len(m.gate(r,800)),24)
  with self.assertRaises(ValueError):m.gate(r,400)
 def test_missing_duplicate_or_failed_cases_block(self):
  rows=self.rows()
  bad=rows.copy();bad[-1]=bad[-3]
  fail=[dict(x) for x in rows];fail[-1]['correct']=False
  for r in [rows[:-1],bad,fail]:
   with self.assertRaises(ValueError):m.gate(r,800)
 def test_saved_originals_800_profiles_pass_without_relabeling_400(self):
  root=Path(__file__).resolve().parents[4];raw=json.loads((root/'program/scripts/plan_qa_bench/results/heartbeat_20261011_0800/A_schema_raw_observation_complete.json').read_text(encoding='utf8'))
  for ident in ['saluki_original_d3_a1_appschema_v1','e4bbase_d3_appschema_v1','e4bqat_original_d3_appschema_v1']:
   job=next(x for x in raw if x['id']==ident);rows=[json.loads(l) for l in job['files']['d_test_'+ident+'.jsonl'].splitlines()];self.assertEqual(len(m.gate(rows,800)),24)
if __name__=='__main__':unittest.main()
