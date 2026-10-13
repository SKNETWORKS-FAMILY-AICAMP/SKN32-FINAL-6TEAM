"""고정 교대 실험의 형식·의미·지연을 분리한다. 실패와 미완료도 남긴다."""
from pathlib import Path
import argparse,json,statistics
from jsonschema import validate,ValidationError

def summarize(manifest, rows):
    expected=manifest['requests']; by_key={}
    for row in rows:
        key=row['key']
        if key in by_key:raise ValueError('중복 결과를 독립 표본으로 합칠 수 없습니다')
        by_key[key]=row
    if set(by_key)-{c['key'] for c in expected}:raise ValueError('사전 고정 입력에 없는 결과')
    audited=[]
    for case in expected:
        row=by_key.get(case['key'])
        value={'key':case['key'],'variant':case['variant'],'phase':case['phase'],'completed':row is not None,
               'schema_passed':False,'semantic_passed':False}
        if row:
            try:validate(row.get('raw'),case['schema']);value['schema_passed']=True
            except ValidationError as e:value['schema_error']=e.message
            decoded=row.get('decoded',{})
            value['semantic_passed']=bool(value['schema_passed'] and all(decoded.get(k)==v for k,v in case['expected'].items()))
            value.update({k:row.get(k) for k in ('seconds','usage','timings','outside_engine_timing_seconds','error_type')})
        else:value['error_type']='not_completed'
        audited.append(value)
    grouped={}
    for variant in ['baseline','compact']:
        selected=[r for r in audited if r['variant']==variant and r['phase']=='latency_development']
        done=[r for r in selected if r['completed'] and r.get('timings')]
        def metric(f):
            values=[f(r) for r in done]
            return {'n':len(values),'median':statistics.median(values) if values else None,
                    'min':min(values) if values else None,'max':max(values) if values else None}
        grouped[variant]={'completed':sum(r['completed'] for r in selected),'planned':len(selected),
          'semantic_passed':sum(r['semantic_passed'] for r in selected),
          'wall_seconds':metric(lambda r:r['seconds']),
          'prompt_seconds':metric(lambda r:r['timings']['prompt_ms']/1000),
          'generation_seconds':metric(lambda r:r['timings']['predicted_ms']/1000),
          'outside_engine_seconds':metric(lambda r:r['outside_engine_timing_seconds'])}
    return {'planned':len(expected),'completed':sum(r['completed'] for r in audited),
            'schema_passed':sum(r['schema_passed'] for r in audited),'semantic_passed':sum(r['semantic_passed'] for r in audited),
            'rows':audited,'latency_comparison':grouped,'independent_accuracy':False,
            'adoption':False,'outside_engine_is_not_exact_queue_measurement':True,
            'timing_interpretation':'N=2 per variant, shared CPU and automatic serving tests; no p95 or whole-product speed claim'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('manifest',type=Path);parser.add_argument('answers',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();assert not args.output.exists(),'기존 집계는 새 이름으로 보존합니다'
    value=summarize(json.loads(args.manifest.read_text(encoding='utf-8')),
                    [json.loads(l) for l in args.answers.read_text(encoding='utf-8').splitlines() if l.strip()])
    with args.output.open('x',encoding='utf-8') as handle:json.dump(value,handle,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in value.items() if k!='rows'},ensure_ascii=False))
