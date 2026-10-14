"""세 새 완료 평가를 직접 검증하고 양자화 비교·학습 효과·예약을 분리해 기록한다."""
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
    a, ac = read(BASE/'A_snapshot_hb1534.json'), read(BASE/'A_conditions_hb1534.json')
    b, bc = read(BASE/'B_snapshot_hb1527.json'), read(BASE/'B_conditions_hb1527.json')
    hashes = read(BASE/'qat_completed_hashes_hb1527.json')
    refill = read(BASE/'qat_adapter_refill_hb1527.json')
    assert str(a['worker_pid']) in a['processes'] and len(ac['ready']) >= 3
    assert b['active_training_variants'] == ['spark_s1_4b_oos']
    assert len(a['manifest']['jobs']) == refill['jobs_registered'] == 34
    now = datetime.now()
    stamp = now.strftime('%Y-%m-%d_%H%M%S')+'_qat_three_completion_refill'
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

    specs = [
        ('e4bqat_original_d3', 'D3', 'choice_counts.json',
         'program/scripts/plan_qa_bench/results/empty_probe/all_prompts_d3.json', 'e4bbase_d3'),
        ('e4bqat_original_mx', 'MX / user E', 'mx_counts.json',
         'datasets/travel/mx_testset/mx_main_prompts.json', 'e4bbase_mx'),
        ('e4bqat_oos1_h', 'H', 'h_counts.json',
         'program/scripts/plan_qa_bench/results/hard_set/h_set_test_30_20261015_agree.json', 'e4bqat_original_h'),
    ]
    results, pairs = {}, {}
    # 역할 메타데이터 혼동을 먼저 기록한다. 원본 started.json은 수정하지 않는다.
    correction = dict(job='e4bqat_oos1_h', our_training=True,
        issue='Publisher-only description was copied from original and said no our-travel additional training; adapter and our_training=True prove this is a trained variant.',
        resolution='Normalize derived publisher description; preserve original execution metadata; future refill descriptions separate publisher training and our adapter.')
    with (BASE/(stamp+'_role_correction.json')).open('x', encoding='utf-8') as f:
        json.dump(correction, f, indent=2)
    for job, suite, countfile, goldrel, baseline in specs:
        r, old = read(BASE/job/countfile), read(BASE/baseline/countfile)
        own = job == 'e4bqat_oos1_h'
        assert r['our_training'] == own and not old['our_training']
        for key in ['prompt_sha256','script_sha256','engine_version']:
            assert r['execution'][key] == old['execution'][key], (job,key)
        if own:
            assert r['execution']['job']['model'] == old['execution']['job']['model']
            assert r['execution']['job']['lora_sha256'] == '6d3cf6786fb5e99511930e493776d38695adf6fd201fd16398df7ade01f767ba'
        goldpath = ROOT/goldrel
        gold = read(goldpath)
        answer = BASE/job/f"d_test_{r['execution']['job']['tag']}.jsonl"
        old_answer = BASE/baseline/f"d_test_{old['execution']['job']['tag']}.jsonl"
        rows = [json.loads(x) for x in answer.read_text(encoding='utf-8').splitlines()]
        previous = {x['i']:x for x in (json.loads(s) for s in old_answer.read_text(encoding='utf-8').splitlines())}
        run, ref = {x['i']:x for x in rows}, {x['i']:x for x in gold}
        assert len(rows) == len(run) == len(ref) == r['saved'] == r['expected']
        assert set(run) == set(ref) == set(previous) and r['missing'] == 0
        assert hashlib.sha256(answer.read_bytes()).hexdigest() == r['answer_sha256'] == hashes[job][answer.name]
        assert hashlib.sha256(goldpath.read_bytes()).hexdigest() == r['gold_sha256'] == r['execution']['prompt_sha256']
        assert all(run[i]['gold'] == previous[i]['gold'] == ref[i]['gold'] and
                   run[i]['type'] == previous[i]['type'] == ref[i]['type'] for i in ref)
        paired = {}
        groups = [(kind, label, positive) for kind in ['control','mixed']
                  for label, positive in [('request',True),('no_request',False)]] if suite.startswith('MX') else [
                      (None,'positive',True),(None,'negative',False)]
        for kind, label, positive in groups:
            ids = [i for i,g in ref.items() if (g['gold'] is not None) == positive and
                   (kind is None or g['kind'] == kind)]
            st = r['counts'][kind][label] if kind else r[label]
            assert len(ids) == st['total']
            assert sum(correct(run[i]) for i in ids) == st['correct']
            assert sum(not valid(run[i]) for i in ids) == st['failed_or_missing']
            assert sum(valid(run[i]) and ref[i]['gold'] is None and run[i]['pick'] is not None for i in ids) == st['false_pick']
            gain = sum(correct(run[i]) and not correct(previous[i]) for i in ids)
            loss = sum(correct(previous[i]) and not correct(run[i]) for i in ids)
            paired[(kind+'_' if kind else '')+label] = dict(total=len(ids), new_only_correct=gain,
                baseline_only_correct=loss, exact_p=binomtest(gain,gain+loss).pvalue if gain+loss else 1)
        assert sum(not valid(x) for x in rows) == r['failed_or_unparsed']
        assert a['state']['jobs'][job]['status'].startswith('completed')
        assert a['state']['jobs'][job]['failed_or_unparsed'] == r['failed_or_unparsed']
        if own:
            r['publisher_training'] = 'Google Instruct release and quantization-aware training; our-travel oos1 adapter recorded separately'
            r['role_metadata_correction'] = correction
            save((BASE/job/countfile).relative_to(ROOT), json.dumps(r,ensure_ascii=False,indent=2)+'\n')
            path = BASE/job/'h_report.md'
            text = path.read_text(encoding='utf-8').replace(
                'Google Instruct release; publisher quantization-aware training; no our-travel additional training',r['publisher_training'])
            save(path.relative_to(ROOT),text+'\n개발사 설명의 원본 복사 문구를 바로잡았습니다. 우리 여행 oos1 어댑터가 적용된 학습판입니다. 원본 실행 기록은 그대로 보존했습니다.\n')
        with (BASE/job/'verification.json').open('x',encoding='utf-8') as f:
            json.dump(dict(saved=len(rows),missing=0,failed_or_unparsed=r['failed_or_unparsed'],
                remote_hash_match=True,frozen_input_hash_match=True,exact_ids_gold_type_match=True,
                independent_direct_recount=True,matched_baseline_input_script_engine=True,
                our_training=own,repetitions=1),f,indent=2)
        results[job], pairs[job] = r, paired
    with (BASE/(stamp+'_paired.json')).open('x',encoding='utf-8') as f:
        json.dump(pairs,f,indent=2)
    state = read(DAILY/'gpu_backlog_2026-10-08.json')
    for machine,snap,cond,obs in [('A',a,ac,'hb1534'),('B',b,bc,'hb1527')]:
        state['gpu_'+machine].update(snapshot=(BASE/f'{machine}_snapshot_{obs}.json').relative_to(ROOT).as_posix(),
            conditions_snapshot=(BASE/f'{machine}_conditions_{obs}.json').relative_to(ROOT).as_posix(),
            observed_at_utc=snap['observed_at_utc'],instant_gpu_memory_and_utilization=snap['gpu_snapshot'],
            root_available_bytes=cond['root_space']['available_bytes'])
    completed = [v for v in a['state']['jobs'].values() if v['status'].startswith('completed')]
    state['gpu_A'].update(state=a['state'],answers_saved_at_snapshot=a['answers'],jobs_completed=len(completed),
        jobs_completed_with_errors=sum(v['status']=='completed_with_errors' for v in completed),
        jobs_running=sum(v['status']=='running' for v in a['state']['jobs'].values()),jobs_ready_waiting=len(ac['ready']),
        jobs_registered=34,planned_answers=71040,refill_evidence=(BASE/'qat_adapter_refill_hb1527.json').relative_to(ROOT).as_posix())
    for job in results: state['gpu_A']['completed_'+job+'_archived'] = True
    state.update(recorded_at=now.isoformat(),latest_routine_observation=dict(new_completed_jobs=3,
        new_failed_jobs=0,new_failed_or_unparsed_answers=5,queue_refill=True,added_jobs=6,worker_restart=False,report=report))
    save('program/research/daily_rag_slm/gpu_backlog_2026-10-08.json',json.dumps(state,ensure_ascii=False,indent=2)+'\n')
    day = read(DAILY/'2026-10-08.json')
    for job,suite,_,_,_ in specs:
        r = results[job]
        assert not any(x.get('model')==r['model'] and x.get('suite')==suite for x in day['new_completed_evaluations'])
        entry = {k:r[k] for k in ['model','our_training','publisher_training','saved','expected','missing','failed_or_unparsed','repetitions','final_ranking'] if k in r}
        entry.update(suite=suite,report=report)
        for key in ['positive','negative','counts','aggregate_gates_passed','sources']:
            if key in r: entry[key] = r[key]
        day['new_completed_evaluations'].append(entry)
    save('program/research/daily_rag_slm/2026-10-08.json',json.dumps(day,ensure_ascii=False,indent=2)+'\n')
    arm = read(ROOT/'program/scripts/plan_qa_bench/results/arm_serving_20261008/observation_hb1527.json')
    ar = read(DAILY/'arm_serving_2026-10-08.json')
    assert arm['resource_summary']['five_minute_target_verified'] and arm['health']['status'] == 'ok'
    ar.update(last_observed_at=arm['observed_at'],current_saved=arm['active']['saved'],
        resource_measurement=arm['resource_summary'],latest_raw_observation='program/scripts/plan_qa_bench/results/arm_serving_20261008/observation_hb1527.json')
    save('program/research/daily_rag_slm/arm_serving_2026-10-08.json',json.dumps(ar,ensure_ascii=False,indent=2)+'\n')
    summary = 'QAT 배포 원본 D3·혼합 문장과 우리 여행 oos1 학습판의 어려운 문장5,690개를 회수했다. 학습판은 어려운 잡담 오지목을 줄였지만 정상 요청도 함께 확인해야 하므로 제품 채택을 보류한다. 기존 어댑터의 누락 QAT 비교6개를 같은 실행기에 보충했다.'
    save('program/research/daily_rag_slm/2026-10-08.md',(DAILY/'2026-10-08.md').read_text(encoding='utf-8')+
         f'\n## {now:%H시%M분} — QAT 새 완료·학습판 비교·예약 보충\n\n{summary}\n\n[원본 답안·실패·비교·백업 근거](../../../{report}).\n')
    for rel,prefix,conclusion in [
        ('final_project_cs/wiki/quality/slm-model-evaluation.md','../records/reports/','QAT 원본 누락 평가와 같은 기반의 여행 학습판 평가를 회수했다. 잡담 개선과 정상 요청 보존을 분리해 판단한다.'),
        ('final_project_cs/wiki/operations/gpu-work-queue.md','../records/reports/','기존 어댑터 구조·누락 범위를 확인해 QAT 추가 비교를 예약하고 실행기 재시작 없이 유지했다.'),
        ('final_project_cs/wiki/log.md','records/reports/','새 완료 답안을 보관하고 배포 원본과 여행 학습판을 구분해 집계했다.')]:
        save(rel,(ROOT/rel).read_text(encoding='utf-8')+f'\n`[실측 2026-10-08]` {conclusion} [근거]({prefix}{stamp}.md).\n')
    ratio = lambda n,d: f'{n:,}/{d:,} = {100*n/d:.2f}%'
    lines = ['# QAT 새 완료·학습판 비교·대기열 보충','',summary,'',
        '| 할 일 | 상태 | 진행 |','|---|---|---|',
        '| 답안 보관·전체 문항 대조 | 완료 | 5,690/5,690 = 100% |',
        '| 형식 실패 | 원문·분모 보존 | 5/5,690 = 0.09% |',
        '| 추가 QAT 비교 예약 | 완료 | 6/6 = 100% |','',
        '## 배포 원본 비교와 학습 효과','',
        '| 시험 | 항목 | 비교 기준 | 새 결과 |','|---|---|---:|---:|']
    for job,suite,countfile,_,baseline in specs:
        r, old = results[job], read(BASE/baseline/countfile)
        p,n = (r['counts']['mixed']['request'],r['counts']['mixed']['no_request']) if suite.startswith('MX') else (r['positive'],r['negative'])
        op,on = (old['counts']['mixed']['request'],old['counts']['mixed']['no_request']) if suite.startswith('MX') else (old['positive'],old['negative'])
        title = 'oos1 학습판 H' if r['our_training'] else 'QAT 원본 '+suite
        lines += [f"| {title} | 정상 요청 정답 | {ratio(op['correct'],op['total'])} | {ratio(p['correct'],p['total'])} |",
                  f"| {title} | 요청 없음 오지목 | {ratio(on['false_pick'],on['total'])} | {ratio(n['false_pick'],n['total'])} |"]
    lines += ['', '원본 D3·혼합 비교 기준은 우리 추가 학습 없는 Q4_K_M 배포판이다. oos1 H 비교 기준은 같은 QAT 가중치의 우리 추가 학습 없는 원본이다. 개발사 지시 학습·양자화 학습과 우리 여행 추가 학습을 구분했다. 입력·전체ID·정답·유형·실행 코드 해시·llama.cpp 4ebdf2c가 같다. 가중치/양자화 변경의 정확도 비교이며 같은 모델 엔진 속도 시험이 아니다.',
        f'[같은 문항의 개선·손실·정확 검정](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/{stamp}_paired.json). 각 모델 실행1회이며 일정별 상관·다중 비교·반복 편차를 통제한 최종 우열로 해석하지 않는다.',
        '', '## 혼합 문장 범위·실패·채택 한계','',
        '혼합2,007개와 대조2,007개다. 각 부류 정상1,033개·요청 없음974개이며 E 전체를 자연 자유 문장이라고 부르지 않는다. 자연 작성 혼합239개와 코드 조합1,768개를 분리한다. 자연 작성에도 아직 사람 정답 검수가 필요하다. 기존 개발/회귀 자료이고 독립 보류240+480개는 작성·검수·해시 고정 후 별도 최종 검증해야 한다.0/720 완료 상태다.']
    mx = results['e4bqat_original_mx']
    natural = mx['sources']['llm']['mixed']
    lines += [f"QAT 원본 자연 작성 혼합 정상 정답{ratio(natural['request']['correct'],natural['request']['total'])}, 요청 없음 오지목{ratio(natural['no_request']['false_pick'],natural['no_request']['total'])}. 사전 합산{mx['aggregate_gates_passed']}/4 기준 통과, 세부 MX3·MX4·MX5a는 실패했다. 정상 정답 개선과 오지목 증가가 함께 있으므로 Q4_K_M보다 전체적으로 우수하다고 채택하지 않는다.",
        '혼합 형식 실패0개·대조 요청 없음 형식 실패4개다. D3의 정상 요청 형식 실패1개와 합쳐5개다. 단일 번호/null 계약에서 배열을 출력한 원문을 보존했으며 배열에서 번호 하나를 골라 정답으로 고치지 않았다. 실패와 실제 오지목은 따로 표시하되 전체 정답률에서는 실패도 오답이다.', '',
        '## 답안·직접 계수·역할 기록','']
    for job,_,countfile,_,_ in specs:
        r = results[job]
        link = '../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/'+job
        lines += [f"- [{r['model']} 답안·로그·집계]({link}/) · [해시·문항·직접 계수 검증]({link}/verification.json). 원격/로컬 답안 SHA256`{r['answer_sha256']}`."]
    lines += ['', 'oos1 실행 기록의 개발사 설명에는 원본에서 복사한 “우리 학습 없음” 문구가 남아 있었다. 실제 어댑터 인자·해시·our_training=True를 확인하고 파생 집계의 개발사 설명을 수정 직전 백업 후 바로잡았다. 원본 started.json·답안·과거 리포트는 수정하지 않았다. 새 예약의 개발사 설명도 우리 어댑터 학습과 분리했다.',
        '', '## 예약·자원·재개','',
        f"GPU 서버 A 등록34개·71,040문항이며 oos1 혼합 평가가 실행 중이고 준비된{len(ac['ready'])}개가 기다린다(관측{a['observed_at_utc']}). oos2·oos3·oos2r 각H/MX6개를 새 이름으로 예약했다. 기존oos1 H가 성공한 동일 QAT 기반에서 세 어댑터의516개 텐서 이름·형태·자료형이 모두 일치했다. 각 새 판의 실제 로딩·정확도 성공을 미리 주장하지 않으며 첫 실행 결과에서 확인한다. 기존 Q4_K_M 완료를 QAT 시험 완료로 옮기지 않는다.",
        '[원자적 manifest 교체·수정 직전 원격 백업·입력/어댑터 해시](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/qat_adapter_refill_hb1527.json). 기존 실행기는 살아 있으며 추가 실행기·중복 평가·작업 중단·새 모델 다운로드·기존 모델 삭제·새 결제가 없다.',
        f"GPU 서버 B는 기존 Spark 본 학습과 뒤5개 예약을 유지한다.4개는 기존 입력을 쓰고1개는 다운로드/공간 확인이 필요하다. Oracle ARM 관측{arm['observed_at']} 최근{arm['resource_summary']['window_s']:.2f}초 작업CPU는 두 코어 전체 대비{arm['resource_summary']['cpu_pct_two_cores']:.2f}%, host busy{arm['resource_summary']['host_cpu_busy_pct']:.2f}%, steal{arm['resource_summary']['host_steal_pct']:.2f}%다. 목표 이상 연속 표본{arm['resource_summary']['above_20_contiguous_seconds']:.2f}초이며24시간 유지 증거는 아니다. 답안25/360개·메모리8,948,330,496바이트(파일 캐시 포함)·공간54,412,320,768바이트다.",
        '다음 확인에서는 새 어댑터 로딩/실패를 확인하고 완료 답안부터 회수한다. 실패는 원인 수정 없이 반복하지 않는다. 원본 비교군 완료·반복·별도 보류 검증 전 제품 모델 승격을 하지 않는다.',
        '', '## 수정 직전 백업','']
    lines += [f'- [{x}](../../../../{x})' for x in backups]
    text = '\n'.join(lines)+'\n'
    assert not (ROOT/report).exists()
    save(report,text)
    for _,target in re.findall(r'\[([^\]]+)\]\(([^)]+)\)',text):
        assert (ROOT/report).parent.joinpath(target.split('#')[0]).resolve().exists(), target
    print(json.dumps(dict(report=report,paired=pairs,ready_A=len(ac['ready']),backups=backups,links_broken=0),ensure_ascii=False))


if __name__ == '__main__':
    main()
