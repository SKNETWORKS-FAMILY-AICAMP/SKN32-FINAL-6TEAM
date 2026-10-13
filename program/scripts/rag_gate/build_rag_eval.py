# Codex 가 낸 규정 질문 시험 세트(180문제: 답 있음 100 · 코퍼스에 없음 40 · 비슷하지만 다름 20 · 주제 밖 20)를 검증해 fixtures/rag_questions.json 으로 저장한다.
#  검증만 한다: 형식 · 정답 출처 id 존재 · 정답 줄(customer line)이 있는 절인지 · 유형별 개수 · 중복. 문장·정답은 고치지 않고, 뺄 때는 사유를 출력한다(MANUAL_DROP).
# 사용: python build_rag_eval.py <Codex 가 낸 JSON 파일>
import json, os, re, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
raw = open(sys.argv[1], encoding='utf-8').read()
d = json.loads(re.search(r'\{.*\}', raw, re.S).group(0))
ch = json.load(open(os.path.join(HERE, 'fixtures', 'policy_chunks.json'), encoding='utf-8'))
LINE = {c['source']: c['line'] for c in ch if c['line']}
ALL = {c['source'] for c in ch}
MANUAL_DROP = {}   # {질문 문장: 사유} — 검토 뒤 채운다
out, dropped, seen = [], [], set()
for x in d['questions']:
    q = x['q'].strip()
    if q in MANUAL_DROP:
        dropped.append((q, MANUAL_DROP[q]))
        continue
    if q in seen:
        dropped.append((q, '문장 중복'))
        continue
    seen.add(q)
    gold = list(x.get('gold') or [])
    bad = [g for g in gold if g not in LINE]
    if bad:
        dropped.append((q, f'정답 출처가 없거나 고객용 문장이 없는 절: {bad}'))
        continue
    if x['type'] == 'answerable' and not gold:
        dropped.append((q, '답 있음인데 정답이 비어 있음'))
        continue
    if x['type'] != 'answerable' and gold:
        dropped.append((q, '답 없음 유형인데 정답이 있음'))
        continue
    out.append({'q': q, 'type': x['type'], 'gold': gold, 'note': x.get('note', '')})
json.dump({'questions': out}, open(os.path.join(HERE, 'fixtures', 'rag_questions.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('문제', len(out), '· 유형', dict(Counter(x['type'] for x in out)))
srcs = Counter(g for x in out if x['type'] == 'answerable' for g in x['gold'][:1])
print('답 있음이 겨냥한 서로 다른 출처', len(srcs), '· 출처당 최대', max(srcs.values()) if srcs else 0)
print('버린 문제', len(dropped), dropped)
