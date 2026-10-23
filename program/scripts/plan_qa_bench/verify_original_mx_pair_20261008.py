"""원본 MX 두 판의 실제 계수·형식 실패·짝지은 비교를 보관한다."""
from pathlib import Path
import json, hashlib, sys
import numpy as np
from collections import defaultdict
from backlog_mx_report import summarize, false_pick_increase, valid
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'eval_kit'))
from stats import mcnemar_exact
items=json.loads((ROOT/'datasets/core/pointing/testset/requests_inside_chitchat_pairs_v1/mx_main_prompts.json').read_text(encoding='utf-8'))
folder=HERE/'results/gpu_backlog_20261008/e4bbase_mx'
counts=json.loads((folder/'mx_counts.json').read_text(encoding='utf-8'))
raw=folder/'d_test_mx_backlog_e4bbase.jsonl'
assert hashlib.sha256(raw.read_bytes()).hexdigest()=='541960a76220dd7a9a38863218718074c462f6182256c6b3f80babdbd72ee29f'
gemma={r['i']:r for r in [json.loads(l) for l in raw.read_text(encoding='utf-8').splitlines()]}
frog={r['i']:r for r in [json.loads(l) for l in (folder.parent/'frog_mx/d_test_mx_backlog_frog.jsonl').read_text(encoding='utf-8').splitlines()]}
assert len(gemma)==len(frog)==len(items)==4014 and set(gemma)==set(frog)=={x['i'] for x in items}
assert counts['failed_or_unparsed']==1 and counts['missing']==0
assert counts['gold_sha256']==counts['execution']['prompt_sha256']
# 해석 실패는 null 정답으로 처리하지 않고 실제 오지목과 구분한다.
controls=[x for x in items if x['kind']=='control' and x['gold'] is None]
cc=summarize(controls,gemma)
assert cc['total']==974 and cc['correct']==740 and cc['false_pick']==233 and cc['failed_or_missing']==1
mixed_positive=[x for x in items if x['kind']=='mixed' and x['gold'] is not None]
mixed_negative=[x for x in items if x['kind']=='mixed' and x['gold'] is None]
assert sum(gemma[x['i']]['pick']==x['gold'] for x in mixed_positive)==960
assert sum(gemma[x['i']]['pick'] is not None for x in mixed_negative)==154
assert abs(counts['false_pick_increase_pp']-100*(154-233)/974)<1e-12
test_c={'false_pick':0,'total':2,'failed_or_missing':1}
test_m={'false_pick':0,'total':2,'failed_or_missing':0}
assert false_pick_increase(test_c,test_m)==0,'A format error is not an actual false pick'
def compare(rows):
    a=[valid(gemma[x['i']]) and gemma[x['i']]['pick']==x['gold'] for x in rows]
    b=[valid(frog[x['i']]) and frog[x['i']]['pick']==x['gold'] for x in rows]
    cl=defaultdict(lambda:np.zeros(3))
    for x,aa,bb in zip(rows,a,b):cl[x['itin']]+=np.array([int(aa),int(bb),1])
    u=np.array(list(cl.values()));rng=np.random.default_rng(7)
    boots=u[rng.integers(0,len(u),size=(2000,len(u)))].sum(axis=1)
    diff=(boots[:,0]-boots[:,1])/boots[:,2]
    return {'gemma_correct':sum(a),'frog_correct':sum(b),'total':len(rows),'gemma_minus_frog_pp':100*(sum(a)-sum(b))/len(rows),
        'cluster95_pp':[float(100*np.quantile(diff,.025)),float(100*np.quantile(diff,.975))],'paired_exact':mcnemar_exact(a,b),'clusters':len(cl),'bootstrap_replicates':2000,'bootstrap_seed':7}
result={'verified_complete_answers':4014,'failed_or_unparsed':1,'missing':0,'format_failure_excluded_from_correct_not_denominator':True,
 'false_pick_delta_uses_actual_false_picks':True,'request':compare(mixed_positive),'no_request_correct':compare(mixed_negative),
 'model_repetitions':1,'same_suite':True,'full_cohort_rank':False,'quantization_note':'Gemma is Q4_K_M; Frog artifact quantization not verified here. Artifact hashes/engine versions recorded; this is not a same-precision architecture or speed claim.'}
with (folder/'verification_and_pair_comparison.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
print(json.dumps(result,ensure_ascii=True))
