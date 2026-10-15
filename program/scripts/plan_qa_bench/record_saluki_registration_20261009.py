"""Reconcile verified download/queue evidence into shared candidate and daily state."""
import json
import shutil
from datetime import datetime
from pathlib import Path

root = Path(__file__).resolve().parents[3]
evidence = root / 'program/scripts/plan_qa_bench/results/saluki_preflight_20261009'
download = json.loads((evidence/'download_verified_A_20261009.json').read_text(encoding='utf-8'))['state']
queue = json.loads((evidence/'queue_registered_A_20261009.json').read_text(encoding='utf-8'))
assert download['status'] == 'verified'
assert download['bytes_saved'] == download['expected_bytes']
assert download['sha256'] == download['expected_sha256'] == queue['model_sha256']
assert queue['smoke_registered'] == 1 and queue['main_conditionally_registered'] == 5
assert sum(j['expected'] for j in queue['jobs'] if j['suite'] != 'smoke12') == 9425
assert queue['canonical_smoke_ids_gold_type_prompt_match'] == [12, 12]
stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S') + '_saluki_download_and_queue'


def update(relative, transform):
    p = root/relative
    old = p.read_text(encoding='utf-8')
    new = transform(old)
    if old == new:
        return
    backup = p.parent/'_backup'/stamp
    backup.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, backup/p.name)
    p.write_text(new, encoding='utf-8')
    print((backup/p.name).relative_to(root).as_posix())


def candidates(s):
    obj = json.loads(s)
    candidate = next(x for x in obj['candidates'] if x['repo_id'] == 'ConwayResearch/Underdog-Saluki-27B-1.0')
    candidate.update(
        status='weights_downloaded_and_SHA_verified; existing_worker_smoke_queued; five_main_suites_smoke_gated',
        weights_downloaded=True, whole_weights_sha256_verified=True,
        weight_verification_evidence='program/scripts/plan_qa_bench/results/saluki_preflight_20261009/download_verified_A_20261009.json',
        gpu_runner_compatibility_verified=False, korean_travel_measured=False,
        queue_evidence='program/scripts/plan_qa_bench/results/saluki_preflight_20261009/queue_registered_A_20261009.json',
        weight_storage={'type': 'existing GPU A RAM filesystem, ephemeral',
                        'permanent_copy_status': 'pending; local PC free space insufficient',
                        'loss_on_restart_possible': True},
        registered_jobs=[x['id'] for x in queue['jobs']],
        main_expected_rows=9425, main_completed_rows=0,
        smoke_expected_rows=12, smoke_completed_rows=0,
        required_next_action='Observe existing worker without duplicate launch; collect smoke answers and source engine log; five main suites become ready only after 12 parsed responses and zero API errors. Archive verified weights on existing persistent space. Collect all original answers and strict full-denominator summaries; no product adoption from development score alone.',
    )
    return json.dumps(obj, ensure_ascii=False, indent=2)+'\n'


def daily(s):
    obj = json.loads(s)
    obj['implementation'].update(Saluki_weights_downloaded_and_SHA_verified=True,
                                 Saluki_smoke_job_registered=1, Saluki_main_jobs_conditionally_registered=5)
    obj['Saluki_queue'] = {
        'smoke_completed_rows': 0, 'smoke_expected_rows': 12,
        'main_completed_rows': 0, 'main_expected_rows': 9425,
        'state': 'Registered with existing worker, awaiting serial execution and successful smoke gate',
        'evidence': 'program/scripts/plan_qa_bench/results/saluki_preflight_20261009/queue_registered_A_20261009.json',
        'weight_verification': 'program/scripts/plan_qa_bench/results/saluki_preflight_20261009/download_verified_A_20261009.json',
        'runner': 'program/scripts/plan_qa_bench/server/queues/saluki_eval_20261009.py',
        'weight_persistence': 'GPU A ephemeral RAM copy; persistent copy pending',
    }
    obj['resume'] = [x for x in obj['resume'] if not x.startswith('Saluki:') and not x.startswith('After resource')]
    obj['resume'].insert(2, 'Saluki is already downloaded, SHA verified and registered: never duplicate smoke or main jobs; read queue evidence and raw worker state, collect smoke then D3/E/H/D/D2 outputs. Main readiness is conditional on smoke success.')
    obj['resume'].insert(3, 'Saluki RAM filesystem is ephemeral: complete persistent archiving inside existing space, verify the same SHA, and preserve failed attempts before any explicit repair.')
    return json.dumps(obj, ensure_ascii=False, indent=2)+'\n'


update('program/research/daily_rag_slm/model_release_watchlist.json', candidates)
update('program/research/daily_rag_slm/2026-10-09.json', daily)


def daily_text(s):
    s = s.replace('Saluki는 가중치 보관·설치 실행기 스모크·여행 평가를 완료하지 않았으며 준비된 GPU 작업 수에 포함하지 않는다.',
                  'Saluki 가중치는 GPU 서버 A의 기존 임시 메모리 공간에 받아 전체 SHA를 확인했다. 연결검사와 본 평가는 기존 실행기에 등록돼 대기하며, 실행기 호환과 여행 성능은 실제 답안으로 확인해야 한다. 임시 원본은 재시작 시 사라질 수 있어 기존 영구 공간 보관을 이어간다.')
    marker = '## Saluki 다운로드와 순차 시험 등록'
    if marker not in s:
        s += '\n'+marker+'\n\n약 7.9GB의 고정 원본과 전체 파일 해시를 확인하고 기존 GPU 실행기에 연결검사 및 성공 조건이 걸린 본 평가를 등록했다. 실제 Saluki 답안은 아직 대기하며 설치·등록을 정확도 시험 완료로 표시하지 않는다. [다운로드 검증](../../scripts/plan_qa_bench/results/saluki_preflight_20261009/download_verified_A_20261009.json) · [실행 등록 근거](../../scripts/plan_qa_bench/results/saluki_preflight_20261009/queue_registered_A_20261009.json).\n\n[수정 직전 후보·날짜 기록 백업](_backup/'+stamp+'/).\n'
    return s


update('program/research/daily_rag_slm/2026-10-09.md', daily_text)
update('program/research/daily_rag_slm/index.md', lambda s: s.replace('GPU 대기열 보충·Saluki 선택 검토, 전체 논문 조사와 모델 실측은 대기',
       'GPU 대기열 보충·Saluki 다운로드와 시험 등록·E 구성 감사, 전체 논문 조사와 모델 실측은 대기'))
print('BACKUP_STAMP='+stamp)
