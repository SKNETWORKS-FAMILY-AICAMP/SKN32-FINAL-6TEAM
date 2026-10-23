# 가벼운 모델 앙상블(오프라인, 서버 불필요) — yok3x fork 방식: 모델마다 확률을 내고 평균한다.
#  - 임베딩·재평가 모델의 쌍 점수(emb_rr_out.json · scores.json) → 질문마다 항목 확률(소프트맥스, 온도는 개발용에서만 고름)
#  - 모델 상위 k개는 개발용(mine38 + dev50)의 정확도로만 고른다. 판정은 보류 묶음(test50 + hard40) 90개.
#  - 「전부 섞기」와 비교해 yok3x 의 관찰(전부 섞으면 나빠짐)을 확인한다.
#  - 기권: 평균 확률의 최고값이 문턱 미만이면 「없음」. 문턱은 개발용에서만 정한다.
# 사용: python ensemble_light.py <작업 폴더 SP>   (SP 배치는 README 참고)
import json, math, os, sys
from collections import defaultdict
from datetime import date

SP = sys.argv[1]
sys.path.insert(0, SP)
from recog_v2 import RecognizerV3  # noqa: E402

J = os.path.join(SP, 'rerank_job')
job = json.load(open(os.path.join(J, 'job.json'), encoding='utf-8'))['sets']
pairs = json.load(open(os.path.join(J, 'pairs.json'), encoding='utf-8'))
scores = {}
for fn in ('emb_rr_out.json', 'scores.json'):
    p = os.path.join(J, fn)
    if os.path.exists(p) and os.path.getsize(p):
        scores.update(json.load(open(p, encoding='utf-8')))
DEV, HELD = ('mine38', 'dev50'), ('test50', 'hard40')


class RuleOnly(RecognizerV3):
    # 규칙(filt)만 쓴다 — 임베딩 색인을 만들지 않으므로 올라마·카카오 분류 파일이 필요 없다
    def __init__(self, items, today):
        self.items = sorted(items, key=lambda i: (i['date'], i['start']))
        self.today = today
        self.days = sorted({date.fromisoformat(i['date']) for i in self.items})


REC = {s: RuleOnly(st['items'], date.fromisoformat(st['today'])) for s, st in job.items()}

# 모델 -> (set, qi) -> {item_id: score}
T = {m: defaultdict(dict) for m in scores}
for m, sc in scores.items():
    for p, v in zip(pairs, sc):
        T[m][(p['set'], p['qi'])][p['item']] = v


def softmax(d, temp):
    mx = max(d.values())
    e = {k: math.exp((v - mx) / temp) for k, v in d.items()}
    z = sum(e.values())
    return {k: v / z for k, v in e.items()}


def allowed(s, q):
    pool, sig = REC[s].filt(q)
    ids = {i['id'] for i in pool}
    return (ids if sig else None), sig


def probs_for(m, s, qi, q, temp, use_rules=True):
    d = T[m][(s, qi)]
    if use_rules:
        ids, sig = allowed(s, q)
        if ids is not None:
            d = {k: v for k, v in d.items() if k in ids}
            if not d:
                return {}
    return softmax(d, temp) if d else {}


def calib_temp(m):
    # 개발용에서 정답 항목이 있는 질문의 음의 로그우도가 가장 작은 온도
    best, bt = None, 0.05
    for temp in (0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5):
        nll = 0
        n = 0
        for s in DEV:
            for qi, x in enumerate(job[s]['qs']):
                if x['gold'] is None:
                    continue
                pr = probs_for(m, s, qi, x['q'], temp)
                nll += -math.log(max(pr.get(x['gold'], 0.0), 1e-9))
                n += 1
        if best is None or nll / n < best:
            best, bt = nll / n, temp
    return bt


def predict(models, temps, s, qi, q, tau):
    agg = defaultdict(float)
    for m in models:
        for k, v in probs_for(m, s, qi, q, temps[m]).items():
            agg[k] += v / len(models)
    if not agg:
        return None
    top = max(agg, key=agg.get)
    return top if agg[top] >= tau else None


def stats(models, temps, tau, sets):
    ok = wrong = fp = miss = n = 0
    for s in sets:
        for qi, x in enumerate(job[s]['qs']):
            p = predict(models, temps, s, qi, x['q'], tau)
            g = x['gold']
            n += 1
            ok += (p == g)
            wrong += (p is not None and g is not None and p != g)
            fp += (p is not None and g is None)
            miss += (p is None and g is not None)
    return ok, n, wrong + fp, miss


def pick_tau(models, temps):
    best, bt = None, 0.0
    for tau in [x / 20 for x in range(0, 20)]:
        ok, n, bad, miss = stats(models, temps, tau, DEV)
        score = ok - 2 * bad
        if best is None or score > best:
            best, bt = score, tau
    return bt


def solo_dev_acc(m, temps):
    ok = n = 0
    for s in DEV:
        for qi, x in enumerate(job[s]['qs']):
            if x['gold'] is None:
                continue
            p = predict([m], temps, s, qi, x['q'], 0.0)
            n += 1
            ok += (p == x['gold'])
    return ok / n


temps = {m: calib_temp(m) for m in scores}
dev_acc = {m: solo_dev_acc(m, temps) for m in scores}
rank = sorted(scores, key=lambda m: -dev_acc[m])
print('== 모델별(개발용 정확도로 정렬, 규칙 적용, 온도는 개발용에서 고름)')
for m in rank:
    tau = pick_tau([m], temps)
    ok, n, bad, miss = stats([m], temps, tau, HELD)
    print(f"  {m:<42} 개발 {dev_acc[m]:.0%} · 보류 {ok}/{n}={ok / n:.0%} 엉뚱한 답 {bad} 못 찾음 {miss} (문턱 {tau:.2f}, 온도 {temps[m]})")
print('\n== 앙상블(확률 평균) — 모델 상위 k개는 개발용 정확도로만 고름')
for k in (1, 2, 3, 4, 5, 6, len(rank)):
    models = rank[:k]
    tau = pick_tau(models, temps)
    ok, n, bad, miss = stats(models, temps, tau, HELD)
    label = '전부 섞기' if k == len(rank) else f'상위 {k}개'
    print(f"  {label:<10} {k:>2}개  보류 {ok}/{n}={ok / n:.0%} · 엉뚱한 답 {bad} · 못 찾음 {miss} (문턱 {tau:.2f})  [{', '.join(x.split('/')[-1] for x in models[:6])}{'…' if k > 6 else ''}]")
