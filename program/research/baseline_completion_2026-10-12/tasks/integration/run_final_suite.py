"""새 전용 DB에서 현재 manifest의 한 전체 묶음을 선택해 실행한다."""
from pathlib import Path
import json, runpy, sys
import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
CS = ROOT/'final_project_cs'
suite = sys.argv[1]
assert suite in ('common','travel')
sys.path.insert(0,str(CS))
from scripts.run_test_suite import SuiteSelector
original = pytest.main

def run(args, **kwargs):
    run_dir = Path(next(x.split('=',1)[1] for x in args if x.startswith('--junitxml='))).parent
    manifest = json.loads((CS/'tests/test-suites.json').read_text(encoding='utf-8'))
    class Progress:
        def pytest_runtest_logreport(self,report):
            row = dict(nodeid=report.nodeid,when=report.when,outcome=report.outcome,seconds=report.duration)
            if report.failed: row['failure'] = report.longreprtext
            with (run_dir/'progress.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(row,ensure_ascii=False)+'\n')
    # 合成 조직만 준비하며 지식·고객·요식 업무 자료는 복사하지 않는다.
    from app.infrastructure.db.session import get_connection
    with get_connection() as conn:
        conn.execute("INSERT INTO tenants(tenant_id,name) VALUES('demo','Isolated synthetic travel tenant') ON CONFLICT DO NOTHING")
    return original(args,plugins=[SuiteSelector(suite,manifest,str(run_dir/'collection.json')),Progress()],**kwargs)

pytest.main = run
sys.argv = [str(HERE/'run_isolated_integration.py'),'-m','not live',*sys.argv[2:]]
runpy.run_path(str(HERE/'run_isolated_integration.py'),run_name='__main__')
