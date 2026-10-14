"""보관된 QAT 학습판 MX/H 완료를 검증하고 최신 관측·예약 근거와 연결한다."""
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
valid = lambda r: bool(r.get('parsed')) and not r.get('error')
correct = lambda r: valid(r) and r['pick'] == r['gold']


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    args = sys.argv[1:]
    no_refill = '--no-refill' in args
    observation, evidence, *jobs = [x for x in args if x != '--no-refill']
    assert jobs and len(jobs) == len(set(jobs))
    a, ac = read(BASE/f'A_snapshot_{observation}.json'), read(BASE/f'A_conditions_{observation}.json')
    b, bc = read(BASE/f'B_snapshot_{observation}.json'), read(BASE/f'B_conditions_{observation}.json')
    hashes = read(BASE/f'qat_completed_hashes_{evidence}.json')
    refill = None if no_refill else read(BASE/f'qat_choice_refill_{evidence}.json')
    assert str(a['worker_pid']) in a['processes'] and len(ac['ready']) >= 3
    assert b['active_training_variants'] == ['spark_s1_4b_oos']
    if refill:
        assert len(a['manifest']['jobs']) == refill['jobs_registered']
    day = read(DAILY/'2026-10-08.json')
    arm_path = ROOT/f'program/scripts/plan_qa_bench/results/arm_serving_20261008/observation_{evidence}.json'
    arm = read(arm_path)
    assert arm['health']['status'] == 'ok' and arm['resource_summary']['five_minute_target_verified']
    results, paired = {}, {}
    for job in jobs:
        assert job.startswith('e4bqat_oos') and job.endswith(('_mx', '_h'))
        assert not (BASE/job/'verification.json').exists()
        mx = job.endswith('_mx')
        cf = 'mx_counts.json' if mx else 'h_counts.json'
        r = read(BASE/job/cf)
        suite = 'MX / user E' if mx else 'H'
        assert r['our_training'] and not any(x.get('model') == r['model'] and x.get('suite') == suite for x in day['new_completed_evaluations'])
        old = read(BASE/('e4bqat_original_mx' if mx else 'e4bqat_original_h')/cf)
        assert not old['our_training']
        for key in ['prompt_sha256', 'script_sha256', 'engine_version']:
            assert r['execution'][key] == old['execution'][key]
        assert r['execution']['job']['model_sha256'] == old['execution']['job']['model_sha256']
        registered = next(j for j in a['manifest']['jobs'] if j['id'] == job)
        assert r['execution']['job']['lora_sha256'] == registered['lora_sha256']
        answer = BASE/job/f"d_test_{r['execution']['job']['tag']}.jsonl"
        goldpath = ROOT/('datasets/travel/mx_testset/mx_main_prompts.json' if mx else 'program/scripts/plan_qa_bench/results/hard_set/h_set_test_30_20261015_agree.json')
        rows = [json.loads(x) for x in answer.read_text(encoding='utf-8').splitlines()]
        run = {x['i']: x for x in rows}
        gold = {x['i']: x for x in read(goldpath)}
        old_answer = BASE/('e4bqat_original_mx' if mx else 'e4bqat_original_h')/f"d_test_{old['execution']['job']['tag']}.jsonl"
        previous = {x['i']: x for x in (json.loads(line) for line in old_answer.read_text(encoding='utf-8').splitlines())}
        assert len(rows) == len(run) == len(gold) == r['saved'] == r['expected'] and r['missing'] == 0
        assert set(run) == set(gold) == set(previous)
        assert hashlib.sha256(answer.read_bytes()).hexdigest() == r['answer_sha256'] == hashes[job]
        assert hashlib.sha256(goldpath.read_bytes()).hexdigest() == r['gold_sha256'] == r['execution']['prompt_sha256']
        assert all(run[i]['gold'] == previous[i]['gold'] == g['gold'] and run[i]['type'] == previous[i]['type'] == g['type'] for i, g in gold.items())
        groups = [(kind, label, pos) for kind in ['control', 'mixed'] for label, pos in [('request', True), ('no_request', False)]] if mx else [(None, 'positive', True), (None, 'negative', False)]
        paired[job] = {}
        for kind, label, positive in groups:
            ids = [i for i, g in gold.items() if (g['gold'] is not None) == positive and (kind is None or g['kind'] == kind)]
            st = r['counts'][kind][label] if kind else r[label]
            assert len(ids) == st['total']
            assert sum(correct(run[i]) for i in ids) == st['correct']
            assert sum(not valid(run[i]) for i in ids) == st['failed_or_missing']
            assert sum(valid(run[i]) and gold[i]['gold'] is None and run[i]['pick'] is not None for i in ids) == st['false_pick']
            gain = sum(correct(run[i]) and not correct(previous[i]) for i in ids)
            loss = sum(correct(previous[i]) and not correct(run[i]) for i in ids)
            paired[job][(kind+'_' if kind else '')+label] = dict(total=len(ids), trained_only_correct=gain, original_only_correct=loss, exact_p=binomtest(gain, gain+loss).pvalue if gain+loss else 1)
        assert sum(not valid(x) for x in rows) == r['failed_or_unparsed'] == a['state']['jobs'][job]['failed_or_unparsed']
        assert a['state']['jobs'][job]['status'].startswith('completed')
        results[job] = (r, old, suite, cf)
    now = datetime.now()
    stamp = now.strftime('%Y-%m-%d_%H%M%S')+('_qat_completion_and_choice_refill' if refill else '_qat_completion_verified')
    report = 'final_project_cs/wiki/records/reports/'+stamp+'.md'
    backups = []

    def save(rel, text):
        path = ROOT/rel
        if path.exists():
            backup = path.parent/'_backup'/stamp/path.name
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
            backups.append(backup.relative_to(ROOT).as_posix())
        path.write_text(text, encoding='utf-8')

    total = sum(r['saved'] for r, *_ in results.values())
    errors = sum(r['failed_or_unparsed'] for r, *_ in results.values())
    for job, (r, _, suite, _) in results.items():
        verification = dict(remote_hash_match=True, frozen_input_hash_match=True, exact_ids_gold_type_match=True, independent_direct_recount=True, matched_original_input_script_engine_model=True, adapter_matches_registered_hash=True, our_training=True, saved=r['saved'], missing=0, failed_or_unparsed=r['failed_or_unparsed'], repetitions=1)
        with (BASE/job/'verification.json').open('x', encoding='utf-8') as f: json.dump(verification, f, indent=2)
        entry = {k: r[k] for k in ['model', 'our_training', 'publisher_training', 'saved', 'expected', 'missing', 'failed_or_unparsed', 'repetitions']}
        entry.update(suite=suite, report=report, final_ranking=False)
        for key in ['positive', 'negative', 'counts', 'aggregate_gates_passed', 'sources']:
            if key in r: entry[key] = r[key]
        day['new_completed_evaluations'].append(entry)
    with (BASE/(stamp+'_paired.json')).open('x', encoding='utf-8') as f: json.dump(paired, f, indent=2)
    state = read(DAILY/'gpu_backlog_2026-10-08.json')
    for machine, snap, cond in [('A', a, ac), ('B', b, bc)]:
        state['gpu_'+machine].update(snapshot=(BASE/f'{machine}_snapshot_{observation}.json').relative_to(ROOT).as_posix(), conditions_snapshot=(BASE/f'{machine}_conditions_{observation}.json').relative_to(ROOT).as_posix(), observed_at_utc=snap['observed_at_utc'], instant_gpu_memory_and_utilization=snap['gpu_snapshot'], root_available_bytes=cond['root_space']['available_bytes'])
    completed = [v for v in a['state']['jobs'].values() if v['status'].startswith('completed')]
    state['gpu_A'].update(state=a['state'], answers_saved_at_snapshot=a['answers'], jobs_registered=len(a['manifest']['jobs']), planned_answers=sum(j['expected'] for j in a['manifest']['jobs']), jobs_completed=len(completed), jobs_completed_with_errors=sum(v['status']=='completed_with_errors' for v in completed), jobs_running=sum(v['status']=='running' for v in a['state']['jobs'].values()), jobs_ready_waiting=len(ac['ready']))
    if refill:
        state['gpu_A']['refill_evidence'] = (BASE/f'qat_choice_refill_{evidence}.json').relative_to(ROOT).as_posix()
    for job in jobs: state['gpu_A']['completed_'+job+'_archived'] = True
    state.update(recorded_at=now.isoformat(), latest_routine_observation=dict(new_completed_jobs=len(jobs), new_failed_jobs=0, new_failed_or_unparsed_answers=errors, queue_refill=bool(refill), added_jobs=len(refill['added_jobs']) if refill else 0, worker_restart=False, report=report))
    save('program/research/daily_rag_slm/gpu_backlog_2026-10-08.json', json.dumps(state, ensure_ascii=False, indent=2)+'\n')
    save('program/research/daily_rag_slm/2026-10-08.json', json.dumps(day, ensure_ascii=False, indent=2)+'\n')
    ar = read(DAILY/'arm_serving_2026-10-08.json')
    ar.update(last_observed_at=arm['observed_at'], current_saved=arm['active']['saved'], resource_measurement=arm['resource_summary'], latest_raw_observation=arm_path.relative_to(ROOT).as_posix())
    save('program/research/daily_rag_slm/arm_serving_2026-10-08.json', json.dumps(ar, ensure_ascii=False, indent=2)+'\n')
    queue_summary = f"입력이 준비된 누락 비교{len(refill['added_jobs'])}개를 같은 실행기에 보충했다." if refill else f"기존 실행기와 준비된 대기 평가{len(ac['ready'])}개를 유지했다."
    summary = f'QAT 여행 학습판의 새 평가{len(jobs)}건·{total:,}개를 보관했다. 정상 요청 정답과 요청 없음 오지목을 함께 대조했고 합격·반복·독립 보류 검증 전 채택하지 않는다. '+queue_summary
    save('program/research/daily_rag_slm/2026-10-08.md', (DAILY/'2026-10-08.md').read_text(encoding='utf-8')+f'\n## {now:%H시%M분} — QAT 완료 회수·예약 상태 확인\n\n{summary}\n\n[집계·검증·예약·백업 근거](../../../{report}).\n')
    connections = [('final_project_cs/wiki/quality/slm-model-evaluation.md', '../records/reports/', 'QAT 여행 학습판의 새 결과를 같은 기반 원본과 대조하고 정상 요청 보존과 오지목을 함께 판정했다.'), ('final_project_cs/wiki/log.md', 'records/reports/', '완료 답안을 보관하고 기존 실행기를 유지했다. '+queue_summary)]
    if refill:
        connections.append(('final_project_cs/wiki/operations/gpu-work-queue.md', '../records/reports/', '대기 작업 감소에 따라 기존 QAT 원본과 어댑터의 누락 선택 시험을 원자적 교체로 보충했다.'))
    for rel, prefix, conclusion in connections:
        save(rel, (ROOT/rel).read_text(encoding='utf-8')+f'\n`[실측 2026-10-08]` {conclusion} [근거]({prefix}{stamp}.md).\n')
    ratio = lambda n, d: f'{n:,}/{d:,} = {100*n/d:.2f}%'
    lines = ['# QAT 평가 완료·같은 문항 검증', '', '[실측] '+summary, '', '| 할 일 | 상태 | 진행 |', '|---|---|---|', f'| 답안 보관·전체 문항 검증 | 완료 | {total:,}/{total:,} = 100% |', f'| 오류·해석 실패 | 원문·분모 보존 | {errors}/{total:,} = {100*errors/total:.2f}% |']
    if refill:
        lines.append(f"| 누락 시험 예약 | 완료 | {len(refill['added_jobs'])}/{len(refill['added_jobs'])} = 100% |")
    lines += ['', '## 같은 QAT 원본과 여행 학습판', '', '| 시험 | 항목 | 우리 학습 없는 원본 | 우리 여행 학습판 |', '|---|---|---:|---:|']
    notes = []
    for job, (r, old, suite, cf) in results.items():
        mx = job.endswith('_mx')
        p, n = (r['counts']['mixed']['request'], r['counts']['mixed']['no_request']) if mx else (r['positive'], r['negative'])
        op, on = (old['counts']['mixed']['request'], old['counts']['mixed']['no_request']) if mx else (old['positive'], old['negative'])
        lines += [f"| {job} | 정상 요청 정답 | {ratio(op['correct'],op['total'])} | {ratio(p['correct'],p['total'])} |", f"| {job} | 요청 없음 오지목 | {ratio(on['false_pick'],on['total'])} | {ratio(n['false_pick'],n['total'])} |"]
        if mx:
            st = r['paired']['request']; natural = r['sources']['llm']['mixed']
            notes += ['', f"{job} 대조 정상{st['correct_control']}/{st['pairs']}에서 혼합{st['correct_mixed']}/{st['pairs']}로{st['loss_pp']:.2f}%p 손실이다. 일정별95% 구간{st['loss_cluster95_pp'][0]:.2f}~{st['loss_cluster95_pp'][1]:.2f}%p, 사전 합산{r['aggregate_gates_passed']}/4 기준 통과다. 세부 기준은 원본 집계에 보존한다.", f"자연 작성 혼합239개는 정상{natural['request']['correct']}/93·요청 없음 오지목{natural['no_request']['false_pick']}/146이다. 코드 조합1,768개와 분리한다. 전체 E 혼합2,007개를 전부 자연 자유 문장이라고 부르지 않는다.", '']
    lines += notes
    lines += ['', '입력·전체 ID·정답·유형·실행 코드·엔진4ebdf2c·기반 가중치 해시가 원본과 같다. 어댑터 해시는 실제 등록 내용과 대조했다. 개발사 지시 학습·양자화 학습과 우리 여행 추가 학습을 구분한다. 오류·미완료를 분모에서 빼지 않는다. 모델별 실행1회·기존 개발/회귀 자료이며 속도 직접 비교나 독립 고객 표본으로 해석하지 않는다.', f'[같은 문항의 정확 검정](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/{stamp}_paired.json). 정확 검정은 일정별 상관·반복 편차·다중 비교·새 보류 검증을 대신하지 않는다. 보류240개 정상+480개 요청 없음은 작성·검수·중복 검사·해시 고정이 필요하며 최종 채택을 보류한다.', '', '## 답안·재현 도구·백업', '']
    for job, (r, _, _, cf) in results.items():
        link = '../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/'+job
        lines += [f"- [{r['model']} 답안·로그]({link}/) · [집계]({link}/{cf}) · [직접 계수·해시 검증]({link}/verification.json). 답안 원격/로컬 SHA256`{r['answer_sha256']}`."]
    lines += ['', f'관측{a["observed_at_utc"]} 기준 GPU 서버 A는 기존 평가를 수행하고 준비된{len(ac["ready"])}개가 대기한다. '+queue_summary+' 등록은 완료가 아니며 완료·실패·실행 중 작업을 재시작하지 않는다.']
    if refill:
        lines += [f'[manifest 수정 직전 백업·원자적 교체·입력 및 어댑터 해시](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/qat_choice_refill_{evidence}.json). 원본 모델 전체 해시를 이번 준비에서 재계산한 것은 아니며 기존 검증된 파일을 사용했다.']
    lines += ['새 모델 다운로드·기존 모델 삭제·추가 실행기·결제는 없다.', 'GPU 서버 B는 기존 Spark 학습과 기존 기반으로 준비된4개 레시피·다운로드/공간 재확인이 필요한1개 후보를 유지한다. B56와B57을 중복 실행하지 않는다.', f'Oracle ARM 최근{arm["resource_summary"]["window_s"]:.2f}초 작업CPU는 두 코어 전체 대비{arm["resource_summary"]["cpu_pct_two_cores"]:.2f}%, host busy{arm["resource_summary"]["host_cpu_busy_pct"]:.2f}%, steal{arm["resource_summary"]["host_steal_pct"]:.2f}%다. 답안{arm["active"]["saved"]}/{arm["active"]["expected"]}개로 진행 중이며24시간 유지나 cs 전체 배포 완료를 주장하지 않는다.', '[예약 재현 도구](../../../../program/scripts/plan_qa_bench/server/queues/refill_qat_choice_20261008.py) · [로컬 회수 검증 도구](../../../../program/scripts/plan_qa_bench/record_qat_completion_batch.py). 예약 도구는 등록 중복을 거부하므로 같은 예약을 반복 실행하지 않는다.', '', '수정 직전에 보관한 이전 상태와 wiki를 연결한다. 과거 답안·실행 메타데이터·리포트는 수정하지 않았다.', '']
    if no_refill:
        lines += ['완료 회수와 예약 보충을 각각 실제 수행 여부로 기록하도록 도구를 보완했다. 기존 답안·원본 대조·오류 포함 전체 분모를 직접 검증한다. [도구 수정 직전 백업](../../../../program/scripts/plan_qa_bench/_backup/2026-10-08_164453_optional_refill_evidence/record_qat_completion_batch.py).', '']
    lines += [f'- [{x}](../../../../{x})' for x in backups]
    text = '\n'.join(lines)+'\n'
    assert not (ROOT/report).exists()
    save(report, text)
    for _, target in re.findall(r'\[([^\]]+)\]\(([^)]+)\)', text):
        assert (ROOT/report).parent.joinpath(target.split('#')[0]).resolve().exists(), target
    print(json.dumps(dict(report=report, saved=total, errors=errors, ready_A=len(ac['ready']), registered=len(a['manifest']['jobs']), paired=paired, backups=backups, links_broken=0), ensure_ascii=False))


if __name__ == '__main__':
    main()
