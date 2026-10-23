# 「소형」을 사용자 예산(활성 파라미터 3.8B 미만 · 저장 18GB 미만 — 26B-A4B 보다 작게)으로 다시 잡은 오프라인 계산.
#  앞선 small_ensemble_769.py 는 12B(Decider·Winnow·Cygnet 등, 밀집 11.9B)를 「소형」으로 썼는데 사용자 예산을 못 지킨다 — 이 파일은 4B 급(유효 4B 이하)만 구성원으로 쓴다.
#  구성원: 가르친 E4B · 무학습 E4B QAT · Hopper 4B · Plumb-4B · lev · JevK5 4B · Manchego v2.1 · Winnow-E4B (모두 mix8~10 에서 잰 값 있음).
#  비교 구간: mix8~10 요청 둘 제외 460문제(모든 구성원이 푼 문제). 새 호출 없음. 합의·투표는 사용자가 쓰지 말라고 한 방식이라 참고로만 낸다 — 주 결과는 「유형별 라우팅」.
# 사용: python small4b_ensemble_460.py > results/small4b_ensemble_460.txt
import csv, json, math, os, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SETS3 = ['mix8', 'mix9', 'mix10']
sys.stdout.reconfigure(encoding='utf-8')


def fnum(x):
    return None if x in ('', None) else int(float(x))


rows = list(csv.DictReader(open(os.path.join(HERE, 'results/export/per_question.csv'), encoding='utf-8-sig')))
GOLD, TYPE, PICK = {}, {}, defaultdict(dict)
for r in rows:
    if r['set'] in SETS3:
        k = (r['set'], int(r['q_index']))
        GOLD[k], TYPE[k] = fnum(r['gold']), r['q_type']
        PICK[r['model']][k] = fnum(r['pick'])
E4BT = {}
for s in SETS3:
    ev = json.load(open(os.path.join(HERE, f'results/_pull/distill_eval/eval_r16e2_{s}.json'), encoding='utf-8'))
    for i, p in enumerate(ev['r16e2#lora']['picks']):
        E4BT[(s, i)] = p
PICK['가르친 E4B'] = E4BT
KEYS = [k for k in sorted(GOLD, key=lambda k: (SETS3.index(k[0]), k[1])) if TYPE[k] != 'compound_intent']
print(f'# 4B 급(활성 4B 이하)만으로 — mix8~10 요청 둘 제외 {len(KEYS)}문제 오프라인 계산\n')


def find(prefix):
    c = [m for m in PICK if m.startswith(prefix)]
    assert len(c) == 1, (prefix, c)
    return c[0]


M = {'가르친 E4B': '가르친 E4B', 'E4B QAT 무학습': find('Gemma 4 E4B QAT'), 'Hopper 4B': find('Hopper 4B'), 'Plumb-4B': find('Plumb-4B'), 'lev': find('lev('),
     'JevK5 4B': find('JevK5 4B'), 'Manchego v2.1': find('Manchego v2.1'), 'Winnow-E4B': find('Winnow-E4B')}
ok = lambda m, k: PICK[M[m]].get(k) == GOLD[k]


def mc(a, b, keys=KEYS):
    oa = sum(1 for k in keys if a(k) and not b(k))
    ob = sum(1 for k in keys if b(k) and not a(k))
    n = oa + ob
    return oa, ob, (1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(oa, ob) + 1)) / 2 ** n))


print('## 1. 단독 (460문제)')
for m in M:
    n = sum(ok(m, k) for k in KEYS)
    a, b, p = mc(lambda k, m=m: ok(m, k), lambda k: ok('가르친 E4B', k)) if m != '가르친 E4B' else (0, 0, 1)
    print(f'{m:<16}{n:>4}/460 = {100 * n / 460:5.1f}%' + ('' if m == '가르친 E4B' else f'  | 가르친 E4B 대비 {a}:{b}, p={p:.3f}'))

types = sorted({TYPE[k] for k in KEYS})
print('\n## 2. 유형별 정확도(%) — 4B 급 구성원')
cols = list(M)
print(f'{"유형":<22}{"n":>4} ' + ' '.join(f'{c[:8]:>9}' for c in cols))
for t in types:
    ks = [k for k in KEYS if TYPE[k] == t]
    print(f'{t:<22}{len(ks):>4} ' + ' '.join(f'{100 * sum(ok(c, k) for k in ks) / len(ks):9.1f}' for c in cols))

print('\n## 3. 4B 급 합집합 천장(하나라도 맞힘) — 고르는 방법이 있어야 의미가 있다')
for lab, ms in (('가르친 E4B + Hopper 4B', ['가르친 E4B', 'Hopper 4B']), ('가르친 E4B + Plumb-4B', ['가르친 E4B', 'Plumb-4B']), ('가르친 E4B + 4B 결정 모델 넷(Hopper·Plumb·lev·JevK5)', ['가르친 E4B', 'Hopper 4B', 'Plumb-4B', 'lev', 'JevK5 4B']),
                ('가르친 E4B + 무학습 E4B QAT', ['가르친 E4B', 'E4B QAT 무학습'])):
    n = sum(1 for k in KEYS if any(ok(m, k) for m in ms))
    print(f'{lab:<52}{n}/460 = {100 * n / 460:.1f}%')
base = sum(ok('가르친 E4B', k) for k in KEYS)
print(f'(가르친 E4B 단독 {base}/460 = {100 * base / 460:.1f}%)')

print('\n## 4. 유형별 라우팅(사용자가 말한 방식) — 약한 유형만 그 유형에 가장 강한 4B 급 전문가에게')
errs = Counter(TYPE[k] for k in KEYS if not ok('가르친 E4B', k))
print('가르친 E4B 오답의 유형: ' + ', '.join(f'{t}:{v}' for t, v in errs.most_common()))
for t, _ in errs.most_common(3):
    ks = [k for k in KEYS if TYPE[k] == t]
    best = sorted(((sum(ok(c, k) for k in ks), c) for c in cols if c != '가르친 E4B'), reverse=True)[:3]
    print(f'  {t}({len(ks)}): 가르친 E4B {sum(ok("가르친 E4B", k) for k in ks)} · 다음으로 강한 4B 급 ' + ' · '.join(f'{c} {n}' for n, c in best))
# 유형을 안다고 가정한 상한(낙관) — 유형마다 구성원 중 최고
route = {}
for t in types:
    ks = [k for k in KEYS if TYPE[k] == t]
    bm = max(cols, key=lambda c: (sum(ok(c, k) for k in ks), c == '가르친 E4B'))
    for k in ks:
        route[k] = PICK[M[bm]].get(k)
    if bm != '가르친 E4B':
        print(f'  [유형을 알 때 최고] {t} → {bm}')
n = sum(route[k] == GOLD[k] for k in KEYS)
print(f'유형을 미리 안다고 가정한 4B 급 라우팅 상한: {n}/460 = {100 * n / 460:.1f}% (같은 460에서 고른 값이라 낙관)')
