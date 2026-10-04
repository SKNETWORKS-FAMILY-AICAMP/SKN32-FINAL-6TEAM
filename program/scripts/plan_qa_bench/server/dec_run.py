# 서버에서: Jev 호환 /v1/systemone 엔드포인트(llama.cpp 서버 등 — 로컬이라 무료)에 jev_run.py 와 같은 요청을 보내 항목별 확률을 저장한다.
#  요청: state = {today, customer_message, previous_conversation?} · questions.target = choice(후보 = 일정 항목 한 줄 설명 전부 + 「none」 = 해당 없음) — jev_run.py 와 글자 그대로 같은 criteria·instructions.
#  출력: dec_<TAG>_<세트>.json = {세트: {ids, rows:[{probs, confidence}], keys}, _sec_per_q, _n, _errors, _input_tokens} (jev_out_<세트>.json 과 같은 모양 — 평가 코드가 그대로 읽는다)
# 사용: DEC_URL=http://127.0.0.1:8099/v1/systemone DEC_TAG=winnow12b SETS=mix8,mix9 python3 dec_run.py
import json, os, sys, time, urllib.request, urllib.error
from datetime import date

URL = os.environ['DEC_URL']
TAG = os.environ['DEC_TAG']
W = '월화수목금토일'


def lab(i):
    d = date.fromisoformat(i['date'])
    return f"{d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"


def call(body):
    for attempt in range(3):
        req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        try:
            return json.load(urllib.request.urlopen(req, timeout=600)), None
        except urllib.error.HTTPError as e:
            return None, f'HTTP {e.code}: {e.read().decode()[:160]}'
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                return None, str(e)[:160]
            time.sleep(3)


for name in os.environ['SETS'].split(','):
    job = json.load(open(f'{name}.json', encoding='utf-8'))['sets'][name]
    items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
    if os.environ.get('ROT'):                       # 일정 목록을 k칸 순환 회전(확률 평균용) — 키 이름은 그대로라 채점은 같다
        _k = int(os.environ['ROT']) % len(items)
        items = items[_k:] + items[:_k]
    ids = [i['id'] for i in items]
    rows, t0, errs, tok, first_err = [], time.time(), 0, 0, None
    for x in job['qs']:
        crit = {f"item_{i['id']}": lab(i) for i in items}
        crit['none'] = '이 일정에는 고객 문장이 가리키는 항목이 없다'
        state = {'today': job['today'], 'customer_message': x['q']}
        if x.get('history'):
            state['previous_conversation'] = [f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']]
        body = {'state': state, 'questions': {'target': {'type': 'choice', 'instructions': '고객 메시지가 가리키는 여행 일정 항목은 어느 것인가? 없으면 none.', 'criteria': crit}}}
        r, err = call(body)
        if r is None:
            errs += 1
            first_err = first_err or err
            rows.append({'probs': {}, 'confidence': None})
            continue
        a = (r.get('answers') or r).get('target', r)
        rows.append({'probs': {k: float(v) for k, v in (a.get('probabilities') or {}).items()}, 'confidence': a.get('confidence')})
        tok += (r.get('usage') or {}).get('input_tokens', 0)
    res = {name: {'ids': ids, 'rows': rows, 'keys': [f'item_{i}' for i in ids]}, '_sec_per_q': (time.time() - t0) / len(job['qs']), '_n': len(rows),
           '_errors': errs, '_input_tokens': tok, '_first_error': first_err, '_tag': TAG}
    json.dump(res, open(f'dec_{TAG}_{name}.json', 'w', encoding='utf-8'), ensure_ascii=False)
    print(f"{TAG} {name} {len(rows)}문제 {res['_sec_per_q']:.2f}초/문제 오류 {errs} 입력토큰 {tok}" + (f' 첫 오류: {first_err}' if first_err else ''), flush=True)
