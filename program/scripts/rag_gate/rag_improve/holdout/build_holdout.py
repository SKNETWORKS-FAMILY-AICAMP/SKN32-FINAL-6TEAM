# 보류(holdout) 세트 만들기 — 질문은 Claude 작업자 1이 주제 목록만 보고 썼고(holdout_questions_raw.json), 정답은 Claude 작업자 2가 규정 조각 글만 보고 따로 달았다(holdout_labels_raw.json).
#  둘 다 어떤 검색 결과도 보지 않았다. 이 세트는 개선 방법을 고르는 데 쓰지 않고, 마지막에 개선 전 · 후를 한 번씩만 잰다.
#  한계: 질문 작성자와 라벨러가 모두 Claude(같은 계열)다 — 합성 질문이다.
import json
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
CH = json.load(open(os.path.join(HERE, '..', '..', 'fixtures', 'policy_chunks.json'), encoding='utf-8'))
IDS = {c['source'] for c in CH}
raw = json.load(open(os.path.join(HERE, 'holdout_questions_raw.json'), encoding='utf-8'))['questions']
lab = json.load(open(os.path.join(HERE, 'holdout_labels_raw.json'), encoding='utf-8'))['labels']
assert len(raw) == len(lab) == 140
out, bad = [], 0
for r, l in zip(raw, lab):
    assert r['q'] == l['q'], (r['q'], l['q'])
    gold = [g for g in l['gold'] if g in IDS]
    part = [g for g in l['partial'] if g in IDS]
    bad += (len(gold) != len(l['gold'])) + (len(part) != len(l['partial']))
    typ = l['type']
    if typ == 'answerable' and not gold:
        typ = 'near_miss'
    out.append({'q': r['q'], 'type': typ, 'gold': gold, 'partial': part, 'writer_intent': r['intent'], 'note': l['note']})
json.dump({'questions': out}, open(os.path.join(HERE, 'holdout_questions.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print('질문', len(out), '유형', dict(Counter(o['type'] for o in out)), '존재하지 않는 조각 번호', bad)
print('작성자 의도 대 라벨 유형', dict(Counter((o['writer_intent'], o['type']) for o in out)))
print('답 있음 질문의 정답 줄 수 분포', dict(Counter(len(o['gold']) for o in out if o['type'] == 'answerable')))
