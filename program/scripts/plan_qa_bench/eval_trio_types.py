# 지목한 3종 조합 — Qwen3-Reranker-4B + WeMM-Embedding-4B + OpenDecider-small(4B) — 을 오프라인으로 잰다.
#  - 재평가·임베딩은 쌍 점수를 질문마다 소프트맥스(온도는 개발용에서만), OpenDecider 는 저장된 선택지 확률을 쓴다.
#  - 합치기: 세 확률 평균. OpenDecider 의 「없음」 확률은 (없음 몫 = OD/3)로 반영하는 변형과 무시하는 변형을 둘 다 잰다.
#  - 규칙(날짜·시간대·시각·종류)은 켠 것과 끈 것을 모두 낸다. 문턱은 개발용(mine38+dev50)에서만 고르고 판정은 보류 90개.
# 사용: python ensemble_trio.py <datasets/travel/plan_qa_bench/raw 폴더>
import json, math, os, sys
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from recog_v2 import RecognizerV3  # noqa: E402

RAW = sys.argv[1]
job = json.load(open(os.path.join(HERE, 'fixtures', 'job.json'), encoding='utf-8'))['sets']
pairs = json.load(open(os.path.join(RAW, 'pairs.json'), encoding='utf-8'))
sc = json.load(open(os.path.join(RAW, 'emb_rr_out.json'), encoding='utf-8'))
od = json.load(open(os.path.join(HERE, 'results', 'od_out_opendecider-small.json'), encoding='utf-8'))
DEV, HELD = ('mine38', 'dev50'), ('test50', 'hard40')
HARD = {'paraphrase_knowledge', 'sequence'}
EMB = ['Qwen/Qwen3-Reranker-4B', 'tencent/WeMM-Embedding-4B']


class RuleOnly(RecognizerV3):
    def __init__(self, items, today):
        self.items = sorted(items, key=lambda i: (i['date'], i['start']))
        self.today = today
        self.days = sorted({date.fromisoformat(i['date']) for i in self.items})


REC = {s: RuleOnly(st['items'], date.fromisoformat(st['today'])) for s, st in job.items()}
T = {m: defaultdict(dict) for m in EMB}
for m in EMB:
    for p, v in zip(pairs, sc[m]):
        T[m][(p['set'], p['qi'])][p['item']] = v


def softmax(d, t):
    mx = max(d.values())
    e = {k: math.exp((v - mx) / t) for k, v in d.items()}
    z = sum(e.values())
    return {k: v / z for k, v in e.items()}


def allowed(s, q):
    pool, sig = REC[s].filt(q)
    return ({i['id'] for i in pool} if sig else None)


def emb_probs(m, s, qi, q, t, rules):
    d = T[m][(s, qi)]
    if rules:
        ids = allowed(s, q)
        if ids is not None:
            d = {k: v for k, v in d.items() if k in ids} or d
    return softmax(d, t)


def od_probs(s, qi, q, rules):
    ids, pr = od[s]['ids'], od[s]['probs'][qi]
    d = {i: pr[k] for k, i in enumerate(ids)}
    none = pr[len(ids)]
    if rules:
        al = allowed(s, q)
        if al is not None:
            d = {k: v for k, v in d.items() if k in al} or d
    return d, none


def temp_for(m, rules):
    best = None
    for t in (0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2):
        nll = n = 0
        for s in DEV:
            for qi, x in enumerate(job[s]['qs']):
                if x['gold'] is None:
                    continue
                nll += -math.log(max(emb_probs(m, s, qi, x['q'], t, rules).get(x['gold'], 0), 1e-9))
                n += 1
        if best is None or nll / n < best[0]:
            best = (nll / n, t)
    return best[1]


def predict(use, temps, s, qi, q, tau, rules, none_mode):
    agg = defaultdict(float)
    none = 0.0
    for m in EMB:
        if m in use:
            for k, v in emb_probs(m, s, qi, q, temps[m], rules).items():
                agg[k] += v / len(use)
    if 'od' in use:
        d, nn = od_probs(s, qi, q, rules)
        z = sum(d.values()) or 1
        for k, v in d.items():
            agg[k] += (v / z if none_mode == 'ignore' else v) / len(use)
        if none_mode == 'count':
            none += nn / len(use)
    top = max(agg, key=agg.get)
    if none_mode == 'count' and none > agg[top]:
        return None
    return top if agg[top] >= tau else None


def stats(use, temps, tau, sets, rules, nm, types=None):
    ok = bad = miss = n = 0
    for s in sets:
        for qi, x in enumerate(job[s]['qs']):
            if types is not None and (x.get('type') in HARD) != types:
                continue
            p, g = predict(use, temps, s, qi, x['q'], tau, rules, nm), x['gold']
            n += 1
            ok += (p == g)
            bad += (p is not None and p != g)
            miss += (p is None and g is not None)
    return ok, n, bad, miss



# ── 유형별 채점(기존 판정 90문항 = test50 + hard40) — 재평가·WeMM·OpenDecider vs Gemma 26B
gem = json.load(open(os.path.join(HERE, 'results', 'llm_out.json'), encoding='utf-8'))
g26 = {(s, qi): gem['gemma4:26b'][s][qi] for s in HELD for qi in range(len(job[s]['qs']))}
COMBOS = {'재평가4B': [EMB[0]], 'WeMM-4B': [EMB[1]], 'OD-small': ['od'], 'A3(재평가4B+WeMM-4B)': EMB, '세 개 전부': EMB + ['od']}
types = sorted({x.get('type') for s in HELD for x in job[s]['qs']})
res = {}
for rules in (True,):
    temps = {m: temp_for(m, rules) for m in EMB}
    for name, use in COMBOS.items():
        nm = 'count'
        tau = max([x / 20 for x in range(20)], key=lambda t: (lambda a: a[0] - 2 * a[2])(stats(use, temps, t, DEV, rules, nm)))
        bt = defaultdict(lambda: [0, 0])
        for s in HELD:
            for qi, x in enumerate(job[s]['qs']):
                p = predict(use, temps, s, qi, x['q'], tau, rules, nm)
                bt[x.get('type')][0] += (p == x['gold']); bt[x.get('type')][1] += 1
        res[name] = bt
bt26 = defaultdict(lambda: [0, 0])
for s in HELD:
    for qi, x in enumerate(job[s]['qs']):
        bt26[x.get('type')][0] += (g26[(s, qi)] == x['gold']); bt26[x.get('type')][1] += 1
print('기존 판정 90문항 — 유형별 맞은 수 (규칙 켬, 문턱은 개발용에서 고름). 26B 대비 ▲=이김 ▼=짐')
print(f"{'유형':<24}{'n':>3}{'26B':>5}  " + '  '.join(f'{n[:9]:<9}' for n in COMBOS))
for t in types:
    n = bt26[t][1]
    row = []
    for name in COMBOS:
        v = res[name][t][0]; d = v - bt26[t][0]
        row.append(f"{v}{'▲' if d > 0 else ('▼' if d < 0 else '=')}".ljust(9))
    print(f"{str(t):<24}{n:>3}{bt26[t][0]:>5}  " + '  '.join(row))
tot = {n: sum(res[n][t][0] for t in types) for n in COMBOS}
print('합계 26B', sum(bt26[t][0] for t in types), '/ 90 ·', ' · '.join(f'{n} {v}' for n, v in tot.items()))
