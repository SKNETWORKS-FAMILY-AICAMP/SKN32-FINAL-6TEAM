# 순서·상대 위치 세트(ord2=개발용, ord3=판정용) 채점 — 직접 짚기 vs 자리표 추출 + 코드 조회.
#  방식: Jev 직접 / Codex 직접 / [S1] Jev 자리표 + 코드 / [S2] 규칙 자리표 + Jev 기준항목 + 코드 / [S3] 규칙 우선, 빈 칸만 Jev 자리표로 채움 + Jev 기준항목 + 코드
#  코드가 확정 못 하면(fallback) 그 방식의 「직접 짚기」(Jev 직접)로 대신한다. 정답 null 은 일정 밖.
# 사용: python eval_ord.py ord2 ord3
import json, os, sys
from slot_lookup import resolve
from rule_slots import rule_slots

HERE = os.path.dirname(os.path.abspath(__file__))
from testsets import fixture  # 시험 세트 자리 — datasets/core/pointing (2026-10-16)
R = lambda f: os.path.join(HERE, 'results', f)
J = lambda f: json.load(open(f, encoding='utf-8'))


def jev_direct(job, suf=''):
    rows = J(R(f'jev_out_{job}{suf}.json'))[job]['rows']
    def g(i):
        p = rows[i]['probs']; k = max(p, key=p.get)
        return None if k == 'none' else int(k.split('_')[1])
    return g


def stat(qs, get):
    ok = bad = miss = 0
    for i, x in enumerate(qs):
        p, g = get(i), x['gold']
        ok += (p == g); bad += (p is not None and p != g); miss += (p is None and g is not None)
    return ok, len(qs), bad, miss


def show(name, r, extra=''):
    print(f"  {name:<46} {r[0]}/{r[1]}={r[0] / r[1]:.0%} 엉뚱 {r[2]} 못 찾음 {r[3]} {extra}")


def run(job):
    st = J(fixture(f'{job}.json'))['sets'][job]
    qs, items = st['qs'], st['items']
    print(f"\n## {job} — {len(qs)}문제 (정답 null {sum(x['gold'] is None for x in qs)})")
    dj = jev_direct(job)
    show('Jev 직접 짚기', stat(qs, dj))
    show('Jev 직접 짚기(정의 명시)', stat(qs, jev_direct(job, '_proto')))
    for tag in ('gpt-6-luna', 'gpt-6-sol'):
        for sf, lab in (('', ''), ('_proto', '(정의 명시)')):
            f = R(f'codex_{tag}_{job}{sf}.json')
            if os.path.exists(f):
                c = J(f)[job]
                show(tag + lab, stat(qs, lambda i, c=c: c.get(str(i))))
    jrows = J(R(f'jev_slots_{job}.json'))[job]
    fbs = {'못 정하면 못 찾음': lambda i: None, '못 정하면 Jev 직접': dj}

    def slots_of(mode, i):
        js = jrows[i]['slots']
        rs = rule_slots(qs[i]['q'], items)
        if mode == 'S1':
            return dict(js)
        s = {'anchor': js.get('anchor'), 'nextday': rs['nextday'], 'kw': rs['kw']}
        for k in ('day', 'pos', 'kind', 'meal', 'rel'):
            s[k] = rs[k] if (rs[k] is not None or mode == 'S2') else js.get(k)
        return s

    for mode, name in (('S1', 'S1 Jev 자리표 + 코드'), ('S2', 'S2 규칙 자리표 + Jev 기준항목 + 코드'), ('S3', 'S3 규칙 우선·빈 칸 Jev + 코드')):
        for fbn, fb in fbs.items():
            cnt = {'item': 0, 'none': 0, 'fallback': 0}
            def g(i, mode=mode, fb=fb, cnt=cnt):
                r = resolve(items, slots_of(mode, i))
                cnt[r[0]] += 1
                return r[1] if r[0] == 'item' else (None if r[0] == 'none' else fb(i))
            show(f'{name} · {fbn}', stat(qs, g), f"| 확정 {cnt['item']} · 일정 밖 {cnt['none']} · 대신 {cnt['fallback']}")
    return st


if __name__ == '__main__':
    for j in sys.argv[1:]:
        run(j)
