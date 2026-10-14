import tempfile
from pathlib import Path
import unittest

import yaml
from prepare_guardrails import prepare


class ArmSourceBudgetTests(unittest.TestCase):
    def test_rebuild_uses_new_source_and_backs_up_existing_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/'source.yaml'; target=root/'ops'/'arm.yaml'
            original={'travel':{'source_budget_shared':False,'source_budget_on_db_error':'allow',
                               'kakao_budget':{'kakao_local_keyword':{'day':1000,'month':31000}}},
                      'unrelated_feature':{'revision':1}}
            source.write_text(yaml.safe_dump(original),encoding='utf-8')
            prepare(source,target)
            first=target.read_bytes()
            config=yaml.safe_load(first)
            self.assertEqual(config['travel']['kakao_budget']['kakao_local_keyword'],{'day':100,'month':3000})
            self.assertEqual(config['travel']['source_budget_on_db_error'],'refuse')
            self.assertTrue(config['travel']['source_budget_shared'])
            original['unrelated_feature']['revision']=2
            source.write_text(yaml.safe_dump(original),encoding='utf-8')
            prepare(source,target)
            self.assertEqual(yaml.safe_load(target.read_text())['unrelated_feature']['revision'],2)
            backups=list((target.parent/'_backup').glob('*/arm.yaml'))
            self.assertEqual(len(backups),1)
            self.assertEqual(backups[0].read_bytes(),first)


if __name__=='__main__':
    unittest.main()
