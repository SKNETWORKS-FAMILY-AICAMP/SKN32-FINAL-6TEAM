# Y2 분류 게이트(§50) — 「일정 문의인가」 2지선다 학습·시험용 문장 모음을 만든다.
#  라벨: 무관(0) = 주제 밖 유형(out_of_scope) · AI Hub 잡담, 관련(1) = 그 밖의 모든 유형(없지만 있을 법한 곳·비슷한 이름 가짜 포함).
#  시험 세트 문장(mix8·mix9)은 학습에 쓰지 않는다. 잡담: 학습 3,000개(시험 표본 chat_sample_3000 과 겹치지 않음) · 시험 = chat_sample_3000.
# 출력: fixtures/gate_sents.json {"texts": [...]} · fixtures/gate_meta.json [{"i": 문장 번호, "kind": "lab|chat_train|chat_test", "set":…, "qi":…, "label": 0|1, "type":…}]
import json, os, random, re
HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, '..', '..', '..', 'datasets', 'travel', '020.주제별 텍스트 일상 대화 데이터', 'processed')
texts, idx, meta = [], {}, []


def add(t):
    if t not in idx:
        idx[t] = len(texts)
        texts.append(t)
    return idx[t]


for w in ('heavy', 'mix4', 'mix5', 'mix6', 'mix7', 'mix8', 'mix9'):
    st = json.load(open(os.path.join(HERE, 'fixtures', f'{w}.json'), encoding='utf-8'))['sets'][w]
    for qi, x in enumerate(st['qs']):
        meta.append({'i': add(x['q']), 'kind': 'lab', 'set': w, 'qi': qi, 'label': 0 if x['type'] == 'out_of_scope' else 1, 'type': x['type'],
                     'split': x.get('split')})
sample = json.load(open(os.path.join(D, 'chat_sample_3000.json'), encoding='utf-8'))
for k, t in enumerate(sample):
    meta.append({'i': add(t), 'kind': 'chat_test', 'set': 'chat', 'qi': k, 'label': 0, 'type': 'chat'})
test_set = set(sample)
pool = [json.loads(l)['t'] for l in open(os.path.join(D, 'chat_utterances.jsonl'), encoding='utf-8')]
pool = [t for t in pool if 5 <= len(t) <= 40 and len(re.findall(r'[가-힣]', t)) / len(t) >= 0.5 and t not in test_set]
rnd = random.Random(20261003)
for k, t in enumerate(rnd.sample(pool, 3000)):
    meta.append({'i': add(t), 'kind': 'chat_train', 'set': 'chat', 'qi': k, 'label': 0, 'type': 'chat'})
json.dump({'texts': texts}, open(os.path.join(HERE, 'fixtures', 'gate_sents.json'), 'w', encoding='utf-8'), ensure_ascii=False)
json.dump(meta, open(os.path.join(HERE, 'fixtures', 'gate_meta.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('문장', len(texts), '· 행', len(meta), '· 관련', sum(m['label'] for m in meta), '· 무관', sum(1 - m['label'] for m in meta))
