from pathlib import Path
import json,importlib.util,collections,time,argparse,hashlib
R=Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser(description='기존 합성 답안을 재생합니다. 새 추론을 하지 않으며 기존 출력을 덮지 않습니다.')
parser.add_argument('--input',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();O=args.output
O.mkdir(parents=True,exist_ok=False)
spec=importlib.util.spec_from_file_location('adapter',R/'final_project_cs/deploy/arm/ollama_adapter.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
data=json.loads(args.input.read_text(encoding='utf8'))
out=[];start=time.perf_counter()
for job in data:
 for name,text in job['files'].items():
  if not name.endswith('.jsonl'):continue
  for line in text.splitlines():
   r=json.loads(line);raw=r['raw_response'];c=raw['choices'][0]['message'].get('content');old=isinstance(c,str)
   try:
    v=a.chat_response(raw,{'format':'json'});new=True;reason=None;assert v['message']['content']==c
   except a.ModelOutputError as e:new=False;reason=e.code
   out.append({'job':job['id'],'i':r['i'],'old_success':old,'new_success':new,'reason':reason,'diagnostic_correct':r['correct'],'finish_reason':r.get('finish_reason')})
summary={'scope':'recorded synthetic development replay; zero new inference calls','total':len(out),'old_success':sum(r['old_success'] for r in out),'new_success':sum(r['new_success'] for r in out),'rejected':dict(collections.Counter(r['reason'] for r in out if r['reason'])),'per_job':{j['id']:{'total':sum(r['job']==j['id'] for r in out),'accepted':sum(r['job']==j['id'] and r['new_success'] for r in out)} for j in data},'seconds':time.perf_counter()-start,'input_sha256':hashlib.sha256(args.input.read_bytes()).hexdigest(),'adapter_sha256':hashlib.sha256((R/'final_project_cs/deploy/arm/ollama_adapter.py').read_bytes()).hexdigest()}
(O/'response_guard_replay_rows.json').write_text(json.dumps(out,indent=2),encoding='utf-8');(O/'response_guard_replay_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
