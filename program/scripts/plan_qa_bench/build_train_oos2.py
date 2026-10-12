# 두 번째 잡담 보강 학습 자료(train_oos2.jsonl) — 첫 번째(train_oos.jsonl 1,713행)에 솔 6.1 이 만들고 루나 6.0 이 합의한 학습용 어려운 문장(H-train)을 더한다.
#  더하는 것: 함정(정답 「없음」) 약 600 + 대조(정답 항목 하나) 약 300. 유형 비율은 어려운 세트에서 oos1 이 약했던 곳에 기운다: N6 새 항목 추가 · N1 항목 낱말 섞인 잡담 · N2 일정에 없는 비슷한 장소 · N4 모호한 말 · P3 날짜/순서/시각.
#  고르는 법: 각 유형에서 「oos1 이 틀린 문장」을 먼저(최대 70%) 뽑고 나머지는 무작위 — 틀린 것만 모으면 분포가 한쪽으로 쏠리기 때문. 채굴 결과 파일(d_test_lp_htrain_q4km_oos1.jsonl)이 없으면 전부 무작위.
#  ★시험과 안 겹치게: H 시험(합의분 · 이견분)·D3·D2 잡담 문장과 글자 3-gram 자카드 0.6 이상 겹치는 문장은 뺀다. 일정은 처음부터 D 시험 일정과 겹치지 않는 학습 자료의 일정만 쓴다(build_hard_set.py --heads-file).
# 사용: python build_train_oos2.py <원본 train_oos.jsonl> <출력 train_oos2.jsonl> [SEED=20261017]
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding='utf-8')
src, dst = sys.argv[1], sys.argv[2]
SEED = int(os.environ.get('SEED', '20261017'))
rnd = random.Random(SEED)
HS = os.path.join(HERE, 'results', 'hard_set')
TRAIN_SET = os.path.join(HS, 'h_set_train_60_20261016.json')
TEST_SETS = [os.path.join(HS, 'h_set_test_30_20261015.json')]
MINE = os.path.join(HERE, 'results', 'd_test', 'd_test_lp_htrain_q4km_oos1.jsonl')
QUOTA = {'hard_N6': 200, 'hard_N1': 120, 'hard_N2': 110, 'hard_N4': 100, 'hard_N3': 40, 'hard_N5': 30,
         'hard_P3': 150, 'hard_P2': 55, 'hard_P4': 55, 'hard_P1': 40}
FROM_ERR = 0.7
QRE = re.compile(r'고객 질문: (.*?)\n\n', re.S)


def tri(t):
    t = re.sub(r'\s+', '', t)
    return {t[i:i + 3] for i in range(max(1, len(t) - 2))}


def jac(a, b):
    return len(a & b) / max(1, len(a | b))


# 겹침 검사용 시험 문장
test_q = []
for f in TEST_SETS:
    test_q += [x['q'] for x in json.load(open(f, encoding='utf-8'))]
for f in ('all_prompts_d3.json', 'all_prompts_d2.json'):
    for x in json.load(open(os.path.join(HERE, 'results', 'empty_probe', f), encoding='utf-8')):
        m = QRE.search(x['prompt'])
        if m:
            test_q.append(m.group(1).strip())
test_tri = [tri(q) for q in test_q]

items = [x for x in json.load(open(TRAIN_SET, encoding='utf-8')) if x['status'] == 'agree']
mined = {}
if os.path.exists(MINE):
    for line in open(MINE, encoding='utf-8'):
        r = json.loads(line)
        mined[r['i']] = r
print('학습용 합의 문장', len(items), '/ 채굴 결과', len(mined), '건')


def wrong(x):
    r = mined.get(x['i'])
    if not r or not r.get('parsed'):
        return False
    return r['pick'] != x['gold']


added, dropped_overlap, stats = [], 0, {}
for typ, q in QUOTA.items():
    pool = [x for x in items if x['type'] == typ]
    clean = []
    for x in pool:
        t = tri(x['q'])
        if max((jac(t, b) for b in test_tri), default=0) >= 0.6:
            dropped_overlap += 1
            continue
        clean.append(x)
    err = [x for x in clean if wrong(x)]
    rest = [x for x in clean if not wrong(x)]
    rnd.shuffle(err)
    rnd.shuffle(rest)
    take_err = err[:int(q * FROM_ERR)]
    take = take_err + rest[:q - len(take_err)]
    if len(take) < q:   # 무작위가 모자라면 남은 틀린 것으로 채움
        take += [x for x in err if x not in take][:q - len(take)]
    stats[typ] = (len(pool), len(err), len(take_err), len(take))
    for x in take:
        added.append({'persona': 'h' + str(x['itin']), 'idx': x['i'], 'type': x['type'], 'gold': x['gold'], 'prompt': x['prompt'],
                      'completion': json.dumps({'item': x['gold']}, ensure_ascii=False)})
base = [json.loads(l) for l in open(src, encoding='utf-8')]
rows = base + added
rnd.shuffle(rows)
with open(dst, 'w', encoding='utf-8') as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')
none_rows = sum(1 for r in rows if r['gold'] is None)
print('원본', len(base), '+ 더함', len(added), '= 출력', len(rows), '/ 「없음」', none_rows, f'({100 * none_rows / len(rows):.1f}%)', '/ 시험과 겹쳐 뺀 문장', dropped_overlap)
for t, (n, e, te, tk) in stats.items():
    print(f'  {t}: 후보 {n} · 틀린 것 {e} · 틀린 것에서 뽑음 {te} · 합계 {tk}')
json.dump({'base_rows': len(base), 'added': len(added), 'rows': len(rows), 'none_rows': none_rows, 'dropped_overlap': dropped_overlap,
           'per_type': {t: {'pool': n, 'oos1_wrong': e, 'taken_wrong': te, 'taken': tk} for t, (n, e, te, tk) in stats.items()}, 'seed': SEED, 'mined_rows': len(mined)},
          open(os.path.join(HERE, 'results', 'train_oos2_report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
