# OpenDecider 결과(od_out_*.json: 질문마다 [항목들..., 「없음」] 선택지의 확률)를 평가한다.
#  - 기본: 확률이 가장 큰 선택지. 「없음」이 최고면 기권.
#  - 문턱: 개발용(mine38 + dev50)에서만 정한다(최고 확률이 문턱 미만이면 기권). 판정은 보류 90문항.
# 사용: python eval_od.py <od_out_*.json ...>
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
job = json.load(open(os.path.join(HERE, 'fixtures', 'job.json'), encoding='utf-8'))['sets']
DEV, HELD = ('mine38', 'dev50'), ('test50', 'hard40')


def predict(res, s, qi, tau):
    ids, probs = res[s]['ids'], res[s]['probs'][qi]
    j = max(range(len(probs)), key=lambda k: probs[k])
    if j == len(ids) or probs[j] < tau:      # 「없음」 선택지가 최고이거나 확신이 문턱 미만
        return None
    return ids[j]


def stats(res, tau, sets, types=None):
    ok = bad = miss = n = 0
    for s in sets:
        for qi, x in enumerate(job[s]['qs']):
            if types is not None and x.get('type') not in types:
                continue
            p, g = predict(res, s, qi, tau), x['gold']
            n += 1
            ok += (p == g)
            bad += (p is not None and p != g)
            miss += (p is None and g is not None)
    return ok, n, bad, miss


if __name__ == '__main__':
    HARD = {'paraphrase_knowledge', 'sequence'}
    for path in sys.argv[1:]:
        res = json.load(open(path, encoding='utf-8'))
        best = max([x / 20 for x in range(0, 20)], key=lambda t: (lambda a: a[0] - 2 * a[2])(stats(res, t, DEV)))
        for label, tau in (('문턱 없음', 0.0), (f'개발용에서 고른 문턱 {best:.2f}', best)):
            a = stats(res, tau, HELD)
            easy = stats(res, tau, HELD, {x.get('type') for s in HELD for x in job[s]['qs']} - HARD - {None})
            hard = stats(res, tau, HELD, HARD)
            d = stats(res, tau, DEV)
            print(f"{os.path.basename(path)} · {label}: 보류 {a[0]}/{a[1]}={a[0] / a[1]:.0%} 엉뚱 {a[2]} 못 찾음 {a[3]} | 쉬운 {easy[0]}/{easy[1]} · 어려운 {hard[0]}/{hard[1]} | 개발용 {d[0]}/{d[1]} | {res['_sec_per_q']:.2f}초/질문")
