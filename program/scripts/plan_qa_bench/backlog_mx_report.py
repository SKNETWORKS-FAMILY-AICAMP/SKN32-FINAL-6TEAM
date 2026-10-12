"""모델의 MX 결과를 고정 전체 분모와 일정별 구간으로 집계한다. 새 모델 호출 없음."""
import argparse, hashlib, json, sys
from pathlib import Path
from collections import defaultdict
import numpy as np
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE.parent/'eval_kit'))
from stats import wilson, mcnemar_exact
sys.stdout.reconfigure(encoding='utf-8')
POS={'MX1','MX2','MX6a'}

def valid(row):
    return row is not None and bool(row.get('parsed')) and not row.get('error')

def summarize(items, answers):
    correct=0; false_pick=0; failed=0
    for x in items:
        r=answers.get(x['i'])
        failed+=not valid(r)
        correct+=valid(r) and r.get('pick')==x['gold']
        false_pick+=x['gold'] is None and valid(r) and r.get('pick') is not None
    n=len(items)
    return {'total':n,'correct':int(correct),'false_pick':int(false_pick),'failed_or_missing':int(failed),
            'correct_wilson95':wilson(correct,n),'false_pick_wilson95':wilson(false_pick,n)}

def good(x,answers):
    r=answers.get(x['i'])
    return valid(r) and r.get('pick')==x['gold']

def false_pick_increase(control,mixed):
    return 100*(mixed['false_pick']/mixed['total']-control['false_pick']/control['total'])

def paired(items,answers):
    groups=defaultdict(dict)
    for x in items: groups[x['pair']][x['kind']]=x
    assert all(set(v)=={'control','mixed'} for v in groups.values())
    units=defaultdict(lambda:np.zeros(3,dtype=float))
    controls=[];mixed=[]
    for pair in groups.values():
        c,m=pair['control'],pair['mixed']
        assert c['itin']==m['itin'] and c['gold']==m['gold'] and c['cat']==m['cat']
        cc,mm=good(c,answers),good(m,answers)
        controls.append(cc);mixed.append(mm)
        units[c['itin']]+=np.array([int(cc),int(mm),1])
    a=np.array(list(units.values()))
    rng=np.random.default_rng(7)
    samples=a[rng.integers(0,len(a),size=(2000,len(a)))].sum(axis=1)
    rates_c=samples[:,0]/samples[:,2]; rates_m=samples[:,1]/samples[:,2]
    loss=rates_c-rates_m
    return {'pairs':len(groups),'itineraries':len(units),'correct_control':int(sum(controls)),
            'correct_mixed':int(sum(mixed)),'loss_pp':100*(sum(controls)-sum(mixed))/len(groups),
            'loss_cluster95_pp':(100*np.quantile(loss,.025),100*np.quantile(loss,.975)),
            'mixed_accuracy_cluster95':(np.quantile(rates_m,.025),np.quantile(rates_m,.975)),
            'paired_exact':mcnemar_exact(controls,mixed),'bootstrap_replicates':2000,'bootstrap_seed':7}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('job');args=ap.parse_args()
    folder=HERE/'results/gpu_backlog_20261008'/args.job
    started=json.loads((folder/'started.json').read_text(encoding='utf-8'))
    answer=folder/f"d_test_{started['job']['tag']}.jsonl"
    golden=ROOT/'datasets/travel/mx_testset/mx_main_prompts.json'
    items=json.loads(golden.read_text(encoding='utf-8'))
    rows=[json.loads(l) for l in answer.read_text(encoding='utf-8').splitlines()]
    answers={r['i']:r for r in rows}; gold={x['i']:x for x in items}
    assert len(answers)==len(rows),'Duplicate answers'
    assert set(answers)<=set(gold),'Unexpected answer IDs'
    assert all(r['gold']==gold[i]['gold'] and r['type']==gold[i]['type'] for i,r in answers.items()),'Gold/type mismatch'
    by={}
    for kind in ['control','mixed']:
        by[kind]={label:summarize([x for x in items if x['kind']==kind and (x['cat'] in POS)==positive],answers) for label,positive in [('request',True),('no_request',False)]}
    pair_stats={label:paired([x for x in items if (x['cat'] in POS)==positive],answers) for label,positive in [('request',True),('no_request',False)]}
    p,n=by['mixed']['request'],by['mixed']['no_request']
    errors=sum(not valid(r) for r in answers.values());missing=len(set(gold)-set(answers))
    fp_increase=false_pick_increase(by['control']['no_request'],n)
    gates={'request_accuracy':p['correct']/p['total']>=.95,'false_pick':n['false_pick']/n['total']<=.01,
           'request_loss':pair_stats['request']['loss_pp']<=2,'false_pick_increase':fp_increase<=1}
    subtypes={cat:summarize([x for x in items if x['cat']==cat and x['kind']=='mixed'],answers) for cat in sorted({x['cat'] for x in items})}
    publisher=started['job'].get('publisher_training') or ('coding RL' if args.job.startswith('frog') else 'See publisher model card')
    result={'model':started['job']['label'],'our_training':started['job']['our_training'],'publisher_training':publisher,
      'saved':len(rows),'expected':len(items),'missing':missing,'failed_or_unparsed':errors,'repetitions':1,
      'counts':by,'paired':pair_stats,'subtypes_mixed':subtypes,'sources':{src:{kind:{label:summarize([x for x in items if x['src']==src and x['kind']==kind and (x['cat'] in POS)==positive],answers) for label,positive in [('request',True),('no_request',False)]} for kind in ['control','mixed']} for src in ['code','llm']},
      'aggregate_gates':gates,'aggregate_gates_passed':sum(gates.values()),'aggregate_gates_total':4,
      'subtype_gates':{cat:subtypes[cat]['false_pick']/subtypes[cat]['total']<=.03 for cat in ['MX3','MX4','MX5a']},
      'complete_valid':missing==0 and errors==0,'failed_records':[r for r in rows if not valid(r)],
      'false_pick_increase_pp':fp_increase,'answer_sha256':hashlib.sha256(answer.read_bytes()).hexdigest(),
      'gold_sha256':hashlib.sha256(golden.read_bytes()).hexdigest(),'execution':started,
      'limits':['one run','existing developer/regression suite; not new independent final holdout','paired exact p does not remove shared itinerary correlation; cluster intervals supplied','no complete matched original cohort ranking','token p_null is not verbal confidence or calibrated option probability']}
    with (folder/'mx_counts.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    display=('Jev 계열 모델 중 '+result['model']) if result['model'].startswith('Winnow') else result['model']
    report=f'''# {display} — 혼합 요청 평가

우리 자료 추가 학습 여부: {result['our_training']}. 개발사 학습: {result['publisher_training']}. 기존 혼합·대조 문항을 각각 2,007개씩 평가했습니다.

| 항목 | 상태 | 진행 |
|---|---|---|
| 답안 보관 | 완료 | {len(rows)}/{len(items)} = {100*len(rows)/len(items):.2f}% |
| 혼합 정상 요청 정답 | 실측 | {p['correct']}/{p['total']} = {100*p['correct']/p['total']:.2f}% |
| 혼합 요청 없음 오지목 | 실측 | {n['false_pick']}/{n['total']} = {100*n['false_pick']/n['total']:.2f}% |
| 사전 합산 기준 | 실측 | {sum(gates.values())}/4 = {100*sum(gates.values())/4:.2f}% |

정상 요청 분모는 혼합 문장 중 정답 항목이 있는 문항, 오지목 분모는 혼합 문장 중 정답이 없는 문항입니다. 실패·미완료를 분모에서 빼지 않았습니다. 미완료 {missing}개, 오류·해석 실패 {errors}개입니다.

| 부류 | 대조 정답 | 혼합 정답 | 정답률 손실 | 일정별 95% 구간 |
|---|---:|---:|---:|---|
'''
    for label,st in pair_stats.items():
        lo,hi=st['loss_cluster95_pp']
        report+=f"| {label} | {st['correct_control']}/{st['pairs']} | {st['correct_mixed']}/{st['pairs']} | {st['loss_pp']:+.2f}%p | {lo:+.2f} ~ {hi:+.2f}%p |\n"
    report+=f'\n실제 오지목 증가 계수는 {fp_increase:+.2f}%p입니다. 오류·미완료가 있으면 요청 없음 정답률 손실과 오지목 증가가 다를 수 있으므로 사전 오지목 증가 기준은 실제 오지목 계수로 판정합니다. 59개 일정의 군집 부트스트랩 2,000회·시드7이며 모델 실행은1회입니다. 같은 입력의 대조 대비 손실이며 다른 모델 간 우열 검정이 아닙니다.\n\n'
    report+='유형·코드 연결/자연 혼합별 분자·분모, 짝지은 검정, 실행 버전·해시는 [집계 JSON](mx_counts.json)에 있습니다. 생성한 토큰의 확률과 말로 한 확신도를 같은 확률이라고 해석하지 않습니다. 다른 실행 경로와 속도를 직접 비교하지 않습니다. 기존 개발 자료이며 사람 정답 검수와 새 독립 보류 자료 검증을 대신하지 않습니다. 원본 비교군의 모든 시험이 끝나기 전 최종 순위를 정하지 않습니다.\n'
    with (folder/'mx_report.md').open('x',encoding='utf-8') as f:f.write(report)
    print(json.dumps({k:result[k] for k in ['saved','expected','missing','failed_or_unparsed','answer_sha256','counts','paired','aggregate_gates_passed','subtype_gates']},ensure_ascii=False))

if __name__=='__main__':main()
