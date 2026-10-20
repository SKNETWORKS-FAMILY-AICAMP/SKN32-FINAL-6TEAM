"""Keep current measurements distinct from v1 and from test-runner failures."""
from pathlib import Path
from collections import Counter
import datetime,hashlib,json,xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent
WORK=HERE.parents[2]
def xml(name):
 root=ET.parse(HERE/'checks'/name).getroot();s=root.find('testsuite') if root.tag=='testsuites' else root
 rows=s.findall('testcase');counts=Counter();problems=[]
 for c in rows:
  state='error' if c.find('error') is not None else 'failed' if c.find('failure') is not None else 'skipped' if c.find('skipped') is not None else 'passed'
  counts[state]+=1
  if state in {'error','failed'}:problems.append(dict(case=c.get('classname','')+'::'+c.get('name',''),category='Team의 직접 의존 검사 실패' if 'import' in c.get('name','') else '추가 검토 필요'))
 return dict(counts={k:counts[k] for k in ['passed','failed','error','skipped']},total=len(rows),duration_seconds=float(s.get('time','0')),problems=problems)
base=xml('base-backend-v2.xml');changes=xml('changes-backend-v2.xml')
front_raw=json.loads((HERE/'checks/frontend-v2.json').read_text(encoding='utf-8'))
frontend=dict(passed=front_raw['numPassedTests'],failed=front_raw['numFailedTests'],total=front_raw['numTotalTests'],success=front_raw['success'],files=[dict(path=Path(s['name']).relative_to(WORK).as_posix(),status=s['status'],tests=len(s.get('assertionResults',[]))) for s in front_raw['testResults']])
combined={k:base['counts'][k]+changes['counts'][k] for k in ['passed','failed','error','skipped']}
train=WORK/'datasets/core/pointing/trainset/train_oos2/train_oos2.jsonl'
training=dict(path=train.relative_to(WORK).as_posix(),rows=sum(bool(x.strip()) for x in train.read_text(encoding='utf-8').splitlines()),sha256=hashlib.sha256(train.read_bytes()).hexdigest())
summary=dict(date_kst='2026-10-10',baseline_id='triPilot-BL-2026-10-10-v2',selected_tests=combined,selected_total=sum(combined.values()),base_backend=base,changed_backend=changes,frontend=frontend,training_data=training,
 dataset_check=dict(exit_code=0,golden=72,holdout=24,label_by={'claude-draft':96},meaning='형식·라벨 검사. 사람 정답 검수·모델 정확도·독립성 검증 아님'),
 prior_result=dict(file='checks/project-checks.json',meaning='v1의 235/238·실패2·DB오류1. 이번 판의 실행으로 합산하지 않음'),
 runner_retries=[dict(scope='새 백엔드 단위 시험',initial='76통과·임시 폴더 생성 오류5',correction='쓰기 허용된 새 basetemp 경로를 지정해 81/81 재실행 통과'),dict(scope='웹 단위 시험',initial='28통과·2개 파일 임시 SSR 파일 읽기 오류',correction='단일 threads 작업자로 6파일 전체 재실행, 52/52 통과')],
 excluded=['v1의 개인정보 DB 시험은 쇼핑몰 분류 fixture를 사용해 현행 여행 평가에서 제외. 이번 DB/API 개인정보 검증은 미실행','전체 MVP 18항목·운영 DB·외부 API·GPU 학습·실제 제품 화면은 이번 작업에서 재검증하지 않음'],
 commands=[dict(cwd='final_project_cs',command='python -m scripts.verify_travel_eval_datasets'),dict(cwd='final_project_cs',command='python -m pytest tests/contract/test_team_contract.py tests/contract/test_core_isolation.py tests/contract/test_team_tool_discipline.py tests/architecture/test_basement_is_domain_free.py -q -m "not live"'),dict(cwd='final_project_cs',command='python -m pytest tests/unit/test_service_improvement.py tests/unit/travel/mobility/test_turn_policy_content_reload_v1.py -q --basetemp=<새로 만든 쓰기 가능한 시험 폴더>'),dict(cwd='final_project_cs/frontend/apps/web',command='node node_modules/vitest/vitest.mjs run src/features/consent/consent-sync.test.ts src/features/consent/terms-content.test.ts src/features/consent/terms-text.test.ts src/features/map/edge-chips.test.ts src/features/map/providers/pin.test.ts src/features/plan-check/use-server-review-undo.test.ts --pool=threads --maxWorkers=1 --fileParallelism=false')],
 product_release='not_verified',production_checks='실서버 확인(서버 응답): 안 했음. x600 서버의 cs 프로젝트 서버·외부 API·GPU 모델 미확인')
target=HERE/'checks/project-checks-v2.json'
if target.exists():raise RuntimeError('Preserve the prior measurement before replacing it')
target.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k in ['selected_tests','selected_total','frontend','base_backend','changed_backend']},ensure_ascii=False,indent=2))
