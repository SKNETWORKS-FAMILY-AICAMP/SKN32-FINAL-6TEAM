# 서버에서: 「한 줄로 이은 시험」 — 질문 하나를 ① 규칙 → ② ML 판별기 → ③ Jev 분류 → ④ 전문가(소형 LLM) 순서로 실제 호출해 끝까지 처리한다.
#  단계마다 앞 단계가 끝내면 뒤 단계는 부르지 않는다. 문제마다 어느 단계에서 끝났는지 · 호출 수 · 단계별 시간 · 실패 사유를 남긴다.
#  ① 규칙(코드): clauses.analyze → rule_slots → slot_lookup.resolve. 「앞뒤」 표현의 기준 항목은 학습 임베딩 점수(chain_emb.py) 1위가 0.4 이상일 때만 쓴다.
#     규칙이 못 정했는데 앞 대화가 있으면 곧바로 전문가로 보낸다(eval_router.stage 와 같다).
#  ② ML 판별기: 학습한 분류 인코더(multilingual-e5-base, 머리 4개: 의도·감정·긴급도·대상 — train_cls.py --save). 의도가 「그 밖」일 확률이 REJECT_P 이상이면 범위 밖으로 닫는다.
#  ③ Jev 계열 분류 모델: Winnow-E4B(Jev 계열 모델 중 하나, 유효 4B, 학습 없는 원본 — 가르친 판이 아님) 한 번의 호출로 질문 5개(어느 전문가로 보낼지 + 의도·감정·긴급도·대상). 「보낼 곳」 확률이 큰 쪽으로 간다.
#  ④ 전문가: 「일정 항목 짚기」 → 가르친 E4B(Q8 GGUF, 서비스 입력 그대로) · 「범위 밖」 → 없음.
#  사전 등록(결과를 보기 전에 고정): REJECT_P=0.9 · Jev 는 확률이 큰 쪽(문턱 없음) · 아무것도 시험 세트로 고르지 않는다. ★사후 수정: 스모크(시험 세트 44문제)에서 Jev 입력에 일정이 없어 일정 질문 26개 중 21개가 「범위 밖」으로 닫혀(full_v1) Jev 입력에 일정 목록을 넣은 판(full)을 만들었다 — 두 판 모두 보고한다. 변형: full(주) · e4b_only · no_rules · no_jev · no_ml · rules_e4b · full_noctx(Jev 입력에 「일정을 가진 고객」 줄이 없는 민감도 판).
#  같은 입력이면 같은 출력(온도 0)이라 단계 호출 결과는 변형 사이에 재사용하되, full#live · e4b_only#live 는 캐시 없이 다시 호출해 실제 지연과 재현(같은 답인지)을 본다.
# 사용: python chain_e2e.py [변형,쉼표]  (기본: 전부)   환경: E4B_URL · JEV_URL · SETS
import collections
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date

ROOT = '/root/chain'
sys.path.insert(0, ROOT)
from clauses import analyze  # noqa: E402
from rule_slots import rule_slots  # noqa: E402
from slot_lookup import resolve  # noqa: E402

W = os.environ.get('SETS', 'mix8,mix9,mix10,mix11,mix12').split(',')
E4B_URL = os.environ.get('E4B_URL', 'http://127.0.0.1:8201/v1/chat/completions')
JEV_URL = os.environ.get('JEV_URL', 'http://127.0.0.1:8092/v1/systemone')
LIMIT = int(os.environ.get('LIMIT', '0'))
STRIDE = int(os.environ.get('STRIDE', '1'))     # 스모크 시험용: N 번째 문제마다 하나(기본 1 = 전부)
REJECT_P = 0.9
TAU_ANCHOR = 0.4
OUT = f'{ROOT}/out'
os.makedirs(OUT, exist_ok=True)
J = lambda f: json.load(open(f, encoding='utf-8'))
JOB = {w: J(f'{ROOT}/fixtures/{w}.json')['sets'][w] for w in W}
GOLDSETS = J(f'{ROOT}/fixtures/gold_sets.json')
EMB = J(f"{OUT}/{os.environ.get('EMB_FILE', 'emb_scores.json')}")['scores']
WK = '월화수목금토일'
SFX = '\n\n답은 JSON 한 줄로만: {"item": 번호} 또는 {"item": null}'

# ---------------- ② 분류 인코더 ----------------
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
from transformers import AutoModel, AutoTokenizer  # noqa: E402

torch.set_num_threads(int(os.environ.get('CLS_THREADS', '16')))
META = J(f'{ROOT}/cls_e5base/meta.json')
HEADS = META['heads']
CLS_TOK = AutoTokenizer.from_pretrained(META['name'])


class Cls(nn.Module):
    def __init__(self):
        super().__init__()
        self.enc = AutoModel.from_pretrained(META['name'], dtype=torch.float32)
        h = self.enc.config.hidden_size
        self.drop = nn.Dropout(0.1)
        self.heads = nn.ModuleList([nn.Linear(h, len(v)) for v in HEADS.values()])

    def forward(self, **kw):
        kw.pop('token_type_ids', None)
        out = self.enc(**kw).last_hidden_state
        m = kw['attention_mask'].unsqueeze(-1).to(out.dtype)
        pooled = (out * m).sum(1) / m.sum(1).clamp(min=1)
        return [h(self.drop(pooled)) for h in self.heads]


CLS = Cls()
CLS.load_state_dict(torch.load(f'{ROOT}/cls_e5base/model.pt'))
CLS.eval()


def cls_stage(q):
    t0 = time.perf_counter()
    x = CLS_TOK([q], return_tensors='pt', truncation=True, max_length=META['maxlen'])
    with torch.no_grad():
        lg = CLS(**x)
    probs = {h: dict(zip(HEADS[h], torch.softmax(l[0], -1).tolist())) for h, l in zip(HEADS, lg)}
    return probs, (time.perf_counter() - t0) * 1000


# ---------------- ③ Jev 분류(Winnow-E4B) ----------------
ROUTE_Q = {'type': 'choice', 'instructions': '이 고객 메시지는 어디로 보내야 하는가?',
           'criteria': {'point': '고객의 여행 일정에 있는 항목(식당·이동·활동·숙소 등)을 가리키거나 그 일정의 확인·변경·취소를 요청하는 말',
                        'reject': '여행 일정과 무관한 잡담·인사·일반 정보·날씨·가격 문의·서비스 범위 밖 요청'}}
CLS_Q = {
    'intent': ('고객 메시지의 요청 종류는 무엇인가?', {'itinerary_submit': '여행 일정을 보내거나 등록·검증해 달라는 말', 'incident_report': '이미 일어난 문제(늦음·휴무·매진·날씨·길 막힘·분실·사고)를 알리는 말',
                                              'confirm_request': '영업시간·이동 시간·예약 상태 등을 묻거나 확인해 달라는 말', 'adjust_reject': '일정을 바꿔 달라·취소해 달라·원래대로 되돌려 달라, 또는 제안을 거절하는 말',
                                              'other': '인사·잡담·감사·의미 없는 말·서비스 범위 밖 요청'}),
    'sentiment': ('고객의 감정은 무엇인가?', {'positive': '만족·기쁨·감사', 'neutral': '감정 표현 없이 사실을 말하거나 요청', 'negative': '불만·불안·짜증·걱정·당황'}),
    'severity': ('이 메시지는 얼마나 급한가?', {'low': '급하지 않다. 일반 문의·여유 있는 변경·잡담', 'medium': '곧 처리해야 하지만 당장 일정이 깨지지는 않는다', 'high': '지금~1~2시간 안의 일정에 지장이 생기고 있거나 곧 생긴다', 'critical': '안전·건강·귀국편 놓침·여권 분실·사고처럼 즉시 조치가 필요하다'}),
    'case_type': ('고객 메시지가 말하는 대상은 무엇인가?', {'activity': '관광·체험·공연·쇼핑 등 여행지에서 하는 활동', 'dining': '식당·카페', 'mobility': '지하철·버스·택시·도보·공항 이동', 'booking': '예약·결제·취소·변경 같은 예약 기록',
                                              'lodging': '숙소', 'flight': '항공편', 'other': '대상이 없거나 전체 일정·잡담'}),
}


def post(url, body, timeout=600):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


CTX = '고객은 서비스에 여행 일정을 등록해 둔 상태이고, 서비스는 그 일정 목록을 알고 있다.'


def itin_lines(job):
    items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
    days = sorted({i['date'] for i in items})
    out = []
    for i in items:
        d = date.fromisoformat(i['date'])
        out.append(f"{i['id']}. {days.index(i['date']) + 1}일차 {d.month}/{d.day}({WK[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}")
    return out


def jev_stage(x, job, mode='itin'):
    """Jev 입력 판: itin = 메시지 + 고객의 일정 목록(수정 판 — 보낼 곳을 정하려면 일정을 알아야 한다) · ctx = 메시지 + 「일정을 등록해 둔 고객」 한 줄(사전 등록 판) · none = 메시지만."""
    state = {'customer_message': x['q']}
    if mode == 'ctx':
        state['context'] = CTX
    elif mode == 'itin':
        state['context'] = CTX
        state['customer_itinerary'] = itin_lines(job)
    if x.get('history'):
        state['previous_conversation'] = [f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']]
    qs = {'route': ROUTE_Q, **{k: {'type': 'choice', 'instructions': v[0], 'criteria': v[1]} for k, v in CLS_Q.items()}}
    t0 = time.perf_counter()
    try:
        r = post(JEV_URL, {'state': state, 'questions': qs})
        a = r.get('answers') or r
        pr = {k: (a[k].get('probabilities') or {}) for k in qs}
        return pr, (time.perf_counter() - t0) * 1000, None
    except Exception as e:  # noqa: BLE001
        return None, (time.perf_counter() - t0) * 1000, repr(e)[:160]


# ---------------- ④ 전문가: 가르친 E4B ----------------
def build(job, x):
    items = sorted(job['items'], key=lambda i: (i['date'], i['start']))
    days = sorted({i['date'] for i in items})

    def lab(i):
        d = date.fromisoformat(i['date'])
        return f"{i['id']}. {days.index(i['date']) + 1}일차 {d.month}/{d.day}({WK[d.weekday()]}) {i['start']} [{i['kind']}] {i['title']} @ {i['place']}"
    hist = ''
    if x.get('history'):
        hist = '앞 대화:\n' + '\n'.join(f"{'고객' if h['role'] == 'customer' else '서비스'}: {h['text']}" for h in x['history']) + '\n\n'
    return (f"오늘은 {job['today']} 이다. 고객의 여행 일정(번호. 일차 날짜 시각 [종류] 제목 @ 장소):\n" + '\n'.join(lab(i) for i in items) + f"\n\n{hist}"
            f"고객 질문: {x['q']}\n\n이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라. "
            "질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 null. 확실하지 않으면 null." + SFX), {i['id'] for i in items}


CONFS = {}
TAGP = os.environ.get('OUT_TAG', '')     # 전문가가 다른 서버일 때 결과 파일 이름 앞에 붙인다(예: tw → chain_tw_no_jev.json)


def e4b_stage(w, x):
    prompt, valid = build(JOB[w], x)
    t0 = time.perf_counter()
    try:
        r = post(E4B_URL, {'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 16, 'temperature': 0, 'cache_prompt': True})
        txt = r['choices'][0]['message']['content']
        CONFS[(w, id(x))] = r.get('x_conf')
    except Exception as e:  # noqa: BLE001
        return None, (time.perf_counter() - t0) * 1000, 'http_error: ' + repr(e)[:120], ''
    ms = (time.perf_counter() - t0) * 1000
    import re
    m = re.search(r'"item"\s*:\s*(null|\d+)', txt)
    if not m:
        return None, ms, 'parse_fail', txt[:60]
    if m.group(1) == 'null':
        return None, ms, None, txt[:60]
    v = int(m.group(1))
    return (v if v in valid else None), ms, (None if v in valid else 'out_of_range'), txt[:60]


# ---------------- 한 문제를 끝까지 ----------------
CACHE = {'ml': {}, 'jev': {}, 'e4b': {}}


def cached(kind, key, fn, use):
    if use and key in CACHE[kind]:
        return CACHE[kind][key], True
    v = fn()
    CACHE[kind][key] = v
    return v, False


def rules_stage(w, i, x):
    job = JOB[w]
    items = job['items']
    t0 = time.perf_counter()
    a = analyze(x['q'])
    rs = rule_slots(a['tt'], items)
    if rs['day'] is None:
        rs['day'] = rule_slots(x['q'], items)['day']
    anchor = None
    emb_ms = 0.0
    if rs['rel'] is not None:
        kind = 'excl' if a['negation'] else 'tt'
        row = EMB[w][str(i)].get(kind)
        if row:
            emb_ms = row['ms']
            k = max(row['scores'], key=row['scores'].get)
            if row['scores'][k] >= TAU_ANCHOR:
                anchor = int(k)
    slots = {k: rs[k] for k in ('day', 'pos', 'kind', 'meal', 'rel', 'kw', 'nextday')}
    slots['anchor'] = anchor
    r = resolve(items, slots)
    return r, (time.perf_counter() - t0) * 1000 + emb_ms, rs['rel'] is not None


VARIANTS = {   # rules · ml · jev · e4b_only
    'full': dict(rules=True, ml=True, jev=True, jev_in='itin'),          # 수정 판: Jev 입력에 고객의 일정 목록
    'full_v1': dict(rules=True, ml=True, jev=True, jev_in='ctx'),        # 사전 등록 판: 「일정 보유」 한 줄만
    'e4b_only': dict(rules=False, ml=False, jev=False, direct=True),
    'full_noctx': dict(rules=True, ml=True, jev=True, jev_in='none'),
    'no_rules': dict(rules=False, ml=True, jev=True, jev_in='itin'),
    'no_jev': dict(rules=True, ml=True, jev=False),
    'no_ml': dict(rules=True, ml=False, jev=True, jev_in='itin'),
    'rules_e4b': dict(rules=True, ml=False, jev=False),
}


def one(w, i, fl, use_cache):
    job, x = JOB[w], JOB[w]['qs'][i]
    tr = {'set': w, 'qi': i, 'type': x['type'], 'gold': x['gold'], 'q': x['q'], 'path': [], 'calls': {}, 'ms': {}, 'fail': [], 'route': None}
    pick, ended = None, None
    t_all = 0.0
    route = None
    if fl.get('direct'):
        route = 'point'
    if fl['rules'] and route is None:
        r, ms, used_emb = rules_stage(w, i, x)
        tr['ms']['rules'] = ms
        t_all += ms
        tr['calls']['rules'] = 1
        tr['path'].append('rules')
        if used_emb:
            tr['calls']['embed'] = 1
        if r[0] == 'item':
            pick, ended = r[1], 'rules'
        elif r[0] == 'none':
            pick, ended = None, 'rules'
        elif x.get('history'):
            route = 'point'
            tr['path'].append('history→expert')
        tr['rule_why'] = r[2] if len(r) > 2 else None
    if ended is None and route is None and fl['ml']:
        (pr, ms), hit = cached('ml', (w, i), lambda: cls_stage(x['q']), use_cache)
        tr['ms']['ml'] = ms
        t_all += ms
        tr['calls']['ml'] = 1
        tr['path'].append('ml')
        tr['ml_intent'] = {k: round(v, 3) for k, v in pr['intent'].items()}
        tr['ml_labels'] = {h: max(pr[h], key=pr[h].get) for h in HEADS}
        if pr['intent']['other'] >= REJECT_P:
            route = 'reject'
            tr['route_by'] = 'ml'
        elif not fl['jev']:
            route = 'point'          # Jev 단계가 없으면 ML 이 「범위 밖이 아님」으로 통과시킨 것이 곧 보낼 곳 결정이다
            tr['route_by'] = 'ml'
    if ended is None and route is None and fl['jev']:
        (pr, ms, err), hit = cached('jev', (w, i, fl.get('jev_in', 'itin')), lambda: jev_stage(x, job, fl.get('jev_in', 'itin')), use_cache)
        tr['ms']['jev'] = ms
        t_all += ms
        tr['calls']['jev'] = 1
        tr['path'].append('jev')
        if err or not pr or not pr.get('route'):
            tr['fail'].append('jev_error: ' + str(err))
            route = 'point'
            tr['route_by'] = 'jev_fallback'
        else:
            rp = pr['route']
            route = max(rp, key=rp.get)
            tr['route_by'] = 'jev'
            tr['jev_route_p'] = {k: round(v, 3) for k, v in rp.items()}
            tr['jev_labels'] = {h: max(pr[h], key=pr[h].get) for h in CLS_Q if pr.get(h)}
    if ended is None and route is None:
        route = 'point'
        tr['route_by'] = 'default'
    if ended is None:
        tr['route'] = route
        if route == 'point':
            (p, ms, err, raw), hit = cached('e4b', (w, i), lambda: e4b_stage(w, x), use_cache)
            tr['ms']['e4b'] = ms
            t_all += ms
            tr['calls']['e4b'] = 1
            tr['path'].append('e4b')
            if err:
                tr['fail'].append(err)
                tr['raw'] = raw     # 실패한 호출의 원문 앞 60자 — 읽기 실패 원인을 보려고 남긴다(2026-10-06)
            pick, ended = p, 'e4b'
        else:
            pick, ended = None, 'reject'
            tr['path'].append('reject→없음')
    tr['pick'], tr['ended'], tr['total_ms'] = pick, ended, t_all
    tr['route_gold'] = 'reject' if x['type'] in ('out_of_scope', 'chitchat', 'tourist_synth_out') else 'point'     # 뒤 둘은 섞은 시험 세트(mixed)의 유형 — 정답이 「없음」인 일정 밖 말
    return tr


def run_variant(name, use_cache=True, tag=None):
    fl = VARIANTS[name]
    traces = []
    t0 = time.time()
    for w in W:
        n = len(JOB[w]['qs'])
        for i in range(0, n if not LIMIT else min(n, LIMIT), STRIDE):
            traces.append(one(w, i, fl, use_cache))
    print(f'{tag or name} 끝 {len(traces)}문제 {time.time() - t0:.0f}초', flush=True)
    json.dump(traces, open(f'{OUT}/chain_{TAGP + "_" if TAGP else ""}{(tag or name).replace("#", "_")}.json', 'w', encoding='utf-8'), ensure_ascii=False)
    return traces


def score(traces):
    r = {'n769': 0, 'ok769': 0, 'wrong769': 0, 'miss769': 0, 'comp_n': 0, 'comp_A': 0, 'comp_B': 0}
    by = collections.defaultdict(lambda: [0, 0])
    ended = collections.Counter()
    lat = []
    calls = collections.Counter()
    for t in traces:
        ended[t['ended']] += 1
        lat.append(t['total_ms'])
        for k, v in t['calls'].items():
            calls[k] += v
        if t['type'] == 'compound_intent':
            r['comp_n'] += 1
            r['comp_A'] += t['pick'] == t['gold']
            r['comp_B'] += t['pick'] in (GOLDSETS.get(t['set'], {}).get(str(t['qi'])) or [])
            continue
        ok = t['pick'] == t['gold']
        r['n769'] += 1
        r['ok769'] += ok
        r['wrong769'] += (t['pick'] is not None and not ok)
        r['miss769'] += (t['pick'] is None and t['gold'] is not None)
        by[t['type']][0] += ok
        by[t['type']][1] += 1
    lat.sort()
    r['lat_median_ms'] = lat[len(lat) // 2]
    r['lat_p95_ms'] = lat[int(len(lat) * 0.95)]
    r['by_type'] = {k: v for k, v in by.items()}
    r['ended'] = dict(ended)
    r['calls'] = dict(calls)
    return r


def mcnemar(a, b):
    """a, b = 같은 문제 순서의 트레이스 목록 → (a 만 맞음, b 만 맞음, 정확검정 p) — 요청 둘 제외."""
    x = y = 0
    for ta, tb in zip(a, b):
        if ta['type'] == 'compound_intent':
            continue
        oa, ob = ta['pick'] == ta['gold'], tb['pick'] == tb['gold']
        x += oa and not ob
        y += ob and not oa
    n = x + y
    p = 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, k) for k in range(min(x, y) + 1)) / 2 ** n)
    return x, y, p


def routing(traces):
    """Jev·ML 이 「어느 전문가로 보낼지」 정한 문제만 — 정답 경로: 범위 밖(out_of_scope) → reject, 그 밖 → point."""
    c = collections.Counter()
    ok_after = collections.Counter()
    for t in traces:
        if t['route'] is None:
            continue
        if t.get('route_by') in (None, 'default') or t['ended'] == 'rules':
            continue
        key = (t['route_gold'], t['route'])
        c[key] += 1
        ok_after[(t['route_gold'] == t['route'], t['pick'] == t['gold'])] += 1
    return {f'{a}→{b}': n for (a, b), n in c.items()}, {f'경로{"맞음" if a else "틀림"}·최종{"정답" if b else "오답"}': n for (a, b), n in ok_after.items()}


if __name__ == '__main__':
    names = sys.argv[1].split(',') if len(sys.argv) > 1 else ['full_v1', 'full_noctx', 'e4b_only', 'full', 'no_rules', 'no_jev', 'no_ml', 'rules_e4b', 'full#live', 'e4b_only#live']
    res = {}
    allt = {}
    for nm in names:
        live = nm.endswith('#live')
        base = nm.split('#')[0]
        if live:   # 캐시 없이 다시 호출 — 실제 지연과 재현(같은 답인지) 확인
            saved = {k: dict(v) for k, v in CACHE.items()}
            CACHE.update({'ml': {}, 'jev': {}, 'e4b': {}})
        tr = run_variant(base, use_cache=not live, tag=nm)
        allt[nm] = tr
        res[nm] = score(tr)
        res[nm]['routing'] = routing(tr)
        if live:
            CACHE.update(saved)
            same = sum(1 for a, b in zip(allt[base], tr) if a['pick'] == b['pick'])
            res[nm]['same_pick_as_first_pass'] = f'{same}/{len(tr)}'
    base = allt.get('e4b_only')
    if base:
        for nm, tr in allt.items():
            if nm != 'e4b_only' and not nm.endswith('#live'):
                res[nm]['vs_e4b_only(a만,b만,p)'] = mcnemar(tr, base)
    json.dump(res, open(f'{OUT}/chain_summary{"_" + TAGP if TAGP else ""}.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({k: {x: v for x, v in r.items() if x in ('ok769', 'n769', 'wrong769', 'miss769', 'comp_A', 'comp_B', 'lat_median_ms', 'lat_p95_ms', 'ended', 'calls', 'vs_e4b_only(a만,b만,p)')} for k, r in res.items()}, ensure_ascii=False, indent=1))
