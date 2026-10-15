import sys
import types
import unittest
from unittest.mock import patch

# Windows에서는 Linux 잠금 모듈만 대역으로 두고 순수 manifest 검사를 시험한다.
with patch.dict(sys.modules, {'fcntl': types.ModuleType('fcntl')}):
    from hf_nf4_contract_queue import validate_dependencies, unfinished_jobs


class DependencyGuard(unittest.TestCase):
    def test_missing_smoke_rejected(self):
        with self.assertRaises(ValueError):
            validate_dependencies([{'id': 'main', 'dependency': 'absent_smoke'}])

    def test_dependency_after_main_rejected(self):
        with self.assertRaises(ValueError):
            validate_dependencies([{'id': 'main', 'dependency': 'smoke'}, {'id': 'smoke'}])

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            validate_dependencies([{'id': 'smoke'}, {'id': 'smoke'}])

    def test_ordered_dependencies_and_unexecuted_denominator(self):
        jobs = [{'id': 'smoke'}, {'id': 'main', 'dependency': 'smoke'}]
        validate_dependencies(jobs)
        self.assertEqual(unfinished_jobs(jobs, {'smoke': {'status': 'failed'}}), ['main'])
        self.assertEqual(unfinished_jobs(jobs, {'smoke': {'status': 'completed'},
                        'main': {'status': 'completed_with_errors'}}), [])


if __name__ == '__main__':
    unittest.main()
