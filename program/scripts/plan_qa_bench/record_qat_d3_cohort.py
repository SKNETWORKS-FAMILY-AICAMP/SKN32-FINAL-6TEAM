"""같은 QAT 기반 원본·여행 어댑터 네 판의 완료된 D3만 대조한다."""
from pathlib import Path
from datetime import datetime
import json
import hashlib
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
    jobs = ['e4bqat_original_d3']+[f'e4bqat_{v}_d3' for v in ['oos1','oos2','oos3','oos2r']]
    results = {j:read(BASE/j/'choice_counts.json') for j in jobs}
    answers = {}
    goldpath = ROOT/'datasets/core/pointing/testset/synthetic_chitchat_plus_questions_v1/all_prompts_d3.json'
    gold = {x['i']:x for x in read(goldpath)}
    for job,r in results.items():
        assert r['saved'] == r['expected'] == 360 and r['missing'] == 0
        path = BASE/job/f"d_test_{r['execution']['job']['tag']}.jsonl"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == r['answer_sha256']
        assert hashlib.sha256(goldpath.read_bytes()).hexdigest() == r['gold_sha256'] == r['execution']['prompt_sha256']
        rows = [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines()]
        run = {x['i']:x for x in rows}
        assert len(rows) == len(run) == len(gold) and set(run) == set(gold)
        assert all(run[i]['gold'] == g['gold'] and run[i]['type'] == g['type'] for i,g in gold.items())
        answers[job] = run
    old = results[jobs[0]]
    assert not old['our_training']
    assert old['failed_or_unparsed'] == 1
    assert all(results[j]['failed_or_unparsed'] == 0 for j in jobs[1:])
    correct = lambda x: bool(x.get('parsed')) and not x.get('error') and x['pick'] == x['gold']
    paired = {}
    for job in jobs[1:]:
        r = results[job]
        assert r['our_training'] and read(BASE/job/'verification.json')['remote_hash_match']
        for key in ['engine_version','script_sha256','prompt_sha256']:
            assert r['execution'][key] == old['execution'][key]
        assert r['execution']['job']['model_sha256'] == old['execution']['job']['model_sha256']
        paired[job] = {}
        for label,positive in [('request',True),('no_request',False)]:
            ids = [i for i,g in gold.items() if (g['gold'] is not None) == positive]
            gain = sum(correct(answers[job][i]) and not correct(answers[jobs[0]][i]) for i in ids)
            loss = sum(correct(answers[jobs[0]][i]) and not correct(answers[job][i]) for i in ids)
            paired[job][label] = dict(total=len(ids), trained_only_correct=gain, original_only_correct=loss,
                exact_p=binomtest(gain,gain+loss).pvalue if gain+loss else 1)
    now = datetime.now();stamp = now.strftime('%Y-%m-%d_%H%M%S')+'_qat_d3_five_variants'
    report = 'final_project_cs/wiki/records/reports/'+stamp+'.md'
    with (BASE/(stamp+'_paired.json')).open('x',encoding='utf-8') as f:
        json.dump(dict(paired=paired,repetitions=1,final_ranking=False),f,indent=2)
    day = read(DAILY/'2026-10-08.json');backups = []
    def save(rel,text):
        p = ROOT/rel
        if p.exists():
            b = p.parent/'_backup'/stamp/p.name;b.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,b)
            backups.append(b.relative_to(ROOT).as_posix())
        p.write_text(text,encoding='utf-8')
    day['matched_qat_d3_summary'] = dict(report=report,variants=5,our_travel_adapter_variants=4,
        expected_per_variant=360,all_saved=True,final_ranking=False,holdout_validation_complete=False)
    save('program/research/daily_rag_slm/2026-10-08.json',json.dumps(day,ensure_ascii=False,indent=2)+'\n')
    state = read(DAILY/'gpu_backlog_2026-10-08.json')
    state['latest_routine_observation'].update(new_completed_jobs=2,report=report)
    save('program/research/daily_rag_slm/gpu_backlog_2026-10-08.json',json.dumps(state,ensure_ascii=False,indent=2)+'\n')
    summary = '같은 QAT 기반 원본과 여행 어댑터 네 판의 D3를 모두 보관했다. 정상 요청과 잡담 오지목을 함께 대조하며 기존 혼합 문장 손실·독립 보류·반복 검증 전 채택하지 않는다.'
    save('program/research/daily_rag_slm/2026-10-08.md',(DAILY/'2026-10-08.md').read_text(encoding='utf-8')+f'\n## {now:%H시%M분} — QAT 원본·어댑터 네 판 직접 선택 대조\n\n{summary}\n\n[완료 범위·짝지은 비교·백업](../../../{report}).\n')
    for rel,prefix in [('final_project_cs/wiki/quality/slm-model-evaluation.md','../records/reports/'),('final_project_cs/wiki/log.md','records/reports/')]:
        save(rel,(ROOT/rel).read_text(encoding='utf-8')+f'\n`[실측 2026-10-08]` QAT 원본과 여행 어댑터 네 판의 같은 직접 선택 시험을 대조했다. 혼합 문장·반복·독립 보류 검증 전 채택은 보류한다. [근거]({prefix}{stamp}.md).\n')
    ratio = lambda n,d:f'{n}/{d} = {100*n/d:.2f}%'
    lines = ['# QAT 원본·여행 어댑터 네 판의 직접 선택 D3', '',summary,'',
        '| 할 일 | 상태 | 진행 |','|---|---|---|','| 같은 문항 평가 회수 | 완료 | 5/5판 = 100% |',
        '| 전체 답안 | 완료 | 1,800/1,800 = 100% |','| 오류·해석 실패 | 원본의 실패 보존 | 1/1,800 = 0.06% |','',
        '## 원본과 추가 학습 역할','',
        '기반은 Gemma-4-E4B-it QAT Q4_0다. 개발사의 지시 학습·양자화 학습은 원본에도 있으며, 우리 여행 학습 없음과 구분한다. 여행 어댑터를 QAT 원본에 적용해 추론한 결과이며 어댑터 자체를 QAT 방식으로 새 학습했다는 뜻이 아니다.', '',
        '| 우리 여행 추가 학습 | 정상 요청 정답 | 잡담 오지목 | 오류·해석 실패 |','|---|---:|---:|---:|']
    for job,r in results.items():
        label = '없음 — 배포 원본' if not r['our_training'] else '어댑터 '+job.split('_')[1]
        lines.append(f"| {label} | {ratio(r['positive']['correct'],120)} | {ratio(r['negative']['false_pick'],240)} | {r['failed_or_unparsed']}/360 |")
    lines += ['', '정상 요청 분모120개는 정답 일정 항목이 있는 문항이고 잡담 분모240개는 항목 선택이 없어야 하는 문항이다. 실패는 해당 분모에 남기고 정확도에서 오답으로 처리한다. 실제 오지목은 형식 실패와 분리한다. 같은 항목을 반복한 soak 자료를 추가 정확도 표본으로 합치지 않는다.',
        f'[원본과 같은 문항 정확 검정](../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/{stamp}_paired.json). 전체 ID·정답·유형·기반 해시·입력·실행 코드·엔진을 대조했다. 각 실행1회이고, 원본과의 검정이 어댑터끼리 우열·반복 편차·다중 비교·독립 보류 검증을 대신하지 않는다.', '',
        '## 완료 답안·직접 검증·한계','']
    for job,r in results.items():
        link = '../../../../program/scripts/plan_qa_bench/results/gpu_backlog_20261008/'+job
        lines.append(f"- [{r['model']} 답안·실행 조건]({link}/) · [집계·Wilson 구간·오류 원문]({link}/choice_counts.json). 답안SHA256 `{r['answer_sha256']}`.")
    lines += ['', '기존 개발/회귀 자료이며 새 독립 보류720개 검증은 완료되지 않았다. D3 전체가 끝났다는 것이 일반 D·어려운 H·혼합 E·원본 비교군 전체 완료를 뜻하지 않는다. 기존 혼합 문장에서 발견된 정상 요청 손실도 그대로 유지한다. 모델 정확도와 같은 모델 엔진 속도를 구분하고 속도를 직접 비교하지 않는다.',
        'GPU 서버 A 기존 실행기는 일반 D를 수행하며 관측시 준비된7개가 대기한다. GPU 서버 B의 기존 Spark 학습과 뒤 예약을 유지하며 새 실행기·중단·중복·새 결제·모델 삭제는 없다.', '', '## 수정 직전 백업', '']
    lines += [f'- [{p}](../../../../{p})' for p in backups]
    text = '\n'.join(lines)+'\n';assert not (ROOT/report).exists();save(report,text)
    for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)',text):
        assert (ROOT/report).parent.joinpath(target.split('#')[0]).resolve().exists(),target
    print(json.dumps(dict(report=report,new_completed=2,new_saved=720,new_errors=0,all_d3_variants=5,paired=paired,links_broken=0)))


if __name__ == '__main__':
    main()
