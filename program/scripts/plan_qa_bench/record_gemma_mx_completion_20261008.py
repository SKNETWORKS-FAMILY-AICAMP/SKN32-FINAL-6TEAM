"""원본 Gemma MX의 완료·형식 실패·같은 세트 비교를 백업 후 wiki에 연결한다."""
from pathlib import Path
from datetime import datetime
import json, shutil
ROOT=Path(__file__).resolve().parents[3]
stamp=datetime.now().strftime('%Y-%m-%d_%H%M%S')+'_gemma_mx_completion'
results=ROOT/'program/scripts/plan_qa_bench/results/gpu_backlog_20261008'
r=json.loads((results/'e4bbase_mx/mx_counts.json').read_text(encoding='utf-8'))
assert r['saved']==r['expected']==4014 and r['failed_or_unparsed']==1 and r['missing']==0
backups=[]
def save(rel,text):
    p=ROOT/rel
    if p.exists():
        b=p.parent/'_backup'/stamp/p.name;b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,b)
        backups.append(str(b.relative_to(ROOT)).replace('\\','/'))
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
daily='program/research/daily_rag_slm/'
a=json.loads((results/'A_snapshot_1050.json').read_text(encoding='utf-8'))
b=json.loads((results/'B_snapshot_1050.json').read_text(encoding='utf-8'))
ac=json.loads((results/'A_conditions_1050.json').read_text(encoding='utf-8'))
bc=json.loads((results/'B_conditions_1050.json').read_text(encoding='utf-8'))
state=json.loads((ROOT/daily/'gpu_backlog_2026-10-08.json').read_text(encoding='utf-8'))
state['gpu_A'].update({'snapshot':'program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_snapshot_1050.json',
 'conditions_snapshot':'program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_conditions_1050.json','observed_at_utc':a['observed_at_utc'],
 'state':a['state'],'answers_saved_at_snapshot':a['answers'],'jobs_completed':4,'jobs_completed_with_errors':2,'jobs_running':1,
 'jobs_ready_waiting':len(ac['ready']),'instant_gpu_memory_and_utilization':a['gpu_snapshot'],'completed_e4bbase_mx_archived':True})
state['gpu_B'].update({'snapshot':'program/scripts/plan_qa_bench/results/gpu_backlog_20261008/B_snapshot_1050.json',
 'conditions_snapshot':'program/scripts/plan_qa_bench/results/gpu_backlog_20261008/B_conditions_1050.json','observed_at_utc':b['observed_at_utc'],
 'instant_gpu_memory_and_utilization':b['gpu_snapshot'],'root_available_bytes':bc['root_space']['available_bytes']})
state['latest_routine_observation']={'new_completed_jobs':1,'new_failed_jobs':0,'new_failed_or_unparsed_answers':1,'queue_refill':False,'worker_restart':False,
 'reason':'Gemma original MX archived with format failure retained.12 prepared A jobs remain; B has4 executable recipes including2 automatic downloads.', 'recorded_at':datetime.now().isoformat()}
save(daily+'gpu_backlog_2026-10-08.json',json.dumps(state,ensure_ascii=False,indent=2)+'\n')
day=json.loads((ROOT/daily/'2026-10-08.json').read_text(encoding='utf-8'))
assert not any(x.get('model')=='Gemma-4-E4B-it Q4_K_M' and x.get('suite')=='MX' for x in day['new_completed_evaluations'])
day['new_completed_evaluations'].append({'model':'Gemma-4-E4B-it Q4_K_M','our_training':False,'publisher_training':'Instruct release','suite':'MX',
 'saved':4014,'expected':4014,'missing':0,'failed_or_unparsed':1,'mixed_requests_correct':960,'mixed_requests_total':1033,'mixed_false_pick':154,'mixed_no_request_total':974,
 'request_loss_pp':r['paired']['request']['loss_pp'],'aggregate_gates_passed':1,'aggregate_gates_total':4,'repetitions':1,'full_ranking':False,
 'report':'program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_mx/mx_report.md'})
save(daily+'2026-10-08.json',json.dumps(day,ensure_ascii=False,indent=2)+'\n')
save(daily+'2026-10-08.md',(ROOT/daily/'2026-10-08.md').read_text(encoding='utf-8')+'''
## 10시50분 확인 — Gemma E4B 원본 MX 완료와 같은 세트 비교

우리 자료 학습 없는 Gemma-4-E4B-it Q4_K_M(개발사 지시 학습)의 MX답안4,014/4,014개를 보관했고 GPU 서버 A 원본 SHA256과 일치했습니다. 혼합 정상 요청 정답960/1033=92.93%, 요청 없는 혼합 문장 오지목154/974=15.81%, 사전 합산1/4 통과입니다. 대조 정상 요청984/1033에서 혼합에 따른 정답 손실2.32%p, 일정별95% 구간1.28~3.30%p입니다.

대조의 요청 없음 문항1201490이 `{"item": [9, 32]}` 배열을 내 형식 실패1개입니다. null 정답으로 고치거나 전체 분모에서 빼지 않았습니다. 요청 없음 대조는 정답740/974·오지목233/974·형식 실패1/974입니다. 실제 오지목 증가−8.11%p와 실패 포함 정답률 손실−8.21%p를 구분하도록 집계 도구를 백업 후 보완했습니다. 독립 직접 계수·분모 보존·형식 실패 처리·실제 오지목 증가 예제를 검증했습니다.

같은 MX혼합 문항에서 Gemma 정답960/1033 대 FrogNano898/1033로62개 차이, 일정별 차이95% 구간3.95~8.14%p입니다. 오지목154/974 대167/974의 차이는 일정별 구간이0을 포함해 우열을 확정하지 않습니다. 이 비교는 보관된 배포판·1회·이 세트의 결과이며 양자화가 같은 아키텍처 비교나 전체 상위권 판정이 아닙니다. 다른 원본 모델의 시험과 독립 보류·반복 검증은 대기합니다.

[답안·집계](../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_mx/mx_report.md) · [검증·짝지은 비교](../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_mx/verification_and_pair_comparison.json) · [완료 리포트](../../../final_project_cs/wiki/records/reports/2026-10-08_gemma-original-mx-completion.md).

GPU 서버 A는 원본 Gemma D를 실행하며 준비된 평가12개가 대기합니다. GPU 서버 B는 기존 Winnow-E4B 우리 자료 학습을 계속하고 뒤 학습4개 중2개는 기존 기반,2개는 자동 다운로드 준비가 필요합니다. 관측 시 공간 조건은 충족하지만 다음 다운로드 직전에 다시 확인합니다. 진행 중 작업을 중단·중복하지 않았습니다.
''')
rel='final_project_cs/wiki/quality/slm-model-evaluation.md'
save(rel,(ROOT/rel).read_text(encoding='utf-8')+'''
`[실측 2026-10-08]` 우리 자료 추가 학습 없는 Gemma E4B의 MX를 회수했고 대조 형식 실패1개를 포함해 전체 분모로 집계했다. 형식 실패가 있으면 요청 없음 정답률 손실과 실제 오지목 증가를 따로 계산한다. [완료·집계 수정·같은 세트 비교 근거](../records/reports/2026-10-08_gemma-original-mx-completion.md).
''')
rel='final_project_cs/wiki/log.md';text=(ROOT/rel).read_text(encoding='utf-8')
save(rel,text.replace('# 문서 변경 이력 (cs)\n','# 문서 변경 이력 (cs)\n\n## 2026-10-08 — Gemma E4B 원본 MX 완료·형식 실패 지표 분리\n\n배열 출력1개를 실패로 보존하고, 실제 오지목 증가와 실패 포함 정답률 손실을 따로 집계했다. [완료·검증 리포트](records/reports/2026-10-08_gemma-original-mx-completion.md).\n',1))
save('final_project_cs/wiki/records/reports/2026-10-08_gemma-original-mx-completion.md','''# Gemma E4B 배포 원본 MX 완료 — 2026-10-08

우리 자료 추가 학습 없는 Gemma-4-E4B-it Q4_K_M(개발사 지시 학습)의 혼합·대조 답안4,014개를 보관했다. 형식 실패1개를 전체 분모와 오답에 포함해 집계했다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 답안 회수·문항 일치 | 완료 | 4,014/4,014 = 100% |
| 혼합 정상 요청 정답 | 실측 | 960/1,033 = 92.93% |
| 혼합 요청 없음 오지목 | 실측 | 154/974 = 15.81% |
| 사전 합산 기준 | 일부 통과 | 1/4 = 25% |

## 원본·실패·집계

[답안](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_mx/d_test_mx_backlog_e4bbase.jsonl) · [집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_mx/mx_counts.json) · [검증 및 원본 두 판 비교](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/e4bbase_mx/verification_and_pair_comparison.json).

로컬·GPU 서버 A 원본 SHA256은 `541960a76220dd7a9a38863218718074c462f6182256c6b3f80babdbd72ee29f`로 동일하다. 고정 입력 해시도 실행 시 기록과 같으며 입력 ID·정답·유형을 대조했다. 정상/요청 없음 혼합 문항은1,033/974개이며 각각 같은 수의 대조 문항이 있다.

대조 문항1201490의 `{"item": [9, 32]}`는 단일 번호 또는 null 계약에 맞지 않는다. null 정답으로 재해석하지 않고 전체 오답으로 보존했다. 미완료0, 해석 실패1이며 전부 분모에 남겼다. 요청 없음 대조 정답740개+오지목233개+형식 실패1개=974개다.

집계 도구의 오지목 증가 기준을 실제 오지목 계수 차이로 계산하도록 수정했다. 실패가 있으면 요청 없음 정답률 손실과 오지목 증가가 같지 않다: 이 실행은 각각−8.21%p와−8.11%p다. 오류가 없는 FrogNano 이전 집계에는 영향이 없고 기존 산출물을 다시 덮지 않았다. 누락·실패를 정답으로 세지 않는 직접 계수와 실패로 인한 정답률 변화가 실제 오지목으로 둔갑하지 않는 예제를 검증했다.

## 이 세트에서의 비교와 한계

Gemma 정상 요청 대조984/1,033에서 혼합960/1,033으로2.32%p 감소했다. 동일 일정59개 군집 부트스트랩2,000회·시드7의 감소95% 구간은1.28~3.30%p다. 지정 오지목 부류MX3·MX4·MX5a 기준은0/3 통과했다.

같은 혼합 문항에서 Gemma960/1,033 대 FrogNano898/1,033이며62개 차이(+6.00%p, 일정별95% 구간3.95~8.14%p)다. 오지목154/974 대167/974의13개 차이는 짝지은 검정p=0.1821·일정별 구간이0을 포함하므로 우열을 확정하지 않는다.

두 배포 원본 모두 우리 학습은 없으며 개발사 학습 역할은 Gemma 지시 학습·FrogNano 코딩 강화학습으로 다르다. Gemma는Q4_K_M, FrogNano 양자화는 이번 비교에서 검증하지 않았다. 따라서 이 저장된 배포판·한 세트의 관측 차이이며 같은 정밀도 아키텍처 비교나 일반 우열·전체 상위권 판정이 아니다. 모델 실행1회와 부트스트랩2,000회는 서로 다른 반복이다. 기존 개발/회귀 자료이며 독립 보류·모델 반복 실행 검증은 남아 있다. 토큰 확률과 말로 한 확신도·다른 실행 경로의 지연도 구분한다.

## 실행 유지·문서·백업

GPU 서버 A는 다음 원본 Gemma D평가를 시작했고 준비된 평가12개가 남아 있다. GPU 서버 B의 기존 Winnow-E4B 학습과 뒤 예약4개를 유지했다. 이중2개는 기반 다운로드 준비가 필요하며 공간은 다음 다운로드 직전에 재확인한다. 실행기를 추가하거나 기존 작업을 중단·반복하지 않았다. 완료 어댑터는 이번 관측에서 새로 발견되지 않았다.

일일 Markdown/JSON·GPU 상태·평가 wiki·cs wiki log를 동일 근거로 연결했다. 집계 도구 수정 전 판은 [도구 백업](../../../../program/scripts/plan_qa_bench/_backup/2026-10-08_1051_mx_failure_metrics/)에 보관했다. 다른 수정 직전 판:

'''+''.join('- ['+p+'](../../../../'+p+')\n' for p in backups))
print(json.dumps({'archived':4014,'failed_format':1,'aggregate_gates':[1,4],'ready_A':len(ac['ready']),'ready_B_with_auto_download':4,'report':'final_project_cs/wiki/records/reports/2026-10-08_gemma-original-mx-completion.md'},ensure_ascii=True))
