"""Connect independently counted first Saluki runtime evidence, preserving prior states."""
import json
import shutil
from datetime import datetime
from pathlib import Path

root = Path(__file__).resolve().parents[3]
verification_path = 'program/scripts/plan_qa_bench/results/saluki_parent_verification_20261009_0235.json'
verify = json.loads((root/verification_path).read_text(encoding='utf-8'))
smoke = verify['counts']['saluki_original_smoke12_a1']
partial = verify['counts']['saluki_original_d3_a1']
assert smoke['saved'] == smoke['parsed'] == smoke['expected'] == 12 and smoke['errors'] == 0
report = '2026-10-09_023533_saluki-install-smoke-and-evaluation.md'
report_path = 'final_project_cs/wiki/records/reports/'+report
assert (root/report_path).exists()
stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')+'_saluki_actual_runtime_links'


def update(relative, transform):
    p=root/relative
    old=p.read_text(encoding='utf-8')
    new=transform(old)
    if old==new:
        return
    backup=p.parent/'_backup'/stamp
    backup.mkdir(parents=True,exist_ok=True)
    shutil.copy2(p,backup/p.name)
    p.write_text(new,encoding='utf-8')
    print((backup/p.name).relative_to(root).as_posix())


def watchlist(s):
    obj=json.loads(s)
    c=next(x for x in obj['candidates'] if x['repo_id']=='ConwayResearch/Underdog-Saluki-27B-1.0')
    c.update(status='smoke_passed; D3_original_actually_running; E/H/D/D2_sequentially_queued',
             gpu_runner_compatibility_verified=True,korean_travel_measured=True,
             korean_travel_measurement_scope='First partial D3 snapshot only; main comparison incomplete',
             smoke_completed_rows=12,smoke_correct_rows=smoke['correct_among_saved'],
             main_completed_rows=partial['saved'],main_completed_suites=0,
             snapshot_observed_at_utc=verify['snapshot_observed_at_utc'],
             runtime_verification=verification_path,runtime_report=report_path,
             original_benchmark_completed=False,upper_tier=None)
    c['weight_storage'].update(permanent_copy_status='GPU B existing disk transfer started; not fully SHA verified; no local durable archive',
                              preservation_progress_evidence='program/scripts/plan_qa_bench/results/saluki_preflight_20261009/runtime_20261009_0232/B_preservation_capture.json')
    return json.dumps(obj,ensure_ascii=False,indent=2)+'\n'


def daily(s):
    obj=json.loads(s)
    obj['implementation']['saluki_runtime_compatibility_verified']=True
    obj['measurement'].update(Saluki_completed_rows=partial['saved'],Saluki_partial_D3_execution_observed=True,
                              Saluki_project_model_evaluation_completed=False)
    obj['Saluki_queue'].update(smoke_completed_rows=12,smoke_correct_rows=smoke['correct_among_saved'],
                              main_completed_rows=partial['saved'],main_completed_suites=0,
                              state='Smoke passed, actual D3 running, E/H/D/D2 queued; no final ranking',
                              snapshot_observed_at_utc=verify['snapshot_observed_at_utc'],
                              runtime_verification=verification_path,
                              weight_persistence='GPU A ephemeral RAM; GPU B existing disk transfer running, unverified; no local durable archive')
    if report_path not in obj['reports']:
        obj['reports'].append(report_path)
    obj['resume']=[x.replace('read queue evidence and raw worker state, collect smoke then D3/E/H/D/D2 outputs. Main readiness is conditional on smoke success.',
                             'smoke already passed, collect actual D3 then E/H/D/D2 outputs from the same worker; retain complete denominators and snapshot timestamps.') for x in obj['resume']]
    obj['resume'].append('Read preservation_result_20261009.json and existing relay/receiver state before any archival repair; the verified RAM source remains while the existing GPU B disk transfer runs. Do not duplicate the transfer.')
    return json.dumps(obj,ensure_ascii=False,indent=2)+'\n'


update('program/research/daily_rag_slm/model_release_watchlist.json',watchlist)
update('program/research/daily_rag_slm/2026-10-09.json',daily)


def day_text(s):
    s=s.replace('Saluki는 공식 자료를 확인한 원본 비교 후보이며 우리 여행 질의 실측은 아직 대기한다.',
                'Saluki 원본의 연결검사를 통과했고 실제 여행 질의 비교를 시작했다. 전체 결과와 채택 판단은 대기한다.')
    s=s.replace('| Saluki 여행 질의 본 비교 | 조건부 대기 | 0/9425 = 0% |',
                f"| Saluki 여행 질의 본 비교 | 실행 중·부분 관측 | {partial['saved']}/9425 = {100*partial['saved']/9425:.2f}% |")
    s=s.replace('연결검사와 본 평가는 기존 실행기에 등록돼 대기하며, 실행기 호환과 여행 성능은 실제 답안으로 확인해야 한다.',
                '연결검사를 실제 답안으로 통과했고 같은 실행기에서 본 비교가 시작됐다. 전체 여행 성능은 미완료 문항을 포함한 분모로 판정해야 한다.')
    s=s.replace('실제 Saluki 답안은 아직 대기하며 설치·등록을 정확도 시험 완료로 표시하지 않는다.',
                '뒤이은 실제 연결검사와 본 비교의 시작은 아래 리포트로 확인했다. 설치·등록과 전체 정확도 시험 완료를 구분한다.')
    if report not in s:
        s+='\n## Saluki 실제 가동 확인\n\n[설치·연결검사·본 평가 시작 리포트](../../../'+report_path+')와 [부모 독립 재계수](../../scripts/plan_qa_bench/results/saluki_parent_verification_20261009_0235.json)에서 실행 조건과 부분 관측 시각을 확인한다. 연결검사 정답은 본 평가에 합치지 않는다. GPU 서버 B 디스크 사본은 기존 전송이 진행 중이며 전체 해시 확인 전이다. 완료된 cosine 답안의 회수 대기도 최신 GPU 상태 기록에 남겼다.\n\n[이번 후보·날짜 기록 백업](_backup/'+stamp+'/).\n'
    return s


update('program/research/daily_rag_slm/2026-10-09.md',day_text)
update('program/research/daily_rag_slm/index.md',lambda s:s.replace('전체 논문 조사와 모델 실측은 대기','전체 논문 조사와 모델 최종 비교는 대기'))
update('final_project_cs/wiki/quality/slm-model-evaluation.md',lambda s:s if report in s else s.rstrip()+
       '\n\n`[실측 2026-10-09]` Saluki 원본은 실제 연결검사를 통과해 같은 여행 문항의 본 비교가 시작됐다. 전체 비교·보류 검증 전 채택은 대기한다. [실행·조건·보관 근거](../records/reports/'+report+').\n')
update('final_project_cs/wiki/operations/gpu-work-queue.md',lambda s:s if report in s else s.rstrip()+
       '\n\n`[실측 2026-10-09]` 기존 실행기에 연결검사 성공 조건을 건 신모델 원본 비교를 등록했고 실제 계산을 확인했다. 임시 모델 원본의 보관 상태도 재확인한다. [실행·전송·재개 근거](../records/reports/'+report+').\n')
entry='## 2026-10-09 — Saluki 원본의 실제 비교 시작\n\n고정 원본과 전체 파일 해시를 확인했고 연결검사 통과 뒤 본 비교가 시작됐다. 전체 평가·모델 채택은 아직 대기한다. [실행·보관 근거](records/reports/'+report+').\n\n'
update('final_project_cs/wiki/log.md',lambda s:s if report in s else s.replace('## ',entry+'## ',1))
front='---\ntype: report\ntitle: Saluki 원본 설치와 실제 평가 시작\ndescription: 고정 가중치와 연결검사를 확인하고 동일 여행 문항의 순차 비교를 시작했다\nstatus: draft\ndomain: travel\ntags: [evaluation, gpu, research]\n---\n\n'
update(report_path,lambda s:s if s.startswith('---') else front+s)
print('BACKUP_STAMP='+stamp)
