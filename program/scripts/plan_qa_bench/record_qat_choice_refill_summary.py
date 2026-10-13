"""완료된 원본 D·학습판 D3와 누락 D/D2 예약 보충을 근거 중심으로 연결한다."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import re
import shutil
import sys
from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT/'program/scripts/plan_qa_bench/results/gpu_backlog_20261008'
DAILY = ROOT/'program/research/daily_rag_slm'
read = lambda p: json.loads(p.read_text(encoding='utf-8'))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    observation, evidence = sys.argv[1:3]
    jobs = ['e4bqat_original_d', 'e4bqat_oos1_d3', 'e4bqat_oos2_d3']
    a, ac = read(BASE/f'A_snapshot_{observation}.json'), read(BASE/f'A_conditions_{observation}.json')
    b = read(BASE/f'B_snapshot_{observation}.json')
    refill = read(BASE/f'qat_regression_refill_{evidence}.json')
    assert len(a['manifest']['jobs']) == refill['jobs_registered'] == 47
    assert sum(j['expected'] for j in a['manifest']['jobs']) == refill['expected_registered'] == 90155
    assert len(refill['added_jobs']) == 8 and refill['added_expected_questions'] == 14940
    assert refill['no_worker_restart'] and refill['adapter_hashes_verified'] and len(ac['ready']) >= 3
    assert str(a['worker_pid']) in a['processes'] and b['active_training_variants'] == ['spark_s1_4b_oos']
    day = read(DAILY/'2026-10-08.json')
    results = {j: read(BASE/j/'choice_counts.json') for j in jobs}
    old = read(BASE/'e4bqat_original_d3/choice_counts.json')
    rows = lambda r, folder: {x['i']: x for x in (json.loads(line) for line in (folder/f"d_test_{r['execution']['job']['tag']}.jsonl").read_text(encoding='utf-8').splitlines())}
    previous = rows(old, BASE/'e4bqat_original_d3')
    correct = lambda r: bool(r.get('parsed')) and not r.get('error') and r['pick'] == r['gold']
    paired = {}
    for job, r in results.items():
        v = read(BASE/job/'verification.json')
        assert v['remote_hash_match'] and v['independent_direct_recount'] and v['missing'] == 0
        assert r['saved'] == r['expected'] == a['state']['jobs'][job]['saved']
        assert r['failed_or_unparsed'] == a['state']['jobs'][job]['failed_or_unparsed']
        assert hashlib.sha256((BASE/job/f"d_test_{r['execution']['job']['tag']}.jsonl").read_bytes()).hexdigest() == r['answer_sha256']
        assert any(x.get('model') == r['model'] and x.get('suite') == r['suite'] for x in day['new_completed_evaluations'])
        if r['suite'] != 'D3':
            assert not r['our_training']
            continue
        assert r['our_training'] and not old['our_training']
        for key in ['prompt_sha256', 'script_sha256', 'engine_version']:
            assert r['execution'][key] == old['execution'][key]
        assert r['execution']['job']['model_sha256'] == old['execution']['job']['model_sha256']
        registration = next(j for j in a['manifest']['jobs'] if j['id'] == job)
        assert r['execution']['job']['lora_sha256'] == registration['lora_sha256']
        current = rows(r, BASE/job)
        assert set(current) == set(previous)
        assert all(current[i]['gold'] == previous[i]['gold'] and current[i]['type'] == previous[i]['type'] for i in current)
        paired[job] = {}
        for label, positive in [('request', True), ('no_request', False)]:
            ids = [i for i, row in previous.items() if (row['gold'] is not None) == positive]
            gain = sum(correct(current[i]) and not correct(previous[i]) for i in ids)
            loss = sum(correct(previous[i]) and not correct(current[i]) for i in ids)
            paired[job][label] = dict(total=len(ids), trained_only_correct=gain, original_only_correct=loss,
                                     exact_p=binomtest(gain, gain+loss).pvalue if gain+loss else 1)
    arm_path = ROOT/f'program/scripts/plan_qa_bench/results/arm_serving_20261008/observation_{evidence}.json'
    arm = read(arm_path)
    assert arm['health']['status'] == 'ok' and arm['resource_summary']['five_minute_target_verified']
    now = datetime.now()
    stamp = now.strftime('%Y-%m-%d_%H%M%S')+'_qat_choice_completion_and_regression_refill'
    report = 'final_project_cs/wiki/records/reports/'+stamp+'.md'
    with (BASE/(stamp+'_paired.json')).open('x', encoding='utf-8') as f:
        json.dump(paired, f, indent=2)
    backups = []
    def save(rel, text):
        path = ROOT/rel
        if path.exists():
            backup = path.parent/'_backup'/stamp/path.name
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
            backups.append(backup.relative_to(ROOT).as_posix())
        path.write_text(text, encoding='utf-8')
    state = read(DAILY/'gpu_backlog_2026-10-08.json')
    state['gpu_A'].update(jobs_registered=47, planned_answers=90155, jobs_ready_waiting=len(ac['ready']),
        refill_evidence=(BASE/f'qat_regression_refill_{evidence}.json').relative_to(ROOT).as_posix())
    state['latest_routine_observation'].update(new_completed_jobs=len(jobs),
        new_failed_or_unparsed_answers=sum(r['failed_or_unparsed'] for r in results.values()),
        queue_refill=True, added_jobs=8, report=report)
    state['recorded_at'] = now.isoformat()
    save('program/research/daily_rag_slm/gpu_backlog_2026-10-08.json', json.dumps(state, ensure_ascii=False, indent=2)+'\n')
    ar = read(DAILY/'arm_serving_2026-10-08.json')
    ar.update(last_observed_at=arm['observed_at'], current_saved=arm['active']['saved'],
        resource_measurement=arm['resource_summary'], latest_raw_observation=arm_path.relative_to(ROOT).as_posix())
    save('program/research/daily_rag_slm/arm_serving_2026-10-08.json', json.dumps(ar, ensure_ascii=False, indent=2)+'\n')
    summary = 'QAT 원본 D와 여행 학습판 D3 두 판의 답안을 보관하고 실패를 분모에 남겼다. 관측 대기2건에 누락 D/D2 평가8건을 보충해 일반 정상 요청 회귀와 요청 없음 오지목을 함께 확인한다.'
    save('program/research/daily_rag_slm/2026-10-08.md', (DAILY/'2026-10-08.md').read_text(encoding='utf-8')+f'\n## {now:%H시%M분} — QAT 선택 시험 회수·회귀 평가 예약\n\n{summary}\n\n[집계·대조·예약·백업](../../../{report}).\n')
    for rel, prefix in [('final_project_cs/wiki/operations/gpu-work-queue.md', '../records/reports/'), ('final_project_cs/wiki/quality/slm-model-evaluation.md', '../records/reports/'), ('final_project_cs/wiki/log.md', 'records/reports/')]:
        save(rel, (ROOT/rel).read_text(encoding='utf-8')+f'\n`[실측 2026-10-08]` 완료 선택 시험의 실패를 보존하고 누락된 일반 요청·요청 없음 비교를 기존 실행기에 예약했다. [근거]({prefix}{stamp}.md).\n')
    ratio = lambda n, d: f'{n:,}/{d:,} = {100*n/d:.2f}%'
    total = sum(r['saved'] for r in results.values())
    errors = sum(r['failed_or_unparsed'] for r in results.values())
    lines = ['# QAT 선택 시험 회수와 누락 회귀 평가 예약', '', summary, '', '| 할 일 | 상태 | 진행 |', '|---|---|---|',
        f'| 답안 보관·전체 문항 검증 | 완료 | {ratio(total,total)} |', f'| 실패·해석 불가 | 원문·분모 보존 | {ratio(errors,total)} |', '| 누락 평가 예약 | 완료 | 8/8 = 100% |', '',
        '## 같은 QAT 기반의 직접 선택 D3', '', '| 모델 역할 | 정상 요청 정답 | 요청 없음 오지목 | 오류·해석 실패 |', '|---|---:|---:|---:|',
        f"| 우리 여행 추가 학습 없는 원본 | {ratio(old['positive']['correct'],120)} | {ratio(old['negative']['false_pick'],240)} | {old['failed_or_unparsed']}/360 |"]
    for job in jobs[1:]:
        r = results[job]
        lines.append(f"| 우리 여행 학습판 {job.split('_')[1]} | {ratio(r['positive']['correct'],120)} | {ratio(r['negative']['false_pick'],240)} | {r['failed_or_unparsed']}/360 |")
    lines += ['', '입력·전체 문항 ID·정답·유형·실행 코드·엔진·기반 가중치 해시가 같다. 등록된 어댑터 해시를 대조했다. 개발사 지시 학습·양자화 학습과 우리 여행 추가 학습을 구분한다. 학습판별1회 실행이며 서로 다른 혼합 문장 시험에서 발견된 정상 요청 손실을 무효화하지 않는다.',
        f'[같은 문항 정확 검정](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/{stamp}_paired.json). 반복 편차·독립 보류·다중 비교를 대신하지 않으며 최종 순위·제품 채택은 보류한다.', '', '## 원본 D의 전체 실패 보존', '']
    r = results[jobs[0]]
    lines += [f"정상 요청 정답{ratio(r['positive']['correct'],r['positive']['total'])}, 기존 일정 항목 선택 없음 오지목{ratio(r['negative']['false_pick'],r['negative']['total'])}다. 전체2,735개 중 단일 선택2,669개·복합 진단66개를 분리한다. 실패17개(정상12·항목 없음3·복합2)는 원문과 해당 분모에 보존했다. 형식 실패를 실제 오지목 계수에 합하거나 배열 출력을 정답으로 바꾸지 않는다.", '', '## 원본 기록·예약·자원', '']
    entries = [x for x in day['new_completed_evaluations'] if any(x.get('model')==r['model'] and x.get('suite')==r['suite'] for r in results.values())]
    for e in entries:
        lines.append(f"- [{e['model']} {e['suite']} 답안·직접 검증·실패 원문]({Path(e['report']).name}).")
    lines += ['', f"GPU 서버 A 실행기PID{a['worker_pid']}를 유지했다. 원자적 manifest 갱신으로 여행 학습판 oos1/oos2/oos3/oos2r의 D·D2 각각1개, 총8개·14,940문항을 예약했다. {a['observed_at_utc']} 기준 준비된{len(ac['ready'])}개가 대기한다. 등록47개·계획90,155문항은 완료 수가 아니다.",
        f'[수정 전 manifest 백업·입력/어댑터 해시·중복 등록 방지](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/qat_regression_refill_{evidence}.json). 원본 모델 전체 해시는 이번 준비에서 재계산하지 않고 기존 검증된 파일을 사용했다. 실행 중 작업 중단·추가 worker·새 모델 다운로드·삭제·결제는 없다.',
        'GPU 서버 B는 기존 Spark 학습과 기존 기반으로 실행 가능한4개·다운로드/공간 준비가 필요한1개 예약을 유지한다. B56/B57을 중복 실행하지 않는다.',
        f"Oracle ARM 최근{arm['resource_summary']['window_s']:.2f}초의 두 코어 대비 작업 CPU{arm['resource_summary']['cpu_pct_two_cores']:.2f}%, host busy{arm['resource_summary']['host_cpu_busy_pct']:.2f}%, steal{arm['resource_summary']['host_steal_pct']:.2f}%다. 24시간 유지나 cs 프로젝트 전체 배포 완료로 해석하지 않는다.",
        '[예약 재현 도구](../../../../program/scripts/plan_qa_bench/server/queues/refill_qat_regression_20261008.py) · [회수 집계 도구](../../../../program/scripts/plan_qa_bench/backlog_choice_report.py) · [기록 검증 도구](../../../../program/scripts/plan_qa_bench/record_qat_choice_refill_summary.py). 예약 재현 도구를 다시 실행하면 중복 등록을 거부한다.', '', '## 수정 직전 백업', '']
    lines += [f'- [{p}](../../../../{p})' for p in backups]
    text = '\n'.join(lines)+'\n'
    assert not (ROOT/report).exists()
    save(report, text)
    for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', text):
        assert (ROOT/report).parent.joinpath(target.split('#')[0]).resolve().exists(), target
    print(json.dumps(dict(report=report, saved=total, errors=errors, added_jobs=8, ready_A=len(ac['ready']), paired=paired, links_broken=0)))


if __name__ == '__main__':
    main()
