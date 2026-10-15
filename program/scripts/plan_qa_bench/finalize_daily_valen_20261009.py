"""실제 다운로드·등록 근거만 일일 정본에 연결한다. 모델 성능 완료는 표시하지 않는다."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'program/scripts/plan_qa_bench/results/gpu_backlog_20261008'
OUT = ROOT / 'program/scripts/rag_gate/results/daily_20261009_selective_v1/valen_registration_parent_verification.json'
assert not OUT.exists()
registration = json.loads((BASE / 'Valen_registration_20261009.json').read_text(encoding='utf-8'))
download = json.loads((BASE / 'Valen_download_verified_20261009.json').read_text(encoding='utf-8'))
cpu = json.loads((BASE / 'Valen_cpu_preflight_20261009.txt').read_text(encoding='utf-8'))
assert registration['worker_preserved'] and registration['current_child_preserved']
assert registration['main_expected'] == 9425 and len(registration['jobs']) == 6
assert sum(j['expected'] for j in registration['jobs'] if j['suite'] != 'smoke12') == 9425
assert len({j['id'] for j in registration['jobs']}) == 6
assert all(j['our_training'] is False for j in registration['jobs'])
assert all(j['dependency'] for j in registration['jobs'] if j['suite'] != 'smoke12')
assert download['status'] == 'verified' and len(download['hashes']) == 17
assert registration['model_sha256'] == download['hashes']['model.safetensors']
assert download['free_after'] >= 3 * 2**30
assert cpu['compiled'] == cpu['expected'] == 12 and cpu['max_tokens'] <= 32768
assert not cpu['weights_loaded'] and not cpu['GPU_used']
now = datetime.now(ZoneInfo('Asia/Seoul'))
stamp = now.strftime('%Y-%m-%d_%H%M%S_valen_registration_reconcile')
backups = []

def backup(path):
    dest = path.parent / '_backup' / stamp / path.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    backups.append(str(dest.relative_to(ROOT)).replace('\\', '/'))

def save_json(path, data):
    backup(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

watch_path = ROOT / 'program/research/daily_rag_slm/model_release_watchlist.json'
watch = json.loads(watch_path.read_text(encoding='utf-8'))
candidate = next(c for c in watch['candidates'] if c['repo_id'] == 'Valen-Team/Valen-0.8B')
candidate.update(
    status='Pinned original downloaded/SHA verified; CPU processor12/12 passed; GPU smoke queued and main5 dependency-waiting',
    weights_downloaded=True, weights_sha256=registration['model_sha256'],
    download_verified_files=17, download_expected_files=17,
    original_benchmark_state='GPU smoke0/12 and conditional main0/9425 at registration; not accuracy measured',
    required_next_action='Collect existing worker GPU smoke and conditional matched D3/E/H/D/D2; preserve failures; no duplicate launch; rank only after matched completion and repeat/holdout',
    download_verification=str((BASE / 'Valen_download_verified_20261009.json').relative_to(ROOT)).replace('\\', '/'),
    queue_registration=str((BASE / 'Valen_registration_20261009.json').relative_to(ROOT)).replace('\\', '/'),
    CPU_preflight=dict(compiled=12, expected=12, max_tokens=3816, weights_loaded=False, GPU_used=False),
    GPU_smoke_registered=1, main_conditionally_registered=5,
    queue_registered_at_utc=registration['timestamp_utc'],
    original_benchmark_completed=False, korean_travel_measured=False, upper_tier=None, product_adoption=False)
watch['updated_at_kst'] = now.isoformat()
save_json(watch_path, watch)

day_path = ROOT / 'program/research/daily_rag_slm/2026-10-09.json'
day = json.loads(day_path.read_text(encoding='utf-8'))
day['implementation'].update(Valen_original_download_SHA_verified=True,
    Valen_CPU_compile_passed=12, Valen_CPU_compile_expected=12,
    Valen_GPU_smoke_registered=1, Valen_main_conditionally_registered=5)
day['measurement'].update(Valen_GPU_smoke_completed=False, Valen_main_completed_rows=0,
    Valen_main_planned_rows=9425, Valen_observation_scope='Registration evidence only; CPU compilation is not GPU inference or accuracy')
day['Valen_queue'] = dict(evidence=candidate['queue_registration'], weight_verification=candidate['download_verification'],
    smoke_expected=12, main_expected=9425, GPU_inference_at_registration=0, conditional_main_jobs=5,
    original_without_our_training=True, publisher_decision_training=True,
    selection_probability='Native choice head; not token likelihood or verbal certainty',
    all_input_information_checked=9425, all_input_token_compile='running separately; GPU runner refuses oversize without truncation')
finch_report = 'final_project_cs/wiki/records/reports/2026-10-09_1010_finch-completion-and-multi-item-role.md'
if finch_report not in day['reports']: day['reports'].append(finch_report)
day['updated_at_kst'] = now.isoformat()
save_json(day_path, day)

report = ROOT / 'final_project_cs/wiki/records/reports/2026-10-09_1015_daily-research-and-serving.md'
text = report.read_text(encoding='utf-8')
text = text.replace('既存', '기존')
text = text.replace('기존 실행환경·코드9파일·라이선스 확인, 원본 시험 등록 준비', '원본17파일 SHA 확인, CPU12/12 통과, GPU 연결→본5개 조건부 등록')
text += '''\n## 새 원본 시험 등록 확인 — 10:22 KST\n\nValen-0.8B 배포 원본17파일의 SHA를 확인해 GPU 서버 A의 기존 공간에 보관했다. 가중치3,417,285,852바이트이며 회수 기록의 남은 공간4,408,303,616바이트는3GiB 보존 조건을 지켰다. 기존 실행환경에서 processor·Qwen3.5 코드 import·12문항 CPU 입력 변환이12/12 통과했다(최대3,816토큰). 가중치 GPU 로드와 실제 정확도 시험은 이 검사에 포함되지 않는다.\n\n10:21:45 KST에 실행 중 작업과 worker를 유지한 채 연결12문항과 D3→E(MX)→H→D→D2 본5개9,425문항을 기존 대기열에 백업·원자적 등록했다. 본 작업은 연결검사 성공 표시가 생기기 전 조건 대기다. 등록 당시 GPU 추론은0/12·본평가0/9,425이며 원본 상위권·추가 학습 대상·제품 채택을 확정하지 않는다. 전체 입력9,425개는 선택지 최대47개·정보 보존·정답 분리를 검사했고, 전체 실제 토큰 길이의 CPU 검사는 별도 실행 기록으로 회수한다. 단일 선택 API로 D 복합66개를 복수 항목 완전 정답이라고 집계하지 않는다.\n\n[등록 원본](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/Valen_registration_20261009.json) · [다운로드 SHA](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/Valen_download_verified_20261009.json) · [CPU 입력 변환](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/Valen_cpu_preflight_20261009.txt) · [native 답안 집계기](../../../../program/scripts/plan_qa_bench/backlog_valen_report.py) · [이번 정본 갱신 백업과 부모 검증](../../../../program/scripts/rag_gate/results/daily_20261009_selective_v1/valen_registration_parent_verification.json).\n'''
backup(report)
report.write_text(text, encoding='utf-8')

md = ROOT / 'program/research/daily_rag_slm/2026-10-09.md'
backup(md)
with md.open('a', encoding='utf-8') as f:
    f.write('\nValen-0.8B 원본 다운로드17/17·CPU 입력 변환12/12를 확인하고, GPU 연결검사와 조건부 본5평가를 기존 worker에 등록했습니다. 실제 정확도는 등록 시점0/9,425이며 상위권 판정은 대기합니다. [등록 근거](../../scripts/plan_qa_bench/results/gpu_backlog_20261008/Valen_registration_20261009.json) · [일일 리포트](../../../final_project_cs/wiki/records/reports/2026-10-09_1015_daily-research-and-serving.md).\n')

result = dict(verified_at_kst=now.isoformat(), downloads=17, downloads_expected=17,
    CPU_compiled=12, CPU_expected=12, GPU_load_completed=False,
    registered_jobs=6, registered_expected=6, main_expected=9425,
    queue_registered_at_utc=registration['timestamp_utc'],
    worker_and_current_job_preserved=True, backups=backups,
    evidence_SHA256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [BASE/'Valen_registration_20261009.json',BASE/'Valen_download_verified_20261009.json',BASE/'Valen_cpu_preflight_20261009.txt']})
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False))
