"""답안의 독립 직접 계수와 분모 보존 예제로 새 MX 집계를 검증한다."""
import json, hashlib
from pathlib import Path
from backlog_mx_report import summarize
root=Path(__file__).resolve().parents[3]
folder=root/'program/scripts/plan_qa_bench/results/gpu_backlog_20261008/frog_mx'
data=json.loads((folder/'mx_counts.json').read_text(encoding='utf-8'))
answer=folder/'d_test_mx_backlog_frog.jsonl'
assert hashlib.sha256(answer.read_bytes()).hexdigest()=='46aefc1479b5ccc378fd1f9178a761955b98976f968992dfab2928e0a26d59df'
rows=[json.loads(l) for l in answer.read_text(encoding='utf-8').splitlines()]
items=json.loads((root/'datasets/travel/mx_testset/mx_main_prompts.json').read_text(encoding='utf-8'))
ref={x['i']:x for x in items}
mixed=[r for r in rows if ref[r['i']]['kind']=='mixed']
positives=[r for r in mixed if r['gold'] is not None]
negatives=[r for r in mixed if r['gold'] is None]
assert len(rows)==len(ref)==4014 and len({r['i'] for r in rows})==4014
assert (len(positives),sum(r['pick']==r['gold'] for r in positives))==(1033,898)
assert (len(negatives),sum(r['pick'] is not None for r in negatives))==(974,167)
gold=[{'i':1,'gold':7},{'i':2,'gold':None}]
missing=summarize(gold,{})
assert missing['total']==2 and missing['correct']==0 and missing['failed_or_missing']==2
bad=summarize(gold,{1:{'parsed':True,'pick':7,'error':'timeout'},2:{'parsed':False,'pick':None}})
assert bad['total']==2 and bad['correct']==0 and bad['failed_or_missing']==2
good=summarize(gold,{1:{'parsed':True,'pick':7},2:{'parsed':True,'pick':None}})
assert good['total']==2 and good['correct']==2 and good['failed_or_missing']==0
assert data['counts']['mixed']['request']['correct']==898 and data['counts']['mixed']['no_request']['false_pick']==167
report={'checks_passed':7,'checks_total':7,'answer_sha256_matches_remote':True,'strict_coverage':4014,'expected':4014,
 'independent_request_count':[898,1033],'independent_false_pick_count':[167,974],
 'missing_error_unparsed_denominator_examples_passed':3,'comparison_scope':'One model, paired request-only versus mixed; no model rank decided'}
with (folder/'verification.json').open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps(report,ensure_ascii=True))
