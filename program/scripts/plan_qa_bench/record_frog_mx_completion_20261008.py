"""새 완료 결과를 일일 상태·wiki 작업 리포트·정본 연결에 백업 후 반영한다."""
from pathlib import Path
from datetime import datetime
import json, shutil
ROOT=Path(__file__).resolve().parents[3]
stamp=datetime.now().strftime('%Y-%m-%d_%H%M')+'_frog_mx_completion'
backup_paths=[]

def save(rel,text):
    p=ROOT/rel
    if p.exists():
        b=p.parent/'_backup'/stamp/p.name
        b.parent.mkdir(parents=True,exist_ok=True)
        assert not b.exists()
        shutil.copy2(p,b)
        backup_paths.append(str(b.relative_to(ROOT)).replace('\\','/'))
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(text,encoding='utf-8')

results=ROOT/'program/scripts/plan_qa_bench/results/gpu_backlog_20261008'
counts=json.loads((results/'frog_mx/mx_counts.json').read_text(encoding='utf-8'))
assert counts['complete_valid'] and counts['saved']==counts['expected']==4014
assert json.loads((results/'frog_mx/verification.json').read_text(encoding='utf-8'))['checks_passed']==7
a=json.loads((results/'A_snapshot_1029.json').read_text(encoding='utf-8'))
b=json.loads((results/'B_snapshot_1029.json').read_text(encoding='utf-8'))
daily='program/research/daily_rag_slm/'
state_path=daily+'gpu_backlog_2026-10-08.json'
state=json.loads((ROOT/state_path).read_text(encoding='utf-8'))
state['gpu_A'].update({'snapshot':'program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_snapshot_1029.json','observed_at_utc':a['observed_at_utc'],
 'state':a['state'],'answers_saved_at_snapshot':a['answers'],'jobs_completed':2,'jobs_running':1,'jobs_ready_waiting':14,
 'instant_gpu_memory_and_utilization':a['gpu_snapshot'],'completed_frog_mx_archived':True})
state['gpu_B'].update({'snapshot':'program/scripts/plan_qa_bench/results/gpu_backlog_20261008/B_snapshot_1029.json','observed_at_utc':b['observed_at_utc'],'instant_gpu_memory_and_utilization':b['gpu_snapshot']})
state['latest_routine_observation']={'new_completed_jobs':1,'new_failed_jobs':0,'worker_restart':False,'queue_refill':False,'reason':'14 A ready jobs and4 existing B executable recipes remain queued; completed Frog MX archived and verified','recorded_at':datetime.now().isoformat()}
save(state_path,json.dumps(state,ensure_ascii=False,indent=2)+'\n')
day=json.loads((ROOT/daily/'2026-10-08.json').read_text(encoding='utf-8'))
entry={'model':'FrogNano-4B-2609','our_training':False,'publisher_training':'coding RL','suite':'MX','saved':4014,'expected':4014,
 'errors':0,'unparsed':0,'mixed_requests_correct':898,'mixed_requests_total':1033,'mixed_false_pick':167,'mixed_no_request_total':974,
 'request_loss_pp':counts['paired']['request']['loss_pp'],'aggregate_gates_passed':1,'aggregate_gates_total':4,'repetitions':1,'full_ranking':False,
 'report':'program/scripts/plan_qa_bench/results/gpu_backlog_20261008/frog_mx/mx_report.md'}
assert not any(x.get('suite')=='MX' and x.get('model')==entry['model'] for x in day['new_completed_evaluations'])
day['new_completed_evaluations'].append(entry)
save(daily+'2026-10-08.json',json.dumps(day,ensure_ascii=False,indent=2)+'\n')
save(daily+'2026-10-08.md',(ROOT/daily/'2026-10-08.md').read_text(encoding='utf-8')+'''
## 10시 30분 확인 — FrogNano 원본 혼합 요청 완료

우리 자료로 학습하지 않은 FrogNano-4B-2609(개발사 코딩 강화학습 있음)의 혼합 요청 MX 답안4,014/4,014를 회수했습니다. SHA256은 GPU 서버 A 완료 원본과 일치하고 문항 ID·정답·유형 일치, 누락0·오류/해석실패0을 확인했습니다. 새 집계의 직접 계수와 누락·오류 분모 보존 예제7/7도 통과했습니다.

혼합 정상 요청 정답898/1033=86.93%, 요청 없는 혼합 문장 오지목167/974=17.15%입니다. 요청만 있는 대조 정답955/1033=92.45%에서 선택률5.52%p가 떨어졌으며 일정별95% 구간은3.98~6.96%p입니다. 사전 합산 기준1/4 통과, MX3/MX4/MX5a 오지목 기준도0/3 통과입니다. 모델 실행1회·일정별 부트스트랩2,000회이며 기존 개발/회귀 세트입니다. 모델 간 최종 순위·서비스 채택을 결정하지 않습니다.

[혼합 요청 답안·집계](../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/frog_mx/mx_report.md) · [작업 리포트](../../../final_project_cs/wiki/records/reports/2026-10-08_frog-original-mx-completion.md).

GPU 서버 A는 원본 Gemma-4-E4B-it의 H를 이어서 실행하며 준비된 평가14개가 남았습니다. GPU 서버 B는 Jev 계열 모델 중 Winnow-E4B에 우리 자료로 학습 중이며 뒤 본 학습4개가 예약돼 있습니다. 이 중2개는 기존 스크립트의 기반 다운로드 준비가 필요하고2개는 기존 기반으로 실행합니다. 여유 공간은 다음 후보 다운로드 직전에 다시 확인합니다. 진행 중 프로세스를 중단·중복하지 않았습니다.
''')

# 앞 감사는 당시 관측으로 보존하고 오늘 새 완료 범위만 별도 표에 추가한다.
coverage=[]
for suite,path,expected in [('D','d_test/d_test_a_frognano.jsonl',2735),('D2','d_test/d_test_d2_frog.jsonl',1000),('D3','d_test/d_test_d3_frog.jsonl',360),('H','gpu_backlog_20261008/frog_h/d_test_h_backlog_frog.jsonl',1316),('MX','gpu_backlog_20261008/frog_mx/d_test_mx_backlog_frog.jsonl',4014)]:
    p=ROOT/'program/scripts/plan_qa_bench/results'/path
    rows=[json.loads(l) for l in p.read_text(encoding='utf-8').splitlines()]
    assert len(rows)==expected
    coverage.append({'suite':suite,'saved':len(rows),'expected':expected,'source':path})
coverage_path='program/scripts/plan_qa_bench/results/frog_original_coverage_2026-10-08_1030.md'
save(coverage_path,'''# FrogNano 원본 추가 시험 보관 범위 — 2026-10-08 10시30분

기존 감사의 당시 미확인 H·MX가 새로 완료돼 우리 자료 학습 없는 FrogNano의 D/D2/D3/H/MX 보관 범위는5/5입니다. 아래 분자는 저장된 답안 수이며 정답 수가 아닙니다. 다른 모델·모든 역할의 완료를 뜻하지 않습니다.

| 시험 | 답안 보관 | 원본 |
|---|---|---|
'''+''.join(f"| {x['suite']} | {x['saved']}/{x['expected']} = 100% | [답안]({x['source']}) |\n" for x in coverage)+'''
기존 [13변형 감사](test_coverage_audit_2026-10-08.md)는 당시 관측으로 보존했습니다. MAI 검토·직접 선택 등 역할이 다른 평가는 별도이며, 원본 비교군의 모든 문항을 같은 계약으로 완료한 뒤 순위를 판단합니다. 모델 배포판에는 개발사 코딩 학습이 있으나 우리 추가 학습은 없습니다.
''')
report_rel='final_project_cs/wiki/records/reports/2026-10-08_frog-original-mx-completion.md'
save('final_project_cs/wiki/quality/slm-model-evaluation.md',(ROOT/'final_project_cs/wiki/quality/slm-model-evaluation.md').read_text(encoding='utf-8')+'''
## 원본 비교의 최신 근거

`[실측 2026-10-08]` 우리 자료 추가 학습 없는 FrogNano의 H·MX를 모두 보관·검증했다. 기존 다섯 추가 시험의 답안 보관이 완료됐으나 원본 비교군 전체의 최종 순위는 대기한다. [완료·집계·한계 기록](../records/reports/2026-10-08_frog-original-mx-completion.md).
''')
p=ROOT/'final_project_cs/wiki/log.md'
text=p.read_text(encoding='utf-8')
entry_log='''
## 2026-10-08 — FrogNano 원본 혼합 요청 평가 완료

우리 자료 추가 학습 없는 FrogNano의 혼합 요청 답안을 회수·검증하고 전체 분모와 일정별 구간을 집계했다. 원본 비교군 최종 순위는 대기한다. [완료 리포트](records/reports/2026-10-08_frog-original-mx-completion.md).
'''
save('final_project_cs/wiki/log.md',text.replace('# 문서 변경 이력 (cs)\n','# 문서 변경 이력 (cs)\n'+entry_log,1))
save(report_rel,'''# FrogNano 배포 원본의 혼합 요청 평가 완료 — 2026-10-08

우리 여행 자료로 추가 학습하지 않은 FrogNano-4B-2609의 MX 답안4,014개를 회수·집계했다. 개발사 코딩 강화학습은 있음으로 구분한다. 같은 일정의 요청만 있는 대조와 잡담이 섞인 요청을 비교한 시험이며 다른 모델 간 최종 순위를 확정하지 않았다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 답안 회수·문항 일치 | 완료 | 4,014/4,014 = 100% |
| 집계 검증 | 통과 | 7/7 = 100% |
| 혼합 정상 요청 정답 | 실측 | 898/1,033 = 86.93% |
| 혼합 요청 없음 오지목 | 실측 | 167/974 = 17.15% |

## 실행·원본 보호

기존 GPU 서버 A 지속 실행기가 완료한 작업을 회수했으며 실행기를 추가로 띄우지 않았다. GPU 서버 B의 기존 학습도 중단하지 않았다. 이번에 새 GPU 시험을 중복 시작하거나 모델 파일을 삭제하지 않았다. Strata와 완료 MAI 시험은 재실행하지 않았다.

[원본 답안](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/frog_mx/d_test_mx_backlog_frog.jsonl) · [실행 버전·입력 해시](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/frog_mx/started.json) · [상세 집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/frog_mx/mx_counts.json) · [집계 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/frog_mx/verification.json).

회수한 답안 SHA256은 GPU 서버 A 완료 원본과 동일하다: `46aefc1479b5ccc378fd1f9178a761955b98976f968992dfab2928e0a26d59df`. llama.cpp commit4ebdf2c, 기존 조건·한 번 실행이다. 양자화와 모델 역할이 다른 실행기의 지연을 직접 비교하지 않았다.

## 결과와 해석

정상 요청 분모는 혼합 문장 중 항목 정답이 있는1,033개, 오지목 분모는 혼합 문장 중 정답 없음974개이다. 요청만 있는 대조에도 각각 같은 수가 있다. 누락·호출 오류·해석 실패는0개이며 실패를 분모에서 제외하지 않는 집계로 검증했다.

대조 정상 요청955/1,033=92.45%에서 혼합898/1,033=86.93%로5.52%p 감소했다. 일정59개를 단위로 군집 부트스트랩2,000회·시드7로 계산한95% 감소 구간은3.98~6.96%p이다. 요청 없음 오지목은 대조173/974에서 혼합167/974로6개 줄었다. 변화 구간이0을 포함하므로 잡담이 오지목을 개선했다고 일반화하지 않는다.

사전 합산 기준1/4 통과, 지정 부류 MX3·MX4·MX5a 오지목 기준0/3 통과다. 유형별 및 코드 연결/자연 혼합별 계수는 상세 집계에 보관했다. 토큰 p_null을 보정된 확률이나 MAI가 말한 확신도와 같은 값이라고 해석하지 않았다.

기존 개발·회귀 자료이며 새 독립 보류 자료와 구분한다. 모델 실행은1회이고 부트스트랩2,000회는 모델 실행 반복이 아니다. 사람 정답 검수와 독립 보류 자료의 최종 검증은 남아 있다. 원본 비교군의 부족한 시험을 이어가며 최종 상위권 판정을 보류한다.

## 문서 연결·보관 범위

[모델 평가 wiki](../../quality/slm-model-evaluation.md)와 cs wiki log에 결론·리포트를 연결했다. 일일 Markdown/JSON과 GPU 상태도 같은 완료 근거를 반영했다. 기존 시험 감사는 과거 관측으로 보존하고 [FrogNano 다섯 세트 보관 확인](../../../../program/scripts/plan_qa_bench/results/frog_original_coverage_2026-10-08_1030.md)을 별도로 작성했다. [집계 도구](../../../../program/scripts/plan_qa_bench/backlog_mx_report.py)는 누락·실패도 전체 문항 분모에 남긴다.

## 다음 실행과 백업

관측 시 GPU 서버 A는 원본 Gemma-4-E4B-it H를 실행하며 준비된 평가14개가 대기했다. GPU 서버 B는 Jev 계열 모델 중 Winnow-E4B에 우리 자료 학습을 계속하며 뒤 본 학습4개가 예약돼 있다. 기존 스크립트의 기반 다운로드2개와 기존 기반으로 준비된 학습률 비교2개를 구분했고 공간은 다음 다운로드 직전에 다시 확인한다. 새 완료 어댑터는 이번 확인 범위에서 발견되지 않았다.

수정 직전 판은 아래 위치에 보존했다.

'''+''.join('- ['+p+'](../../../../'+p+')\n' for p in backup_paths))
print(json.dumps({'backups':backup_paths,'coverage_sets':len(coverage),'report':report_rel},ensure_ascii=True))
