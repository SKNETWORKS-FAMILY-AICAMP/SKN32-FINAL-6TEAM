"""첫 실행 실패를 보존하고 별도 수정 시도 등록만 정본에 기록한다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import hashlib
import shutil

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'program/scripts/plan_qa_bench/results/gpu_backlog_20261008'
repair = json.loads((BASE/'Valen_registration_attempt2_20261009.json').read_text())
runner = ROOT/'program/scripts/plan_qa_bench/server/queues/valen_native_eval_20261009_v2.py'
assert hashlib.sha256(runner.read_bytes()).hexdigest() == repair['runner_sha256']
assert repair['failed_a1_preserved']['status'] == 'failed'
assert repair['failed_a1_preserved']['saved'] == 0
assert repair['unstarted_main_relinked'] == 5
now = datetime.now(ZoneInfo('Asia/Seoul'))
stamp = now.strftime('%Y-%m-%d_%H%M%S_valen_environment_repair')
out = ROOT/'program/scripts/rag_gate/results/daily_20261009_selective_v1/valen_environment_repair_parent_verification.json'
assert not out.exists()
backups = []

def save(path, content):
    dest = path.parent/'_backup'/stamp/path.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    backups.append(str(dest.relative_to(ROOT)).replace('\\','/'))
    path.write_text(content, encoding='utf-8')

watch_path = ROOT/'program/research/daily_rag_slm/model_release_watchlist.json'
watch = json.loads(watch_path.read_text(encoding='utf-8'))
c = next(c for c in watch['candidates'] if c['repo_id']=='Valen-Team/Valen-0.8B')
c.update(status='Original17 files verified; first GPU smoke attempt failed before weight load due to environment selection; corrected separate a2 queued, main5 gated',
    failed_attempts=[dict(attempt=repair['repair_of'], saved=0, expected=12, exit_code=1,
        cause='Resolved python symlink confused virtual environment selection; failed before weight load',
        logs_preserved=True, failures_not_removed=True)],
    repaired_attempt=repair['new_attempt'], repair_registered_at_utc=repair['timestamp_utc'],
    repair_evidence='program/scripts/plan_qa_bench/results/gpu_backlog_20261008/Valen_registration_attempt2_20261009.json',
    runner_v2='program/scripts/plan_qa_bench/server/queues/valen_native_eval_20261009_v2.py',
    original_benchmark_state='a1 failure0/12 preserved; a2 GPU smoke pending; main0/9425 at repair registration')
watch['updated_at_kst']=now.isoformat()
save(watch_path,json.dumps(watch,ensure_ascii=False,indent=2)+'\n')
day_path = ROOT/'program/research/daily_rag_slm/2026-10-09.json'
day=json.loads(day_path.read_text(encoding='utf-8'))
day['Valen_queue'].update(failed_a1=repair['failed_a1_preserved'], cause=c['failed_attempts'][0]['cause'],
    current_attempt=repair['new_attempt'], repair_evidence=c['repair_evidence'],
    repair_registered_at_utc=repair['timestamp_utc'], GPU_load_passed=False)
day['measurement'].update(multi_item_role_collected_rows=3340, multi_item_role_planned_rows=5010,
    multi_item_role_collected_jobs=4, multi_item_role_planned_jobs=6)
day['updated_at_kst']=now.isoformat()
save(day_path,json.dumps(day,ensure_ascii=False,indent=2)+'\n')
report=ROOT/'final_project_cs/wiki/records/reports/2026-10-09_1015_daily-research-and-serving.md'
addition='''\n## 初回 연결 실패 보존과 수정 시도 — 10:26 KST\n\n첫 Valen 연결 시도는 가중치를 불러오기 전에 실행 환경 선택 오류로 종료했다. 시스템 Python과 가상환경 Python의 실행 파일 링크가 같은 곳을 가리켜 기존 판별이 가상환경을 구별하지 못했다. 첫 시도 답안0/12·종료코드1과 로그를 보존했다. 모델 정확도 저하나 GPU 메모리 실패로 해석하지 않는다.\n\n가상환경 prefix 판별과 연결 attempt 구분을 수정한 새 실행기 v2를 만들었다. 10:26:11 KST에 별도 a2 시도를 기존 worker에 등록하고, 아직 시작하지 않은 본5개에만 새 실행기 SHA를 연결했다. 설치·새 worker·진행 중 작업 중단은 없으며 성공 여부는 실제 GPU 연결 결과 회수 후 확인한다. 자동 반복 재시작이 아니다.\n\n복수 항목 역할 시험은 별도4설정의 답안3,340/3,340·파일 SHA20/20을 로컬로 보관했다. 전체 계획은6설정5,010호출이며 반복 호출을 고유 질문 수로 합치지 않는다.\n\n[수정 시도 등록·첫 실패](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/Valen_registration_attempt2_20261009.json) · [수정 실행기](../../../../program/scripts/plan_qa_bench/server/queues/valen_native_eval_20261009_v2.py) · [복수 항목 답안 회수 SHA](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/A_multi_items_completed_20261009_1024/verification.json) · [부모 검사·백업 목록](../../../../program/scripts/rag_gate/results/daily_20261009_selective_v1/valen_environment_repair_parent_verification.json).\n'''.replace('初回','첫')
save(report,report.read_text(encoding='utf-8')+addition)
md=ROOT/'program/research/daily_rag_slm/2026-10-09.md'
save(md,md.read_text(encoding='utf-8')+'\n첫 Valen GPU 연결 시도는 가중치 로드 전 실행 환경 판별 오류로 실패했습니다(답안0/12, 로그 보존). 원인 수정한 별도a2 등록과 미시작 본5개 연결을 완료했으며 GPU 성공·정확도는 대기입니다. [실패·수정 등록](../../scripts/plan_qa_bench/results/gpu_backlog_20261008/Valen_registration_attempt2_20261009.json).\n')
proof=dict(verified_at_kst=now.isoformat(), first_failure_preserved=True, saved=0, expected=12,
    new_attempt=repair['new_attempt'], runner_sha256=repair['runner_sha256'],
    registration_sha256=hashlib.sha256((BASE/'Valen_registration_attempt2_20261009.json').read_bytes()).hexdigest(),
    GPU_load_success_claimed=False, backups=backups)
out.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(proof,ensure_ascii=False))
