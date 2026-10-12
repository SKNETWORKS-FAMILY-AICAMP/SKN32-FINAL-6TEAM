# mix6 진단(코드·문턱은 고치지 않는다) — 종단(E4B QAT)이 틀린 문제마다 어느 단계가 결정했는지(규칙·앞단·넘김)와 앞단 1위·점수, 직접 짚기 답을 보인다.
import contextlib, io, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'eval_mix6.py'), encoding='utf-8').read()
head = src[:src.index("qs = SETS['mix6']['qs']")]
ns = {'__name__': 'em', '__file__': os.path.join(HERE, 'eval_mix6.py')}
bak = sys.argv
sys.argv = ['x']
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(head, 'em_head', 'exec'), ns)
sys.argv = bak
SETS, G, S, run, top = ns['SETS'], ns['G'], ns['S'], ns['run'], ns['ns']['top']
from clauses import analyze
from rule_slots import rule_slots
from slot_lookup import resolve
st = SETS['mix6']
qs, items = st['qs'], st['items']
T = {i['id']: i['title'] + '@' + i['place'] for i in items}
M = 'gemma4:e4b-it-qat'
FB = sys.argv[1] if len(sys.argv) > 1 else M
for i, x in enumerate(qs):
    p, used = run('mix6', i, 0.25, 0.6, M)
    if p == x['gold']:
        continue
    a = analyze(x['q'])
    rs = rule_slots(a['tt'], items)
    slots = {k: rs[k] for k in ('day', 'pos', 'kind', 'meal', 'rel', 'kw', 'nextday')}
    slots['anchor'] = None
    r = resolve(items, slots)
    k, sc = top('mix6', 'tt', i)
    stage = '규칙(' + r[0] + ')' if r[0] in ('item', 'none') else ('넘김' if used else ('앞단 수락' if sc >= 0.6 else '앞단 없음(<0.25)'))
    d = G['mix6'][M][i]
    print(f"[{x['type']}] {x['q']} | 정답 {x['gold']}:{T.get(x['gold'], '없음')[:18]} | 종단 {p}:{T.get(p, '없음')[:18]} ← {stage}, 앞단1위 {k}:{T.get(k, '')[:14]}({sc:.2f}) | E4B QAT 직접 {d}{' ✓' if d == x['gold'] else ' ✗'}")
