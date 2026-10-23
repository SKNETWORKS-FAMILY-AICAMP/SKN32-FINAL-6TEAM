"""복수 항목 계약의 B·C를 고정 전체 분모로 집계하고 형식 실패를 보존한다."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE/'server/queues'))
sys.path.insert(0, str(HERE.parent/'eval_kit'))
from multi_items_eval_20261009 import parse_items
from stats import wilson


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('job')
    ap.add_argument('--prompts', default=str(HERE.parents[2]/'datasets/travel/multi_items_eval_20261009/prompts.json'))
    ap.add_argument('--output', default='multi_items_counts.json')
    args = ap.parse_args()
    folder = HERE/'results/gpu_backlog_20261008'/args.job
    start = json.loads((folder/'started.json').read_text(encoding='utf-8'))
    prompt = Path(args.prompts)
    digest = hashlib.sha256(prompt.read_bytes()).hexdigest()
    assert digest == start['prompt_sha256'], 'Frozen prompt hash mismatch'
    gold = json.loads(prompt.read_text(encoding='utf-8')); refs = {x['i']:x for x in gold}
    assert len(gold) == len(refs) == 835
    answers = folder/f"d_test_{start['job']['tag']}.jsonl"
    raw = [json.loads(line) for line in answers.read_text(encoding='utf-8').splitlines() if line.strip()]
    rows = {x['i']:x for x in raw}; assert len(raw) == len(rows), 'Duplicate IDs'
    assert set(rows) <= set(refs), 'Unexpected ID'
    good={};failed=[]
    for ident,x in rows.items():
        ref=refs[ident]
        assert all(x[k] == ref[k] for k in ['set','qi','type','gold','gold_set'])
        parsed,picks=parse_items(x.get('content'),set(ref['allowed_items']))
        valid=parsed and bool(x.get('parsed')) and not x.get('error')
        if valid: assert picks==x['pick']
        good[ident]=valid
        if not valid: failed.append(x)
    def summarize(subset):
        B=C=first=FP=bad=0
        for x in subset:
            r=rows.get(x['i']); valid=good.get(x['i'],False); want=set(x['gold_set'])
            pick=set(r['pick']) if valid else set()
            B+=bool(valid and ((pick & want) if want else not pick))
            C+=bool(valid and pick==want)
            first+=bool(valid and ((r['pick'] and r['pick'][0]==x['gold']) if want else not r['pick']))
            FP+=bool(valid and not want and pick)
            bad+=not valid
        return dict(total=len(subset),B=B,C=C,first_item_diagnostic=first,false_pick=FP,failed_or_missing=bad,C_wilson95=wilson(C,len(subset)))
    result=dict(model=start['job']['label'],our_training=start['job']['our_training'],publisher_training=start['job'].get('publisher_training'),saved=len(raw),expected=835,missing=835-len(raw),failed_or_unparsed=len(failed),metadata_matches=len(raw),counts={name:summarize([x for x in gold if n is None or len(x['gold_set'])==n]) for name,n in [('all',None),('single',1),('compound',2),('no_request',0)]},answer_sha256=hashlib.sha256(answers.read_bytes()).hexdigest(),prompt_sha256=digest,execution=start,failed_records=failed,repetitions=1,independent_holdout=False,final_ranking=False,limits=['Changed output contract; compare only models with this exact contract','Existing development fixture; not new independent holdout','No output grammar enforcement; exact JSON and allowed IDs required','Failure and missing count as wrong; observed false picks separately reported'])
    target=folder/args.output
    with target.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:result[k] for k in ['saved','expected','missing','failed_or_unparsed','counts']},ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
