# 서버에서: 싼 앞단(학습 임베딩)의 상위 후보를 넘김 모델에게 「힌트」로 주는 방식 — 작은 모델의 짚기를 돕는 결합(올라마, 형식 강제).
#  MODE=hint     : 일정 전체는 그대로 주고 「검색이 고른 상위 5개」를 덧붙인다(틀릴 수 있다고 알림)
#  MODE=restrict : 일정에 상위 5개 항목만 싣는다(입력 토큰 약 1/8) — 재현율 상한이 있다(Codex 가 지적한 C안)
#  힌트 파일 hints_<JOB>.json = {"top": [[id…5개], …문제 순서]} (로컬에서 학습 임베딩 점수로 만든다)
#  사용: MODE=hint JOB=mix5 python3 llm_point_hint.py 모델...   → llm_<JOB>_<MODE>_out.json
import json, os, sys, time, urllib.request
from datetime import date

JOB = os.environ.get('JOB', 'heavy')
MODE = os.environ.get('MODE', 'hint')
models = sys.argv[1:]
job = json.load(open(f'{JOB}.json', encoding='utf-8'))['sets'][JOB]
hints = json.load(open(f'hints_{JOB}.json', encoding='utf-8'))['top']
W = '월화수목금토일'
S = {'type': 'object', 'properties': {'item': {'type': ['integer', 'null']}}, 'required': ['item']}
items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
days = sorted({i['date'] for i in items})
ids = {i['id'] for i in items}


def lab(i):
    d = date.fromisoformat(i['date'])
    return f"{i['id']}. {days.index(i['date']) + 1}일차 {d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"


OUTF = f'llm_{JOB}_{MODE}_out.json'
out = json.load(open(OUTF)) if os.path.exists(OUTF) else {}


def post(b):
    for n in range(3):
        try:
            r = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=json.dumps(b).encode(), headers={'content-type': 'application/json'})
            return json.loads(urllib.request.urlopen(r, timeout=600).read())
        except Exception as e:  # noqa: BLE001
            if n == 2:
                return {'message': {'content': '{}'}, 'error': str(e)[:200]}
            time.sleep(3)


for model in models:
    picks, errs, t0 = [], 0, time.time()
    for qi, x in enumerate(job['qs']):
        top = [t for t in hints[qi] if t in ids]
        if MODE == 'restrict':
            plan = '\n'.join(lab(i) for i in items if i['id'] in top)
            note = ''
            head = '고객의 여행 일정 중 질문과 가장 비슷한 후보(번호. 일차 날짜 시각 [종류] 제목 @ 장소):'
        else:
            plan = '\n'.join(lab(i) for i in items)
            note = f"\n\n검색 전문가가 이 질문과 가장 비슷하다고 본 항목(유사도 순): {', '.join(map(str, top))}\n(검색은 틀릴 수 있다. 일정과 질문을 직접 대조해 판단하라.)"
            head = '고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):'
        hist = ''
        if x.get('history'):
            hist = '앞 대화:\n' + '\n'.join(f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']) + '\n\n'
        text = (f"오늘은 {job['today']} 이다. {head}\n{plan}{note}\n\n{hist}고객 질문: {x['q']}\n\n이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. "
                "질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. 확실하지 않으면 null.")
        r = post({'model': model, 'stream': False, 'format': S, 'think': False, 'options': {'temperature': 0}, 'messages': [{'role': 'user', 'content': text}]})
        errs += 'error' in r
        try:
            v = json.loads(r['message']['content']).get('item')
        except Exception:  # noqa: BLE001
            v = None
        picks.append(v if v in ids else None)
    out[model] = {'picks': picks, '_errors': errs, '_sec_per_q': (time.time() - t0) / len(job['qs'])}
    json.dump(out, open(OUTF + '.tmp', 'w'), ensure_ascii=False)
    os.replace(OUTF + '.tmp', OUTF)
    print(MODE, JOB, model, f"{out[model]['_sec_per_q']:.2f}s/q errors={errs}", flush=True)
