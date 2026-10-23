# 지목한 3종 조합 — Qwen3-Reranker-4B + WeMM-Embedding-4B + OpenDecider-small(4B) — 을 오프라인으로 잰다.
#  - 재평가·임베딩은 쌍 점수를 질문마다 소프트맥스(온도는 개발용에서만), OpenDecider 는 저장된 선택지 확률을 쓴다.
#  - 합치기: 세 확률 평균. OpenDecider 의 「없음」 확률은 (없음 몫 = OD/3)로 반영하는 변형과 무시하는 변형을 둘 다 잰다.
#  - 규칙(날짜·시간대·시각·종류)은 켠 것과 끈 것을 모두 낸다. 문턱은 개발용(mine38+dev50)에서만 고르고 판정은 보류 90개.
# 사용: python ensemble_trio.py <datasets/core/pointing/benchmarks/plan_qa_bench/raw 폴더>
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


COMBOS = {
    '재평가4B 단독': [EMB[0]],
    'WeMM-4B 단독': [EMB[1]],
    'OD-small 단독': ['od'],
    '재평가4B+WeMM-4B': EMB,
    '재평가4B+OD': [EMB[0], 'od'],
    'WeMM-4B+OD': [EMB[1], 'od'],
    '세 개 전부': EMB + ['od'],
}
print('모델별 온도는 개발용에서 고름. 판정 = 보류 90(test50+hard40). 엉뚱=틀린 항목+없는 질문에 항목.')
for rules in (False, True):
    temps = {m: temp_for(m, rules) for m in EMB}
    print(f"\n### 규칙 {'켬' if rules else '끔'} (온도 {', '.join(f'{m.split(chr(47))[-1]}={temps[m]}' for m in EMB)})")
    for nm in ('ignore', 'count'):
        print(f"-- OD 「없음」 확률 {'무시' if nm == 'ignore' else '반영'}")
        for name, use in COMBOS.items():
            if nm == 'count' and 'od' not in use:
                continue
            tau = max([x / 20 for x in range(20)], key=lambda t: (lambda a: a[0] - 2 * a[2])(stats(use, temps, t, DEV, rules, nm)))
            a = stats(use, temps, tau, HELD, rules, nm)
            e = stats(use, temps, tau, HELD, rules, nm, False)
            h = stats(use, temps, tau, HELD, rules, nm, True)
            print(f"  {name:<18} 보류 {a[0]}/{a[1]}={a[0] / a[1]:.0%} 엉뚱 {a[2]} 못 찾음 {a[3]} | 쉬운 {e[0]}/{e[1]} 어려운 {h[0]}/{h[1]} (문턱 {tau:.2f})")
