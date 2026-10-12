"""이미 완료·회수된 단일 D/D2/D3 결과를 검증하고 새 기록으로 연결한다."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'program/scripts/plan_qa_bench/results/gpu_backlog_20261008'
DAILY = ROOT / 'program/research/daily_rag_slm'

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    job, observation, remote_hash = sys.argv[1:4]
    folder = BASE / job
    r = json.loads((folder / 'choice_counts.json').read_text(encoding='utf-8'))
    matched_path = folder/'matched_original.json'
    matched = json.loads(matched_path.read_text(encoding='utf-8')) if matched_path.exists() else None
    if matched:
        assert matched['trained_job'] == job and matched['suite'] == r['suite']
        assert matched['trained_answer_sha256'] == r['answer_sha256']
        assert matched['adapter_our_training'] and not matched['original_our_training']
        assert matched['frozen_input_script_engine_model_match'] and matched['full_ids_gold_type_match']
    answer = folder / f"d_test_{r['execution']['job']['tag']}.jsonl"
    rows = [json.loads(line) for line in answer.read_text(encoding='utf-8').splitlines()]
    names = {'D':'all_prompts.json','D2':'all_prompts_d2.json','D3':'all_prompts_d3.json'}
    gold_path = ROOT / 'program/scripts/plan_qa_bench/results/empty_probe' / names[r['suite']]
    gold = json.loads(gold_path.read_text(encoding='utf-8'))
    run = {x['i']:x for x in rows}
    assert len(rows) == len(run) == len(gold) == r['saved'] == r['expected'] and r['missing'] == 0
    assert set(run) == {x['i'] for x in gold}
    assert hashlib.sha256(answer.read_bytes()).hexdigest() == remote_hash == r['answer_sha256']
    assert hashlib.sha256(gold_path.read_bytes()).hexdigest() == r['gold_sha256'] == r['execution']['prompt_sha256']
    assert all(run[x['i']]['gold'] == x['gold'] and run[x['i']]['type'] == x['type'] for x in gold)
    valid = lambda x: bool(x.get('parsed')) and not x.get('error')
    for label,positive in [('positive',True),('negative',False)]:
        selected = [x for x in rows if x['type'] != 'compound_intent' and (x['gold'] is not None) == positive]
        assert len(selected) == r[label]['total']
        assert sum(valid(x) and x['pick'] == x['gold'] for x in selected) == r[label]['correct']
        assert sum(valid(x) and x['gold'] is None and x['pick'] is not None for x in selected) == r[label]['false_pick']
        assert sum(not valid(x) for x in selected) == r[label]['failed_or_missing']
    assert sum(not valid(x) for x in rows) == r['failed_or_unparsed']
    verification = {'saved':len(rows),'remote_hash_match':True,'fixed_prompt_hash_match':True,
        'exact_id_gold_type_match':True,'independent_direct_recount':True,'missing':0,
        'failed_or_unparsed':r['failed_or_unparsed'],'model_repetitions':1}
    with (folder / 'verification.json').open('x',encoding='utf-8') as f: json.dump(verification,f,indent=2)

    now = datetime.now()
    report_rel = f"final_project_cs/wiki/records/reports/{now:%Y-%m-%d_%H%M%S}_{job}-completion.md"
    backup_stamp = now.strftime('%Y-%m-%d_%H%M%S') + '_' + job + '_completion'
    assert not (ROOT / report_rel).exists()
    backups = []
    def save(rel,text):
        p = ROOT / rel
        if p.exists():
            b = p.parent / '_backup' / backup_stamp / p.name
            b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,b)
            backups.append(b.relative_to(ROOT).as_posix())
        p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
    state = json.loads((DAILY / 'gpu_backlog_2026-10-08.json').read_text(encoding='utf-8'))
    observations = {machine:(json.loads((BASE / f'{machine}_snapshot_{observation}.json').read_text(encoding='utf-8')),
                             json.loads((BASE / f'{machine}_conditions_{observation}.json').read_text(encoding='utf-8')))
                    for machine in ['A','B']}
    a,ac = observations['A']; b,bc = observations['B']
    assert a['state']['jobs'][job]['status'].startswith('completed')
    assert a['state']['jobs'][job]['failed_or_unparsed'] == r['failed_or_unparsed']
    assert str(ac['worker_pid']) in a['processes']
    assert len(ac['ready']) >= 3
    for machine,(snap,cond) in observations.items():
        state['gpu_'+machine].update({'snapshot':(BASE / f'{machine}_snapshot_{observation}.json').relative_to(ROOT).as_posix(),
            'conditions_snapshot':(BASE / f'{machine}_conditions_{observation}.json').relative_to(ROOT).as_posix(),
            'observed_at_utc':snap['observed_at_utc'],'instant_gpu_memory_and_utilization':snap['gpu_snapshot'],
            'root_available_bytes':cond['root_space']['available_bytes']})
    completed = [x for x in a['state']['jobs'].values() if x['status'].startswith('completed')]
    state['gpu_A'].update({'state':a['state'],'answers_saved_at_snapshot':a['answers'],'jobs_completed':len(completed),
        'jobs_completed_with_errors':sum(x['status']=='completed_with_errors' for x in completed),
        'jobs_running':sum(x['status']=='running' for x in a['state']['jobs'].values()),'jobs_ready_waiting':len(ac['ready']),
        'completed_'+job+'_archived':True})
    state['recorded_at'] = now.isoformat()
    state['latest_routine_observation'] = {'new_completed_jobs':1,'new_failed_jobs':0,
        'new_failed_or_unparsed_answers':r['failed_or_unparsed'],'queue_refill':False,'worker_restart':False,
        'reason':f'{job} archived; {len(ac["ready"])} prepared A jobs remain; B queue unchanged. Recheck base download space immediately before execution.',
        'recorded_at':now.isoformat()}
    save('program/research/daily_rag_slm/gpu_backlog_2026-10-08.json',json.dumps(state,ensure_ascii=False,indent=2)+'\n')
    day = json.loads((DAILY / '2026-10-08.json').read_text(encoding='utf-8'))
    assert not any(x.get('model') == r['model'] and x.get('suite') == r['suite'] for x in day['new_completed_evaluations'])
    entry = {k:r[k] for k in ['model','our_training','publisher_training','suite','saved','expected','missing',
                              'failed_or_unparsed','positive','negative','repetitions','final_ranking']}
    entry['report'] = report_rel
    if matched:
        entry['matched_original_evidence'] = matched_path.relative_to(ROOT).as_posix()
    day['new_completed_evaluations'].append(entry)
    save('program/research/daily_rag_slm/2026-10-08.json',json.dumps(day,ensure_ascii=False,indent=2)+'\n')
    def ratio(data,key):
        return f"{data[key]:,}/{data['total']:,} = {100*data[key]/data['total']:.2f}%" if data['total'] else '대상 문항 없음'
    display_model = ('Jev 계열 모델 중 ' if 'Winnow' in r['model'] else '') + r['model']
    p,n = r['positive'],r['negative']
    role = '우리 여행 자료로 추가 학습함' if r['our_training'] else '우리 여행 자료로 추가 학습하지 않은 배포 원본'
    body = f"{display_model}({role})의 {r['suite']} 답안{r['saved']:,}/{r['expected']:,}개를 보관했다. 정상 요청 정답{ratio(p,'correct')}, 기존 항목 선택 없음 오지목{ratio(n,'false_pick')}, 형식 실패{r['failed_or_unparsed']}개다. 실패·미완료는 분모에서 빼지 않았다."
    save('program/research/daily_rag_slm/2026-10-08.md',(DAILY / '2026-10-08.md').read_text(encoding='utf-8') +
         f"\n## {now:%H시%M분} — {r['model']} {r['suite']} 완료\n\n{body}\n\n[완료·검증·한계 리포트](../../../{report_rel}).\n")
    rel = 'final_project_cs/wiki/quality/slm-model-evaluation.md'
    save(rel,(ROOT / rel).read_text(encoding='utf-8') + f"\n`[실측 {now:%Y-%m-%d}]` {r['model']}의 {r['suite']} 답안을 회수했고 형식 실패를 원문·분모에 보존했다. [완료·검증 근거](../records/reports/{Path(report_rel).name}).\n")
    rel = 'final_project_cs/wiki/log.md'
    save(rel,(ROOT / rel).read_text(encoding='utf-8') + f"\n## {now:%Y-%m-%d} — {r['model']} {r['suite']} 완료\n\n답안·실패 원문과 고정 문항 대조를 보관했다. [완료 리포트](records/reports/{Path(report_rel).name}).\n")
    links = f"../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/{job}"
    role = '우리 여행 자료로 추가 학습함' if r['our_training'] else '우리 여행 자료로 추가 학습하지 않은 배포 원본'
    lines = [f"# {display_model} — {r['suite']} 완료",'',f"{role}의 시험 답안을 회수하고 실패를 보존했다.",'',
        '| 할 일 | 상태 | 진행 |','|---|---|---|',f"| 답안 보관·문항 대조 | 완료 | {r['saved']:,}/{r['expected']:,} = 100% |"]
    if p['total']:lines.append(f"| 정상 요청 정답 | 실측 | {ratio(p,'correct')} |")
    if n['total']:lines.append(f"| 항목 선택 없음 오지목 | 실측 | {ratio(n,'false_pick')} |")
    lines += [f"| 실패·해석 불가 | 보존 | {r['failed_or_unparsed']}/{r['expected']:,} = {100*r['failed_or_unparsed']/r['expected']:.2f}% |",'',
        '## 원본·조건·검증','',body,'',
        f"[답안]({links}/{answer.name}) · [실행 조건]({links}/started.json) · [유형별 집계·실패 원문]({links}/choice_counts.json) · [독립 직접 계수·해시 검증]({links}/verification.json).",'',
        f"GPU 서버 A 원본·로컬 사본 SHA256은 `{remote_hash}`로 같다. 고정 입력 해시·전체ID·정답·유형 및 정상/항목 없음 독립 직접 계수를 확인했다. 미완료0이며 배열이나 문자열 출력을 번호·null로 고쳐 정답 처리하지 않았다. 개발사 학습 역할 기록은 `{r['publisher_training']}`이다.",'',
        f"전체{r['expected']:,}개 중 단일 선택 집계{r['single_choice_expected']:,}개, 복합 문항{r['compound_diagnostic_total']}개는 별도 진단이다. 복합 문항을 단일 선택 전체 정확도로 해석하지 않는다."]
    chat = r['subtypes'].get('chitchat')
    if matched:
        lines += ['', '## 같은 기반 원본과 여행 어댑터', '',
            '개발사의 지시 학습·양자화 학습이 있는 배포 원본에 우리 여행 어댑터를 적용한 결과다. 같은 기반·전체 ID·정답·유형·입력·실행 코드·엔진을 대조했다. 원본의 실패도 해당 분모에 남겼다.', '',
            '| 항목 | 우리 여행 학습 없는 원본 | 우리 여행 어댑터 |', '|---|---:|---:|']
        for label,title,key in [('positive','정상 요청 정답','correct'),('negative','항목 선택 없음 오지목','false_pick')]:
            group = matched['groups'][label]
            if group['total']:
                lines.append(f"| {title} | {ratio(group['original'],key)} | {ratio(group['our_travel_adapter'],key)} |")
        lines += ['', f'[같은 문항 정확 검정·전체 해시 대조]({links}/matched_original.json). 실행1회이며 다중 비교·일정별 상관·시드 편차·독립 보류 검증을 대신하지 않는다. 다른 시험의 정상 요청 손실을 무효화하거나 최종 우열로 해석하지 않는다.',
            '[원본 대조 도구](../../../../program/scripts/plan_qa_bench/verify_choice_matched_original.py) · [대조 결과 연결 전 기록 도구 백업](../../../../program/scripts/plan_qa_bench/_backup/2026-10-08_172455_matched_original_choice_report/record_backlog_choice_completion.py).']
    if chat:lines += ['',f"잡담만의 오지목은 {ratio(chat,'false_pick')}이며 형식 실패{chat['failed_or_missing']}개다. 항목 선택 없음 전체와 잡담만의 분모는 다르다."]
    if r['failed_records']:
        lines += ['','## 형식 실패 원문','', '| 문항 ID | 유형 | 출력 |','|---|---|---|']
        for x in r['failed_records']:
            output = str(x.get('content',x.get('error'))).replace('|','\\|').replace('\n','<br>')
            lines.append(f"| {x['i']} | {x['type']} | `{output}` |")
    lines += ['','## 한계·실행 유지·백업','',
        '기존 개발/회귀 자료의 모델 실행1회다. 전체 원본 비교군의 모든 시험·반복·독립 보류 검증 전 최종 순위나 제품 채택을 확정하지 않는다. 말로 한 확신도와 토큰 확률, 모델 변경 정확도와 같은 모델 엔진 속도를 구분한다.',
        f"GPU 서버 A의 같은 실행기가 다음 평가를 수행하며 입력까지 준비된{len(ac['ready'])}개가 대기한다. GPU 서버 B의 기존 학습과 예약을 유지했다. 다음 기반 다운로드 직전 공간을 재확인한다. 중복 실행·실행기 추가·작업 중단·새 결제·모델 삭제는 하지 않았다.",'',
        '일일 Markdown/JSON·GPU 상태·평가 wiki·cs wiki log에 근거를 연결했다. 기존 원본 기록은 수정하지 않았다. 수정 직전 백업:', '']
    lines += [f'- [{x}](../../../../{x})' for x in backups]
    save(report_rel,'\n'.join(lines)+'\n')
    print(json.dumps({'saved':r['saved'],'failed':r['failed_or_unparsed'],'normal':[p['correct'],p['total']],
        'false_pick':[n['false_pick'],n['total']],'ready_A':len(ac['ready']),'report':report_rel,'backup_stamp':backup_stamp},ensure_ascii=False))

if __name__ == '__main__':main()
