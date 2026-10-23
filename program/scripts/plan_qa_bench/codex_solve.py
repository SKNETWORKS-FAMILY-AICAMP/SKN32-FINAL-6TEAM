# Codex CLI 의 GPT-6 Luna · Sol · Astra 가 시험 문제를 직접 짚는다 — 외부 API 쪽 정확도를 재는 용도. 문제마다 `codex exec` 를 한 번씩 부른다.
#  질의문은 claude_solve.py · opencode_solve.py 와 글자 하나까지 같다(일정 + 앞 대화 + 질문 + 「item 번호 하나, 없으면 null」 + 출력 형식). 규칙 문장 없음.
#  ★공정 비교 아님(참고용): Codex CLI 는 에이전트 지시문·도구 정의가 같이 실리고 모델이 생각(reasoning)을 한다 — 생각 수준은 낮게(`model_reasoning_effort=low`) 둔다.
#   원시 API 호출이 아니다. 비용은 구독 쿼터로 나가며(API 요금 아님) 호출당 토큰은 로그에서 읽어 남긴다.
#  ★저자 편향: mix8~11 은 Codex(gpt-6-sol)가 쓴 문제라 Sol·Luna 에 유리할 수 있다. mix12 는 Claude 가 썼다 — Codex 모델에는 mix12 가 가장 깨끗하다.
#  읽기 전용 · 빈 임시 폴더 · 세션 저장 안 함. 쿼터 창이 막히면(usage limit) 바로 멈추고 재시도 시각을 출력한다.
# 사용: python codex_solve.py <모델> <세트들,쉼표> [--limit N] [--workers 3] [--effort low]     모델: gpt-6-luna | gpt-6-sol | gpt-6-astra
#   결과: results/codex_<모델>_<세트>.json  (이어서 하기 가능)
import json, os, re, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
args = sys.argv[1:]
MODEL, SETS = args[0], args[1].split(',')
opt = lambda k, d: args[args.index(k) + 1] if k in args else d
LIMIT, WORKERS, EFFORT = int(opt('--limit', '0')), int(opt('--workers', '3')), opt('--effort', 'low')
MULTI = '--multi' in args   # 둘 다 찾기(C): 번호 하나가 아니라 가리키는 항목 번호를 items 배열로 모두 답하게 한다(claude_solve.py --multi 와 같은 문장)
PREFIX = opt('--out-prefix', 'codex')   # 결과 파일 이름 앞부분. 예전 Codex 묶음 풀이 결과(codex_gpt-6-luna_mix8·mix9 등, 형식이 다름)와 이름이 겹치면 --out-prefix codexcli 로 피한다
W = '월화수목금토일'
WORK = os.path.join(tempfile.gettempdir(), 'codex_solve_work_' + MODEL)
os.makedirs(WORK, exist_ok=True)
SCHEMA = os.path.join(WORK, 'schema.json')
json.dump({'type': 'object', 'properties': {'items': {'type': 'array', 'items': {'type': 'integer'}}}, 'required': ['items'], 'additionalProperties': False} if MULTI else
          {'type': 'object', 'properties': {'item': {'type': ['integer', 'null']}}, 'required': ['item'], 'additionalProperties': False}, open(SCHEMA, 'w'))
quota_hit = []


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
    head = f"오늘은 {job['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n{plan}\n\n{hist}"
    if MULTI:
        return (head + f"고객 질문: {x['q']}\n\n이 질문이 가리키는 일정 항목 번호를 items 배열에 모두 넣어라. 항목이 하나면 하나만, 질문이 여러 항목을 말하면 말한 순서대로 전부 넣는다. "
                "질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 빈 배열. 확실하지 않으면 빈 배열. 출력 형식: " + '{"items": [번호, ...]} 한 줄만. 도구는 쓰지 말고 바로 답한다.')
    return (head + f"고객 질문: {x['q']}\n\n이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. "
            "질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. 확실하지 않으면 null."
            ' 출력 형식: {"item": 번호 또는 null} 한 줄만. 도구는 쓰지 말고 바로 답한다.')


def call(text, tag):
    if quota_hit:
        return {'error': 'quota'}
    pf, of = os.path.join(WORK, f'{tag}.prompt.md'), os.path.join(WORK, f'{tag}.out.json')
    open(pf, 'w', encoding='utf-8').write(text)
    if os.path.exists(of):
        os.remove(of)
    cmd = ['codex', 'exec', '--skip-git-repo-check', '-s', 'read-only', '--ephemeral', '-C', WORK, '-m', MODEL,
           '-c', f'model_reasoning_effort="{EFFORT}"', '--output-schema', SCHEMA, '-o', of, '-']
    err = ''
    for n in range(3):
        try:
            t0 = time.time()
            with open(pf, 'rb') as f:
                r = subprocess.run(cmd, stdin=f, capture_output=True, timeout=600, shell=(os.name == 'nt'))
            log = (r.stdout + b'\n' + r.stderr).decode('utf-8', 'replace')
            if re.search(r'usage limit|hit your .*limit', log, re.I):
                quota_hit.append(re.search(r'try again at[^.\n]*', log, re.I).group(0) if re.search(r'try again at', log, re.I) else '시각 모름')
                return {'error': 'quota: ' + quota_hit[0]}
            if os.path.exists(of) and os.path.getsize(of):
                m = re.search(r'tokens used\s*\n?\s*([\d,]+)', log, re.I)
                return {'result': open(of, encoding='utf-8').read(), 'tokens': int(m.group(1).replace(',', '')) if m else None, 'ms': int((time.time() - t0) * 1000)}
            err = log[-300:]
        except Exception as e:  # noqa: BLE001
            err = str(e)[:300]
        time.sleep(6 * (n + 1))
    return {'error': err}


def parse_multi(res, ids):
    ms = re.findall(r'\{[^{}]*\}', res or '')
    for m in reversed(ms):
        try:
            v = json.loads(m).get('items')
        except Exception:  # noqa: BLE001
            continue
        if isinstance(v, list):
            got = []
            for i in v:
                if isinstance(i, int) and i in ids and i not in got:
                    got.append(i)
            return got, True
    return [], False


def parse(res, ids):
    if MULTI:
        return parse_multi(res, ids)
    ms = re.findall(r'\{[^{}]*\}', res or '')
    for m in reversed(ms):
        try:
            v = json.loads(m).get('item')
        except Exception:  # noqa: BLE001
            continue
        return (v if v in ids else None), True
    return None, False


for name in SETS:
    job = json.load(open(fixture(f'{name}.json'), encoding='utf-8'))['sets'][name]
    qs = job['qs'][:LIMIT] if LIMIT else job['qs']
    ids = {i['id'] for i in job['items']}
    outf = os.path.join(HERE, 'results', f'{PREFIX}_{MODEL}_{name}{"_multi" if MULTI else ""}{"_smoke" if LIMIT else ""}.json')
    done = json.load(open(outf, encoding='utf-8')) if os.path.exists(outf) else {'rows': {}}
    if 'rows' not in done:
        sys.exit(f'{outf} 는 다른 형식의 예전 결과 파일이다 — 덮어쓰지 않고 멈춘다. --out-prefix codexcli 처럼 다른 이름을 쓴다.')
    rows = done['rows']
    todo = [k for k in range(len(qs)) if str(k) not in rows or rows[str(k)].get('error')]
    t0 = time.time()

    def one(k):
        res = call(build(job, qs[k]), f'{name}_{k}')
        pick, ok = parse(res.get('result'), ids)
        return k, {'pick': (pick[0] if pick else None) if MULTI else pick, **({'picks': pick} if MULTI else {}), 'parsed': ok, 'raw': (res.get('result') or '')[:120], 'error': res.get('error'), 'ms': res.get('ms'), 'tokens': res.get('tokens')}

    meta = {'model': MODEL, 'effort': EFFORT, 'set': name, 'fair_comparison': False,
            'caveat': 'Codex CLI(에이전트 지시문·도구 정의 + 생각 수준 낮음), 원시 API 아님. 구독 쿼터. mix8~11 은 Codex(sol) 저자 편향 가능.'
            + (' 둘 다 찾기(C): 정답 집합(gold_sets.json)은 Claude 하위 작업이 만들었고 mix12 문제도 Claude 가 썼다 — Claude 가 푼 C 는 출제자 편향, Codex 가 푼 C 는 mix12 가 출제자와 다른 쪽(mix8~11 은 Codex 출제).' if MULTI else '')}
    with ThreadPoolExecutor(WORKERS) as ex:
        for n, (k, row) in enumerate(ex.map(one, todo)):
            rows[str(k)] = row
            if n % 10 == 9 or n == len(todo) - 1:
                json.dump({**meta, 'rows': rows}, open(outf, 'w', encoding='utf-8'), ensure_ascii=False)
                print(name, f'{len(rows)}/{len(qs)}', f'{time.time() - t0:.0f}초', flush=True)
    json.dump({**meta, 'rows': rows}, open(outf, 'w', encoding='utf-8'), ensure_ascii=False)
    if quota_hit:
        sys.exit(f'쿼터 창이 막혔다 — 멈춘다. 재시도: {quota_hit[0]}')
    ok = sum(1 for r in rows.values() if r['parsed'])
    if MULTI:
        gs = json.load(open(fixture('gold_sets.json'), encoding='utf-8'))[name]
        c_all = sum(1 for k in range(len(qs)) if frozenset(rows[str(k)].get('picks') or []) == frozenset(gs[str(k)]))
        comp = [k for k in range(len(qs)) if qs[k]['type'] == 'compound_intent']
        c_comp = sum(1 for k in comp if frozenset(rows[str(k)].get('picks') or []) == frozenset(gs[str(k)]))
        print(f'{MODEL} {name} 둘 다 찾기: C 정확 {c_all}/{len(qs)} · 요청 둘만 {c_comp}/{len(comp)} · 파싱 {ok} · 오류 {sum(1 for r in rows.values() if r.get("error"))}', flush=True)
    hit = sum(1 for k in range(len(qs)) if rows[str(k)]['pick'] == qs[k]['gold'])
    nc = [k for k in range(len(qs)) if qs[k]['type'] != 'compound_intent']
    hit_nc = sum(1 for k in nc if rows[str(k)]['pick'] == qs[k]['gold'])
    tk = [r['tokens'] for r in rows.values() if r.get('tokens')]
    print(f'{MODEL} {name}: 맞음 {hit}/{len(qs)} · 요청 둘 제외 {hit_nc}/{len(nc)} · 파싱 {ok} · 오류 {sum(1 for r in rows.values() if r.get("error"))} · 호출당 토큰 평균 {sum(tk) / max(1, len(tk)):.0f} · 문제당 {(time.time() - t0) / max(1, len(todo)):.1f}초(작업 {WORKERS}개 병렬)', flush=True)
