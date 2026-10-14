"""배포 원본 QAT의 새 완료 답안·형식 실패를 보존하고 같은 문항으로 대조한다."""
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
valid = lambda x: bool(x.get('parsed')) and not x.get('error')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    hashes = read(BASE/'qat_completed_hashes_hb1507.json')
    a, ac = read(BASE/'A_snapshot_hb1507.json'), read(BASE/'A_conditions_hb1507.json')
    b, bc = read(BASE/'B_snapshot_hb1507.json'), read(BASE/'B_conditions_hb1507.json')
    assert len(ac['ready']) >= 3 and str(a['worker_pid']) in a['processes']
    assert b['active_training_variants'] == ['spark_s1_4b_oos']
    results, pairs = {}, {}
    for suite, count_file, gold_file in [('D2','choice_counts.json','empty_probe/all_prompts_d2.json'),
                                        ('H','h_counts.json','hard_set/h_set_test_30_20261015_agree.json')]:
        job, baseline = 'e4bqat_original_'+suite.lower(), 'e4bbase_'+suite.lower()
        r, old = read(BASE/job/count_file), read(BASE/baseline/count_file)
        assert not r['our_training'] and not old['our_training']
        for key in ['prompt_sha256','script_sha256','engine_version']:
            assert r['execution'][key] == old['execution'][key], key
        answer = BASE/job/f"d_test_{r['execution']['job']['tag']}.jsonl"
        old_answer = BASE/baseline/f"d_test_{old['execution']['job']['tag']}.jsonl"
        rows = [json.loads(x) for x in answer.read_text(encoding='utf-8').splitlines()]
        previous = {x['i']: x for x in (json.loads(s) for s in old_answer.read_text(encoding='utf-8').splitlines())}
        gold_path = ROOT/'program/scripts/plan_qa_bench/results'/gold_file
        gold = read(gold_path)
        run, ref = ({x['i']: x for x in values} for values in [rows,gold])
        assert len(rows) == len(run) == len(ref) == r['saved'] == r['expected']
        assert set(run) == set(ref) == set(previous)
        assert hashlib.sha256(answer.read_bytes()).hexdigest() == hashes[job]['sha256'] == r['answer_sha256']
        assert hashlib.sha256(gold_path.read_bytes()).hexdigest() == r['gold_sha256'] == r['execution']['prompt_sha256']
        assert all(run[i]['gold'] == previous[i]['gold'] == ref[i]['gold'] and
                   run[i]['type'] == previous[i]['type'] == ref[i]['type'] for i in ref)
        assert r['missing'] == 0 and r['failed_or_unparsed'] == 1
        paired = {}
        for label, positive in [('positive',True),('negative',False)]:
            ids = [i for i,g in ref.items() if (g['gold'] is not None)==positive]
            correct = lambda x: valid(x) and x['pick'] == x['gold']
            assert len(ids) == r[label]['total']
            assert sum(correct(run[i]) for i in ids) == r[label]['correct']
            assert sum(not valid(run[i]) for i in ids) == r[label]['failed_or_missing']
            assert sum(valid(run[i]) and ref[i]['gold'] is None and run[i]['pick'] is not None for i in ids) == r[label]['false_pick']
            gain = sum(correct(run[i]) and not correct(previous[i]) for i in ids)
            loss = sum(correct(previous[i]) and not correct(run[i]) for i in ids)
            paired[label] = dict(total=len(ids), qat_only_correct=gain, q4km_only_correct=loss,
                qat_correct=r[label]['correct'],q4km_correct=old[label]['correct'],
                qat_false_pick=r[label]['false_pick'],q4km_false_pick=old[label]['false_pick'],
                exact_p=binomtest(gain,gain+loss).pvalue if gain+loss else 1)
        assert sum(not valid(x) for x in rows) == 1
        assert a['state']['jobs'][job]['status'] == 'completed_with_errors'
        with (BASE/job/'verification.json').open('x',encoding='utf-8') as f:
            json.dump(dict(saved=len(rows),missing=0,failed_or_unparsed=1,remote_hash_match=True,
                frozen_input_hash_match=True,exact_ids_gold_type=True,direct_recount=True,
                matched_baseline_input_script_engine=True,repetitions=1),f,indent=2)
        results[suite], pairs[suite] = r, paired

    now = datetime.now()
    stamp = now.strftime('%Y-%m-%d_%H%M%S')+'_qat_original_d2_h_completion'
    report_rel = 'final_project_cs/wiki/records/reports/'+stamp+'.md'
    backups = []
    def save(rel, text):
        p = ROOT/rel
        if p.exists():
            dest = p.parent/'_backup'/stamp/p.name
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(p,dest)
            backups.append(dest.relative_to(ROOT).as_posix())
        p.write_text(text,encoding='utf-8')
    with (BASE/(stamp+'_paired.json')).open('x',encoding='utf-8') as f:
        json.dump(pairs,f,indent=2)
    state = read(DAILY/'gpu_backlog_2026-10-08.json')
    for machine,snap,cond in [('A',a,ac),('B',b,bc)]:
        state['gpu_'+machine].update(snapshot=(BASE/f'{machine}_snapshot_hb1507.json').relative_to(ROOT).as_posix(),
            conditions_snapshot=(BASE/f'{machine}_conditions_hb1507.json').relative_to(ROOT).as_posix(),
            observed_at_utc=snap['observed_at_utc'],instant_gpu_memory_and_utilization=snap['gpu_snapshot'],
            root_available_bytes=cond['root_space']['available_bytes'])
    completed = [v for v in a['state']['jobs'].values() if v['status'].startswith('completed')]
    state['gpu_A'].update(state=a['state'],answers_saved_at_snapshot=a['answers'],jobs_completed=len(completed),
        jobs_completed_with_errors=sum(v['status']=='completed_with_errors' for v in completed),
        jobs_running=1,jobs_ready_waiting=len(ac['ready']))
    for suite in results: state['gpu_A']['completed_e4bqat_original_'+suite.lower()+'_archived'] = True
    state.update(recorded_at=now.isoformat(),latest_routine_observation=dict(new_completed_jobs=2,
        new_failed_jobs=0,new_failed_or_unparsed_answers=2,queue_refill=False,worker_restart=False,report=report_rel))
    save('program/research/daily_rag_slm/gpu_backlog_2026-10-08.json',json.dumps(state,ensure_ascii=False,indent=2)+'\n')
    day = read(DAILY/'2026-10-08.json')
    for suite,r in results.items():
        assert not any(x.get('model')==r['model'] and x.get('suite')==suite for x in day['new_completed_evaluations'])
        entry = {k:r[k] for k in ['model','our_training','publisher_training','saved','expected','missing',
            'failed_or_unparsed','positive','negative','repetitions','final_ranking']}
        entry.update(suite=suite,report=report_rel)
        day['new_completed_evaluations'].append(entry)
    save('program/research/daily_rag_slm/2026-10-08.json',json.dumps(day,ensure_ascii=False,indent=2)+'\n')
    arm = read(ROOT/'program/scripts/plan_qa_bench/results/arm_serving_20261008/observation_hb1507.json')
    ar = read(DAILY/'arm_serving_2026-10-08.json')
    assert arm['resource_summary']['five_minute_target_verified'] and arm['health']['status']=='ok'
    ar.update(last_observed_at=arm['observed_at'],current_saved=arm['active']['saved'],
        resource_measurement=arm['resource_summary'],latest_raw_observation='program/scripts/plan_qa_bench/results/arm_serving_20261008/observation_hb1507.json')
    save('program/research/daily_rag_slm/arm_serving_2026-10-08.json',json.dumps(ar,ensure_ascii=False,indent=2)+'\n')
    summary = '우리 여행 자료로 추가 학습하지 않은 Gemma-4-E4B-it QAT Q4_0 원본의 D2·H2,316개를 회수했고 형식 실패2개를 원문·분모에 보존했다. 같은 문항의 Q4_K_M 원본과 대조했으며 QAT 원본이 더 좋다고 채택하지 않는다.'
    save('program/research/daily_rag_slm/2026-10-08.md',(DAILY/'2026-10-08.md').read_text(encoding='utf-8')+
        f'\n## {now:%H시%M분} — QAT 원본 D2·H 완료\n\n{summary}\n\n[완료·검증·실패 리포트](../../../{report_rel}).\n')
    for rel,prefix in [('final_project_cs/wiki/quality/slm-model-evaluation.md','../records/reports/'),
                       ('final_project_cs/wiki/log.md','records/reports/')]:
        save(rel,(ROOT/rel).read_text(encoding='utf-8')+
            f'\n`[실측 {now:%Y-%m-%d}]` QAT 배포 원본의 D2·H 답안과 형식 실패를 회수해 같은 문항의 다른 배포 원본과 대조했다. [근거]({prefix}{stamp}.md).\n')
    lines = ['# Gemma QAT 원본 D2·H 완료','',summary,'',
        '| 할 일 | 상태 | 진행 |','|---|---|---|','| 답안 보관·전체 문항 대조 | 완료 | 2,316/2,316 = 100% |',
        '| 형식 실패 | 보존 | 2/2,316 = 0.09% |',
        '| GPU 서버 A 다음 일감 | 준비됨 | 3/3개 = 100% |','',
        '## 같은 문항의 배포 원본 비교','',
        '| 시험 | 항목 | Q4_K_M 원본 | QAT Q4_0 원본 |','|---|---|---:|---:|']
    for suite in results:
        for label,title,key in [('positive','정상 요청 정답','correct'),('negative','요청 없음 오지목','false_pick')]:
            p = pairs[suite][label]
            if not p['total']: continue
            old_key, new_key = ('q4km_correct','qat_correct') if key=='correct' else ('q4km_false_pick','qat_false_pick')
            lines.append(f"| {suite} | {title} | {p[old_key]}/{p['total']} = {100*p[old_key]/p['total']:.2f}% | {p[new_key]}/{p['total']} = {100*p[new_key]/p['total']:.2f}% |")
    lines += ['', '두 판은 모두 우리 여행 추가 학습이 없는 배포 원본이다. 개발사 지시 학습·QAT 역할은 우리 추가 학습과 구분한다. 입력 해시·전체 문항ID·정답·유형·코드 해시·llama.cpp 버전4ebdf2c를 맞췄다. 서로 다른 가중치/양자화 배포판의 비교이며 같은 모델 엔진 속도 시험으로 해석하지 않는다. 모델 실행각1회·기존 개발/회귀 문항이며 전체 원본 비교군·반복·독립 보류 검증 전 순위나 제품 채택은 확정하지 않는다.',
        f'[같은 문항 개선·손실·정확 검정](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/{stamp}_paired.json). 문항별 검정은 일정별 상관·여러 비교와 반복 편차를 통제한 최종 검정이 아니다.',
        '', '## 형식 실패·보관·검증','',
        '두 실패는 호출 오류가 아니라 단일 번호/null 계약에 배열을 출력한 사례다. 배열 중 번호 하나를 골라 정답 처리하지 않았다. 현재16토큰 출력 제한에서 미완성 배열이며 번호 배열이 완성돼도 단일 선택 계약을 위반한다. 실패한 null을 요청 없음 정답으로 세지 않았고 실패와 실제 오지목을 따로 표시한다. 재실행하지 않는다.','',
        '| 시험 | 문항 ID | 유형 | 원문 |','|---|---|---|---|']
    for suite,r in results.items():
        job = 'e4bqat_original_'+suite.lower()
        for failed in r['failed_records']:
            content = str(failed.get('content',failed.get('error'))).replace('|','\\|').replace('\n','<br>')
            lines.append(f"| {suite} | {failed['i']} | {failed['type']} | `{content}` |")
        lines += ['',f'[{suite} 답안·로그·실행 조건·해시/직접 계수 검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/{job}/). GPU 서버 A 원본 SHA256은`{hashes[job]["sha256"]}`로 로컬 사본과 같다.','']
    lines += ['## 실행 유지·다음 일감·백업','',
        'GPU 서버 A는 기존 실행기로 QAT 원본 MX를 수행하며 원본 D3·oos1 QAT H·MX3개가 준비됐다. GPU 서버 B는 기존 Spark 본 학습과 뒤4개 기존 입력 학습·1개 다운로드/공간 확인 후보를 유지한다. Oracle ARM은 최근300.06초 두 코어 전체 대비CPU89.83%, host busy90.22%, steal0.17%, 메모리8,925,679,616바이트(파일 캐시 포함), 공간54,411,526,144바이트다. 답안14/360개 저장, 재시작0회이며 목표 이상 연속 표본1,895.43초다.24시간 유지 증거는 아니다.',
        '실행기 추가·중복 평가·작업 중단·새 결제·기존 모델 삭제는 하지 않았다. 과거 기록은 수정하지 않았고 새 결과를 해당 wiki와 일일 기록에 연결했다. 수정 직전 백업:', '']
    lines += [f'- [{x}](../../../../{x})' for x in backups]
    text = '\n'.join(lines)+'\n'
    save(report_rel,text)
    for title,target in re.findall(r'\[([^\]]+)\]\(([^)]+)\)',text):
        assert (ROOT/report_rel).parent.joinpath(target.split('#')[0]).resolve().exists(),target
    print(json.dumps(dict(report=report_rel,comparisons=pairs,ready_A=len(ac['ready']),links_broken=0),ensure_ascii=False))


if __name__=='__main__':
    main()
