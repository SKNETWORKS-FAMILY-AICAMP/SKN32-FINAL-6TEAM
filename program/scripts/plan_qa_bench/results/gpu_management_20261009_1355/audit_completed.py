from pathlib import Path
import json,hashlib,math,importlib.util,sys
sys.stdout.reconfigure(encoding='utf-8')
root=Path.cwd();here=Path(__file__).parent;bench=root/'program/scripts/plan_qa_bench'
spec=importlib.util.spec_from_file_location('valen_contract',bench/'server/queues/prepare_valen_contract_20261009.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
gold=json.loads((bench/'results/empty_probe/all_prompts_d2.json').read_text(encoding='utf-8'))
native=json.loads((root/'datasets/travel/valen_native_eval_20261009/d2.json').read_text(encoding='utf-8'))
answers=[json.loads(x) for x in (bench/'results/gpu_backlog_20261008/valen_08b_original_d2_a2/d_test_valen_08b_original_d2_a2.jsonl').read_text(encoding='utf-8').splitlines()]
ref={x['i']:x for x in native};passed=0;none_chosen=0;samples=[]
assert len(answers)==len(ref)==len(gold)==1000
for g,n in zip(gold,native):assert m.convert(g)==n and n['gold'] is None
for a in answers:
 n=ref[a['i']];q=n['request']['questions']['selection'];p=a['choice_probabilities'];sel=a['native_response']['answers']['selection']
 assert a['parsed'] and not a.get('error') and set(p)==set(q['criteria']) and 'NONE' in p
 assert sel['choice']==max(p,key=p.get) and a['pick']==(None if sel['choice']=='NONE' else int(sel['choice']))
 assert math.isclose(sum(p.values()),1,abs_tol=1e-6) and a['p_null']==p['NONE']
 assert all(a[k]==n[k] for k in ['i','set','qi','type','gold'])
 none_chosen+=a['pick'] is None;passed+=1
 if a['qi'] in [0,299,699,999]:samples.append({'i':a['i'],'question':q['instructions'],'NONE_text':q['criteria']['NONE'],'picked':a['pick'],'p_NONE':p['NONE'],'choice_keys':len(p),'source_prompt_sha256':n['source_prompt_sha256']})
with (here/'Valen_D2_mapping_audit.json').open('x',encoding='utf-8') as f:json.dump({'fixed_conversion_matches':[1000,1000],'answer_mapping_matches':[passed,1000],'NONE_chosen':[none_chosen,1000],'U_FFFD_in_fixed_input':sum(json.dumps(x,ensure_ascii=False).count('\ufffd') for x in native),'samples':samples,'interpretation':'Observed failure of this fixed travel/native-choice path; underlying cause not isolated, no general model capability claim'},f,ensure_ascii=False,indent=2)
gs=json.loads((bench/'fixtures/gold_sets.json').read_text(encoding='utf-8'));B=C=single=cb=cc=total=errors=0;sets=[]
tag='oos2r_finch_5e5_seed20261013_20261008'
for s in ['mix8','mix9','mix10','mix11','mix12']:
 p=here/'B_finch_seed13'/f'eval_{tag}_{s}.json';d=json.loads(p.read_text(encoding='utf-8'))[tag+'#lora']
 assert d['_errors']==0 and len(d['picks'])==len(gs[s]);errors+=d['_errors']
 for i,pick in enumerate(d['picks']):
  want=set(gs[s][str(i)]);actual=set([] if pick is None else pick if isinstance(pick,list) else [pick]);b=bool(want&actual) if want else not actual;c=want==actual
  B+=b;C+=c;total+=1
  if len(want)==2:cb+=b;cc+=c
  else:single+=c
 sets.append({'set':s,'saved':len(d['picks']),'errors':d['_errors'],'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
assert total==835
r=json.loads((here/'B_finch_seed13/recipe_complete.json').read_text());trace=r['rate_trace'];capped=[x['step'] for x in trace if math.isclose(x['lr'],r['finch_cap'],rel_tol=1e-12)]
intervals=[]
for step in capped:
 if intervals and intervals[-1][1]+1==step:intervals[-1][1]=step
 else:intervals.append([step,step])
out={'our_training':True,'seed':20261013,'basic_B':[B,835],'basic_C':[C,835],'single_correct':[single,769],'compound_B':[cb,66],'compound_C':[cc,66],'errors':errors,'missing':0,'sets':sets,'output_contract':'Single item basic HF NF4; compound C is diagnostic and not strict multi-item role','optimizer_steps':[654,654],'lr_cap_steps':[len(capped),654],'lr_cap_intervals':intervals,'lr_min':min(x['lr'] for x in trace),'lr_max':max(x['lr'] for x in trace),'training_seconds':r['training_seconds'],'initial_loss_seconds':r['initial_loss_seconds'],'rank':r['rank'],'epochs':r['epochs'],'accum':r['accum'],'train_sha256':r['train_sha256'],'independent_holdout':False,'final_ranking':False}
with (here/'FINCH_seed13_basic_counts.json').open('x',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
print(json.dumps(out,ensure_ascii=False))
