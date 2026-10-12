# JevK5 계열(알리베르섹바이 JevK5 4B·9B, crh225 Plumb-4B 등 JevK5 런타임 모델)을 llama-server(GGUF) + jevk5 런타임의 JevK5GGUF 클라이언트로
# mix 세트에 Jev 와 같은 요청(state + choice criteria)으로 푼다. 모델마다 temperature·knockout_temperature 는 모델 카드 값을 그대로 넘긴다.
# 사용: URL=http://127.0.0.1:8110 TAG=jevk54b TEMP=1.22 KTEMP=0.93 SETS=mix9,mix8 python jevk5_run.py   (LIMIT=3 이면 스모크)
import json, os, sys, time
from datetime import date
from jevk5 import JevK5GGUF

W = '월화수목금토일'
URL, TAG = os.environ['URL'], os.environ['TAG']
TEMP = float(os.environ['TEMP'])
KTEMP = float(os.environ['KTEMP']) if os.environ.get('KTEMP') else None
LIMIT = int(os.environ.get('LIMIT', '0'))
client = JevK5GGUF(url=URL, temperature=TEMP, knockout_temperature=KTEMP, timeout_s=900)


def lab(i):
    dd = date.fromisoformat(i['date'])
    return f"{dd.month}/{dd.day}({W[dd.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"


for name in os.environ['SETS'].split(','):
    job = json.load(open(f'/root/work/{name}.json', encoding='utf-8'))['sets'][name]
    items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
    ids = [i['id'] for i in items]
    keys = [f'item_{i}' for i in ids] + ['none']
    qs = job['qs'][:LIMIT] if LIMIT else job['qs']
    rows, errs, t1 = [], 0, time.time()
    for qi, x in enumerate(qs):
        crit = {f"item_{i['id']}": lab(i) for i in items}
        crit['none'] = '이 일정에는 고객 문장이 가리키는 항목이 없다'
        state = {'today': job['today'], 'customer_message': x['q']}
        if x.get('history'):
            state['previous_conversation'] = [f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']]
        question = {'type': 'choice', 'instructions': '고객 메시지가 가리키는 여행 일정 항목은 어느 것인가? 없으면 none.', 'criteria': crit}
        try:
            r = client.decide(state, question)
            pr = r.get('probabilities') or r.get('probs')
            if pr is None:
                raise RuntimeError('probabilities 키 없음: ' + str(list(r.keys())))
            rows.append({'probs': {k: float(v) for k, v in pr.items()}, 'confidence': r.get('confidence')})
        except Exception as e:  # noqa: BLE001
            errs += 1
            rows.append({'probs': {}, 'confidence': None})
            if errs <= 3:
                import traceback; traceback.print_exc(); print('오류', qi, str(e)[:300], flush=True)
        if qi % 20 == 0:
            print(name, qi, f'{(time.time() - t1) / (qi + 1):.2f}초/문제', flush=True)
    res = {name: {'ids': ids, 'rows': rows, 'keys': keys[:-1]}, '_sec_per_q': (time.time() - t1) / max(1, len(rows)), '_n': len(rows), '_errors': errs, '_tag': TAG}
    json.dump(res, open(f'/root/work/dec_{TAG}_{name}.json' if not LIMIT else f'/root/work/dec_{TAG}_{name}_smoke.json', 'w', encoding='utf-8'), ensure_ascii=False)
    print(f"{TAG} {name} {len(rows)}문제 {res['_sec_per_q']:.2f}초/문제 오류 {errs}", flush=True)
