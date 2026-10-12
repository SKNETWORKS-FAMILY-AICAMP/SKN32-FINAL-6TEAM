# D2 — 새 잡담 보류 세트(정답 = 없음 1,000문장): D 시험의 잡담 오지목 시드 변동(5.1 · 21.5 · 9.4%)이 시험 세트의 우연이 아닌지, 거부권(FrogNano) 효과가 새 문장에서도 나오는지, 잡담 보강 학습(oos)의 효과를 **학습에도 D 시험에도 안 쓴 문장**으로 보려고 만든다.
#  풀(서로 겹치지 않게): D 시험 = AI Hub 앞 20만 줄 필터 앞 1,000 + KoCulture 앞 300 / 잡담 보강 학습 = AI Hub 40~70만 줄 + KoCulture 300번째 이후 무작위 100(train_oos.jsonl) / **D2 = AI Hub 70~100만 줄에서 700 + KoCulture 300번째 이후에서 학습에 안 쓴 300**.
#  D 시험 잡담 · 학습 부정 예와 정확 일치 · 글자 3-gram 자카드 0.6 이상은 뺀다. 일정 프롬프트는 D 시험 프롬프트(all_prompts.json)의 일정에서 무작위로 골라 고객 질문만 바꾼다(형식 · 끝 지시 그대로).
# 사용: python build_d2_holdout.py <all_prompts.json> <train_oos.jsonl> <출력 all_prompts_d2.json>
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
TRAVEL = os.path.join(ROOT, 'datasets', 'travel')
sys.stdout.reconfigure(encoding='utf-8')
all_prompts, train_oos, dst = sys.argv[1], sys.argv[2], sys.argv[3]
rnd = random.Random(20261008)


def trigrams(t):
    t = re.sub(r'\s+', '', t)
    return {t[i:i + 3] for i in range(max(1, len(t) - 2))}


def jacc(a, b):
    return len(a & b) / max(1, len(a | b))


P = json.load(open(all_prompts, encoding='utf-8'))
QRE = re.compile(r'고객 질문: (.*?)\n\n', re.S)
test_chat = [QRE.search(p['prompt']).group(1).strip() for p in P if p['type'] == 'chitchat']
train_neg = []
for l in open(train_oos, encoding='utf-8'):
    r = json.loads(l)
    if r['type'].startswith('chitchat_neg'):
        train_neg.append(QRE.search(r['prompt']).group(1).strip())
assert len(test_chat) == 1300 and len(train_neg) == 400, (len(test_chat), len(train_neg))
ref = [(t, trigrams(t)) for t in test_chat + train_neg]
refset = {t for t, _ in ref}


def ok(t):
    if t in refset:
        return False
    tg = trigrams(t)
    return not any(jacc(tg, o) >= 0.6 for _, o in ref)


aihub = []
with open(os.path.join(TRAVEL, '020.주제별 텍스트 일상 대화 데이터', 'processed', 'chat_utterances.jsonl'), encoding='utf-8') as f:
    for k, line in enumerate(f):
        if k < 700000:
            continue
        if k >= 1000000:
            break
        x = json.loads(line)
        t = x['t'].strip()
        if 6 <= len(t) <= 80 and '여행' not in (x.get('subject') or '') and not re.fullmatch(r'[ㅋㅎㅠㅜ\s.?!~]+', t):
            aihub.append(t)
kocul = []
for line in open(os.path.join(TRAVEL, 'koculture_dialogues', 'processed', 'utterances.jsonl'), encoding='utf-8'):
    t = json.loads(line)['question'].strip()
    if 6 <= len(t) <= 80:
        kocul.append(t)
kocul = kocul[300:]


def take(pool, n):
    pool = list(dict.fromkeys(pool))
    rnd.shuffle(pool)
    out = []
    for t in pool:
        if ok(t):
            out.append(t)
            if len(out) == n:
                break
    return out


a = take(aihub, 700)
k = take(kocul, 300)
assert len(a) == 700 and len(k) == 300, (len(a), len(k))
base = [p for p in P if p['type'] not in ('chitchat', 'compound_intent')]
items = []
for n, t in enumerate([(x, 'AI Hub') for x in a] + [(x, 'KoCulture') for x in k]):
    q, src = t
    b = rnd.choice(base)
    head, rest = b['prompt'].split('고객 질문: ', 1)
    tail = rest.split('\n\n', 1)[1]
    items.append({'i': 900000 + n, 'set': 'd2', 'qi': n, 'type': 'chitchat_holdout_' + ('aihub' if src == 'AI Hub' else 'kocul'), 'gold': None, 'prompt': head + '고객 질문: ' + q + '\n\n' + tail})
json.dump(items, open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
mx = max(jacc(trigrams(i_), o) for i_ in a + k for _, o in ref)
print(json.dumps({'AI Hub 후보': len(aihub), 'KoCulture 후보': len(kocul), 'D2 문장': len(items), '최대 자카드(D2 × 시험 잡담 · 학습 부정 예)': round(mx, 3)}, ensure_ascii=False))
