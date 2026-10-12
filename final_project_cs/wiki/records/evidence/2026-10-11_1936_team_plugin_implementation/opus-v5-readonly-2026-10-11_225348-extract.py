from pathlib import Path
from datetime import datetime
import hashlib,json,sys
base=Path(__file__).parent
prefix=Path(__file__).name.removesuffix('-extract.py')
start=json.loads((base/(prefix+'-start-sha256.json')).read_text(encoding='utf-8'))
candidate=Path(start['candidate'])
end={'at':datetime.now().isoformat(),'candidate':str(candidate),'runtime_sources':{p:hashlib.sha256((candidate/p).read_bytes()).hexdigest() for p in start['runtime_sources']},'audit_inputs':{p:hashlib.sha256((candidate/p).read_bytes()).hexdigest() for p in start['audit_inputs']}}
(base/(prefix+'-end-sha256.json')).write_text(json.dumps(end,indent=2),encoding='utf-8')
diff={group:{p:{'start':h,'end':end[group].get(p)} for p,h in start[group].items() if end[group].get(p)!=h} for group in ('runtime_sources','audit_inputs')}
(base/(prefix+'-sha256-diff.json')).write_text(json.dumps(diff,indent=2),encoding='utf-8')
events=[]
for line in (base/(prefix+'-review.jsonl')).read_text(encoding='utf-8-sig',errors='replace').splitlines():
 try: events.append(json.loads(line))
 except json.JSONDecodeError: pass
calls=[block for e in events if e.get('type')=='assistant' for block in (e.get('message') or {}).get('content',[]) if block.get('type')=='tool_use']
errors={block.get('tool_use_id'):block.get('content') for e in events if e.get('type')=='user' for block in (e.get('message') or {}).get('content',[]) if block.get('type')=='tool_result' and block.get('is_error')}
reads=[{'tool_use_id':c.get('id'),**c.get('input',{}),'is_error':c.get('id') in errors} for c in calls if c.get('name')=='Read']
final=next((e for e in reversed(events) if e.get('type')=='result'),{})
init=next((e for e in events if e.get('type')=='system' and e.get('subtype')=='init'),{})
metadata={'requested_model':'claude-opus-5-5','initial_model':init.get('model'),'available_tools':init.get('tools'),'is_error':final.get('is_error'),'subtype':final.get('subtype'),'modelUsage':final.get('modelUsage'),'canonical_models':{k:v.get('canonicalModel') for k,v in (final.get('modelUsage') or {}).items()},'permission_denials':final.get('permission_denials'),'tool_call_count':len(calls),'tool_names':sorted({c.get('name') for c in calls}),'read_calls':reads,'tool_errors':errors,'tests_executed':False,'runtime_hash_count':len(start['runtime_sources']),'sha256_diff':diff}
(base/(prefix+'-model-metadata.json')).write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
(base/(prefix+'-result.txt')).write_text(final.get('result') or 'NO_FINAL_RESULT',encoding='utf-8')
print(json.dumps({'final_result':bool(final),'model':metadata['canonical_models'],'is_error':metadata['is_error'],'read_calls':len(reads),'distinct_successful_read_paths':len({r.get('file_path') for r in reads if not r['is_error']}),'sha256_diff':diff,'tool_names':metadata['tool_names'],'permission_denials':metadata['permission_denials']},ensure_ascii=False,indent=2))
