# Claude 모델(Fable 5.1 · Opus 5.5)이 시험 문제를 직접 짚는다 — 로컬 모델 비교의 기준선. 클로드 CLI(`claude -p`)를 문제마다 한 번씩 부른다.
#  질의문은 올라마 직접 짚기(server/llm_point_heavy.py, 옵션 없음)와 글자 하나까지 같다: 일정 + (앞 대화) + 질문 + 「item 번호 하나, 없으면 null」.
#  차이: 로컬 모델은 JSON 형식 강제(format)와 생각 끄기(think False)를 쓰고, 여기서는 그 형식을 한 문장으로 요구하고 노력 수준을 낮춘다(--effort).
#  빈 폴더에서 실행해 프로젝트 지침 파일을 읽지 않게 하고, 도구·스킬·세션 저장을 끈다. 사용자 전역 지침은 CLI 가 읽을 수 있어 호출당 입력 토큰을 결과에 남긴다.
# 사용: python claude_solve.py <모델 별칭> <세트들,쉼표> [--limit N] [--workers 4] [--effort low]
#   결과: results/claude_<별칭>_<세트>.json  {'ids','picks','raw','usage'...}  (이어서 하기 가능 — 이미 푼 문제는 건너뛴다)
import json, os, re, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[1:]
MODEL, SETS = args[0], args[1].split(',')
opt = lambda k, d: args[args.index(k) + 1] if k in args else d
LIMIT, WORKERS, EFFORT = int(opt('--limit', '0')), int(opt('--workers', '4')), opt('--effort', 'low')
TAG = re.sub(r'[^A-Za-z0-9.]+', '_', MODEL)
W = '월화수목금토일'
SYS = '너는 여행 일정 질문 분류기다. 다른 말 없이 JSON 한 줄만 출력한다.'
CWD = os.path.join(tempfile.gettempdir(), 'claude_solve_empty')
os.makedirs(CWD, exist_ok=True)


def build(job, x):
    items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
    days = sorted({i['date'] for i in items})

    def lab(i):
        d = date.fromisoformat(i['date'])
        return f"{i['id']}. {days.index(i['date']) + 1}일차 {d.month}/{d.day}({W[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"
    plan = '\n'.join(lab(i) for i in items)
    hist = ''
    if x.get('history'):
        hist = '앞 대화:\n' + '\n'.join(f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']) + '\n\n'
    return (f"오늘은 {job['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n{plan}\n\n{hist}"
            f"고객 질문: {x['q']}\n\n이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. "
            "질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. 확실하지 않으면 null."
            ' 출력 형식: {"item": 번호 또는 null} 한 줄만.')


def call(text):
    cmd = ['claude', '-p', '--model', MODEL, '--effort', EFFORT, '--tools', '', '--disable-slash-commands', '--no-session-persistence',
           '--setting-sources', 'project', '--system-prompt', SYS, '--output-format', 'json']
    env = dict(os.environ, MAX_THINKING_TOKENS='0')     # 확장 생각을 끈다(로컬 모델의 think False 에 해당)
    for n in range(4):
        try:
            r = subprocess.run(cmd, input=text, capture_output=True, text=True, encoding='utf-8', timeout=600, cwd=CWD, env=env, shell=(os.name == 'nt'))
            if r.stdout.strip():
                res = json.loads(r.stdout)
                if res.get('is_error') and 'authenticate' in (res.get('result') or ''):
                    sys.exit('클로드 CLI 로그인이 안 돼 있다 — 터미널에서 `claude auth login` 으로 로그인한 뒤 다시 실행한다: ' + res['result'])
                if r.returncode == 0:
                    return res
            err = (r.stderr or r.stdout)[:300]
        except Exception as e:  # noqa: BLE001
            err = str(e)[:300]
        time.sleep(8 * (n + 1))
    return {'is_error': True, 'result': '', 'error': err}


def parse(res, ids):
    m = re.search(r'\{[^{}]*\}', res or '')
    if not m:
        return None, False
    try:
        v = json.loads(m.group(0)).get('item')
    except Exception:  # noqa: BLE001
        return None, False
    return (v if v in ids else None), True


for name in SETS:
    job = json.load(open(os.path.join(HERE, 'fixtures', f'{name}.json'), encoding='utf-8'))['sets'][name]
    qs = job['qs'][:LIMIT] if LIMIT else job['qs']
    ids = {i['id'] for i in job['items']}
    outf = os.path.join(HERE, 'results', f'claude_{TAG}_{name}{"_smoke" if LIMIT else ""}.json')
    done = json.load(open(outf, encoding='utf-8')) if os.path.exists(outf) else {'rows': {}}
    rows = done['rows']
    todo = [k for k in range(len(qs)) if str(k) not in rows or rows[str(k)].get('error')]
    t0 = time.time()

    def one(k):
        res = call(build(job, qs[k]))
        pick, ok = parse(res.get('result'), ids)
        u = res.get('usage') or {}
        return k, {'pick': pick, 'parsed': ok, 'raw': (res.get('result') or '')[:200], 'error': res.get('error'),
                   'cost': res.get('total_cost_usd'), 'ms': res.get('duration_ms'),
                   'in': (u.get('input_tokens') or 0) + (u.get('cache_creation_input_tokens') or 0) + (u.get('cache_read_input_tokens') or 0), 'out': u.get('output_tokens')}

    with ThreadPoolExecutor(WORKERS) as ex:
        for n, (k, row) in enumerate(ex.map(one, todo)):
            rows[str(k)] = row
            if n % 10 == 9 or n == len(todo) - 1:
                json.dump({'model': MODEL, 'effort': EFFORT, 'set': name, 'rows': rows}, open(outf, 'w', encoding='utf-8'), ensure_ascii=False)
                print(name, f'{len(rows)}/{len(qs)}', f'{time.time() - t0:.0f}초', flush=True)
    json.dump({'model': MODEL, 'effort': EFFORT, 'set': name, 'rows': rows}, open(outf, 'w', encoding='utf-8'), ensure_ascii=False)
    ok = sum(1 for r in rows.values() if r['parsed'])
    hit = sum(1 for k in range(len(qs)) if rows[str(k)]['pick'] == qs[k]['gold'])
    cost = sum(r['cost'] or 0 for r in rows.values())
    print(f'{MODEL} {name}: 맞음 {hit}/{len(qs)} · 파싱 {ok} · 비용 합 {cost:.3f}달러(CLI 보고값) · 입력 토큰 평균 {sum(r["in"] for r in rows.values()) / max(1, len(rows)):.0f}', flush=True)
