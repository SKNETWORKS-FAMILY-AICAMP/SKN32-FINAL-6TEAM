# 앞단 v3(e16d) 학습 자료 — 기존 train_pairs.json(6,000 그룹) + (가) 채팅 말투 변형 사본 1,800 그룹 + (나) 실제 잡담 「정답 없음」 2,200 그룹.
#  변형: 끝말 붙이기·붙여쓰기·낱글자 받침 바꾸기·끝 글자 자르기 중 1~2개(AI Hub 일상 대화의 끝말 빈도를 따른 목록). 잡담은 시험용 표본(chat_sample_3000)과 겹치지 않는 문장.
#  잡담 그룹의 후보 문서는 기존 그룹의 일정 문서 목록(모두 정답 아님)이고 행마다 chat=True 를 붙인다 — 학습 손실이 이 표시로 점수 상한(0.10)을 건다.
# 사용: python build_train_chat.py → fixtures/train_pairs_chat.json (git 무시)
import collections, json, os, random, re

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, '..', '..', '..', 'datasets', 'travel', '020.주제별 텍스트 일상 대화 데이터', 'processed')
d = json.load(open(os.path.join(HERE, 'fixtures', 'train_pairs.json'), encoding='utf-8'))
rnd = random.Random(20261002)
g = collections.defaultdict(list)
for x in d['train']:
    g[x['g']].append(x)
pos_groups = [gid for gid, xs in g.items() if any(x['label'] for x in xs)]
ENDS = ['ㅋㅋ', 'ㅠㅠ', '..', '임', '얌', '여', '욤', 'ㅇㅇ', 'ㅎㅎ', '?', '!!', '용', '염']
BATCHIM = ['ㄴ', 'ㅁ', 'ㅇ', 'ㄹ', '']
CHO = 0xAC00


def typo(q):
    idx = [i for i, ch in enumerate(q) if '가' <= ch <= '힣']
    if not idx:
        return q
    i = rnd.choice(idx)
    code = ord(q[i]) - CHO
    jong = code % 28
    new = rnd.choice([0, 1, 4, 8, 16, 21])      # 받침 없음·ㄱ·ㄴ·ㄹ·ㅁ·ㅇ
    if new == jong:
        return q
    return q[:i] + chr(CHO + code - jong + new) + q[i + 1:]


def noisy(q):
    ops = rnd.sample(['end', 'nospace', 'typo', 'cut'], rnd.choice([1, 2]))
    for op in ops:
        if op == 'end':
            q = q + rnd.choice(ENDS)
        elif op == 'nospace' and ' ' in q:
            q = q.replace(' ', '')
        elif op == 'typo':
            q = typo(q)
        elif op == 'cut' and len(q) >= 5:
            q = q[:-1]
    return q


aug = []
for k, gid in enumerate(rnd.sample(pos_groups, 1800)):
    for x in g[gid]:
        y = dict(x)
        y['g'] = 10_000_000 + gid
        y['q'] = None
        aug.append(y)
    q2 = noisy(g[gid][0]['q'])
    for y in aug[-len(g[gid]):]:
        y['q'] = q2
# 잡담 그룹
sample3000 = set(json.load(open(os.path.join(D, 'chat_sample_3000.json'), encoding='utf-8')))
pool = [json.loads(l)['t'] for l in open(os.path.join(D, 'chat_utterances.jsonl'), encoding='utf-8')]
pool = [t for t in pool if 5 <= len(t) <= 40 and len(re.findall(r'[가-힣]', t)) / len(t) >= 0.5 and t not in sample3000]
rnd.shuffle(pool)
chat_rows = []
all_gids = sorted(g)
for k, t in enumerate(pool[:2200]):
    src = g[rnd.choice(all_gids)]
    for x in src:
        chat_rows.append({'g': 20_000_000 + k, 'q': t, 'doc': x['doc'], 'label': 0, 'chat': True})
out = {'train': d['train'] + aug + chat_rows, 'val': d['val']}
json.dump(out, open(os.path.join(HERE, 'fixtures', 'train_pairs_chat.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('그룹: 원본', len(g), '+ 변형', 1800, '+ 잡담', 2200, '= ', len(g) + 4000)
for gid in rnd.sample(pos_groups, 0):
    pass
ex = [(g[gid][0]['q'], None) for gid in rnd.sample(pos_groups, 8)]
print('변형 예:', [(q, noisy(q)) for q, _ in ex])
print('잡담 예:', pool[:5])
