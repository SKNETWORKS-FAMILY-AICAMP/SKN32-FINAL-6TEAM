from pathlib import Path
from collections import Counter
import datetime, hashlib, json, shutil, xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parent
WORKSPACE=ROOT.parents[2]
path=ROOT/'checks/selected-offline.xml'
root=ET.parse(path).getroot()
suite=root.find('testsuite') if root.tag=='testsuites' else root
cases=suite.findall('testcase')
counts=Counter('error' if c.find('error') is not None else 'failed' if c.find('failure') is not None else 'skipped' if c.find('skipped') is not None else 'passed' for c in cases)
failures=[]
for case in cases:
    problem=case.find('failure')
    if problem is None: problem=case.find('error')
    if problem is not None:
        # Keep classification and node identifiers; omit environment values and tracebacks.
        failures.append({'case':case.get('classname','')+'::'+case.get('name',''),
                         'type':problem.get('type',''),
                         'category':'로컬 개발 DB 접속 오류' if 'OperationalError' in (problem.text or '') else 'Team의 금지된 직접 import 검사 실패'})
train=WORKSPACE/'datasets/core/pointing/trainset/train_oos2/train_oos2.jsonl'
training={'path':'datasets/core/pointing/trainset/train_oos2/train_oos2.jsonl','available':train.exists()}
if train.exists():
    rows=[json.loads(s) for s in train.read_text(encoding='utf-8').splitlines() if s.strip()]
    training.update(rows=len(rows),sha256=hashlib.sha256(train.read_bytes()).hexdigest(),field_names=sorted(rows[0]))
summary={'date_kst':'2026-10-10','selected_tests':dict(counts),'selected_total':len(cases),
         'duration_seconds':float(suite.get('time','0')),'failures':failures,
         'dataset_check':{'exit_code':0,'golden':72,'holdout':24,'label_by':{'claude-draft':96},'meaning':'형식·라벨 어휘·정확 중복 검사, 정확도 또는 사람 정답 검수 아님'},
         'broad_suite':{'status':'interrupted','reason':'실패·DB 연결 오류를 관측한 후 범위를 줄인 검사로 전환. 전체 통과율은 계산하지 않음'},
         'training_data':training,
         'commands':['python -m scripts.verify_travel_eval_datasets','python -m pytest tests/contract/test_team_contract.py tests/contract/test_core_isolation.py tests/contract/test_team_tool_discipline.py tests/architecture/test_basement_is_domain_free.py tests/security/test_pii_redaction_runtime.py -q -m "not live"'],
         'product_release':'not_verified','production_checks':'실서버 확인(서버 응답): 안 했음. 원격 제품·외부 API·실제 모델 정확도는 재측정하지 않음'}
out=ROOT/'checks/project-checks.json'
out.parent.mkdir(exist_ok=True)
if out.exists():
    backup=ROOT/'_backup'/datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S_checks')
    backup.mkdir(parents=True,exist_ok=True);shutil.copy2(out,backup/out.name)
out.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
