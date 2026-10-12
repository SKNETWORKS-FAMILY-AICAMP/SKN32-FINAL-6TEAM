import json, sys, re
from datetime import date
from collections import defaultdict
SP = sys.argv[1]
sys.path.insert(0, SP)
from recog_v2 import RecognizerV3, post, NEXT, PREV

cats = json.load(open(SP + '/kakao_cats.json', encoding='utf-8'))
cx = json.load(open(SP + '/codex_qset.json', encoding='utf-8'))
q2 = json.load(open(SP + '/codex_qset2.json', encoding='utf-8'))['questions']
pairs = json.load(open(SP + '/rerank_job/pairs.json', encoding='utf-8'))
scores = json.load(open(SP + '/rerank_job/scores.json', encoding='utf-8'))
src = open(SP + '/eval_v2.py', encoding='utf-8').read()
ns = {}
exec(src[src.index('mine_items = ['):src.index('src = open')], {}, ns)
mine = ns['mine_items']
s1 = open(SP + '/plan_qa_match.py', encoding='utf-8').read()
Qa = eval(s1[s1.index('Q=[') + 2:s1.index('NOW=datetime')].strip())
s2 = open(SP + '/plan_qa_nollm.py', encoding='utf-8').read()
Qb = eval(s2[s2.index('HELD=[') + 5:s2.index('NOW=datetime')].strip())
SETS = {'mine38': (mine, date(2026, 10, 2), [(q, g) for q, g in Qa + Qb]),
        'dev50': (cx['itinerary'], date.fromisoformat(cx['today']), [(x['q'], x['gold']) for n, x in enumerate(cx['questions']) if n % 2 == 0]),
        'test50': (cx['itinerary'], date.fromisoformat(cx['today']), [(x['q'], x['gold']) for n, x in enumerate(cx['questions']) if n % 2 == 1]),
        'hard40': (cx['itinerary'], date.fromisoformat(cx['today']), [(x['q'], x['gold']) for x in q2])}
REC = {'mine38': RecognizerV3(mine, cats, date(2026, 10, 2), SP + '/alias_cache.json')}
REC['dev50'] = REC['test50'] = REC['hard40'] = RecognizerV3(cx['itinerary'], cats, date.fromisoformat(cx['today']), SP + '/alias_cache.json')

# LLM 번호 짚기 결과: hard40·test50 은 앞 실행 저장본, dev50 은 지금 같은 질의문으로 만든다
llm = {'hard40': json.load(open(SP + '/llm_out_새 .json'))['a'], 'test50': json.load(open(SP + '/llm_out_시험.json'))['a']}
items = sorted(cx['itinerary'], key=lambda i: (i['date'], i['start']))
days = sorted({i['date'] for i in items})
W = '월화수목금토일'


def lab(i):
    d = date.fromisoformat(i['date'])
    return f"{days.index(i['date']) + 1}일차 {d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"


S = {'type': 'object', 'properties': {'item': {'type': ['integer', 'null']}}, 'required': ['item']}


def ask(q):
    plan = '\n'.join(f"{i['id']}. {lab(i)}" for i in items)
    b = {'model': 'gemma4:12b', 'stream': False, 'think': False, 'format': S, 'options': {'temperature': 0},
         'messages': [{'role': 'user', 'content':
                       f"오늘은 {cx['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n{plan}\n\n"
                       f"고객 질문: {q}\n\n이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. "
                       "질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. 확실하지 않으면 null."}]}
    v = json.loads(post('/api/chat', b)['message']['content']).get('item')
    return v if v in {i['id'] for i in items} else None


llm['dev50'] = [ask(q) for q, _ in SETS['dev50'][2]]

for model, sc in scores.items():
    table = defaultdict(dict)
    for p, s in zip(pairs, sc):
        table[(p['set'], p['qi'])][p['item']] = s

    def consistent(setname, q, pick):
        if pick is None or re.search(NEXT, q, re.I) or re.search(PREV, q, re.I):
            return True
        pool, sig = REC[setname].filt(q)
        return (not sig) or pick in {i['id'] for i in pool}

    def run(setname, variant, tau):
        _, _, QS = SETS[setname]
        out = []
        for qi, (q, g) in enumerate(QS):
            s = table[(setname, qi)]
            top = max(s, key=s.get)
            if variant == 'RR':
                out.append(top if s[top] >= tau else None)
            elif variant == 'RR+규칙':
                pool, sig = REC[setname].filt(q)
                ids = {i['id'] for i in pool}
                if sig and not ids:
                    out.append(None)
                    continue
                cand = {k: v for k, v in s.items() if k in ids} if sig else s
                t2 = max(cand, key=cand.get)
                out.append(t2 if (cand[t2] >= tau or (sig and len(ids) == 1)) else None)
            elif variant == 'LLM+RR확인+규칙':
                pick = llm[setname][qi]
                ok = pick is not None and s.get(pick, 0) >= tau and consistent(setname, q, pick)
                out.append(pick if ok else None)
        return out

    def stats(setname, out):
        QS = SETS[setname][2]
        ok = sum(o == g for o, (_, g) in zip(out, QS))
        wrong = sum(o is not None and g is not None and o != g for o, (_, g) in zip(out, QS))
        fp = sum(o is not None and g is None for o, (_, g) in zip(out, QS))
        miss = sum(o is None and g is not None for o, (_, g) in zip(out, QS))
        return ok, wrong, fp, miss, len(QS), sum(g is None for _, g in QS)

    grid = [x / 100 for x in range(1, 96)]
    print(f"\n=== {model} ===")
    for variant, devsets in (('RR', ['mine38', 'dev50']), ('RR+규칙', ['mine38', 'dev50']), ('LLM+RR확인+규칙', ['dev50'])):
        # 문턱은 개발용에서만: 맞음 − 2×(틀린 항목 + 없는 질문 오짚음) 이 가장 큰 값
        best = max(grid, key=lambda t: sum((lambda st: st[0] - 2 * (st[1] + st[2]))(stats(d, run(d, variant, t))) for d in devsets))
        line = f"{variant:<16} 문턱 {best:.2f} |"
        tot = [0, 0, 0, 0, 0]
        for d in ('hard40', 'test50'):
            ok, wrong, fp, miss, n, nn = stats(d, run(d, variant, best))
            line += f" {d}: 맞음 {ok}/{n} 틀림 {wrong} 오짚음 {fp}/{nn} 못찾음 {miss} |"
            tot = [a + b for a, b in zip(tot, (ok, wrong, fp, miss, n))]
        line += f" 합계 {tot[0]}/{tot[4]}={tot[0] / tot[4]:.0%} 엉뚱한 답 {tot[1] + tot[2]} 못찾음 {tot[3]}"
        print(line)

for d in ('hard40', 'test50'):
    QS = SETS[d][2]
    out = [llm[d][i] if (lambda p: p is None or True)(llm[d][i]) else None for i in range(len(QS))]
print('\n(비교) LLM 1회 + 규칙 되확인 — 앞 실행 값: hard40 33/40 틀림 3 오짚음 2 · test50 49/50 틀림 0 오짚음 0 · 합계 82/90=91% 엉뚱한 답 5')
