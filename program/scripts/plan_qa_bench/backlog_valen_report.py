"""Valen 원본 선택지 답안을 재검사하여 실패 포함 고정 분모로 집계한다."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from backlog_mx_report import paired, summarize

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def check_native(row, criteria):
    if not row.get('parsed') or row.get('error'):return False
    try:
        # Native API content is the original response, never generated {item} JSON.
        response=json.loads(row['content'])
        assert response==row['native_response']
        answer=response['answers']['selection'];probs=answer['probabilities']
        assert answer['type']=='choice' and set(probs)==set(criteria)
        assert all(type(v) in (float,int) and math.isfinite(v) and 0<=v<=1 for v in probs.values())
        assert math.isclose(sum(probs.values()),1,abs_tol=1e-6)
        chosen=answer['choice'];assert chosen==max(probs,key=probs.get)
        assert row['pick']==(None if chosen=='NONE' else int(chosen))
        assert row['choice_probabilities']==probs and row['p_null']==probs['NONE']
        assert response['usage']['input_tokens']<=32768
        return True
    except (ValueError,TypeError,AssertionError,KeyError):return False


def main():
    ap=argparse.ArgumentParser();ap.add_argument('job');ap.add_argument('suite',choices=['d','d2','d3','h','mx','smoke12']);a=ap.parse_args()
    folder=HERE/'results/gpu_backlog_20261008'/a.job
    start=json.loads((folder/'started.json').read_text(encoding='utf-8'))
    native_folder=ROOT/'datasets/travel/valen_native_eval_20261009'
    prompt=native_folder/(a.suite+'.json')
    assert hashlib.sha256(prompt.read_bytes()).hexdigest()==start['prompt_sha256']
    gold=json.loads(prompt.read_text(encoding='utf-8'));ref={x['i']:x for x in gold}
    answer=folder/f"d_test_{start['job']['tag']}.jsonl"
    rows=[json.loads(l) for l in answer.read_text(encoding='utf-8').splitlines()]
    assert len(rows)==len({r['i'] for r in rows}) and {r['i'] for r in rows}<=set(ref)
    for r in rows:
        x=ref[r['i']];assert all(r[k]==x[k] for k in ['set','qi','gold','type'])
        assert not r.get('parsed') or check_native(r,x['request']['questions']['selection']['criteria']), 'Native output contract mismatch'
    run={x['i']:x for x in rows}
    single=[x for x in gold if x['type']!='compound_intent']
    pos=[x for x in single if x['gold'] is not None];neg=[x for x in single if x['gold'] is None]
    result=dict(model='Valen-0.8B original native choice head',our_training=False,publisher_training='Developer decision SFT',
        expected=len(gold),saved=len(rows),missing=len(gold)-len(rows),
        failed_or_unparsed=sum(not r.get('parsed') or bool(r.get('error')) for r in rows),
        full=summarize(gold,run),positive=summarize(pos,run),negative=summarize(neg,run),
        single_expected=len(single),compound_diagnostic_only=len(gold)-len(single),
        subtypes={t:summarize([x for x in gold if x['type']==t],run) for t in sorted({x['type'] for x in gold})},
        prompt_sha256=hashlib.sha256(prompt.read_bytes()).hexdigest(),
        answer_sha256=hashlib.sha256(answer.read_bytes()).hexdigest(),
        probability_kind='Native choice head normalized candidate probability; not next token, verbal certainty or JSON output',
        original_content_contract_checked=True,execution=start,repetitions=1,final_ranking=False)
    if a.suite=='mx':
        mixed=[x for x in gold if x['kind']=='mixed'];control=[x for x in gold if x['kind']=='control']
        result['mixed_positive']=summarize([x for x in mixed if x['gold'] is not None],run)
        result['mixed_negative']=summarize([x for x in mixed if x['gold'] is None],run)
        result['paired_positive']=paired([x for x in gold if x['gold'] is not None],run)
        result['control_negative']=summarize([x for x in control if x['gold'] is None],run)
        mp,mn=result['mixed_positive'],result['mixed_negative'];cn=result['control_negative']
        gates=dict(normal_accuracy=mp['correct']/mp['total']>=.95,
                   false_pick=mn['false_pick']/mn['total']<=.01,
                   normal_loss=result['paired_positive']['loss_pp']<=2,
                   false_pick_increase=100*(mn['false_pick']/mn['total']-cn['false_pick']/cn['total'])<=1)
        result.update(gates=gates,gates_passed=sum(gates.values()),gates_total=4)
    with (folder/'native_counts.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    with (folder/'native_report.md').open('x',encoding='utf-8') as f:
        f.write(f'# Valen-0.8B 원본 — {a.suite}\n\n우리 자료 추가 학습 없음, 개발사 결정 학습 있음. 일반 JSON 생성 대신 원본 선택지 API를 사용했습니다. 실패·미완료는 전체 고정 분모에서 빼지 않습니다.\n\n| 할 일 | 상태 | 진행 |\n|---|---|---|\n')
        for label,n,d in [('답안 보관',len(rows),len(gold)),('정상 요청 정답',result['positive']['correct'],len(pos)),('요청없음 오지목',result['negative']['false_pick'],len(neg))]:
            if d:f.write(f'| {label} | 실측 | {n}/{d} = {100*n/d:.2f}% |\n')
        f.write('\n선택지 확률은 결정 head 출력이며 다음 토큰 확률·말로 한 확신도와 다릅니다. D의 복합 66문항은 단일 선택 진단이며 복수 항목 완전 정답으로 간주하지 않습니다. 기존 개발·회귀 자료의 1회 시험으로 최종 순위·제품 채택은 보류합니다.\n\n[전체 집계·실패 포함 분모·원본 계약](native_counts.json)\n')
    print(json.dumps({k:result[k] for k in ['expected','saved','missing','failed_or_unparsed','positive','negative']},ensure_ascii=False))

if __name__=='__main__':main()
