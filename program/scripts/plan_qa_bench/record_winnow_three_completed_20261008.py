"""새 완료 답안 세 묶음을 원문·해시·같은 문항 대조로 검증하고 기록한다."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil
import sys
from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'program/scripts/plan_qa_bench/results/gpu_backlog_20261008'
DAILY = ROOT / 'program/research/daily_rag_slm'


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def valid(r):
    return bool(r.get('parsed')) and not r.get('error')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    a, ac = read(BASE/'A_snapshot_refill1455.json'), read(BASE/'A_conditions_refill1455.json')
    b, bc = read(BASE/'B_snapshot_refill1455.json'), read(BASE/'B_conditions_refill1455.json')
    assert len(ac['ready']) == 3 and str(a['worker_pid']) in a['processes']
    assert b['active_training_variants'] == ['spark_s1_4b_oos']
    remote_hashes = {Path(line.split()[1]).parent.name: line.split()[0]
                     for line in (BASE/'winnow_completed_remote_hashes_1455.txt').read_text().splitlines() if line.strip()}
    pairs, results = {}, {}
    for suite, count_file, gold_file in [
        ('D', 'choice_counts.json', 'empty_probe/all_prompts.json'),
        ('D2', 'choice_counts.json', 'empty_probe/all_prompts_d2.json'),
        ('H', 'h_counts.json', 'hard_set/h_set_test_30_20261015_agree.json')]:
        job = 'winnow_oos_'+suite.lower()
        original = 'winnow_original_'+suite.lower()
        r, before = read(BASE/job/count_file), read(BASE/original/count_file)
        results[suite] = r
        assert r['our_training'] and not before['our_training']
        assert r['execution']['job']['model'] == before['execution']['job']['model']
        for key in ['prompt_sha256', 'script_sha256', 'engine_version']:
            assert r['execution'][key] == before['execution'][key], key
        assert r['execution']['job']['lora'] and not before['execution']['job'].get('lora')
        answer = BASE/job/f"d_test_{r['execution']['job']['tag']}.jsonl"
        old_answer = BASE/original/f"d_test_{before['execution']['job']['tag']}.jsonl"
        rows = [json.loads(x) for x in answer.read_text(encoding='utf-8').splitlines()]
        old = [json.loads(x) for x in old_answer.read_text(encoding='utf-8').splitlines()]
        gold_path = ROOT/'program/scripts/plan_qa_bench/results'/gold_file
        gold = read(gold_path)
        run, ref, prior = ({x['i']: x for x in values} for values in [rows, gold, old])
        assert len(rows) == len(run) == len(ref) == len(prior) == r['expected']
        assert set(run) == set(ref) == set(prior)
        assert hashlib.sha256(answer.read_bytes()).hexdigest() == remote_hashes[job] == r['answer_sha256']
        assert hashlib.sha256(gold_path.read_bytes()).hexdigest() == r['gold_sha256'] == r['execution']['prompt_sha256']
        assert all(run[i]['gold'] == prior[i]['gold'] == ref[i]['gold'] and
                   run[i]['type'] == prior[i]['type'] == ref[i]['type'] for i in ref)
        assert r['missing'] == r['failed_or_unparsed'] == 0
        stats = {}
        for label, positive in [('positive', True), ('negative', False)]:
            ids = [i for i, g in ref.items() if g['type'] != 'compound_intent' and (g['gold'] is not None) == positive]
            correct = lambda row: valid(row) and row['pick'] == row['gold']
            assert len(ids) == r[label]['total']
            assert sum(correct(run[i]) for i in ids) == r[label]['correct']
            assert sum(valid(run[i]) and ref[i]['gold'] is None and run[i]['pick'] is not None for i in ids) == r[label]['false_pick']
            gained = sum(correct(run[i]) and not correct(prior[i]) for i in ids)
            lost = sum(correct(prior[i]) and not correct(run[i]) for i in ids)
            stats[label] = dict(total=len(ids), original_correct=sum(correct(prior[i]) for i in ids),
                trained_correct=sum(correct(run[i]) for i in ids), trained_only_correct=gained,
                original_only_correct=lost, exact_p=binomtest(gained, gained+lost).pvalue if gained+lost else 1.0,
                original_false_pick=before[label]['false_pick'], trained_false_pick=r[label]['false_pick'],
                original_failures=before[label]['failed_or_missing'], trained_failures=r[label]['failed_or_missing'])
        pairs[suite] = stats
        with (BASE/job/'verification.json').open('x', encoding='utf-8') as f:
            json.dump(dict(saved=len(rows), remote_hash_match=True, fixed_prompt_hash_match=True,
                exact_ids_gold_type=True, direct_recount=True, same_base_script_engine=True,
                missing=0, failed_or_unparsed=0, repetitions=1), f, indent=2)

    now = datetime.now()
    stem = now.strftime('%Y-%m-%d_%H%M%S')+'_winnow_three_completion_refill'
    report_rel = 'final_project_cs/wiki/records/reports/'+stem+'.md'
    backups = []
    def save(rel, text):
        p = ROOT/rel
        if p.exists():
            dest = p.parent/'_backup'/stem/p.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)
            backups.append(dest.relative_to(ROOT).as_posix())
        p.write_text(text, encoding='utf-8')

    with (BASE/(stem+'_paired.json')).open('x', encoding='utf-8') as f:
        json.dump(pairs, f, ensure_ascii=False, indent=2)
    state = read(DAILY/'gpu_backlog_2026-10-08.json')
    for machine, snap, cond in [('A', a, ac), ('B', b, bc)]:
        state['gpu_'+machine].update(snapshot=(BASE/f'{machine}_snapshot_refill1455.json').relative_to(ROOT).as_posix(),
            conditions_snapshot=(BASE/f'{machine}_conditions_refill1455.json').relative_to(ROOT).as_posix(),
            observed_at_utc=snap['observed_at_utc'], instant_gpu_memory_and_utilization=snap['gpu_snapshot'],
            root_available_bytes=cond['root_space']['available_bytes'])
    completed = [v for v in a['state']['jobs'].values() if v['status'].startswith('completed')]
    state['gpu_A'].update(state=a['state'], answers_saved_at_snapshot=a['answers'],
        jobs_registered=len(a['manifest']['jobs']), planned_answers=sum(j['expected'] for j in a['manifest']['jobs']),
        jobs_completed=len(completed), jobs_completed_with_errors=sum(v['status']=='completed_with_errors' for v in completed),
        jobs_running=1, jobs_ready_waiting=len(ac['ready']),
        refill_evidence='program/scripts/plan_qa_bench/results/gpu_backlog_20261008/manifest_qat_refill_1454.json')
    for suite in results: state['gpu_A']['completed_winnow_oos_'+suite.lower()+'_archived'] = True
    state.update(recorded_at=now.isoformat(), latest_routine_observation=dict(new_completed_jobs=3,
        new_failed_jobs=0, new_failed_or_unparsed_answers=0, queue_refill=True, evaluations_added=3,
        worker_restart=False, report=report_rel))
    save('program/research/daily_rag_slm/gpu_backlog_2026-10-08.json', json.dumps(state, ensure_ascii=False, indent=2)+'\n')
    day = read(DAILY/'2026-10-08.json')
    for suite, r in results.items():
        assert not any(x.get('model')==r['model'] and x.get('suite')==suite for x in day['new_completed_evaluations'])
        entry = {k:r[k] for k in ['model','our_training','publisher_training','saved','expected','missing',
                                  'failed_or_unparsed','positive','negative','repetitions','final_ranking']}
        entry.update(suite=suite, report=report_rel)
        day['new_completed_evaluations'].append(entry)
    day['gpu_queue']['registered_evaluations'] = len(a['manifest']['jobs'])
    save('program/research/daily_rag_slm/2026-10-08.json', json.dumps(day, ensure_ascii=False, indent=2)+'\n')
    arm_path = ROOT/'program/scripts/plan_qa_bench/results/arm_serving_20261008/observation_1455.json'
    arm, ar = read(arm_path), read(DAILY/'arm_serving_2026-10-08.json')
    assert arm['health']['status']=='ok' and arm['resource_summary']['five_minute_target_verified']
    ar.update(last_observed_at=arm['observed_at'], current_job=arm['active']['job_id'],
        current_saved=arm['active']['saved'], current_expected=arm['active']['expected'],
        resource_measurement=arm['resource_summary'], latest_raw_observation=arm_path.relative_to(ROOT).as_posix())
    save('program/research/daily_rag_slm/arm_serving_2026-10-08.json', json.dumps(ar, ensure_ascii=False, indent=2)+'\n')
    line = f'Jev 계열 모델 중 Winnow-E4B(우리 여행 자료로 학습)의 D·D2·H 완료 답안5,051개를 보관·대조했다. QAT 배포 원본의 누락 평가3개를 기존 GPU 서버 A 실행기에 추가했고 GPU 서버 B 학습과 Oracle ARM 실제 추론을 유지했다.'
    save('program/research/daily_rag_slm/2026-10-08.md', (DAILY/'2026-10-08.md').read_text(encoding='utf-8')+
         f'\n## {now:%H시%M분} — 완료 회수·대기열 보충\n\n{line}\n\n[검증·비교·백업 근거](../../../{report_rel}).\n')
    for rel, prefix in [('final_project_cs/wiki/quality/slm-model-evaluation.md','../records/reports/'),
                        ('final_project_cs/wiki/operations/gpu-work-queue.md','../records/reports/'),
                        ('final_project_cs/wiki/log.md','records/reports/')]:
        save(rel, (ROOT/rel).read_text(encoding='utf-8')+
             f'\n`[실측 {now:%Y-%m-%d}]` 완료 답안 회수와 QAT 원본 누락 평가 예약을 확인했다. [근거]({prefix}{stem}.md).\n')
    lines = ['# Winnow-E4B 여행 학습판 추가 평가 완료와 GPU 일감 보충','',line,'',
        '| 할 일 | 상태 | 진행 |','|---|---|---|','| 새 완료 답안 검증 | 완료 | 5,051/5,051 = 100% |',
        '| GPU 서버 A 준비된 대기 평가 | 예약 | 3/3 = 100% |',
        '| Oracle ARM 현재 설정 | 진행 | 7/360 = 1.94% |','',
        '## 같은 기반 모델·문항 비교','',
        '두 판은 같은 Q8_0 기반·입력 해시·실행 코드 해시·llama.cpp 버전이며 추가 학습 어댑터만 다르다. 원본은 우리 자료로 학습하지 않았고 개발사 결정 학습 역할은 실행 기록에 따로 적었다. 실패는 오답이며 분모에서 빼지 않았다. 오지목과 형식 실패는 별도다.','',
        '| 묶음 | 정상 요청 정답: 원본 → 여행 학습판 | 요청 없음 오지목: 원본 → 여행 학습판 | 형식 실패: 원본 → 학습판 |',
        '|---|---|---|---|']
    for suite, r in results.items():
        original = read(BASE/('winnow_original_'+suite.lower())/('h_counts.json' if suite=='H' else 'choice_counts.json'))
        p,n = pairs[suite]['positive'], pairs[suite]['negative']
        positive = f"{p['original_correct']}/{p['total']} → {p['trained_correct']}/{p['total']}" if p['total'] else '대상 없음'
        lines.append(f"| {suite} | {positive} | {n['original_false_pick']}/{n['total']} → {n['trained_false_pick']}/{n['total']} | {original['failed_or_unparsed']} → 0 |")
    paired_name=stem+'_paired.json'
    lines += ['',f'[같은 문항 정답 유지·개선·손실과 정확 검정](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/{paired_name}).',
        '', '원본 개발/회귀 자료의 각1회 실행이다. 일정별 문항 상관·여러 비교·반복 편차를 통제한 최종 검정이 아니다. MX는3057/4014개 저장 단계이며 완성 전 순위·제품 채택을 확정하지 않는다. 독립 보류 자료720개와 반복 검증은 아직 완료되지 않았다.',
        '', '## 회수·예약·실제 환경', '']
    for suite in results:
        job='winnow_oos_'+suite.lower()
        lines.append(f'- [{suite} 답안·실행 조건·검증](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/{job}/): GPU 서버 A 원본 SHA256, 전체ID·정답·유형, 고정 입력 해시와 독립 계수를 대조했다.')
    lines += ['', '기존 Gemma-4-E4B-it QAT Q4_0 배포 원본의 D2·H·MX 총6,330문항을 예약했다. 로컬 결과 파일 목록과 GPU 서버 A 기존 답안 목록을 확인한 범위에서 해당 원본의 세 묶음은 완료 기록이 없으며, QAT 어댑터 시험과는 구분했다. 모델 파일5,154,939,136바이트·GGUF 헤더·전체SHA256을 검증했다. 다운로드는 필요 없다. 기존 Gemma 구조 실행기를 쓰며 이 가중치의 GPU 연결·정확도 성공은 아직 실행 전이다.',
        'GPU 서버 A의 manifest 원본을 원격 _backup에 보관하고 같은 폴더의 임시 파일을 원자적으로 교체했다. 실행기 PID는 유지했고 중복 실행이나 진행 중인 작업 중단은 하지 않았다. 총25개49,360문항 예약이며 현재 계산1개, 준비된 다음 평가3개다.',
        'GPU 서버 B는 Spark 본 학습1개, 기존 입력으로 준비된 학습4개, 기반 다운로드·공간 확인이 필요한 후보1개를 유지한다. Oracle ARM은 정상 추론 중 최근300.06초 두 코어 전체 대비CPU89.96%, host busy90.16%, steal0.16%, 작업 메모리8,924,016,640바이트(파일 캐시 포함), 남은 공간54,411,616,256바이트다. 목표 이상 연속 표본1,050.24초이며24시간 유지 증거는 아니다. 실제 답안7개는 모두 잡담이며 전체 정확도나 정상 요청 정답률로 해석하지 않는다.',
        '', '## 수정 직전 백업', '']
    lines += [f'- [{x}](../../../../{x})' for x in backups]
    save(report_rel, '\n'.join(lines)+'\n')
    print(json.dumps(dict(report=report_rel, comparisons=pairs, ready_A=len(ac['ready']), arm_cpu=arm['resource_summary']['cpu_pct_two_cores']), ensure_ascii=False))


if __name__=='__main__':
    main()
