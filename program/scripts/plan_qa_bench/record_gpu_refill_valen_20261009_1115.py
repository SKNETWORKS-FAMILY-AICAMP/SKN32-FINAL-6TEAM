"""누락 역할 등록·완료 원본 회수 근거를 새 리포트와 GPU 상태에 연결한다."""
from pathlib import Path
from datetime import datetime, timezone
import copy, hashlib, json, math, re, shutil, statistics

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
RESULTS=HERE/'results/gpu_backlog_20261008'
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def write_new(path,data):
    with path.open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
def pct(n,d):return f'{n}/{d} = {100*n/d:.2f}%'
def quantile(values,q):
    values=sorted(values);point=(len(values)-1)*q;low=math.floor(point);high=math.ceil(point)
    return values[low]+(values[high]-values[low])*(point-low)

registration=read(RESULTS/'missing_multi_role_registration_20261009_1108.json')
archive=RESULTS/'A_valen_D3_E_completed_20261009_1110'
h_archive=RESULTS/'A_valen_H_completed_20261009_1113'
snapshot=read(h_archive/'snapshot.json');manifest=read(h_archive/'manifest.json')
b_snapshot=ROOT/'program/scripts/plan_qa_bench/results/utilization_check_20261009_1100/B_snapshot.json'
b=read(b_snapshot)
jobs=['valen_08b_original_d3_a1','valen_08b_original_mx_a1','valen_08b_original_h_a1']
counts={j:read(RESULTS/j/'native_counts.json') for j in jobs}
assert sum(c['expected'] for c in counts.values())==5690
assert all(c['saved']==c['expected'] and c['missing']==c['failed_or_unparsed']==0 for c in counts.values())
metrics={}
for j in jobs:
    rows=[json.loads(l) for l in (RESULTS/j/f'd_test_{j}.jsonl').read_text(encoding='utf-8').splitlines()]
    ms=[r['ms'] for r in rows];summary=read(RESULTS/j/'valen_summary.json')
    metrics[j]={'measured_call_count':len(ms),'latency_ms_mean':statistics.mean(ms),
        'latency_ms_p50':quantile(ms,.5),'latency_ms_p95':quantile(ms,.95),
        'latency_includes':'native predict, response validation and JSON serialization; excludes model load and network',
        'path':'native choice head; not directly comparable to JSON-generation engines',
        'max_gpu_allocated_bytes':summary['max_gpu_allocated'],
        'input_tokens_max':max(r['usage']['input_tokens'] for r in rows),
        'repetitions':1,'errors':0,'missing':0,'answer_sha256':counts[j]['answer_sha256']}
write_new(RESULTS/'Valen_D3_E_H_metrics_20261009_1115.json',metrics)

status_path=ROOT/'program/research/daily_rag_slm/gpu_backlog_2026-10-09.json'
previous=status_path.read_bytes();status=json.loads(previous)
stamp=datetime.now().strftime('%Y-%m-%d_%H%M%S')+'_gpu_refill_and_valen_completion'
backup=status_path.parent/'_backup'/stamp;backup.mkdir()
shutil.copy2(status_path,backup/status_path.name)
status['before_1100_missing_role_refill']={'A':copy.deepcopy(status['A']),'B':copy.deepcopy(status['B']),
    'conditional_work':copy.deepcopy(status.get('conditional_work',[])),
    'multi_items_role':copy.deepcopy(status.get('multi_items_role',{}))}
state=snapshot['state']['jobs'];running=[k for k,v in state.items() if v['status']=='running']
status['recorded_at_utc']=datetime.now(timezone.utc).isoformat()
status['A'].update(observed_at_utc=snapshot['observed_at_utc'],snapshot=str((h_archive/'snapshot.json').relative_to(ROOT)).replace('\\','/'),
    conditions=str((h_archive/'snapshot.json').relative_to(ROOT)).replace('\\','/'),gpu_snapshot=snapshot['GPU'].strip(),
    worker_pid=snapshot['worker_pid'],worker_restarted=False,manifest_jobs=len(manifest['jobs']),
    manifest_questions=sum(j['expected'] for j in manifest['jobs']),completed_jobs=sum(v['status'].startswith('completed') for v in state.values()),
    failed_jobs=sum(v['status']=='failed' for v in state.values()),running_jobs=running,
    running_answers_saved={k:state[k]['saved'] for k in running},running_saved_count_is_worker_launch_snapshot=True,
    ready_jobs=len(snapshot['ready']),ready_ids=snapshot['ready'],input_blocked_jobs=len(snapshot['blocked']),blocked_ids=snapshot['blocked'],
    filesystem_available_bytes=snapshot['available_bytes'],space_observed_at_utc=snapshot['observed_at_utc'],
    manifest_sha256=snapshot['manifest_sha256'],current_role_refill_audit=str((RESULTS/'missing_multi_role_registration_20261009_1108.json').relative_to(ROOT)).replace('\\','/'))
status['B'].update(observed_at_utc=b['observed_at_utc'],snapshot=str(b_snapshot.relative_to(ROOT)).replace('\\','/'),
    gpu_snapshot=b['gpu_snapshot'],active_training=b['active_training_variants'],training_steps_saved=480,
    training_steps_expected=654,prepared_training_jobs=3,space_observation_not_refreshed=True)
status['conditional_work']=[c for c in status.get('conditional_work',[]) if c.get('candidate')!='Valen-Team/Valen-0.8B']
status['scope'].update(new_model_download=True,new_model_download_definition='Valen original pinned weights downloaded earlier on 2026-10-09; no weights downloaded during this refill',new_model_download_this_refill=False)
status['multi_items_role'].update(registered_jobs=9,registered_questions=7515,expected=7515,completed_jobs=6)
status['multi_items_role']['refill_1100']={'registration':str((RESULTS/'missing_multi_role_registration_20261009_1108.json').relative_to(ROOT)).replace('\\','/'),
    'new_jobs':3,'new_questions':2505,'saved_at_refill':0,'expected':2505,'old_comparisons_repeated':False,'independent_holdout':False}
status['valen_original_execution'].update(completed_main_suites=3,completed_main_saved=5690,completed_main_expected=5690,
    main_expected=9425,active_main_saved={k:state[k]['saved'] for k in running},active_main_saved_is_launch_snapshot=True,
    main_complete=False,completion_archive=str(archive.relative_to(ROOT)).replace('\\','/'),
    H_completion_archive=str(h_archive.relative_to(ROOT)).replace('\\','/'),completion_SHA_verified=22,completion_SHA_expected=22,
    metrics=str((RESULTS/'Valen_D3_E_H_metrics_20261009_1115.json').relative_to(ROOT)).replace('\\','/'),
    latest_counts={j:str((RESULTS/j/'native_counts.json').relative_to(ROOT)).replace('\\','/') for j in jobs})
report_path=ROOT/'final_project_cs/wiki/records/reports/2026-10-09_1115_gpu-missing-multi-role-refill-and-valen-results.md'
status['refill_1100_report']=str(report_path.relative_to(ROOT)).replace('\\','/')
status['refill_1100_state_backup']=str(backup.relative_to(ROOT)).replace('\\','/')
tmp=status_path.with_suffix('.json.tmp')
assert status_path.read_bytes()==previous
with tmp.open('x',encoding='utf-8') as f:json.dump(status,f,ensure_ascii=False,indent=2)
tmp.replace(status_path)

d3=counts[jobs[0]];mx=counts[jobs[1]];h=counts[jobs[2]]
doc=f'''---
type: report
title: 누락 복수 항목 역할 예약 및 Valen 원본 완료 결과
description: 기존 GPU worker 대기열 보충과 완료 D3·E·H 답안의 SHA·실패 포함 분모 집계
status: draft
domain: travel
tags: [GPU, evaluation, SLM, native-choice]
---

# 누락 복수 항목 역할 예약 및 Valen 원본 완료 결과

GPU 서버 A는 계산을 이어가는 기존 worker에 누락된 복수 항목 시험 3개를 추가했습니다. Valen-0.8B 원본의 직접 선택·혼합 질의·함정 시험 3종은 모두 회수했지만 요청없는 문장 오지목이 많아 현재 결과로 채택할 수 없습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 누락 역할 등록 | 완료 | 3/3 = 100% |
| 새 역할 문항 실행 | 대기 | 0/2505 = 0% |
| Valen 완료 3종 답안 회수 | 완료 | 5690/5690 = 100% |
| 원격·로컬 파일 SHA 비교 | 통과 | 22/22 = 100% |
| Valen 전체 본 시험 | 진행 | 5690/9425 = 60.37% |

등록 관측 {registration['observed_at_utc']} (한국 시각 11:06:51), 최종 회수 관측 {snapshot['observed_at_utc']} (한국 시각 11:11:36)입니다. GPU 서버 A GPU {snapshot['GPU'].strip()}, 기존 worker PID {snapshot['worker_pid']} 유지·잠금 보존, Valen D 계산1개·준비4개(D2+새 역할3개)·입력 조건 대기0개입니다. 완료83개는 해석 실패를 포함한 완료 상태도 세며 별도 첫 연결 실패1개를 숨기지 않습니다. 공간 {snapshot['available_bytes']}bytes는 3GiB 보존 기준 이상이며 이번 작업은 모델을 받거나 삭제하지 않았습니다. worker state의 실행중 saved=0은 시작 시 기록이므로 현재 살아 있는 문항 수를 0이라고 단정하지 않습니다.

GPU 서버 B는 별도 11:01:30 관측에서 GPU100%, FINCH 두 번째 시드 480/654갱신, B57/B58 프로세스 유지·후속 학습3개입니다. 공간은 이전 관측값을 보존했으며 이번 프로세스 관측을 새 공간 측정으로 쓰지 않습니다. 짧은 GPU 표본으로 하루 종일 풀가동이라고 단정하지 않습니다.

새 예약은 우리 자료 학습 없는 Gemma-4-12B-it Q4_K_M, Jev 계열 모델 중 Winnow-E4B Q8_0 원본(우리 자료 학습 없음), Winnow-E4B Q8_0 기반 여행 학습판입니다. 각 835문항은 583단일·186요청없음·66복합이며 같은 일정과 질의를 유지하고 strict items 배열 출력 역할을 추가했습니다. 기존 전체 manifest에서 같은 모델·어댑터의 이 역할 누락을 대조했고, 기존 실행기에서 같은 입력 정보 835/835와 API 오류0도 확인했습니다. 이것은 완료 D/E의 재실행이나 새로운 독립 보류 시험이 아닙니다. 전체 모델2개·어댑터1개 SHA를 확인했으며 입력과 실행기 SHA도 고정했습니다. 기존 6설정 완료 5010개 뒤 범위를 9설정·7515개로 넓혔습니다. Valen의 단일 선택 API를 복수 항목 C 정답으로 바꾸지 않았습니다.

| Valen 원본 시험 | 정상 요청 정답 | 요청없음 오지목 | 실패·미완료 |
|---|---:|---:|---:|
| D3 직접 선택 | {d3['positive']['correct']}/120 | {d3['negative']['false_pick']}/240 | 0/360 |
| E(MX) 실제 질의가 섞인 평문 | {mx['mixed_positive']['correct']}/1033 | {mx['mixed_negative']['false_pick']}/974 | 0/4014 |
| H 함정·대조 | {h['positive']['correct']}/461 | {h['negative']['false_pick']}/855 | 0/1316 |

E는 2007쌍·4014개 답안이며 mixed쪽 1033정상+974요청없음과 같은 문항의 control쪽을 별도로 셉니다. 대조 정답389/1033, mixed정답266/1033, 정상 선택손실11.9071%p, 대조 오지목974/974, mixed오지목968/974로 사전 기준1/4만 통과했습니다. 실패·미완료는 모든 고정 분모에 남기며 선택지 ID·확률합·유한값·원문 응답과 pick 일치·정답 메타데이터도 다시 검증했습니다.

Valen은 개발사 결정 SFT가 있는 배포 원본이며 우리 자료 추가 학습이 없습니다. 고정 revision 3bf3e6d6318385884bf85e38dea1ca59afdf93f1, 가중치 SHA465714dd28702c4232d9233c2a2157d366967c541b2a27d9dadccc816304fd48입니다. 확률은 native choice head 출력이며 다음 토큰 확률·말로 한 확신도와 다릅니다. 아래 지연은 모델 로드와 네트워크를 제외한 predict·응답검사·직렬화 구간으로 일반 JSON 생성 경로와 직접 속도 비교하지 않습니다. 기존 개발·회귀 자료 각1회이고 전체 본 시험·최종 순위는 아직 완료가 아닙니다.

| 시험 | 지연 p50 / p95 | 최대 GPU 할당 | 호출 |
|---|---:|---:|---:|
'''
for j,label in zip(jobs,['D3','E(MX)','H']):
    x=metrics[j];doc+=f"| {label} | {x['latency_ms_p50']:.1f} / {x['latency_ms_p95']:.1f}ms | {x['max_gpu_allocated_bytes']}bytes | {x['measured_call_count']}/{x['measured_call_count']} |\n"
doc+='''
근거·재개:
- [등록 감사·원격 manifest 수정 직전 백업](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/missing_multi_role_registration_20261009_1108.json)
- [누락 역할·동일835 입력 대조](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/multi_role_missing_preflight_20261009_1105.json)
- [D3/E 원본 전체 SHA14/14](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_valen_D3_E_completed_20261009_1110/verification.json)
- [H 원본 전체 SHA8/8](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_valen_H_completed_20261009_1113/verification.json)
- [D3 native 집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/valen_08b_original_d3_a1/native_counts.json)
- [E native 집계·쌍 대조·사전 기준](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/valen_08b_original_mx_a1/native_counts.json)
- [H native 집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/valen_08b_original_h_a1/native_counts.json)
- [실측 지연·메모리·원본 SHA](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/Valen_D3_E_H_metrics_20261009_1115.json)
- [기존 worker 실제 계산·새 준비 대기·공간](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_valen_H_completed_20261009_1113/snapshot.json)
- [GPU 서버 B 별도11시 관측](../../../../program/scripts/plan_qa_bench/results/utilization_check_20261009_1100/B_snapshot.json)
- [누락 역할 원자 등록 코드](../../../../program/scripts/plan_qa_bench/server/queues/refill_missing_multi_roles_20261009_1100.py)
- [완료 원본 읽기 전용 회수 코드](../../../../program/scripts/plan_qa_bench/server/queues/recover_valen_completed_20261009_1110.py)
'''
doc+=f'\n[GPU 상태 수정 직전 로컬 백업](../../../../{backup.relative_to(ROOT).as_posix()}/{status_path.name})을 남겼습니다. 기존 worker는 Valen D→D2 뒤 새3역할을 자동 실행합니다. 완료 답안을 새 이름으로 회수한 뒤 backlog_multi_items_report.py로 strict B/C 고정 분모를 집계하며 실패한 작업을 원인 수정 없이 반복하지 않습니다. 공유 wiki·날짜 기록은 부모 작업이 연결합니다.\n'
with report_path.open('x',encoding='utf-8') as f:f.write(doc)
links=re.findall(r'\]\(([^)]+)\)',doc);assert all((report_path.parent/p).resolve().exists() for p in links)
proof={'report_links_checked':len(links),'report_links_expected':len(links),
    'new_jobs_registered':3,'new_questions_registered':2505,'existing_worker_preserved':True,
    'A_ready':len(snapshot['ready']),'A_blocked':len(snapshot['blocked']),
    'completed_native_answers_verified':5690,'expected_completed_native_answers':5690,
    'archive_SHA':22,'archive_SHA_expected':22,'report':report_path.relative_to(ROOT).as_posix(),
    'observed_at_utc':snapshot['observed_at_utc'],'model_or_environment_changed_this_refill':False}
write_new(RESULTS/'gpu_refill_valen_20261009_1115_verification.json',proof)
print(json.dumps(proof,ensure_ascii=False))
