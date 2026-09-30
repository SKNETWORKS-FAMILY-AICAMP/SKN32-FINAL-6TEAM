# Jev(TypeSafe System One) — 「이 질문이 가리키는 일정 항목」을 Choice 로 고르고 선택지별 확률을 저장한다.
#  - 키는 환경변수 ACOP_JEV_API_KEY, 없으면 final_project_cs/.env (git 무시 파일)의 같은 이름 줄에서 읽는다. 키 값은 출력·저장하지 않는다.
#  - 선택지에 항목 설명을 직접 넣는다(위치 인덱스 방식은 Jev 문서·측정에서 오답이 났다). 「해당 없음」 선택지를 넣는다.
#  - 고객 문장은 우리 합성 시험 세트(Codex 작성)만 보낸다. 실제 입력(team_typed_132)은 가리기 전에는 보내지 않는다.
#  - --rules: 날짜·시간대·시각·종류 규칙으로 후보를 먼저 좁힌 뒤 보낸다(Jev 문서가 날짜·시간은 코드에 두라고 권함).
# 사용: python jev_run.py [--job job|heavy] [--probe] [--rules] [--model jev-latest]   → results/jev_out_<job>[_rules].json
import json, os, sys, time, urllib.request, urllib.error
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
URL = 'https://api.typesafe.ai/v1/systemone'
W = '월화수목금토일'
probe, rules = '--probe' in sys.argv, '--rules' in sys.argv
model = sys.argv[sys.argv.index('--model') + 1] if '--model' in sys.argv else 'jev-latest'

def load_key():
    k = os.environ.get('ACOP_JEV_API_KEY', '').strip()
    if k:
        return k
    envp = os.path.join(HERE, '..', '..', '..', 'final_project_cs', '.env')
    if os.path.exists(envp):
        for line in open(envp, encoding='utf-8'):
            line = line.strip()
            if line.startswith('ACOP_JEV_API_KEY') and '=' in line:
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    return ''


key = load_key()
if not key:
    sys.exit('키가 없습니다: 환경변수 ACOP_JEV_API_KEY 또는 final_project_cs/.env 에 넣어 주세요.')
PROTO = os.environ.get('PROTO') == '1'
RULE = '한 문장에 항목이 여럿 나오면 가장 먼저 언급된 항목 하나만 고른다. 「그거·거기·방금 바꾼 것」 같은 말은 앞 대화에서 가리키는 항목으로 푼다. 앞 대화가 없어 대상을 알 수 없으면 null 이다.'
jobname = sys.argv[sys.argv.index('--job') + 1] if '--job' in sys.argv else 'job'

job = json.load(open(os.path.join(HERE, 'fixtures', jobname + '.json'), encoding='utf-8'))['sets']
REC = None
if rules:
    from recog_v2 import RecognizerV3

    class RuleOnly(RecognizerV3):
        def __init__(self, items, today):
            self.items = sorted(items, key=lambda i: (i['date'], i['start']))
            self.today = today
            self.days = sorted({date.fromisoformat(i['date']) for i in self.items})

    REC = {s: RuleOnly(st['items'], date.fromisoformat(st['today'])) for s, st in job.items()}


def call(body):
    for attempt in range(6):
        req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={
            'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
        try:
            return json.load(urllib.request.urlopen(req, timeout=60))
        except urllib.error.HTTPError as e:
            if e.code in (429, 529) and attempt < 5:
                time.sleep(2 ** attempt)
                continue
            sys.exit(f'HTTP {e.code}: {e.read().decode()[:300]}')   # 키는 응답에 없으므로 출력해도 안전
    sys.exit('재시도 초과')


def lab(i):
    d = date.fromisoformat(i['date'])
    return f"{d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"


res, n, t0, first = {}, 0, time.time(), None
for sname, st in job.items():
    items = sorted(st['items'], key=lambda i: (i['date'], i['start']))
    ids = [i['id'] for i in items]
    rows = []
    for x in st['qs']:
        pool = items
        if rules and x.get('pool') is not None:
            pool = [i for i in items if i['id'] in set(x['pool'])]
        elif REC:
            p, sig = REC[sname].filt(x['q'])
            if sig and p:
                pool = sorted(p, key=lambda i: (i['date'], i['start']))
        crit = {f"item_{i['id']}": lab(i) for i in pool}
        crit['none'] = '이 일정에는 고객 문장이 가리키는 항목이 없다'
        state = {'today': st['today'], 'customer_message': x['q']}
        if x.get('history'):
            state['previous_conversation'] = [f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']]
        body = {'model': model, 'state': state,
                'questions': {'target': {'type': 'choice',
                                         'instructions': '고객 메시지가 가리키는 여행 일정 항목은 어느 것인가? 없으면 none.' + (' ' + RULE if PROTO else ''),
                                         'criteria': crit}}}
        r = call(body)
        a = (r.get('answers') or r).get('target', r)
        if first is None:
            first = json.dumps(a, ensure_ascii=False)[:500]
            print('첫 응답 모양:', first, flush=True)
        pr = a.get('probabilities', {})
        rows.append({'probs': {k: float(v) for k, v in pr.items()}, 'confidence': a.get('confidence')})
        n += 1
        if probe and n >= 3:
            break
    res[sname] = {'ids': ids, 'rows': rows, 'keys': [f"item_{i}" for i in ids]}
    if probe:
        break
res['_sec_per_q'] = (time.time() - t0) / max(n, 1)
res['_n'] = n
res['_model'] = model
out = os.path.join(HERE, 'results', f'jev_out_{jobname}' + ('_rules' if rules else '') + ('_proto' if PROTO else '') + ('_probe' if probe else '') + '.json')
json.dump(res, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
print(f"저장 {out} · {res['_sec_per_q']:.2f}초/질문 · n={n}")
