"""Connect the new six-hour evidence to its canonical daily and wiki owners."""
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S') + '_six_hour_2000'
report = 'final_project_cs/wiki/records/reports/2026-10-09_2000_six-hour-gpu-arm-report.md'
gpu_path = ROOT / 'program/research/daily_rag_slm/gpu_backlog_2026-10-09.json'
gpu = json.loads(gpu_path.read_text(encoding='utf-8'))
assert '1953' in json.dumps(gpu), 'Wait for the GPU agent final state'
gpu_report = gpu['report']
assert (ROOT / gpu_report).is_file()
backups = []

def write_existing(relative, value):
    p = ROOT / relative
    backup = p.parent / '_backup' / stamp
    backup.mkdir(parents=True, exist_ok=True)
    target = backup / p.name
    assert not target.exists()
    shutil.copy2(p, target)
    backups.append(backup.relative_to(ROOT).as_posix())
    p.write_text(value, encoding='utf-8')

daily_path = 'program/research/daily_rag_slm/2026-10-09.json'
daily = json.loads((ROOT / daily_path).read_text(encoding='utf-8'))
daily.setdefault('six_hour_status_history', []).append(daily['six_hour_status'])
daily['six_hour_status'] = {
    'recorded_at_kst': datetime.now().astimezone().isoformat(), 'report': report,
    'GPU_report': gpu_report, 'GPU_state': gpu_path.relative_to(ROOT).as_posix(),
    'GPU_parent_verification': 'program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/parent_recount.json',
    'ARM_state': 'program/research/daily_rag_slm/arm_serving_2026-10-09.json',
    'new_GPU_A_answers_collected': 19570, 'new_GPU_B_basic_answers_collected': 835,
    'GPU_hash_files_verified': 72, 'ARM_hash_files_verified': 8,
    'ARM_cache_completed_calls': 240, 'ARM_cache_planned_calls': 240,
    'ARM_cache_unique_questions': 60, 'ARM_ABBA_final': True,
    'ARM_cache_development_latency_gate_pass': True, 'independent_validation_pass': False,
    'product_adoption': False, 'full_service_deployment': False,
    'E_human_review': [0,158], 'Saluki_training_runs': [0,1],
    'backup': 'program/research/daily_rag_slm/_backup/' + stamp,
}
daily['updated_at_kst'] = daily['six_hour_status']['recorded_at_kst']
for new in [report, gpu_report]:
    if new not in daily['reports']: daily['reports'].append(new)
daily['measurement']['Valen_main_completed_rows'] = 9425
daily['measurement']['Valen_observation_scope'] = 'Previously completed full five suites; 14:00 report retains performance failure and contract-audit evidence, not a new completion at20:00'
daily['resume'] = [x for x in daily['resume'] if not x.startswith('Observe existing ARM Q8')]
daily['resume'].append('ARM cache ABBA complete240/240: do not repeat as independent accuracy; collect existing concurrent2 and seven pending profiles, verify context/tenant isolation before adoption')
daily['resume'].append('Use existing pinned B58 completed-adapter feeder after inspecting its PID/lock/state; do not start duplicate feeder or GPU workers')
write_existing(daily_path, json.dumps(daily, ensure_ascii=False, indent=2)+'\n')

appendices = {
 'program/research/daily_rag_slm/2026-10-09.md': '\n\n## 20시 6시간 회수와 캐시 교대 비교 완료\n\n새 FINCH 추가 평가18,850개와 cosine 비교 학습판을 보관했고 소진된 GPU 서버 A에 누락 평가를 보충했다. 같은 일정의 후속 질문 캐시가 개발 지연 기준을 통과했지만 새 일정 첫 요청·독립 검증·제품 채택은 남는다. 사람 검수와 Saluki 학습 조건 대기는 유지한다. [정기 보고](../../../'+report+') · [GPU 최종 관측·자동 공급 검증](../../../'+gpu_report+').\n',
 'program/research/daily_rag_slm/index.md': '\n- [20시 6시간 현황·캐시 교대 결과](../../../'+report+'): 추가 평가·학습판 회수와 GPU 작업 소진 보충, ARM 같은 문맥 재사용의 개발 진단 통과 및 독립 검증 대기를 연결합니다.\n',
 'final_project_cs/wiki/operations/arm-serving-queue.md': '\n`[실측 2026-10-09 저녁]` 같은 모델·같은 일정의 후속 질문 캐시 교대 진단을 모두 완료했고 사전 개발 지연 기준을 통과했다. 새 일정 첫 요청과 사용자 간 캐시 격리·독립 검증은 별도로 남으며 제품 채택이나 전체 서비스 배포 완료를 뜻하지 않는다. [전체 반복·자원·한계·회수 근거](../records/reports/'+Path(report).name+').\n',
 'final_project_cs/wiki/operations/gpu-work-queue.md': '\n`[보완 2026-10-09 저녁]` 완료 학습판의 누락 평가를 기존 단일 실행기에 공급하는 로컬 경로를 추가했다. 승인된 두 후속 학습판만 완료 레시피·파일 해시·고정 입력·역할 중복·여유 공간을 확인한 뒤 처리하고, 별도 파일 잠금으로 중복 공급을 막는다. 실패는 원인 검토 전 자동 재시도하지 않으며 기존 학습·평가 실행기를 중단하거나 추가로 띄우지 않는다. [실행·검증·현재 조건 대기](../records/reports/'+Path(gpu_report).name+').\n',
 'final_project_cs/wiki/quality/slm-model-evaluation.md': '\n`[실측 근거 추가 2026-10-09 저녁]` 두 번째 시드 FINCH의 추가 평가를 모두 보관했지만 사전 합산 기준 전체를 통과하지 못했다. 같은 모델 캐시의 개발 지연 진단 통과는 모델 정확도 향상·독립 검증·제품 채택과 분리한다. [유형별 분자/분모·반복·검수 상태](../records/reports/'+Path(report).name+').\n',
}
for relative, addition in appendices.items():
    previous = (ROOT / relative).read_text(encoding='utf-8')
    assert addition.strip() not in previous
    write_existing(relative, previous+addition)

log_path = 'final_project_cs/wiki/log.md'
old = (ROOT / log_path).read_text(encoding='utf-8')
entry = '\n## 2026-10-09 — 20시 완료 회수·자동 공급·ARM 캐시 교대 결과\n\n새 학습판 평가와 다음 비교 어댑터를 보관하고 소진된 GPU 서버 A를 기존 실행기로 보충했다. 승인된 후속 학습판의 자동 공급을 검증했으며 Oracle ARM의 같은 문맥 후속 질문 캐시 개발 진단 통과와 독립 검증 대기를 구분했다. [정기 설명·원본·백업](records/reports/'+Path(report).name+').\n'
write_existing(log_path, old.replace('\n## ', entry+'\n## ', 1))

report_path = ROOT / report
old = report_path.read_text(encoding='utf-8')
addition = '\n\n## 보충 뒤 최종 관측과 자동 공급\n\n[실측20:07:05KST] GPU 서버 A는 새 cosine D3 두 판720/720을 추가 완료해 이번 GPU 서버 A 회수는12세트19,570/19,570=100%다. 새 답안과 학습판 파일 SHA72/72 및 원본 문항ID집합·정답·유형19,570/19,570을 확인했다. GPU82%·D실행·준비7개이며 등록113개 중 완료103·과거실패2·실행1·준비7이다. 현재D 저장 수는 최종 관측에서 조회하지 않았다. [실측20:05:37KST] GPU 서버 B는 세 번째 시드 cosine270/654=41.28%·GPU94%·다음 FINCH1개다. 준비3개 목표에는 미달하며 공간·가중치·학습 호환 조건 대기4개군을 준비 완료로 세지 않는다. 최신 상세 관측·조건 대기와 숨김 로컬 공급 실행기·잠금·읽기 전용 스모크는 [GPU 최종 보고]('+Path(gpu_report).name+')를 따른다. 이 시점의 가동을 지난6시간 연속 사용률로 확대하지 않는다. [전체 원본 문항 대조](../../../../program/scripts/plan_qa_bench/results/gpu_management_20261009_1953/source_identity_verification.json).\n\n문서 수정 직전에 보존한 위치: '+ ' · '.join('['+str(i+1)+'번째 백업]('+str(Path(__import__('os').path.relpath(ROOT/b,report_path.parent))).replace('\\','/')+'/)' for i,b in enumerate(dict.fromkeys(backups))) +'. 과거 날짜 보고와 실패 시도는 보존했다.\n'
addition += '\n자동 공급의 읽기 전용 검사·변형 코드 구문·파일 잠금과 지속 프로세스를 확인했다. 승인된 B58 두 학습판은 아직 완료 대기이므로, 이 자동 공급 경로가 실제 완료 어댑터를 전송·등록하는 전체 과정은 아직 실증하지 않았다. 기존 수동 회수·등록 성공과 구분하고 첫 완료 때 검증한다.\n'
write_existing(report, old+addition)
out = ROOT / 'program/scripts/plan_qa_bench/results/heartbeat_20261009_1953_arm/document_update_verification.json'
assert not out.exists()
out.write_text(json.dumps({'report':report,'GPU_report':gpu_report,'backups':list(dict.fromkeys(backups)),'updated_files':list(appendices)+[daily_path,log_path,report]}, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
print(json.dumps({'updated':len(appendices)+3,'report':report,'GPU_report':gpu_report,'backup_groups':len(set(backups))},ensure_ascii=False))
