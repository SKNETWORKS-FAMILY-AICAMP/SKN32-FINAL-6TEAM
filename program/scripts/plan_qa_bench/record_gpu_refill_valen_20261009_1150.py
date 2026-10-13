"""새 완료·로드 전 실패·명시적 수정 예약을 별도 기록으로 보존한다."""
from pathlib import Path
from datetime import datetime,timezone
import copy,hashlib,json,re,shutil,sys
from backlog_mx_report import summarize

ROOT=Path(__file__).resolve().parents[3]
R=ROOT/'program/scripts/plan_qa_bench/results/gpu_backlog_20261008'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def new(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2)
failed=R/'valen_08b_original_d2_a1';started=read(failed/'started.json')
goldpath=ROOT/'datasets/travel/valen_native_eval_20261009/d2.json'
assert hashlib.sha256(goldpath.read_bytes()).hexdigest()==started['prompt_sha256']
gold=read(goldpath);assert len(gold)==1000 and not (failed/'d_test_valen_08b_original_d2_a1.jsonl').exists()
new(failed/'failed_preload_counts.json',dict(expected=1000,saved=0,missing=1000,failed_or_missing=1000,
    full=summarize(gold,{}),loaded_model=False,API_calls=0,preload_failure=1,
    log_sha256=hashlib.sha256((failed/'job.log').read_bytes()).hexdigest(),prompt_sha256=started['prompt_sha256'],
    failure='Raw cgroup headroom threshold included reclaimable ordinary file cache',
    replacement_attempt='valen_08b_original_d2_a2',previous_failure_preserved=True,accuracy_failure=False,
    failures_removed_from_denominator=False,final_ranking=False))
a=read(R/'A_snapshot_refill1140_20261009.json');cond=read(R/'A_conditions_refill1140_20261009.json')
b=read(R/'B_snapshot_hb1135_20261009.json');m=a['manifest'];s=a['state']['jobs']
running=[k for k,v in s.items() if v['status']=='running'];steps=re.findall(r'step (\d+)/(\d+)',b['logs'][b['active_training_log']])[-1]
registration=read(R/'qat_multi_role_registration_20261009_1140.json');retry=read(R/'Valen_D2_attempt2_registered_20261009_1140.json')
d=read(R/'valen_08b_original_d_a1/native_counts.json')
g12=read(R/'g12bbase_multi_items_bc_a1/multi_items_counts.json')
w=read(R/'winnow_original_multi_items_bc_a1/multi_items_counts.json')
assert d['saved']==d['expected']==2735 and g12['metadata_matches']==w['metadata_matches']==835
statuspath=ROOT/'program/research/daily_rag_slm/gpu_backlog_2026-10-09.json';before=statuspath.read_bytes();status=json.loads(before)
stamp=datetime.now().strftime('%Y-%m-%d_%H%M%S')+'_gpu_refill_valen_D2_failure'
backup=statuspath.parent/'_backup'/stamp;backup.mkdir();shutil.copy2(statuspath,backup/statuspath.name)
status['before_1130_followup']={'A':copy.deepcopy(status['A']),'B':copy.deepcopy(status['B'])}
def relative(p):return p.relative_to(ROOT).as_posix()
status['recorded_at_utc']=datetime.now(timezone.utc).isoformat()
status['A'].update(observed_at_utc=a['observed_at_utc'],snapshot=relative(R/'A_snapshot_refill1140_20261009.json'),
    conditions=relative(R/'A_conditions_refill1140_20261009.json'),gpu_snapshot=a['gpu_snapshot'],worker_pid=a['worker_pid'],
    worker_restarted=False,manifest_jobs=len(m['jobs']),manifest_questions=sum(j['expected'] for j in m['jobs']),
    completed_jobs=sum(v['status'].startswith('completed') for v in s.values()),failed_jobs=sum(v['status']=='failed' for v in s.values()),
    running_jobs=running,running_answers_saved={k:sum(v for p,v in a['answers'].items() if p.startswith(k+'/d_test_')) for k in running},
    running_saved_count_is_worker_launch_snapshot=False,ready_jobs=len(cond['ready']),ready_ids=cond['ready'],
    input_blocked_jobs=len(cond['blocked']),blocked_ids=cond['blocked'],filesystem_available_bytes=cond['temp_space']['available_bytes'],
    space_observed_at_utc=cond['observed_at_utc'],manifest_sha256=retry['manifest_sha256'])
status['B'].update(observed_at_utc=b['observed_at_utc'],snapshot=relative(R/'B_snapshot_hb1135_20261009.json'),
    gpu_snapshot=b['gpu_snapshot'],active_training=b['active_training_variants'],training_steps_saved=int(steps[0]),
    training_steps_expected=int(steps[1]),prepared_training_jobs=3,space_observation_not_refreshed=True)
status['multi_items_role'].update(registered_jobs=12,registered_questions=10020,expected=10020,completed_jobs=8)
status['multi_items_role']['refill_1130']={'new_jobs':3,'new_questions':2505,'audit':relative(R/'qat_multi_role_registration_20261009_1140.json'),
    'old_comparisons_repeated':False,'independent_holdout':False,'additional_completed':{
        'g12bbase_multi_items_bc_a1':relative(R/'g12bbase_multi_items_bc_a1/multi_items_counts.json'),
        'winnow_original_multi_items_bc_a1':relative(R/'winnow_original_multi_items_bc_a1/multi_items_counts.json')}}
status['valen_original_execution'].update(completed_main_suites=4,completed_main_saved=8425,completed_main_expected=8425,
    main_expected=9425,main_complete=False,active_main_saved={},D2_first_attempt_failed=True,D2_first_attempt_missing=1000,
    D2_failed_preload_counts=relative(failed/'failed_preload_counts.json'),D2_replacement_attempt='valen_08b_original_d2_a2',
    D2_replacement_registration=relative(R/'Valen_D2_attempt2_registered_20261009_1140.json'),
    D2_guard_tests=relative(R/'Valen_D2_memory_guard_v3_tests_20261009_1140.json'),
    D2_replacement_is_pending=True,first_failure_not_repeated_without_fix=True)
status['valen_original_execution']['latest_counts']['valen_08b_original_d_a1']=relative(R/'valen_08b_original_d_a1/native_counts.json')
report=ROOT/'final_project_cs/wiki/records/reports/2026-10-09_1150_gpu-refill-valen-d2-failure-and-winnow-role.md'
status['refill_1130_report']=relative(report);status['refill_1130_backup']=relative(backup)
temp=statuspath.with_suffix('.json.tmp');assert statuspath.read_bytes()==before
with temp.open('x',encoding='utf-8') as f:json.dump(status,f,ensure_ascii=False,indent=2)
temp.replace(statuspath)
doc=f'''---
type: report
title: GPU 누락 역할 보충·Valen 로드 전 실패 수정·Winnow 역할 완료
description: 기존 worker 가동 확인과 원본 보존 및 별도 수정 attempt 예약
status: draft
domain: travel
tags: [GPU, SLM, evaluation, memory]
---

# GPU 누락 역할 보충·Valen 로드 전 실패 수정·Winnow 역할 완료

GPU 서버 A는 기존 worker로 유효 시험을 계산 중이며 부족해진 후속 일을 보충했습니다. Valen의 요청없음 시험은 로드 전 메모리 검사에서 멈춰 실패 원본을 보존하고 수정한 별도 시도를 예약했습니다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| 누락 QAT 여행 학습판 복수 역할 등록 | 완료 | 3/3 = 100% |
| 새 완료 Valen D·원본 복수 역할 답안 회수 | 완료 | 4405/4405 = 100% |
| 이번 회수 원격·로컬 SHA 비교 | 통과 | 22/22 = 100% |
| Valen D2 첫 시도 | 로드 전 실패 | 0/1000 = 0% |
| 수정 메모리 검사 CPU 확인 | 통과 | 5/5 = 100% |
| 수정 D2 별도 시도 | 예약 | 0/1000 = 0% |

GPU 서버 A 최종 실제 관측 {a['observed_at_utc']}, GPU{a['gpu_snapshot']}, 기존 worker PID{a['worker_pid']} 유지·Winnow-E4B 여행 학습판 복수 역할 계산1개입니다. 조건 관측 {cond['observed_at_utc']}에서 준비4개(QAT oos1·oos3·oos2r 누락 복수 역할+수정 Valen D2 a2), 입력 대기0개, 저장공간{cond['temp_space']['available_bytes']}bytes를 확인했습니다. 11:32의 GPU0%가 지속되는 유휴 상태는 아니었고, 11:33·11:40에는 실제 계산을 확인했습니다. 짧은 관측으로 장시간 연속 가동을 단정하지 않습니다. GPU 서버 B는 {b['observed_at_utc']}에 GPU{b['gpu_snapshot']}·FINCH seed20261013 {steps[0]}/{steps[1]}갱신, 기존 B57/B58와 후속3개를 유지했습니다. 공간은 이전 기록으로 구분합니다.

추가 QAT 학습판 3개는 각835문항(583단일·186요청없음·66복합), 동일 strict items 배열·64출력·기존 엔진 역할입니다. 이미 끝난 단일 D/E를 다시 실행하거나 자료를 바꾸지 않았습니다. 모델·어댑터 전체 SHA, 입력·실행기 SHA, 기존 엔진의 해당 기반·어댑터 완료 실행을 확인한 뒤 manifest 수정 직전 백업·원자 교체했습니다. 새로운 모델 다운로드·worker·임대·기존 모델 삭제는 없습니다.

| 새 완료 판 | 정상 요청 정답 / B | 요청없음 오지목 / C | 복합 C | 실패·미완료 |
|---|---:|---:|---:|---:|
| Valen-0.8B 원본 단일 D | 531/883 | 1776/1786 | 단일 진단66 | 0/2735 |
| Gemma-4-12B-it 원본 strict 복수 역할 | B789/835 | C696/835·오지목22/186 | 57/66 | 0/835 |
| Winnow-E4B 원본 strict 복수 역할 | B775/835 | C647/835·오지목14/186 | 42/66 | 20/835 |

Valen은 우리 추가 학습 없음·개발사 결정 SFT 있음이며 D 복합66은 복수 C 정답으로 세지 않습니다. Gemma12B 원본은 우리 추가 학습이 없고, Winnow-E4B 원본은 Jev 계열 결정 모델의 배포 원본이며 우리 추가 학습이 없습니다. 복수 역할 B는 정답을 하나 이상 고르거나 요청없음에서 빈 목록을 맞춘 수, C는 전체 항목 집합을 정확히 맞춘 수입니다. Winnow 원본의 형식실패20개는835 고정 분모에 포함해 오답으로 셌습니다. 기존 알려진 자료 각1회이므로 독립 보류 검증·최종 순위·모델 채택은 아직 아닙니다.

Valen D2 a1의 실패 위치는 v2 main의 cgroup headroom>4GiB 검사였습니다. 모델 로드·API 호출 전 0개 저장·1000개 미실행이며 정확도 오답이나 실제 OOM으로 분류하지 않습니다. 11:36:56 실측 cgroup 사용30985519104/제한30999998464bytes, rss1274036224bytes·cache29352660992bytes 중 shmem7948734464bytes, ordinary inactive_file8232615936+active_file13171298304bytes, failcnt0·OOM kill0입니다. 사용량에 회수 가능한 일반 파일캐시를 포함해 로드 전 검사가 보수적으로 멈췄습니다.

v3는 직접 여유4GiB 경로를 유지하고 shmem·익명 메모리를 제외한 일반 파일캐시만 보수적으로 차감해 여유8GiB 이상인 경로를 추가했습니다. 실제 cgroup 한도·모델·추론 수학·정답·입력·확률·출력 계약은 바꾸지 않았습니다. GPU idle 검사와 원본 전체 SHA 검사도 유지했습니다. CPU 경계5/5를 확인하고 별도 D2 a2를 기존worker 뒤에 등록했으며 아직 로드 성공으로 표시하지 않습니다. 첫 시도의 로그·시작 기록과1000 미실행 분모는 보존했습니다. 재시도는 캐시를 감안한 메모리 여유가 부족하면 다시 실패를 보존합니다. 실패작업을 무조건 재시작하거나 Saluki RAM 모델을 지우지 않습니다.

후보 학습 상태는 Winnow-E4B 여행 QLoRA 완료·HF/GGUF 보관 및 기본835개 완료, Spark-S1-4B-v6 여행 QLoRA 완료·HF/GGUF 보관 및 기본835개 완료, Jevify-Gemma4-E4B는 다운로드 미완료 후 가중치 없음으로 학습 연결검사 실패입니다. Spark의 고정 공식 카드와 config를 전체 확인했습니다. TypeSafe Jev/System One에 영감을 받은 독립 구현이며 TypeSafe 제휴 모델이 아닙니다. 기반 Qwen/Qwen3.5-4B, Qwen3_5ForCausalLM이며, 원본 계약은 선택지 문자 토큰 로짓을 제한하고 fitted temperature로 보정하는 결정 경로입니다. 공식 Jev 제품과 구분하고, 현재 우리 JSON 생성 학습·평가와 원본 선택지 점수 경로도 구분합니다. 공개 카드 점수를 우리 여행 실측으로 옮기지 않습니다.

근거·재개:
- [실제 A 계산 스냅샷](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_snapshot_refill1140_20261009.json)
- [실제 A 준비4·공간 조건](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_conditions_refill1140_20261009.json)
- [B 별도 실제 학습 관측](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/B_snapshot_hb1135_20261009.json)
- [QAT 누락3개·전체 SHA·manifest 백업](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/qat_multi_role_registration_20261009_1140.json)
- [새 완료 D·D2 실패·Gemma12B 원본 회수 SHA15/15](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_valen_D_D2_multi_completed_20261009_1135/verification.json)
- [Winnow 원본 복수 회수 SHA7/7](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_winnow_original_multi_completed_20261009_1142/verification.json)
- [Valen D 단일 집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/valen_08b_original_d_a1/native_counts.json)
- [Gemma12B 복수 집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/g12bbase_multi_items_bc_a1/multi_items_counts.json)
- [Winnow 원본 복수 집계·실패20개](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_original_multi_items_bc_a1/multi_items_counts.json)
- [D2 첫 실패·1000 미실행 고정 분모](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/valen_08b_original_d2_a1/failed_preload_counts.json)
- [cgroup 실제 메모리·캐시·OOM](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/Valen_D2_memory_failure_preflight_20261009_1140.json)
- [수정 메모리 검사5/5·새 실행기 SHA](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/Valen_D2_memory_guard_v3_tests_20261009_1140.json)
- [별도 D2 a2 등록·manifest 백업](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/Valen_D2_attempt2_registered_20261009_1140.json)
- [수정 v3 실행기](../../../../program/scripts/plan_qa_bench/server/queues/valen_native_eval_20261009_v3.py)
- [Spark 고정 공식 카드·구조 SHA](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/publisher_family_status_20261009_1145/official_source.json)
- [Winnow 여행 학습판 기본835 집계](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/winnow_e4b_oos_training_1308/basic_scores_1328.json)
- [Spark HF/GGUF 보관](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/adapters_archived_20261009_0115.json)
- [Jevify 학습 연결 실패 원문](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/B_completed_20261009_0121/qlora_smoke_jevify_e4b_oos.log)
'''
doc+=f'\n[GPU 상태 수정 직전 백업](../../../../{relative(backup)}/{statuspath.name})을 남겼습니다. 기존 worker의 현재 Winnow 여행 학습판 완료 뒤 QAT3개와 별도 D2 a2가 자동 이어집니다. 완료 답안은 즉시 새 폴더로 회수해 같은 고정 자료·실패 포함 분모로 집계합니다. 날짜·후보 정본·wiki/log는 부모가 별도로 연결합니다.\n'
with report.open('x',encoding='utf-8') as f:f.write(doc)
links=re.findall(r'\]\(([^)]+)\)',doc);assert all((report.parent/p).resolve().exists() for p in links)
new(R/'gpu_refill_1130_20261009_verification.json',dict(links_checked=len(links),links_expected=len(links),
    recovered_completed_saved=4405,recovered_completed_expected=4405,archive_SHA=22,archive_SHA_expected=22,
    A_worker_preserved=True,A_ready=4,new_role_jobs=3,explicit_corrected_attempts=1,
    new_worker=False,new_weights_downloaded=False,failed_D2_missing_preserved=1000,
    report=relative(report),observation=a['observed_at_utc']))
sys.stdout.reconfigure(encoding='utf-8');print(json.dumps({'report':relative(report),'links_verified':len(links),'ready':4,'B_steps':steps},ensure_ascii=False))
