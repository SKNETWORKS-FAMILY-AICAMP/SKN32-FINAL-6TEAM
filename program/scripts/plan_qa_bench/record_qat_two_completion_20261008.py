"""QAT 여행 학습판의 새 MX/H 완료를 고정 분모와 같은 문항으로 검증한다."""
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
    observation = sys.argv[1]
    a, ac = read(BASE/f'A_snapshot_{observation}.json'), read(BASE/f'A_conditions_{observation}.json')
    b, bc = read(BASE/f'B_snapshot_{observation}.json'), read(BASE/f'B_conditions_{observation}.json')
    remote_hashes = read(BASE/f'qat_completed_hashes_{observation}.json')
    assert str(a['worker_pid']) in a['processes'] and len(ac['ready']) >= 3
    assert b['active_training_variants'] == ['spark_s1_4b_oos']
    now = datetime.now()
    stamp = now.strftime('%Y-%m-%d_%H%M%S')+'_qat_two_trained_completion'
    report = 'final_project_cs/wiki/records/reports/'+stamp+'.md'
    assert not (ROOT/report).exists()
    backups = []

    def save(path, text):
        path = ROOT/path
        if path.exists():
            backup = path.parent/'_backup'/stamp/path.name
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
            backups.append(backup.relative_to(ROOT).as_posix())
        path.write_text(text, encoding='utf-8')

    specs = [
        ('e4bqat_oos1_mx', 'MX / user E', 'mx_counts.json', 'e4bqat_original_mx',
         'datasets/travel/mx_testset/mx_main_prompts.json',
         '6d3cf6786fb5e99511930e493776d38695adf6fd201fd16398df7ade01f767ba'),
        ('e4bqat_oos2_h', 'H', 'h_counts.json', 'e4bqat_original_h',
         'program/scripts/plan_qa_bench/results/hard_set/h_set_test_30_20261015_agree.json',
         '28fbce6efc2ace8fdda5cbcdc803b5be9ae8f7715e238819c8f7e60a418e0348'),
    ]
    results, pairs = {}, {}
    for job, suite, countfile, baseline, goldrel, adapter_hash in specs:
        r, old = read(BASE/job/countfile), read(BASE/baseline/countfile)
        assert r['our_training'] and not old['our_training']
        for key in ['prompt_sha256', 'script_sha256', 'engine_version']:
            assert r['execution'][key] == old['execution'][key]
        assert r['execution']['job']['model_sha256'] == old['execution']['job']['model_sha256']
        assert r['execution']['job']['lora_sha256'] == adapter_hash
        answer = BASE/job/f"d_test_{r['execution']['job']['tag']}.jsonl"
        rows = [json.loads(x) for x in answer.read_text(encoding='utf-8').splitlines()]
        ref = {x['i']: x for x in read(ROOT/goldrel)}
        run = {x['i']: x for x in rows}
        old_answer = BASE/baseline/f"d_test_{old['execution']['job']['tag']}.jsonl"
        previous = {x['i']: x for x in (json.loads(v) for v in old_answer.read_text(encoding='utf-8').splitlines())}
        assert len(rows) == len(run) == len(ref) == r['saved'] == r['expected']
        assert set(run) == set(ref) == set(previous) and r['missing'] == 0
        assert hashlib.sha256(answer.read_bytes()).hexdigest() == r['answer_sha256'] == remote_hashes[job]
        assert hashlib.sha256((ROOT/goldrel).read_bytes()).hexdigest() == r['gold_sha256'] == r['execution']['prompt_sha256']
        assert all(run[i]['gold'] == previous[i]['gold'] == g['gold'] and run[i]['type'] == previous[i]['type'] == g['type'] for i, g in ref.items())
        groups = [(kind, label, pos) for kind in ['control', 'mixed'] for label, pos in [('request', True), ('no_request', False)]] if suite.startswith('MX') else [(None, 'positive', True), (None, 'negative', False)]
        paired = {}
        for kind, label, positive in groups:
            ids = [i for i, g in ref.items() if (g['gold'] is not None) == positive and (kind is None or g['kind'] == kind)]
            st = r['counts'][kind][label] if kind else r[label]
            assert len(ids) == st['total']
            assert sum(correct(run[i]) for i in ids) == st['correct']
            assert sum(not valid(run[i]) for i in ids) == st['failed_or_missing']
            assert sum(valid(run[i]) and ref[i]['gold'] is None and run[i]['pick'] is not None for i in ids) == st['false_pick']
            gain = sum(correct(run[i]) and not correct(previous[i]) for i in ids)
            loss = sum(correct(previous[i]) and not correct(run[i]) for i in ids)
            paired[(kind+'_' if kind else '')+label] = dict(total=len(ids), trained_only_correct=gain, original_only_correct=loss, exact_p=binomtest(gain, gain+loss).pvalue if gain+loss else 1)
        assert sum(not valid(x) for x in rows) == r['failed_or_unparsed'] == a['state']['jobs'][job]['failed_or_unparsed']
        assert a['state']['jobs'][job]['status'] == 'completed'
        if job == 'e4bqat_oos1_mx':
            # 원본 실행 메타데이터는 보존하고 자동 생성 파생물의 역할만 정정한다.
            before = r['publisher_training']
            r['publisher_training'] = 'Google Instruct release and quantization-aware training; our-travel oos1 adapter recorded separately'
            r['role_metadata_correction'] = dict(original_description=before, our_training=True, adapter_sha256=adapter_hash, original_started_json_preserved=True)
            save(answer.parent.relative_to(ROOT)/countfile, json.dumps(r, ensure_ascii=False, indent=2)+'\n')
            path = answer.parent/'mx_report.md'
            save(path.relative_to(ROOT), path.read_text(encoding='utf-8').replace(before, r['publisher_training'])+'\n원본에서 복사된 개발사 설명을 바로잡았습니다. 우리 여행 oos1 학습판이며 원본 실행 기록은 보존했습니다.\n')
        with (BASE/job/'verification.json').open('x', encoding='utf-8') as f:
            json.dump(dict(remote_hash_match=True, frozen_input_hash_match=True, exact_ids_gold_type_match=True, independent_direct_recount=True, matched_original_input_script_engine_model=True, our_training=True, saved=len(rows), missing=0, failed_or_unparsed=r['failed_or_unparsed'], repetitions=1), f, indent=2)
        results[job], pairs[job] = r, paired
    with (BASE/(stamp+'_paired.json')).open('x', encoding='utf-8') as f:
        json.dump(pairs, f, indent=2)
    state = read(DAILY/'gpu_backlog_2026-10-08.json')
    for machine, snap, cond in [('A', a, ac), ('B', b, bc)]:
        state['gpu_'+machine].update(snapshot=(BASE/f'{machine}_snapshot_{observation}.json').relative_to(ROOT).as_posix(), conditions_snapshot=(BASE/f'{machine}_conditions_{observation}.json').relative_to(ROOT).as_posix(), observed_at_utc=snap['observed_at_utc'], instant_gpu_memory_and_utilization=snap['gpu_snapshot'], root_available_bytes=cond['root_space']['available_bytes'])
    completed = [v for v in a['state']['jobs'].values() if v['status'].startswith('completed')]
    state['gpu_A'].update(state=a['state'], answers_saved_at_snapshot=a['answers'], jobs_completed=len(completed), jobs_completed_with_errors=sum(v['status']=='completed_with_errors' for v in completed), jobs_running=sum(v['status']=='running' for v in a['state']['jobs'].values()), jobs_ready_waiting=len(ac['ready']))
    for job in results:
        state['gpu_A']['completed_'+job+'_archived'] = True
    state.update(recorded_at=now.isoformat(), latest_routine_observation=dict(new_completed_jobs=2, new_failed_jobs=0, new_failed_or_unparsed_answers=0, queue_refill=False, worker_restart=False, report=report))
    save('program/research/daily_rag_slm/gpu_backlog_2026-10-08.json', json.dumps(state, ensure_ascii=False, indent=2)+'\n')
    day = read(DAILY/'2026-10-08.json')
    for job, suite, *_ in specs:
        r = results[job]
        assert not any(x.get('model') == r['model'] and x.get('suite') == suite for x in day['new_completed_evaluations'])
        entry = {k: r[k] for k in ['model', 'our_training', 'publisher_training', 'saved', 'expected', 'missing', 'failed_or_unparsed', 'repetitions']}
        entry.update(suite=suite, report=report, final_ranking=False)
        for key in ['positive', 'negative', 'counts', 'aggregate_gates_passed', 'sources']:
            if key in r: entry[key] = r[key]
        day['new_completed_evaluations'].append(entry)
    save('program/research/daily_rag_slm/2026-10-08.json', json.dumps(day, ensure_ascii=False, indent=2)+'\n')
    arm_path = ROOT/f'program/scripts/plan_qa_bench/results/arm_serving_20261008/observation_{observation}.json'
    arm = read(arm_path)
    assert arm['resource_summary']['five_minute_target_verified'] and arm['health']['status'] == 'ok'
    ar = read(DAILY/'arm_serving_2026-10-08.json')
    ar.update(last_observed_at=arm['observed_at'], current_saved=arm['active']['saved'], resource_measurement=arm['resource_summary'], latest_raw_observation=arm_path.relative_to(ROOT).as_posix())
    save('program/research/daily_rag_slm/arm_serving_2026-10-08.json', json.dumps(ar, ensure_ascii=False, indent=2)+'\n')
    summary = 'QAT 기반의 여행 oos1 학습판 혼합 문장과 oos2 학습판 어려운 문장5,330개를 보관했다. oos1은 혼합 정상 요청의 손실이 커 사전 합산 기준1/4 통과로 채택하지 않는다. oos2 H는 정상 요청과 잡담 오지목의 균형을 계속 비교한다.'
    save('program/research/daily_rag_slm/2026-10-08.md', (DAILY/'2026-10-08.md').read_text(encoding='utf-8')+f'\n## {now:%H시%M분} — QAT 여행 학습판 두 평가 완료\n\n{summary}\n\n[전체 분모·같은 문항·실패·백업 근거](../../../{report}).\n')
    for rel, prefix in [('final_project_cs/wiki/quality/slm-model-evaluation.md', '../records/reports/'), ('final_project_cs/wiki/log.md', 'records/reports/')]:
        save(rel, (ROOT/rel).read_text(encoding='utf-8')+f'\n`[실측 2026-10-08]` QAT 기반 여행 학습판의 혼합 요청 손실과 어려운 잡담 오지목을 분리해 확인했다. [완료·채택 보류 근거]({prefix}{stamp}.md).\n')
    mx, h = results['e4bqat_oos1_mx'], results['e4bqat_oos2_h']
    natural = mx['sources']['llm']['mixed']
    body = f'''# QAT 여행 학습판 두 평가 완료

[실측] {summary}

| 할 일 | 상태 | 진행 |
|---|---|---|
| 답안 보관·해시·전체 ID 대조 | 완료 | 5,330/5,330 = 100% |
| 오류·해석 실패 | 실측 | 0/5,330 = 0% |

## 같은 QAT 원본 대비 학습 효과

| 시험 | 항목 | 우리 학습 없는 QAT 원본 | 우리 여행 학습판 |
|---|---|---:|---:|
| oos1 혼합 / E | 정상 요청 정답 | 978/1,033 = 94.68% | 865/1,033 = 83.74% |
| oos1 혼합 / E | 요청 없음 오지목 | 207/974 = 21.25% | 28/974 = 2.87% |
| oos2 어려운 문장 H | 정상 요청 정답 | 424/461 = 91.97% | 433/461 = 93.93% |
| oos2 어려운 문장 H | 요청 없음 오지목 | 489/855 = 57.19% | 186/855 = 21.75% |

각 기준 원본의 전체 직접 계수는 해당 보관 폴더를 따른다. 입력·문항·정답·유형·실행 코드·엔진4ebdf2c·QAT 기반 가중치 해시를 일치 확인하고, 적용 어댑터 해시를 대조했다. 각 실행1회·기존 개발/회귀 자료다. 개발사 지시 학습·양자화 학습과 우리 여행 추가 학습을 구분한다. 모델 정확도 변화이며 같은 모델 엔진 속도 우열 시험이 아니다.

oos1은 대조 정상996/1,033에서 혼합865/1,033으로12.68%p 손실, 일정별95% 구간10.70~14.78%p다.59개 일정 군집 부트스트랩2,000회·시드7이며 합산 기준1/4, 세부 MX3 실패다. 잡담 개선만으로 채택하지 않는다. 같은 QAT 기반 oos1 H는422/461·오지목90/855였으므로 oos2 H의 정상 정답 증가와 오지목 증가도 함께 기록한다.

자연 작성 혼합239개에서는 정상{natural['request']['correct']}/93·요청 없음 오지목{natural['no_request']['false_pick']}/146이다. 코드로 이어 붙인1,768개와 분리한다. 자연 작성 문항의 사람 정답 검수 전이며 E 전체2,007개를 모두 자연 자유 질의라고 부르지 않는다. 전체 혼합2,007·대조2,007개를 합해4,014개다. H는 정상461·요청 없음855개다. 실패·미완료는 분모에서 빼지 않는다.

[같은 문항 정확 검정](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/{stamp}_paired.json)은 실행1회에서의 차이다. 일정 상관·반복 편차·독립 보류 검증을 대신하지 않는다. 최종 모델 순위나 제품 채택을 확정하지 않는다. 별도 보류720개는 아직 작성·검수·해시 고정이 필요하다.

## 원본 답안·검증·역할 정정

'''
    for job, _, cf, *_ in specs:
        link = '../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/'+job
        body += f"- [{job} 답안·로그]({link}/) · [집계]({link}/{cf}) · [해시·직접 검증]({link}/verification.json). 원격/로컬 답안 SHA256`{results[job]['answer_sha256']}`.\n"
    body += f'''
oos1의 원본에서 복사된 개발사 설명 중 “우리 학습 없음” 문구는 파생 집계만 직전 백업 후 바로잡았다. our_training=True와 어댑터 해시를 확인했고 원본 started.json은 보존했다. oos2는 새 어댑터 실제 로딩 뒤1,316개를 완료했다. 준비 단계의 텐서 구조 일치를 정확도 성공으로 쓰지 않았다.

## 이어지는 작업과 자원

관측{a['observed_at_utc']} 기준 GPU 서버 A는 oos2 혼합을 실행하며 준비된{len(ac['ready'])}개가 기다린다. GPU 서버 B는 Spark 여행 학습 중이며 기존 기반의4개 학습 레시피와 다운로드/공간 재확인이 필요한1개 후보를 뒤에 유지한다. 현재 계산·준비 작업·조건 대기를 구분했다. 실행기 추가·중단·재학습·새 결제·기존 모델 삭제는 하지 않았다.

Oracle ARM은 최근{arm['resource_summary']['window_s']:.2f}초 두 코어 전체 대비 작업CPU{arm['resource_summary']['cpu_pct_two_cores']:.2f}%, 기계 busy{arm['resource_summary']['host_cpu_busy_pct']:.2f}%, steal{arm['resource_summary']['host_steal_pct']:.2f}%다. 답안{arm['active']['saved']}/360개는 진행 중이며 정확도 결론을 내지 않는다. 최근5분 목표를 충족했지만24시간 유지·cs 프로젝트 전체 배포 완료라고 쓰지 않는다.

## 수정 직전 백업

'''
    body += '\n'.join(f'- [{x}](../../../../{x})' for x in backups)+'\n'
    save(report, body)
    for _, target in re.findall(r'\[([^\]]+)\]\(([^)]+)\)', body):
        assert (ROOT/report).parent.joinpath(target.split('#')[0]).resolve().exists(), target
    print(json.dumps(dict(report=report, ready_A=len(ac['ready']), paired=pairs, backups=backups, links_broken=0), ensure_ascii=False))


if __name__ == '__main__':
    main()
