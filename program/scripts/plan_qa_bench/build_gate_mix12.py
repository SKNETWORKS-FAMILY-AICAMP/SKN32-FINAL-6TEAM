# mix12 의 질문 문장만 모아 게이트 임베딩 입력(fixtures/gate_sents_mix12.json)을 만든다 — 앞서 만든 gate_sents.json·gate_meta.json 의 번호는 건드리지 않는다.
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
st = json.load(open(os.path.join(HERE, 'fixtures', 'mix12.json'), encoding='utf-8'))['sets']['mix12']
json.dump({'texts': [x['q'] for x in st['qs']]}, open(os.path.join(HERE, 'fixtures', 'gate_sents_mix12.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('mix12 문장', len(st['qs']))
