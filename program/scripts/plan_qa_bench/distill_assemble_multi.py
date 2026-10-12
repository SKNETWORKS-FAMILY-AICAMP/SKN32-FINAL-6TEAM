# 「여러 항목을 내는 학생」용 학습 자료 — distill_assemble.py 가 이미 거른 train.jsonl·val.jsonl 의 같은 문제를 그대로 쓰고(제외·분할 동일),
# 지시문과 정답 형식만 {"items": [번호, ...]} 로 바꾼다. 요청 둘은 gold_set 을 먼저 말한 순서대로 둘 다, 한 항목은 하나, 없음은 빈 배열.
# 사용: python distill_assemble_multi.py   → fixtures/distill/train_multi.jsonl · val_multi.jsonl
import json, os, re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, 'fixtures', 'distill')
OLD_TAIL = re.compile(r'이 질문이 가리키는 일정 항목 번호 하나를 item 에 넣어라\. .*$', re.S)
NEW_TAIL = ('이 질문이 가리키는 일정 항목 번호를 모두 items 배열에 넣어라(한 항목이면 하나, 두 항목을 함께 말했으면 먼저 말한 순서대로 둘). '
            '질문이 이 일정에 없는 장소·일반 정보·다른 식당·다른 명소를 묻는다면 빈 배열. 확실하지 않으면 빈 배열.'
            '\n\n답은 JSON 한 줄로만: {"items": [번호, ...]} 또는 {"items": []}')
fx = {}
for i in range(1, 11):
    name = f'distill_p{i:02d}'
    fx[f'p{i:02d}'] = json.load(open(os.path.join(D, f'{name}.json'), encoding='utf-8'))['sets'][name]['qs']
for split in ('train', 'val'):
    rows = [json.loads(l) for l in open(os.path.join(D, f'{split}.jsonl'), encoding='utf-8')]
    out, kinds = [], Counter()
    for r in rows:
        q = fx[r['persona']][r['idx']]
        items = q.get('gold_set') or ([q['gold']] if q['gold'] is not None else [])
        assert items == [] or items[0] == q['gold'], (r['persona'], r['idx'], items, q['gold'])
        assert OLD_TAIL.search(r['prompt']), (r['persona'], r['idx'])
        out.append({**r, 'prompt': OLD_TAIL.sub(NEW_TAIL, r['prompt']), 'completion': json.dumps({'items': items}, ensure_ascii=False), 'gold_set': items})
        kinds[len(items)] += 1
    with open(os.path.join(D, f'{split}_multi.jsonl'), 'w', encoding='utf-8') as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(split, len(out), '정답 항목 수별', dict(kinds))
