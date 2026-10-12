"""신규 완료 D/D2/D3를 검증하고 백업 후 정본에 근거 링크를 연결한다."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'program/scripts/plan_qa_bench/results/gpu_backlog_20261008'
sys.stdout.reconfigure(encoding='utf-8')
stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S') + '_gemma_choice_completion'
report_rel = 'final_project_cs/wiki/records/reports/2026-10-08_gemma-original-choice-completion.md'
assert not (ROOT / report_rel).exists(), 'Completion already recorded'
backups = []


def save(rel, text):
    p = ROOT / rel
    if p.exists():
        b = p.parent / '_backup' / stamp / p.name
        b.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, b)
        backups.append(b.relative_to(ROOT).as_posix())
    p.write_text(text, encoding='utf-8')


data = []
remote_hashes = {
    'D': '0aa347270a46aa08b57ff36aed5aef7697fc1862dd9c7d0d0cb133b5f7ad06cf',
    'D2': '67938f8a18f0b86c0af3b9493e7360e2f5b89e46a25ced0f706d1f5042b66ea3',
    'D3': 'd11e34627fb3a27a2ca9f5faf0718a5c4f415af63e3e478b1896a28217ec44f7',
}
checks = []
for suite in ['D', 'D2', 'D3']:
    folder = BASE / ('e4bbase_' + suite.lower())
    r = json.loads((folder / 'choice_counts.json').read_text(encoding='utf-8'))
    answer = folder / f"d_test_{r['execution']['job']['tag']}.jsonl"
    rows = [json.loads(line) for line in answer.read_text(encoding='utf-8').splitlines()]
    assert r['saved'] == r['expected'] and r['missing'] == 0
    assert hashlib.sha256(answer.read_bytes()).hexdigest() == r['answer_sha256'] == remote_hashes[suite]
    for key, positive in [('positive', True), ('negative', False)]:
        selected = [x for x in rows if x['type'] != 'compound_intent' and (x['gold'] is not None) == positive]
        valid = lambda x: bool(x.get('parsed')) and not x.get('error')
        assert r[key]['total'] == len(selected)
        assert r[key]['correct'] == sum(valid(x) and x['pick'] == x['gold'] for x in selected)
        assert r[key]['false_pick'] == sum(valid(x) and x['gold'] is None and x['pick'] is not None for x in selected)
        assert r[key]['failed_or_missing'] == sum(not valid(x) for x in selected)
    checks.append({'suite': suite, 'direct_recount': True, 'remote_hash_match': True,
                   'fixed_prompt_hash_match': r['gold_sha256'] == r['execution']['prompt_sha256'],
                   'expected': r['expected'], 'failed_or_unparsed': r['failed_or_unparsed']})
    data.append(r)
assert [r['failed_or_unparsed'] for r in data] == [13, 0, 2]
verification = {'checks': checks, 'model_runs': 1, 'new_calls': 0, 'compound_diagnostic_excluded_from_single_choice_only': 66}
with (BASE / 'gemma_choice_verification_20261008.json').open('x', encoding='utf-8') as f:
    json.dump(verification, f, ensure_ascii=False, indent=2)

daily = ROOT / 'program/research/daily_rag_slm'
day = json.loads((daily / '2026-10-08.json').read_text(encoding='utf-8'))
for r in data:
    assert not any(x.get('model') == r['model'] and x.get('suite') == r['suite'] for x in day['new_completed_evaluations'])
    day['new_completed_evaluations'].append({k: r[k] for k in ['model', 'our_training', 'publisher_training', 'suite', 'saved', 'expected', 'missing', 'failed_or_unparsed', 'positive', 'negative', 'repetitions', 'final_ranking']})
    day['new_completed_evaluations'][-1]['report'] = report_rel
save('program/research/daily_rag_slm/2026-10-08.json', json.dumps(day, ensure_ascii=False, indent=2) + '\n')

a = json.loads((BASE / 'A_snapshot_1106.json').read_text(encoding='utf-8'))
b = json.loads((BASE / 'B_snapshot_1100.json').read_text(encoding='utf-8'))
ac = json.loads((BASE / 'A_conditions_1106.json').read_text(encoding='utf-8'))
bc = json.loads((BASE / 'B_conditions_1100.json').read_text(encoding='utf-8'))
state = json.loads((daily / 'gpu_backlog_2026-10-08.json').read_text(encoding='utf-8'))
completed = [x for x in a['state']['jobs'].values() if x['status'].startswith('completed')]
state['recorded_at'] = datetime.now().isoformat()
state['gpu_A'].update({'snapshot': (BASE / 'A_snapshot_1106.json').relative_to(ROOT).as_posix(),
                      'conditions_snapshot': (BASE / 'A_conditions_1106.json').relative_to(ROOT).as_posix(),
                      'observed_at_utc': a['observed_at_utc'], 'state': a['state'], 'answers_saved_at_snapshot': a['answers'],
                      'jobs_completed': len(completed), 'jobs_completed_with_errors': sum(x['status'] == 'completed_with_errors' for x in completed),
                      'jobs_running': 1, 'jobs_ready_waiting': len(ac['ready']),
                      'instant_gpu_memory_and_utilization': a['gpu_snapshot'], 'completed_e4bbase_choice_archived': True})
state['gpu_B'].update({'snapshot': (BASE / 'B_snapshot_1100.json').relative_to(ROOT).as_posix(),
                      'conditions_snapshot': (BASE / 'B_conditions_1100.json').relative_to(ROOT).as_posix(),
                      'observed_at_utc': b['observed_at_utc'], 'instant_gpu_memory_and_utilization': b['gpu_snapshot'],
                      'root_available_bytes': bc['root_space']['available_bytes']})
state['latest_routine_observation'] = {'new_completed_jobs': 3, 'new_failed_jobs': 0, 'new_failed_or_unparsed_answers': 15,
    'queue_refill': False, 'worker_restart': False, 'reason': 'Archived Gemma D/D2/D3; A has9 fully prepared jobs, B has4 recipes including2 automatic model downloads.',
    'recorded_at': datetime.now().isoformat()}
save('program/research/daily_rag_slm/gpu_backlog_2026-10-08.json', json.dumps(state, ensure_ascii=False, indent=2) + '\n')

summary = '''
## 11時台確認 — Gemma E4B 배포 원본의 다섯 평가 묶음 완료

우리 자료 추가 학습 없는 Gemma-4-E4B-it Q4_K_M(개발사 지시 학습)의 D 2735/2735·D2 1000/1000·D3 360/360개를 새로 회수했다. 이미 보관한 H/MX를 합쳐 예정된5/5 묶음·9425/9425개를 보관했다. 전체 형식 실패17개(D13·D3 2·H1·MX1)를 원문과 해당 분모에 남겼으며 미완료0이다.

D 단일 선택 정상 정답738/883=83.58%, 잡담 오지목54/1300=4.15%(형식 실패2개 별도)다. D2 요청 없음 오지목69/1000=6.90%, D3 정상 정답103/120=85.83%·잡담 오지목19/240=7.92%(형식 실패2개 별도)다. D 복합66개는 별도 진단으로 보존하고 단일 번호 선택 정확도에 합치지 않았다. 배열·문자열 출력을 번호나 null로 고쳐 정답 처리하지 않았다.

새 세 파일은 GPU 서버 A 원본과 SHA256이 같고 고정 입력 해시·문항 ID·정답·유형 및 독립 직접 계수를 확인했다. 기존 개발/회귀 문항의1회 평가이며 전체 원본 비교군 상위권·제품 채택·파인튜닝 후보 선정을 확정하지 않는다.

GPU 서버 A는 Gemma12B 원본 H를 실행하며 입력까지 준비된 평가9개가 남았다. GPU 서버 B는 Jev 계열 모델 중 Winnow-E4B(우리 여행 자료로 학습)를 계속하며 학습4개가 순서대로 대기한다. 그중2개는 기반 모델 다운로드 준비가 필요하고2개는 기존 기반이다. 새 실행기·재시험·삭제·결제 없이 기존 대기열을 유지한다.

[새 완료 리포트](../../../final_project_cs/wiki/records/reports/2026-10-08_gemma-original-choice-completion.md) · [직접 계수·원본 해시 검증](../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/gemma_choice_verification_20261008.json).
'''.replace('11時台確認', '11시 확인')
save('program/research/daily_rag_slm/2026-10-08.md', (daily / '2026-10-08.md').read_text(encoding='utf-8') + summary)
rel = 'final_project_cs/wiki/quality/slm-model-evaluation.md'
save(rel, (ROOT / rel).read_text(encoding='utf-8') + '\n`[실측 2026-10-08]` Gemma E4B 배포 원본의 D/D2/D3도 회수해 예정된 다섯 평가 묶음을 완료했다. 형식 실패17개를 분모에 남겼고 복합 문항은 별도 진단이다. [범위·수치·실패 보존 근거](../records/reports/2026-10-08_gemma-original-choice-completion.md).\n')
rel = 'final_project_cs/wiki/log.md'
save(rel, (ROOT / rel).read_text(encoding='utf-8').replace('# 문서 변경 이력 (cs)\n', '# 문서 변경 이력 (cs)\n\n## 2026-10-08 — Gemma E4B 배포 원본 다섯 묶음 회수 완료\n\nD/D2/D3를 추가 회수해 원본5/5 묶음을 보관했다. 복합 요청과 형식 실패를 분리해 집계했고 전체 모델 순위는 보류했다. [완료 리포트](records/reports/2026-10-08_gemma-original-choice-completion.md).\n', 1))

links = '\n'.join(f"- [{r['suite']} 답안·집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_{r['suite'].lower()}/choice_report.md)" for r in data)
tables = '\n'.join(f"| {r['suite']} 답안 보관 | 완료 | {r['saved']}/{r['expected']} = 100% |" for r in data)
save(report_rel, f'''# Gemma E4B 배포 원본 D/D2/D3 회수 완료 — 2026-10-08

우리 자료 추가 학습 없는 Gemma-4-E4B-it Q4_K_M(개발사 지시 학습)의 나머지 세 묶음을 회수했다. 앞서 보관한 어려운 문장·혼합 문장 시험까지 합쳐 이 배포판의 예정된 다섯 묶음이 완료됐다.

| 할 일 | 상태 | 진행 |
|---|---|---|
{tables}
| 다섯 묶음 답안 보관 | 완료 | 9425/9425 = 100% |

## 수치·분모·실패

D 정상 요청738/883=83.58%, 요청 없음 전체 오지목75/1786=4.20%·형식 실패2/1786이며 그중 잡담 오지목54/1300=4.15%·형식 실패2/1300이다. 단일 선택 전체2669개와 복합66개를 분리한다. D 형식 실패13개 중 복합7개·단일 선택 정상4개·잡담2개다. 복합66개는 진단 원문에 보존했으며 전체 지시 수행 성공이나 단일 선택 정확도로 채택하지 않는다.

D2는 요청 없는1000개뿐이며 오지목69/1000=6.90%·정답931/1000=93.10%·실패0이다. D3는 정상 요청103/120=85.83%, 잡담 오지목19/240=7.92%·형식 실패2/240·정답219/240이다. 두 실패는 null 정답으로 재해석하지 않았다.

세 묶음4095개에서 누락0·형식 실패15개다. 전체 다섯 묶음9425개에는 D13·D3 2·H1·MX1로 형식 실패17개가 있다. 배열·문자열 출력을 고쳐 정답 처리하거나 실패·미완료를 해당 유형의 분모에서 제외하지 않는다. 실제 오지목 계수와 형식 실패를 따로 표시하고 실패는 정확도에서 오답으로 센다.

## 실행 근거와 한계

{links}
- [독립 직접 계수·GPU 서버 A 원본 해시 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/gemma_choice_verification_20261008.json)
- [앞선 어려운 문장 완료](2026-10-08_gemma-original-h-completion.md) · [앞선 혼합 문장 완료](2026-10-08_gemma-original-mx-completion.md)

세 답안의 SHA256을 GPU 서버 A 원본과 대조했다. 집계에는 실행 기록·고정 입력 해시·실패 원문이 있으며 고정 입력 SHA256과 ID·유형·정답이 모두 일치했다. 개발/회귀 문항의 모델 실행1회이며 토큰 확률은 말로 한 확신도와 같지 않다. 기존 다섯 묶음 완료가 모든 과거 모델·모든 역할·새 독립 보류 시험 완료를 뜻하지 않는다. 남은 원본 모델과 같은 범위 비교 및 반복·독립 보류 검증 전에 상위권·학습 후보·제품 채택을 확정하지 않는다.

GPU 서버 A는 Gemma12B 원본 H를 시작했고 입력 준비된 평가9개가 대기한다. GPU 서버 B는 Jev 계열 모델 중 Winnow-E4B(우리 데이터로 학습)를 실행하며 뒤4개 레시피가 대기한다.2개는 기존 기반,2개는 자동 다운로드 준비가 필요하므로 다운로드 직전 공간을 다시 확인한다. 새로운 실행기나 중복 작업을 시작하지 않았다.

## 문서와 백업

일일 연구 Markdown/JSON, GPU 대기열 상태, 모델 평가 wiki와 cs wiki 변경 기록에 같은 근거를 연결했다. 이번 수정 직전 판은 아래에 보관했다. 이전 완료 리포트는 수정하지 않았다.

''' + '\n'.join(f'- [{p}](../../../../{p})' for p in backups) + '\n')
print(json.dumps({'new_suites': 3, 'new_saved': 4095, 'new_format_failures': 15, 'all_gemma_suites': 5, 'all_saved': 9425, 'all_format_failures': 17, 'ready_A': len(ac['ready']), 'queued_B': 4, 'report': report_rel}, ensure_ascii=False))
