"""완료·회수된 MX 답안을 재계수하고 백업한 상태 및 wiki에 연결한다."""
from pathlib import Path
from datetime import datetime
import hashlib, json, shutil, sys

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'program/scripts/plan_qa_bench/results/gpu_backlog_20261008'
DAILY=ROOT/'program/research/daily_rag_slm'

def main():
    job, observation, remote_hash=sys.argv[1:4]
    folder=BASE/job
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    r=read(folder/'mx_counts.json')
    answer=folder/f"d_test_{r['execution']['job']['tag']}.jsonl"
    rows=[json.loads(line) for line in answer.read_text(encoding='utf-8').splitlines()]
    gold_path=ROOT/'datasets/travel/mx_testset/mx_main_prompts.json'
    gold=read(gold_path);run={x['i']:x for x in rows}
    assert len(rows)==len(run)==len(gold)==r['expected']==r['saved']==4014
    assert set(run)=={x['i'] for x in gold} and r['missing']==0
    assert hashlib.sha256(answer.read_bytes()).hexdigest()==r['answer_sha256']==remote_hash
    assert hashlib.sha256(gold_path.read_bytes()).hexdigest()==r['gold_sha256']==r['execution']['prompt_sha256']
    assert all(run[x['i']]['gold']==x['gold'] and run[x['i']]['type']==x['type'] for x in gold)
    valid=lambda x:bool(x.get('parsed')) and not x.get('error')
    for kind in ['control','mixed']:
        for label,positive in [('request',True),('no_request',False)]:
            selected=[x for x in gold if x['kind']==kind and (x['gold'] is not None)==positive]
            st=r['counts'][kind][label]
            assert len(selected)==st['total']
            assert sum(valid(run[x['i']]) and run[x['i']]['pick']==x['gold'] for x in selected)==st['correct']
            assert sum(valid(run[x['i']]) and x['gold'] is None and run[x['i']]['pick'] is not None for x in selected)==st['false_pick']
            assert sum(not valid(run[x['i']]) for x in selected)==st['failed_or_missing']
    assert sum(not valid(x) for x in rows)==r['failed_or_unparsed']
    with (folder/'verification.json').open('x',encoding='utf-8') as f:
        json.dump({'remote_hash_match':True,'fixed_prompt_hash_match':True,'exact_id_gold_type_match':True,
            'independent_direct_recount':True,'saved':len(rows),'missing':0,'failed_or_unparsed':r['failed_or_unparsed']},f,indent=2)
    now=datetime.now(); stamp=now.strftime('%Y-%m-%d_%H%M%S')+'_'+job+'_completion'
    report=f'final_project_cs/wiki/records/reports/{stamp}.md';backups=[]
    assert not (ROOT/report).exists()
    def save(rel,text):
        path=ROOT/rel
        if path.exists():
            backup=path.parent/'_backup'/stamp/path.name
            backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,backup)
            backups.append(backup.relative_to(ROOT).as_posix())
        path.write_text(text,encoding='utf-8')
    observations={m:(read(BASE/f'{m}_snapshot_{observation}.json'),read(BASE/f'{m}_conditions_{observation}.json')) for m in ['A','B']}
    a,ac=observations['A'];b,bc=observations['B']
    assert a['state']['jobs'][job]['status'].startswith('completed')
    assert a['state']['jobs'][job]['failed_or_unparsed']==r['failed_or_unparsed']
    assert str(ac['worker_pid']) in a['processes'] and len(ac['ready'])>=3
    state=read(DAILY/'gpu_backlog_2026-10-08.json')
    assert 'qlora_train2.py /root/hf_models/spark_s1_4b' in b['processes'], 'Audit the changed B stage before recording'
    for machine,(snap,cond) in observations.items():
        state['gpu_'+machine].update({'snapshot':(BASE/f'{machine}_snapshot_{observation}.json').relative_to(ROOT).as_posix(),
            'conditions_snapshot':(BASE/f'{machine}_conditions_{observation}.json').relative_to(ROOT).as_posix(),
            'observed_at_utc':snap['observed_at_utc'],'instant_gpu_memory_and_utilization':snap['gpu_snapshot'],
            'root_available_bytes':cond['root_space']['available_bytes']})
    completed=[x for x in a['state']['jobs'].values() if x['status'].startswith('completed')]
    state['gpu_A'].update({'state':a['state'],'answers_saved_at_snapshot':a['answers'],'jobs_completed':len(completed),
        'jobs_completed_with_errors':sum(x['status']=='completed_with_errors' for x in completed),
        'jobs_running':sum(x['status']=='running' for x in a['state']['jobs'].values()),'jobs_ready_waiting':len(ac['ready']),
        'completed_'+job+'_archived':True})
    state['recorded_at']=now.isoformat()
    state['latest_routine_observation']={'new_completed_jobs':1,'new_failed_jobs':0,'new_failed_or_unparsed_answers':r['failed_or_unparsed'],
        'queue_refill':False,'worker_restart':False,'recorded_at':now.isoformat()}
    save('program/research/daily_rag_slm/gpu_backlog_2026-10-08.json',json.dumps(state,ensure_ascii=False,indent=2)+'\n')
    p,n=r['counts']['mixed']['request'],r['counts']['mixed']['no_request']
    cp,cn=r['counts']['control']['request'],r['counts']['control']['no_request']
    natural=r['sources']['llm']['mixed'];loss=r['paired']['request']
    day=read(DAILY/'2026-10-08.json')
    assert not any(x.get('model')==r['model'] and x.get('suite')=='MX / user E' for x in day['new_completed_evaluations'])
    entry={k:r[k] for k in ['model','our_training','publisher_training','saved','expected','missing','failed_or_unparsed','repetitions']}
    entry.update({'suite':'MX / user E','mixed_request_correct':p['correct'],'mixed_request_total':p['total'],
        'mixed_false_pick':n['false_pick'],'mixed_no_request_total':n['total'],'request_loss_pp':loss['loss_pp'],
        'aggregate_gates_passed':r['aggregate_gates_passed'],'aggregate_gates_total':4,'natural_mixed':natural,
        'final_ranking':False,'report':report})
    day['new_completed_evaluations'].append(entry)
    save('program/research/daily_rag_slm/2026-10-08.json',json.dumps(day,ensure_ascii=False,indent=2)+'\n')
    display=('Jev 계열 모델 중 '+r['model']) if r['model'].startswith('Winnow') else r['model']
    role='우리 여행 자료로 추가 학습함' if r['our_training'] else '우리 여행 자료 추가 학습 없는 배포 원본'
    ratio=lambda st,key:f"{st[key]:,}/{st['total']:,} = {100*st[key]/st['total']:.2f}%"
    summary=f"{display}({role})의 혼합 문장 답안4,014개를 보관했다. 정상 요청 정답{ratio(p,'correct')}, 요청 없음 오지목{ratio(n,'false_pick')}, 형식 실패{r['failed_or_unparsed']}개·미완료0이다. 사전 합산{r['aggregate_gates_passed']}/4 기준 통과다. 실패는 분모에서 빼지 않았다."
    save('program/research/daily_rag_slm/2026-10-08.md',(DAILY/'2026-10-08.md').read_text(encoding='utf-8')+
        f'\n## {now:%H시%M분} — {display} 혼합 문장 평가 완료\n\n{summary}\n\n[완료·실패·범위 리포트](../../../{report}).\n')
    for rel,tail in [
        ('final_project_cs/wiki/quality/slm-model-evaluation.md',f'\n`[실측 2026-10-08]` {display}의 혼합 문장 답안을 회수했고 형식 실패를 원문·분모에 보존했다. [완료·기준·한계 근거](../records/reports/{Path(report).name}).\n'),
        ('final_project_cs/wiki/log.md',f'\n## 2026-10-08 — {display} 혼합 문장 완료\n\n원본·우리 학습 여부를 구분하고 실패를 포함해 집계했다. [리포트](records/reports/{Path(report).name}).\n')]:
        save(rel,(ROOT/rel).read_text(encoding='utf-8')+tail)
    links=f'../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/{job}'
    lo,hi=loss['loss_cluster95_pp']
    body=f'''# {display} — 혼합 문장 완료

[실측] {summary}

| 할 일 | 상태 | 진행 |
|---|---|---|
| 답안 보관·문항 대조 | 완료 | 4,014/4,014개 = 100% |
| 혼합 정상 요청 정답 | 실측 | {ratio(p,'correct')} |
| 혼합 요청 없음 오지목 | 실측 | {ratio(n,'false_pick')} |
| 사전 합산 기준 | 실측 | {r['aggregate_gates_passed']}/4 = {25*r['aggregate_gates_passed']:.0f}% |

## 원본·분모·검증

혼합2,007개·대조2,007개이며 각 부류의 정상 요청1,033개·요청 없음974개다. 혼합의 정상 형식 실패{p['failed_or_missing']}개·요청 없음 실패{n['failed_or_missing']}개, 대조의 정상 실패{cp['failed_or_missing']}개·요청 없음 실패{cn['failed_or_missing']}개로 전체 실패{r['failed_or_unparsed']}개다. 요청 없음 혼합은 정답{n['correct']}개·오지목{n['false_pick']}개·실패{n['failed_or_missing']}개를 합해974개다. 실패는 실제 오지목 계수와 구분하지만 전체 정답률에는 오답으로 포함한다.

[답안]({links}/{answer.name}) · [실행 조건]({links}/started.json) · [집계·유형·실패 원문]({links}/mx_counts.json) · [독립 직접 계수·해시 검증]({links}/verification.json) · [작업 로그]({links}/job.log). GPU 서버 A 원본/로컬 답안 SHA256은`{remote_hash}`로 같다. 고정 입력 해시·전체ID·정답·유형과 대조/혼합 각 정상/요청 없음 직접 계수를 확인했다. 배열 등 계약 밖 출력을 번호나 null로 고쳐 정답 처리하지 않았다. 개발사 역할 기록은`{r['publisher_training']}`이며 우리 여행 추가 학습과 구분한다.

## 대조·자연 혼합·채택 한계

정상 요청 정답은 대조{cp['correct']}/{cp['total']}에서 혼합{p['correct']}/{p['total']}으로 변화했고 손실{loss['loss_pp']:.4f}%p다. 일정별95% 구간{lo:.4f}~{hi:.4f}%p, 59개 일정의 군집 부트스트랩2,000회·시드7이다. 점 추정 기준과 불확실성 구간을 구분한다. 요청 없음 정답률 손실과 실제 오지목 증가는 실패가 있으면 같지 않으며 실제 오지목 증가는{r['false_pick_increase_pp']:.4f}%p다. 사전 기준의 통과/실패 원문은 집계JSON을 따른다.

자연스럽게 작성한 혼합239개는 정상 요청{ratio(natural['request'],'correct')}·요청 없음 오지목{ratio(natural['no_request'],'false_pick')}이다. 코드로 이어 붙인1,768개와 분리했다. 사람 정답 검수 전이고 모델 합의로 선정된 기존 개발/회귀 자료이므로 실제 고객 자유 대화 전체를 대표하지 않는다.

모델 실행1회이며 전체 원본 비교군의 같은 세트 완료·반복·독립 고정 보류 검증 전 일반 우열·상위권·제품 채택을 확정하지 않는다. 원본의 이 결과를 우리 여행 학습판의 결과로 옮기지 않는다. 모델 변경 정확도와 같은 모델 엔진 속도, 토큰 확률과 말로 한 확신도를 구분한다.

## 다음 작업·도구·백업

GPU 서버 A는 같은 실행기로 다음 평가를 수행하고 입력까지 준비된{len(ac['ready'])}개가 대기한다. GPU 서버 B의 기존 Spark 여행 학습과 뒤5개 예약을 유지했다. 그중4개는 기존 기반·1개는 다운로드와 공간 재확인이 필요하다. B57 두 번째 시드 비교는 B56 완료 뒤 이어진다. 새 실행기·중복 시험·작업 중단·새 결제·기존 모델 삭제는 하지 않았다.

집계 스크립트는 원본과 학습판 모두의 실행 조건을 읽고 Winnow의 Jev 계열과 정확한 이름을 표시한다. 후속 예약 설명은 현재 B57을 포함하도록 보완했다. [수정 직전 기록 도구 백업](../../../../program/scripts/plan_qa_bench/_backup/2026-10-08_1500_mx_followup_counts/record_backlog_mx_completion.py). [수정 직전 스크립트 백업](../../../../program/scripts/plan_qa_bench/_backup/2026-10-08_1353_mx_model_role/backlog_mx_report.py). 변경된 일일 Markdown/JSON·GPU 상태·평가 wiki·cs log는 수정 직전에 보관했다. 과거 리포트·원본 답안은 수정하지 않았다.

'''
    body+='\n'.join(f'- [{x}](../../../../{x})' for x in backups)+'\n'
    save(report,body)
    print(json.dumps({'report':report,'backup_stamp':stamp,'normal':[p['correct'],p['total']],
        'false_pick':[n['false_pick'],n['total']],'errors':r['failed_or_unparsed'],'gates':r['aggregate_gates_passed'],
        'ready_A':len(ac['ready'])},ensure_ascii=False))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
