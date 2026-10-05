# OpenCode(`opencode run`)의 무료 모델(Muse Spark 1.3 Contributor Free)이 시험 문제를 직접 짚는다 — 문제마다 한 번씩 부른다.
#  질의문은 claude_solve.py 와 글자 하나까지 같다(일정 + 앞 대화 + 질문 + 「item 번호 하나, 없으면 null」 + 출력 형식 한 문장). 규칙 문장 없음.
#  ★공정 비교 아님: 무료 구간은 「설정을 하나도 안 바꾼 OpenCode 안에서만」 열려 있어(설정 파일·권한 환경변수를 주면 403 FreeTierError), OpenCode 의 코딩 에이전트
#   지시문·도구 정의(호출당 입력 약 1.9만 토큰)가 같이 실리고 모델이 생각(reasoning)을 한다. 우회하지 않는다. 결과는 「참고용」으로만 표에 넣는다.
#  ★데이터: 이 모델의 무료 조건은 「프롬프트와 응답을 Meta 의 다음 모델 학습에 쓰도록 허락」이다. 보내는 것은 합성 일정·질문(mix8~12)뿐이다 — 고객 데이터·골든/홀드아웃은 보내지 않는다.
#  빈 임시 폴더에서 실행한다(프로젝트 지침 파일을 읽지 않게).
# 사용: python opencode_solve.py <세트들,쉼표> [--limit N] [--workers 3] [--model opencode/muse-spark-1.3-contributor-free]
#   결과: results/opencode_<별칭>_<세트>.json  (이어서 하기 가능)
import json, os, re, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[1:]
SETS = args[0].split(',')
opt = lambda k, d: args[args.index(k) + 1] if k in args else d
LIMIT, WORKERS, MODEL = int(opt('--limit', '0')), int(opt('--workers', '3')), opt('--model', 'opencode/muse-spark-1.3-contributor-free')
TAG = re.sub(r'[^A-Za-z0-9.]+', '_', MODEL.split('/')[-1])
W = '월화수목금토일'
CWD = os.path.join(tempfile.gettempdir(), 'opencode_solve_empty')
os.makedirs(CWD, exist_ok=True)
free_tier_errors = 0


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
            ' 출력 형식: {"item": 번호 또는 null} 한 줄만. 도구는 쓰지 말고 바로 답한다.')


def call(text):
    global free_tier_errors
    cmd = ['opencode', 'run', '-m', MODEL, '--format', 'json']
    env = {k: v for k, v in os.environ.items() if k not in ('OPENCODE_CONFIG', 'OPENCODE_PERMISSION')}   # 설정을 바꾸면 무료 구간이 막힌다
    err = ''
    for n in range(4):
        try:
            t0 = time.time()
            r = subprocess.run(cmd, input=text, capture_output=True, text=True, encoding='utf-8', timeout=300, cwd=CWD, env=env, shell=(os.name == 'nt'))
            txt, tok, errs = '', {}, []
            for line in r.stdout.splitlines():
                try:
                    ev = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                if ev.get('type') == 'text':
                    txt += ev['part'].get('text', '')
                elif ev.get('type') == 'step_finish':
                    tok = ev['part'].get('tokens', {})
                elif ev.get('type') == 'error':
                    errs.append(json.dumps(ev.get('error'), ensure_ascii=False)[:300])
            if txt.strip():
                free_tier_errors = 0
                return {'result': txt, 'tokens': tok, 'ms': int((time.time() - t0) * 1000)}
            err = (errs[0] if errs else (r.stderr or r.stdout)[:300])
            if 'FreeTierError' in err:
                free_tier_errors += 1
                if free_tier_errors >= 5:
                    sys.exit('무료 구간 거절(FreeTierError)이 연속 5번 — 멈춘다. 설정을 건드리지 않았는지·무료 기간이 끝났는지 확인: ' + err)
        except Exception as e:  # noqa: BLE001
            err = str(e)[:300]
        time.sleep(6 * (n + 1))
    return {'result': '', 'error': err}


def parse(res, ids):
    ms = re.findall(r'\{[^{}]*\}', res or '')
    for m in reversed(ms):
        try:
            v = json.loads(m).get('item')
        except Exception:  # noqa: BLE001
            continue
        return (v if v in ids else None), True
    return None, False


for name in SETS:
    job = json.load(open(os.path.join(HERE, 'fixtures', f'{name}.json'), encoding='utf-8'))['sets'][name]
    qs = job['qs'][:LIMIT] if LIMIT else job['qs']
    ids = {i['id'] for i in job['items']}
    outf = os.path.join(HERE, 'results', f'opencode_{TAG}_{name}{"_smoke" if LIMIT else ""}.json')
    done = json.load(open(outf, encoding='utf-8')) if os.path.exists(outf) else {'rows': {}}
    rows = done['rows']
    todo = [k for k in range(len(qs)) if str(k) not in rows or rows[str(k)].get('error')]
    t0 = time.time()

    def one(k):
        res = call(build(job, qs[k]))
        pick, ok = parse(res.get('result'), ids)
        tk = res.get('tokens') or {}
        return k, {'pick': pick, 'parsed': ok, 'raw': (res.get('result') or '')[:200], 'error': res.get('error'), 'ms': res.get('ms'),
                   'in': tk.get('input'), 'out': tk.get('output'), 'reasoning': tk.get('reasoning')}

    with ThreadPoolExecutor(WORKERS) as ex:
        for n, (k, row) in enumerate(ex.map(one, todo)):
            rows[str(k)] = row
            if n % 10 == 9 or n == len(todo) - 1:
                json.dump({'model': MODEL, 'set': name, 'fair_comparison': False, 'caveat': 'OpenCode 코딩 에이전트 지시문·도구 정의가 같이 실리고 모델이 생각을 한다(무료 구간은 설정을 안 바꾼 OpenCode 안에서만 열림). 참고용.', 'rows': rows},
                          open(outf, 'w', encoding='utf-8'), ensure_ascii=False)
                print(name, f'{len(rows)}/{len(qs)}', f'{time.time() - t0:.0f}초', flush=True)
    json.dump({'model': MODEL, 'set': name, 'fair_comparison': False, 'caveat': 'OpenCode 코딩 에이전트 지시문·도구 정의가 같이 실리고 모델이 생각을 한다(무료 구간은 설정을 안 바꾼 OpenCode 안에서만 열림). 참고용.', 'rows': rows},
              open(outf, 'w', encoding='utf-8'), ensure_ascii=False)
    ok = sum(1 for r in rows.values() if r['parsed'])
    hit = sum(1 for k in range(len(qs)) if rows[str(k)]['pick'] == qs[k]['gold'])
    ins = [r['in'] for r in rows.values() if r.get('in')]
    print(f'{MODEL} {name}: 맞음 {hit}/{len(qs)} · 파싱 {ok} · 오류 {sum(1 for r in rows.values() if r.get("error"))} · 입력 토큰 평균 {sum(ins) / max(1, len(ins)):.0f} · 문제당 {(time.time() - t0) / max(1, len(todo)):.1f}초(작업 {WORKERS}개 병렬)', flush=True)
