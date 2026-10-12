"""Gemma12B 원본 혼합 문장 완료를 검증하고 새 리포트와 대기열 기록에 연결한다."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'program/scripts/plan_qa_bench/results/gpu_backlog_20261008'
DAILY = ROOT / 'program/research/daily_rag_slm'
REPORT = 'final_project_cs/wiki/records/reports/2026-10-08_1218_gemma12b-original-mx-completion.md'
REMOTE_SHA = '1c0963a3adc6aa7f24d89c8b38434b8aaf69672556b8d303ca82d8ed2e1d5729'
sys.stdout.reconfigure(encoding='utf-8')
assert not (ROOT / REPORT).exists(), 'Already recorded'
folder = BASE / 'g12bbase_mx'
r = json.loads((folder / 'mx_counts.json').read_text(encoding='utf-8'))
raw = folder / 'd_test_mx_backlog_g12bbase.jsonl'
gold_path = ROOT / 'datasets/travel/mx_testset/mx_main_prompts.json'
gold = json.loads(gold_path.read_text(encoding='utf-8'))
rows = [json.loads(line) for line in raw.read_text(encoding='utf-8').splitlines()]
answers = {x['i']: x for x in rows}
assert r['saved'] == r['expected'] == len(rows) == len(answers) == len(gold) == 4014
assert set(answers) == {x['i'] for x in gold}
assert r['missing'] == r['failed_or_unparsed'] == 0 and r['our_training'] is False
assert hashlib.sha256(raw.read_bytes()).hexdigest() == r['answer_sha256'] == REMOTE_SHA
assert hashlib.sha256(gold_path.read_bytes()).hexdigest() == r['gold_sha256'] == r['execution']['prompt_sha256']
assert all(answers[x['i']]['gold'] == x['gold'] and answers[x['i']]['type'] == x['type'] for x in gold)
for kind in ['mixed', 'control']:
    for label,positive in [('request',True),('no_request',False)]:
        selected = [x for x in gold if x['kind'] == kind and (x['gold'] is not None) == positive]
        valid = lambda row: bool(row.get('parsed')) and not row.get('error')
        st = r['counts'][kind][label]
        assert len(selected) == st['total']
        assert sum(valid(answers[x['i']]) and answers[x['i']]['pick'] == x['gold'] for x in selected) == st['correct']
        assert sum(valid(answers[x['i']]) and x['gold'] is None and answers[x['i']]['pick'] is not None for x in selected) == st['false_pick']
assert r['counts']['mixed']['request']['correct'] == 993
assert r['counts']['mixed']['no_request']['false_pick'] == 201
assert r['aggregate_gates_passed'] == 3
with (folder / 'verification.json').open('x',encoding='utf-8') as f:
    json.dump({'remote_answer_sha256': REMOTE_SHA, 'answer_remote_hash_match': True, 'fixed_prompt_hash_match': True,
        'exact_id_gold_type_match': True, 'independent_direct_recount': True, 'saved':4014,'missing':0,
        'failed_or_unparsed':0,'model_repetitions':1}, f, indent=2)

stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S') + '_gemma12b_mx_completion'
backups = []
def save(rel, text):
    p = ROOT / rel
    if p.exists():
        b = p.parent / '_backup' / stamp / p.name
        b.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,b)
        backups.append(b.relative_to(ROOT).as_posix())
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(text,encoding='utf-8')

observations = {}
for machine in ['A','B']:
    observations[machine] = (json.loads((BASE / f'{machine}_snapshot_1216.json').read_text(encoding='utf-8')),
                             json.loads((BASE / f'{machine}_conditions_1216.json').read_text(encoding='utf-8')))
a,ac = observations['A']; b,bc = observations['B']
assert a['state']['jobs']['g12bbase_mx']['status'] == 'completed'
assert a['state']['jobs']['g12bbase_d']['status'] == 'running' and len(ac['ready']) >= 3
assert str(ac['worker_pid']) in a['processes']
assert 'qlora_train2.py /root/hf_models/winnow-e4b-hf' in b['processes']
state = json.loads((DAILY / 'gpu_backlog_2026-10-08.json').read_text(encoding='utf-8'))
for machine,(snap,cond) in observations.items():
    state['gpu_' + machine].update({'snapshot': (BASE / f'{machine}_snapshot_1216.json').relative_to(ROOT).as_posix(),
        'conditions_snapshot': (BASE / f'{machine}_conditions_1216.json').relative_to(ROOT).as_posix(),
        'observed_at_utc':snap['observed_at_utc'],'instant_gpu_memory_and_utilization':snap['gpu_snapshot'],
        'root_available_bytes':cond['root_space']['available_bytes']})
completed = [x for x in a['state']['jobs'].values() if x['status'].startswith('completed')]
state['gpu_A'].update({'state':a['state'],'answers_saved_at_snapshot':a['answers'],'jobs_completed':len(completed),
    'jobs_completed_with_errors':sum(x['status']=='completed_with_errors' for x in completed),
    'jobs_running':1,'jobs_ready_waiting':len(ac['ready']),'completed_g12bbase_mx_archived':True})
state['recorded_at'] = datetime.now().isoformat()
state['latest_routine_observation'] = {'new_completed_jobs':1,'new_failed_jobs':0,'new_failed_or_unparsed_answers':0,
    'queue_refill':False,'worker_restart':False,'recorded_at':datetime.now().isoformat(),
    'reason':f'Gemma12B original MX archived; {len(ac["ready"])} prepared A evaluations remain. B has2 existing-input recipes and2 recipes requiring automatic base downloads; recheck download space immediately before each.'}
save('program/research/daily_rag_slm/gpu_backlog_2026-10-08.json',json.dumps(state,ensure_ascii=False,indent=2)+'\n')
day = json.loads((DAILY / '2026-10-08.json').read_text(encoding='utf-8'))
assert not any(x.get('model') == r['model'] and x.get('suite') == 'MX' for x in day['new_completed_evaluations'])
day['new_completed_evaluations'].append({'model':r['model'],'our_training':False,'publisher_training':'Instruct release','suite':'MX / user E',
    'saved':4014,'expected':4014,'missing':0,'failed_or_unparsed':0,'mixed_request_correct':993,'mixed_request_total':1033,
    'mixed_false_pick':201,'mixed_no_request_total':974,'request_loss_pp':r['paired']['request']['loss_pp'],
    'aggregate_gates_passed':3,'aggregate_gates_total':4,'natural_request_correct':92,'natural_request_total':93,
    'natural_false_pick':37,'natural_no_request_total':146,'repetitions':1,'full_ranking':False,'report':REPORT})
save('program/research/daily_rag_slm/2026-10-08.json',json.dumps(day,ensure_ascii=False,indent=2)+'\n')
save('program/research/daily_rag_slm/2026-10-08.md',(DAILY / '2026-10-08.md').read_text(encoding='utf-8') + f'''
## 12시16분 확인 — Gemma12B 배포 원본 E 혼합 문장 평가 완료

우리 여행 자료로 추가 학습하지 않은 Gemma-4-12B-it Q4_K_M의 답안4,014/4,014개를 보관·검증했다. 혼합 정상 요청993/1,033=96.13%, 기존 항목을 고르면 안 되는 문장의 오지목201/974=20.64%, 사전 합산3/4 통과다. 정상 요청 대조1,010/1,033에서 혼합993/1,033으로 손실1.65%p, 일정별95% 구간0.87~2.38%p다. 감상·잡담 MX4 오지목118/121이므로 정상 요청 점수만으로 채택하지 않는다.

자연 혼합239개는 정상92/93·오지목37/146이다. 코드 이어 붙인1,768개와 분리했다. 사람 정답 검수 전·기존 개발/회귀 자료·모델 실행1회이며 독립 보류·반복·전체 원본 비교군 상위권 판정은 대기다. 미완료·호출/해석 실패0, GPU 서버 A 원본 해시·실행 입력 해시·전체ID와 정답/유형 및 독립 직접 계수가 같았다.

GPU 서버 A는 다음Gemma12B D평가를 실행하고 준비된7개가 대기한다. GPU 서버 B는 Jev 계열 모델 중 Winnow-E4B(우리 여행 자료로 학습)의 본 학습을 계속하며 뒤4개 레시피 중2개는 기존 입력,2개는 기반 자동 다운로드가 필요하다. 다음 다운로드 직전 공간을 다시 확인한다. 중복 실행·중단·새 결제·모델 삭제는 하지 않았다.

[완료·검증 리포트](../../../{REPORT}).
''')
rel = 'final_project_cs/wiki/quality/slm-model-evaluation.md'
save(rel,(ROOT / rel).read_text(encoding='utf-8') + '\n`[실측 2026-10-08]` Gemma12B 배포 원본의 E 혼합 문장 답안을 회수했다. 정상 요청 기준은 통과했으나 요청 없음 오지목 기준은 실패했으므로 제품 채택은 보류한다. [완료·유형별 실패·검증 근거](../records/reports/2026-10-08_1218_gemma12b-original-mx-completion.md).\n')
rel = 'final_project_cs/wiki/log.md'
save(rel,(ROOT / rel).read_text(encoding='utf-8') + '\n## 2026-10-08 — Gemma12B 원본 E 혼합 문장 평가 완료\n\n정상 요청 정답과 감상·잡담의 오지목을 함께 집계했다. [완료·검증 리포트](records/reports/2026-10-08_1218_gemma12b-original-mx-completion.md).\n')

report = '''# Gemma12B 배포 원본 E 혼합 문장 평가 완료 — 2026-10-08

우리 여행 자료로 추가 학습하지 않은 Gemma-4-12B-it Q4_K_M의 혼합 문장 평가를 보관했다. 정상 요청을 잘 짚었으나 항목을 고르면 안 되는 감상·잡담도 자주 지목해 제품 채택 기준 전체를 통과하지 못했다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 혼합·대조 답안 보관·문항 대조 | 완료 | 4,014/4,014 = 100% |
| 혼합 정상 요청 정답 | 실측 | 993/1,033 = 96.13% |
| 혼합 요청 없음 오지목 | 실측 | 201/974 = 20.64% |
| 사전 합산 기준 | 일부 통과 | 3/4 = 75% |

## 범위와 결과

사용자 명칭 E는 실행 기록의 MX 혼합 문장 시험이다. 혼합2,007개(정상1,033·항목 선택 없음974)와 같은 요청의 대조2,007개를 함께 실행했다. 항목 선택 없음에는 일반 여행 질문·새 항목 추가·일정 전체 변경도 포함하며 여행과 무관한 잡담만을 뜻하지 않는다.

| 작성 방식 | 정상 요청 정답 | 항목 선택 없음 오지목 |
|---|---:|---:|
| 코드 이어 붙인1,768개 | 901/940 = 95.85% | 164/828 = 19.81% |
| 모델 자연 혼합239개 | 92/93 = 98.92% | 37/146 = 25.34% |

대조 정상 요청1,010/1,033에서 혼합993/1,033으로 정답률1.65%p 감소했다. 동일 일정59개 군집 부트스트랩2,000회·시드7의 손실95% 구간은0.87~2.38%p로 사전 상한2%p를 넘는 값도 포함한다. 점추정 합산 기준은3/4 통과이며 정상 요청≥95%·선택 손실≤2%p·오지목 증가≤1%p를 통과하고 오지목≤1% 기준을 실패했다. 반복으로 안정성을 확인한 합격은 아니다. 대조 오지목192/974에서 혼합201/974로 실제 오지목 증가0.92%p다.

| 항목 선택 없음 유형 | 오지목 |
|---|---:|
| 일정 밖 장소·일반 여행 질문 | 46/457 = 10.07% |
| 장소 언급 감상·잡담 | 118/121 = 97.52% |
| 새 항목 추가·일정 전체 변경 | 17/236 = 7.20% |
| 일정 전체 감정·불만 | 20/160 = 12.50% |

지정된세 부류의 오지목≤3% 기준은0/3 통과다. 정상 요청 점수 하나로 채택하거나12B 이름의 모델을 기본 소형 범위약8B 이하에 자동 포함하지 않는다.

## 원본·검증·한계

[답안](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/g12bbase_mx/d_test_mx_backlog_g12bbase.jsonl) · [조건·버전](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/g12bbase_mx/started.json) · [유형별 집계·구간](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/g12bbase_mx/mx_counts.json) · [원본 해시·独立 직접 계수](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/g12bbase_mx/verification.json).

GPU 서버 A 원본과 로컬 답안 SHA256은 `1c0963a3adc6aa7f24d89c8b38434b8aaf69672556b8d303ca82d8ed2e1d5729`로 같다. 고정 입력과 실행 당시 입력 해시가 같고 전체ID·정답·유형을 대조했다. 독립 직접 계수로 혼합/대조의 정상·항목 없음 분모·정답·오지목을 모두 확인했다. 미완료·호출 오류·해석 실패0이며 실패·미완료를 분모에서 빼지 않았다.

배포 Instruct 원본이며 우리 자료로 추가 학습하지 않았다. Q4_K_M, llama.cpp commit4ebdf2c, 모델 실행1회다. 문항별Wilson 구간·일정 군집 부트스트랩 반복은 모델 반복 실행을 대신하지 않는다. 기존 개발/회귀 자료이고 사람 정답 검수·독립 보류 검증은 남았다. 전체 원본 비교군 상위권이나 일반 우열을 확정하지 않는다. 말로 한 확신도와 토큰 확률, 다른 모델 정확도와 같은 모델 엔진 속도를 구분한다.

## 실행 유지·문서·백업

GPU 서버 A의 같은 실행기가 다음Gemma12B D평가를 시작했고 준비된평가7개가 남아 있다. GPU 서버 B는 Jev 계열 모델 중 Winnow-E4B(우리 여행 자료로 학습)의 기존 본 학습을 계속하며 뒤4개 학습이 예약돼 있다.2개는 기존 기반·입력,2개는 자동 다운로드 준비가 필요하다. 다음 다운로드 직전 공간을 재확인한다. 실행기 추가·중복 시험·작업 중단·새 결제·모델 삭제는 하지 않았다.

일일연구 Markdown/JSON·GPU 대기열 상태·평가 wiki·cs wiki log에 같은 근거를 연결했다. 과거 결과 리포트는 수정하지 않았다. 수정 직전 판 백업:

'''.replace('独立', '독립') + ''.join(f'- [{p}](../../../../{p})\n' for p in backups)
save(REPORT,report)
print(json.dumps({'saved':4014,'failed':0,'normal':[993,1033],'false_pick':[201,974],'aggregate_gates':[3,4],
    'ready_A':len(ac['ready']),'queued_B':4,'report':REPORT,'backup_stamp':stamp},ensure_ascii=False))
