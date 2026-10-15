from pathlib import Path
import ast, json, types

ROOT=Path(__file__).resolve().parents[2]
state=json.loads((Path(__file__).parent/'collection-integrity-state-v1.json').read_text(encoding='utf8'))
ev=ROOT/state['evidence']
class Response:
    status_code=200
    text='redacted provider error'
    def json(self): return {'response':{'header':{'resultCode':'30'},'body':{'items':'','totalCount':0}}}
request=types.SimpleNamespace(get=lambda *a,**kw:Response())
results=[]
for name in ('tago_subway_collect.py','tago_retry_empty.py'):
    path=ROOT/'datasets/mobility/scripts'/name
    tree=ast.parse(path.read_text(encoding='utf8'))
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='call')
    env={'requests':request,'BASE':'https://example.org','COMMON':{},'time':types.SimpleNamespace(sleep=lambda _:None)}
    exec(compile(ast.Module(body=[function],type_ignores=[]),str(path),'exec'),env)
    value=env['call']('operation') if name=='tago_subway_collect.py' else env['call']()
    results.append({'script':name,'controlled_resultCode':'30','actual_return':value,
                    'false_success': isinstance(value,dict) or value==([], 'ok')})
assert all(r['false_success'] for r in results)
(ev/'before-reproduction-v1.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
print('controlled provider error misclassified:',len(results),'/',len(results))
