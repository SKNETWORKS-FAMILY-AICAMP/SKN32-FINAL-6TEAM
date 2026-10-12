# mix10 의 게이트 확률 — eval_gate.py 의 e16d 헤드와 같은 데이터·같은 설정(5세트 전부 + 잡담 학습 3,000, 로지스틱 C=4, class_weight=balanced)으로 다시 학습해
#  mix10 문장의 확률을 results/gate_p_e16d.json 의 p['mix10'] 에 덧붙인다(다른 세트 값은 그대로).
# 사용: python eval_gate_mix10.py   (results/gate_emb_e16d.npy · gate_emb_e16d_mix10.npy 가 있어야 한다)
import json, os
import numpy as np
from sklearn.linear_model import LogisticRegression

HERE = os.path.dirname(os.path.abspath(__file__))
R = lambda f: os.path.join(HERE, 'results', f)
meta = json.load(open(os.path.join(HERE, 'fixtures', 'gate_meta.json'), encoding='utf-8'))
LAB = ['heavy', 'mix4', 'mix5', 'mix6', 'mix7']
X = np.load(R('gate_emb_e16d.npy')).astype('float32')
X10 = np.load(R('gate_emb_e16d_mix10.npy')).astype('float32')
rows = {k: [m for m in meta if m['kind'] == k] for k in ('lab', 'chat_train')}
train = [m for m in rows['lab'] if m['set'] in LAB] + rows['chat_train']
clf = LogisticRegression(C=4.0, max_iter=3000, class_weight='balanced').fit(np.array([X[m['i']] for m in train]), np.array([m['label'] for m in train]))
old = json.load(open(R('gate_p_e16d.json')))
# 재현 확인: mix9 확률이 앞서 저장한 값과 같아야 한다(같은 분류기)
chk = [m for m in rows['lab'] if m['set'] == 'mix9'][:20]
diff = max(abs(float(clf.predict_proba(X[m['i']][None])[0, 1]) - old['p']['mix9'][str(m['qi'])]) for m in chk)
print('mix9 재현 최대 차이', diff)
assert diff < 1e-6, '분류기가 앞서 쓴 것과 다르다'
st = json.load(open(os.path.join(HERE, 'fixtures', 'mix10.json'), encoding='utf-8'))['sets']['mix10']
assert len(X10) == len(st['qs'])
old['p']['mix10'] = {str(k): float(clf.predict_proba(X10[k][None])[0, 1]) for k in range(len(X10))}
json.dump(old, open(R('gate_p_e16d.json'), 'w'))
print('mix10 게이트 확률', len(X10))
