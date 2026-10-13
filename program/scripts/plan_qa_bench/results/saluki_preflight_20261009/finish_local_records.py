"""GPU 보충 리포트를 날짜 기록과 wiki 정본에 연결한다. 기존 파일은 직전에 백업한다."""
import json
import re
import shutil
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
DAY = ROOT / 'program/research/daily_rag_slm'
gpu_report = ROOT / sys.argv[1]
assert gpu_report.is_file()
assert gpu_report.parent == ROOT / 'final_project_cs/wiki/records/reports'
gpu_state = ROOT / sys.argv[2]
assert gpu_state.is_file()
now = datetime.now(timezone(timedelta(hours=9)))
stamp = now.strftime('%Y-%m-%d_%H%M%S_saluki_gpu_links')
saluki_report = ROOT / 'final_project_cs/wiki/records/reports/2026-10-09_0117_saluki-official-review.md'
assert saluki_report.is_file()
backups = []

def replace_existing(path, edit):
    original = path.read_bytes()
    decoded = original.decode('utf-8-sig').replace('\r\n', '\n')
    revised = edit(decoded)
    assert revised != decoded
    backup = path.parent / '_backup' / stamp
    backup.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup / path.name)
    backups.append(str(backup.relative_to(ROOT)).replace('\\', '/'))
    temporary = path.with_name(path.name + '.saluki-links.tmp')
    temporary.write_text(revised, encoding='utf-8')
    assert path.read_bytes() == original, 'Another writer changed the common document; re-read before retry'
    temporary.replace(path)

def create_or_preserve_partial(path, text):
    if path.exists():
        backup = path.parent / '_backup' / (stamp + '_partial_record_resume')
        backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup / path.name)
        backups.append(str(backup.relative_to(ROOT)).replace('\\', '/'))
    path.write_text(text, encoding='utf-8')

date = '2026-10-09'
day_state = {
    'schema_version': 1, 'date': date, 'recorded_at_kst': now.isoformat(),
    'scope': 'User-requested GPU queue replenishment and selected Saluki release review; full daily paper survey pending',
    'research': {'selected_release_review_completed': True, 'selected_releases_checked': 1,
                 'selected_releases_planned': 1, 'daily_paper_survey_completed': False},
    'review': {'official_metadata_license_notice_completed': True,
               'upper_tier_and_product_adoption_determined': False},
    'implementation': {'GPU_queue_replenishment_completed': True,
                       'machines_checked': 2, 'machines_replenished': 2,
                       'saluki_evaluation_plan_prepared': True,
                       'saluki_runtime_compatibility_verified': False},
    'measurement': {'GPU_queue_execution_observed': True,
                    'Saluki_project_model_evaluation_completed': False,
                    'Saluki_completed_rows': 0, 'Saluki_planned_rows': 9425,
                    'long_term_continuous_GPU_utilization_proven': False},
    'canonical_candidate_state': 'model_release_watchlist.json',
    'GPU_state': str(gpu_state.relative_to(ROOT)).replace('\\', '/'),
    'reports': [str(p.relative_to(ROOT)).replace('\\', '/') for p in [gpu_report, saluki_report]],
    'resume': ['Read real processes, locks, GPU state and latest queue records before any launch',
               'Collect completed queued adapters and evaluations under new output names',
               'Saluki: preserve fixed revision and license; recheck space including queued output growth and quota',
               'After resource and compatibility gates pass, smoke then matched original D3/H/E/D/D2',
               'Do not automatically fine-tune approximately 27B as an <=8B SLM',
               'Continue the daily paper survey separately; this user-requested check is not full survey completion'],
}
create_or_preserve_partial(DAY / (date + '.json'), json.dumps(day_state, ensure_ascii=False, indent=2))
gpu_rel = '../../../' + str(gpu_report.relative_to(ROOT)).replace('\\', '/')
saluki_rel = '../../../' + str(saluki_report.relative_to(ROOT)).replace('\\', '/')
day_text = f'''---
type: report
title: 2026-10-09 GPU 대기열 보충과 Saluki 원본 검토
description: 사용자 요청으로 실제 실행과 후속 작업을 확인하고 신모델을 조건부 후보로 보관했다
status: draft
domain: travel
tags: [research, evaluation, gpu]
---

# GPU 대기열 보충과 Saluki 원본 검토

GPU 서버 A의 빈 대기열을 보충해 실제 평가가 시작되는 것을 확인했고, GPU 서버 B의 학습 뒤 독립 시드 비교를 추가 예약했다. Saluki는 공식 자료를 확인한 원본 비교 후보이며 우리 여행 질의 실측은 아직 대기한다.

| 할 일 | 상태 | 진행 |
|---|---|---|
| GPU 서버 A/B 실제 상태 확인·보충 | 완료 | 2/2 = 100% |
| 선택한 신모델 공식 자료 검토 | 완료 | 1/1 = 100% |
| Saluki 여행 질의 본 비교 | 조건부 대기 | 0/9425 = 0% |

분모 9425는 예정된 다섯 단일 선택 평가의 문항 합계다. GPU 가동은 관측 시점의 실측이며 장기간 무중단 가동이 입증됐다는 뜻이 아니다.

## 원본 근거와 정본

- [GPU 완료 결과 회수·실행·대기열 보충 리포트]({gpu_rel}) — 실제 관측, 새 예약, 실패 보존과 백업.
- [Saluki 공식 검토와 조건부 시험 계획]({saluki_rel}) — 공식 출처, 성능 해석 범위, 공간·실행기 게이트.
- [후보 상태 정본](model_release_watchlist.json) — revision·파일 해시·라이선스·우리 시험과 추가 학습 여부.
- [오늘의 구조화 상태]({date}.json) — 조사·검토·구현·실측을 구분한 재개 지점.

## 아직 끝나지 않은 일

이 기록은 요청받은 GPU 대기열 보충과 Saluki 한 후보 확인 범위다. 오늘의 전체 최신 논문 조사 완료로 표시하지 않았다. Saluki는 가중치 보관·설치 실행기 스모크·여행 평가를 완료하지 않았으며 준비된 GPU 작업 수에 포함하지 않는다. 약 27B의 압축 파일이 작다는 이유로 소형 모델 추가 학습 대상에 넣지 않는다.

기존 실행·잠금·공간과 산출물 증가를 다시 확인한 뒤 순서대로 이어간다. 완료된 비교를 무의미하게 반복하거나 진행 중 학습을 중단하지 않는다. 원본 비교·독립 보류 검증 전 모델 채택을 확정하지 않는다.

## 수정 직전 백업

- [후보 목록 이전판](_backup/2026-10-09_011710_saluki_review/) — 기존 두 후보를 유지한 원본.
- [날짜 색인](_backup/{stamp}/) — 오늘 기록을 연결하기 직전 원본.
- [모델 평가 기준](../../../final_project_cs/wiki/quality/_backup/{stamp}/) — 검토 근거를 연결하기 직전 원본.
- [GPU 운영 문서](../../../final_project_cs/wiki/operations/_backup/{stamp}/) — 새 실행 근거를 연결하기 직전 원본.
- [wiki 변경 이력](../../../final_project_cs/wiki/_backup/{stamp}/) — 이번 작업을 기록하기 직전 원본.
- [Saluki 실행 계획](../../../program/scripts/plan_qa_bench/results/saluki_preflight_20261009/_backup/2026-10-09_012445_before_smoke_inputs/) — 12문항 연결 검사 입력을 고정하기 직전 원본.
'''
create_or_preserve_partial(DAY / (date + '.md'), day_text)

index = DAY / 'index.md'
row = '| [2026-10-09.md](2026-10-09.md) · [실행 상태](2026-10-09.json) | GPU 대기열 보충·Saluki 선택 검토, 전체 논문 조사와 모델 실측은 대기 |\n'
replace_existing(index, lambda text: text.replace('|---|---|\n', '|---|---|\n' + row, 1))
quality = ROOT / 'final_project_cs/wiki/quality/slm-model-evaluation.md'
replace_existing(quality, lambda text: text + '\n`[검토 2026-10-09]` Saluki는 공식 원본을 확인한 조건부 비교 후보이며 압축 파일 크기와 소형 모델 학습 범위를 구분한다. 우리 여행 질의 측정과 채택은 대기한다. [근거](../records/reports/' + saluki_report.name + ').\n')
operations = ROOT / 'final_project_cs/wiki/operations/gpu-work-queue.md'
replace_existing(operations, lambda text: text + '\n`[실측 2026-10-09]` 완료 학습판의 누락 평가로 빈 GPU 서버 A 대기열을 보충했고 GPU 서버 B에는 세 번째 독립 시드 대조를 예약했다. FINCH 학습 프로세스 관측 누락도 보완했다. [실행·보존·백업 근거](../records/reports/' + gpu_report.name + ').\n')
log = ROOT / 'final_project_cs/wiki/log.md'
entry = '\n## 2026-10-09 — GPU 대기열 재보충과 Saluki 공식 검토\n\n기존 GPU 실행기를 유지하며 완료 학습판 추가 평가와 독립 시드 비교를 예약했고, Saluki는 공식 자료와 조건부 원본 시험 계획을 보관했다. [GPU 실행 근거](records/reports/' + gpu_report.name + ') · [신모델 검토 근거](records/reports/' + saluki_report.name + ').\n'
replace_existing(log, lambda text: text.replace('# 문서 변경 이력 (cs)\n', '# 문서 변경 이력 (cs)\n' + entry, 1))
checked = []
for p in [DAY / (date + '.md'), index]:
    for target in re.findall(r'\]\(([^)]+)\)', p.read_text(encoding='utf-8')):
        if '://' in target or target.startswith('#'):
            continue
        target = target.split('#', 1)[0]
        if not target:
            continue
        assert (p.parent / target).resolve().exists(), (p, target)
        checked.append(target)
print(json.dumps({'day_created': date, 'common_files_updated': 4,
                  'local_links_checked': len(checked), 'backups': backups}, ensure_ascii=False))
