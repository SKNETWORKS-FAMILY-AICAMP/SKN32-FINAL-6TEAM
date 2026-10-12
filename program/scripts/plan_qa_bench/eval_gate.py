# Y2 분류 게이트(§50) — 「일정 문의인가」 2지선다 헤드(로지스틱)를 학습하고 확률 파일을 만든다.
#  임베딩: gate_emb_base.npy(Qwen3-Embedding-0.6B 고정) · gate_emb_e16d.npy(e16d LoRA) — 서버 gate_embed.py 가 만든다(results/ 로 복사해 둔다).
#  기존 5세트: 세트 하나를 빼고(+ AI Hub 잡담 학습 3,000) 학습해 그 세트의 확률을 낸다(교차검증). mix8·mix9·잡담 시험 표본: 5세트 전부 + 잡담 학습으로 학습한 헤드의 확률.
#  출력: results/gate_p_<base|e16d>.json = {"p": {세트: {문제번호: p(관련)}}, "chat_test": [p…3000]} + 표준출력에 지표(AUROC·정확도·잡담 오탐).
# 사용: python eval_gate.py [--md 출력파일]
import json, os, sys
import numpy as np
from sklearn.linear_model import LogisticRegression

HERE = os.path.dirname(os.path.abspath(__file__))
R = lambda f: os.path.join(HERE, 'results', f)
meta = json.load(open(os.path.join(HERE, 'fixtures', 'gate_meta.json'), encoding='utf-8'))
LAB = ['heavy', 'mix4', 'mix5', 'mix6', 'mix7']
TEST = ['mix8', 'mix9']


def auroc(y, s):
    pos = [a for a, b in zip(s, y) if b == 1]
    neg = [a for a, b in zip(s, y) if b == 0]
    if not pos or not neg:
        return float('nan')
    return sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))


out = []
for tag in ('base', 'e16d'):
    f = R(f'gate_emb_{tag}.npy')
    if not os.path.exists(f):
        out.append(f'(임베딩 {tag} 없음 — 서버 계산 대기)')
        continue
    X = np.load(f).astype('float32')
    rows = {k: [m for m in meta if m['kind'] == k] for k in ('lab', 'chat_train', 'chat_test')}
    ct = rows['chat_train']
    pdict = {w: {} for w in LAB + TEST}

    def fit(train_rows):
        Xt = np.array([X[m['i']] for m in train_rows])
        yt = np.array([m['label'] for m in train_rows])
        return LogisticRegression(C=4.0, max_iter=3000, class_weight='balanced').fit(Xt, yt)

    for w in LAB:
        clf = fit([m for m in rows['lab'] if m['set'] in LAB and m['set'] != w] + ct)
        for m in rows['lab']:
            if m['set'] == w:
                pdict[w][m['qi']] = float(clf.predict_proba(X[m['i']][None])[0, 1])
    clf_all = fit([m for m in rows['lab'] if m['set'] in LAB] + ct)
    for m in rows['lab']:
        if m['set'] in TEST:
            pdict[m['set']][m['qi']] = float(clf_all.predict_proba(X[m['i']][None])[0, 1])
    chat_p = [float(clf_all.predict_proba(X[m['i']][None])[0, 1]) for m in rows['chat_test']]
    json.dump({'p': {w: {str(k): v for k, v in d.items()} for w, d in pdict.items()}, 'chat_test': chat_p}, open(R(f'gate_p_{tag}.json'), 'w'))
    out.append(f'### 게이트 헤드 — 임베딩 {tag}')
    out.append('| 세트 | 관련 문제 | 무관 문제 | AUROC | p≥0.5 정확도 | 관련을 무관으로 거름 | 무관을 관련으로 통과 |')
    out.append('|---|---:|---:|---:|---:|---:|---:|')
    for w in LAB + TEST:
        ms = [m for m in rows['lab'] if m['set'] == w]
        y = [m['label'] for m in ms]
        s = [pdict[w][m['qi']] for m in ms]
        acc = sum((a >= 0.5) == (b == 1) for a, b in zip(s, y)) / len(y)
        fn = sum(1 for a, b in zip(s, y) if b == 1 and a < 0.5)
        fp = sum(1 for a, b in zip(s, y) if b == 0 and a >= 0.5)
        out.append(f'| {w}{" (교차검증)" if w in LAB else " (시험)"} | {sum(y)} | {len(y) - sum(y)} | {auroc(y, s):.3f} | {acc:.1%} | {fn} | {fp} |')
    fpc = sum(1 for p in chat_p if p >= 0.5)
    out.append(f'| 잡담 시험 표본 3,000 | 0 | 3000 | — | — | — | {fpc} ({fpc / 3000:.1%}) |')
    out.append('')
print('\n'.join(out))
if '--md' in sys.argv:
    open(sys.argv[sys.argv.index('--md') + 1], 'w', encoding='utf-8').write('\n'.join(out) + '\n')
