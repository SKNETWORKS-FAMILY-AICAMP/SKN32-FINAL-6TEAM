# 「섞은 시험 세트(mixed8~12)」 한 줄 연결 시험 결과를 출처별로 집계한다.
#  입력: 서버 C 에서 chain_e2e.py(OUT_TAG=mixed)가 만든 chain_mixed_<변형>.json 5개 세트 합본 — 이 PC 의 datasets/travel/mixed_testset/results/ 에 내려받아 둔다(문장 원문이 있어 git 밖).
#  출처는 세트 파일(datasets/travel/mixed_testset/mixedN.json)의 질문 순서(qi)로 붙인다.
#  출력: results/mixed_chain_report.txt — 건수·비율만(문장 원문은 싣지 않는다: AI Hub 는 재배포 제한, 관광지 질문 모음은 라이선스 표기 없음).
# 사용: python mixed_report.py [변형,쉼표]
import collections
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MIXED = os.path.join(ROOT, 'datasets', 'travel', 'mixed_testset')
RES = os.path.join(MIXED, 'results')
SETS = ['mixed8', 'mixed9', 'mixed10', 'mixed11', 'mixed12']
sys.stdout.reconfigure(encoding='utf-8')
VARS = sys.argv[1].split(',') if len(sys.argv) > 1 else ['e4b_only', 'rules_e4b', 'no_jev', 'full']
TAG = os.environ.get('OUT_TAG', 'mixed')
LAB = {'e4b_only': '가르친 E4B 단독', 'rules_e4b': '규칙 → 가르친 E4B', 'no_jev': '규칙 → ML → 가르친 E4B', 'full': '규칙 → ML → Jev 계열 모델(학습 없는 Winnow-E4B) → 가르친 E4B'}
LAB_TW = {'e4b_only': '가르친 Winnow-E4B 단독', 'rules_e4b': '규칙 → 가르친 Winnow-E4B', 'no_jev': '규칙 → ML → 가르친 Winnow-E4B'}


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def fmt(k, n):
    lo, hi = wilson(k, n)
    return f'{k}/{n} = {100 * k / n:.1f}% (95% 구간 {100 * lo:.1f}~{100 * hi:.1f}%)' if n else '0/0'


def pct(k, n):
    return f'{k}/{n} = {100 * k / n:.1f}%' if n else '0/0'


SRC = {}
for w in SETS:
    job = json.load(open(os.path.join(MIXED, f'{w}.json'), encoding='utf-8'))['sets'][w]
    for i, q in enumerate(job['qs']):
        SRC[(w, i)] = q.get('src', '')


def group(t):
    ty, src = t['type'], SRC[(t['set'], t['qi'])]
    if ty == 'compound_intent':
        return '요청 둘(복합)'
    if ty == 'tourist_synth_in':
        return '관광지 질문 × 일정 안 장소(정답 = 그 항목)'
    if ty == 'tourist_synth_out':
        return '관광지 질문 × 일정 밖 장소(정답 = 없음)'
    if ty == 'chitchat':
        return '일상 대화(AI Hub)(정답 = 없음)' if src.startswith('일상') else '신조어 구어체(KoCulture)(정답 = 없음)'
    return '기존 합성 질문 769(Codex·Claude)'


ORDER = ['기존 합성 질문 769(Codex·Claude)', '관광지 질문 × 일정 안 장소(정답 = 그 항목)', '관광지 질문 × 일정 밖 장소(정답 = 없음)', '일상 대화(AI Hub)(정답 = 없음)', '신조어 구어체(KoCulture)(정답 = 없음)', '요청 둘(복합)']


def load(name):
    return json.load(open(os.path.join(RES, f'chain_{TAG}_{name}.json'), encoding='utf-8'))


def bad(t):
    """읽기 실패(형식 오류·호출 오류) — 엄격 계수에서는 오답이다(정답이 「없음」이어도)."""
    return any(f == 'parse_fail' or f.startswith('http_error') for f in t['fail'])


def good(t):
    return t['pick'] == t['gold'] and not bad(t)


def mcn(a, b):
    n = a + b
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, k) for k in range(min(a, b) + 1)) / 2 ** n)


def main(tag_label):
    data = {}
    for v in VARS:
        try:
            data[v] = load(v)
        except FileNotFoundError:
            print(f'- {v}: 결과 파일이 없다(건너뜀)')
    if not data:
        return
    n_all = len(next(iter(data.values())))
    print(f'# 섞은 시험 세트 한 줄 연결 시험 — {tag_label}')
    print(f'- 질문 {n_all}개(세트 5개 × 약 547개). 구성: 기존 합성 질문 835(그중 요청 둘 66 제외 769) + 관광지 질문 틀 × 우리 장소 목록(일정 안 300 · 일정 밖 300) + AI Hub 일상 대화 1,000 + KoCulture 구어체 300. 변형당 1회(출력은 결정적).')
    print('- 정답: 일정 항목 번호 또는 「없음」. **엄격 계수 — 형식 오류(읽기 실패·빈 답)는 정답이 「없음」이어도 오답**(`good()`).\n')
    # 전체 표 — 정답 없음 질문에 항목을 짚은 건수(= 새어 나감)와 항목 짚기 정확도
    for v, rows in data.items():
        lab = (LAB_TW if tag_label.startswith('가르친 Winnow') else LAB).get(v, v)
        print(f'## {lab}')
        print('| 출처 | 질문 수 | 맞음(엄격) | 틀린 항목을 짚음 | 항목이 있는데 「없음」 | 정답이 「없음」인데 항목을 짚음 | 읽기 실패(빈 답 등) |')
        print('|---|---:|---:|---:|---:|---:|---:|')
        by = collections.defaultdict(list)
        for t in rows:
            by[group(t)].append(t)
        tot = collections.Counter()
        for g in ORDER:
            ts = by.get(g, [])
            if not ts:
                continue
            ok = sum(1 for t in ts if good(t))
            wrong = sum(1 for t in ts if t['pick'] is not None and t['gold'] is not None and t['pick'] != t['gold'])
            miss = sum(1 for t in ts if t['pick'] is None and t['gold'] is not None and not bad(t))
            leak = sum(1 for t in ts if t['pick'] is not None and t['gold'] is None)
            rf = sum(1 for t in ts if bad(t))
            print(f'| {g} | {len(ts)} | {fmt(ok, len(ts)) if "요청 둘" not in g else pct(ok, len(ts))} | {wrong} | {miss} | {leak} | {rf} |')
            if '요청 둘' not in g:
                tot['n'] += len(ts)
                tot['ok'] += ok
        ts_none = [t for t in rows if t['gold'] is None and t['type'] != 'compound_intent']
        leak_all = sum(1 for t in ts_none if t['pick'] is not None)
        ts_item = [t for t in rows if t['gold'] is not None and t['type'] != 'compound_intent']
        ok_item = sum(1 for t in ts_item if good(t))
        ended = collections.Counter(t['ended'] for t in rows)
        calls = collections.Counter()
        for t in rows:
            for k, c in t['calls'].items():
                calls[k] += c
        lat = sorted(t['total_ms'] for t in rows)
        print(f'\n- **정답이 「없음」인 질문 전체에서 항목을 짚은 비율(새어 나감)**: {fmt(leak_all, len(ts_none))}')
        print(f'- **정답 항목이 있는 질문에서 맞힌 비율**: {fmt(ok_item, len(ts_item))}')
        print(f'- 요청 둘 제외 전체 정답: {fmt(tot["ok"], tot["n"])}')
        print(f'- 전문가(가르친 모델) 호출 {calls.get("e4b", 0)}회 / {len(rows)}문제 = {100 * calls.get("e4b", 0) / len(rows):.0f}% · 단계가 끝낸 곳 {dict(ended)}')
        print(f'- 응답 지연(질문 하나, 단계 합): 중앙 {lat[len(lat) // 2]:.0f}ms · p95 {lat[int(len(lat) * 0.95)]:.0f}ms')
        print()
    # 변형끼리 짝지은 비교(요청 둘 제외, 전체 정답)
    if 'e4b_only' in data:
        base = data['e4b_only']
        print('## 전문가 단독과 견줌(요청 둘 제외, 같은 질문 짝지어 McNemar 정확검정)')
        print('| 변형 | 이쪽만 맞음 | 단독만 맞음 | p |')
        print('|---|---:|---:|---:|')
        for v, rows in data.items():
            if v == 'e4b_only':
                continue
            a = b = 0
            for tv, tb in zip(rows, base):
                if tv['type'] == 'compound_intent':
                    continue
                ov, ob = good(tv), good(tb)
                a += ov and not ob
                b += ob and not ov
            print(f'| {(LAB_TW if tag_label.startswith("가르친 Winnow") else LAB).get(v, v)} | {a} | {b} | {mcn(a, b):.3g} |')
        print()
    # 유형별(기존 합성 질문) — 이전 835 시험과 견주려고
    print('## 기존 합성 질문 769만 따로(이전 한 줄 연결 시험 값과 견주기)')
    for v, rows in data.items():
        ts = [t for t in rows if group(t).startswith('기존')]
        ok = sum(1 for t in ts if good(t))
        print(f'- {(LAB_TW if tag_label.startswith("가르친 Winnow") else LAB).get(v, v)}: {ok}/{len(ts)} = {100 * ok / len(ts):.1f}%')


if __name__ == '__main__':
    main(os.environ.get('LABEL', '가르친 E4B(Q8 GGUF) 전문가'))
