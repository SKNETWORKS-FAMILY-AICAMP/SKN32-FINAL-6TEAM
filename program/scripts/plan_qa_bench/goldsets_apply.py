# 하위 작업이 낸 요청 둘 정답 목록(goldset_out.json)을 검증해 fixtures/gold_sets.json 으로 만든다.
#  검증: ① 모든 번호가 그 세트 일정에 있다 ② 목록의 첫 항목이 기존 정답(gold)과 같은가(요청 둘의 기존 규칙 = 먼저 말한 항목) — 다르면 출력한다.
#  결과 gold_sets.json = {세트: {문제번호: [정답 번호들]}} — 요청 둘은 목록, 나머지 문제는 [gold] 또는 [](정답 없음). 기존 fixtures/*.json 은 건드리지 않는다.
# 사용: python goldsets_apply.py <goldset_out.json>
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
raw = json.load(open(sys.argv[1], encoding='utf-8'))
out, bad_first, bad_id = {}, [], []
for w in ('mix8', 'mix9', 'mix10', 'mix11', 'mix12'):
    job = json.load(open(os.path.join(HERE, 'fixtures', f'{w}.json'), encoding='utf-8'))['sets'][w]
    ids = {i['id'] for i in job['items']}
    d = {}
    for k, q in enumerate(job['qs']):
        key = f'{w}-{k}'
        if q['type'] == 'compound_intent':
            L = raw.get(key)
            assert L is not None, f'{key} 정답 목록 없음'
            if any(x not in ids for x in L):
                bad_id.append((key, L))
            if not L or L[0] != q['gold']:
                bad_first.append((key, q['q'], q['gold'], L))
            d[str(k)] = L
        else:
            d[str(k)] = [q['gold']] if q['gold'] is not None else []
    out[w] = d
json.dump(out, open(os.path.join(HERE, 'fixtures', 'gold_sets.json'), 'w', encoding='utf-8'), ensure_ascii=False)
comp = [(w, k) for w in out for k, v in out[w].items() if len(v) >= 2]
print('요청 둘 정답 목록', len(raw), '문제 · 항목 2개 이상', len(comp), '· 없는 번호', len(bad_id), '· 첫 항목이 기존 정답과 다름', len(bad_first))
for r in bad_id[:5]:
    print('  번호 오류', r)
for r in bad_first:
    print('  첫 항목 다름', r)
