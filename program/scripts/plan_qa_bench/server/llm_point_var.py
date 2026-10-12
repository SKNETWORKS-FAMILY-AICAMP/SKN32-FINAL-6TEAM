# 서버에서: 올라마 직접 짚기의 「질의문·디코딩 방식」 변형 — HF 경로(제로샷 E2B 217)와 올라마 경로(E2B 201~202)의 격차 원인을 가른다.
#  SFX=1 : 질의문 끝에 「답은 JSON 한 줄로만: {"item": 번호} 또는 {"item": null}」을 덧붙인다(HF 제로샷과 같은 지시)
#  FMT=0 : 올라마 형식 강제(JSON 스키마)를 끄고 자유 생성(최대 14토큰) + 관대한 파서(HF 와 같은 읽기). 기본은 형식 강제 켬
#  키: <모델>|sfx[|nofmt] → llm_<JOB>_var_out.json
# 사용: SFX=1 FMT=0 JOB=heavy python3 llm_point_var.py 모델...
import json, os, re, sys, time, urllib.request
from datetime import date

JOB = os.environ.get('JOB', 'heavy')
SFX = os.environ.get('SFX') == '1'
FMT = os.environ.get('FMT', '1') != '0'
models = sys.argv[1:]
job = json.load(open(f'{JOB}.json', encoding='utf-8'))['sets'][JOB]
OUTF = f'llm_{JOB}_var_out.json'
W = '월화수목금토일'
S = {'type': 'object', 'properties': {'item': {'type': ['integer', 'null']}}, 'required': ['item']}
items_all = sorted(job['items'], key=lambda i: (i['date'], i['start']))
days = sorted({i['date'] for i in items_all})
ids_all = {i['id'] for i in items_all}
SUFFIX = chr(10) * 2 + '답은 JSON 한 줄로만: {"item": 번호} 또는 {"item": null}'


def lab(i):
    d = date.fromisoformat(i['date'])
    return f"{i['id']}. {days.index(i['date']) + 1}일차 {d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"


def post(b):
    for n in range(3):
        try:
            r = urllib.request.Request('http://127.0.0.1:11434/api/chat', data=json.dumps(b).encode(), headers={'content-type': 'application/json'})
            return json.loads(urllib.request.urlopen(r, timeout=1800).read())
        except Exception as e:  # noqa: BLE001
            if n == 2:
                return {'message': {'content': ''}, 'error': str(e)[:200]}
            time.sleep(5)


def parse(s):
    m = re.search(r'"item"\s*:\s*(null|\d+)', s) or re.search(r'(null|\d+)', s)
    return None if (not m or m.group(1) == 'null') else int(m.group(1))


out = json.load(open(OUTF)) if os.path.exists(OUTF) and os.path.getsize(OUTF) else {}
for model in models:
    picks, errors, t0 = [], 0, time.time()
    for x in job['qs']:
        plan = '\n'.join(lab(i) for i in items_all)
        hist = ''
        if x.get('history'):
            hist = '앞 대화:\n' + '\n'.join(f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']) + '\n\n'
        text = (f"오늘은 {job['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n{plan}\n\n{hist}"
                f"고객 질문: {x['q']}\n\n이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. "
                "질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. 확실하지 않으면 null.") + (SUFFIX if SFX else '')
        b = {'model': model, 'stream': False, 'options': {'temperature': 0} if FMT else {'temperature': 0, 'num_predict': 14}, 'think': False,
             'messages': [{'role': 'user', 'content': text}]}
        if FMT:
            b['format'] = S
        r = post(b)
        errors += 'error' in r
        try:
            v = json.loads(r['message']['content']).get('item') if FMT else parse(r['message']['content'])
        except Exception:  # noqa: BLE001
            v = None
        picks.append(v if v in ids_all else None)
    key = model + ('|sfx' if SFX else '') + ('' if FMT else '|nofmt')
    out[key] = {'picks': picks, '_sec_per_q': (time.time() - t0) / len(job['qs']), '_errors': errors}
    tmp = OUTF + '.tmp'
    json.dump(out, open(tmp, 'w'), ensure_ascii=False)
    os.replace(tmp, OUTF)
    print(key, f"{out[key]['_sec_per_q']:.2f}s/q errors={errors}", flush=True)
