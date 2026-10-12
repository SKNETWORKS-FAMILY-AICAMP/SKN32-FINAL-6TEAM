# mix7 진단(코드·문턱은 고치지 않는다) — 종단(E4B QAT, lo 0.10)이 틀린 문제마다 어느 단계가 결정했는지와 앞단 1위·점수, 직접 짚기 답을 보인다.
import contextlib, io, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'eval_mix7.py'), encoding='utf-8').read()
head = src[:src.index("N = len(SETS['mix7']['qs'])")]
ns = {'__name__': 'em', '__file__': os.path.join(HERE, 'eval_mix7.py')}
bak = sys.argv
sys.argv = ['x']
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(head, 'em_head', 'exec'), ns)
sys.argv = bak
SETS, G, run, top = ns['SETS'], ns['G'], ns['run'], ns['ns']['top']
from clauses import analyze
from rule_slots import rule_slots
from slot_lookup import resolve
st = SETS['mix7']
qs, items = st['qs'], st['items']
T = {i['id']: i['title'] + '@' + i['place'] for i in items}
M, LO = 'gemma4:e4b-it-qat', 0.10
for i, x in enumerate(qs):
    p, used = run('mix7', i, LO, 0.6, M)
    if p == x['gold']:
        continue
    a = analyze(x['q'])
    rs = rule_slots(a['tt'], items)
    slots = {k: rs[k] for k in ('day', 'pos', 'kind', 'meal', 'rel', 'kw', 'nextday')}
    slots['anchor'] = None
    r = resolve(items, slots)
    k, sc = top('mix7', 'tt', i)
    stage = '규칙(' + r[0] + ')' if r[0] in ('item', 'none') else ('넘김' if used else ('앞단 수락' if sc >= 0.6 else '앞단 없음'))
    d = G['mix7'][M][i]
    b = G['mix7']['gemma4:26b-a4b-it-q4_K_M'][i]
    print(f"[{x['type']}] {x['q']} | 정답 {x['gold']}:{T.get(x['gold'], '없음')[:16]} | 종단 {p}:{T.get(p, '없음')[:16]} ← {stage}, 앞단1위 {k}({sc:.2f}) | E4B직접 {'✓' if d == x['gold'] else '✗'} 26B직접 {'✓' if b == x['gold'] else '✗'}")
