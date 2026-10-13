"""Gemma12B 원본 H 완료를 원본 검증 후 백업·wiki 기록에 연결한다."""
from pathlib import Path
from datetime import datetime
import json
import hashlib
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'program/scripts/plan_qa_bench/results/gpu_backlog_20261008'
DAILY = ROOT / 'program/research/daily_rag_slm'
REPORT = 'final_project_cs/wiki/records/reports/2026-10-08_gemma12b-original-h-completion.md'
sys.stdout.reconfigure(encoding='utf-8')
assert not (ROOT / REPORT).exists(), 'Already recorded'
r = json.loads((BASE / 'g12bbase_h/h_counts.json').read_text(encoding='utf-8'))
assert r['saved'] == r['expected'] == 1316 and r['missing'] == r['failed_or_unparsed'] == 0
assert r['answer_sha256'] == '89d099fb7d219298306fbe3da1e98d8218f4b9cac94e7d38cbd7163a8fc1dd62'
assert r['gold_sha256'] == r['execution']['prompt_sha256'], 'Fixed prompt hash mismatch'
answer = BASE / 'g12bbase_h/d_test_h_backlog_g12bbase.jsonl'
assert hashlib.sha256(answer.read_bytes()).hexdigest() == r['answer_sha256']
rows = [json.loads(line) for line in answer.read_text(encoding='utf-8').splitlines()]
for label, positive in [('positive', True), ('negative', False)]:
    selected = [x for x in rows if (x['gold'] is not None) == positive]
    assert len(selected) == r[label]['total']
    assert sum(bool(x.get('parsed')) and not x.get('error') and x['pick'] == x['gold'] for x in selected) == r[label]['correct']
    assert sum(bool(x.get('parsed')) and not x.get('error') and x['gold'] is None and x['pick'] is not None for x in selected) == r[label]['false_pick']
assert r['positive']['correct'] == 453 and r['negative']['false_pick'] == 374
with (BASE / 'g12bbase_h/verification.json').open('x', encoding='utf-8') as f:
    json.dump({'answer_remote_hash_match': True, 'fixed_prompt_hash_match': True, 'direct_recount': True, 'saved': 1316,
               'missing': 0, 'failed_or_unparsed': 0, 'repetitions': 1}, f, indent=2)

stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S') + '_gemma12b_h_completion'
backups = []
def save(rel, text):
    p = ROOT / rel
    if p.exists():
        b = p.parent / '_backup' / stamp / p.name
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, b)
        backups.append(b.relative_to(ROOT).as_posix())
    p.write_text(text, encoding='utf-8')

a = json.loads((BASE / 'A_snapshot_1120.json').read_text(encoding='utf-8'))
b = json.loads((BASE / 'B_snapshot_1120.json').read_text(encoding='utf-8'))
ac = json.loads((BASE / 'A_conditions_1120.json').read_text(encoding='utf-8'))
bc = json.loads((BASE / 'B_conditions_1120.json').read_text(encoding='utf-8'))
state = json.loads((DAILY / 'gpu_backlog_2026-10-08.json').read_text(encoding='utf-8'))
completed = [x for x in a['state']['jobs'].values() if x['status'].startswith('completed')]
assert len(ac['ready']) >= 3 and 'qlora_train2.py /root/hf_models/winnow-e4b-hf' in b['processes']
state['recorded_at'] = datetime.now().isoformat()
for machine, snap, conditions in [('A', a, ac), ('B', b, bc)]:
    state['gpu_' + machine].update({'snapshot': (BASE / f'{machine}_snapshot_1120.json').relative_to(ROOT).as_posix(),
        'conditions_snapshot': (BASE / f'{machine}_conditions_1120.json').relative_to(ROOT).as_posix(),
        'observed_at_utc': snap['observed_at_utc'], 'instant_gpu_memory_and_utilization': snap['gpu_snapshot'],
        'root_available_bytes': conditions['root_space']['available_bytes']})
state['gpu_A'].update({'state': a['state'], 'answers_saved_at_snapshot': a['answers'], 'jobs_completed': len(completed),
    'jobs_completed_with_errors': sum(x['status'] == 'completed_with_errors' for x in completed), 'jobs_running': 1,
    'jobs_ready_waiting': len(ac['ready']), 'completed_g12bbase_h_archived': True})
state['latest_routine_observation'] = {'new_completed_jobs': 1, 'new_failed_jobs': 0, 'new_failed_or_unparsed_answers': 0,
    'queue_refill': False, 'worker_restart': False, 'reason': 'Gemma12B original H archived;8 fully prepared A evaluations and4 B recipes including2 automatic downloads remain.',
    'recorded_at': datetime.now().isoformat()}
save('program/research/daily_rag_slm/gpu_backlog_2026-10-08.json', json.dumps(state, ensure_ascii=False, indent=2) + '\n')
day = json.loads((DAILY / '2026-10-08.json').read_text(encoding='utf-8'))
assert not any(x.get('model') == r['model'] and x.get('suite') == 'H' for x in day['new_completed_evaluations'])
day['new_completed_evaluations'].append({k: r[k] for k in ['model', 'our_training', 'publisher_training', 'saved', 'expected', 'missing', 'failed_or_unparsed', 'positive', 'negative', 'repetitions', 'final_ranking']})
day['new_completed_evaluations'][-1].update({'suite': 'H', 'report': REPORT})
save('program/research/daily_rag_slm/2026-10-08.json', json.dumps(day, ensure_ascii=False, indent=2) + '\n')
save('program/research/daily_rag_slm/2026-10-08.md', (DAILY / '2026-10-08.md').read_text(encoding='utf-8') + '''
## 11시20분 확인 — Gemma12B 배포 원본의 어려운 문장 시험 완료

우리 자료로 추가 학습하지 않은 Gemma-4-12B-it Q4_K_M(개발사 지시 학습)의 H1316/1316개를 회수했다. 정상 요청453/461=98.26%, 요청 없는 함정·잡담 오지목374/855=43.74%, 요청 없음 정답481/855=56.26%다. 미완료·해석 실패0이며 GPU 서버 A 원본 SHA256·고정 입력 해시와 일치하고 직접 계수도 확인했다.

정상 요청 정확도만으로 채택하지 않는다. 다섯 묶음 중1/5 완료이며 다음 혼합 문장 평가가 실행 중이다. 기존 개발/회귀 자료의1회 관측으로 전체 원본 비교군 상위권·독립 보류 합격·서비스 적용은 아직 판단하지 않는다. 이12B 이름의 모델을 소형 학습 대상으로 자동 선정하지 않는다.

GPU 서버 A는 준비된 평가8개가 대기하며 GPU 서버 B의 기존 Winnow-E4B 우리 자료 학습 및 뒤4개 레시피를 유지했다. B뒤2개는 기존 기반이고2개는 자동 다운로드 준비가 필요하다. 다운로드 직전 공간을 재확인한다. 중복 실행·중단·삭제·새 결제는 하지 않았다.

[답안·집계](../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/g12bbase_h/h_report.md) · [완료·검증 리포트](../../../final_project_cs/wiki/records/reports/2026-10-08_gemma12b-original-h-completion.md).
''')
rel = 'final_project_cs/wiki/quality/slm-model-evaluation.md'
save(rel, (ROOT / rel).read_text(encoding='utf-8') + '\n`[실측 2026-10-08]` Gemma12B 배포 원본 H를 회수했다. 정상 요청과 요청 없음 오지목을 함께 집계했고 전체 범위·반복·보류 검증 전 채택은 보류한다. [완료·한계 근거](../records/reports/2026-10-08_gemma12b-original-h-completion.md).\n')
rel = 'final_project_cs/wiki/log.md'
save(rel, (ROOT / rel).read_text(encoding='utf-8').replace('# 문서 변경 이력 (cs)\n', '# 문서 변경 이력 (cs)\n\n## 2026-10-08 — Gemma12B 배포 원본 어려운 문장 시험 완료\n\n정상 요청 정답과 요청 없음 오지목을 함께 집계하고 다음 시험을 유지했다. [완료·검증 리포트](records/reports/2026-10-08_gemma12b-original-h-completion.md).\n', 1))
save(REPORT, '''# Gemma12B 배포 원본 H 완료 — 2026-10-08

우리 자료로 추가 학습하지 않은 Gemma-4-12B-it Q4_K_M(개발사 지시 학습)의 어려운 문장 시험을 회수했다. 정상 요청은 잘 맞췄지만 요청 없는 문장을 잘못 지목하는 비율도 높으므로 이 결과만으로 채택하지 않는다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 답안 보관·문항 대조 | 완료 | 1316/1316 = 100% |
| 정상 요청 정답 | 실측 | 453/461 = 98.26% |
| 요청 없음 오지목 | 실측 | 374/855 = 43.74% |
| 예정 다섯 묶음 | 진행 | 1/5 = 20% |

## 원본·조건·검증

요청 없음855개는 정답481개와 오지목374개다. 미완료·호출 오류·해석 실패0이며 실패나 미완료 문항을 분모에서 빼는 처리를 하지 않았다.

[답안](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/g12bbase_h/d_test_h_backlog_g12bbase.jsonl) · [실행 조건](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/g12bbase_h/started.json) · [유형별 계수·구간](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/g12bbase_h/h_counts.json) · [직접 계수·해시 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/g12bbase_h/verification.json).

답안 SHA256은 GPU 서버 A 원본과 같은 `89d099fb7d219298306fbe3da1e98d8218f4b9cac94e7d38cbd7163a8fc1dd62`다. 고정 입력 해시와 실행 당시 입력 해시가 같고 문항 ID·정답·유형을 대조했다. JSON 출력은 단일 번호 또는 null 계약으로 판정했다. 독립 직접 계수에서도 정상/요청 없음 분모·정답·오지목이 같았다. llama.cpp commit4ebdf2c, 모델 실행1회, 기존 개발/회귀 문항이다.

Wilson 구간은 문항별 구간이며 같은 일정 문항 간 상관을 제거하지 않는다. 반복 모델 실행·새 독립 보류 검증을 대신하지 않는다. 토큰 확률을 말로 한 확신도와 같다고 해석하거나 다른 모델·경로의 지연을 같은 모델 엔진 속도로 비교하지 않는다. 정상 요청 점수 하나만으로 전체 상위권이나 제품 채택을 확정하지 않는다. 모델 이름12B를 기본 소형 기준약8B 이하와 혼동해 파인튜닝 후보로 자동 선정하지 않는다.

## 후속 작업·문서·백업

GPU 서버 A의 같은 지속 실행기가 다음 Gemma12B 혼합 문장 시험을 실행하며 준비된 평가8개가 남았다. GPU 서버 B는 Jev 계열 모델 중 Winnow-E4B(우리 여행 자료로 학습)의 기존 본 학습을 계속하며 뒤4개 학습이 예약돼 있다.2개는 기존 기반,2개는 자동 다운로드 준비가 필요하다. 다음 다운로드 직전 공간을 다시 확인한다. 실행기 추가·중복 시험·진행 중 작업 중단·모델 삭제·새 결제는 하지 않았다.

일일 연구 Markdown/JSON·GPU 대기열 상태·평가 wiki·cs wiki log에 같은 근거를 연결했다. 이전 날짜별 원본 리포트는 수정하지 않았다. 수정 직전 판의 백업:

''' + ''.join(f'- [{p}](../../../../{p})\n' for p in backups))
print(json.dumps({'saved': 1316, 'failed': 0, 'ready_A': len(ac['ready']), 'queued_B': 4, 'report': REPORT, 'backup_stamp': stamp}, ensure_ascii=False))
