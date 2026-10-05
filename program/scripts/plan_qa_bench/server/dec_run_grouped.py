# 서버에서: 선택지 상한(2~26개)이 있는 /v1/systemone(올라마 Clef 등)에 묶음 대회로 일정 43~47개를 푼다.
#  1회전: 일정 항목을 균형 있게 GROUP 개 이하(기본 24)로 나눠 묶음마다 한 번 묻는다(각 묶음에 「none」 포함) → 묶음마다 확률 최고 항목이 후보.
#  결승: 후보(묶음 수만큼) + 「none」 으로 한 번 더 물어 최종 확률을 얻는다. 후보가 아닌 항목의 확률은 0.
#  출력은 dec_run.py 와 같은 모양(dec_<TAG>_<세트>.json: probs 가 항목 전체 키, 후보 외 0) — 평가 코드가 그대로 읽는다. 호출 수는 문제당 (묶음 수 + 1).
# 사용: DEC_MODEL=clef-flash DEC_URL=http://127.0.0.1:11434/v1/systemone DEC_TAG=clefflashg SETS=mix11 python dec_run_grouped.py   (GROUP=24 · RULE=1 · LIMIT=3 선택)
import json, math, os, sys, time, urllib.request, urllib.error
from datetime import date
INSTR = '고객 메시지가 가리키는 여행 일정 항목은 어느 것인가? 없으면 none.'
if os.environ.get('RULE'):
    INSTR += ' 한 문장에 항목이 여럿 나오면 가장 먼저 언급된 항목 하나만 고른다. 「그거·거기·방금 바꾼 것」 같은 말은 앞 대화에서 가리키는 항목으로 푼다. 앞 대화가 없어 대상을 알 수 없으면 null 이다.'
URL = os.environ['DEC_URL']
TAG = os.environ['DEC_TAG']
GROUP = int(os.environ.get('GROUP', '24'))
LIMIT = int(os.environ.get('LIMIT', '0'))
W = '월화수목금토일'
NONE = '이 일정에는 고객 문장이 가리키는 항목이 없다'


def lab(i):
    d = date.fromisoformat(i['date'])
    return f"{d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"


def call(state, crit):
    body = {'state': state, 'questions': {'target': {'type': 'choice', 'instructions': INSTR, 'criteria': crit}}}
    if os.environ.get('DEC_MODEL'):
        body['model'] = os.environ['DEC_MODEL']
    for attempt in range(3):
        req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        try:
            r = json.load(urllib.request.urlopen(req, timeout=900))
            a = (r.get('answers') or r).get('target', r)
            return {k: float(v) for k, v in (a.get('probabilities') or {}).items()}, (r.get('usage') or {}).get('input_tokens', 0), None
        except urllib.error.HTTPError as e:
            return None, 0, f'HTTP {e.code}: {e.read().decode()[:160]}'
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                return None, 0, str(e)[:160]
            time.sleep(3)


for name in os.environ['SETS'].split(','):
    job = json.load(open(f'{name}.json', encoding='utf-8'))['sets'][name]
    items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
    ids = [i['id'] for i in items]
    n_groups = math.ceil(len(items) / GROUP)
    size = math.ceil(len(items) / n_groups)
    groups = [items[k:k + size] for k in range(0, len(items), size)]
    qs = job['qs'][:LIMIT] if LIMIT else job['qs']
    rows, t0, errs, tok, first_err, calls = [], time.time(), 0, 0, None, 0
    for x in qs:
        state = {'today': job['today'], 'customer_message': x['q']}
        if x.get('history'):
            state['previous_conversation'] = [f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']]
        winners, bad = [], None
        for g in groups:
            crit = {f"item_{i['id']}": lab(i) for i in g}
            crit['none'] = NONE
            p, t, err = call(state, crit)
            calls += 1
            tok += t
            if p is None:
                bad = err
                break
            cand = {k: v for k, v in p.items() if k != 'none'}
            if cand:
                winners.append(max(cand, key=cand.get))
        if bad is None:
            crit = {k: next(lab(i) for i in items if f"item_{i['id']}" == k) for k in winners}
            crit['none'] = NONE
            p, t, err = call(state, crit) if len(crit) >= 2 else ({winners[0]: 1.0} if winners else {'none': 1.0}, 0, None)
            calls += 1
            tok += t
            bad = err if p is None else None
        if bad is not None:
            errs += 1
            first_err = first_err or bad
            rows.append({'probs': {}, 'confidence': None})
            continue
        rows.append({'probs': {k: float(v) for k, v in p.items()}, 'confidence': None})
    res = {name: {'ids': ids, 'rows': rows, 'keys': [f'item_{i}' for i in ids]}, '_sec_per_q': (time.time() - t0) / max(1, len(qs)), '_n': len(rows),
           '_errors': errs, '_input_tokens': tok, '_calls': calls, '_first_error': first_err, '_tag': TAG, '_group': GROUP}
    json.dump(res, open(f'dec_{TAG}_{name}{"_smoke" if LIMIT else ""}.json', 'w', encoding='utf-8'), ensure_ascii=False)
    print(f"{TAG} {name} {len(rows)}문제 {res['_sec_per_q']:.2f}초/문제 호출 {calls} 오류 {errs} 입력토큰 {tok}" + (f' 첫 오류: {first_err}' if first_err else ''), flush=True)
