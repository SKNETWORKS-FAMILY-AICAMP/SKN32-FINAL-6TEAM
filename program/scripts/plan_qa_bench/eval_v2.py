import json, sys, time
from datetime import date

SP = sys.argv[1]
SPLIT = sys.argv[2]  # dev | test
sys.path.insert(0, SP)
from recog_v2 import Recognizer, RecognizerV3, emb, post  # noqa: E402

cats = json.load(open(SP + '/kakao_cats.json', encoding='utf-8'))
cx = json.load(open(SP + '/codex_qset.json', encoding='utf-8'))
mine_items = [
    dict(id=1, date='2026-10-03', start='10:00', kind='activity', title='경복궁 관람', place='경복궁'),
    dict(id=2, date='2026-10-03', start='12:30', kind='dining', title='토속촌 삼계탕', place='토속촌삼계탕'),
    dict(id=3, date='2026-10-03', start='15:00', kind='activity', title='한강 카약 체험', place='뚝섬한강공원'),
    dict(id=4, date='2026-10-03', start='19:00', kind='dining', title='명동교자 저녁', place='명동교자 본점'),
    dict(id=5, date='2026-10-04', start='09:30', kind='activity', title='북한산 둘레길', place='북한산 둘레길'),
    dict(id=6, date='2026-10-04', start='13:00', kind='dining', title='광장시장 빈대떡', place='광장시장'),
    dict(id=7, date='2026-10-04', start='15:30', kind='activity', title='국립중앙박물관', place='국립중앙박물관'),
    dict(id=8, date='2026-10-04', start='19:00', kind='activity', title='난타 공연', place='명동난타극장'),
    dict(id=9, date='2026-10-05', start='10:00', kind='activity', title='N서울타워 전망대', place='N서울타워'),
    dict(id=10, date='2026-10-05', start='12:00', kind='dining', title='남대문시장 갈치조림', place='남대문시장'),
    dict(id=11, date='2026-10-05', start='14:00', kind='activity', title='롯데월드 어드벤처', place='롯데월드 어드벤처')]
src = open(SP + '/plan_qa_match.py', encoding='utf-8').read()
Qa = eval(src[src.index('Q=[') + 2:src.index('NOW=datetime')].strip())
src2 = open(SP + '/plan_qa_nollm.py', encoding='utf-8').read()
Qb = eval(src2[src2.index('HELD=[') + 5:src2.index('NOW=datetime')].strip())
sets = []
if SPLIT == 'dev':
    sets.append(('내 질문 38', mine_items, date(2026, 10, 2), [(q, g, '-') for q, g in Qa + Qb]))
    sets.append(('Codex 개발용 50', cx['itinerary'], date.fromisoformat(cx['today']),
                 [(x['q'], x['gold'], x['type']) for n, x in enumerate(cx['questions']) if n % 2 == 0]))
else:
    sets.append(('Codex 시험용 50', cx['itinerary'], date.fromisoformat(cx['today']),
                 [(x['q'], x['gold'], x['type']) for n, x in enumerate(cx['questions']) if n % 2 == 1]))
S = {'type': 'object', 'properties': {'item': {'type': ['integer', 'null']}}, 'required': ['item']}


def llm_choose(q, cands, items):
    lab = {i['id']: f"{i['date']} {i['start']} [{i['kind']}] {i['title']} @ {i['place']}" for i in items}
    menu = '\n'.join(f"{c}. {lab[c]}" for c in cands)
    b = {'model': 'gemma4:12b', 'stream': False, 'think': False, 'format': S, 'options': {'temperature': 0},
         'messages': [{'role': 'user', 'content':
                       f"고객 질문: {q}\n\n후보 일정:\n{menu}\n\n질문이 가리키는 후보 번호 하나를 item 에 넣어라. 후보 중 맞는 것이 없으면 null."}]}
    v = json.loads(post('/api/chat', b)['message']['content']).get('item')
    return v if v in cands else None


def summarize(rows):
    n = len(rows)
    rel = [r for r in rows if r[1] is not None]
    non = [r for r in rows if r[1] is None]
    ok = sum(r[2] == r[1] for r in rows)
    okr = sum(r[2] == r[1] for r in rel)
    wrong = sum(r[2] is not None and r[2] != r[1] for r in rel)
    fp = sum(r[2] is not None for r in non)
    miss = sum(r[2] is None for r in rel)
    return (f"맞음 {ok}/{n}={ok / n:.0%} · 항목질문 {okr}/{len(rel)} · 틀린 항목 짚음 {wrong} · "
            f"없는 질문 오짚음 {fp}/{len(non)} · 못 찾음 {miss}")


for name, items, today, QS in sets:
    QV = emb([q for q, _, _ in QS])
    for label, R in (('v2', Recognizer(items, cats, today)), ('v3', RecognizerV3(items, cats, today, SP + '/alias_cache.json'))):
        for tau in (0.45, 0.50, 0.55):
            rows = [(q, g, R.pick(q, qv, tau), t) for (q, g, t), qv in zip(QS, QV)]
            print(f"[{name}] {label} τ={tau} " + summarize(rows))
        if SPLIT == 'dev' and label == 'v3':
            for q, g, p, t in [(q, g, R.pick(q, qv, 0.50), t) for (q, g, t), qv in zip(QS, QV)]:
                if p != g:
                    print(f"    X {t:<18} 정답 {g} · v3 {p} · {q}")
    t0 = time.time()
    rowsL = []
    for (q, g, t), qv in zip(QS, QV):
        ranked, sig, pool = R.rank(q, qv)
        cands = [c for _, c in ranked[:3]]
        ch = llm_choose(q, cands, items) if cands else None
        rowsL.append((q, g, ch if (sig or (ranked and ranked[0][0] >= 0.40)) else None, t))
    print(f"[{name}] v3+LLM(후보3 안에서만) " + summarize(rowsL) + f" · {(time.time() - t0) / len(QS):.1f}s/질문")
